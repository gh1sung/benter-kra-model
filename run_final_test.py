"""
Gate 2 FROZEN FINAL MODEL -- touched exactly once, per Section 7 rules.

Frozen spec (locked BEFORE looking at any 2024-2026 result):
  Variables: baseline 9 (AVESPRAT, LSPEDRAT, LIFE_PCT_WIN, W_PER_RACE,
             JOCK_PCT_WIN, JOCK_NUM_WIN, WEIGHT, POSTPOS, NEWDIST)
             + CAREER_STARTS + DIST_RESIDUAL  (11 total)
  Dropped candidates (weak/inconsistent validation-pool gains): Trainer block,
             DAYS_SINCE_LAST_RACE, HORSE_RATING/HAS_RATING.
  Deferred (unresolved prerequisite): CLASS_MOVE.
  Ridge lambda = 20 (selected on 2021-2023 validation pool walk-forward).
  Train: 2008-2023 (dev + validation pools, pooled Seoul+Busan).
  Test:  2024 - mid 2026 (untouched until this run).
"""
import pandas as pd
from fit_engine import build_estimation_sample, explode, fit_mnl_ridge, score_holdout, calibration_table

FINAL_VARS = ["AVESPRAT", "LSPEDRAT", "LIFE_PCT_WIN", "W_PER_RACE", "JOCK_PCT_WIN",
              "JOCK_NUM_WIN", "WEIGHT", "POSTPOS", "NEWDIST", "CAREER_STARTS", "DIST_RESIDUAL"]
LAMBDA = 20.0

df = pd.read_csv("gate2_features_v3.csv", dtype={"race_id": str}, low_memory=False)
df["race_date"] = pd.to_datetime(df["race_date"])
df["year"] = df["race_date"].dt.year

train = df[df["year"] <= 2023]
test = df[df["year"] >= 2024]

train_sample = build_estimation_sample(train, FINAL_VARS)
test_sample = build_estimation_sample(test, FINAL_VARS)
print(f"Train: {train_sample['race_id'].nunique():,} races, {len(train_sample):,} horse-rows")
print(f"Test:  {test_sample['race_id'].nunique():,} races, {len(test_sample):,} horse-rows")

results = []
for depth in [1, 2, 3]:
    exploded_train = explode(train_sample, depth, FINAL_VARS)
    exploded_test = explode(test_sample, depth, FINAL_VARS)

    fit = fit_mnl_ridge(exploded_train, FINAL_VARS, lam=LAMBDA)
    r2_test, logloss_test, n_test_sets = score_holdout(
        exploded_test, FINAL_VARS, fit["beta_raw"], fit["mu"], fit["sigma"]
    )
    print(f"\n=== Depth E={depth} ===")
    print(f"train pseudo_r2={fit['pseudo_r2']:.4f}  n_train_sets={fit['n_choice_sets']:,}")
    print(f"TEST  pseudo_r2={r2_test:.4f}  log_loss={logloss_test:.2f}  "
          f"log_loss/set={logloss_test/n_test_sets:.4f}  n_test_sets={n_test_sets:,}  converged={fit['converged']}")
    row = {"depth": depth, "train_pseudo_r2": fit["pseudo_r2"], "test_pseudo_r2": r2_test,
           "test_log_loss": logloss_test, "test_log_loss_per_set": logloss_test / n_test_sets,
           "n_train_sets": fit["n_choice_sets"], "n_test_sets": n_test_sets, "converged": fit["converged"]}
    for v in FINAL_VARS:
        row[f"beta_{v}"] = fit["beta"][v]
    results.append(row)

    if depth == 1:
        cal = calibration_table(exploded_test, FINAL_VARS, fit["beta_raw"], fit["mu"], fit["sigma"])
        cal.to_csv("final_calibration_table.csv", index=False)
        print("\n--- Calibration table (E=1, test pool) ---")
        print(cal.to_string(index=False))

pd.DataFrame(results).to_csv("final_test_results.csv", index=False)
print("\nSaved final_test_results.csv and final_calibration_table.csv")

print("\n--- E=1 final standardized coefficients, ranked by |beta| ---")
e1 = results[0]
coefs = sorted([(v, e1[f"beta_{v}"]) for v in FINAL_VARS], key=lambda t: -abs(t[1]))
for v, b in coefs:
    print(f"  {v:<16} {b:+.4f}")
