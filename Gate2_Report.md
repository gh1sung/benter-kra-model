# Gate 2 — Full Fundamental Model: Results & Write-Up (corrected after audit)

Pooled Seoul + Busan, 2008 – July 2026, 369,139 horse-race rows. **This report supersedes the original Gate 2 write-up**, which had a real correctness bug — caught by an external audit (GPT), independently verified against the data below, and fixed. The original report and results are preserved in `deprecated_pre_audit/` for the record; nothing was deleted or hidden.

## 0. The bug, verified

The original estimation-sample code (inherited unchanged from the already-frozen Gate 1 `fit_bc_checksum.py`) did this:

```python
sample = df.loc[mask].dropna(subset=var_list)
```

This drops individual **horse-rows** missing a feature, not whole races. A race could keep running with 8 of its 9 real starters if the 9th (sometimes the actual winner) was missing one feature — the code would then treat the best-finishing *remaining* horse as "the winner" of that choice set.

I reproduced this independently before touching any code, and it matched the external audit's numbers almost exactly: of 5,913 base-eligible races with a real winner, the old baseline-9 sample kept the winner in 5,560 races, and the old final-11-variable sample kept it in only 4,428 — **1,485 actual winners silently missing**. In the untouched 2024–2026 test period specifically, 179 of 1,015 races (17.6%) lost their true winner this way (audit's estimate: 178, 17.5% — same finding to within rounding).

**Root cause, isolated:** `CAREER_STARTS` has 0% missingness in the base-eligible sample (it's always defined for a real start), so it never triggered this. `DIST_RESIDUAL` has ~19% missingness (first-ever route start for a horse), and is responsible for essentially the entire jump from 380 affected races (6.4%, baseline-9 alone) to 1,080 (19.6%, the old final model). So the bug was real and general, but its practical damage was concentrated almost entirely in one variable.

## 1. The fix

`fit_engine.build_estimation_sample` now defaults to `race_safe=True`: if *any* base-eligible horse in a race is missing a required feature, the **whole race** is dropped — never just that horse. I verified this mathematically, not just by eyeballing it: for every race where the true winner satisfies the same base-eligibility filters as everyone else (real finish, distance/condition, age ≥ 3), the winner is now present in 100% of retained races — 0 exceptions, checked directly. The only remaining "winner not in the sample" cases (75 of 4,591 races for baseline-9, 1.6%) are races where the actual winner was a 2-year-old — excluded by the pre-existing, intentional age≥3 restriction carried over from Bolton & Chapman's own methodology, not a completeness artifact.

Added `fit_engine.sample_diagnostics()`, which every fold now reports: race/starter counts, missing-winner count and rate, and field size before/after. This is the transparency GPT's audit asked for.

## 2. DIST_RESIDUAL → renamed ROUTE_RESIDUAL

Second, separate issue from the audit, also confirmed: the Gate 2 estimation sample is restricted to 1600–2000m, so under the sprint(<1600m)/route(≥1600m) bucketing, **every target row falls in the route bucket by construction**. The variable never actually distinguishes 1600m from 1800m from 2000m preference within this sample — it's really "how has this horse performed relative to expectation in route races generally." Renamed to `ROUTE_RESIDUAL` to stop overclaiming what it measures. Also built a data-efficient variant, `ROUTE_RESIDUAL_FILLED` + `HAS_ROUTE_RESIDUAL`, using the same train-fold-only mean-imputation pattern already validated for `HORSE_RATING`, so the model isn't forced to sacrifice most of its races just to use this one feature.

## 3. Ablation, rerun honestly

Reran all 8 walk-forward folds (5 dev, 3 validation) under `race_safe=True`. Two comparisons matter here:

**Apples-to-apples (same race population as baseline-9 in every fold)** — this is the trustworthy comparison, since `CAREER_STARTS`, `Trainer`, `Recency`, `Rating`, and `ROUTE_RESIDUAL_FILLED` all retain the *exact same races and field sizes* as baseline-9 alone (confirmed row-for-row in the diagnostics):

| Block | Mean improvement (8 folds) | Dev | Validation | Folds improved |
|---|---|---|---|---|
| CAREER_STARTS | **0.0398** | 0.0499 | 0.0230 | 8/8 |
| ROUTE_RESIDUAL_FILLED | 0.0078 | 0.0119 | 0.0010 | 6/8 |
| Trainer | 0.0064 | 0.0097 | 0.0009 | 6/8 |
| Recency | 0.0094 | 0.0171 | -0.0035 | 4/8 |
| Rating | 0.0018 | 0.0043 | -0.0025 | 6/8 |

**This is the headline finding of the audit.** Under the OLD (buggy) comparison, `DIST_RESIDUAL` looked like the single strongest variable in the whole candidate pool (mean improvement 0.149, 8/8 folds). Under the corrected, apples-to-apples comparison, `ROUTE_RESIDUAL_FILLED`'s honest contribution is 0.0078 — smaller than `Recency`'s, in the same weak/inconsistent tier as the three blocks already dropped, and its validation-pool effect (0.0010) is close to zero. GPT's suspicion was correct: most of the old result was the model getting an easier, systematically-more-experienced subset of horses to predict, not a real signal.

Direct ablation on the combined 10/11-var candidate confirms this: adding `ROUTE_RESIDUAL_FILLED` on top of `CAREER_STARTS` improves log loss in only 6/8 folds (mean -0.0044, i.e. tiny, and it actively hurts the 2021 validation fold). Adding `CAREER_STARTS` on top of `ROUTE_RESIDUAL_FILLED` improves log loss in 8/8 folds (mean -0.0363) — all the real signal is coming from `CAREER_STARTS`.

**Decision: `ROUTE_RESIDUAL` is dropped from the final model, using the exact same "small/inconsistent validation-pool gains → drop" rule already applied to Trainer/Recency/Rating.** The raw (non-imputed) version of `ROUTE_RESIDUAL` still shows a large apparent improvement in isolation (mean 0.15+, similar to before), but that comparison uses a much smaller, systematically different race population (races where every horse happens to have route history) and isn't trusted as a basis for inclusion — it's reported below as a diagnostic curiosity only, not a decision input.

**Final roster: baseline-9 + CAREER_STARTS only (10 variables).** This is a real downgrade from the previously reported 11-variable model, and it's the correct one.

## 4. Ridge lambda, re-selected

Walk-forward on 2021-2023 with the corrected 10-variable model, expanded grid up to λ=2000. The curve is still shallow (this model isn't overfitting much), with the aggregate minimum around **λ=100** (mean log-loss/set 2.0842, vs. 2.0873 at λ=0). Selected λ=100.

## 5. Frozen final model — 2024-2026, rerun under the fix

Trained 2008-2023, race-safe sample: 3,644 races / 39,493 horse-rows. Tested on 2024-2026: 947 retained races (of 1,015 base-eligible), 9,851 horse-rows. **Winner-present rate in the test pool: 98.1%** (18 of 947 races missing the winner, all confirmed to be age-2 winners excluded by design — 0 completeness-driven losses).

| Depth | Train pseudo-R² | Test pseudo-R² | Test log loss | Log loss/set | Converged |
|---|---|---|---|---|---|
| E=1 | 0.1672 | **0.1424** | **1,893.84** | 1.9998 | Yes |
| E=2 | 0.1352 | 0.1150 | 3,822.04 | 2.0180 | Yes |
| E=3 | 0.1112 | 0.0949 | 5,719.98 | 2.0134 | Yes |

(For reference, the old buggy 11-variable result was test pseudo-R²=0.1391, log loss=1,902.19 — the corrected, simpler 10-variable model performs essentially the same or marginally better, and this time the number can actually be trusted. The E=2 non-convergence from the old run is also gone.)

Final E=1 standardized coefficients:

```
CAREER_STARTS    -0.4037
AVESPRAT         +0.3519
LSPEDRAT         +0.2941
WEIGHT           +0.1641
JOCK_PCT_WIN     +0.1534
W_PER_RACE       +0.1386
LIFE_PCT_WIN     +0.1376
NEWDIST          -0.1111
JOCK_NUM_WIN     +0.0694
POSTPOS          -0.0589
```

`CAREER_STARTS` remains negative and the largest-magnitude coefficient — consistent with the earlier finding (more accumulated starts without graduating up correlates with lower quality: r=0.71 with horse_age, r=-0.13 with AVESPRAT, r=+0.15 with worse finish rank).

**Calibration (E=1):** same qualitative pattern as before — well-calibrated through the low-to-mid probability range, mildly overconfident at the top (predicted 40-50%: actual 32.9%, z=-1.92; predicted 50%+: actual 54.2%, z=-1.46). Slightly less extreme than the old run's z-scores (-2.32/-2.11), but the same direction and the same story: this is the textbook Benter finding (his own Tables 3/4 show the fundamental model is badly overconfident specifically where it disagrees with the public in its own favor), and it's exactly what the planned Stage 2 combination with public odds is designed to correct.

**Caveat carried forward, per the audit's own recommendation:** 2024-2026 was already scored once under the old, buggy methodology before this fix. It is no longer a pristine, never-inspected holdout in the strictest sense, even though nothing was tuned in response to its old numbers. Treat it as a known diagnostic set from here forward — a genuinely untouched period should be reserved for the next true single-touch test.

## 6. Bottom line

The audit was right, and it mattered: one new variable (the renamed `ROUTE_RESIDUAL`, née `DIST_RESIDUAL`) accounted for nearly all of a real methodology bug, and once evaluated fairly, that variable's own contribution turned out to be noise-level, not a real signal — it's dropped. `CAREER_STARTS` is the only new variable that survives an honest, apples-to-apples test, and it does so robustly across all 8 folds. The corrected 10-variable final model performs essentially identically to the old (wrongly) 11-variable one on the 2024-2026 test — meaning the extra complexity was buying nothing, which is exactly what a correct ablation process should reveal. `CLASS_MOVE` remains blocked pending [data team lead]'s input, unchanged from before.
