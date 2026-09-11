# Jeju Contamination Scare — Investigated & Resolved (Day 5)

> Continuation of `day1_context_benter_korea_project.md`, `day4_context_schema_locked_bc_mapped.md`.
> Add to project knowledge alongside the other day-context docs.

## TL;DR

A real code gap was flagged (no region filter anywhere in the estimation-sample logic), which raised
a legitimate risk that Jeju races — a structurally different racing world (native 제주마/한라마, no
thoroughbreds, separate horse/jockey/trainer pool, own class ladder) — had been pooled into the
Seoul+Busan fundamental model. **Verified at the source and it did not happen.** `kra_data.race_info`
contains only 서울 and 부산 at the table level — Jeju was never in this RDS data to begin with, not
excluded by luck. The fundamental model, checksum, and all reported numbers (0.1424 test pseudo-R²,
etc.) stand unchanged. No rebuild was needed.

**One real action item survived:** `win_odds_5yr.csv` (pulled from the public data.go.kr API, a
separate source from RDS) *does* contain Jeju rows and must be filtered to 서울/부산경남 before the
Stage 2 π_i/f_i join. This was already known, not a new finding.

## What triggered it

Reviewing `build_bc_features.py`, `fit_engine.py`, and `fit_bc_checksum.py` found the shared
estimation-sample mask filters on `distance`, `track_condition`, `horse_age`, and `rank` — but **never
on `region`**. Comments throughout the codebase say "pooled Seoul+Busan," but no code enforced it.
Since Jeju genuinely races within the 1600–2000m band (1600/1610/1700/1800/2000m all exist at Jeju),
the missing filter was a real gap, not a false alarm — it just turned out not to have been exercised,
because the upstream data never contained a third region.

## The verification (source-level, not sample-level)

Ran directly against `kra_data.race_info` in DBeaver, unfiltered except `cancel=0`:

```sql
SELECT region, COUNT(*) AS n_races FROM kra_data.race_info WHERE cancel = 0 GROUP BY region;
-- 서울: 19,338   부산: 13,772   (2 rows only — no 제주 row exists)
```

This is the whole table, not the 1600–2000m estimation band — so it rules out contamination at every
possible filter level, not just the one currently used. Total (33,110) is consistent with the
33,099-race figure from the Day 4 track-condition cross-tab, confirming this is the same underlying
table and not a stale/partial query.

**Conclusion:** `race_info` — and by extension `race_info_of_horse`, `race_result_of_horse`, every
table joined on `race_id` — is Seoul+Busan by construction. The RDS pull [data team lead] provided was never a
3-track dataset. Whatever ingestion process populates `kra_data` already excludes Jeju upstream of
anything this project touches.

## Why this was still the right thing to check

The code gap was real regardless of the outcome. Absence of enforcement is not the same as absence of
risk — if `kra_data` is ever refreshed, re-pulled with a different scope, or a colleague adds a table
that does include Jeju, the current code would silently pool it in with no error and no obviously wrong
R² (Jeju speed figures are bucketed by region, so a leak wouldn't announce itself numerically). Cheap
verification now was worth it; assuming from comments alone was not.

## Standing rules going forward

1. **Never trust a code comment as a data guarantee.** "Pooled Seoul+Busan" in a docstring is a
   claim, not a filter. If a restriction matters, it must be an explicit line in the `WHERE`/mask,
   not an assumption about what the source contains.
2. **When a structural risk is identified (different population, different regime, different
   process), verify at the unfiltered source first**, not just downstream in the sample that survived
   existing filters. An unfiltered source check (like CHECK 1 here) is strictly more informative than
   a filtered one — it rules out contamination under *any* future filter change, not just today's.
3. **Different data sources can have different scope, even for "the same" concept.** `kra_data` RDS
   (Seoul+Busan only) and the public data.go.kr odds API (all 3 tracks) are not the same universe.
   Any time two sources are joined (as in Stage 2's π_i/f_i join), explicitly confirm both sides cover
   the identical population before joining — don't assume parity.
2. **Add the region guard defensively anyway**, even though it's currently a no-op:
   ```python
   mask = (... existing filters ...) & (df["region"].isin(["서울", "부산"]))
   ```
   This costs nothing today and prevents silent contamination if the source ever changes.
3. **When verifying a categorical filter against Korean-language data, always print and eyeball the
   raw label values first**, before trusting any count (zero or otherwise). A garbled/mojibake export
   would make a real contamination invisible — an encoding check is a precondition for trusting the
   result, not an optional extra.

## Files/state unaffected by this investigation

- `final_test_results.csv`, `final_calibration_table.csv`, `bc_checksum_*.csv`, `ablation_results_raw.csv`,
  `lambda_selection.csv` — all valid as-is, no re-run required.
- `bc_final_check_report.md` (B&C fidelity check) — conclusions stand.
- Gate 2 frozen model (10 vars: baseline-9 + CAREER_STARTS, `race_safe=True`, test pseudo-R² = 0.1424)
  — unaffected, no rebuild triggered.

## Action item carried into Stage 2 (not new — already planned)

Before joining π_i (public probability) to f_i (fundamental model score):
```python
odds = pd.read_csv("win_odds_5yr.csv")
odds_sb = odds[odds["track"] != "제주"].copy()
```
Confirm the (date, track, race) universe in the filtered odds matches the Seoul+Busan race universe
in the fundamental model output before the join.
