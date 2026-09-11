# Day 4 Context — Full Schema Confirmed, B&C Variables Locked, Raw CSV Pulled

> Continuation of `day1_context_benter_korea_project.md`, `day3_context_rds_connected_and_querying.md`,
> and `benter_korea_explainer.md`.
> This session covered: full DB schema discovery, locking in the 9-variable B&C checksum spec with
> real KRA column mapping, resolving the track-condition restriction empirically, confirming race
> counts, flagging non-finish rank codes, and pulling the full raw-history CSV.
> **Session paused here — CSV in hand (53MB), feature-engineering script not yet built.**

---

## Where things stand

- **Full DB schema confirmed** via `information_schema` — 13 tables now known (Day 3 only had 5).
- **B&C's variables locked at 9** (dropped JMISDATA — Korea has no missing-jockey-data problem;
  `jockey_id` is `NOT NULL` on every `race_info_of_horse` row).
- **Track condition restriction resolved empirically**, not by guessing at the Korean labels.
- **6,000 races** confirmed at 1600–2000m + 건/양 + not cancelled — 12x B&C's 500-race minimum.
- **Full raw-history CSV pulled** (53MB, no distance filter — every horse, every race, every
  distance) via DBeaver Export Resultset. Not yet uploaded/processed in a session.
- **Next real milestone:** build the feature-engineering script, then the multinomial logit fit,
  then compare pseudo-R² against B&C's published ~0.09.

---

## 1. Full DB schema (13 tables, `kra_data` schema)

| Table | Rows | Purpose |
|---|---|---|
| `horse` | 25,630 | Master horse record. **`kra_id` is the join key**, not `id`. |
| `jockey` | 404 | Master jockey record. Has its own `rank1..5`/`total_race` (current-totals only — see gotcha #1). |
| `trainer` | 225 | Master trainer record. |
| `owner` | 1,515 | Master owner record. |
| `stable` | 106 | Training stable/barn record. |
| `stable_contract_status` | 70 | Links stable↔trainer↔jockey contracts. Not used yet. |
| `race_info` | 30,638 | One row per race. Has `distance`, `race_class`, `track_condition`, `track_moisture`, `prize1-5`. |
| `race_info_of_horse` | 347,887 | One row per horse per race (pre-race entry data). Has `jockey_id`, `trainer_id`, `owner_id`, `impost`, `back_num`, `horse_age`, `horse_weight`, `horse_rating`, `kit`. |
| `race_result_of_horse` | 335,936 | One row per horse per race (post-race result). Has `rank`, `goal_time`, `populity`, `win`, `place`. **This is the historical record — use it to derive rolling stats, don't trust `horse.total_race`.** |
| `race_record_of_horse` | 3,035,471 | Sectional/pace splits (`interval_g2f`, `pass_3c`, etc). Not needed for the B&C checksum. |
| `race_record` | 56,781 | Race-level (not horse-level) sectional records. Not used yet. |
| `race_result` | 30,249 | Race-level result metadata — `stewards_report` (JSON), `odds` (JSON), `pass_figure` (JSON). Potential source for bad-luck/interference correction later; not needed now. |
| `record_by_class_by_distance` | 196 | Best/avg time per (race_class, distance, region). **Used as the AVESPRAT normalization baseline.** |

Full column-level detail (all 13 tables, every column, type, key, Korean comment) was pulled this
session via an `information_schema.COLUMNS` query — if needed again, re-run:
```sql
SELECT c.TABLE_NAME, t.TABLE_ROWS, c.ORDINAL_POSITION, c.COLUMN_NAME, c.COLUMN_TYPE,
       c.IS_NULLABLE, c.COLUMN_KEY, c.COLUMN_COMMENT
FROM information_schema.COLUMNS c
JOIN information_schema.TABLES t ON t.TABLE_SCHEMA = c.TABLE_SCHEMA AND t.TABLE_NAME = c.TABLE_NAME
WHERE c.TABLE_SCHEMA = 'kra_data'
ORDER BY c.TABLE_NAME, c.ORDINAL_POSITION;
```

---

## 2. B&C's 9 variables — locked mapping (dropped JMISDATA)

Exact definitions pulled from the 1986 paper itself (equation 14 + surrounding text), not
secondhand summary.

| B&C variable | Definition (from paper) | KRA source | Status |
|---|---|---|---|
| **AVESPRAT** | avg speed rating, last 4 races, track-adjusted | `race_result_of_horse.goal_time` normalized against `record_by_class_by_distance.avg_time` (or a self-computed z-score bucket — see §build spec below) | **Build required — highest priority, highest cost** |
| **LIFE%WIN** | % races won, of those entered in past 2 years | Cumulative from `race_result_of_horse.rank` history, **as-of race date, not `horse.rank1/total_race`** | Build required (mechanical) |
| **W/RACE** | winnings per race, current year | `race_result_of_horse.rank` joined to `race_info.prize1-5`, summed trailing ~1yr | Build required |
| **LSPEDRAT** | track-adjusted speed rating, previous race only | Lagged AVESPRAT | Build required (depends on AVESPRAT) |
| **JOCK%WIN** | jockey % winning rides, current year | Cumulative from `race_info_of_horse.jockey_id` + `race_result_of_horse.rank`, as-of race date | Build required |
| **JOCK#WIN** | jockey # winning rides, current year | Same as above | Build required |
| ~~JMISDATA~~ | flag for jockeys missing from published stats | **Dropped** — `jockey_id` is `NOT NULL` on every row, Korea doesn't have this gap | N/A |
| **WEIGHT** | weight carried | `race_info_of_horse.impost` | **Ready — direct pull** |
| **POSTPOS** | post/gate position | `race_info_of_horse.back_num` | **Ready — direct pull** |
| **NEWDIST** | 1 if horse ran 3-or-4 of last 4 races under ~1 mile, else 0 | Build from `race_info.distance` history per horse; Korea threshold = under 1600m (adapted from B&C's "under one mile") | Build required |

---

## 3. Two correctness gotchas — do not skip these when building the script

**(1) Look-ahead bias.** `horse.total_race`/`rank1` and `jockey.total_race`/`rank1` are running
counters showing **today's** totals, not the totals as of each historical race. Using them
directly leaks future outcomes into past predictions and silently inflates R² — the checksum
would look like it passed when it didn't. Fix: derive LIFE%WIN and JOCK%WIN from
`race_result_of_horse` row-level history, grouped by `horse_id`/`jockey_id`, sorted by
`race_date`, using a **shift-by-1 cumulative** (today's own race must never count toward its own
feature). Proved this pattern works correctly with a synthetic pandas test this session:
```python
df["career_starts_before"] = df.groupby("horse_id").cumcount()
df["career_wins_before"] = df.groupby("horse_id")["is_win"].cumsum().shift(1).fillna(0)
```

**(2) Full history needed before filtering.** A horse's LIFE%WIN going into an 1800m race
includes wins from races at *other* distances too. Build all rolling features across the **full**
pulled history first, then filter down to the 1600–2000m + 건/양 + age 3+ estimation sample as a
separate, later step. Don't filter before building features.

---

## 4. Track condition — resolved empirically, not guessed

Ran `track_condition` vs `track_moisture` cross-tab:

| Label | Moisture range | Avg |
|---|---|---|
| 건 (dry) | 0.01–0.05 | 0.035 |
| 양 (good) | 0.05–0.10 | 0.073 |
| 다 (moist) | 0.09–0.20 | 0.118 |
| 포 (saturated) | 0.15–0.20 | 0.167 |
| 불 (poor) | flat 0.20 (sensor ceiling, not a real range) | 0.20 |

Labels are well-behaved (clean breakpoints at the boundaries). **Decision: restrict to
`track_condition IN ('건','양')`, equivalently `track_moisture <= 0.10`** — mirrors B&C's
"good or fast" restriction. This captures 67% of all races (22,245 / 33,099), so the earlier
worry (from the explainer doc) that this restriction would starve the sample turned out to be
unfounded once real numbers were in hand.

---

## 5. Race count — confirmed sufficient

```sql
SELECT COUNT(*) FROM kra_data.race_info
WHERE distance BETWEEN 1600 AND 2000 AND track_condition IN ('건','양') AND cancel = 0;
-- → 6,000
```

B&C's own minimum was 500 races (they used just 200, exploded to 600 choice sets via their
ranking technique). 6,000 is 12x their minimum — no Gate-1 concern here.

---

## 6. Rank codes ≥90 — resolved (confirmed by [data team lead])

```sql
SELECT `rank`, COUNT(*) AS n FROM kra_data.race_result_of_horse WHERE `rank` >= 90 GROUP BY `rank`;
-- 91: 745 | 92: 1,251 | 93: 2,141 | 95: 2,278
```

(`rank` is a MySQL 8 reserved word — needs backticks.)

| Code | Meaning | Left the gate? | Counts as a "start"? |
|---|---|---|---|
| 91 | 실격 (disqualified) | Yes | **Yes** |
| 92 | 주행중지 (pulled up mid-race) | Yes | **Yes** |
| 93 | 출전제외 (excluded pre-race) | No | **No** |
| 95 | 출전취소 (entry cancelled) | No | **No** |

**Finalized handling:**
- `rank IN (91, 92)` → increment the starts denominator for LIFE%WIN/JOCK%WIN; exclude from the
  win numerator and from rank-ordered choice sets (no valid finishing position). **Check whether
  91 rows have a `goal_time`** — a DQ'd horse crossed the line before being disqualified, so it
  may have a usable time for AVESPRAT even though its rank isn't usable for win-rate. 92 (pulled
  up) almost certainly won't have a time.
- `rank IN (93, 95)` → excluded entirely — not a start, doesn't touch any calculation.

---

## 7. The raw pull query (used to generate the 53MB CSV)

```sql
SELECT
    ri.race_id, ri.race_date, ri.race_class, ri.distance, ri.track_condition,
    ri.track_moisture, ri.region, ri.horse_count,
    ri.prize1, ri.prize2, ri.prize3, ri.prize4, ri.prize5,
    riofh.horse_id, riofh.jockey_id, riofh.trainer_id, riofh.back_num, riofh.impost,
    riofh.horse_age, riofh.horse_weight, riofh.horse_rating,
    rcd.avg_time AS class_dist_avg_time,
    rrofh.`rank`, rrofh.goal_time, rrofh.populity, rrofh.win
FROM kra_data.race_info ri
JOIN kra_data.race_info_of_horse riofh ON riofh.race_id = ri.race_id
LEFT JOIN kra_data.race_result_of_horse rrofh
    ON rrofh.race_id = ri.race_id AND rrofh.horse_id = riofh.horse_id
LEFT JOIN kra_data.record_by_class_by_distance rcd
    ON rcd.race_class = ri.race_class AND rcd.distance = ri.distance AND rcd.region = ri.region
WHERE ri.cancel = 0
ORDER BY riofh.horse_id, ri.race_date;
```

No distance filter — intentionally pulls every race, every distance, for the rolling-feature
build (see gotcha #2). Exported via DBeaver → Export Resultset → CSV → **UTF-8 encoding**
(needed because `kit`/`track_condition` contain Korean text). **Not yet double-checked that the
UTF-8 setting was actually applied on export — worth a quick look at the CSV in a text editor
before processing, in case Korean fields came out garbled.**

---

## 8. Resume point for next session

1. Upload the 53MB CSV.
2. Build the feature-engineering script:
   - As-of-date LIFE%WIN / JOCK%WIN / JOCK#WIN (shift-based cumulative, pattern proven in §3)
   - W/RACE (trailing ~1yr sum of prize won, by `rank` → `prizeN` lookup)
   - NEWDIST (3-or-4-of-last-4 races under 1600m)
   - AVESPRAT — **use the low-cost z-score approach first** (per `benter_korea_explainer.md` §F):
     z-score `goal_time` within (region × distance × race_class × track_condition) buckets,
     ~0.5 day of work. Upgrade to a proper track-variant model later only if time allows —
     that's a clean A/B comparison on the same pipeline, not a redo.
   - LSPEDRAT = lagged AVESPRAT (previous race only)
   - Exclude `rank >= 90` rows from time/rank-based calculations throughout
3. Filter to `distance BETWEEN 1600 AND 2000 AND track_condition IN ('건','양') AND horse_age >= 3`
   for the actual estimation sample — only after step 2 is done on the full history.
4. Implement the Chapman-Staelin rank-order "explosion" process (explosion depth E=1,2,3) to get
   more choice sets out of the ~6,000 races.
5. Fit the multinomial logit (9-variable specification, softmax/MLE).
6. Compute pseudo-R² = 1 − L(model)/L(null) and compare to B&C's published ~0.09 (E=1) /
   ~0.055–0.064 (E=2,3). Land near that range → pipeline validated → move to the 15–16 variable
   expansion. Land far off → debug before trusting anything built on top.

---

## Reference — key project files

- `day1_context_benter_korea_project.md`, `day3_context_rds_connected_and_querying.md`,
  `benter_korea_explainer.md` — prior context, already in project knowledge
- `1986bolton.pdf` — source of the exact B&C variable definitions used in §2
- DBeaver connection details (host/port/driver settings) — unchanged from Day 3, see that doc
- This raw-pull CSV (53MB, local — not yet uploaded to a chat/project)
