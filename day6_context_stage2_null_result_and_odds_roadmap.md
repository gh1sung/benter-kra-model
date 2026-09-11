# Stage 2 Complete: Null Result on Win + Roadmap to Early Odds & Exotics (Day 6)

> Continuation of `day1_context_benter_korea_project.md`, `day4_context_schema_locked_bc_mapped.md`,
> `day5_jeju_contamination_scare_resolved.md`. Add to project knowledge alongside the other
> day-context docs. (Note: this is filed as "Day 6" — "Day 5" was already used for the Jeju
> contamination check, so this continues that numbering rather than colliding with it.)

## TL;DR

Stage 2 (Benter's α/β combination of the fundamental model with public final odds) is **done,
audited, and null on the win market**. Combining the fundamental model with final settled odds
adds essentially zero (ΔR² ≈ 0, not statistically significant, LR p=0.62). This is a real,
mechanically-explained finding, not a bug: when the model and the public disagree, actual race
outcomes side with the public every time, meaning the model carries no information the public
doesn't already have. The original "Korean public is weak/exploitable" hypothesis did not survive
contact with the win pool — it's sharp.

**This is not the end of the project.** Three directions were discussed; two were chosen to pursue
now, one was explicitly parked. The rest of this doc is what a new chat needs to know to pick up
exactly where this left off.

---

## 1. Stage 2 results — what was built and what it found

Pipeline: rebuilt the frozen 10-variable fundamental model (baseline-9 + `CAREER_STARTS`,
`race_safe=True`, checksum reproduced at test pseudo-R² = 0.1424) → generated `f_i` (fundamental
win probability) **out-of-sample** via expanding walk-forward (never scored a race with a model
trained on it) → built `π_i` (public win probability) from `win_odds_5yr.csv` (Jeju dropped,
overround-cleaned) → joined on `(date, region, race_no, gate_no=back_num)` → fit
`utility_i = α·ln(f_i) + β·ln(π_i)` (conditional logit, depth 1 = win-only) on 2021–2024, evaluated
on held-out 2025–2026.

**Headline numbers (TEST, 2025–2026):**
- R²(public-only) = **0.2120**
- R²(fundamental-only) = **0.1416**
- R²(combined) = **0.2120** (same to 4 decimals)
- ΔR² vs public ≈ **+0.00003** — indistinguishable from zero
- raw α = 0.032 (not significant), raw β = 0.943
- Likelihood-ratio test on adding `ln(f_i)` to public-only: **p = 0.62**
- Walk-forward by year (2022–2026) and by track (Seoul/Busan): no fold shows a positive,
  significant contribution from the fundamental model. The one nominally significant fold (2022,
  101 races) was *negative* on its own holdout year — read as small-sample noise, not a real effect.
- Combined model is well-calibrated on TEST (no bucket z-score exceeds ±1.5) — the null isn't
  hiding behind a calibration problem.

**Why it failed — the mechanical diagnosis, not just the number.** Bucketed the joined data by
how much the model disagrees with the public (`ln f_i − ln π_i`). In every bucket, actual win
frequency tracks the *public's* number, not the model's:

| model vs public | public says | model says | actually won |
|---|---|---|---|
| model ≪ public | 15.4% | 7.3% | **15.5%** |
| model ≫ public | 3.1% | 8.5% | **2.9%** |

When the two disagree, reality sides with the public every time. That means the fundamental
model has essentially **zero orthogonal signal** on the win market — everything in it (speed
figures, win rates, jockey stats, weight, post position) is information the betting public
already prices in. This explains the null mechanically, not just statistically.

**Files produced:** `stage2_pi_f_joined.csv`, `stage2_results.csv`, `stage2_walkforward.csv`,
`stage2_per_track.csv`, `stage2_calibration.csv`, `stage2_join_diagnostics.txt`,
`checksum_results.csv`, `Stage2_Report.md`, plus corrected `fit_engine.py` (see §4 for the bug
that was caught and fixed here).

**Reframe of the original hypothesis:** going in, the working assumption was "Korea's public is
weak, therefore exploitable" (see day1/day4 docs). On the **win market**, that's now disproven —
public-only R² (0.21) beats the fundamental model (0.14) outright, and calibration is clean.
The revised, narrower hypothesis carried forward: the win market may be efficient specifically
*because it's where the most attention and (possibly) sharp/late money concentrates* — which
points directly at the two directions below rather than "give up."

---

## 2. Decision: two directions chosen, one parked

Discussed three options. Decision, with the reasoning behind it:

1. **Early odds vs. final odds (chosen — start here).** If final odds are sharp because informed
   money arrives late, the fundamental model's proper partner isn't the final number — it's the
   early number, before that late money has moved it.
2. **Exotic pools — 복승/쌍승/삼복승 etc. (chosen — build in parallel).** Benter's own observation
   (which 지환 recalled correctly): the more combinatorially complex the bet type, the harder it
   is for the public to price correctly, so the gap between model and market grows. This also
   targets a bigger, more lucrative slice of actual betting volume than win-only.
3. **Computer vision / trouble-in-running extraction (parked, not abandoned).** Genuinely the
   highest-ceiling source of real orthogonal signal (pace, ground loss, traffic — things a
   results table can't show), but too time-consuming to chase before the two cheaper, data-ready
   directions are exhausted. Explicitly not now. Separately, there's an open thread about a CEO
   conversation on attracting a new generation of bettors (current base skews old and is
   shrinking) — CV-based content could plausibly serve that too, but that's a distinct
   product/marketing conversation to pick up later, not a modeling decision.

---

## 3. Direction 1 — Early odds vs. final odds

### 3.1 Correct framing (important correction made mid-conversation)

KRA is **pari-mutuel**, not fixed-odds — everyone who bets a horse gets paid the same final
dividend regardless of when they placed the bet. So this is **not** "buy at the early price,
cash out at better odds" (that's not how pari-mutuel works, and an earlier draft of this idea
stated it wrong). The correct question is:

> Does [fundamental model + early odds] predict the actual race outcome better than [final odds]
> alone?

Final odds remain the benchmark to beat. If model+early beats it, the product isn't a betting
execution trick — it's **a better probability estimate than the public's own final number**,
which is sellable to the team/customers as a rating product, independent of any specific bet
placed.

### 3.2 Why this could work where Stage 2 failed

Stage 2 failed because the fundamental model is redundant with information already in final
odds. Early odds are different: they're the market's read **before** late money (possibly
informed/insider money, possibly just casual late piling-on) has moved it. If that late move is
overshoot rather than genuine information, final odds will be *overconfident* relative to truth
on the horses that got hit hardest late — and only someone who saw the early number can detect
that.

### 3.3 Why this is strategically strong for the team specifically

Displaying real-time pre-post odds publicly is restricted in Korea, and the team pays to collect
this data — so unlike Stage 2 (which used only publicly-derivable final odds and public
race-facts), this input is **proprietary** and not easily replicated by a competitor. Even a
null result here is informative (it would mean Korea's late money is itself efficient/informed —
a real finding about market microstructure), and a positive result is directly defensible as a
product, not just a paper finding.

### 3.4 Data available

- 실시간 배당 (real-time odds) snapshots at **25, 15, 10, 6, 2 minutes before post**, plus the
  already-held final odds. Five time points, not just one early/late pair.
- **Capped at ~1 year of history.** Eligible races after the fundamental model's own filters
  (1600–2000m, 건/양, age≥3) run ~300/year, so this test will have on the order of **~300 races**
  to work with — enough for a directional read, not for a tight, publication-grade confidence
  interval. If 300 proves too thin once real data is in hand, the lever is relaxing the distance
  filter (more races, but then track/distance controls need to be added back in — a real
  modeling cost, not free).

### 3.5 Feature construction — decided, with the reasoning locked in

**Do not use all 5 raw time-slices as separate regressors.** A quick simulation built to mirror
this exact structure (5 correlated snapshots close together in time) showed correlations of
0.93–0.98 between adjacent slices and **VIF (variance inflation factor) of 20–36** per slice when
used raw — a severe multicollinearity problem. At ~300 races, that would produce unstable,
sign-flipping coefficients that are really just fitting noise, not signal.

**Decided feature set instead** (level + drift + optional late-acceleration), verified
essentially collinearity-free in the same simulation (correlation between level and drift ≈
−0.08, VIF ≈ 1.01 for both):

1. **LEVEL** = `ln(odds at 25-min)` — where the market started, before late money.
2. **DRIFT** = `ln(odds at 2-min) − ln(odds at 25-min)` — total movement and direction. Most
   likely carrier of the late-money-overshoot signal.
3. **LATE_ACCELERATION** (optional 3rd feature, add only if 1 & 2 show promise) =
   (2-min move) − (average of the 25→6-min moves) — isolates whether the *very last* stretch
   moved differently from the steady earlier trend; the sharpest test of "does late money behave
   differently from earlier money."

Consider computing drift **relative to the field** (horse's move minus the race's average move)
to net out race-wide betting-volume effects (a quiet Tuesday card vs. a big Saturday card) that
would otherwise masquerade as horse-specific signal.

**Explicitly rejected for the model input (not for storytelling):**
- All 5 raw slices — collinearity, above.
- k-means/hierarchical clustering into pattern archetypes ("steamer," "drifter," "stable") as a
  *model input* — at ~300 races, cluster boundaries would be unstable across resamples, and
  discretizing a continuous signal throws away information for no benefit here. **Fine, even
  good, as a post-hoc descriptive/presentation layer** once the real model is built (e.g. "X% of
  races show late-steam patterns and those horses beat their final odds by Y%" is a strong story
  for [program supervisor]/사장님) — just not as what the conditional logit actually fits on.
- (Terminology note for the room: KNN — k-nearest-neighbors — is a *supervised* method, not
  clustering. K-means/hierarchical clustering is the unsupervised family actually being described
  when talking about "pattern types." Easy mix-up, worth having straight when explaining this.)
- Sequence models (RNN/LSTM over the 5 timepoints) — far too many parameters for a ~300-race
  budget; high overfitting risk for no clear benefit over level/drift.
- PCA on the 5 slices — statistically fine but less interpretable than level/drift for
  communicating results to non-technical stakeholders; only worth revisiting if level/drift
  underperforms.

### 3.6 Execution readiness

This reuses the exact Stage 2 conditional-logit machinery (`fit_engine.py`), just with
`ln(π_i^early-derived)` (or LEVEL/DRIFT as separate regressors) swapping in for
`ln(π_i^final)`, and **final odds becoming the thing to beat** rather than the model's partner.
Turnaround should be fast once 실시간 배당 access lands — the fundamental model side is already
built and frozen; only the odds-side feature construction and the join are new work.

---

## 4. Direction 2 — Exotic pools (복승/쌍승/삼복승 etc.)

### 4.1 The mechanism (Benter/Harville), and why the win-market null doesn't block this

Benter's point, correctly recalled: the more combinatorially complex a bet type, the worse the
public gets at pricing it, because humans can't intuitively rank all ordered pairs/triples in a
field the way they can rank single-horse win chances.

Key insight for **why Stage 2's null doesn't disqualify this path**: exotic probabilities can be
derived from win probabilities via the **Harville formula**:

```
P(A 1st, B 2nd) ≈ P(A wins) × P(B wins) / (1 − P(A wins))
```

The win model only needs to be **calibrated** (which it already is — Stage 2's own calibration
table is clean) — it does *not* need to beat the win public. The edge, if it exists, comes from
the **exotic pool being less efficient than the win pool**, not from the win probabilities
themselves being better than the public's. This is why exotics is a legitimate parallel path even
though win-market ΔR² was null.

**Known refinement to apply, not skip:** plain Harville is known to slightly overestimate a
favorite's chance of finishing 2nd/3rd. Standard corrections exist (Henery/Stern/Lo-style
discount factors). Same pattern as the rest of this project: replicate the baseline formula
faithfully first, then fit the documented correction — don't skip straight to a custom model.

### 4.2 Two pieces, different data readiness

**Piece A — build & validate the exotic probability engine. Runnable now, zero new data needed.**
Apply Harville to the existing calibrated win probabilities, then check calibration against
actual finish orders (does predicted P(A-then-B) match how often A-B actually happens?). This
is the prerequisite for everything else in this direction and doesn't wait on any data pull.

**Piece B — measure actual edge vs. the exotic public. Needs a data pull.** Requires **exotic
final dividends** (what a winning 복승/쌍승 ticket actually paid) to compute the exotic pools'
implied probabilities and backtest ROI/EV. `win_odds_5yr.csv` is win-only — this doesn't cover
it. These likely live in the race-*results* payload on data.go.kr (not the real-time feed used
for win odds), which means they are **plausibly available for more years than the 1-year-capped
real-time odds** — worth confirming as the first step of this piece, since it changes the sample
size math considerably in a good way if true.

**Known data coverage, per what's been heard from the team (needs confirmation, not yet
verified against source the way the RDS schema was):** roughly 1 year of 단승식/복승식-type
exotic history, only ~6 months of 삼승식 (trifecta-type). **Start with 복승 (quinella), not
trifecta** — quinella hits often enough for a reasonably tight ROI estimate within a year;
trifecta hits are rare and high-variance, so ROI estimates there would swing wildly even with a
full year, and the 6-month cap makes it worse. Manage expectations on trifecta specifically —
plan to report it as exploratory only, not a headline number.

---

## 5. Combining Direction 1 and Direction 2 — the actual final goal

This is the endpoint of the whole Benter project as currently scoped: **does early-odds-informed
model output, fed into the exotic-probability engine, beat exotic final odds?**

**Why this could be more than additive.** Exotic probabilities are *products* of win
probabilities (Harville). If early odds make the win probabilities even modestly more accurate,
that improvement gets multiplied through the combinatorics of pairing/ordering horses — a small
per-horse gain can compound into a larger exotic-level gain than either piece alone would
suggest.

**The honest symmetric risk.** Harville multiplies noise the same way it multiplies signal. If
early odds make the win probabilities *worse* (i.e., Direction 1 turns out null — Korean late
money is itself efficient), feeding that into the exotic engine would make exotic probabilities
worse too, not better.

**Why this is still low-risk to attempt — the dependency structure:**
- **Exotics-with-final-odds-derived win probabilities (Direction 2 alone) is the robust floor.**
  It only needs calibrated win probabilities, which already exist from Stage 2, and doesn't
  depend on Direction 1 succeeding at all.
- **Direction 1 succeeding is what pushes toward the ceiling** — feeding improved (early-odds-
  informed) win probabilities into the same exotic engine.
- Either way, both floor and ceiling clear the one result already proven not to work (beating
  the win market with final odds alone), so there's no scenario where this combined effort ends
  up worse than where Stage 2 left off.

### Recommended sequencing (each step stands alone if the next stalls on data access)

**Decided starting point: exotics Piece A, not early odds.** Reasoning: early odds is blocked on
external access (실시간 배당 permission, and it's not even confirmed yet whether that lives in
RDS/DBeaver at all — see the open question below). Exotics Piece A needs nothing new — it's
Harville math on win probabilities and finish orders already in hand from Stage 2 — so it can
start immediately instead of sitting idle waiting on someone else's approval. Rule of thumb going
forward: don't let a request that needs another person's sign-off block work that's already
unblocked.

1. **Today, in parallel with #2:** Send both outstanding access/data requests at once — (a)
   실시간 배당 access, and (b) exotic final dividends. Do this immediately rather than after
   finishing Piece A, since the clock on someone else's approval doesn't start until asked.
   **Open question to fold into request (a):** it isn't confirmed that the 5-timepoint real-time
   odds (25/15/10/6/2-min) actually live in RDS/DBeaver — RDS is only known to hold *some*
   pre-race snapshot, not confirmed to be the full time series described. Ask [data team lead] directly
   rather than assuming, same "verify at the source" discipline that resolved the Jeju scare and
   the fit_engine sync gap. Request (b) is expected to be the faster of the two, since exotic
   dividends are likely a data.go.kr public-API pull similar to the one already done for
   `win_odds_5yr.csv`, not an internal permission gate.
2. **Starting now:** Build + calibration-test the exotic probability engine (Piece A) — no new
   data needed, proves the plumbing works, and is not throwaway work regardless of how Direction 1
   turns out later (the engine just takes a win-probability vector as input, whether that vector
   comes from final odds now or early-odds-improved probabilities later).
3. **As soon as exotic dividends land:** Exotic EV/ROI backtest using final-odds-derived win
   probabilities (Piece B) — the robust floor result, likely on more years of data than the
   real-time odds allow. Start with 복승.
4. **Whenever 실시간 배당 access lands (may be before or after #3):** Direction 1 alone — does
   model + early odds (LEVEL/DRIFT/LATE_ACCELERATION) beat final odds as a *win* predictor?
   (~300 races, directional read.)
5. **If 4 shows promise:** feed those improved win probabilities into the Piece A/B exotic
   engine — the combined, highest-ceiling test, bounded by whatever overlap exists between the
   1-year real-time-odds window and the exotic-dividends window.

---

## 6. Standing rules carried forward (still binding)

- **race_safe=True always** — never let a per-row dropna silently drop the actual winner from a
  choice set (the Gate 2 audit bug, re-confirmed still present in a stale synced copy of
  `fit_engine.py` during Stage 2 and re-patched — see `Stage2_Report.md` §2c for the full story;
  the corrected `fit_engine.py` delivered alongside the Stage 2 outputs is the one to trust).
- **f_i must be out-of-sample on every race it's scored on** — expanding walk-forward, never a
  model scored on its own training races. Applies identically to any future f_i regeneration for
  Direction 1/2 work.
- **Always check for a newer version of any file before trusting it** — this project has hit
  stale-file bugs twice now (pre-audit `run_final_test.py`, and the un-synced `fit_engine.py` fix
  during Stage 2). Assume project knowledge can lag behind the actual corrected state.
- **Jeju exclusion** — still required any time `win_odds_5yr.csv` or any future odds/dividends
  pull is joined to the fundamental model (Seoul+Busan only, confirmed at the RDS source in the
  Day 5 Jeju check).
- **Region/date/gate-number join conventions** — `부산경남` (odds side) ↔ `부산` (RDS side);
  `gate_no`/`back_num` is the true per-race horse key; `horse_id` in the odds file is NOT a real
  horse identifier (it's identical to `gate_no` in 100% of rows) — do not join on it.
- **CLASS_MOVE** — still blocked pending [data team lead]'s class-hierarchy mapping document, unchanged
  status.
- **Open verification item, still not closed:** whether raw race facts (finish positions, etc.)
  in RDS are ever retroactively edited after the fact (e.g. disqualification appeals). Low
  estimated risk (far more stable than a rolling rating field) but not yet confirmed with [data team lead].

## 7. Open thread, not part of the modeling roadmap

CEO conversation about the aging Korean racing-fan base and attracting a new generation of
bettors — flagged as a genuinely separate, interesting topic to pick up later. Possibly connects
to a future computer-vision/content angle (Direction 3, parked above), but it's a product/
marketing conversation, not something that changes the current modeling plan.
