# Lucky Engine — Results & Verdict

**Run date:** 2026-07-27
**Question tested:** Can a similarity engine rank dismissed longshot horses so
that the most-similar ones (closest to our historical "Lucky" winners) place
*more often* than their peer group's base rate?

**Verdict: NO. Stop the Lucky tag.** This is the fifth honest null in the
family. Ship **Unlucky** alone. The reasoning below follows the decision rules
in `Lucky_Engine_Execution_Plan.md` §4, which were written down before any
results were seen.

---

## 1. Bottom line in one paragraph

The engine does not sort. On the pre-declared TEST window (2026-03-01 →
2026-07-19), the horses the engine flags as *most* Lucky-like place **less**
often than the average dismissed horse, not more — every definition, every
method, top-10% lift below 1.0. A random shuffle of the scores does just as
well or better. And when we flip the time direction (train on the late window,
test on the early one), the numbers reverse and suddenly look great — which is
the signature of noise, not signal. Three independent stop-conditions from §4
all fire. There is no version of this result that supports shipping a Lucky
tag.

---

## 2. What "lift" and "ratio" mean here (plain language)

Two numbers, answering two different questions:

- **lift** = (place rate of a tier) ÷ (base place rate of that eligible pool).
  `lift > 1` would mean "these horses place more than a typical dismissed
  horse." This is the minimum bar for a *content* product.
- **ratio** = (actual place rate) ÷ (odds-implied place rate). This controls
  for price — it asks whether the horses beat *the market's own expectation*,
  not just their peer average. Much stronger bar, not required to ship.

The **base rate is the number to beat** — roughly 6–9% depending on definition,
not the 0.25% figure from the old narrow definition.

---

## 3. Setup actually run

- **Data rebuilt from raw** (Friday's working pickles weren't saved):
  `surge_rows` reproduced **exactly** (20,044 rows / 1,894 races). `fund_p`
  retrained from the no-distance-limit 10-variable fundamental model on
  2008–2021 and scored on 2022–2026. Confidence check: the joined analysis
  scope came to **1,880 races — an exact match** to the day-8 overlap figure,
  and the held-out fundamental pseudo-R² (~0.14) matches day 8's ~0.1254. The
  fund_p axis is faithful. (Reproduction caveat: retrained model, so individual
  fund_p values may differ by a hair from Friday's — this cannot change the
  verdict, which fails by a wide margin on multiple independent tests.)
- **Analysis table:** 18,706 horse-starts, 1,880 races. BUILD = 1,195 races
  (through 2026-02-28), TEST = 685 races (2026-03-01 →). Join rate 93.3% —
  well above the §3.1 gate of ~1,200 races.
- **Fingerprint (5 features, all knowable 25 min pre-post):** `ln(odds_25)`,
  `rank_25`, `exp_rank_in_race`, `fund_p`, `n_starters`. No outcome leakage.
- **Definitions** (all clear the §1 ≥100 BUILD-reference gate):

  | ID | Definition | BUILD refs | k (=√refs) | TEST base rate |
  |---|---|---|---|---|
  | D1 | bottom 20% expert, placed | 125 | 11 | 6.41% |
  | D2 | bottom 33% expert, placed | 298 | 17 | 8.65% |
  | D3 | bottom 33% + final odds ≥20, placed | 258 | 16 | 7.32% |

- **Methods:** M1 Mahalanobis-to-centroid, M2 kNN mean-distance, M0 random
  shuffle (the sanity floor).

---

## 4. The actual test — TEST window, top-10% tier (the primary metric)

| Definition | M1 lift | M2 lift | **M0 lift (random)** | M1 ratio | M2 ratio |
|---|---|---|---|---|---|
| D1 | 0.81 | 0.67 | 0.94 | 0.66 | 0.58 |
| D2 | 0.74 | 0.80 | 0.63* | 0.69 | 0.80 |
| D3 | 0.79 | 0.94 | 1.08 | 0.65 | 0.80 |

*Every real-method lift is below 1.0.* The most-similar horses place **less**
than the peer average. Ratios sit at 0.58–0.94, all below 1.0 with bootstrap
95% CIs that include or fall below 1.0 — no evidence of beating the market
either.

The starred M0 (0.63) is one random seed; the honest comparison is the seed
average (see §5), where random *beats* the real methods.

---

## 5. Why it's a stop — the three §4 conditions, each fired independently

**(a) Top-10% lift ≤ 1.1 on TEST.** It's not just below 1.1 — every
definition × method is below **1.0**. The engine points at horses that place
less than their peers.

**(b) M0 (random) performs comparably or better.** Averaging the random
shuffle over 20 seeds:

| Definition | M1 | M2 | M0 random (mean over 20 seeds) |
|---|---|---|---|
| D1 | 0.81 | 0.67 | **0.92** |
| D2 | 0.74 | 0.80 | **1.03** |
| D3 | 0.79 | 0.94 | **1.08** |

Random assignment does **as well or better** than the actual similarity
methods. By definition, the engine is sorting nothing.

**(c) Results flip under the §3.6 stability swap.** Training on the late window
and testing on the early one reverses the sign completely:

| Definition | Primary (fit early → test late) | Swapped (fit late → test early) |
|---|---|---|
| D2 M1 top-10% lift | 0.74 | **1.48** |
| D3 M1 top-10% lift | 0.79 | **1.32** |

A combination that loses badly in one direction and wins big in the other is
noise. The plan anticipated exactly this trap and pre-committed to calling it
noise regardless of how good the winning number looks. (D1 couldn't even be
tested swapped — too few late-window references.)

Any one of these three would be enough to stop. All three fired.

---

## 6. What the engine actually latched onto (mechanism)

The horses scored "most Lucky-like" have mean final odds around **54-to-1** —
the engine is pulling toward the very longest-priced, least-supported horses in
the pool. Those place *less*, not more. This echoes the day-8 SURGE finding:
early longshot patterns tend to capture *early money the smart money later
abandoned* (odds drift out toward post), not hidden accumulation. The
similarity math faithfully found that group — and that group is a loser, not a
Lucky. There was never a stable "Lucky profile" in the 25-min-pre-post features
for the engine to point at.

The §2.1 shape check found the references split into two roughly equal blobs
(centroid separation ~1.8–2.3 sd), so a single-centroid Mahalanobis was always
going to be a poor fit — but kNN, which handles that, did no better. The
problem isn't the method; it's that there's no signal.

---

## 7. Product recommendation

- **Ship Unlucky alone.** It remains the proven tag: experts-like × stats-worse,
  ratio 0.950, tight CI, ~15,000 well-powered references, fires on horses
  customers actually care about. It carries the product.
- **Do not ship a Lucky tag in any form** — not as a probability, not as an
  S/A/B/C resemblance tier. The resemblance claim ("closer to past Luckys than
  X% of horses") would be *technically* computable, but it would be pointing
  customers at horses that place *below* the dismissed-horse average. Shipping
  it would be selling a signal we have tested and shown to be absent.
- **Log Lucky as the fifth honest null.** The hypothesis has now been specified
  five ways (SURGE rank → expert_score → DRIFT interaction → archetype grid →
  similarity engine) and returned null each time. Per §4, the answer is no, and
  no means no — this is not an invitation to a sixth re-spec.

One honest door is still open but it is **not** this product: DRIFT
(25분→2분 odds movement) is now computable because `early_odds_5point.csv` is
present (day 8 had it blocked). That's a genuinely different feature, not a
sixth re-spec of the same one. Worth a separate, small scoped test later — but
it does not change today's verdict.

---

## 8. Deliverables

- `lucky_build.py` — rebuilds surge_rows + fund_p, joins, BUILD/TEST split, join-rate gate
- `lucky_engine.py` — M0 / M1 / M2 scoring functions
- `lucky_evaluate.py` — tier tables, lift, price-controlled ratio, bootstrap CIs, §3.5 filter robustness, §3.6 stability swap
- `lucky_results.json` — full numeric results for every cell
- `surge_rows.pkl`, `analysis_table.pkl` — regenerated data inputs

**Standing lesson reinforced:** a clean null is a legitimate deliverable, but it
is not a product. This one is a null. Say so plainly — done.
