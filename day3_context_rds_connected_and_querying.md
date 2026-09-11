# Day 3 Context — RDS Connected, Live Queries Working

> Continuation of `day1_context_benter_korea_project.md` and `benter_korea_explainer.md`.
> This session covered: Gate 0 verification results, getting RDS access from [data team lead],
> setting up DBeaver, and debugging through to a working query against real KRA data.
> **Session paused here — SQL pull was in progress, resuming later.**

---

## Where things stand right now

- **Gate 0: PASSED.** Confirmed via a Cowork session with live browser access to data.go.kr
  (this sandbox itself can't reach that domain — Cowork could). Full verdict and evidence below.
- **RDS access: GRANTED and WORKING.** Connected via DBeaver, ran real queries, got real KRA
  race/horse data back. Was mid-pull (removing a `LIMIT 100` to get the full table) when the
  session paused for the day.
- **확정배당률 (final odds) extraction: PLANNED, NOT YET RUN.** RDS explicitly does not carry
  this ([data team lead] confirmed directly: "최종배당은 수집하고 있지 않습니다"). A full extraction plan
  and Python script are built and ready to hand to Cowork — not yet executed.
- **Next real milestone: the B&C checksum** — replicate Bolton & Chapman's (1986) 10-variable
  model on the 1600–2000m distance band, see if pseudo-R² lands near their published 0.09. This
  is the pipeline-correctness test before trusting any novel result later. Not started yet — was
  about to begin once the full data pull finished.

---

## 1. Gate 0 — API verification (done via Cowork, reviewed this session)

Cowork made live calls to all 3 data.go.kr public APIs and confirmed:

**Q1 — 확정 (final/settled) odds, not 예상 (provisional).** Proven three ways: Σπ (implied
probability sum, using 20% takeout) averaged 1.0004 across 15 races; repeated calls returned
identical values; and API①'s odds matched API③'s `rsutWinPrice` (confirmed 확정 payout) exactly
for every runner in two separate test races.

**Q2 — History depth.** Odds (API①) confirmed back to ≥2005; factor data (API③) confirmed back
to ≥2010. Well over 10,000 races available — Benter's stated minimum is 500–1,000.

**Q3 — API③ field coverage.** Confirmed present: finish time (`rsutRaceRcd`), weight carried
(`pthrBurdWgt`), gate (`pthrGtno`), body weight + change (`pthrWeg`), rating (`pthrRatg`), track
condition + moisture (`rsutTrckStus`), margin (`rsutMargin`), stable jockey/trainer/owner IDs,
equipment (`pthrEquip`), jockey allowance (`hrmJckyAlw`), win/place odds. **Confirmed absent:**
sectional/pace splits, exotic-pool payouts (those are in API①), pool size (API②), pedigree,
workout data.

**Bonus finding:** 1600–2000m band = ~26% of races in a 2-month sample (354 races, 43 race-days,
3 tracks) → extrapolates to roughly 8,600 races in that band over full history. Enough for the
B&C checksum. Also confirmed: speed-figure buckets (경마장×거리×등급×주로상태) are too thin on a
short sample (max 15 races/bucket in 2 months) — the z-score speed figure needs to run on the
full historical backfill, not a slice.

Full verdict doc with runbook (endpoints, params, join keys, service key) exists from that
session — service key: `REDACTED_API_KEY`
(개발계정, 3,000 calls/day, valid to 2028-07-16).

---

## 2. The checksum concept (explained this session, not yet run)

**What it is:** rebuild Bolton & Chapman's (1986) original 10-variable multinomial logit model
exactly, filtered to their same 1600–2000m distance restriction, run it on KRA data, and check
whether pseudo-R² lands near their published ~0.09.

**Why it matters:** the project's actual research question (ΔR² for the two-stage Benter
adaptation) has no known correct answer — nobody's run this on KRA data before. The B&C
replication does have a known answer (it's published), so it's a calibration test: if the KRA
replication lands near 0.09, the whole pipeline (extraction, joins, softmax, MLE fitting,
log-likelihood math) is provably correct before trusting anything novel built on top of it. If it
comes out wildly different, that's a pipeline bug to find now, not after reporting a bad ΔR²
number to the team.

**Pseudo-R² formula:** `R² = 1 − L(model) / L(random guessing)`, where `L` is summed
log-likelihood (log of the probability the model assigned to each race's actual winner, summed
across races). 0 = no better than guessing 1/N per horse; realistic range for this kind of model
is roughly 0.05–0.15 (Benter's own fully-optimized model topped out at 0.14).

---

## 3. RDS access — how it was obtained

[data team lead] 팀장 (data owner) replied to a column-level request email (not a table-name request —
he asked us to specify exact data needs so he could map them to his own schema, since he knows
the DB better than we do). He sent back a PDF: **"마필 데이터 분석 변수 DB 스키마 매핑 정의서"**
— a schema mapping doc covering connection info + a proposed table/column mapping for our
priority list.

**Important: the PDF's column mappings were not fully accurate.** Several had to be corrected
by actually querying the live schema (see Section 4). Treat that PDF as a starting guide, not
ground truth — `DESCRIBE` beats the document every time they conflict.

### Connection details (from the PDF, password sent separately — not stored in this doc)

| Field | Value |
|---|---|
| Tool | DBeaver (Community Edition) |
| Server Host | `REDACTED_DB_HOST` |
| Port | `3306` |
| Database | `kra_data` |
| Username | `Jihwan` |
| Driver property needed | `allowPublicKeyRetrieval = true` (required, or connection fails on MySQL 8.4) |
| `useSSL` setting | **Ignore the PDF's `useSSL: false` instruction** — [data team lead] corrected this himself in a follow-up message. Leave SSL on default. |
| Network restriction | Originally "company WiFi only." **Since lifted** — [data team lead] confirmed home WiFi access is now allowed. No location restriction currently. |
| Access level | Read-only (SELECT only — this is fine, no write access needed or expected) |

**Permissions note:** access is granted per-table, not blanket. First query attempt
(`SELECT * FROM race`) failed with a permissions error (`SELECT command denied`) — this is
expected until [data team lead] explicitly opens each table. Table-by-table access was granted following
up from there.

---

## 4. Confirmed real schema (from live `DESCRIBE` queries — this session)

The PDF's mapping had two specific errors, both caught and fixed by querying the actual tables:

### `race_result_of_horse` (this is where finish time actually lives — PDF said `race_record_of_horse`, which was wrong)
```
race_id, region, race_date, race_num, horse_id, goal_time, rank, gap,
populity, win, place, change_class, change_class_direction
```
`goal_time` (decimal) = finishing time in seconds. This is the correct source for the AVESPRAT
speed-figure input.

### `race_record_of_horse` (sectional/pace data only — NOT finish time, despite similar name)
```
race_id, region, race_date, race_num, horse_id, record_kind, rank, record
```
`record_kind` values are all sectional splits and pass-through checkpoints (e.g. `interval_g2f`,
`pass_g1f`, `pass_3c`) — no overall finish time here. Useful later for pace/running-style
factors, not needed for the baseline model.

### `horse` (join key is NOT `horse_id` — PDF was wrong here too)
```
id (PK, auto_increment), kra_id (UNIQUE — this is the real join key), stable_id,
owner_id, name, birth_date, reg_date, debut_date, sex, total_race,
rank1–rank5, price, total_prize, sire, dam, class, retire_date, rating,
rest_day, status, dosage_* fields, inbreeding_coef_percent, ...
```
`race_info_of_horse.horse_id` joins to `horse.kra_id`, **not** `horse.id`. This was the second
schema-mismatch bug hit and fixed this session.

### `race_info` / `race_info_of_horse` — matched the PDF's description reasonably well
Columns used successfully: `race_id, distance, race_class, track_condition, track_moisture,
region, horse_count` (race_info) and `horse_id, impost, back_num, horse_age, horse_weight, kit,
req_inc_impost, horse_rating` (race_info_of_horse).

**General lesson for future queries against this DB: run `DESCRIBE <table>` before trusting any
column name from the PDF. Two out of the ~5 tables touched so far had incorrect mappings in the
document.**

---

## 5. Working query (confirmed successful, returned 100 real rows)

```sql
SELECT
    ri.race_id,
    ri.distance,
    ri.race_class,
    ri.track_condition,
    ri.track_moisture,
    ri.region,
    ri.horse_count,
    riofh.horse_id,
    riofh.impost,
    riofh.back_num,
    riofh.horse_age,
    riofh.horse_weight,
    riofh.kit,
    riofh.req_inc_impost,
    riofh.horse_rating,
    h.birth_date,
    h.total_race,
    h.rating AS horse_base_rating,
    rrofh.rank,
    rrofh.goal_time
FROM kra_data.race_info ri
JOIN kra_data.race_info_of_horse riofh ON riofh.race_id = ri.race_id
JOIN kra_data.horse h ON h.kra_id = riofh.horse_id
LEFT JOIN kra_data.race_result_of_horse rrofh
    ON rrofh.race_id = ri.race_id AND rrofh.horse_id = riofh.horse_id
LIMIT 100;
```

Sample output confirmed real, sensible data: `goal_time` in seconds (e.g. 78.2, 87.4), ranks,
ages, equipment strings with +/- notation for on/off changes, ratings, data spanning at least
2014–2024. Some expected NULLs (e.g. `horse_rating` blank for lower-rated/unrated horses,
occasional missing `track_condition`/`goal_time` for edge-case rows).

**Was about to re-run this without `LIMIT 100` to pull the full table when the session paused.**

---

## 6. What's ready to go but not yet executed

- **Final odds (확정배당률) extraction plan and script** — both built, sitting in project
  outputs (`cowork_plan_extract_final_odds.md`, `extract_final_odds.py`). Not run yet. Needs to
  go to Cowork (this sandbox can't reach data.go.kr; Cowork's browser tool can). Includes a
  mandatory schema-probe step first (pool-type field name for isolating 단승 rows from exotic
  pools is not yet confirmed), then a checkpointed, rate-limit-aware backfill loop. Plan flags
  a real risk: a full 16-year pull likely doesn't fit in the 3,000-calls/day budget within the
  4-week timeline — recommends sizing the date range down (e.g. last 2–4 years) rather than
  discovering the problem mid-pull.
- **[data team lead] column-request email** — sent, and he responded with RDS access + the schema PDF.
  Loop is functionally closed, though not every requested table's access has necessarily been
  explicitly confirmed open (only the tables actually queried so far are confirmed working).

---

## 7. Resume point for next session

1. **Finish the RDS pull** — re-run the working query above without `LIMIT`, export full result
   to CSV.
2. **Run the B&C checksum** — filter to 1600–2000m, build the 10 original variables, fit, check
   if pseudo-R² lands near 0.09. This is the next real analytical milestone.
3. **In parallel (doesn't block the above):** hand the final-odds extraction plan to Cowork,
   starting with its schema-probe step.
4. Once both the checksum passes and odds are extracted, move to building the remaining ~6
   Korea-specific factors (체중 증감, 장구, 기수감량, 상대 경쟁 강도 via rating, etc.) and then
   the speed figure (AVESPRAT equivalent) — the single highest-priority, highest-effort variable
   in the whole model.

---

## Reference — files already produced this project (in `/mnt/user-data/outputs/`, may need
re-uploading to project knowledge if not already there)

- `day_plan_gate0_and_prep.md` — original task breakdown (API check / meeting prep / model spec)
- `[data team lead]_대화_정리.md` — lighter Korean talking-points version for the [data team lead] conversation
- `extract_final_odds.py` — Python extraction script for 확정배당률 (schema-probe + backfill)
- `cowork_plan_extract_final_odds.md` — Cowork-executable version of the same plan, with
  realistic rate-budget math
- `[data team lead]_RDS_요청_이메일.md` — the column-level RDS request email that led to the access grant
  covered in this document
- `how_to_read_a_chulmapyo.md` — 출마표 (race card) reading reference, from earlier in the
  project
