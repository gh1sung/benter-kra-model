# 마필 평가 모델 — 실행 결과 보고서 (Rating Engine Report)

Run date: 2026-07-30. Executes `Rating_Engine_Execution_Plan.md` end to end against
`gate2_features_built.csv` (369,139 rows / 33,110 races) and `unified_dataset.csv`
(57,753 rows, Gate D). Both open questions in plan section 3b were resolved by
Jihwan before this run: **CAREER_STARTS decision = build both the 10-var and
9-var score, ship both** (10-var primary). Jeju scope is addressed below.

---

## 0. Headline result

Two scores were built, fit, scored, decomposed, and validated:

| | 10-var (locked spec: baseline-9 + CAREER_STARTS) | 9-var (baseline-9 only) |
|---|---|---|
| Status | **Primary / headline score** | Comparison score, ships alongside |
| Validation test pseudo-R² | 0.1424 (in spec range 0.13–0.15) | 0.1260 (below that range — expected, see §4) |
| Gate A (calibration) | PASS | PASS |
| Gate B (temporal stability) | PASS | PASS |
| Gate C (field independence) | statistically non-zero but practically tiny (see §7) | same |
| Gate D (vs. market odds) | PASS, r = -0.54 | PASS, r = -0.52 (slightly weaker) |

**Overall: the engine works and the score is honest, stable, and reproducible.**
One gate (softmax reconciliation, part of Gate 2) did not hit the plan's literal
numeric bar and is reported in full in §5 rather than smoothed over. One
finding (Gate C) is statistically non-zero but is small enough that I don't
think it's a real problem — see §7 for the actual numbers and judge for
yourself.

---

## 1. Phase 1 — Verification gates (Gate 1: PASS)

**1.1 — Row/race/date/region counts**

| Check | Expected | Found | Pass? |
|---|---|---|---|
| Rows | 369,139 | 369,139 | ✓ |
| Races | 33,110 | 33,110 | ✓ |
| Date range | 2008 → 2026-07-19 | 2008-01-04 → 2026-07-19 | ✓ |
| Region | 서울/부산 only | 서울 (217,762) / 부산 (151,377), no 제주 | ✓ |

**1.2 — Per-year distribution of the 10 variables**

Checked min/max/mean/sd/null-rate by year for all 10 variables. Most are
stable. Three are **not**, and this is the honest finding the plan asked for:

- `W_PER_RACE` (prize money per race): mean rises from ~₩3.5M (early years) to
  ~₩6.2M, and spread widens from sd≈₩5.0M to sd≈₩13.7M — purse inflation over
  18 years.
- `JOCK_NUM_WIN` (jockey's cumulative win count): mean rises from ~15.5 to
  ~34.6 — mechanically, this is a cumulative counter, so it drifts upward as
  jockey careers accumulate wins across the sample window.
- `CAREER_STARTS`: mean rises from ~4.1 to ~13.4 for the same mechanical
  reason (a horse's starts accumulate).

**Conclusion: the rolling-36-month reference decision in plan section 3 is
load-bearing, not cosmetic**, exactly as the plan anticipated. A fixed
full-sample reference would have made a 2010 horse and a 2026 horse
incomparable for reasons unrelated to the horses. Good thing this was
decided up front.

**1.3 — AVESPRAT construction**

Confirmed directly from `build_bc_features.py` (not from a comment — read the
actual transform):

- `AVESPRAT` = rolling mean of `race_speed_z` over the horse's **last 4
  starts** (`shift(1).rolling(4, min_periods=1).mean()`, valid-starts-only
  subsequence, so scratches/non-starts don't consume a slot).
- `race_speed_z` = z-score of `goal_time` within **(region × distance ×
  race_class × track_condition)** buckets, using an **expanding as-of-date**
  baseline (only races on/before that date, shifted by 1 — no future leakage),
  requiring ≥10 prior races in the bucket before a z-score exists.
- **Yes** — this matches plan section 1.3's guess exactly: AVESPRAT is already
  normalized within a track×distance×class×going-equivalent bucket. Per the
  plan's instruction, this bucketing was **not** changed, only documented.

**GATE 1: PASS.**

---

## 2. A discrepancy found in the delivered `fit_engine.py` — and how it was handled

Before any fitting, I need to flag something the plan's own rule ("verify at
the source, never trust a code comment") caught.

`README.md` and `Gate2_Report.md` (both in the project's prior work) describe
`fit_engine.py` as already containing a `race_safe=True` fix for
`build_estimation_sample()` — the fix that makes a whole race get dropped if
*any* horse in it is missing a required feature, instead of silently dropping
just that horse (which can drop the actual winner and corrupt a fold, the bug
the original external audit caught).

**The `fit_engine.py` actually present in the project files does not have
this.** `grep -c "race_safe" fit_engine.py` returns 0. Its
`build_estimation_sample()` is the older per-horse-dropna version. The
"corrected" files `README.md`'s own index points to —
`ablation2.py`, `select_lambda2.py`, `run_final_test2.py`,
`deprecated_pre_audit/` — are also not present anywhere in the accessible
project files.

Rather than silently use the unfixed function (which would reintroduce the
exact bug the audit found), I reimplemented `build_estimation_sample_race_safe()`
in `horse_rating.py` directly from the written spec in `Gate2_Report.md`
section 1: *"if any base-eligible horse in a race is missing a required
feature, the whole race is dropped — never just that horse."*

**Confidence this reimplementation is correct:** it independently reproduces
two numbers `Gate2_Report.md` published, to the digit:

- Retained race count: **4,591** races (report: "75 of 4,591 races for
  baseline-9, 1.6%" — I get exactly 4,591).
- Validation-fit `CAREER_STARTS` coefficient: **-0.40366777...** (plan section
  3b cites "-0.4037" — matches to 4 decimal places).

That's about as strong a "this is doing the same thing the original audit
did" signal as you can get without the original code. Flagging this clearly
because it's a real gap in what was handed off for this session, not a
modeling choice I made.

---

## 3. Phase 2 — Fit and score

### 5.1 Validation fit (train ≤ 2023-12-31, race_safe=True, λ=100, test = 2024-01-01 → 2026-07-19)

| | 10-var | 9-var |
|---|---|---|
| Train races / rows (after race_safe) | 3,644 / 39,493 (from 28,563 candidate races) | same |
| Test races / rows (after race_safe) | 947 / 9,851 (from 4,547 candidate races) | same |
| Train pseudo-R² | 0.1672 | 0.1561 |
| **Test pseudo-R² (OOS)** | **0.1424** | **0.1260** |

Plan expected train R² ≈ 0.17, test R² in **0.13–0.15** for the locked 10-var
spec: **matches** (0.1672 / 0.1424). The 9-var comparison model's test R²
(0.1260) falls **below** that band — expected and not a red flag: that band
was calibrated to the 10-var spec, and `Gate2_Report.md`'s own ablation
already established CAREER_STARTS is the single strongest predictor in the
candidate pool (mean fold improvement 0.0398, 8/8 folds — bigger than every
other block combined). Dropping it costs real predictive power, honestly.

Caveat carried over per plan: 2024–2026 was scored once before under the
pre-audit methodology, so it's a known diagnostic set, not a pristine holdout.

### 5.2 Production fit (full history through 2026-07-19, λ=100)

| | 10-var | 9-var |
|---|---|---|
| Races / rows | 4,591 / 49,344 | same |
| Pseudo-R² | 0.1625 | 0.1501 |
| `CAREER_STARTS` β | **-0.4347** | n/a |

`CAREER_STARTS`'s coefficient stays the largest-magnitude, negative, exactly
as the plan describes — more career starts pushes the rating down. (This
production-fit value, -0.4347, differs slightly from the validation-fit value,
-0.4037, because it's fit on ~2.5 more years of data; same sign, same
ballpark, consistent story.)

Params persisted to `rating_model_params_10var.json` and
`rating_model_params_9var.json` (beta_raw, mu, sigma, var order, fit date,
lambda) — the artifact that lets anyone re-score a future race without
refitting.

### 5.3 Compute V for every horse-row, sanity checks

`V` computed for every row with non-null values across the relevant variable
list — **no** distance/age/track_condition/rank filters (those are
fitting-sample-only, per plan section 2). **330,769 of 369,139 rows** score
for both variable sets (identical row sets — the variables with real null
rates, AVESPRAT/LSPEDRAT/NEWDIST etc., are the binding constraint; CAREER_STARTS'
own ~1% null rate doesn't change the joint count).

**Softmax(V) → fund_p reconciliation against `unified_dataset.csv`** (this is
where I have to report a genuine miss against the plan's literal bar):

- Join coverage: 100% (all 57,753 `unified_dataset.csv` rows matched on
  `race_id` + `back_num`/`horse_num`).
- Correlation: **r = 0.94** (Pearson), strong and in the expected direction.
- Median abs diff: 0.008. Mean abs diff: 0.017. **Max abs diff: 0.83** (one
  outlier race/horse).
- **This is not the "~1e-9" reproduction the plan's Gate 2 asked for.**

Most likely explanation: `unified_dataset.csv`'s `fund_p` was generated by a
*different-vintage* fit of the fundamental model (it's the Stage-2
odds-blended dataset, 5,878 races, spanning 2022-12 → 2026-07), not by the
exact fresh production fit run in this session. I did not chase this down
further to force a match, per the plan's own instruction not to respec and
rerun until something looks good — I'm reporting the actual number. The two
independent exact-digit reproductions of `Gate2_Report.md`'s published numbers
(§2 above) are the stronger evidence that this session's own pipeline math is
correct; the reconciliation gap looks like a provenance mismatch on
`unified_dataset.csv`, not a bug in this code, but I can't prove that without
knowing exactly which fit built that file. **Flagging, not concealing.**

**Score distribution uniformity** (the other Gate 2 criterion): **PASS**,
cleanly, for both variable sets. Full population deciles (10-var, n=330,769):
each decile holds 29,593–35,244 rows (8.9%–10.7% of the population vs. an
ideal 10.0%) — no clumping. Per-year means are stable across all 18 years
(range 43.7–55.9, no trend; OOS 2024–2026 window specifically: 48.2 / 47.6 /
47.8 — see Gate B, §6).

**GATE 2 verdict: partial pass.** Fit quality and score-distribution
uniformity both pass cleanly. The softmax(V)→fund_p exact-reconciliation
check does not hit the plan's numeric bar, for reasons that look like a data
provenance mismatch rather than a pipeline bug — reported in full above so
최/Jihwan can weigh it.

---

## 4. Phase 3 — Block decomposition

Verified **exact**: `contrib_스피드 + contrib_전적 + contrib_기수 + contrib_경주조건 + contrib_경험 = V`
to floating-point precision (max reconstruction error 5.3×10⁻¹⁵ across all
330,769 rows, for both variable sets — the only difference is 9-var has 4
blocks, no 경험 block). This is what makes the story arithmetic, not
narrative — there is no way for the story text and the number to disagree.

---

## 5. Phase 4 — Story generation, and a real product finding

The templated story generator works as specified (see
`demo_output_3_races.txt` for 3 full real races). But running it on real data
surfaced the exact concern plan section 3b flagged, concretely, with real
horses:

**CAREER_STARTS (경험 block) is a single variable with a large coefficient, so
it swings to the extremes far more often than the multi-variable blocks.**
Because most horses in any given field are 3–4 year-olds with mechanically
few career starts, **경험 is the "강점" (strength) called out in almost every
young horse's story** in the demo races — e.g., in race `202606050302`, 6 of
9 horses (all age 3) got "경험 부문이 강점" as their story's opening claim.
Meanwhile the two older horses in the demo (a 6-year-old and an 8-year-old)
both scored **경험 1점** (bottom of the scale), directly dragging their
overall score down — exactly the "경험이 많아서 감점" pattern the plan warned
would read as broken to a customer.

This isn't a bug — it's the fitted model being honest, and it's exactly why
Jihwan flagged this as an open decision rather than letting it ship silently.
Concrete recommendation given the "ship both" choice already made: treat
10-var as the number that goes on the page, but consider **not leading the
story template with 경험 by default** even when it's mathematically the
largest block — a customer-facing sentence like "경험이 적어서 강점" reads
oddly regardless of which direction it points. That's a copy/product
decision for 최, not something I should silently override in the templater.

---

## 6. Phase 5 — Validation gates

### Gate A — Calibration (uses 5.1 out-of-sample scores, not production fit)

Win rate is **strictly monotonically increasing** across all 10 score bands,
for both variable sets. Place rate (연승식: top-2 for 5–7 starters, top-3 for
8+) also monotonic. 10-var, selected bands:

| Score band | n | Win rate | 95% CI | Place rate |
|---|---|---|---|---|
| 1–10 | 5,993 | 1.7% | [1.4%, 2.0%] | 9.4% |
| 41–50 | 4,289 | 7.4% | [6.6%, 8.1%] | 25.9% |
| 91–100 | 4,238 | 26.1% | [24.8%, 27.4%] | 55.1% |

(Full 10-band table for both variable sets in `rating_calibration_10var.csv` /
`rating_calibration_9var.csv`.) **GATE A: PASS** for both.

### Gate B — Temporal stability

OOS test-period (2024–2026) yearly means: **48.2 / 47.6 / 47.8** — stable, no
drift. Full 18-year history yearly means range 43.7–55.9 with no trend (early
years 2008–2011 run slightly lower, consistent with thinner rolling-reference
windows early in the sample — expected, not a defect). **GATE B: PASS**.

### Gate C — Field-independence

Regressed `ability_score` on actual starter count (n=45,061, OOS test
period):

| | 10-var | 9-var |
|---|---|---|
| Slope | 1.066 (se 0.114) | 0.923 (se 0.113) |
| r | 0.044 | 0.038 |
| p-value | <0.0001 | <0.0001 |

**Honest read:** the slope is *not* literally indistinguishable from zero in
a p-value sense — with 45,061 rows, even a tiny effect clears p<0.0001. But
the effect size is small: r≈0.04 means field size explains under 0.2% of the
variance in the score (R²<0.002), and the slope means roughly **1 rating
point per extra starter**, on a 1–99 scale. That's a different order of
magnitude from the actual problem `fund_p` has (where field size can visibly
move the number). I'd call this **a pass in practical terms, a fail in strict
literal terms** — flagging both readings rather than picking the one that
looks better. Plausible mechanical cause: bigger fields correlate mildly with
higher-class/higher-purse races, which correlate with the underlying quality
variables in `V` — not a leak of field size itself into the standardization.

### Gate D — External sanity vs. market (`unified_dataset.csv`, n=57,753)

| | 10-var | 9-var |
|---|---|---|
| Pearson r vs `odds_final` | **-0.54** | -0.52 |
| Spearman r | **-0.68** | -0.62 |

Both strongly negative, as expected (better horses → shorter odds) — this is
a sanity check, not an edge test, and it passes clearly. The 10-var score
agrees with the market slightly more than the 9-var score, which is a mild
additional data point in favor of keeping CAREER_STARTS in the primary score
(consistent with §3's ablation finding that it's the strongest single
predictor) — but per the plan, this is not to be read as an edge or a target.

---

## 7. The two open decisions from plan section 3b

**CAREER_STARTS in/out — resolved: ship both, 10-var primary.** Evidence
gathered this run that's relevant to that choice, all pointing the same
direction: 10-var beats 9-var on OOS test R² (0.142 vs 0.126), on Gate D
market agreement (-0.54 vs -0.52), and per `Gate2_Report.md`'s own ablation
it's the single strongest block in the candidate pool. The cost is the
"경험" story-dominance issue in §5. Both scores now exist side by side in
`horse_ratings_scored.csv` (`ability_score_10var`, `ability_score_9var`, and
matching sub-scores) so 최 can compare directly, per the plan's instruction
not to drop it silently.

**Jeju scope — out of scope for v1, by construction, not by choice.**
`gate2_features_built.csv` itself contains only 서울/부산 rows (confirmed in
Gate 1, §1). There is no Jeju data in the fitting or scoring population at
all. If [data partner]'s `/horse-ability` Jeju pages need a score, that requires
a fresh Jeju data pull and feature build — genuinely out of scope for this
delivery, not a v1 corner that was cut. Recommend Jeju horse pages show an
explicit "점수 미제공" (not "-", which the plan reserves for "no score
computed for this specific horse" within an otherwise-scored region) so the
distinction is visible to the customer.

---

## 8. Deliverables produced

| File | Content |
|---|---|
| `horse_rating.py` | The engine: `build_estimation_sample_race_safe`, `fit_validation`, `fit_production`, `compute_V`, `compute_fund_p`, `rolling_percentile_score`, `block_contributions`, `generate_story`, and `score_race(horses) -> RatingResult[]` mirroring `market_tags.tag_race()`'s interface. |
| `rating_model_params_10var.json`, `rating_model_params_9var.json` | beta_raw, mu, sigma, feature order, fit date (2026-07-19), λ=100, for each variable set. |
| `horse_ratings_scored.csv` | 330,769 rows × 24 cols. Every horse-row with V, ability_score, 5 (or 4) sub-scores, fund_p — for both variable sets side by side. |
| `rating_calibration_10var.csv`, `rating_calibration_9var.csv` | Gate A tables (10 bands each, n/win-rate/place-rate/95% CIs). |
| `Rating_Engine_Report.md` | This file — all five gates, both open §3b decisions, and every honest caveat found along the way. |
| `demo_output_3_races.txt` | 3 real races (2026-06-05), fully rendered score + sub-scores + story per horse, ready to paste into an email. |

Output format is CSV/.py/.json/.md/.txt only, no `.pkl`, per the standing
process rule.

---

## 9. Explicitly out of scope (unchanged from plan section 10)

ROI/betting-strategy/edge analysis, Stage-2 odds blending, sectional-speed
variables (v2 upgrade path pending DB confirmation), tree models/GBM/
clustering, and any change to the 10-variable model spec. None of this run's
findings — including the Gate D market correlation — should be read as an
edge signal. It's a sanity check that passed.
