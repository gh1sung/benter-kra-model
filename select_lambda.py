"""Ridge lambda selection: walk-forward over the 2021-2023 validation pool,
using the surviving 11-variable model (baseline9 + CAREER_STARTS + DIST_RESIDUAL).
Picks the lambda minimizing average held-out log loss per choice set."""
import pandas as pd
from fit_engine import build_estimation_sample, explode, fit_mnl_ridge, score_holdout

FINAL_VARS = ["AVESPRAT", "LSPEDRAT", "LIFE_PCT_WIN", "W_PER_RACE", "JOCK_PCT_WIN",
              "JOCK_NUM_WIN", "WEIGHT", "POSTPOS", "NEWDIST", "CAREER_STARTS", "DIST_RESIDUAL"]

df = pd.read_csv("gate2_features_v3.csv", dtype={"race_id": str}, low_memory=False)
df["race_date"] = pd.to_datetime(df["race_date"])
df["year"] = df["race_date"].dt.year

rows = []
for test_year in [2021, 2022, 2023]:
    train = df[df["year"] < test_year]
    test = df[df["year"] == test_year]
    train_sample = build_estimation_sample(train, FINAL_VARS)
    test_sample = build_estimation_sample(test, FINAL_VARS)
    exploded_train = explode(train_sample, 1, FINAL_VARS)
    exploded_test = explode(test_sample, 1, FINAL_VARS)
    for lam in [0.0, 1.0, 5.0, 20.0, 50.0, 100.0]:
        fit = fit_mnl_ridge(exploded_train, FINAL_VARS, lam=lam)
        r2, logloss, n_sets = score_holdout(exploded_test, FINAL_VARS, fit["beta_raw"], fit["mu"], fit["sigma"])
        rows.append({"test_year": test_year, "lambda": lam, "test_r2": r2,
                     "test_logloss_per_set": logloss / n_sets, "n_sets": n_sets, "converged": fit["converged"]})
        print(f"year={test_year} lambda={lam:<6} r2={r2:.4f} logloss/set={logloss/n_sets:.4f} converged={fit['converged']}")

res = pd.DataFrame(rows)
res.to_csv("lambda_selection.csv", index=False)
print("\n=== mean logloss/set by lambda across 3 validation folds ===")
print(res.groupby("lambda")["test_logloss_per_set"].mean().round(4))
