# B&C Track-Record Speed Rating Rebuild — Validation Report

## Implementation decisions

- **Track-record bucket:** `(region, distance)` only. `race_class` and `track_condition` are excluded, matching the paper’s track-and-distance wording. This is an interpretive choice because the paper does not provide implementation code.
- **Cross-track adjustment:** no extra unidentified normalization. Seoul and Busan are separately anchored to their own historical records through `region`.
- **Look-ahead control:** the baseline is computed at the race level. For each `(region, distance)` bucket, races are ordered by `race_date` and `race_id`; the expanding minimum is shifted by one race. Every horse in the same race therefore receives the same pre-race baseline, and a record set in the current race can only affect later races.
- **Coverage threshold:** at least 10 prior completed races in the bucket before assigning `raw_speed_rating`.
- **Formula:** `100 - 5 * (goal_time - track_record_time)`. No clipping is applied; a horse breaking the prior record can score above 100.

## Validation

- Row count: **369,139 in / 369,139 out**.
- `(race_id, horse_id)` uniqueness: **369,139 unique pairs** after rebuild.
- Same-race baseline: maximum distinct `track_record_time` values within a race = **1**.
- Manual horse check: horse `3107` confirmed first-start `AVESPRAT`/`LSPEDRAT` are null; each later `LSPEDRAT` equals the immediately prior start’s raw rating; `AVESPRAT` equals the mean of the prior four starts only.
- Coverage among rows with `goal_time`: **92.07% in 2008**, **99.66% in 2009**, and essentially 100% from 2012 onward, with minor dips from newly appearing or thin distance buckets.
- Toy explosion/MLE test: pseudo-R² = **0.999999945**, predictive-feature beta = **18.328**, maximum absolute noise-feature beta = **0**, optimizer converged.
- Fast grouped likelihood implementation was checked against the original implementation on a 150-race subset: pseudo-R² difference **2.22e-16**, maximum beta difference **1.11e-16**.
- The unchanged full script completed E=1 and E=2 with the same values before exceeding the environment limit at E=3; E=3 was obtained using the numerically equivalent grouped implementation.

The pre-existing non-speed variables were not recomputed. Reading and rewriting the CSV introduces only floating-point serialization noise in three columns (maximum absolute difference below `3e-8`); the feature values are substantively unchanged.

## Pseudo-R² comparison

| Depth | Old z-score | New track-record | B&C published | Change vs old | New holdout |
|---:|---:|---:|---:|---:|---:|
| E=1 | 0.154916 | 0.140532 | 0.091 | -0.014384 (-9.3%) | 0.106008 |
| E=2 | 0.124846 | 0.113340 | 0.064 | -0.011506 (-9.2%) | 0.088963 |
| E=3 | 0.103381 | 0.092696 | 0.055 | -0.010685 (-10.3%) | 0.076339 |

The reformulation lowers in-sample pseudo-R² by roughly 9–10% at every depth, but it does **not** close the gap. The new estimates remain about **1.54×, 1.77×, and 1.69×** the published B&C values at E=1, E=2, and E=3.

## Fixed common-sample check

The speed formulation changes listwise feature coverage, so the headline models do not use exactly the same race set: the new sample loses 16 old races and gains 12 others. To isolate the metric itself, both versions were refit on the identical **61,207 horse rows across 5,911 races**.

| Depth | Old z-score, common sample | New track-record, common sample | Change |
|---:|---:|---:|---:|
| E=1 | 0.155320 | 0.140893 | -0.014427 (-9.3%) |
| E=2 | 0.125560 | 0.112309 | -0.013251 (-10.6%) |
| E=3 | 0.103908 | 0.091251 | -0.012657 (-12.2%) |

This confirms that the decline is caused by the speed-rating reformulation, not by the small change in race coverage. Even on the common sample, the new values remain materially above B&C.

## E=1 standardized coefficients

| Variable | Old z-score beta | New track-record beta | Change |
|---|---:|---:|---:|
| AVESPRAT | +0.431179 | +0.406437 | -0.024742 |
| LIFE_PCT_WIN | +0.247249 | +0.307038 | +0.059790 |
| JOCK_PCT_WIN | +0.213583 | +0.217783 | +0.004200 |
| LSPEDRAT | +0.307837 | +0.197931 | -0.109906 |
| WEIGHT | +0.153185 | +0.191742 | +0.038558 |
| NEWDIST | -0.082653 | -0.186165 | -0.103512 |
| W_PER_RACE | +0.161324 | +0.154944 | -0.006380 |
| JOCK_NUM_WIN | +0.055169 | +0.071990 | +0.016821 |
| POSTPOS | -0.062217 | -0.063529 | -0.001312 |

AVESPRAT remains the largest coefficient, but it moves from **0.431** to **0.406**, farther from B&C’s published **0.562**. Its ratio to the sum of the absolute values of the other eight coefficients falls from **0.336** to **0.292**. WEIGHT rises from **0.153** to **0.192**, rather than moving toward B&C’s **0.012**.

## Conclusion

The track-record formulation explains a meaningful minority of the original pseudo-R² gap, but not most of it. The result rejects the strong version of hypothesis 1: the z-score construction was not the primary reason the Korean checksum exceeded B&C. The fixed common-sample refit confirms that coverage differences are not driving the result. The next diagnostic should be WEIGHT and its mechanical relationship to the Korean rating/class system.

A secondary caveat is the raw-rating lower tail. The minimum is -346, driven by exceptionally slow/DQ/pulled-up times; no outlier clipping was added because it is not in the requested B&C formula and would create another methodological deviation.