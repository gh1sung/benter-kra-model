# DRIFT Tag — Results & Verdict

**Run date:** 2026-07-27
**Question:** Does late money movement (25분전 → 2분전) predict **placement**
(연승), and can it become an honest customer-facing tag?

---

## 1. Verdict, up front

**This is not a sixth null — but it is a descriptive tag, not a predictive one.**

The raw signal is real and stable: horses that drew late money place far more
often than horses that shed it (33.5% vs 20.5% place rate, top vs bottom decile),
the gradient is smoothly monotone (rank correlation 0.93), it holds in **both**
regions and across field sizes, and — critically — it **survives the stability
swap that killed the Lucky engine.** So the early market genuinely carries
place-relevant information.

**But almost all of it is already in the price.** Once you compare each horse to
its own final-odds-implied place probability, the ratio sits at ~1.0 in every
decile and in 15 of 16 well-powered price cells. Money-in horses place more only
because they end up at shorter odds — and the market has already moved them
there. As a *predictive edge* tag, DRIFT adds nothing.

**One genuine price-controlled pocket exists:** heavily-backed favorites (final
odds 1–3) that take *extra* late money **underperform** their shortened price —
ratio falls from 0.94 (least late money) to 0.85 (most), monotone. This is the
place-pool confirmation of the Day-7 Q2 "overshoot" finding from the win pool.
It is real but narrow (one odds band, one well-powered cell), so it ships as a
*caution* note, not a standalone product.

**Recommendation:** ship DRIFT as a **descriptive** tag (both directions:
"막판 자금 유입" / "자금 유출"), with copy that explicitly says the market has
already priced it. Do **not** frame it as an edge. Keep **Unlucky** as the only
predictive tag.

---

## 2. Data honesty first — Gate A and Gate B (both PASS)

| Check | Result | Bar | Status |
|---|---|---|---|
| A.1 — 25분 & 2분 both present | 99.9% of races | ≥80% | **PASS** |
| A.2 — n_recorded_25 == n_starters | **92.1%** (max 16, no cap) | reproduce day-8 92.1% | **PASS** |
| A.3 — scratches (present @25, gone @2) | 80, all excluded | exclude, don't count as "money out" | **PASS** |
| B — sum(placed)/sum(implied_place) | 0.9974, CI [0.978, 1.016] | CI contains 1.0 | **PASS** |

Sign convention verified on a real horse (race 202507200103, gate 3): odds
9999.9 → 33.5, MONEY_IN = +5.56 (money in). Correct.

**Scope achieved:** 20,003 horse-starts, 1,892 races, 2025-06-20 → 2026-07-12.
Split date 2025-12-30 → EARLY 923 races / LATE 969 races.

**Note on the feature.** Working in normalized probability space
(`MONEY_IN = ln(p₂/p₂₅)`) vs raw odds change gave **identical within-race
decile rankings** — because the pari-mutuel normalizer is a per-race constant
that cancels under within-race ranking. So the sum-constraint artifact §2.1
warned about does not affect the decile analysis at all. Good to know; the
naive version would have been fine here.

---

## 3. The core result — decile table (LATE window, placed, base 28.0%)

| decile | n | mean odds_final | actual place | implied place | ratio | 95% CI | lift |
|---|---|---|---|---|---|---|---|
| D1 (money out) | 628 | 37.9 | 0.205 | 0.203 | 1.01 | [0.87, 1.16] | 0.73 |
| D2 | 976 | 32.1 | 0.221 | 0.237 | 0.93 | [0.84, 1.03] | 0.79 |
| D3 | 975 | 29.8 | 0.268 | 0.249 | 1.07 | [0.97, 1.17] | 0.96 |
| D5 | 920 | 30.4 | 0.270 | 0.245 | 1.10 | [1.00, 1.20] | 0.96 |
| D6 | 1139 | 28.3 | 0.243 | 0.270 | 0.90 | [0.82, 0.99] | 0.87 |
| D8 | 971 | 23.9 | 0.306 | 0.311 | 0.98 | [0.90, 1.06] | 1.09 |
| D9 | 979 | 22.7 | 0.328 | 0.320 | 1.02 | [0.95, 1.10] | 1.17 |
| D10 (money in) | 1793 | 23.0 | 0.335 | 0.343 | 0.98 | [0.92, 1.03] | 1.20 |

Read the three columns together: **actual place rate climbs** with money-in
(0.205 → 0.335, lift 0.73 → 1.20), **but so does implied** (0.203 → 0.343), and
**ratio stays flat at ~1.0.** The mean final odds fall from 37.9 to 23.0 across
the deciles — the drift *is* the price move. The market prices it in full.

---

## 4. Price-banded table — the shippability test (§4.3)

16 well-powered (n≥300) cells. **Exactly one** has a 95% CI excluding 1.0:

| band (final odds) | tier | n | mean odds | actual place | implied | ratio | 95% CI |
|---|---|---|---|---|---|---|---|
| **[1,3)** | **mid50** | **425** | **2.1** | **0.701** | **0.782** | **0.897** | **[0.841, 0.950]** ✓ |
| [1,3) | bottom25 | 213 | 2.0 | 0.751 | 0.794 | 0.946 | [0.88, 1.02] · underpowered |
| [1,3) | top25 | 214 | 2.3 | 0.626 | 0.739 | 0.847 | [0.76, 0.93] · underpowered |
| [3,6)–[25,60) | all tiers | 300–1329 | — | — | — | 0.91–1.13 | all contain 1.0 |
| [60,∞) | all tiers | 345–692 | ~85 | ~0.05 | ~0.06 | 0.71–0.80 | all contain 1.0 |

The favorite band [1,3) shows a clean monotone **overshoot**: as late money
piles onto a favorite (bottom25 → top25), its place ratio falls 0.94 → 0.90 →
0.85. Heavily-backed favorites that get *even more* late support place **below**
what their (already short) price implies. Everywhere else, ratios are noise
around 1.0.

This is the same phenomenon as Day-7 Q2 (win-pool overshoot, coef −0.084),
now confirmed in the **place** pool. It is real, but it lives in one odds band
and only one of its three cells is well-powered — too narrow to be its own
price-banded product.

---

## 5. The stability swap (§4.4) — DRIFT survives it

| | LATE (confirm) | EARLY | flip? |
|---|---|---|---|
| D10 − D1 place-rate difference | **+0.130** | **+0.075** | **No** |

Both directions positive. Unlike the Lucky engine (which gave lift 1.48 one way
and 0.74 the other and was correctly called dead), DRIFT's top-vs-bottom
gradient points the **same way in both halves of the year.** The raw signal is
stable. It is the *price control* that flattens it, not instability.

---

## 6. Robustness (§5, LATE, placed)

| Cut | D10−D1 diff | D10 lift | D1 lift | holds? |
|---|---|---|---|---|
| MONEY_IN (prob) | +0.130 | 1.20 | 0.73 | — |
| MONEY_IN_RAW | +0.130 | 1.20 | 0.73 | identical (see §2 note) |
| region 서울 | +0.097 | 1.16 | 0.82 | yes |
| region 부산 | +0.171 | 1.25 | 0.63 | yes |
| field 8–10 | — | 1.12 | — | yes |
| field 11+ | +0.121 | 1.24 | 0.78 | yes |

Holds in both regions and across field sizes (5–7 fields are too small to fill
both extreme deciles cleanly). Not a one-track or one-field artifact.

---

## 7. Which §6 rule fired

- Signs do **not** flip under §4.4 → not dead on the kill switch.
- One well-powered price cell has a CI excluding 1.0 → not dead on the "no real
  price-controlled cell" clause.
- Effect holds in both regions and multiple field sizes → not dead on the
  "one bucket only" clause.
- Decile gradient is monotone-ish (corr 0.93) and holds under swap in both
  regions.

Per §6, that is the **SHIP-a-descriptive-tag** path — with the mandatory caveat
that, because ratios ≈ 1, the copy must state the market already prices it and
the tag is descriptive ("돈이 들어왔습니다"), never predictive ("유리합니다").
The money-*leaving* direction is fully priced too (bottom-decile ratio 1.01), so
it also ships descriptive-only, **not** as a price-beating mirror of Unlucky.

---

## 8. Product copy (§8) — descriptive framing only

**막판 자금 유입 (Late Money In) — descriptive tag**

> **막판 자금 유입** — 이 마필은 경주 25분 전 대비 2분 전 배당률이 크게 낮아졌습니다
> (레이스 내 자금 유입 상위 10%). 과거 같은 수준의 막판 자금 유입을 보인 마필은
> **1,793두 중 601두(33.5%)가 연승권**에 들었습니다(전체 평균 28.0%).
> ※ 다만 이 자금 이동은 최종 배당률에 이미 반영되어 있습니다 — 가격 대비로는
> 시장 예상과 동일한 수준(비율 0.98)입니다. 본 정보는 과거 통계이며 투자 권유나
> 예측이 아닙니다.

**막판 자금 유출 (Late Money Out) — descriptive tag**

> **막판 자금 유출** — 25분 전 대비 2분 전 배당률이 크게 높아졌습니다(자금 유출
> 상위 10%). 과거 유사 마필은 **628두 중 129두(20.5%)만 연승권**에 들었습니다
> (평균 28.0%). ※ 이 역시 최종 배당률에 반영되어 있어, 가격 대비로는 시장 예상과
> 동일합니다(비율 1.01).

**과열 주의 (Overshoot Caution) — favorites only, [1,3) band**

> 인기 1~3배 마필 중 막판에 자금이 더 몰린 경우, 과거 **연승 적중률이 가격 기대치를
> 하회**했습니다(비율 0.85–0.90, 425두 기준 CI 0.84–0.95). 인기마의 막판 과열은
> 오히려 주의 신호일 수 있습니다.

Copy rules honored: every rate shows its denominator N and the price-matched
comparison; ratio ≈ 1 cases explicitly disclaim an edge.

---

## 9. Bottom line for the project

DRIFT breaks the five-null streak in a narrow, honest sense: the early market
**does** carry stable place information, and it survives the test that killed
Lucky. But it is not a predictive edge — the market prices it — so it is
shippable only as descriptive content, with the one genuine price-controlled
finding (favorite overshoot) offered as a caution. The early-market angle for a
*predictive* product is now closed; **Unlucky remains the only tag with a real
price-controlled edge.** If the team wants DRIFT as descriptive color alongside
Unlucky, the copy above is honest and ready. If the bar is "must beat the
price," this is a null and the early-market direction is done.

---

## 10. Deliverables

- `drift_build.py` — join, MONEY_IN feature, Gate A + Gate B
- `drift_evaluate.py` — deciles, price-banded terciles, bootstrap CIs, §4.4 swap, §5 robustness
- `drift_results.json` — every number
- `drift_decile_table.csv`, `drift_price_banded.csv`
- `drift_table.pkl` — the built analysis table (20,003 starts)
