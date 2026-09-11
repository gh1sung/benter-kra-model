# Step 0 Report — 사전인기(expert dismissal) vs. final-odds-implied placement

**Scope run:** 서울 + 부산, 5-year window (2021-07 → 2026-07), 66,609 horse-starts
joined (expert_score × final win odds × race results). Placement rule: 연승식
top-2 for 5–7 starters, top-3 for ≥8. Odds-implied placement via
`harville_engine.py`, λ = 0.8 (the Piece A validated value).

---

## 1. Step 0a finding — the SURGE feature is NOT executable with the data on hand

The whole plan hinges on **25/15/10/6/2-min snapshot odds** to compute `rank_25`
and the SURGE flag. That table is `early_odds_5point.csv` in the Day-7 work.
**It is not present in the available data.** The only odds file here is the
**final** 확정 win odds (`win_odds_5yr.csv`: one row per horse, columns
`date, track, race_no, gate_no, horse_id, odds`, no timepoint column, verified
one row per horse — no snapshots).

So Steps 0a→0b→SURGE cannot be built at all right now. Two things worth noting
for when the snapshot file is reattached:

- The plan's "known risk" is confirmed in the Day-7 notes: `early_odds_5point.csv`
  was **capped at ~1,956 races** (manually copied top-N of the KRA display). That
  is exactly the truncation risk flagged in Step 0a — so even with the file,
  SURGE must be defined as *rank within the recorded set*, never using "absent
  from the 25분전 snapshot" as a signal.
- 1,956 races is a small overlap against this 6,407-race expert scope. Expect the
  is_unranked × SURGE cell to be small — the power caveat in Step 0c-4 will bite.

**What I ran instead:** the part that IS fully executable — the odds-implied
logic of Step 0c applied to the **is_unranked pool as a whole** (expert-dismissed
horses, no early-surge filter). This does not test SURGE, but it characterizes
the pool SURGE would draw from, and it is a clean result on its own.

---

## 2. Definition used and n

- **Group tested:** `is_unranked = 1` — horses that **zero** experts picked.
- **n = 2,407** dismissed horse-starts with complete odds + result (of 2,509 in
  the full table; the rest dropped on the odds/result join, same kind of overlap
  loss as before).
- Pipeline sanity check passed first: across **all** 66,609 horse-starts, actual
  placed = 18,699 vs. odds-implied 18,786, **ratio 0.9954, 95% CI [0.985, 1.006]**
  — straddles 1.0, i.e. the join + Harville engine reproduce the market's own
  placement rate. The test below is measured against a validated baseline.

---

## 3. Naive rate vs. odds-implied ratio (with bootstrap CI)

**Naive (uncorrected — overstates by construction, as warned):**

| group | n | placed% | mean final odds |
|---|---|---|---|
| is_unranked = 1 (dismissed) | 2,407 | **3.03%** | 88.4 |
| is_unranked = 0 (picked) | 64,202 | 28.9% | 24.1 |

Dismissed horses place far less — but that is mostly just because they are
longshots. The real test controls for their own price:

**Odds-implied (the real test), is_unranked = 1:**

| quantity | value |
|---|---|
| actual placed count | 73  (3.03%) |
| odds-implied expected | 149.4  (6.21%) |
| **ratio actual / implied** | **0.489** |
| 95% CI (2,000-rep bootstrap) | **[0.376, 0.602]** |
| CI excludes 1.0? | **Yes** |

Expert-dismissed horses place at **less than half the rate their own final odds
imply.** This is the *opposite* of the hoped-for "undervalued, insider-backed"
tag. Dismissed horses are, if anything, **over**-bet relative to their true
chance — expert dismissal carries real negative information.

---

## 4. Confound checks (Step 0d)

**Favorite/longshot bias (general, all horses).** There is a mild generic
longshot pattern, but it is nowhere near large enough to explain the result:

| final odds | n | actual% | implied% | ratio |
|---|---|---|---|---|
| <2 | 1,884 | 0.795 | 0.861 | 0.92 |
| 5–8 | 8,377 | 0.417 | 0.411 | 1.01 |
| 15–30 | 13,434 | 0.187 | 0.174 | 1.08 |
| 30+ | 20,388 | 0.078 | 0.085 | 0.92 |

The generic longshot ratio bottoms out around **0.92**. The dismissed-horse ratio
is **0.49** — far below the generic effect.

**Odds-matched (the decisive control).** Holding final odds constant, dismissed
horses still place ~half as often as same-odds horses that got ≥1 expert pick:

| final odds band | is_unranked=1 ratio | is_unranked=0 ratio |
|---|---|---|
| 30–50 | 0.68 (n=252) | 1.03 (n=9,091) |
| 50–100 | 0.43 (n=1,387) | 0.85 (n=7,711) |
| 100+ | 0.42 (n=733) | 0.82 (n=1,214) |

So the effect is **specific to expert dismissal, not generic longshot bias.**

**Field size (is_unranked=1).** Underperformance is consistent across field
sizes (ratios 0.44–0.58 in the well-populated 10–12-starter cells); not a
field-size artifact.

**Region.** Robust across both tracks — 서울 ratio 0.52 (CI [0.37, 0.66]),
부산 ratio 0.46 (CI [0.31, 0.62]); both CIs exclude 1.0.

---

## 5. Verdict

**NULL for the intended hypothesis — and in fact a significant negative — for the
is_unranked pool as a whole.** Expert-dismissed horses do not beat, and do not
even match, what their final odds imply; they place at ~0.49× the implied rate,
robust to odds level, field size, and track. 사전인기 dismissal is *informative
beyond the final price*, in the direction that hurts these horses. This sits with
the Q1/Q2/Piece-B/Stage-2 family of honest nulls: the market's final odds are
efficient here too, and dismissal doesn't hide value — it flags weakness.

**Important limit:** this does **not** kill the SURGE hypothesis. SURGE is a
*small, specific subset* of dismissed horses (dismissed AND surging in early
odds). It is possible that the dismissed-but-surging sliver behaves differently
from the dismissed pool overall — that is precisely the untested claim. What this
result does do is **raise the bar:** the pool SURGE fishes in underperforms its
price by half, so SURGE would have to identify a genuinely different
sub-population to show any edge.

---

## 6. Recommended next step

1. **Reattach `early_odds_5point.csv`** (the 25분전 snapshots) — nothing about
   SURGE can proceed without it. Confirm its race coverage against this scope
   first; expect ~1,956 races, so the is_unranked × SURGE cell may fall in the
   underpowered (<150) range the plan flagged.
2. Once joined, define SURGE as **rank within the recorded set only** (never
   absence), per the confirmed truncation.
3. Then run the identical odds-implied ratio + bootstrap machinery from this
   report on the SURGE cell. If n < 150, treat any null as underpowered, not
   disproven (as planned).

*Files: `step0_run.py` (join), `step0_analyze.py` (tests), `Step0_Report.md` (this).*
