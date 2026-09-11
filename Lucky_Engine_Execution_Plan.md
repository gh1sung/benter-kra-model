# Lucky Engine — Execution Plan

**Goal:** Determine whether a similarity engine can rank dismissed longshot
horses such that the most-similar ones place more often than their peer
group's base rate. If yes, the Lucky tag is a product. If no, it isn't, and
we ship Unlucky alone.

**This is a test, not a build.** No product code, no tags, no tiers until
the engine is shown to sort. Expected outcome is honestly uncertain — the
project has four prior nulls on adjacent hypotheses.

---

## 0. Non-negotiable design constraints

These exist because specific failure modes have already bitten this project.

### 0.1 Time split, declared before running
- **BUILD window:** earliest available 25분전 race → 2026-02-28
- **TEST window:** 2026-03-01 → 2026-07-19
- Every definition × method combination is judged on the TEST window only.
- Reference fingerprints are computed from BUILD-window Luckys only.
- Rationale: 3 definitions × 2 methods × k choices = enough combinations
  that the winner would otherwise be partly the luckiest draw.

### 0.2 No outcome leakage into the fingerprint
Features used for distance computation must be knowable **25 minutes before
post**. Permitted:
- `expert_score` (published ~3 days pre-race)
- `exp_rank_in_race` (expert percentile within race)
- `odds_25` (25분전 win odds), `ln(odds_25)`
- `rank_25` (popularity rank at 25분전, within recorded set only)
- `n_starters`
- `fund_p` — fundamental model win prob (10-var Gate 2 model, trained on
  2008–2021 races that do not appear in any analysis scope)

**Forbidden inside the distance calculation:** final odds, `implied_place`,
`placed`, `rank`, `won`, any 2분전/6분전 snapshot value.

Final odds may be used ONLY for (a) the `odds >= 20` eligibility filter and
(b) computing the odds-implied benchmark in evaluation. Never as a
fingerprint dimension.

> **Note on the odds>=20 filter:** final odds settle near post, so using
> them for eligibility is mild look-ahead. In production the filter would
> use `odds_25 >= 20` instead. Step 3.5 below checks whether swapping to
> the 25분전 version changes the reference set materially. If it does, the
> 25분전 version wins and the whole test reruns on it.

### 0.3 Feature count held low
Mahalanobis must estimate a covariance matrix. With ~250 BUILD-window
references, keep the fingerprint to **5–6 features max**. Start with:
`ln(odds_25)`, `rank_25`, `exp_rank_in_race`, `fund_p`, `n_starters`.

### 0.4 k fixed by rule, not tuned
kNN `k = round(sqrt(n_references))`, computed per definition. No tuning of
k against the TEST window.

---

## 1. Definitions to test (3)

All within the early-odds scope (1,894 races). `placed` = 연승식 rule
(top-2 if 5–7 starters, top-3 if ≥8).

| ID | Definition | Refs (full scope) |
|---|---|---|
| D1 | bottom 20% expert in race, PLACED | 206 |
| D2 | bottom 33% expert in race, PLACED | 426 |
| D3 | bottom 33% expert in race AND final odds ≥20, PLACED | 370 |

Counts above are full-scope; BUILD-window counts will be lower (~60-70%).
**Gate:** if any definition has <100 BUILD-window references, drop it and
note why — below that, the covariance estimate for Mahalanobis is not
trustworthy.

Each definition also defines its own **eligible pool** (the same filter
without the `placed` requirement) and its own **base rate**:
- D1 pool 3,404 → base 6.05%
- D2 pool 5,470 → base 7.79%
- D3 pool 5,222 → base 7.09%

The base rate is the number to beat. Not the all-horse average.

---

## 2. Methods to test (2 + 1 baseline)

| ID | Method | Assumption |
|---|---|---|
| M1 | Mahalanobis distance to reference centroid | Luckys form one blob |
| M2 | kNN — mean distance to k nearest references | No shape assumption |
| M0 | Random shuffle of scores | Null baseline |

M0 is not optional. It is the sanity floor: if M1/M2 barely beat M0, the
engine sorts nothing and we stop.

### 2.1 Pre-check: one blob or two?
Before trusting M1, run a quick shape check on the BUILD references
(2-component clustering, or just inspect the spread of `ln(odds_25)` and
`rank_25` among references). If the Luckys are visibly bimodal — e.g. a
"quiet early money" group and a "sudden surge" group — Mahalanobis to a
single centroid describes neither, and M2 should be expected to win.
Record the finding either way; it is informative about the mechanism.

---

## 3. Procedure

### Step 3.1 — Build the analysis table
Join, restricted to the 1,894-race early-odds scope:
- `surge_rows.pkl` → `odds_25`, `rank_25`, `expert_score`, `is_unranked`,
  `n_starters`, `placed`, `implied` (odds-implied place prob), `odds`
- `archetype_scored.pkl` → `fund_p` (fundamental model win prob)

Join key: `(race_id, horse_num)` ↔ `(race_id, back_num)`.
**Verify the join rate before proceeding.** Expect meaningful loss —
`archetype_scored` requires complete Gate-2 features. If the joined scope
falls below ~1,200 races, note it prominently; every downstream n shrinks.

Add `exp_rank_in_race` = within-race percentile rank of `expert_score`
(ascending, so low = dismissed).

Add `window` = BUILD or TEST by `race_date`.

### Step 3.2 — Standardize
Compute mean/sd of each fingerprint feature **on the BUILD-window eligible
pool only**. Apply the same transform to TEST. Never re-fit on TEST.

### Step 3.3 — For each definition D1/D2/D3:
1. Extract BUILD-window references (dismissed AND placed).
2. Report `n_refs_build`. If <100, flag and drop.
3. Run the 2.1 shape check.
4. **M1:** compute reference centroid + covariance from BUILD refs. Score
   every TEST-window eligible horse by Mahalanobis distance to centroid.
   Convert to similarity = −distance.
5. **M2:** k = round(sqrt(n_refs_build)). Score every TEST-window eligible
   horse by (negative) mean Euclidean distance to its k nearest BUILD refs.
6. **M0:** shuffle the M1 scores within the TEST window (fixed seed).

### Step 3.4 — Evaluate (this is the actual test)
For each (definition, method), split TEST-window eligible horses into
similarity tiers: **top 10%, top 25%, and the rest**.

Report per tier:
- `n`
- `actual_place_rate`
- `base_rate` (that definition's eligible-pool rate)
- **`lift` = actual_place_rate / base_rate** ← primary metric
- `odds_implied_rate` (mean of `implied`)
- **`ratio` = actual / odds_implied** ← price-controlled check
- bootstrap 95% CI on `ratio` (2,000 reps, same machinery as Step 0)
- `mean_final_odds` (to see whether tiers differ in price)

**Two numbers matter, and they answer different questions:**
- `lift > 1` → the engine sorts *within its peer group*. Enough for a
  content product ("this profile places more than similar horses").
- `ratio > 1` with CI excluding 1.0 → the engine beats the *market price*.
  Much stronger, much less likely, not required for shipping.

If `lift > 1` but `ratio ≈ 1`, that means high-similarity horses are simply
shorter-priced — the market already knows. Say so plainly; do not report
lift alone.

### Step 3.5 — Filter robustness
Rerun D3 with `odds_25 >= 20` instead of `odds >= 20`. Compare reference
counts and top-tier lift. If materially different, the 25분전 version is
the correct production definition and results should be reported on it.

### Step 3.6 — Stability check
Repeat the full evaluation with BUILD/TEST swapped (fit on late window,
test on early). A combination that wins in one direction and loses in the
other is noise, regardless of how good the winning number looks.

---

## 4. Decision rules — write these down before looking

- **PROCEED to product build** if: at least one (definition, method) shows
  top-10% `lift ≥ 1.3` on TEST, holds direction under 3.6, and beats M0
  by a visible margin.
- **PROCEED with weaker claim** if: `lift` between 1.1 and 1.3 and stable.
  Ships as "resembles past cases" with the base rate quoted, no tier-level
  rate claims.
- **STOP the Lucky tag** if: `lift ≤ 1.1`, or M0 performs comparably, or
  results flip under 3.6. Ship Unlucky alone, log Lucky as a fifth honest
  null.

Do not respec the definition after seeing results and rerun. That is the
fourth-reframe trap already flagged in `project2_plan_context_v2.md`. If
the answer is no, it is no.

---

## 5. Deliverables

- `lucky_build.py` — join, feature build, BUILD/TEST split
- `lucky_engine.py` — M0/M1/M2 scoring functions
- `lucky_evaluate.py` — tier tables, lift, price-controlled ratio, CIs
- `Lucky_Engine_Report.md` — results, verdict against §4, and either a
  product spec or a clean null writeup

---

## 6. Explicitly out of scope

- Gradient boosting / XGBoost / any tree model (see context file §"Why no GBM")
- Unsupervised clustering as a discovery mechanism
- Tier naming, content copy, per-race tag caps — product layer, only after
  the engine is shown to sort
- Anything requiring 25분전 data outside the 1,894-race scope
