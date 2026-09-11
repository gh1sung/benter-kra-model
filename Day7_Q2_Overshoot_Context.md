# Day 7 — Q2 Overshoot: Context & Findings

> Follows Direction 1 (Q1 early-odds replacement), which came back **null**. This session pivoted
> to **Q2 (overshoot correction)** and carried it all the way from hypothesis → statistically
> significant finding → betting-simulation verdict. Read this as the standalone handoff for Day 7.

## 0. The verdict, upfront

**The final win odds overshoot by a real, measurable amount — but far too little to bet through the takeout.**

- Conditional on the final odds, the late-money drift earns a **negative, statistically significant**
  coefficient (overshoot direction): horses backed hard late win *slightly less* than their closing
  price implies.
- The effect only became significant after **expanding the sample 4x** (363 → 1,481 races), which was
  possible *because Q2 does not need the fundamental model* and so the distance filter could be dropped.
- A full out-of-sample **betting simulation** on the **win pool (단승식)** shows the edge (~8% in odds
  terms) is **less than half the 20% takeout**. Strategy ROI = **−100% on 14 bets**; **0% bootstrap
  chance of profit**.
- Tested on the **exotic pool (복승식 / quinella)** too: the correction *does* carry through Harville and
  beats the market-probability version by ~4 points, **confirming the signal is real** — but the exotic
  takeout is **26.7%** (higher than the win pool), so ROI is **−40.9%**, again **0% chance of profit**.
- **Bottom line:** a genuine market-microstructure result (late money is informed on average but
  marginally overshoots), **not a sellable product** on either the win pool or the quinella pool.

## 1. Where we started — the three fundamental-model nulls

Across Stage 2 (final win odds), Piece B (복승 exotic pool), and Direction 1 / Q1 (early win odds), the
**fundamental model** (10 horse-stat variables: AVESPRAT, LSPEDRAT, LIFE_PCT_WIN, W_PER_RACE,
JOCK_PCT_WIN, JOCK_NUM_WIN, WEIGHT, POSTPOS, NEWDIST, CAREER_STARTS; ridge λ=100) added **no orthogonal
signal** beyond the market odds. Its coefficient sat near zero (~0.12) every time.

**Interpretation:** the market's odds already contain everything the horse-stats model knows. You cannot
beat the crowd by knowing *more about the horses*. More variables of the same (public) kind are very
unlikely to help — they are duplicates of information already priced in. New signal, if any, must be
*orthogonal* to the odds (e.g., Direction 3 computer-vision / trouble-in-running).

## 2. Q1 vs Q2 — the reframing

- **Q1 (roadmap):** given only early odds + the fundamental model (final odds hidden), can you beat the
  final odds? → **Null.** Early odds cannot beat the close.
- **Q1's mechanistic detail:** the drift *alone* had coefficient **+0.63** — horses backed late win
  *more* often (late money is informed / momentum). This measured drift **without conditioning on the
  final odds.**
- **Q2 (this session):** *keep* the final odds, add the drift on top, and ask whether the drift signals
  the final number **overshot**. This is the sharper, sellable test — "a better estimate than the
  public's own final number."

**Key realization:** Q2 had **never actually been run.** The Q1 ladder only ever tested final-odds-alone
(M0) or early-odds-alone (E-models). No model combined final odds + drift. Q2 is also **odds-only** — it
does **not** use the fundamental model (drop `f_i`).

**Why the sign flips (positive → negative).** Late money heads the right direction on average (drift
alone = +0.63), but it overshoots the destination. You can only see the overshoot once you *condition on
the final odds* (hand the model the closing price, then look at what the drift adds). What's left is the
residual — the part of the late move the final price doesn't justify — and that residual is **negative**.
Both are true at once: smart in direction, overshoots at the margin.

## 3. Q2 on the original panel (363 races) — soft null, right direction

Conditional logit (Benter-style within-race softmax), features `ln(π_final)` + drift:

| Test | drift coef | z | 95% CI | OOS |
|---|---|---|---|---|
| Q1 (drift alone, no final odds) | **+0.63** | strong + | — | wrong direction |
| Q2 final + DRIFT_close | **−0.12** | −1.64 | [−0.27, +0.02] (includes 0) | *hurt* |

The sign flipped to the **overshoot direction**, but was **not significant** at n=363, and adding drift
*worsened* out-of-sample prediction. A **pocket test** (extreme late movers) found nothing: top-decile
late-inflow horses won 12.1% vs the 11.8% their final odds imply — dead on, no fadeable tail. Read at
this stage: promising but underpowered.

## 4. The expansion — 363 → 1,481 races (the decisive move)

**Logic:** the original 363-race panel was capped by the **1600–2000m distance filter**, which exists
only to serve the fundamental model. Since Q2 doesn't use that model, the filter can be dropped, unlocking
far more races. Ceiling = the **1,956-race early-odds universe** (the final-odds file is a 12,144-race
superset; early odds are the binding constraint).

**Blocker resolved:** winner labels (`is_win`) previously entered only via the fundamental-filtered
`window_fi.csv`. Rebuilt them directly from the **race-results file** (`rank == 1`), which also carries
distance/going/age — so the panel could be rebuilt from scratch with **no** fundamental filter.

**Validation (trust check):** re-imposing the original filters (1600–2000m, going ∈ {건,양}, age ≥ 3)
reproduced **343 races** (≈ the original 363) with the same coefficients — confirming the from-scratch
builder matches the existing pipeline before trusting the expanded numbers.

**Expanded result (1,481 races, ~4x):**

| | 363 races | **1,481 races** |
|---|---|---|
| DRIFT_close coef | −0.12 | **−0.084** |
| z-score | −1.64 (n.s.) | **−2.20 (significant)** |
| Bootstrap 95% CI | [−0.27, +0.02] | **[−0.155, −0.003] (excludes 0)** |
| Bootstrap % negative | 94.6% | **97.5%** |
| Out-of-sample | hurt | **marginally helps (−0.0011/race)** |

The effect was **always there** (−0.12 → −0.084); 363 races was simply too few to separate it from noise.
4x the data shrank the error bars until it crossed significance — a **power** problem, not a wrong idea.

**Not a math artifact:** the cleaner drift measure `DRIFT(25→2min)` — which shares no term with the final
odds — gives −0.074, z = −1.93. Essentially identical, so the signal is genuine.

## 5. The betting simulation — is the small signal profitable?

Out-of-sample (5-fold), EV rule: bet 1 unit on any horse with `EV = p_model × O − 1 > threshold`, using
**real final dividends** `O` (post-takeout, so the fee is charged automatically).

**Sanity checks (all passed):**
- Implied **takeout ≈ 20.0%** (pool overround = 1.25).
- **Market model (M0) placed 0 bets** — every horse is negative-EV by exactly the takeout (efficient market).
- **Blind betting everything = −26.8% ROI** (≈ the takeout drag).

**Q2 drift-corrected strategy:**

| Strategy | Bets (of 1,481 races) | Hit rate | OOS ROI |
|---|---|---|---|
| Market (M0) | 0 | — | no +EV bets |
| **Q2 drift-corrected (EV>0)** | **14** | **0%** | **−100%** |
| Blind (bet all) | 15,845 | — | −26.8% |

Bootstrap (2,000 reps): **P(ROI > 0) = 0%.**

**Why it fails, in one line:** edge ≈ **8%** (from the −0.084 log-odds tilt) vs **20%** takeout. The edge
is less than half the fee. Like an 8%-off coupon at a store with a 20% entry fee. No bet sizing (Kelly,
etc.) changes the sign of a negative expected value.

## 6. Extending the test to the exotic pool (복승식 / quinella)

Everything above is the **win pool (단승식)**. Because exotic bets combine win probabilities *nonlinearly*
(and exotic pools are often less efficient), a small win-side bias could in principle be amplified. Piece B
had already tested 복승 with *market* win-odds (−28.6% ROI) but **never with the overshoot-corrected
probabilities** — so this was genuinely untested.

**Method:** feed the OOS win probabilities (market M0 vs Q2-corrected) through the **Harville** engine to
get quinella-pair probabilities `P(i,j finish 1–2) = pᵢpⱼ/(1−pᵢ) + pⱼpᵢ/(1−pⱼ)`; bet any pair with
`EV = P × dividend − 1 > 0`; settle on the actual top-2 from the results file. **1,479 races matched.**
Dividends use the **2-minute 복승 snapshot** as a proxy for the settled payout (see caveat).

| Strategy (quinella, out-of-sample) | Bets | ROI |
|---|---|---|
| Blind (every pair) | 98,138 | −35.2% |
| Market win-probs → Harville (EV>0) | 6,287 | **−44.6%** |
| **Q2 overshoot-corrected → Harville (EV>0)** | 6,491 | **−40.9%** |

Bootstrap (Q2, EV>0): **P(ROI > 0) = 0%**, 95% CI [−53.8%, −26.5%].

**Read:** two things are true at once. (1) The signal is **real and propagates** — the corrected
probabilities beat the market version by **~3.7 points** (−44.6% → −40.9%), with more bets and more hits,
consistent with the win-pool finding. (2) Exotics make the economics **worse, not better**: the 복승
takeout is **26.7%** (overround 1.364) vs the win pool's 20%, and the ~4 points the correction adds are
outweighed by the ~7 extra points of takeout plus much higher combination variance. Net −41%, zero chance
of profit. The hoped-for nonlinear amplification loses to the higher fee.

**Caveat:** used 2-min quinella odds as a proxy for the settled dividend, because `exotic_odds_5yr.csv`
was not in the uploads. A definitive run would use settled dividends — but the −41% margin (CI never
within 26 points of zero) is far too deep for a small proxy error to flip.

## 7. What this closes, and what's left

- **Closes the price-timing lever on both pools.** Final odds (Stage 2), 복승 exotic with market probs
  (Piece B), early odds (Q1), the overshoot correction on the win pool (Q2), and now the overshoot
  correction pushed through Harville into the 복승 quinella pool all say the same thing: the Korean market
  is efficiently priced against price-derived and fundamental challengers. Late money is informed and only
  marginally overshoots — not enough to arbitrage past a 20% win / 27% exotic takeout.
- **The reportable finding is real (even though negative for betting):** *late money is informed on
  average but overshoots at the margin by a detectable amount.* A genuine market-microstructure result.
- **Only realistic paths to an actual edge from here:**
  1. A **lower-takeout** bet type / market where an ~8% tilt could clear the fee.
  2. **Orthogonal information** — Direction 3 (computer vision / trouble-in-running), the parked
     highest-ceiling source of signal the odds cannot already contain.

## 8. Data used

| File | Role | Coverage |
|---|---|---|
| `modeling_panel.csv` | original fundamental-filtered panel | 363 races |
| `win_odds_5yr.csv` | final win odds / dividends (benchmark + win payouts) | 12,144 races |
| `early_odds_5point.csv` | early snapshots (25/15/10/6/2 min) → LEVEL, DRIFT; also carries 복승/쌍승/복연승 odds (used 2-min 복승 as exotic-payout proxy) | 1,956 races (the cap) |
| `race_info_..._202607200918.csv` | race results (`rank`) → winner + top-2 labels, distance/going/age | full history |

*Not available this session:* `exotic_odds_5yr.csv` (settled exotic dividends) — the exotic test used the
2-min 복승 snapshot as a proxy instead.

## 9. Files produced this session

- `q2_overshoot.py` — Q2 conditional-logit test on the original 363-race panel (coef, SE, CV, bootstrap).
- `q2_pocket.py` — extreme-late-mover / nonlinearity pocket test (found nothing).
- `q2_expand.py` / `q2_build.py` — from-scratch panel rebuild without the distance filter (+ validation).
- `expanded_panel.csv` — **1,481 races, 15,845 horses** (the Q2 working dataset).
- `q2_betsim.py` — out-of-sample **win-pool (단승식)** betting simulation + ROI bootstrap.
- `q2_exotic.py` — out-of-sample **quinella (복승식)** Harville betting simulation + ROI bootstrap.

## 10. One-paragraph summary (for a standup)

We had three nulls showing the fundamental model adds nothing the market odds don't already contain. We
pivoted from "do we know more than the crowd" to "does the crowd make a predictable *mistake*" — the
overshoot hypothesis: horses backed hard late are pushed too short. Testing it properly (conditioning on
the final odds, which had never been done) showed a real overshoot effect that only reached statistical
significance after we quadrupled the sample by dropping the fundamental-model-only distance filter
(363 → 1,481 races; drift coef −0.084, z = −2.20, CI excludes zero). But a full betting simulation proved
the win-pool edge (~8%) is less than half the 20% takeout, so it loses money (ROI −100% on the 14 bets it
generates; 0% bootstrap chance of profit). We also pushed the corrected probabilities into the 복승
quinella pool via Harville: the signal genuinely propagates (it beats the market-probability version by
~4 points), but the 27% exotic takeout buries it even deeper (ROI −41%, 0% chance of profit). Verdict: a
real market-microstructure finding on both pools, not a product. The remaining edges live in lower-takeout
markets or orthogonal data (Direction 3, computer vision).
