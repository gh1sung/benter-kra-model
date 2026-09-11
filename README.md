# Benter-style handicapping model — Korean horse racing (KRA)

**A 4-week research internship at Racing Joy, in full.** This README is the whole story, not
just the headline: the original question, six different ways of trying to answer it that
didn't work, the pivot that did, and the two products that came out the other end. It's written
so someone with no prior context can read it top to bottom and understand what happened and why.

---

## TL;DR

The project set out to test whether William Benter's (1994) horse-racing model — a fundamentals
model blended with the crowd's own odds — could find an edge in Korean racing (KRA) that isn't
already priced in. **It couldn't.** Six different market-efficiency tests, across the win pool,
the exotic (quinella) pool, early-vs-late odds, and a longshot-similarity engine, all came back
null or economically worthless. That's not a failure — it's a real, honestly-earned finding: the
Korean market looks efficient. Partway through, the actual goal shifted from "beat the market" to
"explain the market to customers" — which produced two things that did ship: a set of
**descriptive tags** (Unlucky / Overlooked / DRIFT) that flag when the crowd's opinion and the
model's opinion disagree, and a **0-100 horse ability score** (internally "BB지수" / BB Index)
built on the same fundamental model, with a per-horse story broken into five sub-scores.

---

## Timeline at a glance

| When | What happened |
|---|---|
| Day 1 | Scoped the question: can Benter's two-stage model beat KRA's own odds? Gate framework written before any data was touched. |
| Days 3-5 | RDS access secured, full schema mapped, B&C's 9/10-variable spec locked, a data-contamination scare investigated and ruled out. |
| Day 6 (checksum) | Pipeline validated against Bolton & Chapman (1986) - right order of magnitude, right shape, no leak. Green light to add the odds. |
| Day 6 (Stage 2) | Test 1: null. Fundamental model + final odds adds ~0 over the odds alone on the win market. |
| Day 7 | Tests 2-4. Built the Harville engine (Piece A), tested it against the exotic pool (Piece B - null), tested early-vs-final odds (Q1 - null), found a real-but-unprofitable overshoot effect (Q2). |
| Day 8 | Test 5 (expert-consensus signal - real but 0.0001 delta-R-squared, negligible). The pivot: reframed the whole project from "find an edge" to "ship a product." Built the archetype grid and found the Unlucky tag. |
| Days 8-10 | Overlooked tag added (weaker, caveated). Tested a graded 0-100 "danger score" - no dose-response, binary confirmed as the ceiling. Confidence tiers plus historical comps added. |
| Days 10-13 | Test 6: Lucky engine built and killed (fifth null, all three stop-conditions fired). DRIFT tag tested - real signal, but fully priced in; ships descriptive-only. |
| Days 10-13 (parallel track) | The 10-variable model repurposed as a live 0-100 rating engine ("BB지수"). First live run had a serious bug (90% of scores wrong) - caught before shipping, fixed. Then a second, separate blocker: RDS itself was missing 35% of this week's entries - caught, escalated, held back. |
| Day 13 | Found and fixed a real production bug in the tag logic (debut horses were quietly distorting rankings). Final reframe: tags are explicitly redefined as descriptive, not predictive - this is what actually resolves the project. |

---

## Part 1 - The original question

The starting point was William Benter's 1994 paper, "Computer Based Horse Race Handicapping and
Wagering Systems" - a real, profitable computerized betting operation run in Hong Kong for five
years. Its method, adapted here for Korea:

**Stage 1 - a fundamental model.** Score every horse on a handful of factors (recent speed, win
rate, jockey stats, weight, distance fit, etc.), then turn scores into win probabilities with a
softmax:

```
f_i = exp(score_i) / sum_j exp(score_j)
```

This is a multinomial logit (borrowed from Bolton & Chapman, 1986, not invented by Benter),
fit by maximum likelihood on historical races and validated out-of-sample.

**The catch:** on their own, these probabilities are systematically overconfident - when the
model disagrees with the crowd, the crowd tends to be right. So the raw model can't be bet
directly.

**Stage 2 - blend model and crowd.** A second, simpler model combines the two opinions in
log-odds space:

```
c_i = exp(a*log(f_i) + b*log(pi_i)) / sum_j exp(a*log(f_j) + b*log(pi_j))
```

where `f_i` is the fundamental model's probability, `pi_i` is the crowd's implied probability
(recovered from the odds: `pi_i = (1 - takeout) / odds_i`), and `a`/`b` (also fit by MLE) say how
much to trust each opinion. `a` must be fit out-of-sample - feeding in a model's own
training-set predictions inflates `a` and lies about how good the model is.

**The metric that actually matters - delta R-squared.** Pseudo-R2 is `1 - L(model)/L(random)`,
where `L` is the likelihood the model assigned to the actual winners. What matters isn't a
model's own R2 - it's whether adding it to the crowd improves on the crowd alone:

```
delta_R2 = R2(combined) - R2(crowd alone)
```

Benter's own paper makes the point with a "tipster" comparison: a newspaper-tipster consensus
model looked just as accurate standalone as his real model (R2 0.1014 vs 0.1016) - but added
almost nothing once combined with the crowd (delta R2 0.0002 vs Benter's 0.0090 for a simplified
9-variable version, 0.0178 for his full 5-man-year model). Standalone accuracy is close to
meaningless; only delta R2 tells you if a model knows something the crowd doesn't. That 0.0178 is
what turned into 40x wealth growth over 5 years - the bar being chased here is a small number
that compounds, not a big flashy one.

Betting itself uses the Kelly criterion (`K = advantage / (odds - 1)`, usually run at 1/2-1/3
scale) and, for combination bets, the Harville formula to turn win probabilities into
"horses A and B finish 1-2" probabilities.

**Why Korea might be different from Hong Kong, going in:** KRA has smaller pools, higher takeout
(20-26% vs Benter-era HK's ~19%), and hard per-ticket betting caps (100,000 KRW offline,
50,000/day online) that discourage professional/sharp money. That could mean either a weaker,
more exploitable public, or a harder benchmark to beat if what's left is genuinely well-priced
retail money - an empirical question, not something to guess at. It's also a real structural
constraint on how much money any edge could ever be worth, independent of whether one exists (see
`day1_context_benter_korea_project.md` for the full pool-size/cap arithmetic).

---

## Part 2 - Validating the pipeline before trusting anything

Before testing anything new, the pipeline had to prove it could reproduce a known published
result: Bolton & Chapman's (1986) original 9-variable model. This is the "checksum" - its job is
to catch a broken pipeline (a leak, a wiring bug, a sign flip), not to hit a number to the third
decimal.

Built on 6,000 Korean races (1600-2000m, dry/good track - 12x B&C's own minimum sample), the
checksum came back at 0.115-0.155 pseudo-R2 across explosion depths, vs B&C's published
0.055-0.091. Higher than B&C, but for good reasons, confirmed four ways: the decline pattern
across explosion depths matched B&C's shape exactly; every coefficient sign made racing sense,
with the same variable (AVESPRAT, speed rating) dominant in both; holdout R2 was also elevated
(ruling out a look-ahead leak, which would show up in-sample only); and switching to B&C's
literal speed-figure formula only shaved ~10% off, meaning the gap is a real market/era/
sample-size difference, not an artifact of the modeling choice. Verdict: GO - pipeline
validated, clear to add the public's odds.

One real bug was caught here, by an external audit partway through: the original code dropped
individual horse-rows missing a feature rather than the whole race, which silently deleted actual
winners from ~18% of test-period races (`Gate2_Report.md`). Fixed with `race_safe=True` - a whole
race is now dropped if any horse in it is missing a required feature, never just that horse.
This one fix is why `fit_engine.py` checks for `race_safe=True` everywhere downstream, and it's
referenced as a standing rule in nearly every later day-log.

**Final locked model: 10 variables** - the original 9 (AVESPRAT, LSPEDRAT, LIFE_PCT_WIN,
W_PER_RACE, JOCK_PCT_WIN, JOCK_NUM_WIN, WEIGHT, POSTPOS, NEWDIST) plus `CAREER_STARTS`, which
turned out to be the single strongest predictor in the whole candidate pool (a `ROUTE_RESIDUAL`
variable that looked even stronger before the audit fix turned out to be an artifact of the same
bug, and was dropped).

---

## Part 3 - The hunt for an edge: six tests, six non-starters

With the pipeline trusted, this is the actual research phase: repeatedly asking "does anything
here beat the crowd's own price," across every angle that seemed promising. Every one of these
was a real, pre-registered test with a decision rule written before running it - not a search
that kept going until something looked good.

### Test 1 - Stage 2: fundamental model + final odds, win market

**Result: null.** Delta R2 was about +0.00003 (statistically zero, likelihood-ratio p=0.62).
Bucketing by how much the model disagreed with the crowd, actual outcomes tracked the crowd's
number in every bucket - the fundamental model (speed, form, jockey stats, weight, gate) carries
essentially zero information the odds don't already have.

### Test 2 - Piece A + Piece B: the exotic (quinella) pool

Piece A built and validated a Harville engine (converts win probabilities into "these two
horses finish top-2" probabilities) - needed a correction factor (lambda = 0.8) after finding
favorites place top-2 less often than plain Harville assumes. Piece B then asked: does the
win-pool's own pricing, run through Harville, beat the quinella pool's own price? Null - the
quinella market's own price was, if anything, slightly sharper. Betting the "edge" anyway: -28.6%
ROI, worse every single year 2021-2026, worse still after tuning on early years and testing on
later ones (the standard overfitting check).

### Test 3 - Early odds vs. final odds

Does the market get more efficient closer to post time, meaning the early number plus the
fundamental model can beat the final number? Null. The fundamental model's coefficient sat
near zero (~0.12) every time it was tested; the market is more accurate as it approaches race
time, not less.

### Test 4 - Q2: the overshoot correction (the interesting near-miss)

While testing #3, a side-signal turned up: odds drift between the early and final snapshot
predicts winning on its own (+0.63 coefficient), even before looking at the final price. The
follow-up question - does the remaining drift signal, after the final price already reflects
most of it, mean the final price overshoots? Yes, genuinely - after expanding the sample 4x
(363 to 1,481 races) the effect held up (coefficient -0.084, z = -2.20, CI excludes zero).
But it failed the money test: the edge is ~8% in odds terms, against a 20% (win pool) to
26.7% (quinella pool) takeout. An edge less than half the size of the house's cut can't turn a
profit no matter how it's sized. Win-pool betting simulation: -100% ROI on the 14 bets it
generated. Real finding, not a sellable product.

### Test 5 - Does published expert consensus add anything beyond the odds?

Real, but negligible. Once the estimation window included 2nd/3rd-place finishers (not just
winners), expert consensus was statistically significant (z=2.33 on held-out data) - but
delta R2 = 0.0001, a rounding error. Fourth null in the family.

### Test 6 - The Lucky engine (similarity-based longshot detection)

The most elaborate attempt: build a set of ~16 historical "Lucky" horses (zero expert picks who
won anyway), then use a similarity engine (Mahalanobis / kNN on 5 pre-race features) to flag
horses that resemble them. Killed, decisively - every one of three independent pre-registered
stop-conditions fired: the most-similar horses placed less often than their peer average (lift
below 1.0 for every method and definition); a random shuffle of the same scores did as well or
better; and flipping the train/test time split reversed the result entirely (0.74 one direction,
1.48 the other) - the signature of noise, not signal. Mechanistically, the engine was just
finding the longest-priced horses in the pool (mean odds ~54:1), which place less often, not
more. Fifth honest null. This hypothesis had now been re-specified five different ways
(SURGE rank, expert-score interaction, DRIFT interaction, archetype grid, similarity engine)
and come back null every time - the decision rule written in advance was explicit that a sixth
re-specification was not on the table.

### A side investigation: does data quality on weaker horses matter?

A senior raised a concern that "low-quality" horses might have unreliable data and be dragging
down the model. The audit (`audit.md`, `results.md`, `class_mapping.md`) found the concern was
real but small: low-data horses' win-record signal is genuinely less reliable (a real,
significant, out-of-sample effect - but only ~0.3% of log-loss), and their raw speed figures
stay just as informative. The fix is a soft re-weighting, not deleting ~63% of races as a blunt
exclusion would require - and even the re-weighted model still gets crushed by the market alone
(log loss 1.85 vs ~2.05), so it changes nothing about the bottom line. Kept the baseline model.

**Six tests (plus one side audit), six non-starters as trading strategies.** Every one of them
was a legitimate, rigorously-tested negative result - the honest conclusion is that Korean KRA
odds are close to informationally efficient, at least along every axis tested here.

---

## Part 4 - The pivot: from predicting winners to explaining disagreement

Day 8 is the hinge of the whole project. After the fourth null in a row, there was an explicit,
self-corrected reframe:

> "The north star is the product, not the research question."

Up to that point, the work had been optimizing for "find an effect that survives testing." That's
necessary but not sufficient - a statistically clean null is a legitimate research finding, but
it isn't something Racing Joy can put in front of a customer. So the question changed from "can
we beat the market" to "can we tell customers something true and interesting about a horse,
even if it's not an edge."

**The archetype grid.** Inspired by a 2K-basketball-archetype analogy (a player isn't just "good
or bad," they're a type, defined by which attribute-axes they're strong or weak on), the model
crossed two independent views of each horse - what the experts think (published consensus)
and what the fundamentals say (the 10-variable model) - into a 3x3 grid, and checked which
cells' actual outcomes deviated from what their odds implied.

Two cells stood out:

- **Unlucky** - experts like it, fundamentals say worse (n=15,222 in the original grid): these
  horses placed at 0.950x their own odds-implied rate, a tight, statistically real gap.
  This became the flagship tag.
- **Overlooked** - nobody picked it, fundamentals say better (the "hidden gem" cell): ratio
  0.574 in the original grid - real, but split by year revealed it weakens materially in
  2024+ data (CI crosses 1.0), so it ships with an explicit lower-confidence caveat, never at
  Unlucky's level of confidence.

A graded 0-100 "danger score" version of Unlucky was tested and explicitly rejected - no
dose-response existed to hang a gradient on (Spearman rho = -0.14, p=0.74), so a binary tag is
the honest ceiling, not a limitation of the analysis. Confidence tiers (S/A/B/C, based on how
many similar historical horses exist to compare against - density, not outcome) and a
"historical comps" explanation ("N similar horses like this one did X") were layered on top,
implemented in `market_tags.py`.

**DRIFT (late odds movement)** was tested next as a third candidate signal - does money moving in
late (25 min to 2 min before post) predict placing? The raw signal is real and stable (33.5% vs
20.5% place rate, top vs bottom decile of late money) and survives cross-validation checks that
killed the Lucky engine - but once compared to each horse's own final-odds-implied rate, the
ratio flattens to ~1.0 almost everywhere. The market has already priced the drift by the time
it settles. One narrow, real exception survived: heavily-backed favorites that draw even more
late money underperform their already-short price (ratio 0.94 to 0.85, monotone) - a place-pool
echo of the Q2 overshoot finding. DRIFT ships as a descriptive tag in both directions, with an
explicit "already priced in" disclaimer, plus a narrower "overshoot caution" note for that one
favorite-band finding.

**The final resolving move (Day 13):** partway through fixing a real bug in the tag logic (below),
the tags were explicitly and permanently redefined:

> "None of these are predictive, just descriptive content tags... a simple 'caution alert'...
> nothing predictive."

This one sentence is what actually settles the project's central tension. It means the earlier,
harder question ("does this tag beat the market") is no longer the bar the tags need to clear -
the bar becomes "is the disagreement we're describing real and correctly labeled," which is a
much more honest, and much more clearable, standard for a customer-facing "here's an interesting
pattern" feature.

---

## Part 5 - The rating engine (BB지수 / BB Index)

In parallel with the tag work, the same validated 10-variable fundamental model was repurposed
into a standalone product: a 0-100 horse ability score, decomposed into five interpretable
sub-scores (speed, record, jockey, race conditions, experience), each contributing exactly to
the total (`horse_rating.py`, verified to floating-point precision - the five blocks always sum
to the total score, so the customer-facing story text can never contradict the number).

**Validation gates**, all run before trusting the score in production:
- Calibration - win rate rises strictly monotonically across all 10 score bands (1.7% at
  score 1-10, up to 26.1% at 91-100). Pass.
- Temporal stability - year-over-year means stay flat (48.2/47.6/47.8 across the 2024-2026
  holdout). Pass.
- Field-size independence - technically non-zero (p<0.0001 with 45,000+ rows) but tiny in
  practice (~1 rating point per extra starter, r=0.04). Reported honestly as "pass in practical
  terms, fail in strict literal terms" rather than rounded to a clean PASS.
- Market sanity check - correlates -0.54 with final odds (better horses, shorter odds), as
  expected. This is a sanity check, explicitly not an edge claim.

**A real, honest limitation, not swept under the rug:** debut horses (zero prior races) have no
inputs for a model built entirely on race history - not "hard to estimate," but literally no
data to estimate from. The team's standing rule: never fill this with a zero or an average
(that would misrepresent a real horse as having a 0% or "average" chance); instead the horse is
explicitly flagged as insufficient information, and any race containing one gets an automatic
warning that its other horses' scores may be inflated (since probabilities in that race were
normalized only across the horses that could be scored).

**Two real production incidents, caught before anything wrong shipped:**

1. **The entry-row bug (v1).** The first live run (scoring this week's actual race card) copied
   each horse's most recent already-computed feature values forward - which accidentally
   skipped that horse's most recent actual race entirely, since those features are built with a
   1-race lag. Measured damage: 90% of scored horses' ratings changed once fixed, and the
   model's top pick flipped in 12 of 31 races (39%). Caught because the person running it
   asked why so many horses were being dropped rather than accepting the output - the fix
   (`entry_features_fix.py`) re-runs the actual feature-computation sequence including the
   upcoming race, rather than copying a stale value forward, and was verified to change zero
   already-settled historical rows.
2. **The RDS data gap.** Right after fixing #1, a screenshot of the real KRA race-card PDF
   revealed the pipeline was missing horses that should have been there. Investigation found the
   database itself was ~35% incomplete for that week's entries (confirmed unchanged across two
   pulls two hours apart) - a pure data-availability problem, not a code bug. The output was
   held back and not sent to the supervisor until the gap was resolved at the source.

Both incidents follow the same underlying discipline that shows up everywhere in this project:
an output that runs without an error is not the same as an output that's correct, and every
questionable result gets checked against source data before it's trusted or shipped.

---

## Part 6 - A real production bug in the tag logic itself

Separately from the rating engine's bugs, `market_tags.py` had its own bug, found on Day 13: the
percentile rank used to decide whether a horse counted as "stats say better/worse" was computed
using only the horses the model could actually score as the denominator, not the true field
size. Since debut horses (not randomly missing - the audit showed missing horses actually
skewed toward the stronger end of the field) were disproportionately dropped from that
denominator, the remaining horses' percentiles were quietly pushed toward the extremes.

Two attempted fixes were tried and rejected by their own author before the real one:
rescaling probabilities uniformly doesn't change rank order (mathematically guaranteed - caught
immediately once tested against a "nothing should change when nothing is missing" no-op check);
changing the ranking denominator formula fixed the missing-horse case but broke calibration on
every other race, including ones with no missing horses at all. The actual fix uses partial
identification bounds - computing both a best-case and worst-case percentile for each horse
(assuming missing horses are either all better or all worse), and only firing a tag when it holds
under the unfavorable bound. This is conservative by construction, verified mathematically to
reduce to the exact old behavior when nothing is missing (checked to within 1e-12), and enforced
with an assertion in the code rather than left as a comment.

The conservative fix cost coverage (tag rate fell from ~22-24% to 16.3%), so a second,
lower-confidence tier was added: a tag still fires (flagged as lower-confidence) if only the
point-estimate - not the strict bound - clears the bar, recovering coverage to 19.7%. Because of
how the math works, this recovery could only ever help the Unlucky tag, never Overlooked - a
predictable asymmetry, documented explicitly rather than left looking like an unexplained
inconsistency.

---

## Where this landed

**Shipped, in order of confidence:**
1. **Unlucky** - the one tag with a real, price-controlled statistical basis (ratio 0.950,
   well-powered). Descriptive framing only, per the Day-13 redefinition.
2. **Overlooked** - real in the full sample, explicitly caveated as weaker/unproven in recent
   (2024+) data.
3. **DRIFT** - real and stable as a raw signal, but fully priced in; ships as descriptive color
   plus one narrow "overshoot caution" note for heavily-backed favorites.
4. **BB Index (rating engine)** - a validated 0-100 ability score with a five-part story,
   explicitly a sanity-checked description of a horse's fundamentals, never framed as a betting
   edge.

**Explicitly not shipped:** a Lucky tag in any form (killed on the evidence), any dose-response
"danger score" version of Unlucky (no gradient exists to grade), and anything claiming to beat
the market on win or exotic bets (six tests said no).

**What's still open, per `PRODUCTION_PIPELINE.md`:** none of this has ever run as an unattended
daily job - every step so far has been run manually inside interactive sessions. The two-tier
BUILD (periodic, backward-looking) / SCORE (daily, must finish before post time) architecture is
designed but not automated. The single biggest unresolved methodology question is that every
tag's threshold was calibrated against settled, final odds, but a same-day pipeline can only
ever have pre-race odds available - substituting one for the other has never been tested and
could shift where the tag thresholds should sit.

---

## Repo guide

- **Read the story in order:** `day1_context_benter_korea_project.md` then
  `day3_context_rds_connected_and_querying.md` then `day4_context_schema_locked_bc_mapped.md`
  then `day5_jeju_contamination_scare_resolved.md` then
  `day6_context_stage2_null_result_and_odds_roadmap.md` then
  `day7_full_context_piece_a_to_overshoot_null.md` plus `Day7_Q2_Overshoot_Context.md` then
  `day8_context_step1_null_and_lucky_engine_pivot.md` then
  `day10_context_danger_index_null_overlooked_tag_and_tiers.md` then
  `day11_context_bb_index_live_run_entry_row_bug_and_fix.md` then
  `day12_execution_file_rds_data_gap_blocker.md` then
  `day13_context_fund_p_debut_bug_unlucky_overlooked_fix.md`.
- **Equations and worked examples:** `benter_korea_explainer.md`.
- **Formal write-ups per milestone:** `Gate2_Report.md` (fundamental model + audit fix),
  `bc_fundmodel_final_check_report.md` and `bc_track_record_validation_report.md` (checksum),
  `PieceA_Report.md` and `PieceB_Report.md` (Harville + exotic pool), `Step0_Report.md` and
  `Step0_SURGE_Report.md`, `Lucky_Engine_Report.md`, `DRIFT_Tag_Report.md`,
  `Rating_Engine_Report.md` (BB Index).
- **Side investigation:** `audit.md`, `results.md`, `class_mapping.md`, `senior_summary_ko.md`
  (low-data-horse re-weighting question).
- **Core code:** `fit_engine.py`, `clogit.py`, `clogit2.py` (model fitting),
  `harville_engine.py` (exotic-bet probabilities), `horse_rating.py` (BB Index engine),
  `market_tags.py` (Unlucky/Overlooked tag logic), `drift_build.py`, `drift_evaluate.py`,
  `lucky_engine.py`, `lucky_build.py`, `lucky_evaluate.py`.
- **Production architecture and what's still missing to automate it:** `PRODUCTION_PIPELINE.md`.
- **Result artifacts:** calibration tables, ablation grids, and fitted coefficients - see
  `DATA_DICTIONARY.md` for what's included vs. excluded and why.

## What's not in this repo

- **Raw KRA race/horse/odds data.** It comes from a licensed data source and can't be
  redistributed. `DATA_DICTIONARY.md` documents the schema (columns, row counts) of every
  raw/per-record file the code was actually run against, so the pipeline is reproducible
  against an equivalent data source.
- **Two published academic papers** used as methodology references (Bolton & Chapman 1986,
  Benter 1994) - omitted for copyright reasons; both are findable via a quick search if
  you want the originals.
- A couple of internal, data-provider-specific documents (a schema/data-request doc, one
  internal results report), one internal meeting-transcript file, and one piece of direct
  email correspondence with the data provider - omitted as operational/confidential/personal
  detail with no bearing on the methodology.
- A live API key and a database hostname that appeared in the original working notes have
  been redacted from the docs that are included.

## Notebooks

Cell outputs were stripped before publishing (some had been run against real data and would
have re-leaked exactly what's excluded above). The code itself is intact - re-run against your
own data source to regenerate outputs.
