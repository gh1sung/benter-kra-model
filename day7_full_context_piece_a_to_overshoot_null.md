# Day 7 — Full Context: Piece A → Piece B → Direction 1 (Q1) → Q2 Overshoot

> This is the complete handoff for the whole day-7 session (~6 hours), start to finish. The
> existing `Day7_Q2_Overshoot_Context.md` only picks up after Direction 1 — this file adds
> everything that came before it (Piece A, Piece B) so nothing from the day is missing.

## 0. The one-paragraph version

We spent the day testing whether anything in Korean racing can beat the market's own final
odds. Piece A built and validated a Harville engine (the math that turns win probabilities
into exotic-bet probabilities) and found it needed a correction factor (λ=0.8) to match
reality. Piece B used that corrected engine to ask "does the win-pool price know something
the 복승 (quinella) pool doesn't?" — clean null, no edge, loses money every year 2021-2026.
Direction 1 asked "can early odds (before the market settles) beat the final odds?" — also
null. We then pivoted to Q2: "does the market's final price *overshoot* based on late
betting momentum?" This one worked statistically (real, significant effect, confirmed after
expanding the sample 4x) — but when we ran the actual betting simulation, the edge (~8%) was
less than half the betting fee (20-27% takeout), so it's a real finding but **not a
profitable strategy** on either the win or exotic pool. Full detail below, in the order it
happened.

---

## PART 1 — Piece A: Building and Validating the Harville Engine

**What this piece is for:** Exotic bets (like 복승/quinella, betting on which 2 horses finish
top-2 in either order) need more than just win probabilities — you need a formula to convert
"horse A has a 30% chance to win" into "horses A and B have an 18% chance to finish 1-2
together." The Harville formula is the standard way to do that conversion. Piece A's job was
to build it and check whether it actually matches reality in the Korean market.

**Data:** 33,110 total races pulled, narrowed to 8,643 usable races after joining to odds
data (odds only exist for a 2021-07 to 2026-07 window; races outside that window were
dropped — not a data quality problem, just the file's date range).

### Gate A0 — does the math work? PASS
The engine's 5 functions (exacta, quinella, trifecta, trio, place) passed 45 out of 45 unit
tests, including a from-scratch brute-force check that doesn't share any code with the
engine (built independently by literally enumerating every possible finishing order and
counting) — this confirms the formulas are implemented correctly, not just "looks
reasonable."

### Gate A1 — is plain Harville (no correction) accurate? NO
Compared predicted quinella probabilities to what actually happened, across 289,679
pair-observations. Found a clear, one-directional bias: <cite index="1-40,1-41,1-42,1-43">every bucket under about 5% predicted probability over-hits (actual happens more than predicted), and every bucket above about 7.5% under-hits</cite>. In plain terms: **favorites get placed into the top-2
less often than the plain formula assumes, and longshot pairs land more often than expected.**
The most powerful single check of this — races where the favorite alone was predicted ≥50%
to land top-2 — showed predicted 66.7% vs actual only 59.7% (a huge statistical gap, z=-12,
essentially impossible to be random noise given 6,495 races of sample size). This same
pattern held in both Seoul and Busan tracks and across different field sizes, so it's a real
structural feature of the market, not a fluke of one subgroup.

### Gate A2 — fixing it with a correction factor (λ)
Ran a grid search testing different "λ" (lambda) values — a single tuning number that dials
down the favorite-bias — and found λ=0.8 minimizes prediction error, landing close to a
similar correction used in Hong Kong racing research (used only as a rough sanity check, not
forced to match). After applying λ=0.8, the calibration problem essentially disappeared:
every bucket with a meaningful sample size fell within normal statistical noise (|z| under
about 1.9, versus z up to -12 before the fix).

**Bottom line for Piece A:** the Harville engine works, but only after correcting it with
λ=0.8. `quinella_probs(p, lam=0.8)` (and equivalent functions for other bet types) is the
validated tool ready for Piece B to use on any win-probability vector — market odds today,
or a model-derived vector later.

---

## PART 2 — Piece B: Does the Exotic Pool Mispricing Anything vs. the Win Pool?

**What this piece is for:** Now that the Harville engine (from Piece A) is trustworthy, use
it to ask: if you take the *win pool's* prices and run them through Harville to predict the
*quinella pool*, do you beat the quinella pool's own price? If yes, that's a real,
exploitable mispricing between the two pools.

### A real data bug found and fixed first
Before trusting any result, found that the exotic odds file (`exotic_odds_5yr.csv`) had 3,258
rows (0.7% of all quinella data) with the exact value `9999.9` repeated — a placeholder
value standing in for missing real payouts, not a genuine number (a real payout is
continuous and essentially never repeats exactly, so seeing the *same* number thousands of
times is the tell). 85% of these fake rows were concentrated in 2021, which is exactly the
year that — before the fix — showed a wildly unrealistic +1,239% ROI. After removing the
placeholder rows, that year's ROI dropped to a normal -13.3%, in line with every other year.
This is flagged as worth reporting back to whoever owns the raw exotic-odds data pull, since
the same placeholder pattern might exist in other bet types (쌍승식, 삼복승식, 복연승식) that
weren't checked this session.

Final usable dataset after all cleaning: 8,607 races (454,432 race-pair rows), each race
having exactly one confirmed real winner.

**Measured betting-house cut (takeout) on this pool:** 27.0% (backed out from the real data,
not assumed) — a tight, consistent number across the sample.

### Gate B1 — does the win-pool price contain info the exotic pool is missing?
Compared prediction sharpness (log-loss — lower means better predictions) of two approaches:
using win-pool prices pushed through Harville (`q_model`) vs. just using the exotic pool's
own quoted price (`q_market`). Result: <cite index="2-77,2-78">the market's own price was marginally sharper on both the pooled measure and the winning-pair-only measure</cite>. In plain terms: no, the win pool doesn't
know something the exotic pool doesn't — if anything the exotic pool's own price is very
slightly better.

### Gate B2 — does betting on this "edge" actually make money?
Ran the actual betting simulation: bet on every pair where the model said the expected value
was positive. Result: **-28.6% ROI** on 87,683 bets across 8,528 races — close to (slightly
worse than) simply eating the measured 27% takeout, meaning there's no edge beyond just
losing to the house fee. This held up **every single year from 2021 to 2026** (ROI ranged
from -13.3% to -41.3%, never positive), so it's not a cherry-picked bad stretch. Even trying
to tune a threshold parameter on early years and testing it on later years (a standard
overfitting check) made results *worse*, not better (-41.5% out-of-sample).

**Bottom line for Piece B:** clean null result. The 복승 (quinella) exotic pool is not
mispriced relative to the win pool — Korea's market looks efficiently priced in both places.
This matches the same "efficient market" pattern seen elsewhere in the broader project (e.g.
Stage 2's earlier null on the win market itself).

---

## PART 3 — Direction 1 / Q1: Can Early Odds Beat the Final (Settled) Odds?

**What this piece is for:** So far, both pieces found the *final* settled odds are hard to
beat. This direction asked a different question: what if you only had the *early* odds
(before the market fully settles, e.g. 25 minutes before the race) plus the fundamental
horse-stats model — could that combination predict the outcome better than waiting for the
final number?

**Result: null.** Across every version tested (Stage 2's final-odds model, Piece B's exotic
pool, and this early-odds test), <cite index="0-28,0-29,0-30,0-31">the fundamental model — 10 horse-stat variables including speed rating, life win percentage, wins per race, jockey stats, weight, post position, distance change, and career starts, run through a ridge-regularized fit — added no orthogonal signal beyond the market odds, with its coefficient sitting near zero (about 0.12) every time it was tested</cite>.

**What this means in plain terms:** you cannot beat the crowd's final price by knowing more
*about the horses themselves* using this kind of data — the market has already absorbed all
of that information into the price by the time it settles. Early odds specifically also
can't beat the final odds: the market gets *more* accurate as it approaches race time, so
waiting for the close is better than betting on early numbers.

**One useful side-finding buried in this null result:** while testing this, a related but
separate quantity was measured — how much horses' odds move between the early snapshot and
the close (this is called "drift"). Without conditioning on the final odds at all, drift
*alone* had a strong **positive** relationship with winning (coefficient +0.63): horses that
get backed heavily late tend to win *more* often. This is the seed that led directly into
Part 4 below.

---

## PART 4 — Q2: The Overshoot Correction (full detail in the companion file)

This is where the day's one real finding came from. Full blow-by-blow detail — the
reframing from Q1 to Q2, the 363-race soft null, the 4x sample expansion to 1,481 races that
pushed the result to significance, the win-pool betting simulation, and the quinella/Harville
extension — is already written up in **`Day7_Q2_Overshoot_Context.md`** in this project, so
it isn't duplicated here. Short summary to close the loop:

- **The idea:** late betting money is directionally smart (drift alone predicts wins), but
  once you condition on the final odds already reflecting most of that, does the *remaining*
  drift signal that the final price overshot?
- **Answer: yes, genuinely.** After expanding the sample 4x (363 → 1,481 races, made possible
  because this test doesn't need the fundamental model or its distance filter), the overshoot
  effect became statistically significant (drift coefficient -0.084, z = -2.20, confidence
  interval excludes zero) and confirmed with a second, independent drift measure.
- **But it failed the economic-significance test — this is the "how we failed to show
  economic significance" part:** the actual out-of-sample betting simulation showed the edge
  is about 8% in odds terms, while the win-pool takeout (house cut) is 20% and the quinella
  exotic pool's takeout is 26.7%. An edge less than half the size of the fee cannot turn a
  profit no matter how you size your bets. Win-pool result: -100% ROI on the 14 bets the
  strategy generated, 0% bootstrap chance of profit. Pushed through Harville into the
  quinella pool: the signal *does* carry through and beats the market-price version by about
  4 points, confirming it's real — but the higher 26.7% exotic takeout makes the loss even
  worse (-40.9% ROI, again 0% chance of profit).

**Why this still matters despite losing money:** it's a genuine, reportable
market-microstructure finding — late money is informed on average but slightly overshoots at
the margin — even though it's not a sellable betting product. The two realistic paths left
for finding an actual profitable edge are (1) a lower-takeout bet type where an 8% tilt could
clear the fee, or (2) orthogonal information the odds can't already contain, i.e. Direction 3
(computer vision / trouble-in-running analysis), which remains the highest-ceiling unexplored
source of signal.

---

## Files produced across the full session

**Piece A:** `harville_engine.py`, `test_harville_engine.py`, `build_exotic_outcomes.py`,
`validate_piece_a.py`, `exotic_outcomes.csv`, `piece_a_calibration.csv`,
`piece_a_favorite_bias.csv`, `piece_a_calibration_lambda_fit.csv`

**Piece B:** `build_piece_b_dataset.py`, `run_piece_b.py`, `test_piece_b.py`,
`piece_b_calibration.csv`, `piece_b_logloss.csv`, `piece_b_backtest_by_year.csv`

**Direction 1 / Q1:** folded into the early-odds ladder tests referenced in
`Day7_Q2_Overshoot_Context.md` §1-2 (no separate standalone files beyond what's cited there)

**Q2 (see companion file for full list):** `q2_overshoot.py`, `q2_pocket.py`,
`q2_expand.py` / `q2_build.py`, `expanded_panel.csv`, `q2_betsim.py`, `q2_exotic.py`

## Full report documents already in the project

- `PieceA_Report.md` — full Piece A writeup
- `PieceB_Report.md` — full Piece B writeup
- `Day7_Q2_Overshoot_Context.md` — full Q2 writeup (Direction 1 summary + all Q2 detail)
