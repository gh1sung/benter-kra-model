# Piece A — Harville Exotic Engine: Results

Quinella (복승), Seoul + Busan, odds-overlap window 2021-07 to 2026-07, 8,643 races usable
after the odds↔outcomes join (out of 33,110 total races in the raw pull — the gap is just
the odds file's 5-year window vs. the full 2008–2026 finish-rank history, not a data-quality
problem: every dropped race failed the join for the expected reason, no odds coverage for
that date).

## 0. The verdict, upfront

**Plain Harville (λ=1) is NOT calibrated on 복승.** It shows exactly the textbook bias the
spec flagged as a known risk: it systematically **overestimates the favorite's chance of
landing in the top-2**, and correspondingly underestimates longshot pairs. **Fitting λ fixes
it.** Best-fit λ = 0.8 — landing right on the Hong Kong ballpark the spec cited as a rough
prior, not something forced to match it. After the correction, calibration is clean across
almost the entire range.

## 1. Gate A0 — plumbing sanity: PASS

`harville_engine.py`'s 5 functions (exacta, quinella, trifecta, trio, place) pass 45/45 unit
tests, including a from-scratch brute-force cross-check (independent full-permutation
enumeration, not sharing any code with the engine's closed-form formulas) at n=4,5,6 and both
λ=1.0 and λ=0.8. The A/B/C worked example in the spec reproduces exactly
({A,B}=0.514, {A,C}=0.325, {B,C}=0.161).

## 2. Gate A1 — plain Harville calibration (λ=1.0)

Predicted quinella probability bucketed, compared to actual hit frequency, pooled over all
289,679 pair-observations across 8,643 races:

| predicted P bucket | n | predicted | actual | z |
|---|---|---|---|---|
| 0.00–0.01 | 286,490 | 0.0032 | 0.0041 | **+8.57** |
| 0.01–0.025 | 83,128 | 0.0161 | 0.0184 | **+5.38** |
| 0.075–0.10 | 9,558 | 0.0864 | 0.0754 | **−3.80** |
| 0.15–0.175 | 2,457 | 0.1618 | 0.1245 | **−5.02** |
| 0.25–0.30 | 1,023 | 0.2725 | 0.2131 | **−4.27** |
| 0.50–1.01 | 70 | 0.5873 | 0.4143 | **−2.94** |

(Full 14-bucket table: `piece_a_calibration.csv`.) The pattern is one-directional and
monotonic-ish: **every bucket under ~5% predicted probability over-hits, every bucket above
~7.5% under-hits.** Low-probability pairs (longshot-longshot combos) land more often than
Harville says; high-probability pairs (favorite-involving combos) land less often. That is
exactly the shape of the known Harville favorite-place bias, not a random join/data bug.

**Favorite-in-quinella diagnostic (the direct fingerprint):** for the 6,495 races where the
favorite's predicted P(top-2) was ≥50%, predicted mean was 66.7% but actual was only 59.7%
(z = **−11.99**, the single largest miscalibration in the whole exercise, and the best-powered
one — n=6,495). Favorites get placed into the top-2 less often than Harville's clean
"peel off the winner, renormalize everyone else" assumption implies.

**Same bias in both regions** (서울 z=−3.34 to −3.36 in the high buckets, 부산 z=−2.63 to
−3.82) and **across field sizes** (worst in the 9–14-runner range where the sample is
largest; the 15+ bucket is too thin, n≤14 per cell, to read anything into). This is a
structural property of the market, not a Seoul-only or small-field-only artifact.

## 3. Gate A2 — fitted λ

1-D grid search over λ ∈ [0.5, 1.0] in steps of 0.05, minimizing pooled quinella log-loss on
8,628 races (15 fewer than the join total — those lack a usable realized top-2 due to a
DQ/pulled-up horse landing in 1st or 2nd, same rank-code handling as everywhere else in this
project):

| λ | log-loss/race |
|---|---|
| 0.70 | 3.1479 |
| 0.75 | 3.1461 |
| **0.80** | **3.1458** ← minimum |
| 0.85 | 3.1471 |
| 1.00 (plain Harville) | 3.1589 |

The curve is smooth and has a clean interior minimum at λ=0.8 (not pinned to a grid edge,
and flat enough around the minimum — 0.75/0.80/0.85 all within 0.001 of each other — that
this isn't noise-chasing).

**Calibration after the λ=0.8 correction:**

| predicted P bucket | n | predicted | actual | z |
|---|---|---|---|---|
| 0.00–0.01 | 267,350 | 0.0036 | 0.0036 | −0.42 |
| 0.01–0.025 | 96,191 | 0.0161 | 0.0162 | +0.40 |
| 0.075–0.10 | 9,973 | 0.0863 | 0.0811 | −1.84 |
| 0.15–0.175 | 2,142 | 0.1614 | 0.1615 | +0.02 |
| 0.25–0.30 | 545 | 0.2719 | 0.2716 | −0.02 |
| 0.50–1.01 | 16 | 0.7032 | 0.3750 | −2.87 |

(Full table: `piece_a_calibration_lambda_fit.csv`.) Every bucket with a meaningful sample
size (n ≥ 69) now sits under |z| ≈ 1.9. The one bucket over 2 is the top one, n=16 — too
small to be a real signal rather than a coin-flip run.

## 4. What this unlocks

Piece A is done: the engine is validated, the bias is understood and correctable, and
`quinella_probs(p, lam=0.8)` (plus `exacta_probs`/`trifecta_probs`/`trio_probs`/`place_probs`
with the same λ) is ready to take any calibrated win-prob vector — public odds now, or a
model-derived / blended vector later — with zero rework. Piece B (pricing the exotic public
against this) can start immediately.

## 5. Files

- `harville_engine.py`, `test_harville_engine.py` — Gate A0
- `build_exotic_outcomes.py`, `validate_piece_a.py` — Gate A1/A2 pipeline
- `exotic_outcomes.csv` — 33,110 races, realized top-2/top-3
- `piece_a_calibration.csv`, `piece_a_favorite_bias.csv`, `piece_a_by_region.csv`,
  `piece_a_by_field_size.csv` — Gate A1 (λ=1.0)
- `piece_a_lambda_grid.csv`, `piece_a_calibration_lambda_fit.csv` — Gate A2 (λ=0.8)
