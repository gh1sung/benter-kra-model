"""
Bolton & Chapman (1986) feature-engineering pipeline for KRA data.

This revision replaces the prior population-z-score speed metric with B&C's
track-record-relative rating:

    raw_speed_rating = 100 - 5 * (goal_time - prior_track_record_time)

The track record is defined within (region, distance), using only earlier
races in that bucket. It is computed at race level and shifted by one race so
no horse in the current race can contribute to its own baseline. At least 10
prior races are required before a rating is assigned.

The other seven B&C variables are unchanged. By default this script reuses the
already-engineered input CSV and only rebuilds the speed-derived columns. Pass
--rebuild-all to recompute the unchanged rolling variables as well.
"""

import argparse
import os
import pandas as pd
import numpy as np

DEFAULT_IN_PATH = "/mnt/data/bc_features_built.csv"
DEFAULT_OUT_PATH = "/mnt/data/bc_features_track_record.csv"

NON_START_RANKS = {93, 95}
MIN_PRIOR_RACES = 10


def load_and_flag(path):
    df = pd.read_csv(path, dtype={"race_id": str}, low_memory=False)
    df["race_date"] = pd.to_datetime(df["race_date"])
    df["is_start"] = ((~df["rank"].isin(NON_START_RANKS)) & df["rank"].notna()).astype(int)
    df["is_win"] = (df["rank"] == 1).astype(int)
    return df


def build_race_speed_z(df, min_prior_races=MIN_PRIOR_RACES):
    """
    Build B&C's track-record-relative speed rating.

    Interpretive choices:
      * Track-record bucket: (region, distance) only. Race class and track
        condition are deliberately excluded because B&C tie the record to
        track and distance, not to those additional conditions.
      * Cross-track adjustment: each region is anchored to its own historical
        record. No extra unidentified normalization is imposed.

    Look-ahead safety:
      * Reduce horse rows to one minimum goal_time per race.
      * Within each (region, distance), order races by race_date then race_id.
      * Use the expanding minimum shifted by one race.
      * Require at least min_prior_races completed prior races in the bucket.

    The historical function name is retained so downstream imports do not
    break, but its output is now raw_speed_rating rather than a z-score.
    """
    required = {"race_id", "race_date", "region", "distance", "goal_time"}
    missing = required - set(df.columns)
    if missing:
        raise KeyError(f"Missing columns required for speed rating: {sorted(missing)}")

    n_before = len(df)
    df = df.copy()
    df["race_date"] = pd.to_datetime(df["race_date"])

    # A race must have a single bucket identity. This also protects the map
    # below from hidden fan-out or ambiguous race IDs.
    race_identity = df.groupby("race_id", sort=False).agg(
        n_region=("region", "nunique"),
        n_distance=("distance", "nunique"),
        n_date=("race_date", "nunique"),
    )
    bad_identity = race_identity.query("n_region != 1 or n_distance != 1 or n_date != 1")
    if not bad_identity.empty:
        raise ValueError(f"Found {len(bad_identity)} race_id values with inconsistent identity fields")

    # One observation per race: the fastest valid horse time in that race.
    # Computing the expanding record here, instead of on horse rows, ensures
    # every horse in the same race receives the identical pre-race baseline.
    valid = df.loc[df["goal_time"].notna(),
                   ["race_id", "race_date", "region", "distance", "goal_time"]].copy()
    race_times = (
        valid.groupby(["race_id", "race_date", "region", "distance"], as_index=False)
             .agg(race_min_goal_time=("goal_time", "min"))
             .sort_values(["region", "distance", "race_date", "race_id"], kind="mergesort")
    )

    bucket_cols = ["region", "distance"]
    g = race_times.groupby(bucket_cols, sort=False)
    race_times["prior_race_count"] = g.cumcount()
    race_times["track_record_time"] = g["race_min_goal_time"].transform(
        lambda s: s.cummin().shift(1)
    )
    race_times.loc[
        race_times["prior_race_count"] < min_prior_races,
        "track_record_time"
    ] = np.nan

    if race_times["race_id"].duplicated().any():
        raise AssertionError("race_id is not unique in race-level track-record table")

    track_record_map = race_times.set_index("race_id")["track_record_time"]
    prior_count_map = race_times.set_index("race_id")["prior_race_count"]
    df["track_record_time"] = df["race_id"].map(track_record_map)
    df["track_record_prior_races"] = df["race_id"].map(prior_count_map)
    df["raw_speed_rating"] = np.where(
        df["goal_time"].notna() & df["track_record_time"].notna(),
        100.0 - 5.0 * (df["goal_time"] - df["track_record_time"]),
        np.nan,
    )

    # Remove the obsolete rating to prevent accidental downstream reuse.
    if "race_speed_z" in df.columns:
        df = df.drop(columns=["race_speed_z"])

    if len(df) != n_before:
        raise AssertionError(f"Row count changed in speed build: {n_before} -> {len(df)}")
    return df


def build_time_windowed_features(df):
    """
    LIFE%WIN (730-day trailing window), JOCK%WIN / JOCK#WIN (365-day trailing),
    W/RACE (365-day trailing). Unchanged from the prior validated build.
    """
    df = df.reset_index(drop=True)
    df["_row_id"] = df.index

    prize_cols = {1: "prize1", 2: "prize2", 3: "prize3", 4: "prize4", 5: "prize5"}
    df["race_winnings"] = 0.0
    for rnk, col in prize_cols.items():
        mask = df["rank"] == rnk
        df.loc[mask, "race_winnings"] = df.loc[mask, col]

    horse_sorted = df.sort_values(["horse_id", "race_date"]).set_index("race_date")
    g = horse_sorted.groupby("horse_id")

    life_wins = g["is_win"].rolling("730D", closed="left").sum().reset_index(level=0, drop=True)
    life_starts = g["is_start"].rolling("730D", closed="left").sum().reset_index(level=0, drop=True)
    yr_winnings = g["race_winnings"].rolling("365D", closed="left").sum().reset_index(level=0, drop=True)
    yr_starts = g["is_start"].rolling("365D", closed="left").sum().reset_index(level=0, drop=True)

    horse_sorted = horse_sorted.reset_index()
    horse_sorted["LIFE_PCT_WIN"] = np.where(life_starts.values > 0, life_wins.values / life_starts.values * 100, np.nan)
    horse_sorted["W_PER_RACE"] = np.where(yr_starts.values > 0, yr_winnings.values / yr_starts.values, np.nan)
    horse_feats = horse_sorted.set_index("_row_id")[["LIFE_PCT_WIN", "W_PER_RACE"]]

    jock_sorted = df.sort_values(["jockey_id", "race_date"]).set_index("race_date")
    gj = jock_sorted.groupby("jockey_id")

    jock_wins = gj["is_win"].rolling("365D", closed="left").sum().reset_index(level=0, drop=True)
    jock_starts = gj["is_start"].rolling("365D", closed="left").sum().reset_index(level=0, drop=True)

    jock_sorted = jock_sorted.reset_index()
    jock_sorted["JOCK_PCT_WIN"] = np.where(jock_starts.values > 0, jock_wins.values / jock_starts.values * 100, np.nan)
    jock_sorted["JOCK_NUM_WIN"] = jock_wins.values
    jock_feats = jock_sorted.set_index("_row_id")[["JOCK_PCT_WIN", "JOCK_NUM_WIN"]]

    df = df.set_index("_row_id")
    df[["LIFE_PCT_WIN", "W_PER_RACE"]] = horse_feats
    df[["JOCK_PCT_WIN", "JOCK_NUM_WIN"]] = jock_feats
    df = df.reset_index(drop=True)
    return df


def build_last4_features(df):
    """
    AVESPRAT = mean raw_speed_rating over the horse's last four starts.
    LSPEDRAT = raw_speed_rating from the immediately preceding start.
    NEWDIST logic is unchanged.
    """
    df = df.reset_index(drop=True)
    if "_row_id" not in df.columns:
        df["_row_id"] = df.index

    starts = df[df["is_start"] == 1].sort_values(["horse_id", "race_date", "race_id"]).copy()
    starts["under_1600"] = (starts["distance"] < 1600).astype(int)

    g = starts.groupby("horse_id", sort=False)
    starts["AVESPRAT"] = g["raw_speed_rating"].transform(
        lambda s: s.shift(1).rolling(4, min_periods=1).mean()
    )
    starts["LSPEDRAT"] = g["raw_speed_rating"].transform(lambda s: s.shift(1))
    last4_under = g["under_1600"].transform(
        lambda s: s.shift(1).rolling(4, min_periods=1).sum()
    )
    starts["NEWDIST"] = (last4_under >= 3).astype(int)
    starts.loc[g.cumcount() == 0, "NEWDIST"] = np.nan

    feats = starts.set_index("_row_id")[["AVESPRAT", "LSPEDRAT", "NEWDIST"]]
    df = df.set_index("_row_id")
    df[["AVESPRAT", "LSPEDRAT", "NEWDIST"]] = feats
    df = df.reset_index(drop=True)
    return df


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default=DEFAULT_IN_PATH)
    parser.add_argument("--output", default=DEFAULT_OUT_PATH)
    parser.add_argument("--min-prior-races", type=int, default=MIN_PRIOR_RACES)
    parser.add_argument(
        "--rebuild-all", action="store_true",
        help="Also recompute the unchanged LIFE/W/JOCK variables from raw columns."
    )
    return parser.parse_args()


def main():
    args = parse_args()
    df = load_and_flag(args.input)
    n_before = len(df)
    unique_before = df[["race_id", "horse_id"]].drop_duplicates().shape[0]
    if unique_before != n_before:
        raise AssertionError(
            f"Input is not unique by (race_id, horse_id): {unique_before} unique vs {n_before} rows"
        )

    df = build_race_speed_z(df, min_prior_races=args.min_prior_races)

    required_existing = {"LIFE_PCT_WIN", "W_PER_RACE", "JOCK_PCT_WIN", "JOCK_NUM_WIN"}
    if args.rebuild_all or not required_existing.issubset(df.columns):
        df = build_time_windowed_features(df)

    df = build_last4_features(df)
    df["WEIGHT"] = df["impost"]
    df["POSTPOS"] = df["back_num"]

    unique_after = df[["race_id", "horse_id"]].drop_duplicates().shape[0]
    if len(df) != n_before or unique_after != len(df):
        raise AssertionError(
            f"Row integrity failed: before={n_before}, after={len(df)}, unique_after={unique_after}"
        )

    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    df.to_csv(args.output, index=False)
    print(f"Saved {len(df):,} rows x {len(df.columns)} columns to {args.output}")
    print(f"Track-record bucket: (region, distance); minimum prior races: {args.min_prior_races}")
    print(f"raw_speed_rating coverage: {df['raw_speed_rating'].notna().mean():.2%}")
    return df


if __name__ == "__main__":
    main()
