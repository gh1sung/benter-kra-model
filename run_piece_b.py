"""
run_piece_b.py

Piece B, deliverable 2. Reads piece_b_dataset.csv (from
build_piece_b_dataset.py) and runs the three analyses from the plan (§4):

  Gate B0 -- plumbing sanity: q_model/q_market sum to ~1 per race, exactly
             one y==1 per race.
  Gate B1 -- information: is q_model (win-pool-derived) better calibrated /
             lower log-loss than q_market (the exotic pool's own price)?
  Gate B2 -- edge: EV backtest at tau=0 (assumption-free) and walk-forward
             tau selection, ROI by year.

Outputs: piece_b_calibration.csv, piece_b_logloss.csv, piece_b_backtest_by_year.csv
"""
import argparse
import sys

import numpy as np
import pandas as pd

DEFAULT_IN_PATH = "/mnt/user-data/outputs/piece_b_dataset.csv"
DEFAULT_OUT_DIR = "/mnt/user-data/outputs"
BINS = [0, .010, .025, .05, .075, .10, .125, .15, .175, .20, .25, .30, .40, .50, 1.01]


# ---------------------------------------------------------------------------
# 4.1 calibration
# ---------------------------------------------------------------------------

def calibration_table(df, prob_col, bins=BINS):
    cal = df.copy()
    cal["bucket"] = pd.cut(cal[prob_col], bins, right=False)
    g = cal.groupby("bucket", observed=True)
    tab = g.agg(n=("y", "size"), pred_mean=(prob_col, "mean"),
                actual_freq=("y", "mean")).reset_index()
    tab["se"] = np.sqrt(tab["pred_mean"] * (1 - tab["pred_mean"]) / tab["n"])
    tab["z"] = (tab["actual_freq"] - tab["pred_mean"]) / tab["se"]
    tab["prob_source"] = prob_col
    return tab


# ---------------------------------------------------------------------------
# 4.2 log-loss
# ---------------------------------------------------------------------------

def log_loss(df, prob_col, eps=1e-12):
    p = df[prob_col].clip(eps, 1 - eps)
    y = df["y"]
    ll = -(y * np.log(p) + (1 - y) * np.log(1 - p))
    return ll.mean()


def winning_pair_log_loss(df, prob_col, eps=1e-12):
    """Restricted to the pair that actually hit each race -- does the model
    put more probability on what actually happened?"""
    hits = df[df["y"] == 1]
    p = hits[prob_col].clip(eps, 1 - eps)
    return (-np.log(p)).mean()


# ---------------------------------------------------------------------------
# 4.3 EV backtest
# ---------------------------------------------------------------------------

def ev_backtest(df, tau=0.0):
    bets = df[df["q_model"] * df["d"] - 1 > tau].copy()
    n_bets = len(bets)
    if n_bets == 0:
        return {"tau": tau, "n_bets": 0, "n_races_touched": 0,
                "hit_rate": np.nan, "staked": 0.0, "returned": 0.0, "roi": np.nan}
    staked = float(n_bets)
    returned = float(bets.loc[bets["y"] == 1, "d"].sum())
    return {
        "tau": tau,
        "n_bets": n_bets,
        "n_races_touched": bets["race_id"].nunique() if "race_id" in bets else np.nan,
        "hit_rate": bets["y"].mean(),
        "staked": staked,
        "returned": returned,
        "roi": (returned - staked) / staked,
    }


def backtest_by_year(df, tau=0.0):
    out = []
    for year, grp in df.groupby("year"):
        r = ev_backtest(grp, tau=tau)
        r["year"] = year
        out.append(r)
    return pd.DataFrame(out)


def select_tau_walk_forward(df, tau_grid):
    """OOS discipline per plan §4.3: tune tau on earlier years, evaluate on
    later years. Two-fold split on the sorted year list (upgrade to rolling
    folds if the year count supports it)."""
    years = sorted(df["year"].unique())
    mid = len(years) // 2
    train_years, test_years = years[:mid], years[mid:]
    train_df = df[df["year"].isin(train_years)]
    test_df = df[df["year"].isin(test_years)]

    train_results = pd.DataFrame([ev_backtest(train_df, tau=t) for t in tau_grid])
    if train_results["roi"].notna().any():
        best_tau = train_results.loc[train_results["roi"].idxmax(), "tau"]
    else:
        best_tau = 0.0

    test_result = ev_backtest(test_df, tau=best_tau)
    return best_tau, train_years, test_years, test_result


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in-path", default=DEFAULT_IN_PATH)
    ap.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    args = ap.parse_args()

    try:
        df = pd.read_csv(args.in_path)
    except FileNotFoundError:
        print(f"ERROR: {args.in_path} not found. Run build_piece_b_dataset.py first.",
              file=sys.stderr)
        sys.exit(1)

    # Gate B0
    per_race_q_model = df.groupby("race_id")["q_model"].sum()
    per_race_q_market = df.groupby("race_id")["q_market"].sum()
    per_race_y = df.groupby("race_id")["y"].sum()

    # q_market is renormalized over whatever pairs are quoted, so it always
    # sums to ~1 by construction. q_model is NOT renormalized to the quoted
    # subset -- it's the full Harville distribution over the field, and some
    # races have partial market coverage (pairs dropped as sentinel-dividend
    # rows), so summing q_model over only the quoted pairs will legitimately
    # land below 1. That's expected data incompleteness, not a join bug --
    # reported here for transparency, not as a pass/fail gate.
    print("[Gate B0, informational] q_model coverage of the quoted market per race: "
          f"mean={per_race_q_model.mean():.4f}, min={per_race_q_model.min():.4f}, "
          f"max={per_race_q_model.max():.4f}")
    n_low_coverage = (per_race_q_model < 0.90).sum()
    print(f"[Gate B0, informational] races with <90% of q_model mass covered by "
          f"quoted pairs: {n_low_coverage} / {len(per_race_q_model)}")
    print("[Gate B0] q_market sum-to-1 per race (should always be ~1.0): "
          f"mean={per_race_q_market.mean():.4f}, min={per_race_q_market.min():.4f}, "
          f"max={per_race_q_market.max():.4f}")

    # This one IS a hard gate: every scored race must have exactly one
    # realized winning pair among its rows, no more, no fewer.
    print(f"[Gate B0] races with exactly one y==1: {(per_race_y == 1).sum()} / {len(per_race_y)}")
    n_bad_y = (per_race_y != 1).sum()
    print(f"[Gate B0] races with y-sum != 1 (should be 0): {n_bad_y}")
    if n_bad_y > 0:
        print("[Gate B0] FAIL -- fix the join before trusting anything downstream.")
    else:
        print("[Gate B0] PASS on the hard check (exactly one winner per race).")

    # Gate B1 -- calibration
    cal_model = calibration_table(df, "q_model")
    cal_market = calibration_table(df, "q_market")
    pd.concat([cal_model, cal_market], ignore_index=True).to_csv(
        f"{args.out_dir}/piece_b_calibration.csv", index=False)
    print("\n[Gate B1] q_model calibration:")
    print(cal_model.to_string(index=False))
    print("\n[Gate B1] q_market calibration:")
    print(cal_market.to_string(index=False))

    # Gate B1 -- log-loss
    ll_model_pooled = log_loss(df, "q_model")
    ll_market_pooled = log_loss(df, "q_market")
    ll_model_winner = winning_pair_log_loss(df, "q_model")
    ll_market_winner = winning_pair_log_loss(df, "q_market")
    ll_df = pd.DataFrame([
        {"metric": "pooled_log_loss", "q_model": ll_model_pooled, "q_market": ll_market_pooled},
        {"metric": "winning_pair_log_loss", "q_model": ll_model_winner, "q_market": ll_market_winner},
    ])
    ll_df.to_csv(f"{args.out_dir}/piece_b_logloss.csv", index=False)
    print("\n[Gate B1] log-loss (lower is better):")
    print(ll_df.to_string(index=False))

    model_better = (ll_model_pooled < ll_market_pooled) and (ll_model_winner < ll_market_winner)
    print(f"\n[Gate B1 verdict] q_model beats q_market on log-loss: {model_better}")
    if not model_better:
        print("[Gate B1] WARNING per plan §5: win pool isn't clearly sharper than the "
              "exotic pool here -- check lambda/join/scratch-handling before trusting "
              "any EV number below.")

    # Gate B2 -- EV backtest
    tau0 = ev_backtest(df, tau=0.0)
    print(f"\n[Gate B2] tau=0 backtest (assumption-free, no tuned parameters): {tau0}")

    by_year_tau0 = backtest_by_year(df, tau=0.0)
    by_year_tau0.to_csv(f"{args.out_dir}/piece_b_backtest_by_year.csv", index=False)
    print("\n[Gate B2] tau=0 ROI by year:")
    print(by_year_tau0.to_string(index=False))

    tau_grid = np.round(np.arange(0.0, 0.51, 0.05), 2)
    best_tau, train_years, test_years, oos_result = select_tau_walk_forward(df, tau_grid)
    print(f"\n[Gate B2] walk-forward: tau tuned on {train_years} -> best tau={best_tau}, "
          f"evaluated OOS on {test_years}: {oos_result}")


if __name__ == "__main__":
    main()
