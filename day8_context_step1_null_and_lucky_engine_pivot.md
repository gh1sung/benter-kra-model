# Day 8 Context — Step 1 result, archetype grid, and the pivot to the Lucky engine

> Handoff doc. Written to be self-sufficient: someone reading only this plus
> `Lucky_Engine_Execution_Plan.md` should be able to pick the conversation up
> mid-stride without re-deriving anything.

---

## 0. Who this is and what the project is

Jihwan (성지환), intern at [data partner] (Korean horse racing analytics).
Project 2 = **배당 패턴 분석** — compare 전문가 종합 인기도 (사전인기, expert
consensus published ~3 days pre-race) against market odds and actual
results, looking for divergences that can become customer-facing content
tags.

Project 1 (Benter/Bolton & Chapman replication + public-opinion correction)
produced a family of nulls — Stage 2, Piece B, Q1 — plus one real-but-tiny
result (Q2 overshoot, ~8% edge vs 20% takeout). Project 2 inherits that
context and, so far, that pattern.

**Critical framing established this session:** the north star is **the
product**, not the research question. Jihwan stated this directly and it
was a correction of Claude's drift. Claude had been optimizing for "find an
effect that survives testing"; Jihwan is optimizing for "ship something
[data partner] can sell." The statistical work is instrumental. This should
govern how results are framed going forward — a finding that is
statistically clean but unsellable is a partial failure, and a finding that
is sellable but statistically shaky must be flagged as such rather than
quietly shipped.

**Communication preference, stated explicitly:** plain language, minimal
jargon, explain terms briefly when used. Jihwan is a DS student actively
learning. He specifically asked Claude to *keep challenging rigor* while
*dropping the expert register*. Those are not in tension — do both.

---

## 1. What happened this session, in order

### 1.1 Step 0 review (inherited, not run this session)
Two prior reports were reviewed:

- `Step0_Report.md` — expert-dismissed horses (`is_unranked=1`, n=2,407)
  place at **0.489×** what their own final odds imply, CI [0.376, 0.602],
  robust to odds level, field size, region. Dismissal carries real negative
  information beyond the price.
- `Step0_SURGE_Report.md` — the actual SURGE test (`is_unranked=1 AND
  rank_25<=5`) came back **0 placed / 43**, vs ~3 implied. Underpowered
  (<150 floor) and wrong-signed. Mechanism finding: SURGE horses were short
  at 25분전 (mean 13.6) but drifted OUT to mean 78.2 by post — the
  definition captured *early popularity the smart money abandoned*, not
  insider accumulation.

Jihwan's own read, which was correct and sharper than the report's framing:
the interesting thing isn't the 0.49, it's whether Luckys *exist* and which
horses beat their own price.

### 1.2 Ratio table (run this session, later SUPERSEDED)
Claude ran an odds-band × expert-tercile ratio table on `rows.pkl`, showing
apparent monotone lift with expert score (up to ratio 1.146, CIs excluding
1.0), replicating on a 2021-24/2025-26 time split (1.053 → 1.055).

**This was later shown to be mostly an artifact.** See 1.4.

### 1.3 Step 1 — plan pivot and a real bug
**Original Step 1** was the `unranked × surge` conditional logit. Not
executable: n=43 can't carry a logit. Step 1 was repointed to test whether
`expert_score` adds signal beyond final odds — same slot in the ladder,
different feature.

**Bug found:** `fast_nll_grad_ridge` in `fit_engine.py` assumes the
chosen/winning row is physically **first** within each choice-set block.
`explode()` always built data that way; the new win-only join did not.
Symptom: odds-only baseline pseudo-R² came out ~0.0001, which is impossible
(favorites won 36% of races). Fixed by sorting `[race_id, chosen]`
descending before fitting.

**Fix verified robust** (`shuffle_row_order_check.py`): shuffling non-winner
rows within each block changes coefficients by 1e-16; violating winner-first
reproduces the bug exactly (β 1.179 → 0.130). So the dependency is genuinely
"is the chosen row first," not a row-identity artifact. **Any future join
feeding this engine must sort winner-first.**

**Corrected Step 1 result:**
- Win-only (6,268 races): expert_score not significant (z=−0.98), does not
  replicate.
- WIN+2nd+3rd explosion (18,717 choice sets): β=+0.055, z=3.00 in-sample,
  **z=2.33 held out on 2025-26**. Real and replicating.
- **ΔR² = 0.0001** against a 0.157 baseline. A rounding error.

**Verdict:** real, replicates, economically negligible. Fourth entry in the
honest-null family. Not worth a BB지수 weight.

### 1.4 Why the ratio table overstated it
Within the "15–30 odds" band, the high-expert tercile averaged **19.7** odds
vs **23.5** for the low tercile — a real ~16% price gap hiding inside a
supposedly price-controlled bucket. Most of the apparent 10–15% expert
effect was leftover price variation. Same coarse-bucket failure mode as the
earlier price-conditioning simulation (+5.9pp fake lift survived 5 buckets).
**Lesson: bucketed price controls leak. Use the horse's own continuous
implied probability as denominator.**

### 1.5 Archetype grid (the productive turn)
Prompted by Jihwan's 2K-player-archetype analogy: *"Embiid has great middy,
lay, dunk, defense → that makes him a 2-way 3-level scorer. We have the
attributes but don't know how many archetypes there are."*

Key conceptual point established: **you define the axes, the data tells you
which corners pay.** 2K archetypes weren't discovered by an algorithm; a
human decided the axes were scoring/defense/athleticism and named the
corners. Clustering on horse data would rediscover "expensive vs cheap"
(i.e. the odds) and hand back nothing.

Two axes chosen:
- **Market view** — final odds (and/or expert opinion)
- **Fundamental view** — Gate 2's 10-variable model score

**Setup:** fundamental model retrained on 2008–2021 races (247,866 rows,
24,026 races) with **no 1600–2000m restriction** — Jihwan confirmed that
limit was a B&C artifact and wanted maximum data. Trained pseudo-R²=0.1254.
Scored on a disjoint 2022–2026 analysis set (61,446 rows, 6,046 races).
Zero train/test overlap.

**Grid result (ratio = actual place rate ÷ own-final-odds-implied):**

| Expert view | Fundamental view | n | ratio | sig |
|---|---|---|---|---|
| experts like | stats say worse | 15,222 | **0.950** | YES |
| experts like | stats neutral | 11,731 | 1.014 | no |
| experts like | stats say better | 3,983 | **1.059** | YES |
| lukewarm | stats say worse | 4,721 | **0.905** | YES |
| lukewarm | stats neutral | 8,733 | 1.001 | no |
| lukewarm | stats say better | 15,018 | 1.001 | no |
| nobody picked | stats say worse | 334 | **0.308** | YES |
| nobody picked | stats neutral | 428 | **0.487** | YES |
| nobody picked | stats say better | 1,276 | **0.574** | YES |

**Two product-relevant readings:**
- Row 1 (`experts like × stats worse`, mean odds 5.5, ratio 0.950,
  n=15,222) = a **real, well-powered Unlucky tag** that fires on horses
  customers actually care about.
- Bottom row (`nobody picked × stats better`, ratio 0.574) = the exact
  "hidden gem" profile, and it **underperforms its price badly**. The naive
  Lucky story does not survive as a grouped average.

### 1.6 Real Lucky cases found
Searched for winners that zero experts picked: **16 out of 6,276 races
(0.25%)**. They exist but are rare.

Concrete example surfaced (real, not fabricated):
**2026-07-03, 부산 R6, gate 11** — zero expert picks, 25분전 odds **833.3**
(rank 11 of 11, i.e. dead last in the early market), final odds **80.8**,
**placed**. Money moved in hard between 25분전 and post.

Full candidate list saved to `lucky_candidates_all.csv`.

### 1.7 Jihwan's reframe — this is the key turn of the session
Jihwan pushed back on the averaging approach:

> "I'm not trying to answer a statistical question. I want to tag a horse
> that says 'this horse is showing the same patterns in early betting as
> our previous actual winners.' We're not saying it'll win — 99.9% it
> loses — but there were 10 instances out of the whole bunch. It's the
> customer's decision; we're just the information givers."

Proposed product form: a **confidence tier** (S/A/B/C) reflecting
resemblance to past Luckys, not a win probability.

**Claude's response and the important distinction:**
- A **trained classifier** predicting "will this be a Lucky" is not viable
  on ~16 positives. It would memorize them and emit noise on new horses.
- A **similarity engine** — measure each horse's distance to a reference
  set of known Luckys — *is* viable, because it makes a resemblance claim
  rather than a probability claim.
- Output should read: *"this horse's early-betting pattern is closer to our
  historical Lucky profile than 99.4% of horses"* — true, verifiable, and
  it never implies a hit rate the data can't support.

### 1.8 Cosine similarity — why 최's attempt failed, and how this differs
[program supervisor] previously tried cosine similarity on odds movements; it stalled.
From `project2_plan_context.md`: **"there was no target to optimize
toward."** He got groups out and had no way to say any group mattered —
unsupervised grouping applied to a question that needed an answer key.

Claude's engine differs in **what it points at**, not in the math:

| | 최's version | Lucky engine |
|---|---|---|
| Tool | cosine similarity | can be the same math |
| Question | "what groups exist?" | "how close to known winners?" |
| Answer key | none | the reference set of past Luckys |
| Output | unlabeled clusters | a ranking |

**Correction Claude issued:** earlier in the session Claude said "no
clustering" flatly. That was too broad — it applies to *unsupervised*
clustering as a discovery mechanism. The same distance math against a
labeled reference set is a legitimately different thing. 최's instinct about
the tool wasn't wrong; what was missing was the reference set.

**But cosine specifically is a poor fit here** — it ignores magnitude, so a
horse going 100→50 and one going 4→2 look identical. For this product those
are opposite stories (longshot getting noticed vs favorite getting
hammered). Magnitude *is* the signal.

### 1.9 Reference set counts — the break-even
The 16-Lucky problem was an artifact of an impossibly narrow definition.
Loosening changes everything:

**Early-odds scope (1,894 races — the only scope where a 25분전 pattern can
exist):**

| Definition | Refs | Pool | Base rate |
|---|---|---|---|
| nobody picked & placed | 18 | 770 | 2.34% |
| bottom 20% expert & placed | **206** | 3,404 | 6.05% |
| bottom 33% expert & placed | **426** | 5,470 | 7.79% |
| bottom 33% + odds≥20 & placed | **370** | 5,222 | 7.09% |
| bottom 50% + odds≥15 & placed | 891 | 8,677 | 10.27% |

**Full final-odds scope (6,046 races), for reference:** nobody-picked &
placed = 68; bottom-33% & placed = 1,423.

**Break-even ≈ 206 (the bottom-20% line).** Past the ~150 floor where
Mahalanobis becomes usable and tiers can carry observed rates.

**Recommended primary definition: bottom 33% + odds ≥20 → 370 refs.** The
odds floor guarantees every tagged horse actually pays big if it hits,
which is half the product pitch. Without it you'd tag 6-to-1 horses.

**Important:** the base rate to beat is **7.09%**, not 0.25%. The 0.25% was
the narrow-definition artifact.

---

## 2. Current state of the two tags

| | References | Status |
|---|---|---|
| **Unlucky** (experts like × stats worse) | 15,222 | **Proven.** ratio 0.950, tight CI, well-powered. Ships on existing work. |
| **Lucky** (dismissed × early pattern) | 370 | **Buildable, unproven.** Engine not yet built. |

These are at very different readiness levels. Unlucky may end up carrying
the product while Lucky stays exploratory.

Two tags is the right *product* call even though the grid has 9 cells and 4
are statistically real — only the disagreement corners are sellable. The
"market and stats agree" cells are denominators, not content.

---

## 3. Similarity tool comparison (decided this session)

| Tool | Verdict |
|---|---|
| **Cosine** | ❌ Ignores magnitude; magnitude is the signal here |
| **Euclidean** | ✅ Usable now; needs careful standardization |
| **Mahalanobis** | ✅ Correct tool *if* ≥150 refs; handles feature correlation (e.g. `odds_25` and final odds are highly correlated, Euclidean double-counts that) |
| **kNN** | ✅ No shape assumption; handles multi-flavor Luckys that a centroid would average away |

**Decision:** test Mahalanobis and kNN head-to-head, with a random-shuffle
baseline. Cosine excluded. k fixed by rule (√n), not tuned.

---

## 4. Why no GBM / XGBoost (asked repeatedly, answered definitively)

1. Trees find interactions **among features you give them**. Every main
   effect has been measured and is tiny (expert_score β=0.055, DRIFT
   β=−0.084). Interactions between small effects are typically smaller.
   Trees organize existing signal; they don't create it.
2. The early-odds scope is ~1,894 races. GBMs overfit hard on small data —
   they'd produce impressive in-sample numbers that evaporate on holdout.
3. Low interpretability is the wrong property right now, immediately after
   a bug produced an impossible result.

**Skip entirely, not "later."** Same for unsupervised clustering as a
discovery mechanism (§1.8).

---

## 5. Design traps identified for the Lucky engine test

All of these are baked into the execution plan; repeated here because they
are the reason the plan is shaped the way it is.

1. **Multiple-comparison trap.** 3 definitions × 2 methods × k values means
   the winner is partly the luckiest combination. → Declare the time split
   up front; judge everything on the later window only.
2. **Leakage.** The reference set is defined by an outcome (`placed`).
   Fingerprint features must be knowable at 25분전. Final odds settle near
   post and partly reflect informed money — excluded from the distance
   calculation, used only for eligibility filtering and evaluation. Plan
   §3.5 additionally checks whether `odds_25>=20` should replace
   `odds>=20` as the filter, since the latter is mild look-ahead.
3. **Price confound.** More-similar horses likely have shorter odds, and
   short-odds horses place more anyway. A 1.4× lift could be entirely
   price. → Every tier is measured against its own odds-implied rate, not
   just raw placement. This is the exact trap that made the §1.4 ratio
   table wrong.
4. **Random baseline is mandatory.** If real similarity barely beats
   shuffled scores, the engine sorts nothing.
5. **The fourth-reframe trap.** This is now the *fifth* specification of
   essentially one hypothesis (SURGE rank → expert_score → DRIFT
   interaction → archetype grid → similarity engine). Decision rules were
   written before running specifically so a null doesn't prompt a sixth
   respec. **If the answer is no, it is no.**

---

## 6. Files

### Produced this session
- `step1_expert_score_package.zip` — full Step 1 deliverable:
  - `README_STEP1.md` — plan→pivot→result narrative
  - `project2_plan_context_v2.md` — v1 preserved + v2 addendum
  - `code/` — naive ratio table (superseded), win-only join+fit, depth-3
    join+fit, `fit_engine.py` reference copy
  - `verification/shuffle_row_order_check.py` + output — bug-fix proof
  - `results/` — console outputs for both fits
  - `data/` — three pickles
- `Lucky_Engine_Execution_Plan.md` — the test plan (see it for procedure)
- `day8_context_step1_null_and_lucky_engine_pivot.md` — this file

### Working files in `/home/claude/w/` (regenerable, not in the zip)
- `archetype_base.pkl` — Gate2 features + odds + expert score joined
- `archetype_scored.pkl` — above + `fund_p`, `mkt_p`, `placed`, `won`
- `archetype_final.pkl` — above + `implied_place` (Harville λ=0.8), `edge`
- `lucky_candidates_all.csv` — the 16 zero-expert winners
- `build_archetype.py`, `fit_archetype.py`, `archetype_grid.py`,
  `find_lucky.py`, `lucky_counts.py`

### Inputs relied on
- `/mnt/user-data/uploads/gate2_features_built.csv` — 369,139 rows, 33,110
  races, 2008-01-04 → 2026-07-19, all distances 1000–2300m. **This is the
  no-distance-limit version.** 330,769 rows complete on the 10 model vars.
- `/mnt/user-data/uploads/surge_rows.pkl` — early-odds joined scope, 20,044
  rows, 1,894 races, has `odds_25` and `rank_25`
- `/mnt/project/expert_score_seoul_busan.csv` — 68,932 rows, 6,407 races
- `/mnt/project/win_odds_5yr.csv` — final win odds, 127,202 rows
- `/mnt/project/exotic_outcomes.csv` — results incl. winner/2nd/3rd
- `/mnt/project/fit_engine.py`, `/mnt/project/harville_engine.py`

**Overlap confirmed:** gate2-complete × expert = **6,306 races**;
gate2-complete × expert × early-odds = **1,880 races**. Essentially full
overlap — the earlier worry that the 1600–2000m restriction would shrink
the scope was resolved by using the unrestricted file.

### Missing / not available
- `early_odds_5point.csv` (raw 25/15/10/6/2분 snapshots) is **not present**
  in this environment. Only the pre-joined `surge_rows.pkl` is, which has
  25분전 values (`odds_25`, `rank_25`) but **not** 15/10/6/2분. So DRIFT
  (25분→2분) **cannot currently be computed** — it needs the raw file
  reattached. Any DRIFT work is blocked on that.

---

## 7. Where things stand / immediate next action

Execution plan is written and approved in shape; **not yet run.** Jihwan
asked for the plan and this context file first.

Next action is to execute `Lucky_Engine_Execution_Plan.md` §3, starting
with Step 3.1 (join + join-rate verification). The first real gate is
whether the joined early-odds × Gate2 scope holds up — if it drops below
~1,200 races, every downstream n shrinks and the plan needs adjusting
before the methods are compared.

Decision rules are in plan §4 and were written before any results were
seen. Honor them.

---

## 8. Standing lessons carried forward

- **Verify schema/assumptions before trusting them.** Two confirmed errors
  in [data team lead]'s mapping doc; the `fast_nll_grad_ridge` row-order assumption
  was undocumented and silently wrong-in-use.
- **An impossible-looking baseline is a bug, not a finding.** pseudo-R²
  ≈ 0 for an odds-only model should have been caught instantly.
- **Bucketed controls leak.** Use continuous per-horse denominators.
- **Prefer full-sample interaction terms over carved-out subgroups.** Q2
  went 363 → 1,481 by doing this; SURGE died at n=43 by not doing it.
- **Loose definitions first, tighten only if something shows.** The
  16-Lucky problem was definitional, not real.
- **Bootstrapping quantifies uncertainty; it does not create power.**
- **Product first.** A clean null is a legitimate deliverable, but it is
  not a product. Say which one you have.
