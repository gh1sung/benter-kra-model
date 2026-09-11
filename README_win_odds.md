# Getting the full 16-year 확정 win-odds history

## The honest constraint
The whole history **can** be pulled — it's only ~2,400 API calls total (one call per
racing date, using the `numOfRows=200000` trick that returns a whole day at once).
That fits inside **~1 day** of the dev key's 3,000-calls/day cap, ~3–4 hours of running,
producing ~370,000 rows (~8 MB).

What I **can't** do is run those 3–4 hours and hand you an 8 MB file from inside this
chat — the browser session drops every few minutes and I can't route megabytes back
through my tools. So the full pull is done by the script below, on your machine.

## Run it (one command) — 5-year window
```bash
pip install requests
python3 extract_win_odds.py --start 2021-07-16 --end 2026-07-15 --out win_odds_5yr.csv
```
(For the full history instead, use `--start 2010-01-01`. Odds exist back to ~2005.)

**Why run this instead of me doing it in the browser:** the data.go.kr API has been
responding slowly (~10–15s per request even for empty days). Unattended, that's a ~2–3h
job the script handles fine. Through my browser session it's hundreds of flaky
round-trips — not doable in a sitting. The script is simply the right tool for a slow API.

**Data-integrity fix (important):** the script now tells a *failed* fetch apart from a
*genuinely empty* (no-racing) day. A failed date is logged, NOT written, and NOT saved to
the checkpoint — so re-running the same command automatically retries only the failures.
Earlier drafts (and my first browser harness) could have mistaken a timeout for an empty
day and silently dropped real races; that can't happen now.
- Leave it running. It prints progress per date.
- If it stops for any reason (hits the daily cap, network, you close it), **just run the
  exact same command again** — it reads `win_odds_full.csv.checkpoint.json` and resumes
  from where it left off. It will not re-pull dates already done.
- Want to go deeper than 2010? Try `--start 2005-01-01` (odds exist back to ~2005; the
  script just skips dates with no data).
- `--all-days` also checks Mon–Thu for rare holiday racing (roughly doubles calls).

## Output columns
`date, track, race_no, gate_no, horse_id, odds`
- `odds` = 확정 (final) 단승식 win odds. Verified: equals API③'s `rsutWinPrice` exactly.
- **`horse_id` = `gate_no` = `chulNo` (출발번호).** API① carries no stable horse number.
  To attach a persistent 마번, join to API③ `raceRsutDtl` on
  `(date, track, race_no, chulNo == pthrGtno)` and take `pthrHrno`.
- One row per horse per race. Scratched horses have no win-odds row (expected).

## Built-in validation (matches the Gate 0 checks)
- Per race it computes `Σ (1 − 0.20)/odds`; anything outside 0.95–1.05 is printed as a
  `Σπ` flag (would signal a bad pool filter). The 626-race in-browser sample had **zero**.
- Every 50th race it cross-checks odds against API③'s `rsutWinPrice` and prints OK /
  MISMATCH. Sample run: all OK.

## Match the window to RDS
Odds only matter where they join to factor data. If [data team lead]'s RDS factor dump covers,
say, 2015→now, set `--start 2015-01-01` — pulling older odds that join to nothing wastes
calls. The overlap of (odds window ∩ factor window) is what the model actually uses.

## If you'd rather not run Python
Tell me and I can keep pulling in-browser across sessions into a downloadable file —
but it's much slower and drop-prone than the script. The script is the right tool for
"the whole thing."
