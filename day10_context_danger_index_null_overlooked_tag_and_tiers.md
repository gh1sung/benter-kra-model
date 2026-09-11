# Day 10 Context — Danger-index test (null), Overlooked tag built, confidence tiers, manual threshold control

> Handoff doc. Written to be self-sufficient: someone reading only this plus
> `market_tags.py` should be able to pick the conversation up mid-stride
> without re-deriving anything.

---

## 0. Who this is and what the project is

Jihwan (성지환), intern at [data partner] (Korean horse racing analytics).
Project 2 = **배당 패턴 분석** — expert consensus (사전인기) vs. market odds
vs. fundamental model vs. actual results, looking for divergences that
become customer-facing content tags.

Inherited from Day 8: **Unlucky** tag proven (`experts like × stats say
worse`, n=15,222 in the original archetype grid, ratio 0.950, CI excludes
1). **Lucky** tag reframed away from a group-average claim into a
similarity/resemblance claim, execution plan written but not run this
session — no Lucky-engine work happened Day 10; this session focused
entirely on Unlucky's product shape and expert-vs-stats archetypes.

---

## 1. What happened this session, in order

### 1.1 Danger-index test — can Unlucky be graded instead of binary?

Jihwan's question: since Unlucky is proven, can it carry a **danger 지수**
(0-100 score) instead of a flat tag? Decision criterion agreed up front:
if placement ratio degrades **monotonically** as the expert-vs-stats gap
widens, a graded score is honest; if flat, ship binary only.

**Rebuild required** because the original archetype grid's scored file
(`archetype_scored.pkl`) wasn't available in this environment (pkl,
couldn't be uploaded to project knowledge -- see Section 5 for the
resulting process change). Rebuilt from scratch:

- Refit the **corrected 10-variable** fundamental model (baseline-9 +
  CAREER_STARTS, per the audit -- `DIST_RESIDUAL` excluded, it was the
  bug artifact). Unrestricted file (no 1600-2000m cap), train <=2021
  (23,436 races, 231,501 rows), score all years.
  - Train pseudo-R^2 = **0.1756**, `converged=False` from BFGS but
    confirmed harmless: betas identical to 4 decimals under 10x more
    iterations -- precision-loss flag, not a real non-convergence.
  - **Do not confuse this 0.1756 with the Gate2_Report 0.1424** -- the
    archetype grid's original 0.1254 used 11 vars including the
    since-dropped `DIST_RESIDUAL`, so this is not the same fit reproduced
    wrong, it's a different, more-correct model with a legitimately
    different R^2.
- Built win odds keyed to `race_id`+`horse_num` from `win_odds_5yr.csv` by
  reconstructing `race_id` = date(8) + track_code(2) + race_no(2).
  Track code confirmed via `drift_table.csv` crosswalk: `01`=서울,
  `03`=부산 (제주 excluded throughout, per standing rule).
- Harville lambda=0.8 place probabilities computed from market-implied win
  prob (not fund_p) -- this is the market's view of place risk, the
  denominator every ratio is measured against.
- Full join: **57,753 rows, 5,878 races** (`unified_dataset.csv`). Narrower
  than the original grid's ~30K-row scope because `win_odds_5yr.csv` only
  covers 8,660 of the ~33K total races -- **this is a real scope
  limitation, flagged to Jihwan, worth asking [data team lead] for fuller odds
  coverage.**

**The test:** inside "experts like it" (top expert-score tercile,
dataset-wide), sliced by fund_p's field-relative rank (computed against
the **full race field**, not the experts-like subset -- first attempt at
this made that mistake and it inverted the apparent direction; caught and
documented as a bug before drawing conclusions).

**Result: no dose-response.** Spearman rho(decile, ratio) = **-0.14, p =
0.74**. Worst-fundamentals decile and best-fundamentals decile land at
nearly the same ratio (0.925 vs 0.927). Sanity-check reconstruction of the
original Unlucky cell in this narrower join: n=478, ratio=**0.913** -- same
direction and neighborhood as the original 0.950, just a smaller n from
the odds-coverage gap, not a contradiction.

**Verdict: binary tag confirmed as the ceiling for Unlucky as a single
signal.** A 0-100 danger score would be fake precision -- no gradient
exists to hang it on. Also found structurally: the "experts-like" slice
rarely contains truly bad fundamentals (`mean_fund_p_rank` stays mostly in
the top half even within this group) -- there just isn't a wide range of
disagreement severity to grade in the first place.

### 1.2 Historical-comps frame -- "X because Y similar horses did Z"

Jihwan's next ask: even if binary, can Unlucky show **reasoning** -- "this
horse is Unlucky because N similar past horses in this situation did NOT
place"? Built and shipped as `unlucky_tag.py` (later folded into
`market_tags.py`, see 1.4):

- Reference pool = the 478 real historical Unlucky cases from 1.1's join
  (`unlucky_reference_pool.csv`).
- Matching: 2 features only (log-odds, field-relative fund_p rank),
  standardized, Euclidean distance -- kept deliberately simple/explainable
  rather than a high-dimensional similarity score.
- `MIN_COMPS = 5` floor: suppresses the comps box entirely if too few
  matches exist, so nothing gets shown as evidence when it isn't.
- Smoke-tested end to end on a real race: correctly tagged, pulled 10
  comps, produced a customer-facing sentence.

**Explicit framing carried forward:** the comps box is a communication
device for the already-proven 0.950/0.913 population ratio, not a new
independent statistical claim. Important not to let anyone (internally or
externally) treat "10 comps, 20% placed" as its own powered result.

### 1.3 Scoped four possible product extensions

Jihwan asked whether binary+comps was really the ceiling, or if there was
more real ground to cover without going to ML/black-box territory. Four
ideas scoped:

1. **Second binary tag -- Overlooked** (`nobody picked x stats say
   better`). Ready -- real cell in the original archetype grid (ratio
   0.574), re-confirmed in this join.
2. **Compound tag (Unlucky + is_unranked).** Doesn't work as stated --
   `is_unranked` (zero expert picks) and "experts like it" (top tercile)
   are mutually exclusive by construction. General idea of stacking a
   second variable isn't dead, just needs a different, non-excluded
   variable (field size, region, days-since-last-race -- none tested
   yet).
3. **Confidence tiers by comp density** (not by outcome/effect size).
   Ready -- checked and confirmed comp density genuinely varies a lot by
   odds level (10 vs 231 comps at different points), so tiering is
   meaningful, not decorative.
4. **Time-decay** (does the signal strengthen closer to race day). Real
   question, data-constrained -- only 2 odds snapshots available
   (`drift_table.csv`, 25분전 + final), and that file's race coverage
   (1,892 races) only overlaps 1,775 of the Unlucky-relevant races, which
   would shrink an already-thin n=478 pool further. Not run this session.

Decision: build #1 and #3 (the two ready ones) this session. #2 needs a
variable pick before it's worth testing. #4 deprioritized on data grounds.

### 1.4 Built Overlooked tag + confirmed it's weaker than Unlucky over time

Same rigor/pipeline as Unlucky:

- Definition: `expert_tercile == "low"` (expert_score <= 23) AND
  `fund_p_race_rank >= 0.667` (top third of fundamentals within race).
- Full sample: **n=1,033, races=955, ratio=0.779, CI=[0.659, 0.900]**
  (excludes 1 -- looks proven at first glance).
- **Year-split check revealed a replication problem:** <=2023 ratio=0.587
  (strong), >=2024 ratio=0.867 with **CI=[0.715, 1.019]** -- crosses 1.0,
  not statistically distinguishable from no-effect in the recent window.
  Confirmed this isn't a sample-composition artifact (odds means stable
  2022-2026, n=729 in the >=2024 split isn't tiny).
- Saved to `overlooked_reference_pool.csv` with the same log_odds +
  fund_p_race_rank standardized features as the Unlucky pool.

**Shipped with a caveat, not with Unlucky's confidence.** This distinction
is baked directly into `market_tags.py` -- every Overlooked explanation
string auto-appends the caveat, so it can't accidentally get presented
without context downstream.

### 1.5 Built confidence tiers (density-based) for both tags

Density check confirmed the concern was real:

| | Unlucky | Overlooked |
|---|---|---|
| Tier spread | mostly S/A across the odds range; thin only at the very-short-odds tail | rockier -- dense mid/long-odds, sparse at both very-short and very-long (>190) odds |

Tier = how many pool horses sit within a "tight" log-odds window of the
query horse's odds level. **This is explicitly NOT a danger grade** -- it
says how much evidence backs a specific tag instance, not how dangerous
the horse is. Kept deliberately separate from 1.1's ruled-out graded
index; conflating the two would smuggle back the thing already tested and
rejected.

Default cutpoints: S>=100, A>=30, B>=10 tight comps (window = 0.3
log-odds, roughly +/-35% relative odds), C below that.

### 1.6 Built `market_tags.py` -- the unified deliverable

Replaced the standalone `unlucky_tag.py` with a generalized module
supporting both tags in one call:

```python
from market_tags import tag_race
results = tag_race(horses, fund_p)   # horses: list of {horse_num, odds_final, expert_score}
for r in results:
    if r.tag:
        print(r.explain())
```

Each `TagResult` carries: tag name (or None + reason), tier, comp count,
comps-placed-rate vs pool-average, and an auto-generated explanation
string with the Overlooked caveat baked in when relevant.

### 1.7 [program supervisor]'s feedback (received between sessions) -- two action items

**(a) COVID-recovery hypothesis for Overlooked's weakening.** 최 suggested
2022-23's strong Overlooked effect might be a COVID-restart artifact
(racing resuming/normalizing), and 2024+ weakening reflects the market
returning to normal. Jihwan's own read: correlational, not obviously
causal, and flagged as a real problem if 2024+ (the better, more current
data) shows a weaker effect.

**Checked this directly, year by year (not just the 2-bucket split):**

| year | n | ratio | CI |
|---|---|---|---|
| 2023 | 293 | 0.586 | [0.391, 0.781] |
| 2024 | 269 | 0.880 | [0.636, 1.125] |
| 2025 | 302 | 0.750 | [0.534, 0.967] |
| 2026 | 158 | 1.116 | [0.715, 1.518] |

**Conclusion communicated to Jihwan:** if COVID-normalization were the
mechanism, expect a smooth fade toward 1.0. Instead it bounces (dips,
rises, dips, rises) -- more consistent with ordinary year-to-year noise on
a modest effect at n≈270-300/year than with a clean recovery curve. Real
correlation with the timing; the shape doesn't confirm the causal story.
Recommended stance for the reply to 최: acknowledge the hypothesis as
plausible-but-unconfirmed, note the bouncing pattern as evidence against a
clean version of it, keep the caveat on Overlooked either way.

**(b) Manual threshold control for confidence tiers.** 최 explicitly
requested being able to type in the comp-count cutpoints and matching
window directly, since he's found himself needing to hand-adjust numbers
per-dataset while testing (수동으로 수치를 조정). Implemented:

- `tag_race(..., tight_window=0.5, tier_cutpoints={"S": 20, "A": 8, "B": 3})`
  -- both now optional keyword overrides, default to the Day-10 baseline
  (window=0.3, S/A/B=100/30/10) if omitted.
- New `tier_distribution_preview(tag_name, tight_window=..., tier_cutpoints=...)`
  helper -- sweeps a pool's odds range, prints/returns the resulting tier
  table and overall distribution, so cutpoints can be dialed in by eye
  before committing, without editing code.
- Tested: same query horse moved from tier C -> tier B just by loosening
  cutpoints from default to a custom looser setting. Confirmed wired
  correctly through both the per-call path and the preview utility.

**Not yet decided:** whether the default cutpoints (100/30/10) should
change, or stay as a reasonable starting point since 최 will tune
per-dataset anyway. Left as-is pending his input -- flagged as an open
question, not resolved.

### 1.8 최's shared reference URL (not yet explored)

최 shared a test environment: `http://61.36.136.176:5050/`, containing
previously-built card-style test pages, specifically flagging "실시간
단승식 배당판 분석" and "실시간 복승식 배당판 분석" (real-time win/place
odds-board analysis) as relevant to the current work. **Not opened or
reviewed this session** -- login-gated, external network, out of scope for
this session's tool access. Worth reviewing before Thursday's update if it
informs product UI/framing expectations.

---

## 2. Current state of all tags

| | Definition | n (this join) | ratio | CI excludes 1? | Status |
|---|---|---|---|---|---|
| **Unlucky** | experts-like x stats-worse | 478 (15,222 in original grid) | 0.913 (0.950 original) | yes | **Proven, ships.** No dose-response found -- binary only, confirmed ceiling. |
| **Overlooked** | nobody-picked x stats-better | 1,033 | 0.779 full-sample | yes (full sample); **no in >=2024 split** | **Real but caveated.** Ship with visible lower-confidence note; do not present at Unlucky's confidence level. |
| **Lucky** | dismissed x early-pattern resemblance | 370 (Day 8 figure) | n/a (similarity claim, not ratio) | n/a | Unchanged from Day 8 -- execution plan written, not run this session. |

Confidence tiers (S/A/B/C, density-based) now apply to both Unlucky and
Overlooked, with manually adjustable thresholds.

---

## 3. Process change this session

Jihwan flagged that `.pkl` outputs can't be uploaded to project knowledge
(only files, not the format itself, unclear if there was ever a real
technical reason). Agreed going forward: **default to CSV outputs**, no
more pkl unless there's a specific, stated technical reason (e.g. object
types that don't serialize to CSV) -- checked, and there wasn't one here,
it was leftover habit. All Day 10 outputs are CSV/py, no pkl produced.

---

## 4. Files

### Produced this session
- `01_fit_fund_model.py` -- corrected 10-var fundamental model refit,
  scores `fund_p_scored.csv`
- `02_build_unified.py` -- joins fund_p + expert + odds + outcomes +
  Harville implied_place -> `unified_dataset.csv` (57,753 rows, 5,878
  races)
- `03_dose_response_test.py` -- the danger-index dose-response test ->
  `dose_response_deciles.csv`, `binary_check.csv`. Null result (rho=-0.14,
  p=0.74).
- `04_build_unlucky_comps.py` -- original single-tag comps builder
  (superseded by `market_tags.py`, kept for reference)
- `05_overlooked_tag.py` -- Overlooked tag build + year-split replication
  check -> `overlooked_reference_pool.csv`
- `06_confidence_tiers.py` -- density-by-odds-level check for both pools
  -> `unlucky_density_by_odds.csv`, `overlooked_density_by_odds.csv`
- **`market_tags.py`** -- the actual deliverable. `tag_race()`,
  `TagResult`, `tier_distribution_preview()`. Manual threshold overrides
  added per 최's request (1.7b).
- `unlucky_reference_pool.csv` (478 rows), `overlooked_reference_pool.csv`
  (1,033 rows) -- both with standardized `log_odds`/`fund_p_race_rank`
  features baked in, ready for `market_tags.py` to load directly.

### Inputs relied on
- `/mnt/user-data/uploads/gate2_features_built.csv` -- 369,139 rows,
  33,110 races, unrestricted (re-uploaded this session; prior sessions'
  copy of this wasn't in project knowledge)
- `/mnt/project/expert_score_seoul_busan.csv` -- 68,932 rows, 6,407 races
- `/mnt/project/win_odds_5yr.csv` -- 127,202 rows, 8,660 races after
  Jeju exclusion -- **this is the scope-limiting file**, see 1.1
- `/mnt/project/exotic_outcomes.csv` -- 33,110 races, winner/2nd/3rd
- `/mnt/project/drift_table.csv` -- used only for the track-code<->region
  crosswalk (01=서울, 03=부산) and for scoping the (unrun) time-decay idea
- `/mnt/project/fit_engine.py`, `/mnt/project/harville_engine.py` -- reused
  as-is, no changes

### Known gaps / not available
- `archetype_scored.pkl` from Day 8 -- not present in this environment,
  hence the full rebuild in 1.1. Superseded by CSV-only outputs going
  forward (Section 3).
- `early_odds_5point.csv` (raw 25/15/10/6/2분 snapshots) -- still not
  present (same gap noted Day 8). Blocks idea #4 (time-decay) and any
  DRIFT work.
- Full win-odds coverage -- `win_odds_5yr.csv` only covers 8,660 of ~33,110
  total races, which is why every ratio in this session's rebuild has a
  smaller n than the original archetype grid. Real, not yet resolved. Ask
  [data team lead] for fuller coverage if a wider Unlucky/Overlooked pool is wanted.

---

## 5. Where things stand / immediate next actions

1. **Reply to 최 on the COVID hypothesis** -- use 1.7a's year-by-year
   table and the "bouncing, not fading" read. Don't overclaim either way.
2. **Decide default tier cutpoints** -- currently S/A/B=100/30/10, unclear
   if these should change or just stay as an adjustable starting point.
   Open question for 최 or Jihwan to resolve.
3. **Idea #2 (compound tag)** -- still needs a second variable picked
   (field size / region / days-since-last-race are candidates, none
   tested). Only worth doing if there's product appetite for a third
   signal beyond Unlucky + Overlooked.
4. **최's shared test URL** (`61.36.136.176:5050`) -- not yet reviewed,
   worth checking before Thursday given he specifically flagged two pages
   as relevant to this exact work.
5. **Win-odds coverage gap** -- worth raising with [data team lead]; current
   8,660/33,110 race coverage caps every ratio's n well below what the
   original archetype grid achieved.
6. Thursday: continue + share progress per 최's standing request.

---

## 6. Standing lessons carried forward (Day 10 additions)

- **Field-relative ranks must be computed against the full population
  before subsetting**, not within an already-filtered subgroup -- ranking
  fund_p within the tiny "experts-like" subset (avg ~3.3 horses/race)
  collapsed to 6 coarse values and inverted the apparent dose-response
  direction. Caught before it produced a wrong conclusion, but it's an
  easy trap to fall into again with any similarly-defined subgroup.
- **A flat dose-response is itself a real, reportable finding** -- same
  spirit as Day 8's "null is a legitimate deliverable" lesson, applied to
  a grading question instead of an existence question. Binary-vs-graded is
  now a resolved question, not an open one.
- **Density-based confidence and outcome-based grading are different
  things and must not be conflated.** Tiers say "how much evidence," not
  "how dangerous." Mixing them back together would quietly reintroduce
  the graded index that was explicitly ruled out.
- **A second proven-looking tag still needs a replication check split by
  time**, not just a full-sample CI. Overlooked's full-sample CI excluded
  1 and looked shippable at that resolution alone; splitting by year
  surfaced a real, material weakening that changes how it should be
  presented.
- **File format constraints are worth fixing at the process level once
  identified**, not worked around silently each time. pkl->CSV default
  switch this session is a small thing but removes a recurring friction
  point.
