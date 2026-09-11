"""
Gate 2, Tier 1: TRAINER_PCT_WIN, TRAINER_NUM_WIN, CAREER_STARTS, DAYS_SINCE_LAST_RACE.

Reuses the exact look-ahead-safe patterns already validated in build_bc_features.py:
  - rolling window features: groupby(id).rolling(window, closed='left') on a
    DatetimeIndex, merged back via synthetic _row_id (never a natural key).
  - sequence features: valid-starts-only subsequence, sorted by id + race_date,
    shift(1) before any cumcount()/diff().

Input:  bc_features_built.csv (production baseline, 369,139 rows / 39 cols)
Output: gate2_features_tier1.csv (same rows, + 4 new columns)
"""
import pandas as pd
import numpy as np

IN_PATH = "bc_features_built.csv"
OUT_PATH = "gate2_features_tier1.csv"


def build_trainer_features(df):
    """TRAINER_PCT_WIN, TRAINER_NUM_WIN: identical construction to JOCK_PCT_WIN/
    JOCK_NUM_WIN, grouped by trainer_id instead of jockey_id. 365-day trailing,
    closed='left'."""
    df = df.reset_index(drop=True)
    if "_row_id" not in df.columns:
        df["_row_id"] = df.index

    tr_sorted = df.sort_values(["trainer_id", "race_date"]).set_index("race_date")
    g = tr_sorted.groupby("trainer_id")

    tr_wins = g["is_win"].rolling("365D", closed="left").sum().reset_index(level=0, drop=True)
    tr_starts = g["is_start"].rolling("365D", closed="left").sum().reset_index(level=0, drop=True)

    tr_sorted = tr_sorted.reset_index()
    tr_sorted["TRAINER_PCT_WIN"] = np.where(tr_starts.values > 0, tr_wins.values / tr_starts.values * 100, np.nan)
    tr_sorted["TRAINER_NUM_WIN"] = tr_wins.values
    tr_feats = tr_sorted.set_index("_row_id")[["TRAINER_PCT_WIN", "TRAINER_NUM_WIN"]]

    df = df.set_index("_row_id")
    df[["TRAINER_PCT_WIN", "TRAINER_NUM_WIN"]] = tr_feats
    df = df.reset_index(drop=True)
    return df


def build_career_starts_and_recency(df):
    """CAREER_STARTS: cumulative count of horse's prior valid starts (unbounded,
    full career). groupby().cumcount() on the valid-starts subsequence already
    gives the count of PRIOR rows in the group (0-based) -- no extra shift needed,
    a horse's own current start never counts toward its own CAREER_STARTS.

    DAYS_SINCE_LAST_RACE: calendar days between this race and the immediately
    preceding valid start. NaN on a horse's first career start."""
    df = df.reset_index(drop=True)
    if "_row_id" not in df.columns:
        df["_row_id"] = df.index

    starts = df[df["is_start"] == 1].sort_values(["horse_id", "race_date"]).copy()
    g = starts.groupby("horse_id")

    starts["CAREER_STARTS"] = g.cumcount()
    starts["DAYS_SINCE_LAST_RACE"] = g["race_date"].transform(lambda s: s.diff().dt.days)

    feats = starts.set_index("_row_id")[["CAREER_STARTS", "DAYS_SINCE_LAST_RACE"]]
    df = df.set_index("_row_id")
    df[["CAREER_STARTS", "DAYS_SINCE_LAST_RACE"]] = feats
    df = df.reset_index(drop=True)
    return df


def main():
    df = pd.read_csv(IN_PATH, dtype={"race_id": str}, low_memory=False)
    df["race_date"] = pd.to_datetime(df["race_date"])
    n0, ncol0 = df.shape

    df = build_trainer_features(df)
    assert df.shape[0] == n0, f"row count changed after trainer merge: {n0} -> {df.shape[0]}"

    df = build_career_starts_and_recency(df)
    assert df.shape[0] == n0, f"row count changed after career/recency merge: {n0} -> {df.shape[0]}"

    df = df.drop(columns=["_row_id"], errors="ignore")

    df.to_csv(OUT_PATH, index=False)
    print(f"Saved {len(df):,} rows x {len(df.columns)} columns to {OUT_PATH}")
    print(f"Row count check: {n0:,} in -> {len(df):,} out  {'OK' if len(df)==n0 else 'MISMATCH!!'}")
    print("New columns:", ["TRAINER_PCT_WIN", "TRAINER_NUM_WIN", "CAREER_STARTS", "DAYS_SINCE_LAST_RACE"])
    return df


if __name__ == "__main__":
    main()
