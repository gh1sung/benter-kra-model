"""
validate_piece_a.py

Piece A, deliverable 4 -- the actual Gate A1 (and, if needed, A2) run.

Pipeline:
  1. Load win_odds_5yr.csv -> per-race win probabilities (overround-stripped).
  2. Load exotic_outcomes.csv (from build_exotic_outcomes.py) -> realized
     top-2/top-3 per race.
  3. Join on (date, region, race_no, gate_no==back_num), Jeju dropped,
     부산경남<->부산 mapped, re-normalize win probs after intersecting the
     two sides' runner lists (scratches / mismatches dropped).
  4. Run harville_engine.quinella_probs() per race, pool across races,
     bucket by predicted probability, compare to actual hit frequency
     (same style as fit_engine.calibration_table).
  5. Three diagnostics: favorite-in-quinella bias check, per-region split,
     by-field-size split.
  6. If Gate A1 shows the known favorite-place overestimate, re-run with a
     fitted lambda (Gate A2) via a simple 1-D grid search minimizing pooled
     quinella log-loss.

Outputs: piece_a_calibration.csv, piece_a_favorite_bias.csv,
piece_a_by_region.csv, piece_a_by_field_size.csv, and (if Gate A2 runs)
piece_a_calibration_lambda_fit.csv.
"""
import argparse
import sys

import numpy as np
import pandas as pd

from harville_engine import quinella_probs, place_probs

DEFAULT_ODDS_PATH = "/mnt/project/win_odds_5yr.csv"
DEFAULT_OUTCOMES_PATH = "/mnt/user-data/outputs/exotic_outcomes.csv"
DEFAULT_OUT_DIR = "/mnt/user-data/outputs"

REGION_MAP = {"부산경남": "부산"}  # odds-side label -> RDS-side label
BINS = [0, .010, .025, .05, .075, .10, .125, .15, .175, .20, .25, .30, .40, .50, 1.01]


# ---------------------------------------------------------------------------
# load + join
# ---------------------------------------------------------------------------

def load_odds(path):
    df = pd.read_csv(path)
    df = df[df["track"] != "제주"].copy()  # Jeju always dropped
    df["region"] = df["track"].replace(REGION_MAP)
    return df[["date", "region", "race_no", "gate_no", "odds"]]


def load_outcomes(path):
    df = pd.read_csv(path)
    df["race_date"] = pd.to_datetime(df["race_date"])
    df["date"] = df["race_date"].dt.strftime("%Y%m%d").astype(int)
    return df


def build_race_records(odds_df, outcomes_df):
    """For each race present on both sides, return a dict with the
    re-normalized win-prob vector (keyed by back_num/gate_no) and the
    realized top-2/top-3, restricted to horses present in both sources."""
    odds_groups = {
        keys: grp for keys, grp in odds_df.groupby(["date", "region", "race_no"])
    }

    records = []
    n_join_total = 0
    n_dropped_no_odds_match = 0
    n_dropped_top2_horse_missing = 0
    n_dropped_field_too_small = 0

    for _, row in outcomes_df.iterrows():
        key = (row["date"], row["region"], row["race_no"])
        n_join_total += 1
        odds_grp = odds_groups.get(key)
        if odds_grp is None or odds_grp.empty:
            n_dropped_no_odds_match += 1
            continue

        starters = set(int(s) for s in str(row["starters"]).split("|") if s)
        odds_gates = set(odds_grp["gate_no"].astype(int))
        field = sorted(starters & odds_gates)
        if len(field) < 2:
            n_dropped_field_too_small += 1
            continue

        top2 = row["top2_pair"]
        top2_pair = None
        if isinstance(top2, str) and top2:
            a, b = (int(x) for x in top2.split("|"))
            if a in field and b in field:
                top2_pair = frozenset((a, b))
            else:
                n_dropped_top2_horse_missing += 1
                continue  # can't score this race for quinella

        sub = odds_grp[odds_grp["gate_no"].astype(int).isin(field)]
        raw = 1.0 / sub.set_index(sub["gate_no"].astype(int))["odds"]
        p = (raw / raw.sum()).to_dict()

        records.append({
            "race_id": f"{row['date']}_{row['region']}_{row['race_no']}",
            "region": row["region"],
            "n_starters": len(field),
            "p": p,
            "top2_pair": top2_pair,
        })

    print(f"[join] races in outcomes file: {n_join_total}")
    print(f"[join] dropped, no odds match: {n_dropped_no_odds_match}")
    print(f"[join] dropped, field too small after intersect: {n_dropped_field_too_small}")
    print(f"[join] dropped, realized top-2 horse missing odds: {n_dropped_top2_horse_missing}")
    print(f"[join] usable races: {len(records)}")
    return records


# ---------------------------------------------------------------------------
# quinella calibration
# ---------------------------------------------------------------------------

def score_quinella(records, lam=1.0):
    """One row per (race, unordered pair): predicted prob + hit indicator."""
    rows = []
    for rec in records:
        if rec["top2_pair"] is None:
            continue
        q = quinella_probs(rec["p"], lam=lam)
        for pair, prob in q.items():
            rows.append({
                "race_id": rec["race_id"],
                "region": rec["region"],
                "n_starters": rec["n_starters"],
                "pair": pair,
                "pred_p": prob,
                "hit": 1 if pair == rec["top2_pair"] else 0,
            })
    return pd.DataFrame(rows)


def calibration_table(scored, bins=BINS):
    cal = scored.copy()
    cal["bucket"] = pd.cut(cal["pred_p"], bins, right=False)
    g = cal.groupby("bucket", observed=True)
    tab = g.agg(n=("hit", "size"), pred_mean=("pred_p", "mean"),
                actual_freq=("hit", "mean")).reset_index()
    tab["se"] = np.sqrt(tab["pred_mean"] * (1 - tab["pred_mean"]) / tab["n"])
    tab["z"] = (tab["actual_freq"] - tab["pred_mean"]) / tab["se"]
    return tab


def quinella_log_loss(records, lam):
    """Pooled -sum(log P(realized pair)), for lambda grid search (Gate A2)."""
    total = 0.0
    n = 0
    for rec in records:
        if rec["top2_pair"] is None:
            continue
        q = quinella_probs(rec["p"], lam=lam)
        p_hit = q.get(rec["top2_pair"], 1e-12)
        total += -np.log(max(p_hit, 1e-12))
        n += 1
    return total, n


# ---------------------------------------------------------------------------
# diagnostics
# ---------------------------------------------------------------------------

def favorite_bias_table(records, lam=1.0):
    rows = []
    for rec in records:
        if rec["top2_pair"] is None:
            continue
        favorite = max(rec["p"], key=rec["p"].get)
        pl2 = place_probs(rec["p"], top=2, lam=lam)
        pred = pl2[favorite]
        actual = 1 if favorite in rec["top2_pair"] else 0
        rows.append({"pred_p": pred, "hit": actual, "n_starters": rec["n_starters"],
                      "region": rec["region"]})
    df = pd.DataFrame(rows)
    return calibration_table(df.assign(pred_p=df["pred_p"]))


def by_field_size(scored):
    bins = [0, 8, 11, 14, 99]
    labels = ["<=8", "9-11", "12-14", "15+"]
    scored = scored.copy()
    scored["size_bucket"] = pd.cut(scored["n_starters"], bins, labels=labels)
    out = []
    for label, grp in scored.groupby("size_bucket", observed=True):
        tab = calibration_table(grp)
        tab["size_bucket"] = label
        out.append(tab)
    return pd.concat(out, ignore_index=True) if out else pd.DataFrame()


def by_region(scored):
    out = []
    for region, grp in scored.groupby("region"):
        tab = calibration_table(grp)
        tab["region"] = region
        out.append(tab)
    return pd.concat(out, ignore_index=True) if out else pd.DataFrame()


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--odds-path", default=DEFAULT_ODDS_PATH)
    ap.add_argument("--outcomes-path", default=DEFAULT_OUTCOMES_PATH)
    ap.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    args = ap.parse_args()

    try:
        odds_df = load_odds(args.odds_path)
        outcomes_df = load_outcomes(args.outcomes_path)
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        print(
            "Run build_exotic_outcomes.py first (needs Piece A Input 2, the raw "
            "finish-rank pull) before this script.",
            file=sys.stderr,
        )
        sys.exit(1)

    records = build_race_records(odds_df, outcomes_df)

    # Gate A1: plain Harville
    scored = score_quinella(records, lam=1.0)
    cal = calibration_table(scored)
    cal.to_csv(f"{args.out_dir}/piece_a_calibration.csv", index=False)
    print("\n[Gate A1] quinella calibration (lam=1.0):")
    print(cal.to_string(index=False))

    fav = favorite_bias_table(records, lam=1.0)
    fav.to_csv(f"{args.out_dir}/piece_a_favorite_bias.csv", index=False)
    print("\n[diagnostic] favorite-in-quinella bias:")
    print(fav.to_string(index=False))

    by_region(scored).to_csv(f"{args.out_dir}/piece_a_by_region.csv", index=False)
    by_field_size(scored).to_csv(f"{args.out_dir}/piece_a_by_field_size.csv", index=False)

    max_abs_z = cal["z"].abs().max()
    fav_max_abs_z = fav["z"].abs().max()
    print(f"\n[Gate A1 verdict] max |z| in main calibration table: {max_abs_z:.2f}")
    print(f"[Gate A1 verdict] max |z| in favorite-bias table: {fav_max_abs_z:.2f}")

    if max_abs_z <= 2.0 and fav_max_abs_z <= 2.0:
        print("[Gate A1] PASS -- plain Harville looks calibrated. Gate A2 not needed.")
        return

    print("[Gate A1] miscalibration detected -- running Gate A2 lambda grid search.")
    lam_grid = np.round(np.arange(0.5, 1.05, 0.05), 2)
    results = []
    for lam in lam_grid:
        ll, n = quinella_log_loss(records, lam)
        results.append({"lam": lam, "log_loss": ll, "log_loss_per_race": ll / n, "n": n})
    grid_df = pd.DataFrame(results)
    grid_df.to_csv(f"{args.out_dir}/piece_a_lambda_grid.csv", index=False)
    best_lam = grid_df.loc[grid_df["log_loss"].idxmin(), "lam"]
    print(f"[Gate A2] best lambda by pooled log-loss: {best_lam}")

    scored_fit = score_quinella(records, lam=best_lam)
    cal_fit = calibration_table(scored_fit)
    cal_fit.to_csv(f"{args.out_dir}/piece_a_calibration_lambda_fit.csv", index=False)
    print(f"\n[Gate A2] quinella calibration (lam={best_lam}):")
    print(cal_fit.to_string(index=False))


if __name__ == "__main__":
    main()
