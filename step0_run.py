"""
Step 0 (executable subset) — expert-dismissed (is_unranked) horses vs. their
FINAL-odds-implied placement.

NOTE: the full plan's SURGE feature needs 25/15/10/6/2-min snapshot odds
(early_odds_5point.csv). That file is NOT in the available data, so SURGE
cannot be built. This script runs the part that IS executable: does the group
of horses that ZERO experts picked (사전인기 dismissed) place more/less often
than their own FINAL win odds imply? That is Step 0c's odds-implied logic
applied to is_unranked alone (no early-surge filter).
"""
import csv, sys
import numpy as np
sys.path.insert(0, "/sessions/admiring-zealous-brahmagupta/mnt/.projects/019f5bac-fecf-767f-8ca3-4b430e3d20e8/docs")
from harville_engine import place_probs

BASE = "/sessions/admiring-zealous-brahmagupta/mnt"
PROJ = BASE + "/.projects/019f5bac-fecf-767f-8ca3-4b430e3d20e8/files"
EXPERT = BASE + "/uploads/expert_score_seoul_busan.csv"
ODDS   = PROJ + "/35d1adcd-d3eb-4acb-9730-c5ce4e682ff3.csv"   # final win odds
RESULT = PROJ + "/527007ac-12ba-4104-92f5-1c2e5799b3b1.csv"   # race results
LAM = 0.8   # validated in Piece A

REGION_CODE = {"서울": "01", "부산": "03", "부산경남": "03", "제주": "02"}

# ---------- load expert_score ----------
expert = {}
races_expert = set()
with open(EXPERT) as f:
    for row in csv.DictReader(f):
        rid = row["race_id"].strip().strip('"')
        hn = int(row["horse_num"])
        expert[(rid, hn)] = {
            "is_unranked": int(row["is_unranked"]),
            "expert_score": float(row["expert_score"]),
            "region": row["region"].strip().strip('"'),
        }
        races_expert.add(rid)
print(f"expert rows: {len(expert)}, races: {len(races_expert)}")

# ---------- load results ----------
results = {}
with open(RESULT) as f:
    for row in csv.DictReader(f):
        rid = row["race_id"].strip()
        n = int(row["n_starters"])
        top2 = set(x for x in row["top2_pair"].split("|") if x)
        top3 = set(x for x in row["top3_triple"].split("|") if x)
        results[rid] = {"n_starters": n, "top2": top2, "top3": top3,
                        "region": row["region"].strip()}
print(f"result races: {len(results)}")

# ---------- load final odds ----------
odds_by_race = {}
with open(ODDS) as f:
    for row in csv.DictReader(f):
        date = row["date"].strip(); track = row["track"].strip()
        rc = REGION_CODE.get(track)
        if rc is None:
            continue
        rno = int(row["race_no"]); rid = f"{date}{rc}{rno:02d}"
        try:
            o = float(row["odds"])
        except ValueError:
            continue
        hn = int(row["gate_no"])
        if o <= 0:
            continue
        odds_by_race.setdefault(rid, {})[hn] = o
print(f"odds races: {len(odds_by_race)}")

implied_cache = {}
def implied_place_for_race(rid, top):
    key = (rid, top)
    if key in implied_cache:
        return implied_cache[key]
    od = odds_by_race[rid]
    hns = sorted(od.keys())
    inv = np.array([1.0/od[h] for h in hns])
    p = inv / inv.sum()
    pp = place_probs({h: p[i] for i, h in enumerate(hns)}, top=top, lam=LAM)
    implied_cache[key] = pp
    return pp

rows = []
js = {"in_expert":0,"no_result":0,"small_field":0,"no_odds_race":0,"no_horse_odds":0,"ok":0}
for (rid, hn), e in expert.items():
    js["in_expert"] += 1
    res = results.get(rid)
    if res is None:
        js["no_result"] += 1; continue
    n = res["n_starters"]
    if n <= 4:
        js["small_field"] += 1; continue
    top = 2 if n <= 7 else 3
    od = odds_by_race.get(rid)
    if od is None:
        js["no_odds_race"] += 1; continue
    if hn not in od:
        js["no_horse_odds"] += 1; continue
    placed_set = res["top2"] if top == 2 else res["top3"]
    placed = 1 if str(hn) in placed_set else 0
    pp = implied_place_for_race(rid, top)
    implied = pp.get(hn)
    if implied is None:
        continue
    js["ok"] += 1
    rows.append({"race_id": rid, "horse_num": hn, "region": e["region"],
        "is_unranked": e["is_unranked"], "expert_score": e["expert_score"],
        "n_starters": n, "top": top, "placed": placed, "implied": implied,
        "odds": od[hn]})

print("join_stats:", js)
print(f"assembled horse-starts: {len(rows)}")
import pickle
with open("/sessions/admiring-zealous-brahmagupta/mnt/outputs/rows.pkl", "wb") as fh:
    pickle.dump(rows, fh)
