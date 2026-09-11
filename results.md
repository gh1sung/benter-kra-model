# results.md — Market-edge test (§3/§4/§5)

The gate (§2) cleared, so we tested whether the low-info signal survives to a **market edge**.
Definition: class cut (senior's literal proposal), primary. Variant compared: baseline 10-var
model (**A**) vs the same model + low-info re-weighting interactions (**re-weighted**, the fix
the gate pointed to — a soft correction, not deletion).

## Setup
- **Odds:** `win_odds_5yr.csv`, joined on (date, region, race_no, gate). 97.7% of window
  horse-rows matched; public implied prob is near-perfectly calibrated (implied 0.14 → 14.5%
  actual win rate, etc.) — the market is efficient, as assumed.
- Stage-1 models trained on pre-window data (2008 → 2021-07). Evaluated on the odds window
  (2021-07 → 2026-07), 7,497 races with full odds coverage.
- Stage-2 blend `log p_final ∝ α·log p_model + β·log p_public`, fit on the first half of the
  window, tested on the second half.

## Model-only, out-of-sample (window)
| | mean log loss |
|---|---|
| baseline model | 2.049 |
| re-weighted model | 2.045 |
| **public odds alone** | **1.853** |

The re-weighting sharpens the standalone model very slightly (consistent with §2.3). But the
**public odds alone crush both models** (1.85 vs 2.05) — the market is far sharper than the
fundamental model on its own.

## Stage-2 blend — the ROI-relevant number (Metric #2)
| variant | α (model) | β (public) | **α/β** | blended test log loss |
|---|---|---|---|---|
| **A baseline** | 0.143 | 0.875 | **0.164** | 1.82821 |
| re-weighted | 0.146 | 0.870 | **0.168** | 1.82830 |
| public only | — | — | — | 1.82896 |

- The blend leans ~86% on the public odds; the model adds only a sliver on top.
- **α/β barely moves (0.164 → 0.168)** — the re-weighting does not change how much the market
  trusts the model.
- Blended log loss is a **statistical tie**: baseline − re-weighted = −0.000092,
  95% CI [−0.00059, +0.00040] (paired race bootstrap). Re-weighting is if anything a hair worse.
- Both blends beat public-only by ~0.0007 nats — negligible.

## Decision (§5, pre-registered)
**α/β unchanged across variants + blended log-loss tie → keep A (baseline).**
Headline: *"sharper maybe, but no market edge."* The market already prices whatever the
low-info re-weighting captures. This closes the question cleanly, consistent with the efficient-
market / closed-Benter frame.

## ROI
Not run as decisive. With blended log loss tied to ~0.0001 nats, any ROI difference is pure
noise at this sample (prior Piece B ran −13% to −41%/yr). Do not decide on it.

## Bottom line
1. The senior's concern is **real but small** in the fundamental model: low-info horses' win-
   record signal is unreliable and a soft re-weight fixes it (statistically significant OOS,
   ~0.3% log loss).
2. It buys **no market edge** — the efficient public odds already contain it.
3. Therefore: **do not exclude** (it would cost ~63% of races for zero market benefit), and a
   shrinkage fix is only worth it if you later want a marginally sharper standalone model for
   non-betting reasons. For the betting pipeline, keep baseline A.
