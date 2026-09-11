"""
Gate 2, Section 7: block ablation + forward addition process.

Primary metric: out-of-sample log loss (lower = better). Pseudo-R^2 reported
secondarily for continuity with Gate 1.

Compute note: this process runs at explosion depth E=1 only (Gate 1's primary
comparison point, ~0.09 B&C benchmark) to keep the fold x config x lambda grid
tractable. The frozen final model is re-checked at E=1/2/3 in run_final_test.py.

Chronological folds (walk-forward, expanding train window, pooled Seoul+Busan):
  Dev pool:        train through Y-1 -> test Y, for Y in 2016..2020  (5 folds)
  Validation pool: train through Y-1 -> test Y, for Y in 2021..2023  (3 folds)
Training for a given fold always uses ALL prior years back to 2008 (expanding),
never a fixed window.

HORSE_RATING handling: 100% null before 2015 (see Section: HORSE_RATING
investigation). Listwise-dropping it would zero out training data for every
fold testing years <=2015 and severely shrink 2016-2018 folds too. Instead,
for any config that includes the Rating block, HORSE_RATING is mean-imputed
using ONLY that fold's own training-set mean (leakage-safe, recomputed fresh
per fold), with HAS_RATING included alongside so the model can learn to
downweight the imputed value when coverage was absent.
"""
import numpy as np
import pandas as pd
from fit_engine import build_estimation_sample, explode, fit_mnl_ridge, score_holdout

IN_PATH = "gate2_features_v3.csv"

BASE9 = ["AVESPRAT", "LSPEDRAT", "LIFE_PCT_WIN", "W_PER_RACE", "JOCK_PCT_WIN",
         "JOCK_NUM_WIN", "WEIGHT", "POSTPOS", "NEWDIST"]

BLOCKS = {
    "Trainer": ["TRAINER_PCT_WIN", "TRAINER_NUM_WIN"],
    "CareerStarts": ["CAREER_STARTS"],
    "Recency": ["DAYS_SINCE_LAST_RACE"],
    "Rating": ["HORSE_RATING_FILLED", "HAS_RATING"],
    "DistResidual": ["DIST_RESIDUAL"],
}
ALL_BLOCK_VARS = [v for vs in BLOCKS.values() for v in vs]
FULL_MODEL = BASE9 + ALL_BLOCK_VARS

DEV_TEST_YEARS = [2016, 2017, 2018, 2019, 2020]
VAL_TEST_YEARS = [2021, 2022, 2023]


def load_data():
    df = pd.read_csv(IN_PATH, dtype={"race_id": str}, low_memory=False)
    df["race_date"] = pd.to_datetime(df["race_date"])
    df["year"] = df["race_date"].dt.year
    return df


def prep_fold(df, test_year):
    """Split into (train, test) raw dataframes for a walk-forward fold, and
    fold-local mean-impute HORSE_RATING using train-only statistics."""
    train = df[df["year"] < test_year].copy()
    test = df[df["year"] == test_year].copy()
    fill_val = train["horse_rating"].mean()  # train-only, no leakage
    train["HORSE_RATING_FILLED"] = train["horse_rating"].fillna(fill_val)
    test["HORSE_RATING_FILLED"] = test["horse_rating"].fillna(fill_val)
    return train, test


def run_config(train, test, var_list, lam=0.0, depth=1):
    """Fit on train, score on test. Returns dict of metrics, or None if either
    side ends up with too few choice sets to fit meaningfully."""
    train_sample = build_estimation_sample(train, var_list)
    test_sample = build_estimation_sample(test, var_list)
    if train_sample["race_id"].nunique() < 30 or test_sample["race_id"].nunique() < 10:
        return None

    exploded_train = explode(train_sample, depth, var_list)
    exploded_test = explode(test_sample, depth, var_list)
    if len(exploded_train) == 0 or len(exploded_test) == 0:
        return None

    fit = fit_mnl_ridge(exploded_train, var_list, lam=lam)
    r2_test, logloss_test, n_test_sets = score_holdout(
        exploded_test, var_list, fit["beta_raw"], fit["mu"], fit["sigma"]
    )
    return {
        "train_r2": fit["pseudo_r2"],
        "test_r2": r2_test,
        "test_logloss": logloss_test,
        "test_logloss_per_set": logloss_test / n_test_sets if n_test_sets else np.nan,
        "n_train_sets": fit["n_choice_sets"],
        "n_test_sets": n_test_sets,
        "converged": fit["converged"],
    }


def run_all_folds(df, configs, test_years, lam=0.0, depth=1, label=""):
    rows = []
    for y in test_years:
        train, test = prep_fold(df, y)
        for cfg_name, var_list in configs.items():
            res = run_config(train, test, var_list, lam=lam, depth=depth)
            if res is None:
                continue
            res.update({"pool": label, "test_year": y, "config": cfg_name, "lambda": lam})
            rows.append(res)
    return pd.DataFrame(rows)


def build_configs():
    configs = {"baseline9": BASE9}
    for name, vs in BLOCKS.items():
        configs[f"baseline9+{name}"] = BASE9 + vs
    configs["full_model"] = FULL_MODEL
    for name, vs in BLOCKS.items():
        configs[f"full_minus_{name}"] = [v for v in FULL_MODEL if v not in vs]
    return configs


def main():
    df = load_data()
    configs = {"baseline9": BASE9}
    for name, vs in BLOCKS.items():
        configs[f"baseline9+{name}"] = BASE9 + vs
    configs["full_model"] = FULL_MODEL
    for name, vs in BLOCKS.items():
        configs[f"full_minus_{name}"] = [v for v in FULL_MODEL if v not in vs]

    print("Running dev-pool walk-forward folds (2016-2020)...")
    dev_results = run_all_folds(df, configs, DEV_TEST_YEARS, lam=0.0, depth=1, label="dev")
    print("Running validation-pool walk-forward folds (2021-2023)...")
    val_results = run_all_folds(df, configs, VAL_TEST_YEARS, lam=0.0, depth=1, label="validation")

    all_results = pd.concat([dev_results, val_results], ignore_index=True)
    all_results.to_csv("ablation_results_raw.csv", index=False)
    print(f"\nSaved {len(all_results)} rows to ablation_results_raw.csv")
    return all_results


def run_one_year(test_year, label, group=None, out_path="ablation_results_raw.csv"):
    """Run configs for a single walk-forward fold (one test year) and append
    to out_path. Designed to be called once per year (optionally split into
    a config subgroup 'A' or 'B') so each run stays within a single
    shell-call time budget -- later years have larger expanding training
    windows and can exceed it if all 12 configs run in one call."""
    import os
    df = load_data()
    configs = build_configs()
    if group == "A":
        names = ["baseline9"] + [f"baseline9+{n}" for n in BLOCKS]
    elif group == "B":
        names = ["full_model"] + [f"full_minus_{n}" for n in BLOCKS]
    else:
        names = list(configs.keys())
    configs = {k: v for k, v in configs.items() if k in names}

    result = run_all_folds(df, configs, [test_year], lam=0.0, depth=1, label=label)
    write_header = not os.path.exists(out_path)
    result.to_csv(out_path, mode="a", header=write_header, index=False)
    print(f"year={test_year} label={label} group={group}: {len(result)} config rows appended to {out_path}")
    print(result[["config", "test_r2", "test_logloss", "n_test_sets", "converged"]].to_string(index=False))


if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 3:
        grp = sys.argv[3] if len(sys.argv) > 3 else None
        run_one_year(int(sys.argv[1]), sys.argv[2], group=grp)
    else:
        main()
