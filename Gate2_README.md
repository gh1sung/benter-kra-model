# Gate 2 deliverables — index

**Status: PASSED** (10-variable model: baseline-9 + `CAREER_STARTS`). See `Gate2_Report.md` for full detail.

## Read this first
- `Gate2_Report.md` — the final write-up: bug found, fix, corrected ablation, final test, calibration, verdict.

## Data
- `gate2_features_built.csv` — production feature file (369,139 rows), includes `ROUTE_RESIDUAL` (renamed from `DIST_RESIDUAL`) and all Gate 2 candidate columns.

## Code (current, corrected)
- `fit_engine.py` — fitting engine incl. the `race_safe=True` fix and `sample_diagnostics()`.
- `ablation2.py` — corrected block-ablation / forward-addition harness.
- `select_lambda2.py` — corrected ridge-lambda selection.
- `run_final_test2.py` — corrected frozen final test (single-touch, 2024–2026).
- `test_fit_engine.py` — toy unit tests for the fitting engine (still valid, unaffected by the bug/fix).

## Results (current, corrected)
- `ablation2_results_raw.csv` — all 8 walk-forward folds × 9 configs.
- `lambda_selection2.csv` — ridge lambda grid results.
- `final_test_results2.csv` — final E=1/2/3 test metrics.
- `final_calibration_table2.csv` — Benter-style calibration table, final model.

## `deprecated_pre_audit/`
The original (buggy) Gate 2 pass, kept for the record — not for use. An external audit caught a real bug (`dropna` silently dropping individual horses, including sometimes the actual winner, from otherwise-surviving races); this made `DIST_RESIDUAL` look far stronger than it was. Everything in this folder predates the fix and is superseded by the files above.
