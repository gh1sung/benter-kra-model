"""
SURGE build — Step 0a (truncation check) + Step 0b (join) for the real
SURGE feature, using the 25분전 win-odds snapshot.

SURGE (starting definition, per plan): is_unranked==1 AND rank_25 <= 5,
where rank_25 = popularity rank by 25분전 단승식(win) odds (1 = shortest odds).
Rank is computed within the RECORDED set only (never uses absence), which is
robust to snapshot truncation.
"""
import csv, sys, json, pickle
import numpy as np
sys.path.insert(0, "/sessions/admiring-zealous-brahmagupta/mnt/.projects/019f5bac-fecf-767f-8ca3-4b430e3d20e8/docs")
from harville_engine import place_probs

BASE = "/sessions/admiring-zealous-brahmagupta/mnt"
PROJ = BASE + "/.projects/019f5bac-fecf-767f-8ca3-4b430e3d20e8/files"
EXPERT = BASE + "/uploads/expert_score_seoul_busan.csv"
EARLY  = BASE + "/uploads/early_odds_5point.csv"
ODDS   = PROJ + "/35d1adcd-d3eb-4acb-9730-c5ce4e682ff3.csv"
RESULT = PROJ + "/527007ac-12ba-4104-92f5-1c2e5799b3b1.csv"
LAM = 0.8
REGION_CODE = {"서울":"01","부산":"03","부산경남":"03","제주":"02"}

# ---- expert ----
expert={}
with open(EXPERT) as f:
    for row in csv.DictReader(f):
        rid=row["race_id"].strip().strip('"'); hn=int(row["horse_num"])
        expert[(rid,hn)]={"is_unranked":int(row["is_unranked"]),
                          "expert_score":float(row["expert_score"]),
                          "region":row["region"].strip().strip('"')}

# ---- results ----
results={}
with open(RESULT) as f:
    for row in csv.DictReader(f):
        rid=row["race_id"].strip(); n=int(row["n_starters"])
        results[rid]={"n_starters":n,
                      "top2":set(x for x in row["top2_pair"].split("|") if x),
                      "top3":set(x for x in row["top3_triple"].split("|") if x),
                      "region":row["region"].strip()}

# ---- final odds ----
odds_by_race={}
with open(ODDS) as f:
    for row in csv.DictReader(f):
        rc=REGION_CODE.get(row["track"].strip())
        if rc is None: continue
        rid=f"{row['date'].strip()}{rc}{int(row['race_no']):02d}"
        try: o=float(row["odds"])
        except ValueError: continue
        hn=int(row["gate_no"])
        if o>0: odds_by_race.setdefault(rid,{})[hn]=o

# ---- 25분전 snapshot -> rank_25 ----
snap25={}   # rid -> {horse_num: win_odds_25}
with open(EARLY) as f:
    for row in csv.DictReader(f):
        if row["minutes_before_post"].strip()!="25": continue
        rid=row["race_id"].strip()
        try: js=json.loads(row["snapshot"])
        except Exception: continue
        win=js.get("단승식",{})
        d={}
        for k,v in win.items():
            try:
                hn=int(k); o=float(v)
                if o>0: d[hn]=o
            except (ValueError,TypeError): continue
        if d: snap25[rid]=d
print(f"races with 25분전 win snapshot: {len(snap25)}")

# ---- STEP 0a: truncation check ----
print("\n"+"="*66)
print("STEP 0a — snapshot completeness (n_recorded vs n_actual_starters)")
print("="*66)
diffs=[]; rows_chk=[]
for rid,d in snap25.items():
    res=results.get(rid)
    if not res: continue
    nr=len(d); na=res["n_starters"]
    diffs.append(nr-na); rows_chk.append((nr,na))
diffs=np.array(diffs)
print(f"races checked: {len(diffs)}")
print(f"n_recorded == n_starters : {(diffs==0).mean()*100:.1f}%")
print(f"n_recorded  < n_starters : {(diffs<0).mean()*100:.1f}%  (mean shortfall {diffs[diffs<0].mean() if (diffs<0).any() else 0:.2f})")
print(f"n_recorded  > n_starters : {(diffs>0).mean()*100:.1f}%")
nr_arr=np.array([a for a,b in rows_chk]); na_arr=np.array([b for a,b in rows_chk])
# is there a fixed cap?
from collections import Counter
print("max n_recorded seen:", nr_arr.max(), "| distribution of n_recorded:",
      dict(sorted(Counter(nr_arr.tolist()).items())))
# completeness over time? split by half
print("(if n_recorded tracks n_starters and no fixed ceiling -> snapshots complete)")

# ---- build rank_25 ----
rank25={}   # (rid,hn)->rank ; also n_recorded
for rid,d in snap25.items():
    order=sorted(d.keys(), key=lambda h:(d[h],h))  # shortest odds first
    for i,h in enumerate(order,1):
        rank25[(rid,h)]=i

# ---- implied placement ----
cache={}
def implied_place(rid,top):
    key=(rid,top)
    if key in cache: return cache[key]
    od=odds_by_race[rid]; hns=sorted(od)
    inv=np.array([1.0/od[h] for h in hns]); p=inv/inv.sum()
    pp=place_probs({h:p[i] for i,h in enumerate(hns)},top=top,lam=LAM)
    cache[key]=pp; return pp

# ---- assemble: horse-starts in the 1,956-race snapshot scope ----
rows=[]
js2={"snap_races":len(snap25),"no_expert":0,"no_result":0,"small":0,
     "no_odds":0,"no_horse_odds":0,"no_rank":0,"ok":0}
for rid in snap25:
    res=results.get(rid)
    if not res: js2["no_result"]+=1; continue
    n=res["n_starters"]
    if n<=4: js2["small"]+=1; continue
    top=2 if n<=7 else 3
    od=odds_by_race.get(rid)
    if od is None: js2["no_odds"]+=1; continue
    for hn in snap25[rid]:
        e=expert.get((rid,hn))
        if e is None: js2["no_expert"]+=1; continue
        if hn not in od: js2["no_horse_odds"]+=1; continue
        rk=rank25.get((rid,hn))
        if rk is None: js2["no_rank"]+=1; continue
        placed=1 if str(hn) in (res["top2"] if top==2 else res["top3"]) else 0
        implied=implied_place(rid,top).get(hn)
        if implied is None: continue
        js2["ok"]+=1
        rows.append({"race_id":rid,"horse_num":hn,"region":e["region"],
            "is_unranked":e["is_unranked"],"expert_score":e["expert_score"],
            "n_starters":n,"top":top,"placed":placed,"implied":implied,
            "odds":od[hn],"rank_25":rk,"odds_25":snap25[rid][hn],
            "n_recorded":len(snap25[rid])})
print("\njoin_stats:",js2)
print("assembled horse-starts (snapshot scope):",len(rows))
pickle.dump(rows,open("/sessions/admiring-zealous-brahmagupta/mnt/outputs/surge_rows.pkl","wb"))
