"""
Bolton & Chapman (1986) pipeline-correctness checksum.

Pipeline: filter to estimation sample -> Chapman-Staelin rank-order "explosion"
-> fit a multinomial (conditional) logit by MLE -> compute pseudo-R^2 -> compare
against B&C's published benchmarks (~0.09 at explosion depth E=1, ~0.055-0.064
at E=2/E=3).

Input:  /mnt/user-data/outputs/bc_features_built.csv  (from build_bc_features.py)
Output: printed summary + /mnt/user-data/outputs/bc_checksum_results.csv
        (one row per explosion depth, in-sample and holdout pseudo-R^2, plus
        fitted coefficients for the E=1 in-sample model)

Design choices, and why:
  - Estimation sample = distance 1600-2000m, track_condition in ('건','양'),
    horse_age >= 3, and a REAL finish (rank < 90 -- excludes DQ/pulled-up/
    scratched/cancelled). Per day4_context, ranks 91/92 already fed the
    starts-denominator in LIFE%WIN/JOCK%WIN during feature-building, but are
    excluded here from the rank-ordered choice sets themselves, since we don't
    know where they'd have actually finished.
  - Rows missing any of the 9 B&C features (first-ever start, no history yet)
    are dropped from the estimation sample. This matches Benter's own
    "unratable horse" concept -- in a later stage those horses would get the
    public's probability instead of a fundamental-model score, but that
    requires odds data we don't have loaded yet. For this checksum, listwise
    deletion is the standard, defensible choice.
  - No intercept term: in a discrete-choice / conditional-logit setup, a
    constant that's the same across every alternative in a choice set cancels
    out of the softmax and isn't identified. Only the 9 feature coefficients
    are fit.
  - Time-based 80/20 train/test split (by race, not by row) for the holdout
    check, since choice sets can't be split across train/test without breaking
    the model.
"""

import numpy as np
import pandas as pd
from scipy.optimize import minimize

IN_PATH = "/mnt/user-data/outputs/bc_features_built.csv"
OUT_PATH = "/mnt/user-data/outputs/bc_checksum_results.csv"

BC_VARS = ["AVESPRAT", "LSPEDRAT", "LIFE_PCT_WIN", "W_PER_RACE",
           "JOCK_PCT_WIN", "JOCK_NUM_WIN", "WEIGHT", "POSTPOS", "NEWDIST"]

BC_BENCHMARKS = {1: (0.09, 0.09), 2: (0.055, 0.064), 3: (0.055, 0.064)}


# ---------------------------------------------------------------------------
# 1. Filter to estimation sample
# ---------------------------------------------------------------------------
def build_estimation_sample(path):
    df = pd.read_csv(path, dtype={"race_id": str}, low_memory=False)
    df["race_date"] = pd.to_datetime(df["race_date"])

    mask = (
        (df["distance"] >= 1600) & (df["distance"] <= 2000) &
        (df["track_condition"].isin(["건", "양"])) &
        (df["horse_age"] >= 3) &
        (df["rank"] < 90)
    )
    sample = df.loc[mask].dropna(subset=BC_VARS).copy()

    # drop any race left with fewer than 2 horses -- no choice possible
    field_size = sample.groupby("race_id")["race_id"].transform("size")
    sample = sample[field_size >= 2].copy()
    return sample


# ---------------------------------------------------------------------------
# 2. Chapman-Staelin explosion
# ---------------------------------------------------------------------------
def explode(sample, max_depth):
    """
    For each race, sort horses by actual finish order (best first). At each
    stage k = 1..min(max_depth, N-1), the choice set is "horses ranked k..N",
    and the chosen alternative is the one ranked k (i.e. after removing the
    winners of all earlier stages). Returns a long dataframe: one row per
    (horse, choice_set), with a `chosen` flag and a `choice_set_id`.
    """
    records = []
    choice_set_id = 0
    for race_id, grp in sample.groupby("race_id", sort=False):
        grp = grp.sort_values("rank")
        horses = grp.to_dict("records")
        n = len(horses)
        depth = min(max_depth, n - 1)
        for k in range(depth):
            candidates = horses[k:]
            if len(candidates) < 2:
                break
            choice_set_id += 1
            for pos, h in enumerate(candidates):
                rec = {col: h[col] for col in BC_VARS}
                rec["choice_set_id"] = choice_set_id
                rec["race_id"] = race_id
                rec["chosen"] = 1 if pos == 0 else 0
                records.append(rec)
    return pd.DataFrame(records)


# ---------------------------------------------------------------------------
# 3. Multinomial logit fit by MLE
# ---------------------------------------------------------------------------
def negloglik_and_grad(beta, X, chosen, group_idx, n_groups):
    """
    X: (n_rows, k) standardized feature matrix
    chosen: (n_rows,) 1/0 flag
    group_idx: (n_rows,) integer choice-set index in [0, n_groups)
    Returns negative log-likelihood and its gradient w.r.t. beta.
    """
    scores = X @ beta
    # softmax within each group, done via groupby-style reduction using np.add.at
    max_per_group = np.full(n_groups, -np.inf)
    np.maximum.at(max_per_group, group_idx, scores)
    shifted = scores - max_per_group[group_idx]
    exp_scores = np.exp(shifted)
    sum_per_group = np.zeros(n_groups)
    np.add.at(sum_per_group, group_idx, exp_scores)
    probs = exp_scores / sum_per_group[group_idx]

    ll = np.sum(chosen * np.log(np.clip(probs, 1e-12, None)))
    nll = -ll

    # gradient: -sum_over_groups( x_chosen - E[x] ), E[x] = sum_j p_j x_j
    weighted_X = X * probs[:, None]
    expected_X = np.zeros((n_groups, X.shape[1]))
    np.add.at(expected_X, group_idx, weighted_X)
    chosen_X = np.zeros((n_groups, X.shape[1]))
    np.add.at(chosen_X, group_idx, X * chosen[:, None])
    grad = -np.sum(chosen_X - expected_X, axis=0)
    return nll, grad


def fit_mnl(exploded_df):
    exploded_df = exploded_df.reset_index(drop=True)
    exploded_df["group_idx"] = exploded_df["choice_set_id"].astype("category").cat.codes
    n_groups = exploded_df["group_idx"].nunique()

    X_raw = exploded_df[BC_VARS].to_numpy(dtype=float)
    mu = X_raw.mean(axis=0)
    sigma = X_raw.std(axis=0)
    sigma[sigma == 0] = 1.0
    X = (X_raw - mu) / sigma  # standardize for stable optimization + comparable coefficients

    chosen = exploded_df["chosen"].to_numpy(dtype=float)
    group_idx = exploded_df["group_idx"].to_numpy()

    beta0 = np.zeros(X.shape[1])
    res = minimize(
        negloglik_and_grad, beta0, args=(X, chosen, group_idx, n_groups),
        method="BFGS", jac=True, options={"maxiter": 500}
    )

    ll_model = -res.fun
    group_sizes = exploded_df.groupby("group_idx").size().to_numpy()
    ll_null = -np.sum(np.log(group_sizes))
    pseudo_r2 = 1 - ll_model / ll_null

    return {
        "beta": dict(zip(BC_VARS, res.x)),
        "converged": res.success,
        "n_choice_sets": n_groups,
        "n_rows": len(exploded_df),
        "ll_model": ll_model,
        "ll_null": ll_null,
        "pseudo_r2": pseudo_r2,
    }


def score_holdout(exploded_df, beta_dict, mu, sigma):
    """Apply an already-fit beta (from train) to a held-out exploded set, compute pseudo-R^2."""
    exploded_df = exploded_df.reset_index(drop=True)
    exploded_df["group_idx"] = exploded_df["choice_set_id"].astype("category").cat.codes
    n_groups = exploded_df["group_idx"].nunique()

    X_raw = exploded_df[BC_VARS].to_numpy(dtype=float)
    X = (X_raw - mu) / sigma
    beta = np.array([beta_dict[v] for v in BC_VARS])
    chosen = exploded_df["chosen"].to_numpy(dtype=float)
    group_idx = exploded_df["group_idx"].to_numpy()

    nll, _ = negloglik_and_grad(beta, X, chosen, group_idx, n_groups)
    ll_model = -nll
    group_sizes = exploded_df.groupby("group_idx").size().to_numpy()
    ll_null = -np.sum(np.log(group_sizes))
    return 1 - ll_model / ll_null, n_groups


def fit_mnl_with_scaler(exploded_df):
    """Same as fit_mnl but also returns the mu/sigma used, so the same scaling
    can be re-applied to a holdout set (fit train stats only, never test stats)."""
    exploded_df = exploded_df.reset_index(drop=True)
    exploded_df["group_idx"] = exploded_df["choice_set_id"].astype("category").cat.codes
    n_groups = exploded_df["group_idx"].nunique()

    X_raw = exploded_df[BC_VARS].to_numpy(dtype=float)
    mu = X_raw.mean(axis=0)
    sigma = X_raw.std(axis=0)
    sigma[sigma == 0] = 1.0
    X = (X_raw - mu) / sigma

    chosen = exploded_df["chosen"].to_numpy(dtype=float)
    group_idx = exploded_df["group_idx"].to_numpy()

    beta0 = np.zeros(X.shape[1])
    res = minimize(
        negloglik_and_grad, beta0, args=(X, chosen, group_idx, n_groups),
        method="BFGS", jac=True, options={"maxiter": 500}
    )
    beta_dict = dict(zip(BC_VARS, res.x))
    return beta_dict, mu, sigma, res.success


# ---------------------------------------------------------------------------
# 4. Main
# ---------------------------------------------------------------------------
def main():
    sample = build_estimation_sample(IN_PATH)
    n_races = sample["race_id"].nunique()
    print(f"Estimation sample: {len(sample):,} horse-rows across {n_races:,} races\n")

    # time-based 80/20 split by race
    race_dates = sample.groupby("race_id")["race_date"].first().sort_values()
    cutoff = race_dates.iloc[int(len(race_dates) * 0.8)]
    train_races = set(race_dates[race_dates < cutoff].index)
    test_races = set(race_dates[race_dates >= cutoff].index)
    print(f"Train/test split at {cutoff.date()}  "
          f"({len(train_races):,} train races, {len(test_races):,} test races)\n")

    results_rows = []
    print(f"{'Depth':<7}{'Choice sets':<14}{'In-sample R2':<15}{'Holdout R2':<13}{'B&C benchmark':<15}{'Converged'}")

    for depth in [1, 2, 3]:
        exploded_all = explode(sample, depth)
        fit_all = fit_mnl(exploded_all)

        exploded_train = explode(sample[sample["race_id"].isin(train_races)], depth)
        exploded_test = explode(sample[sample["race_id"].isin(test_races)], depth)
        beta_train, mu_train, sigma_train, converged_train = fit_mnl_with_scaler(exploded_train)
        holdout_r2, n_test_sets = score_holdout(exploded_test, beta_train, mu_train, sigma_train)

        lo, hi = BC_BENCHMARKS[depth]
        bench_str = f"~{lo}" if lo == hi else f"{lo}-{hi}"
        print(f"{depth:<7}{fit_all['n_choice_sets']:<14,}{fit_all['pseudo_r2']:<15.4f}"
              f"{holdout_r2:<13.4f}{bench_str:<15}{fit_all['converged']}")

        row = {"explosion_depth": depth, "n_choice_sets_full": fit_all["n_choice_sets"],
               "in_sample_pseudo_r2": fit_all["pseudo_r2"], "holdout_pseudo_r2": holdout_r2,
               "n_choice_sets_holdout": n_test_sets, "converged": fit_all["converged"],
               "bc_benchmark_low": lo, "bc_benchmark_high": hi}
        for v in BC_VARS:
            row[f"beta_{v}"] = fit_all["beta"][v]
        results_rows.append(row)

    results = pd.DataFrame(results_rows)
    results.to_csv(OUT_PATH, index=False)

    print("\n--- E=1 standardized coefficients (in-sample), ranked by |beta| ---")
    e1 = results_rows[0]
    coefs = sorted([(v, e1[f"beta_{v}"]) for v in BC_VARS], key=lambda t: -abs(t[1]))
    for v, b in coefs:
        print(f"  {v:<15} {b:+.4f}")

    print(f"\nSaved full results to {OUT_PATH}")
    return results


if __name__ == "__main__":
    main()
