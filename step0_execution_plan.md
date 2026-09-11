# Step 0 Execution Plan — 사전인기 vs 초반 배당 Surge Pattern

## Context (paste this into a new chat first)

[data partner] internship, Korean horse racing. Three prior fundamental-model
projects (Stage 2, Piece B, Q1/Q2 drift) all found the market's **final**
odds are efficient — nothing beats them. New direction: test whether horses
**ignored by expert consensus (사전인기)** but **surging in early market
odds (25분전)** outperform what their **own final odds** imply. Not trying
to beat the market. Trying to find a sellable "high risk, high reward" tag
for horses the crowd dismissed early but insiders may be backing.

Two tables already built and verified:
1. `expert_score_seoul_busan.csv` — 68,932 horse-starts, 6,407 races
   (서울+부산 only, 제주 excluded — no starter data exists for 제주).
   Columns: race_id, horse_num, region, race_date, expert_score
   (5/4/3/2/1 points per rank1-5, summed across ~57-77 usable experts,
   noise/odds-derived "experts" already excluded per 조's list),
   n_picks, is_unranked (1 if zero experts picked the horse — 3.64% of
   all horse-starts, n=2,509, confirmed clean).
2. Realtime odds snapshots (25/15/10/6/2-min pre-race) — same source as
   the Day 7 Q2 drift work. NOT yet joined to the expert_score table.
3. Final win odds (win_odds_5yr.csv) — already in hand from prior work.
4. Race results (rank, top-3 finish) — already in hand from prior work.

**Known risk, unresolved:** realtime odds snapshots may be truncated to
only the top-N horses shown on screen (manually copied from KRA display).
If so, "absent from 25분전 snapshot" is ambiguous (long odds vs. not
recorded) — unlike is_unranked, which is unambiguous. MUST verify before
building the SURGE feature. This is Step 0a below.

---

## Step 0a — Verify realtime odds completeness (do this FIRST, blocks everything else)

For each (race_id, timepoint), count horses recorded vs. actual field size
(from race_info_of_horse or race_info.horse_count).

```sql
SELECT o.race_id, o.timepoint,
       COUNT(DISTINCT o.horse_num) AS n_recorded,
       (SELECT COUNT(*) FROM kra_data.race_info_of_horse r
        WHERE r.race_id = o.race_id) AS n_actual_starters
FROM <realtime_odds_table> o
GROUP BY o.race_id, o.timepoint
LIMIT 50;
```

(Table/column names unconfirmed — DESCRIBE the realtime odds table first,
same discipline as before. Likely lives near win_odds_5yr's source.)

**Decision rule:**
- n_recorded ≈ n_actual_starters consistently → snapshots are complete,
  proceed with SURGE as originally planned (rank-based, using absence
  as a real signal).
- n_recorded is capped at a fixed number (e.g. always ≤8 regardless of
  field size) → truncated. Redefine SURGE using *rank within recorded
  set* only, never using absence as a feature. Flag this finding
  explicitly in any report — it changes what "surge" can mean.
- Also check: does completeness change over the ~1-year history? A
  mid-period change in collection method would need to be controlled for
  or the sample split at that date.

---

## Step 0b — Join expert_score to realtime odds + final odds + results

Build one row per horse-start with:
- `is_unranked` (from expert_score_seoul_busan.csv)
- `expert_score` (continuous, secondary variable)
- `rank_25` = popularity rank at 25분전 (1 = shortest odds)
- `SURGE` = is_unranked AND rank_25 <= 5 (starting definition — loose,
  per the "start loose" principle from prior sessions; tighten only if
  Step 0c shows nothing)
- `odds_final` = final win odds
- `placed` = 연승식 rule: top 2 if starters 5-7, top 3 if starters >=8,
  no 연승식 offered if starters <=4 (exclude those races from placed
  analysis or handle as a separate case)
- `starters` = field size (needed for the placed rule above)

Restrict to 서울+부산, same 6,407-race scope as expert_score table.
Expect some row loss where realtime odds don't cover a given race
(1-year window vs. expert_score's longer history) — report the overlap
count, same as was done for the expert_score/race_info join (Query 17-21
pattern in prior chat).

---

## Step 0c — The core test: naive rate vs. odds-implied rate

**Do NOT stop at the naive comparison.** It will show a large fake lift
by construction (surging horses have short odds; short-odds horses win
more; that's not a finding). Report both, but the second one is the
actual answer.

1. **Naive:** placed% among SURGE=1 horses vs. placed% among
   (is_unranked=1, SURGE=0) horses. Compute and report, but label
   explicitly as "uncorrected, expected to overstate."

2. **Odds-implied (the real test):** for each SURGE=1 horse, compute its
   odds-implied placed probability. Use harville_engine.py (already
   built, from Piece A) to get P(top-2 or top-3) from win odds — same
   method as the Q2 pocket test ("12.1% actual vs 11.8% implied").
   Sum implied probabilities across all SURGE=1 horses → expected count.
   Compare to actual count of SURGE=1 horses that placed.
   Ratio = actual / odds-implied.
   - Ratio ≈ 1.0 → no edge, fully priced. Still possibly useful as a
     Tier-1 product claim (beats 사전인기, doesn't beat the market) —
     say so honestly.
   - Ratio > 1.0, especially with CI excluding 1.0 → genuine signal
     beyond the price. Report the size and the CI.

3. Bootstrap the ratio (2,000 reps, resample horse-starts) for a CI, same
   method as Q2's ROI bootstrap. Do NOT use bootstrapping to inflate
   sample size — only to quantify uncertainty in the ratio itself.

4. Check `n` before trusting any null. At current scope, is_unranked ×
   SURGE could plausibly land in the 200-800 range (needs Step 0b to
   confirm exact count) — per the earlier power analysis, that supports
   detecting lifts of roughly 4-9 percentage points, not smaller ones.
   If n < 150, treat any null as underpowered, not disproven, and
   consider whether the SURGE threshold can be loosened further before
   concluding.

---

## Step 0d — Confound checks before trusting Step 0c

- **Favorite/longshot bias:** check piece_a_favorite_bias.csv — if
  Korean odds already show a general longshot-overbet or underbet
  pattern, SURGE horses (likely still longer-odds than favorites even
  after surging) inherit that bias. Report the general bias size
  alongside the SURGE-specific ratio so it's clear how much of any
  effect is generic vs. specific to the surge pattern.
- **Field-size effects:** SURGE horses may cluster in certain field
  sizes (the is_unranked rate could vary with starters count). Check
  and control if needed.
- **Region:** run 서울 and 부산 separately as a robustness check, given
  they're different tracks with potentially different insider dynamics.

---

## Deliverable for this Step 0 session

A short report (not a full write-up) with:
1. Step 0a finding — snapshot completeness, and which SURGE definition
   it permits.
2. Final SURGE definition used and resulting n.
3. Naive rate vs. odds-implied ratio, with bootstrap CI.
4. Confound check results (0d).
5. One-line verdict: null / Tier-1-only (beats 사전인기, not the market) /
   Tier-2 (beats the market itself) — using the tier framework already
   agreed on, don't re-derive it.
6. If Tier-2 or promising Tier-1: recommended next step (Step 1 logit
   with the interaction term, per the ladder already planned). If null:
   say so plainly, same as the Q1/Q2/Piece-B nulls were reported —
   these are legitimate, reportable results either way.
