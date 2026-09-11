"""
drift_build.py — DRIFT Tag Execution Plan §1-§3.
Builds the analysis table (MONEY_IN in normalized probability space),
runs Gate A (data completeness) and Gate B (pipeline sanity).

MONEY_IN_i = ln( p_i(2) / p_i(25) ),  p_i(t) = (1/odds_i(t)) / sum_j (1/odds_j(t))
Positive = odds shortened = money came in.
"""
import csv, json, pickle
import numpy as np
import pandas as pd
import sys
sys.path.insert(0, "/sessions/sweet-eager-noether/mnt/.projects/019f5bac-fecf-767f-8ca3-4b430e3d20e8/docs")
from harville_engine import place_probs

DL  = "/sessions/sweet-eager-noether/mnt/Downloads"
OUT = "/sessions/sweet-eager-noether/mnt/outputs"
EARLY  = f"{DL}/early_odds_5point.csv"
ODDS   = f"{DL}/win_odds_5yr.csv"
RESULT = f"{DL}/exotic_outcomes.csv"
LAM = 0.8
REGION_CODE = {"서울":"01","부산":"03","부산경남":"03","제주":"02"}
SEED = 20260727

def win_snapshot(row):
    try: js = json.loads(row["snapshot"])
    except Exception: return None
    win = js.get("단승식", {}); d = {}
    for k, v in win.items():
        try:
            hn = int(k); o = float(v)
            if o > 0: d[hn] = o
        except (ValueError, TypeError): continue
    return d or None

# ---- snapshots at 25 and 2 ----
snap = {25: {}, 2: {}}
for row in csv.DictReader(open(EARLY)):
    m = row["minutes_before_post"].strip()
    if m not in ("25", "2"): continue
    d = win_snapshot(row)
    if d: snap[int(m)][str(row["race_id"]).strip()] = d
print(f"races with 25분 win snapshot: {len(snap[25])}")
print(f"races with 2분  win snapshot: {len(snap[2])}")

# ---- results ----
results = {}
for row in csv.DictReader(open(RESULT)):
    rid = str(row["race_id"]).strip()
    results[rid] = {"n_starters": int(row["n_starters"]),
                    "winner": row["winner"].strip(),
                    "top2": set(x for x in row["top2_pair"].split("|") if x),
                    "top3": set(x for x in row["top3_triple"].split("|") if x),
                    "region": row["region"].strip(),
                    "race_date": row["race_date"].strip()}

# ---- final odds ----
odds_final = {}
for row in csv.DictReader(open(ODDS)):
    rc = REGION_CODE.get(row["track"].strip())
    if rc is None: continue
    rid = f"{str(row['date']).strip()}{rc}{int(row['race_no']):02d}"
    try: o = float(row["odds"])
    except ValueError: continue
    if o > 0: odds_final.setdefault(rid, {})[int(row["gate_no"])] = o

# ============================ GATE A.1 ============================
races25 = set(snap[25]); races2 = set(snap[2])
both = races25 & races2
covA1 = len(both) / len(races25 | races2)
print("\n" + "="*66); print("GATE A.1 — 25분 AND 2분 both present"); print("="*66)
print(f"races with both: {len(both)} / {len(races25|races2)} = {100*covA1:.1f}%  "
      f"(require >=80%)  -> {'PASS' if covA1>=0.80 else 'FAIL'}")

# ============================ GATE A.2 ============================
from collections import Counter
diffs = []; nrec = []
for rid in both:
    res = results.get(rid)
    if not res: continue
    nr = len(snap[25][rid]); na = res["n_starters"]
    diffs.append(nr - na); nrec.append(nr)
diffs = np.array(diffs)
print("\n" + "="*66); print("GATE A.2 — n_recorded_25 vs n_starters"); print("="*66)
print(f"races checked: {len(diffs)}")
print(f"exact match n_recorded==n_starters: {100*(diffs==0).mean():.1f}%  (day-8 was 92.1%)")
print(f"n_recorded < n_starters: {100*(diffs<0).mean():.1f}% | > : {100*(diffs>0).mean():.1f}%")
print(f"max n_recorded seen: {max(nrec)} | distribution: {dict(sorted(Counter(nrec).items()))}")

# ---- assemble table + count scratches (A.3) ----
rows = []; scratch = 0; loss = {"no_result":0,"small":0,"no_final":0,"no_final_horse":0,"scratch":0,"ok":0}
for rid in sorted(both):
    res = results.get(rid)
    if not res: loss["no_result"]+=1; continue
    n = res["n_starters"]
    if n <= 4: loss["small"]+=1; continue
    top = 2 if n <= 7 else 3
    of = odds_final.get(rid)
    if of is None: loss["no_final"]+=1; continue
    s25, s2 = snap[25][rid], snap[2][rid]
    # normalized probs at each timepoint over that timepoint's recorded field
    inv25 = {h: 1.0/o for h, o in s25.items()}; z25 = sum(inv25.values())
    inv2  = {h: 1.0/o for h, o in s2.items()};  z2  = sum(inv2.values())
    p25 = {h: inv25[h]/z25 for h in inv25}
    p2  = {h: inv2[h]/z2  for h in inv2}
    # final-odds implied (overround removed) + harville place
    invf = {h: 1.0/o for h, o in of.items()}; zf = sum(invf.values())
    q = {h: invf[h]/zf for h in invf}
    ipl = place_probs(q, top=top, lam=LAM)
    # rank_25 by shortest odds
    order = sorted(s25, key=lambda h: (s25[h], h)); rank25 = {h:i for i,h in enumerate(order,1)}
    for hn in s25:
        if hn not in s2:            # scratched between 25 and 2 -> exclude
            scratch += 1; loss["scratch"]+=1; continue
        if hn not in of:
            loss["no_final_horse"]+=1; continue
        loss["ok"]+=1
        rows.append({
            "race_id": rid, "race_date": res["race_date"], "region": res["region"],
            "horse_num": hn, "n_starters": n, "top": top,
            "odds_25": s25[hn], "odds_2": s2[hn], "odds_final": of[hn],
            "p_25": p25[hn], "p_2": p2[hn],
            "MONEY_IN": np.log(p2[hn]/p25[hn]),
            "MONEY_IN_RAW": np.log(s25[hn]/s2[hn]),
            "rank_25": rank25[hn],
            "q_final": q[hn], "implied_win": q[hn], "implied_place": ipl.get(hn, np.nan),
            "won": 1 if str(hn)==res["winner"] else 0,
            "placed": 1 if str(hn) in (res["top2"] if top==2 else res["top3"]) else 0,
        })

df = pd.DataFrame(rows)
df["race_date"] = pd.to_datetime(df["race_date"])
print("\n" + "="*66); print("GATE A.3 — scratches & join losses"); print("="*66)
print("join/loss counts:", loss)
print(f"scratched (present @25, absent @2, excluded): {scratch}")
print(f"\nassembled: {len(df)} horse-starts, {df['race_id'].nunique()} races, "
      f"{df['race_date'].min().date()} -> {df['race_date'].max().date()}")

# ============================ GATE B ============================
def boot_ci(num, den, reps=2000, seed=SEED):
    num = np.asarray(num,float); den = np.asarray(den,float); n=len(num)
    rng = np.random.default_rng(seed); out=np.empty(reps)
    for b in range(reps):
        idx = rng.integers(0,n,n)
        out[b] = num[idx].sum()/den[idx].sum()
    return float(np.percentile(out,2.5)), float(np.percentile(out,97.5))
val = df.dropna(subset=["implied_place"])
ratio_all = val["placed"].sum()/val["implied_place"].sum()
lo,hi = boot_ci(val["placed"], val["implied_place"])
print("\n" + "="*66); print("GATE B — pipeline sanity sum(placed)/sum(implied_place)"); print("="*66)
print(f"ratio={ratio_all:.4f}  95% CI [{lo:.4f}, {hi:.4f}]  (require CI contains 1.0)  "
      f"-> {'PASS' if lo<=1.0<=hi else 'FAIL'}")

# ---- worked sign example ----
ex = df.sort_values("MONEY_IN", ascending=False).iloc[0]
print("\nWORKED SIGN EXAMPLE (largest MONEY_IN, should have odds_2 < odds_25):")
print(f"  race {ex['race_id']} horse {ex['horse_num']}: odds_25={ex['odds_25']} odds_2={ex['odds_2']} "
      f"p_25={ex['p_25']:.4f} p_2={ex['p_2']:.4f} MONEY_IN={ex['MONEY_IN']:+.3f} "
      f"(odds shortened -> money in: {'OK' if ex['odds_2']<ex['odds_25'] else 'CHECK'})")

df.to_pickle(f"{OUT}/drift_table.pkl")
print(f"\nsaved drift_table.pkl")
