# audit.md — Class/Low-Data Exclusion, Diagnostic Gate (§2)

**Data:** `gate2_features_built.csv` (369,139 horse-rows, 33,110 races, 2008–2026,
Seoul+Busan) joined to `race_class.csv`. Both low-info definitions run in parallel.

## Data checks (§1.2 + standing rules) — all pass

- **Class join rate: 100.0%** — `race_class` is already present in the feature table
  and is byte-identical to the standalone pull for all 33,110 races. 0 unjoined.
- Winner flag `is_win`: 33,068 races with exactly one winner, 42 dead-heats (2 winners),
  0 winnerless. Handled race-safe (no winner rows dropped).
- Region strings match (`서울`/`부산`); no Jeju.
- `CAREER_STARTS`: 4,423 nulls = debut horses (0 prior starts); treated as 0 for the
  career cut. Point-in-time as-of race date (existing build).
- Base 10-var conditional logit reproduces the plan's qualitative result:
  **CAREER_STARTS is the dominant negative main effect, β = −0.537** (95% CI
  [−0.567, −0.508]). The plan cites −0.4037; the gap is pooled-vs-walk-forward fit and
  standardization, not a sign/story difference.

---

## §2.0 Definition overlap — the two "하위군" framings do NOT agree

Cross-tab, class bottom-2 cut vs career-starts <5 cut (horse-rows):

| | career <5 | career ≥5 |
|---|---|---|
| **low class** | 101,165 | 130,943 |
| **normal class** | 12,928 | 124,103 |

- **P(thin-data \| low-class) = 43.6%** — fewer than half of low-class horses are actually thin-data.
- **P(low-class \| thin-data) = 88.7%** — almost all thin-data horses are low-class.
- Jaccard overlap 41.3%, φ = 0.357.

**Finding:** the relationship is asymmetric. Thin-data (new) horses nearly all sit in low
classes, but the low classes are dominated by *experienced-but-weak* horses that are not
thin-data at all. The senior's framing (class) casts a much wider net (62.9% of the field)
than the mechanism he named — 자료 부족 / thin data (30.9%). **His diagnosis and the actual
statistical problem point at different horses.** This matters for what "fix" is appropriate.

---

## §2.1 Prevalence (share of horse-rows low-info)

| threshold | class cut | | career cut |
|---|---|---|---|
| bottom-1 / <3 | 35.5% | | 19.9% |
| **bottom-2 / <5 (primary)** | **62.9%** | | **30.9%** |
| bottom-3 / <10 | 81.2% | | 53.8% |

By region (primary): 서울 class 65.9% / career 31.2%; 부산 class 58.5% / career 30.5%.
Both definitions clear the gate's >10% prevalence bar comfortably.

By year, the class share **rose** from ~50% (2008–2014) to ~73–78% (2021–2026); the career
share is stable ~26–30% after a 2008 ramp-up artifact (60% in 2008 because the data window
starts there, so every horse looks new).

---

## §2.2 Crux — cost of excluding "mostly low-info" races (>½ the field)

- **Class bottom-2: 63.0% of all races dropped** (20,855 / 33,110). Because class is a
  race-level label, a low-class race is 100% low-info — exclusion is all-or-nothing and
  removes roughly two-thirds of the training data.
- **Career <5: 24.8% of races dropped** (8,213 / 33,110); milder, since fields are mixed.

The class cut is enormously more expensive than the career cut for the same nominal idea.

---

## §2.3 Attenuation probe — THE test (race-clustered robust 95% CIs)

Base 10-var conditional logit + `low_info` main effect + `low_info ×` {AVESPRAT, LSPEDRAT,
LIFE_PCT_WIN} (the horse-ability features). Robust SEs cluster on race; validated against a
70-draw race bootstrap (bootstrap SD vs robust SE agree to ~3 decimals).

### Class cut (bottom-2)
| term | β | 95% CI | verdict |
|---|---|---|---|
| low_info (main) | — | — | **not identified** — constant within each race, cancels in the conditional logit (acts like a race fixed effect) |
| low × AVESPRAT | **+0.268** | [+0.211, +0.325] | **significant** |
| low × LSPEDRAT | **+0.163** | [+0.108, +0.217] | **significant** |
| low × LIFE_PCT_WIN | **−0.133** | [−0.158, −0.108] | **significant** |

### Career cut (<5)
| term | β | 95% CI | verdict |
|---|---|---|---|
| low_info (main) | −0.085 | [−0.129, −0.041] | significant |
| low × AVESPRAT | **+0.263** | [+0.198, +0.327] | **significant** |
| low × LSPEDRAT | +0.039 | [−0.032, +0.110] | not sig |
| low × LIFE_PCT_WIN | **−0.195** | [−0.223, −0.168] | **significant** |

**Interpretation — it's re-weighting, not simple attenuation.** For low-info horses:
- their **win/record signal (LIFE_PCT_WIN) is weaker** (negative interaction, both cuts) —
  this is exactly the senior's "자료가 부족해" intuition, and it holds for that feature;
- but their **speed figures (AVESPRAT/LSPEDRAT) stay or get *more* informative** (positive) —
  raw times remain a good signal even when a horse's win record is thin.

So low-info horses are not "unpredictable." The pooled single-slope model is mildly
mis-weighting them: it should lean **more** on speed figures and **less** on win-rate history
for these horses. That's a re-weighting/shrinkage problem, not a "delete the races" problem.

### Out-of-sample validation (walk-forward, expanding window, test 2010–2026, 29,418 races)
Not in-sample overfitting — modeling the difference improves genuine OOS log loss:

| cut | base 10-var | + interactions | improvement (95% CI) |
|---|---|---|---|
| class | 1.98933 | 1.98405 | **+0.00528 [+0.00391, +0.00665]** |
| career | 1.98933 | 1.98466 | **+0.00467 [+0.00346, +0.00589]** |

Real and significant, but **small** — ~0.27% of log loss (~0.005 nats/race on a ~1.99 base).

---

## GATE DECISION (pre-registered, automatic)

**Rule:** proceed to §3 iff the §2.3 interaction is significant (race-bootstrap) under at
least one definition AND that definition's prevalence >~10%.

- **Class cut: GATE CLEARS.** Interactions significant; prevalence 62.9%.
- **Career cut: GATE CLEARS.** Interactions significant; prevalence 30.9%.

This is the **opposite** of the plan's §7 predicted null. The pooled model does *not* fully
absorb the low-info difference — there is a small, OOS-real signal.

**But the shape of the finding redirects the fix.** The gate cleared because feature *weights*
differ, not because low-info horses are noise. Deleting them (variant B) throws away 63% of
races to fix something a soft re-weight handles. The evidence points at **variant C
(shrinkage / interaction), not variant B (exclusion)**. Recommend §3 be run as A vs C
(class-mean shrinkage, real `race_class` buckets, 국산/혼합 separate), with B included only as
a cost benchmark.

### What §3 still needs (not yet available)
- **`win_odds_5yr.csv`** — required for Metric #2, the stage-2 blend α/β (the ROI-relevant
  number) and the ROI backtest. Not provided, so the §3 *money* question is untested.
- Given the closed-Benter / efficient-market prior, the ~0.3% log-loss gain is very likely to
  wash out at the blend against public odds — but that is the next thing to confirm, not assume.

### One structural note for the meeting (see class_mapping.md)
The live class ladders in this data are **국산 vs 혼합**, not 국산 vs 외산 — 외산 as a separate
class exists only in 2008 (20 races). The "keep ladders separate" rule and §3 C-variant
buckets should be 국산/혼합.
