# Day 1 Context: Benter Model — Korean Racing Market Adaptation

**Project window:** 4 weeks (internship at [data partner])
**Core question:** Can William Benter's two-stage fundamental-model + public-odds combination framework (Benter, 1994) be meaningfully adapted to the Korean racing market (KRA), and is it worth pursuing as a research project?

---

## 1. The Benter Model — What It Is

Benter's 1994 paper ("Computer Based Horse Race Handicapping and Wagering Systems") documents a real, profitable computerized betting operation run in Hong Kong for 5 years. The core methodology:

### Stage 1 — Fundamental handicapping model
- Each horse gets a set of weighted factors (recent form, jockey/trainer stats, weight, distance/surface preference, days since last race, etc.) combined into a single score.
- Scores are converted into win probabilities using a **multinomial logit (softmax) model**:

  ```
  P(horse i wins) = exp(score_i) / Σ exp(score_j)  for all horses j in the race
  ```

- This guarantees probabilities are positive and sum to 1 across the race (mutually exclusive outcomes — exactly one winner).
- Weights are fit via **maximum likelihood estimation** on historical race data, validated using **out-of-sample / holdout testing** to avoid overfitting.

### The bias problem
- The raw fundamental model's probabilities, when they disagree with the public's odds, are systematically overconfident — actual outcomes track closer to the public's estimate than the model's own estimate.
- This means the model's raw probabilities **cannot be used directly** to estimate betting advantage.

### Stage 2 — Combining model with public odds
A second, simpler logit model blends the fundamental model's output with the public's implied probability:

```
c_i = exp(α·f_i + β·π_i) / Σ exp(α·f_j + β·π_j)
```

- `f_i` = log of fundamental model's probability for horse i
- `π_i` = log of public's implied probability (from betting odds)
- `α`, `β` = weights (fit via maximum likelihood) representing the relative trustworthiness of the model vs. the public

### Key metric — ΔR²
- **Pseudo-R²**: `R² = 1 − L(model)/L(random guessing)` — measures predictive power (0 = no better than random, 1 = perfect).
- **ΔR² = R²(combined model) − R²(public alone)** — measures how much *incremental* information the fundamental model adds beyond what the public already knows.
- This is the real test of whether a model is worth anything. A standalone model can look accurate but still be worthless if it adds nothing over the public (this is exactly what happened with a "tipster model" comparison in the original paper — looked similarly predictive standalone, but added ~nothing once combined with public odds, while Benter's fundamental model did add real value).

### Betting strategy
- **Kelly criterion**: `K = advantage / (dividend − 1)` — fraction of bankroll to wager to maximize long-run growth. Full Kelly is too risky in practice (overestimating edge by 2x causes negative growth); Benter used **fractional Kelly** (1/2 to 1/3 of the full recommendation).
- **Exotic bets** (quinella, trifecta, etc.) offer disproportionately higher edges than win bets because small individual edges multiply when combined across multiple horses.
- **Harville formula** estimates probabilities for multi-horse-order bets but is itself biased (underestimates randomness of 2nd/3rd place); Benter corrects this with two additional fitted parameters (γ, δ).

### Real-world results
- ~10 years of man-effort (5 to find an edge, 5 more to reach high profitability).
- 4 of 5 seasons profitable; one losing season (~20% of capital lost).
- Wealth grew ~40x (log(wealth/initial) went from 0 to ~3.7) over ~2,500 races bet across 5 years.
- HK pool sizes were >USD $10M per race — this scale was central to making the edge economically meaningful.

---

## 2. Korean Market (KRA) — Structural Facts

| Factor | Korea (KRA) | Hong Kong (Benter's market) |
|---|---|---|
| Tracks | Seoul (Gwacheon), Busan; Jeju (ponies, separate) | Sha Tin, Happy Valley |
| Surface | **100% dirt/sand** — no turf split | Turf + dirt (surface is a modeling variable) |
| Population | Closed, mostly domestic-bred, KRA's own (non-international) rating system | Closed, but larger, internationally-recognized ratings |
| Field size | Min 7, mean ~11, max 16 | Similar (~12–14 typical) |
| Bet types | Win, place, quinella, exacta, quinella place, trio | Win, place, quinella, exacta, trio, etc. |
| Takeout | 20% (win/place), 26% (other types) | ~19% (in Benter's era) |
| **Per-ticket cap (offline)** | **100,000 KRW max per single bet** | No cap (subject to pool-size self-limiting) |
| **Per-ticket cap (online)** | **50,000 KRW per game, 750,000 KRW per day** | N/A |
| Online betting | Legalized June 2024 (Derby-on app), very new, capped and restricted | N/A |
| Typical pool size | Much smaller than HK (not >$10M/race) | >USD $10M/race turnover |
| Legal structure | KRA sole legal monopoly; private/offshore betting is illegal | Legal bookmaker/pool system |

### Structural advantages for Korea (favor modeling)
- **All-dirt tracks** eliminate the turf/dirt data-split problem — every past race is directly comparable, denser and cleaner training data.
- **Closed population, arguably more closed than HK** — fewer horses, more repeat matchups, richer relative-ability data.
- **Standardized, single governing body** (KRA) publishing uniform race data.

### Structural disadvantages for Korea (hurt profitability)
- **Smaller pools** → smaller absolute profit for the same % edge (profit scales with pool size, and pool size is the binding ceiling in HK — but Korea never even reaches that ceiling).
- **Higher takeout** (20–26% vs ~19%) → higher hurdle before any bet becomes +EV.
- **Betting caps are the actual binding constraint**, not pool size. Illustrative calculation (rough, order-of-magnitude):
  - Online channel (750K KRW/day cap), 5–15% edge, ~100 race days/year → **~$2,800–$8,300/year** expected profit.
  - Offline (100K KRW/ticket), 50–100 max-tickets/day, 5–15% edge → **~$18,500–$110,000/year** expected profit (requires physically buying dozens of max-tickets per race day).
- **To match HK-scale profit, a Korean operation would need to find and correctly bet on ~10x more distinct pools/races**, which increases variance, dilutes average edge quality (forced into lower-confidence bets), and risks moving smaller markets faster (harder to stay hidden).
- The cap that (hypothesized) makes the public "weak"/exploitable is the same cap that makes it not worth a professional's time to exploit — a self-stabilizing loop.

---

## 3. The "Weak Public" Paradox — Resolved

**The puzzle:** the betting cap discourages professional/sharp money, which could mean (1) the public's odds are a worse *input* to fold into the model, but also (2) the public is a weaker *benchmark* to beat — seemingly contradictory.

**Resolution:** These don't cancel — they mostly point the same direction.
- If the Korean public is genuinely weak, the model's fitted **β (public weight) will simply be lower automatically** — the combined model self-corrects and doesn't lean heavily on a bad input.
- A weak public as a *benchmark* is pure upside: lower public R² is easier to beat, and mispricings are larger.
- **Caveat:** "weak" is ambiguous. It could mean *exploitable random error* (good — a soft market, more amateur money) OR it could mean *hidden information the model can't see* (bad — insider knowledge, dishonest racing, favorite-longshot bias). Benter explicitly flags dishonest racing and insider information as things that sink fundamental models regardless of how "soft" the public looks. **This is an empirical question that can only be answered by building the model and testing ΔR² on real Korean data — not by armchair reasoning.**

---

## 4. Prior Art in Korea — What's Already Been Done

### Academic research found
- **최혜민 et al. (2015)**, "서울 경마 경기 우승마 예측 모형 연구" (Ewha Womans University Statistics Dept.), *응용통계연구* vol. 28. Used KRA data (race results, horse/jockey/trainer info) with linear regression, random forest, and logistic regression. Found horse's own past win record and jockey's past win record were the strongest predictors. Backtested on 1 month of holdout data across win/place/trio bets — reported **positive returns across all three model types**, with no major difference between models.
- **정준형 et al. (2024)**, "Learning-to-rank 기법을 활용한 서울 경마경기 순위 예측", same journal. Used pairwise learning-to-rank methods (RankNet, LambdaMART via XGBoost/LightGBM/CatBoost Rankers) vs. pointwise (linear regression, random forest). Pairwise models outperformed pointwise across the board; **CatBoost Ranker was the best performer**.
- Related Korean research exists on **경륜** (keirin/velodrome cycling) and **경정** (motorboat racing) — same legalized-gambling ecosystem, similar ML methods, Ewha and Soongsil University groups.

### The gap
**None of the found Korean academic work performs Benter's specific second-stage bias-correction step** (combining the fundamental model with public odds via a second logit regression, measuring ΔR²). Existing work evaluates models in isolation, not against the public benchmark. **This is a genuine, real gap in the published literature** — a legitimate, well-scoped angle for a short research project.

### What Korean bettors actually did to route around the caps
No evidence of a legal, Benter-style professional syndicate operating profitably in Korea. Instead:
- **September 2025**: Seoul police busted an illegal offshore betting ring (~₩170 billion / ~$121M in wagers processed) that illegally streamed KRA race footage to an uncapped site relocated to Vietnam to evade jurisdiction. No betting limits — some single bets were up to 30 million KRW (~$21,000), 200x+ the legal cap. 17,795 registered users; 140 charged with gambling violations.
- A similar case was prosecuted in 2016–2018.
- **Interpretation:** This is strong real-world evidence that the betting cap — not modeling difficulty — is the actual binding constraint on making real money in the Korean market. People who wanted scale went around the cap illegally rather than trying to out-model a soft public within the cap.

---

## 5. Decision Framework — How to Know If This Is Worth Pursuing

### Two separate bars (don't conflate them)
1. **Worth it as a research project** — almost always clearable in 4 weeks, *even with a null result*. A rigorous "no exploitable edge found" is a real, defensible finding, not a failure.
2. **Worth it as a profit-making venture** — much higher bar, gated hard by the caps (see Section 2). This bar should not be the internship's success criterion.

### Gated decision process (time-boxed)

**Gate 0 — Data feasibility (days 1–2, hard stop)**
- Can historical pre-race public odds (not just results) be obtained for past KRA races?
- **This is binary.** Without historical π_i (public implied probabilities), the two-stage combination cannot be built at all — only a standalone model (already done by Ewha group) is possible.
- If this fails: pivot immediately (e.g., to the pairwise learning-to-rank gap instead) — do not discover this in week 3.

**Gate 1 — Baseline fundamental model (days 3–10)**
- Build a simple model (5–10 factors: recent form, jockey win rate, distance/weight, days since last race) using the logit/softmax approach.
- Hold out unseen races. Compute out-of-sample pseudo-R².

**Gate 2 — Measure how "weak" the Korean public actually is**
- Compute the public's own pseudo-R² (à la Benter's Table 1). Directly tests the "weak public" hypothesis.
- If public R² is already well-calibrated (tight correspondence between implied and actual win frequencies) → evidence against easy exploitability.

**Gate 3 — ΔR² (the real go/no-go signal)**
- Run the combined two-stage model, compute ΔR² = R²(combined) − R²(public).
- **ΔR² ≈ 0 or negative** → stop. Write up as a clean, legitimate negative result.
- **ΔR² meaningfully positive** (benchmark: Benter's own HK result was 0.0178) → proceed to Gate 4.

**Gate 4 — Economic significance check**
- Translate the statistical edge into rough expected profit using the pool-size/cap math from Section 2.
- A statistically real edge can still net out to economically trivial money under Korea's caps — that's not a modeling failure, it's confirmation of the structural constraint, and is itself a complete, quantified finding (both halves of the phenomenon proven, not assumed).

### Timeline discipline
- End of week 1: Gates 0 and 1 cleared.
- End of week 2: Gates 2 and 3 cleared (have a real ΔR² number, positive or negative).
- Start of week 3: if no real ΔR² number exists yet, treat as a scope failure and pivot to a different, better-scoped question (e.g., the learning-to-rank gap) rather than continuing indefinitely.

---

## 6. Open Threads / Next Steps

- [ ] Confirm whether KRA publishes or makes scrapable historical pre-race odds (Gate 0) — top priority.
- [ ] Identify the specific factor set for a first-pass Korean fundamental model (start with what the Ewha 2015 paper already found predictive: horse's own past win record, jockey's past win record).
- [ ] Consider the pairwise learning-to-rank angle (2024 Ewha paper) as a backup/parallel direction if Gate 0 fails.
- [ ] Keep the illegal-offshore-betting finding as *context only* — not a direction to pursue, but useful supporting evidence for the "caps are the real constraint" narrative when presenting findings to the team.
- [ ] Frame results for seniors using the "tried before, believed it didn't work, revisit with new data/tools" narrative — non-confrontational, uses their institutional memory rather than positioning against it.

---

*Compiled from a research conversation working through Benter (1994), "Computer Based Horse Race Handicapping and Wagering Systems," and its applicability to the Korean Racing Authority (KRA) market.*
