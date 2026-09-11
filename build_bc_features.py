"""
Bolton & Chapman (1986) feature-engineering pipeline for KRA data.

Builds 7 rolling/derived variables on top of the raw pull:
  AVESPRAT, LSPEDRAT, LIFE%WIN, W/RACE, JOCK%WIN, JOCK#WIN, NEWDIST

Two ready-made variables (WEIGHT = impost, POSTPOS = back_num) need no work
and are left as-is in the output.

Core design rules (from day4_context):
  1. No look-ahead bias: every rolling feature is computed using a shift-by-1 /
     closed='left' window so a race's own outcome never leaks into its own features.
  2. Rolling features are built on the FULL raw history first (all distances),
     never on a pre-filtered subset -- filtering to the 1600-2000m estimation
     sample happens as a separate, later step.
  3. Rank codes: 91 (DQ) and 92 (pulled up) count as STARTS (denominator) but
     never as wins, and are excluded from rank-ordered choice sets. 93 (excluded
     pre-race) and 95 (entry cancelled) are not starts at all -- excluded from
     every calculation. Null rank (4 rows) is treated the same as 93/95.
"""

import pandas as pd
import numpy as np

IN_PATH = "/mnt/user-data/uploads/race_info_race_info_of_horse_race_result_of_horse_record_by_clas_202607200918.csv"
OUT_PATH = "/mnt/user-data/outputs/bc_features_built.csv"

NON_START_RANKS = {93, 95}  # never a start; null rank also treated this way


def load_and_flag(path):
    df = pd.read_csv(path, dtype={"race_id": str}, low_memory=False)
    df["race_date"] = pd.to_datetime(df["race_date"])

    # is_start: did the horse actually leave the gate?
    #   True for normal finishes (rank 1-89ish) and rank 91/92 (DQ / pulled up)
    #   False for rank 93/95 (never started) and null rank (same pattern as 93/95)
    df["is_start"] = (~df["rank"].isin(NON_START_RANKS)) & df["rank"].notna()
    df["is_start"] = df["is_start"].astype(int)

    # is_win: rank == 1 (only meaningful among starts, but rank==1 already implies a start)
    df["is_win"] = (df["rank"] == 1).astype(int)

    return df


def build_race_speed_z(df):
    """
    Raw per-race speed rating: z-score of goal_time within
    (region x distance x race_class x track_condition) buckets.
    Faster time = better = should score HIGHER, so we flip the sign
    (raw goal_time is elapsed time -- lower is better).

    IMPORTANT: uses an EXPANDING (as-of-date) baseline, not a full-sample one.
    A race's z-score is computed only from bucket races that happened ON OR
    BEFORE that race's own date (shifted by 1, so its own time doesn't feed
    its own baseline either). Using the full 2008-2026 sample to normalize a
    2010 race would mean grading it against race times from 2020-2026 that
    hadn't happened yet -- a real leak, confirmed empirically: the difference
    between the two versions is large in early years (~0.6 z-score points in
    2008) and shrinks to near-zero by 2026, exactly the signature of
    future-information bleeding into the past. Requires >=10 prior races in
    the bucket before a z-score is computed at all (thin buckets otherwise).
    """
    bucket_cols = ["region", "distance", "race_class", "track_condition"]
    has_time = df["goal_time"].notna()

    sub = df.loc[has_time, bucket_cols + ["race_date", "goal_time"]].copy()
    sub["_orig_idx"] = df.index[has_time]
    sub = sub.sort_values(bucket_cols + ["race_date"])

    g = sub.groupby(bucket_cols)["goal_time"]
    exp_mean = g.transform(lambda s: s.expanding().mean().shift(1))
    exp_std = g.transform(lambda s: s.expanding().std().shift(1))
    exp_n = g.transform(lambda s: s.expanding().count().shift(1))

    sub["z"] = np.where(
        (exp_n >= 10) & (exp_std > 0),
        -(sub["goal_time"] - exp_mean) / exp_std,
        np.nan
    )
    z_map = sub.set_index("_orig_idx")["z"]

    df["race_speed_z"] = z_map.reindex(df.index).values
    return df


def build_time_windowed_features(df):
    """
    LIFE%WIN (730-day trailing window), JOCK%WIN / JOCK#WIN (365-day trailing),
    W/RACE (365-day trailing). All use closed='left' so the current race's own
    row is excluded from its own feature -- this IS the shift-by-1 logic, just
    expressed as a time window instead of a row count.

    IMPORTANT: merges back onto the original rows using a synthetic unique
    _row_id, NOT natural keys like (race_id, jockey_id) -- those can repeat
    within a single race (same jockey occasionally listed on 2 horses in one
    race, e.g. late substitutions), which would silently duplicate rows on
    a natural-key merge.
    """
    df = df.reset_index(drop=True)
    df["_row_id"] = df.index

    prize_cols = {1: "prize1", 2: "prize2", 3: "prize3", 4: "prize4", 5: "prize5"}
    df["race_winnings"] = 0.0
    for rnk, col in prize_cols.items():
        mask = df["rank"] == rnk
        df.loc[mask, "race_winnings"] = df.loc[mask, col]

    # ---------------- horse-level: LIFE%WIN, W/RACE ----------------
    horse_sorted = df.sort_values(["horse_id", "race_date"]).set_index("race_date")
    g = horse_sorted.groupby("horse_id")

    life_wins = g["is_win"].rolling("730D", closed="left").sum().reset_index(level=0, drop=True)
    life_starts = g["is_start"].rolling("730D", closed="left").sum().reset_index(level=0, drop=True)
    yr_winnings = g["race_winnings"].rolling("365D", closed="left").sum().reset_index(level=0, drop=True)
    yr_starts = g["is_start"].rolling("365D", closed="left").sum().reset_index(level=0, drop=True)

    horse_sorted = horse_sorted.reset_index()  # row order unchanged, so .values below stays aligned
    horse_sorted["LIFE_PCT_WIN"] = np.where(life_starts.values > 0, life_wins.values / life_starts.values * 100, np.nan)
    horse_sorted["W_PER_RACE"] = np.where(yr_starts.values > 0, yr_winnings.values / yr_starts.values, np.nan)
    horse_feats = horse_sorted.set_index("_row_id")[["LIFE_PCT_WIN", "W_PER_RACE"]]

    # ---------------- jockey-level: JOCK%WIN, JOCK#WIN ----------------
    jock_sorted = df.sort_values(["jockey_id", "race_date"]).set_index("race_date")
    gj = jock_sorted.groupby("jockey_id")

    jock_wins = gj["is_win"].rolling("365D", closed="left").sum().reset_index(level=0, drop=True)
    jock_starts = gj["is_start"].rolling("365D", closed="left").sum().reset_index(level=0, drop=True)

    jock_sorted = jock_sorted.reset_index()
    jock_sorted["JOCK_PCT_WIN"] = np.where(jock_starts.values > 0, jock_wins.values / jock_starts.values * 100, np.nan)
    jock_sorted["JOCK_NUM_WIN"] = jock_wins.values
    jock_feats = jock_sorted.set_index("_row_id")[["JOCK_PCT_WIN", "JOCK_NUM_WIN"]]

    # assign back by (unique) index -- guarantees exact 1:1, no fan-out possible
    df = df.set_index("_row_id")
    df[["LIFE_PCT_WIN", "W_PER_RACE"]] = horse_feats
    df[["JOCK_PCT_WIN", "JOCK_NUM_WIN"]] = jock_feats
    df = df.reset_index(drop=True)
    return df


def build_last4_features(df):
    """
    AVESPRAT (avg of race_speed_z over last 4 STARTS), LSPEDRAT (race_speed_z of
    the immediately preceding start only), NEWDIST (1 if >=3 of last 4 starts were
    run under 1600m). All computed on the valid-start subsequence per horse so that
    non-starts (93/95/null) don't consume a "last 4" slot, then assigned back by
    the same unique _row_id used above (not a natural-key merge).
    """
    df = df.reset_index(drop=True)
    if "_row_id" not in df.columns:
        df["_row_id"] = df.index

    starts = df[df["is_start"] == 1].sort_values(["horse_id", "race_date"]).copy()
    starts["under_1600"] = (starts["distance"] < 1600).astype(int)

    g = starts.groupby("horse_id")
    starts["AVESPRAT"] = g["race_speed_z"].transform(lambda s: s.shift(1).rolling(4, min_periods=1).mean())
    starts["LSPEDRAT"] = g["race_speed_z"].transform(lambda s: s.shift(1))
    last4_under = g["under_1600"].transform(lambda s: s.shift(1).rolling(4, min_periods=1).sum())
    starts["NEWDIST"] = (last4_under >= 3).astype(int)
    starts.loc[g.cumcount() == 0, "NEWDIST"] = np.nan  # first career start: no prior distance history

    feats = starts.set_index("_row_id")[["AVESPRAT", "LSPEDRAT", "NEWDIST"]]
    df = df.set_index("_row_id")
    df[["AVESPRAT", "LSPEDRAT", "NEWDIST"]] = feats
    df = df.reset_index(drop=True)
    return df


def main():
    df = load_and_flag(IN_PATH)
    df = build_race_speed_z(df)
    df = build_time_windowed_features(df)
    df = build_last4_features(df)

    # rename the two "ready" variables to match the B&C naming convention
    df["WEIGHT"] = df["impost"]
    df["POSTPOS"] = df["back_num"]

    import os
    os.makedirs("/mnt/user-data/outputs", exist_ok=True)
    df.to_csv(OUT_PATH, index=False)
    print(f"Saved {len(df):,} rows x {len(df.columns)} columns to {OUT_PATH}")
    print("\nNew columns built:", [c for c in ["AVESPRAT","LSPEDRAT","LIFE_PCT_WIN","W_PER_RACE",
                                                  "JOCK_PCT_WIN","JOCK_NUM_WIN","NEWDIST","WEIGHT","POSTPOS"]])
    return df


if __name__ == "__main__":
    main()
