"""
Gate 2, Tier 2 (optional): DIST_RESIDUAL -- Benter (1994)-style distance-preference
factor, tested as an ADDITIONAL candidate alongside NEWDIST (B&C's crude binary
version), not a replacement.

Benter's own description: for each of a horse's past races, predict finishing
position via regression on all non-distance factors, then use the residual
(actual - predicted) across the horse's past races to estimate a distance-
performance relationship.

Implementation (documented simplification -- this is a proxy, not a literal
per-horse regression, since most horses have too few career starts to fit their
own regression reliably):

  1. Outcome: finish_pct = (horse_count - rank) / (horse_count - 1) on real
     finishes only (rank < 90, horse_count >= 2). Winner = 1.0, last = 0.0.
  2. "Non-distance factors" = the already-built, already look-ahead-safe
     features that don't encode distance: AVESPRAT, LIFE_PCT_WIN, W_PER_RACE,
     JOCK_PCT_WIN, JOCK_NUM_WIN, WEIGHT, POSTPOS, TRAINER_PCT_WIN.
  3. A single population-level OLS is refit once per calendar year, using only
     rows from STRICTLY EARLIER years (expanding window) -- so a 2016 race is
     always scored by a model that only ever saw 2008-2015 data. This avoids
     per-row leakage while keeping compute tractable across 369K rows. The
     first year in the data (2008) has no prior-year model, so residuals are
     NaN for all of 2008 -- same "needs prior history" pattern already used
     for race_speed_z (requires >=10 prior races) and AVESPRAT (NaN on debut).
  4. residual_i = finish_pct_i - predicted_pct_i for every real-finish start.
  5. DIST_RESIDUAL for an upcoming race = the horse's EXPANDING mean residual
     (shift-by-1, so the current race's own residual never feeds its own
     feature) computed only over the horse's PAST starts in the SAME distance
     bucket as the upcoming race (bucket = sprint <1600m vs route >=1600m,
     matching the convention NEWDIST already uses). NaN if the horse has no
     prior same-bucket history yet.

Input:  gate2_features_v2.csv (369,139 rows, Tier1 + HAS_RATING already added)
Output: gate2_features_v3.csv (+ DIST_RESIDUAL column)
"""
import pandas as pd
import numpy as np

IN_PATH = "gate2_features_v2.csv"
OUT_PATH = "gate2_features_v3.csv"

NONDIST_VARS = ["AVESPRAT", "LIFE_PCT_WIN", "W_PER_RACE", "JOCK_PCT_WIN",
                 "JOCK_NUM_WIN", "WEIGHT", "POSTPOS", "TRAINER_PCT_WIN"]


def fit_ols(X, y):
    """Plain OLS via lstsq, with an intercept column prepended."""
    Xd = np.column_stack([np.ones(len(X)), X])
    coef, *_ = np.linalg.lstsq(Xd, y, rcond=None)
    return coef  # coef[0] = intercept, coef[1:] = slopes


def predict_ols(coef, X):
    Xd = np.column_stack([np.ones(len(X)), X])
    return Xd @ coef


def build_residuals(df):
    """Step 1-4: expanding-year OLS residuals on real finishes."""
    real_finish = (df["rank"] < 90) & (df["horse_count"] >= 2) & df["rank"].notna()
    sub = df.loc[real_finish].copy()
    sub["finish_pct"] = (sub["horse_count"] - sub["rank"]) / (sub["horse_count"] - 1)
    sub["year"] = pd.to_datetime(sub["race_date"]).dt.year

    has_covars = sub[NONDIST_VARS].notna().all(axis=1)
    sub["residual"] = np.nan

    years = sorted(sub["year"].unique())
    for y in years:
        train_mask = has_covars & (sub["year"] < y)
        test_mask = has_covars & (sub["year"] == y)
        if train_mask.sum() < 500 or test_mask.sum() == 0:
            continue  # not enough prior data yet to fit a stable model
        Xtr = sub.loc[train_mask, NONDIST_VARS].to_numpy(dtype=float)
        ytr = sub.loc[train_mask, "finish_pct"].to_numpy(dtype=float)
        coef = fit_ols(Xtr, ytr)

        Xte = sub.loc[test_mask, NONDIST_VARS].to_numpy(dtype=float)
        pred = predict_ols(coef, Xte)
        sub.loc[test_mask, "residual"] = sub.loc[test_mask, "finish_pct"].to_numpy() - pred

    return sub[["_row_id", "residual"]] if "_row_id" in sub.columns else sub[["residual"]].assign(_row_id=sub.index)


def build_dist_residual(df, resid_df):
    """Step 5: horse's expanding same-bucket-distance mean of past residuals."""
    df = df.reset_index(drop=True)
    df["_row_id"] = df.index
    df = df.merge(resid_df, on="_row_id", how="left")

    starts = df[df["is_start"] == 1].sort_values(["horse_id", "race_date"]).copy()
    starts["bucket"] = np.where(starts["distance"] < 1600, "sprint", "route")

    g = starts.groupby(["horse_id", "bucket"])
    starts["DIST_RESIDUAL"] = g["residual"].transform(lambda s: s.shift(1).expanding().mean())

    feats = starts.set_index("_row_id")[["DIST_RESIDUAL"]]
    df = df.set_index("_row_id")
    df["DIST_RESIDUAL"] = feats["DIST_RESIDUAL"]
    df = df.drop(columns=["residual"]).reset_index(drop=True)
    return df


def main():
    df = pd.read_csv(IN_PATH, dtype={"race_id": str}, low_memory=False)
    df["race_date"] = pd.to_datetime(df["race_date"])
    n0 = len(df)

    df["_row_id"] = df.reset_index(drop=True).index
    resid_df = build_residuals(df)
    df = build_dist_residual(df, resid_df)

    assert len(df) == n0, f"row count changed: {n0} -> {len(df)}"
    df = df.drop(columns=["_row_id"], errors="ignore")

    df.to_csv(OUT_PATH, index=False)
    print(f"Saved {len(df):,} rows x {len(df.columns)} columns to {OUT_PATH}")
    print(f"Row count check: {n0:,} -> {len(df):,}  {'OK' if len(df)==n0 else 'MISMATCH!!'}")
    print("DIST_RESIDUAL non-null:", df["DIST_RESIDUAL"].notna().sum(), "/", len(df))
    print("DIST_RESIDUAL describe:\n", df["DIST_RESIDUAL"].describe())
    return df


if __name__ == "__main__":
    main()
