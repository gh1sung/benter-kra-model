# Piece B — Does the Exotic (복승) Pool Misprice vs the Win Pool?

> Continuation of Piece A (`harville_engine.py`, validated). All 4 inputs from the plan
> are now in hand: `win_odds_5yr.csv`, `exotic_odds_5yr.csv` (uploaded), the raw
> finish-rank pull (uploaded, built into `exotic_outcomes.csv`), and Piece A's
> λ=0.8-corrected Harville engine.

## 0. The verdict, upfront

**No edge. The 복승 (quinella) pool is not mispriced relative to the win pool.**
Win-pool-derived Harville probabilities (`q_model`) do **not** predict actual top-2
finishes better than the exotic pool's own price (`q_market`) — on log-loss, the
market is marginally *sharper* than the model, not the other way around. The EV
backtest confirms it: betting every positive-EV pair loses money in **every single
year** from 2021–2026, and out-of-sample walk-forward testing makes it worse, not
better. This is a clean null, in the same family as Stage 2's null result on the win
market itself — informative, not a failure.

**Before that verdict was trustworthy, a real data bug had to be found and fixed** (§1)
— it was inflating one year's ROI to +1,239%, which would have looked like a huge win
if taken at face value.

## 1. Data quality issue found and fixed: sentinel dividend value

`exotic_odds_5yr.csv` contains **3,258 rows** (0.7% of the 복승식 pool) with
`odds == 9999.9` — a placeholder/sentinel value, not a real settled dividend. The
tell: a genuine payout is a continuous number that shouldn't repeat exactly; this one
did, 3,258 times, across unrelated races and pairs. **85% of these rows (2,770) are
concentrated in 2021**, which is exactly the year that initially showed a wildly
positive backtest ROI (+1,239%) before the fix — 123 "hits" at an average dividend of
1,290 turned out to be dominated by these placeholder rows. After dropping them,
2021's ROI falls to -13.3%, in line with every other year. **This is worth flagging
back to whoever owns the exotic-odds pull** — the same placeholder may exist in the
other pool types (쌍승식, 삼복승식, 복연승식) in this file, unverified here since Piece
B only used 복승식.

Two smaller, related fixes followed from the same root cause and Piece A's own "drop
rather than partially include" convention:
- **22 races** dropped for having no usable realized top-2 (a DQ'd/pulled-up horse in
  rank 1 or 2 — same rank-code handling as Piece A, which hit the identical 15-race
  exclusion before this session's larger raw pull expanded coverage slightly).
- **13 races** dropped because the *winning* pair's own dividend was itself one of the
  sentinel rows — we can't confirm a bet result without a real price for the winner,
  so the whole race is unscoreable, not just that one pair.

## 2. Final dataset

| Step | Races |
|---|---|
| Races in the raw finish-rank pull | 33,110 |
| No win-odds match (5-yr odds window vs. 2008–2026 history) | −24,467 |
| No exotic-odds match | −1 |
| No usable realized top-2 (DQ/pulled-up) | −22 |
| Winning pair's own dividend was a sentinel value | −13 |
| **Usable races** | **8,607** |

454,432 (race, pair) rows. Every race has **exactly one** realized winner (Gate B0
hard check, verified) and `q_market` sums to exactly 1.0 per race by construction.
`q_model` covers ~99.8% of its own probability mass on average across the quoted
market; only 41 races (0.5%) fall below 90% coverage, a minor residual effect of
the sentinel-row removal that doesn't change the picture below.

**Measured takeout**: backed out from the data itself (not hard-coded), median 27.0%,
tight distribution (σ=0.15pp) — confirms the plan's ~27% estimate.

## 3. Gate B1 — does the win pool carry information the exotic pool missed?

**Calibration** — both `q_model` and `q_market` are reasonably well-calibrated; no
bucket with meaningful sample size shows a large systematic miss (all |z| well under
2 except a couple of thin top buckets, n≤14, same "too small to be signal" caveat
Piece A flagged for its own top bucket).

**Log-loss** (lower is better):

| metric | q_model (win pool via Harville) | q_market (exotic pool's own price) |
|---|---|---|
| pooled log-loss | 0.0775 | **0.0765** |
| winning-pair-only log-loss | 3.133 | **3.079** |

The market's own price is marginally sharper on both measures. **q_model does not
beat q_market — Gate B1 verdict: the win pool is not clearly sharper than the exotic
pool for ranking pairs.** Per the plan's own logic (§5), this is a reason for caution
before trusting any EV number, and the backtest below bears that out.

## 4. Gate B2 — EV backtest

**τ=0 (assumption-free, no tuned parameters):**

| | value |
|---|---|
| bets placed | 87,683 |
| races touched | 8,528 |
| hit rate | 0.87% |
| staked | 87,683 |
| returned | 62,649 |
| **ROI** | **−28.6%** |

Close to (slightly worse than) the measured −27% takeout — consistent with **no edge
beyond just eating the takeout**, not a profitable strategy.

**By year — stable and consistently negative, no cherry-picking:**

| year | bets | ROI |
|---|---|---|
| 2021 | 10,070 | −13.3% |
| 2022 | 15,962 | −32.4% |
| 2023 | 17,380 | −24.8% |
| 2024 | 17,195 | −27.5% |
| 2025 | 17,333 | −31.5% |
| 2026 | 9,743 | −41.3% |

**Walk-forward** (τ tuned on 2021–2023, evaluated OOS on 2024–2026): best τ=0.3 in
training, but the OOS result is **−41.5%** — worse than the untuned τ=0 baseline.
Tuning τ doesn't rescue this; if anything it overfits to noise in the training years.

## 5. Bottom line

- **Gate B0**: pass (after fixing the sentinel-dividend bug).
- **Gate B1**: the win pool is not sharper than the exotic pool — a genuine, if mild,
  negative signal that should lower confidence in Gate B2 before even running it.
- **Gate B2**: no edge, in every year, and OOS testing makes it worse, not better.

**This is the "efficient market" outcome the plan explicitly said was worth reporting
honestly** (§5, §9): 복승 is priced consistently with what the sharp win pool would
imply via Harville. There's no exploitable gap here. Combined with Stage 2's null on
the win market itself, the picture across both pieces of this project is the same:
Korea's *final* odds, in both the win and (at least this) exotic pool, look
efficiently priced relative to a fundamental/Harville-derived challenger.

## 6. What this does and doesn't close off

- The §7 secondary test (swap in the Stage 2 combined model instead of pure public
  win odds) wasn't run this session — the plan itself expects it to be null too, and
  Gate B1 already suggests the win-pool information channel isn't the source of any
  edge, so it's a low-priority confirmation rather than a new lead.
  Not run — the plan expects it to be null too, and Gate B1 already suggests the
  win-pool information channel isn't where an edge would come from, so it's a
  low-priority confirmation rather than a promising new lead.
- **The sentinel-dividend bug is worth checking in the other exotic pools** (쌍승식,
  삼복승식, 복연승식) before anyone uses this file for those bet types — this session
  only cleaned and validated 복승식.
- Direction 1 (early-odds work) remains untouched and separate, as scoped.

## 7. Files

- `build_piece_b_dataset.py`, `run_piece_b.py`, `test_piece_b.py` — pipeline + tests
  (10/10 data-independent unit tests pass, including the plan's own worked-example
  numbers)
- `piece_b_dataset.csv` — 454,432 rows, one per (race, pair)
- `piece_b_calibration.csv`, `piece_b_logloss.csv`, `piece_b_backtest_by_year.csv` —
  Gate B1/B2 outputs
- `exotic_outcomes.csv` — 33,110 races, realized top-2/top-3 (rebuilt this session
  from the uploaded raw finish-rank pull, via Piece A's `build_exotic_outcomes.py`)
