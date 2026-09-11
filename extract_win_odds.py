#!/usr/bin/env python3
"""
Extract 확정 win-pool odds (단승식) from KRA API① — CONCURRENT version.

Same output/checkpoint as before, but fetches several dates at once so a slow API
doesn't make it crawl. Reuses any existing <out>.checkpoint.json, so you can stop the
old sequential run (Ctrl-C) and just start this with the SAME --out to resume faster.

Fast trick: one call with NO `meet` and numOfRows=200000 returns the WHOLE race-day,
ALL tracks, ALL pools (~18k–70k rows) — so the pull is ~one call per racing date.

Confirmed schema (verified live 2026-07-16):
  endpoint  : https://apis.data.go.kr/B551015/API160_1/integratedInfo_1
  POOL field: "pool" ; WIN value: "단승식"
  horse key : "chulNo" (= 출발번호/gate). No stable 마번 on API① — join API③ pthrGtno→pthrHrno.
  track     : row field "meet" is the Korean track name (서울/제주/부산경남).
  NOTE: this pulls ALL THREE tracks. To model 서울+부경 only, filter out track=="제주"
        afterward — Jeju rides along for free in the same call, costs no extra time.

Data-integrity: a failed/timed-out fetch is NOT mistaken for an empty day. Failed dates
are logged, not written, not checkpointed — re-run the same command to retry only those.

Validation: per-race Σ(0.8/odds) ≈ 1.00 (20% takeout); every 50th race cross-checked
against API③ rsutWinPrice (independent 확정 payout).

Usage:
  pip3 install requests
  python3 extract_win_odds.py --start 2021-07-16 --end 2026-07-15 --out win_odds_5yr.csv
  # options: --workers 8 (concurrency), --all-days (also probe Mon–Thu for holiday racing)
  # stop anytime; re-run the same command to resume from checkpoint.
"""
import csv, json, os, time, argparse, datetime as dt
from concurrent.futures import ThreadPoolExecutor
import requests

SERVICE_KEY = "REDACTED_API_KEY"
API1 = "https://apis.data.go.kr/B551015/API160_1/integratedInfo_1"
API3 = "https://apis.data.go.kr/B551015/API156/raceRsutDtl"
TAKEOUT = 0.20
DAILY_CAP = 2950
NUMROWS = 200000
XCHECK_EVERY = 50

class FetchError(Exception):
    """Fetch failed after retries — NOT an empty day. Never treat as 'no racing'."""

def get(url, params, tries=6):
    for t in range(tries):
        try:
            return requests.get(url, params=params, timeout=40).json()
        except Exception:
            time.sleep(1.5 * (t + 1))
    return None

def items(j):
    b = ((j or {}).get("response") or {}).get("body") or {}
    it = (b.get("items") or {})
    it = it.get("item") if isinstance(it, dict) else None
    if not it: return []
    return it if isinstance(it, list) else [it]

def fetch_date(ds):
    """One call: whole day, all tracks. Returns 단승 rows [ds,track,rcNo,chulNo,odds].
    Raises FetchError on a failed/invalid response (so caller can retry, not mislabel)."""
    j = get(API1, dict(serviceKey=SERVICE_KEY, pageNo=1, numOfRows=NUMROWS, _type="json", rc_date=ds))
    resp = (j or {}).get("response") or {}
    body = resp.get("body")
    code = (resp.get("header") or {}).get("resultCode")
    if body is None or code not in ("00", "0"):
        raise FetchError(f"{ds}: {(resp.get('header') or {}).get('resultMsg') or 'no valid response'}")
    rows = items(j)                      # valid response; [] here = TRUE empty (no racing)
    if len(rows) >= NUMROWS:
        raise RuntimeError(f"{ds}: hit numOfRows cap — raise NUMROWS and re-run this date")
    return [[ds, r["meet"], r["rcNo"], r["chulNo"], r["odds"]]
            for r in rows if r.get("pool") == "단승식"]

def fetch_safe(ds):
    try:
        return ds, fetch_date(ds), None
    except FetchError as e:
        return ds, None, str(e)

def xcheck(ds, track, rcno, mine):
    cd = {"서울": 1, "제주": 2, "부산경남": 3}.get(track)
    j = get(API3, dict(serviceKey=SERVICE_KEY, pageNo=1, numOfRows=100, _type="json",
                       race_dt=ds, rccrs_cd=cd, race_no=rcno))
    a3 = {str(x["pthrGtno"]): x["rsutWinPrice"] for x in items(j)}
    return sum(1 for g, o in mine if a3.get(str(g)) is not None
               and abs(float(a3[str(g)]) - float(o)) > 1e-9)

def commit(ds, rows, w, fout, done, ck, state):
    """Write one date's rows + validate + checkpoint (single-threaded, main loop)."""
    byrace = {}
    for r in rows: byrace.setdefault((r[1], r[2]), []).append((r[3], r[4]))
    for (track, rcno), hs in byrace.items():
        state["races"] += 1
        sp = sum((1 - TAKEOUT) / o for _, o in hs if o)
        if not (0.95 <= sp <= 1.05):
            state["flags"].append((ds, track, rcno, round(sp, 3)))
            print(f"  !! Σπ {ds} {track} R{rcno} = {sp:.3f}")
        if state["races"] % XCHECK_EVERY == 0:
            m = xcheck(ds, track, rcno, hs)
            print(f"  xcheck {ds} {track} R{rcno}: {'OK' if m==0 else f'MISMATCH x{m}'}")
    for r in rows: w.writerow([r[0], r[1], r[2], r[3], r[3], r[4]])
    fout.flush()
    done.add(ds); json.dump({"done": sorted(done)}, open(ck, "w"))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", required=True)
    ap.add_argument("--end", required=True)
    ap.add_argument("--out", default="win_odds.csv")
    ap.add_argument("--workers", type=int, default=8, help="concurrent requests (default 8)")
    ap.add_argument("--all-days", action="store_true")
    a = ap.parse_args()
    start = dt.date.fromisoformat(a.start); end = dt.date.fromisoformat(a.end)
    ck = a.out + ".checkpoint.json"
    done = set(json.load(open(ck))["done"]) if os.path.exists(ck) else set()
    if done: print(f"resuming — {len(done)} dates already done")

    fresh = not os.path.exists(a.out)
    fout = open(a.out, "a", newline="", encoding="utf-8"); w = csv.writer(fout)
    if fresh: w.writerow(["date", "track", "race_no", "gate_no", "horse_id", "odds"])

    state = {"races": 0, "flags": []}
    calls = 0; failed = []
    days = [(start + dt.timedelta(n)).strftime("%Y%m%d")
            for n in range((end - start).days + 1)]
    days = [d for d in sorted(days, reverse=True)
            if a.all_days or dt.date(int(d[:4]), int(d[4:6]), int(d[6:])).weekday() in (4, 5, 6)]
    days = [d for d in days if d not in done]
    print(f"{len(days)} dates to pull, {a.workers} at a time")

    try:
        with ThreadPoolExecutor(max_workers=a.workers) as ex:
            for k in range(0, len(days), a.workers):
                if calls >= DAILY_CAP:
                    print(f"\nHit daily cap ({calls}). Re-run the same command to continue.")
                    break
                batch = days[k:k + a.workers]
                calls += len(batch)
                results = list(ex.map(fetch_safe, batch))
                for ds, rows, err in results:      # commit in date order, single-threaded
                    if err is not None:
                        failed.append(ds)
                        print(f"  !! FAILED {err} — will retry on next run")
                        continue
                    commit(ds, rows, w, fout, done, ck, state)
                    if rows:
                        print(f"{ds}: {len(rows)} rows | done={len(done)} calls={calls} races={state['races']}")
    finally:
        fout.close()
        print(f"\nrun totals: calls={calls} races={state['races']} "
              f"Σπ_flags={len(state['flags'])} failed={len(failed)} -> {a.out}")
        if failed:
            print("failed dates (not written; re-run same command to retry):", failed[:30])

if __name__ == "__main__":
    main()
