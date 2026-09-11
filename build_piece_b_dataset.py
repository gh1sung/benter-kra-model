"""
build_piece_b_dataset.py

Piece B, deliverable 1. Joins win odds + exotic (복승) odds + realized
outcomes into one row per (race, pair):

  - q_model  : Harville quinella prob derived from the WIN pool (lambda-corrected,
               using Piece A's fitted lambda)
  - q_market : overround-removed quinella prob implied by the EXOTIC pool's
               own dividends (sums to 1 per race -- for calibration/log-loss)
  - d        : raw exotic dividend, as-is (post-takeout payout -- for EV/backtest)
  - y        : 1 if this pair actually finished top-2, else 0 (exactly one per race)

Reuses Piece A's join conventions exactly (see validate_piece_a.py):
  - Jeju dropped (region IN {서울, 부산})
  - 부산경남 (odds side) <-> 부산 (RDS side) mapped
  - gate_no / back_num is the true per-race horse key -- never horse_id on
    the odds side (it's identical to gate_no in every row, not a real ID)
  - Scratches dropped, win probs re-normalized over survivors before Harville
  - Field is the INTERSECTION of: outcome starters, win-odds gates, exotic-odds
    gates -- a horse missing from any one side can't be scored
"""
import argparse
import sys

import numpy as np
import pandas as pd

from harville_engine import quinella_probs

DEFAULT_WIN_ODDS_PATH = "/mnt/project/win_odds_5yr.csv"
DEFAULT_EXOTIC_ODDS_PATH = "/mnt/project/exotic_odds_5yr.csv"
DEFAULT_OUTCOMES_PATH = "/mnt/user-data/outputs/exotic_outcomes.csv"
DEFAULT_OUT_PATH = "/mnt/user-data/outputs/piece_b_dataset.csv"
DEFAULT_LAMBDA = 0.8  # Piece A's fitted lambda -- override with --lam if that changes
POOL_LABEL = "복승식"

REGION_MAP = {"부산경남": "부산"}


# ---------------------------------------------------------------------------
# load
# ---------------------------------------------------------------------------

def load_win_odds(path):
    df = pd.read_csv(path)
    df = df[df["track"] != "제주"].copy()
    df["region"] = df["track"].replace(REGION_MAP)
    return df[["date", "region", "race_no", "gate_no", "odds"]]


SENTINEL_DIVIDEND = 9999.9  # placeholder value in the raw pull, not a real payout --
# confirmed by exact-value repetition (3,258 identical hits across distinct races/
# pairs; a genuine settled dividend wouldn't repeat like that), 85% concentrated in
# 2021. Treated as missing data and dropped, same as any other invalid quote.


def load_exotic_odds(path, pool_label=POOL_LABEL):
    df = pd.read_csv(path)
    df = df[df["pool"] == pool_label].copy()
    if df.empty:
        raise ValueError(
            f"No rows with pool == '{pool_label}' in {path}. Check the pool "
            f"column's actual values -- confirm the label before assuming "
            f"the file is empty of quinella data."
        )
    if "track" in df.columns:
        df["region"] = df["track"].replace(REGION_MAP)
        df = df[df["track"] != "제주"]
    else:
        df["region"] = df["region"].replace(REGION_MAP)

    n_sentinel = (df["odds"] == SENTINEL_DIVIDEND).sum()
    if n_sentinel:
        print(f"[load_exotic_odds] dropping {n_sentinel} rows with sentinel "
              f"dividend == {SENTINEL_DIVIDEND} (treated as missing, not a real payout)")
        df = df[df["odds"] != SENTINEL_DIVIDEND].copy()

    # canonical ascending pair, per the plan's column spec (chulNo, chulNo2)
    lo = df[["chulNo", "chulNo2"]].min(axis=1).astype(int)
    hi = df[["chulNo", "chulNo2"]].max(axis=1).astype(int)
    df["chulNo"], df["chulNo2"] = lo, hi
    df = df.rename(columns={"odds": "dividend"})
    return df[["date", "region", "race_no", "chulNo", "chulNo2", "dividend"]]


def load_outcomes(path):
    """Piece A's build_exotic_outcomes.py output: race_id, race_date, region,
    race_no, n_starters, starters, winner, second, third, top2_pair, top3_triple."""
    df = pd.read_csv(path)
    df["race_date"] = pd.to_datetime(df["race_date"])
    df["date"] = df["race_date"].dt.strftime("%Y%m%d").astype(int)
    return df


# ---------------------------------------------------------------------------
# build
# ---------------------------------------------------------------------------

def build_dataset(win_df, exotic_df, outcomes_df, lam=DEFAULT_LAMBDA):
    win_groups = {k: g for k, g in win_df.groupby(["date", "region", "race_no"])}
    exotic_groups = {k: g for k, g in exotic_df.groupby(["date", "region", "race_no"])}

    rows = []
    n_total = 0
    n_no_win = 0
    n_no_exotic = 0
    n_field_too_small = 0
    n_realized_pair_unquoted = 0
    n_multiple_y = 0
    n_unscoreable = 0

    for _, orow in outcomes_df.iterrows():
        key = (orow["date"], orow["region"], orow["race_no"])
        n_total += 1

        win_grp = win_groups.get(key)
        if win_grp is None or win_grp.empty:
            n_no_win += 1
            continue
        exo_grp = exotic_groups.get(key)
        if exo_grp is None or exo_grp.empty:
            n_no_exotic += 1
            continue

        starters = set(int(s) for s in str(orow["starters"]).split("|") if s)
        win_gates = set(win_grp["gate_no"].astype(int))
        exotic_gates = set(exo_grp["chulNo"].astype(int)) | set(exo_grp["chulNo2"].astype(int))
        field = sorted(starters & win_gates & exotic_gates)
        if len(field) < 2:
            n_field_too_small += 1
            continue

        # re-normalize win probs over the intersected field
        sub = win_grp[win_grp["gate_no"].astype(int).isin(field)]
        raw = 1.0 / sub.set_index(sub["gate_no"].astype(int))["odds"]
        p = (raw / raw.sum()).to_dict()
        q_model = quinella_probs(p, lam=lam)

        exo_sub = exo_grp[
            exo_grp["chulNo"].astype(int).isin(field)
            & exo_grp["chulNo2"].astype(int).isin(field)
        ].copy()
        if exo_sub.empty:
            n_field_too_small += 1
            continue
        exo_sub["inv_d"] = 1.0 / exo_sub["dividend"]
        overround_sum = exo_sub["inv_d"].sum()

        top2 = orow["top2_pair"]
        top2_pair = None
        if isinstance(top2, str) and top2:
            a, b = (int(x) for x in top2.split("|"))
            if a in field and b in field:
                top2_pair = frozenset((a, b))

        if top2_pair is None:
            # No usable realized top-2 for this race (e.g. a DQ'd/pulled-up horse
            # holds rank 1, per build_exotic_outcomes.py's rank-code handling --
            # the same 15-race exclusion Piece A already applied). We don't know
            # who actually won, so this race can't be scored -- drop entirely
            # rather than silently keeping every pair as a false y=0.
            n_unscoreable += 1
            continue

        # The realized pair's own dividend must actually be present in the
        # (sentinel-filtered) market -- if it isn't, we don't have a real
        # price for the bet that would have won, so this race can't be
        # scored at all. Drop it entirely (same convention validate_piece_a.py
        # uses) rather than keeping every OTHER pair marked y=0, which would
        # be correct in isolation but leaves zero positive examples for a
        # race that did in fact have a winner.
        quoted_pairs = set(
            frozenset((int(r.chulNo), int(r.chulNo2))) for r in exo_sub.itertuples()
        )
        if top2_pair not in quoted_pairs:
            n_realized_pair_unquoted += 1
            continue

        y_count = 0
        for _, erow in exo_sub.iterrows():
            i, j = int(erow["chulNo"]), int(erow["chulNo2"])
            pair_key = frozenset((i, j))
            d = float(erow["dividend"])
            q_mkt = float(erow["inv_d"] / overround_sum)
            qm = q_model.get(pair_key, np.nan)
            y = 1 if pair_key == top2_pair else 0
            y_count += y
            rows.append({
                "race_id": f"{orow['date']}_{orow['region']}_{orow['race_no']}",
                "date": orow["date"],
                "year": int(str(orow["date"])[:4]),
                "region": orow["region"],
                "race_no": orow["race_no"],
                "pair": f"{i}|{j}",
                "n_starters": len(field),
                "q_model": qm,
                "q_market": q_mkt,
                "d": d,
                "y": y,
            })

        if y_count > 1:
            n_multiple_y += 1

    out = pd.DataFrame(rows)
    print(f"[join] races in outcomes file: {n_total}")
    print(f"[join] dropped, no win-odds match: {n_no_win}")
    print(f"[join] dropped, no exotic-odds match: {n_no_exotic}")
    print(f"[join] dropped, field too small after intersect: {n_field_too_small}")
    print(f"[join] dropped, no usable realized top-2 (DQ/pulled-up in rank 1/2): {n_unscoreable}")
    print(f"[join] races where realized pair wasn't in the quoted market: {n_realized_pair_unquoted}")
    print(f"[join] races with >1 y==1 pair (bug if nonzero): {n_multiple_y}")
    print(f"[join] usable (race, pair) rows: {len(out)}")
    print(f"[join] usable distinct races: {out['race_id'].nunique() if len(out) else 0}")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--win-odds-path", default=DEFAULT_WIN_ODDS_PATH)
    ap.add_argument("--exotic-odds-path", default=DEFAULT_EXOTIC_ODDS_PATH)
    ap.add_argument("--outcomes-path", default=DEFAULT_OUTCOMES_PATH)
    ap.add_argument("--out-path", default=DEFAULT_OUT_PATH)
    ap.add_argument("--lam", type=float, default=DEFAULT_LAMBDA)
    args = ap.parse_args()

    try:
        win_df = load_win_odds(args.win_odds_path)
    except FileNotFoundError:
        print(f"ERROR: win odds file not found at {args.win_odds_path}", file=sys.stderr)
        sys.exit(1)

    try:
        exotic_df = load_exotic_odds(args.exotic_odds_path)
    except FileNotFoundError:
        print(f"ERROR: exotic odds file not found at {args.exotic_odds_path}", file=sys.stderr)
        print(
            "Piece B Input 2 (exotic_odds_5yr.csv) isn't present in this session. "
            "Confirm the pull completed (failed=0 in its checkpoint) and upload it "
            "to /mnt/user-data/uploads/ or /mnt/project/.",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        outcomes_df = load_outcomes(args.outcomes_path)
    except FileNotFoundError:
        print(f"ERROR: outcomes file not found at {args.outcomes_path}", file=sys.stderr)
        print(
            "Run build_exotic_outcomes.py first (needs Piece A Input 2, the raw "
            "finish-rank pull) before this script.",
            file=sys.stderr,
        )
        sys.exit(1)

    out = build_dataset(win_df, exotic_df, outcomes_df, lam=args.lam)
    out.to_csv(args.out_path, index=False)
    print(f"[done] wrote {len(out)} rows to {args.out_path}")


if __name__ == "__main__":
    main()
