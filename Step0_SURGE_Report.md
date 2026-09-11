# Step 0 — SURGE test (사전인기 dismissed × 25분전 early-odds surge)

**Question.** Do horses that **zero experts picked** (`is_unranked = 1`) but were
**popular in the early market** (top-5 by 25분전 win odds) place more often than
their **own final win odds** imply? This is the "insider-backed, crowd-dismissed"
tag the project set out to test. Not trying to beat the market — testing whether
this specific sliver beats its own price.

**Data / method.**
- Scope: the 25분전 snapshot file (`early_odds_5point.csv`) — **1,956 races**,
  서울+부산, 2025-06-20 → 2026-07-19. Joined to expert_score, final win odds
  (`win_odds_5yr`), and results. 20,044 horse-starts after join.
- `rank_25` = popularity rank by 25분전 단승식(win) odds, 1 = shortest. Computed
  **within the recorded set** (never uses absence).
- `SURGE = is_unranked AND rank_25 <= 5` (the plan's starting definition).
- Odds-implied placement from **final** win odds via `harville_engine.py`, λ=0.8.
- Metric = 연승식 placed (top-2 if 5–7 starters, top-3 if ≥8).

---

## Step 0a — snapshot completeness (was the blocker)

**Snapshots are complete, not truncated to a fixed top-N.** Across 1,955 checked
races, `n_recorded == n_starters` in **92.1%**; recorded count runs 6→16 and its
distribution tracks real field sizes (no ceiling). The 5.6% where recorded >
starters is late scratches; the 2.4% shortfall is minor. So the truncation risk
flagged in the plan **does not bite** — SURGE can use rank safely. (I still
defined rank within the recorded set, so even the residual gaps don't matter.)

---

## Step 0b — scope and n

- Overlap scope: **1,955 races / 20,044 horse-starts**.
- `is_unranked = 1` in scope: **770**.
- **SURGE (rank_25 ≤ 5): n = 43.**
- Pipeline sanity: all-horses ratio in this scope = **0.997, CI [0.978, 1.017]** —
  join + engine reproduce the market's own placement rate. Test is against a
  validated baseline.

---

## Step 0c — the core test

**Naive (uncorrected):**

| group | n | placed% | mean 25분 odds | mean final odds |
|---|---|---|---|---|
| SURGE = 1 | 43 | **0.0%** | 13.6 | 78.2 |
| is_unranked & non-surge (rank_25 > 5) | 727 | 2.5% | 158.6 | 84.1 |

**Odds-implied (the real test), SURGE = 1:**

| quantity | value |
|---|---|
| n | 43 |
| actual placed | **0** |
| final-odds-implied placed | **3.0**  (implied rate 7.0%) |
| ratio actual / implied | **0.00** |
| one-sided p (Poisson, H0: ratio=1) | **≈ 0.049** |
| 95% upper bound on placed rate (rule of three) | 0.070 |

Zero of 43 SURGE horses placed, against ~3 expected from their final odds. The
bootstrap CI is degenerate on zero events, so I report the exact zero-event
statistics instead: the result is marginally significant (p≈0.05) **in the
negative direction**, but the sample is **below the plan's n≥150 power floor**.

**Contrast (same scope):**

| group | n | ratio | 95% CI |
|---|---|---|---|
| SURGE (rank_25 ≤ 5) | 43 | 0.00 | (zero events) |
| is_unranked, non-surge | 727 | 0.39 | [0.22, 0.58] |
| all is_unranked | 770 | 0.37 | [0.22, 0.54] |

**Threshold sweep** (loosening rank never rescues it):

| rank_25 ≤ T | n | actual | implied | ratio |
|---|---|---|---|---|
| 3 | 13 | 0 | 1.1 | 0.00 |
| 5 | 43 | 0 | 3.0 | 0.00 |
| 8 | 229 | 3 | 16.2 | 0.19 |

---

## Step 0d — confounds

- **Region:** 서울 (n=23) and 부산 (n=20) both 0 placings; the effect is not a
  single-track artifact.
- **Field size:** SURGE horses cluster in 10–12-horse fields; the non-surge
  dismissed pool in the same fields still runs ratio ~0.39, so the SURGE zero is
  not a field-size artifact.
- **Favorite/longshot bias:** SURGE horses are longshots on final odds (mean 78),
  but generic longshots run ratio ~0.9 and the non-surge dismissed pool runs 0.39
  — SURGE at 0.00 is below both. Not generic longshot bias.

---

## Mechanism worth flagging (changes what "surge" means)

The SURGE horses are short at 25분전 (mean 13.6) but drift **way out** by post
(mean final 78.2) — verified case-by-case (e.g. 8.5→24.9, 4.1→33.0, 7.2→96.9).
So `rank_25 ≤ 5` did **not** capture "insiders keep pouring money in"; it captured
**early popularity that the smart final money then abandoned.** These are
early-money *traps* that fade, which fits the 0/43 conversion. This suggests the
definition may be pointing the wrong way: a surge should probably be measured as
**odds shortening across 25→2분 (drift direction)**, not "already short at 25분."
That is the Day-7 DRIFT variable, and it's the natural refinement if this line is
pursued.

---

## Verdict

**Null / negative — no support for the SURGE hypothesis.** Dismissed-but-early-
popular horses placed 0/43 vs ~3 implied (p≈0.05, negative), worse than the
already-underperforming dismissed pool (0.37). There is **zero hint of a positive
edge.** Caveat per the plan: n=43 is underpowered (<150), so this is a suggestive
negative, not a hard disproof — but the sign is wrong and the point estimate is
the worst of any subgroup. In the project's tier language: **not Tier-1, not
Tier-2.** Sits with the Q1/Q2/Piece-B/Stage-2 family of honest nulls.

## Recommended next step

The definition, not just the result, is the finding here. Before declaring the
early-market angle dead, re-run with SURGE defined as **odds shortening 25분→2분
(DRIFT < 0 / steepening)** rather than "short at 25분전" — that actually encodes
"money coming in late," which is the insider story. If that also nulls at adequate
n, the early-market angle is closed. Everything else (Step 1 logit with the
interaction term, etc.) waits on that, since the current SURGE cell (n=43) can't
carry a logit.

---

*Files: `surge_build.py` (0a check + join), `surge_analyze.py` (tests),
`surge_horses_T5.csv` (the 43 horses), `harville_engine.py` (unchanged, from
Piece A). Prior is_unranked-only run: `step0_run.py`, `step0_analyze.py`,
`Step0_Report.md`.*
