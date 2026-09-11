"""
lucky_build.py — Lucky Engine Execution Plan, Step 3.1 + 3.2 inputs.

Rebuilds the two data inputs that were regenerable working files (not saved):
  1. surge_rows  — early-odds joined scope (odds_25, rank_25, expert, placed,
                   implied, odds, n_starters). Faithful port of surge_build.py.
  2. fund_p      — fundamental Gate-2 win prob, from the no-distance-limit
                   10-variable model (baseline-9 + CAREER_STARTS), trained on
                   2008-2021, scored on 2022-2026. Reproduces the archetype
                   fundamental axis (day8 §1.5, target train pseudo-R2 ~0.1254).

Then joins them into the 1,894-race early-odds analysis table, adds
exp_rank_in_race and the BUILD/TEST window flag, and reports the join rate
(plan Step 3.1 gate: flag if joined scope < ~1,200 races).

All raw inputs are the canonical copies in the user's Downloads folder.
Outputs: analysis_table.pkl (+ surge_rows.pkl) in the outputs dir.
"""
import csv, json, pickle
import numpy as np
import pandas as pd
from scipy.optimize import minimize

DL   = "/sessions/sweet-eager-noether/mnt/Downloads"
OUT  = "/sessions/sweet-eager-noether/mnt/outputs"
EXPERT = f"{DL}/expert_score_seoul_busan.csv"
EARLY  = f"{DL}/early_odds_5point.csv"
ODDS   = f"{DL}/win_odds_5yr.csv"
RESULT = f"{DL}/exotic_outcomes.csv"
GATE2  = f"{DL}/gate2_outputs/gate2_features_built.csv"
LAM = 0.8                       # Harville place-prob discount (project standard)
REGION_CODE = {"서울":"01","부산":"03","부산경남":"03","제주":"02"}

# ======================================================================
# PART A — surge_rows (faithful port of surge_build.py)
# ======================================================================
print("="*70); print("PART A — rebuilding surge_rows"); print("="*70)

import sys; sys.path.insert(0, f"{DL}")
# harville_engine lives in the project cache; copy the one function we need
sys.path.insert(0, "/sessions/sweet-eager-noether/mnt/.projects/019f5bac-fecf-767f-8ca3-4b430e3d20e8/docs")
from harville_engine import place_probs

expert = {}
with open(EXPERT) as f:
    for row in csv.DictReader(f):
        rid = row["race_id"].strip().strip('"'); hn = int(row["horse_num"])
        expert[(rid, hn)] = {"is_unranked": int(row["is_unranked"]),
                             "expert_score": float(row["expert_score"]),
                             "region": row["region"].strip().strip('"')}

results = {}
with open(RESULT) as f:
    for row in csv.DictReader(f):
        rid = str(row["race_id"]).strip(); n = int(row["n_starters"])
        results[rid] = {"n_starters": n,
                        "top2": set(x for x in row["top2_pair"].split("|") if x),
                        "top3": set(x for x in row["top3_triple"].split("|") if x),
                        "region": row["region"].strip()}

odds_by_race = {}
with open(ODDS) as f:
    for row in csv.DictReader(f):
        rc = REGION_CODE.get(row["track"].strip())
        if rc is None: continue
        rid = f"{str(row['date']).strip()}{rc}{int(row['race_no']):02d}"
        try: o = float(row["odds"])
        except ValueError: continue
        hn = int(row["gate_no"])
        if o > 0: odds_by_race.setdefault(rid, {})[hn] = o

snap25 = {}
with open(EARLY) as f:
    for row in csv.DictReader(f):
        if row["minutes_before_post"].strip() != "25": continue
        rid = str(row["race_id"]).strip()
        try: js = json.loads(row["snapshot"])
        except Exception: continue
        win = js.get("단승식", {})
        d = {}
        for k, v in win.items():
            try:
                hn = int(k); o = float(v)
                if o > 0: d[hn] = o
            except (ValueError, TypeError): continue
        if d: snap25[rid] = d
print(f"races with 25분전 win snapshot: {len(snap25)}")

rank25 = {}
for rid, d in snap25.items():
    order = sorted(d.keys(), key=lambda h: (d[h], h))
    for i, h in enumerate(order, 1):
        rank25[(rid, h)] = i

cache = {}
def implied_place(rid, top):
    key = (rid, top)
    if key in cache: return cache[key]
    od = odds_by_race[rid]; hns = sorted(od)
    inv = np.array([1.0/od[h] for h in hns]); p = inv/inv.sum()
    pp = place_probs({h: p[i] for i, h in enumerate(hns)}, top=top, lam=LAM)
    cache[key] = pp; return pp

rows = []
js2 = {"snap_races": len(snap25), "no_expert": 0, "no_result": 0, "small": 0,
       "no_odds": 0, "no_horse_odds": 0, "no_rank": 0, "ok": 0}
for rid in snap25:
    res = results.get(rid)
    if not res: js2["no_result"] += 1; continue
    n = res["n_starters"]
    if n <= 4: js2["small"] += 1; continue
    top = 2 if n <= 7 else 3
    od = odds_by_race.get(rid)
    if od is None: js2["no_odds"] += 1; continue
    for hn in snap25[rid]:
        e = expert.get((rid, hn))
        if e is None: js2["no_expert"] += 1; continue
        if hn not in od: js2["no_horse_odds"] += 1; continue
        rk = rank25.get((rid, hn))
        if rk is None: js2["no_rank"] += 1; continue
        placed = 1 if str(hn) in (res["top2"] if top == 2 else res["top3"]) else 0
        implied = implied_place(rid, top).get(hn)
        if implied is None: continue
        js2["ok"] += 1
        rows.append({"race_id": rid, "horse_num": hn, "region": e["region"],
                     "is_unranked": e["is_unranked"], "expert_score": e["expert_score"],
                     "n_starters": n, "top": top, "placed": placed, "implied": implied,
                     "odds": od[hn], "rank_25": rk, "odds_25": snap25[rid][hn],
                     "n_recorded": len(snap25[rid])})
print("join_stats:", js2)
surge = pd.DataFrame(rows)
surge["race_date"] = pd.to_datetime(surge["race_id"].str[:8], format="%Y%m%d")
print(f"surge_rows: {len(surge)} rows, {surge['race_id'].nunique()} races, "
      f"{surge['race_date'].min().date()} -> {surge['race_date'].max().date()}")
pickle.dump(rows, open(f"{OUT}/surge_rows.pkl", "wb"))

# ======================================================================
# PART B — fund_p (no-distance-limit 10-var fundamental model)
# ======================================================================
print("\n" + "="*70); print("PART B — rebuilding fund_p"); print("="*70)
VARS = ["CAREER_STARTS", "AVESPRAT", "LSPEDRAT", "WEIGHT", "JOCK_PCT_WIN",
        "W_PER_RACE", "LIFE_PCT_WIN", "NEWDIST", "JOCK_NUM_WIN", "POSTPOS"]
RIDGE = 100.0   # Gate2 final selected lambda

g = pd.read_csv(GATE2)
g["race_date"] = pd.to_datetime(g["race_date"])
g["year"] = g["race_date"].dt.year

# day8 §1.5: retrained on 2008-2021 with NO 1600-2000m restriction and
# "maximum data" -> feature-completeness only (no track/age filter), with the
# audited race-safe rule (drop a race unless its winner has complete features).
complete = g.dropna(subset=VARS).copy()
train_pool = complete[complete["year"] <= 2021].copy()
# race-safe: keep race only if the winner (is_win==1) survived feature-completeness
win_ok = train_pool.groupby("race_id")["is_win"].transform("max") == 1
train = train_pool[win_ok].copy()
fs = train.groupby("race_id")["race_id"].transform("size")
train = train[fs >= 2].copy()
print(f"train (2008-2021): {len(train)} rows, {train['race_id'].nunique()} races "
      f"(day8 target ~247,866 rows / 24,026 races)")

# E=1 explosion == one choice set per race; chosen = the actual winner (is_win)
def explode_e1(sample, var_list):
    recs = []; cid = 0
    for rid, grp in sample.groupby("race_id", sort=False):
        if len(grp) < 2 or grp["is_win"].max() != 1: continue
        cid += 1
        grp = grp.sort_values("is_win", ascending=False)   # winner first
        for pos, (_, h) in enumerate(grp.iterrows()):
            rec = {c: h[c] for c in var_list}
            rec["choice_set_id"] = cid; rec["chosen"] = int(h["is_win"])
            recs.append(rec)
    return pd.DataFrame(recs)

exp = explode_e1(train, VARS).reset_index(drop=True)
gids = exp["choice_set_id"].to_numpy()
starts = np.r_[0, np.flatnonzero(gids[1:] != gids[:-1]) + 1]
sizes = np.diff(np.r_[starts, len(exp)])
Xraw = exp[VARS].to_numpy(float)
mu = Xraw.mean(0); sigma = np.where(Xraw.std(0) == 0, 1.0, Xraw.std(0))
X = (Xraw - mu) / sigma

def nll_grad(beta, X, starts, lam):
    s = X @ beta
    mx = np.maximum.reduceat(s, starts)
    sh = s - np.repeat(mx, np.diff(np.r_[starts, len(s)]))
    es = np.exp(sh); sm = np.add.reduceat(es, starts)
    rs = np.repeat(sm, np.diff(np.r_[starts, len(s)]))
    ll = np.sum(sh[starts] - np.log(sm))
    expd = np.add.reduceat(X * (es/rs)[:, None], starts, axis=0)
    grad = -np.sum(X[starts] - expd, axis=0)
    return -ll + lam*np.sum(beta**2), grad + 2*lam*beta

res = minimize(nll_grad, np.zeros(len(VARS)), args=(X, starts, RIDGE),
               method="BFGS", jac=True, options={"maxiter": 3000, "gtol": 1e-6})
beta = res.x
ll_model = -(nll_grad(beta, X, starts, RIDGE)[0] - RIDGE*np.sum(beta**2))
ll_null = -np.log(sizes).sum()
print(f"converged={res.success}  train pseudo-R2={1 - ll_model/ll_null:.4f}  "
      f"(day8 target ~0.1254)")
print("betas:", {v: round(b, 3) for v, b in zip(VARS, beta)})

# score every 2022-2026 horse with complete features: per-race softmax -> fund_p
score = complete[complete["year"] >= 2022].copy()
Xs = (score[VARS].to_numpy(float) - mu) / sigma
score["_util"] = Xs @ beta
score["_e"] = np.exp(score["_util"] - score.groupby("race_id")["_util"].transform("max"))
score["fund_p"] = score["_e"] / score.groupby("race_id")["_e"].transform("sum")
fund = score[["race_id", "back_num", "fund_p"]].copy()
print(f"scored fund_p: {len(fund)} rows, {fund['race_id'].nunique()} races (2022-2026)")

# ======================================================================
# PART C — join into analysis table (plan Step 3.1)
# ======================================================================
print("\n" + "="*70); print("PART C — join + join-rate gate"); print("="*70)
surge["race_id_int"] = surge["race_id"].astype("int64")
m = surge.merge(fund, left_on=["race_id_int", "horse_num"],
                right_on=["race_id", "back_num"], how="left", suffixes=("", "_g"))
n_races_before = surge["race_id"].nunique()
joined = m.dropna(subset=["fund_p"]).copy()
n_races_after = joined["race_id"].nunique()
print(f"early-odds scope races: {n_races_before}")
print(f"rows with fund_p:       {len(joined)} / {len(surge)} "
      f"({100*len(joined)/len(surge):.1f}%)")
print(f"races surviving join:   {n_races_after}")
if n_races_after < 1200:
    print("  *** GATE WARNING: joined scope < 1,200 races — downstream n shrinks ***")
else:
    print("  GATE OK: joined scope >= 1,200 races")

# exp_rank_in_race: within-race ascending percentile of expert_score (low = dismissed)
joined["exp_rank_in_race"] = joined.groupby("race_id")["expert_score"].rank(
    method="average", pct=True)
joined["ln_odds_25"] = np.log(joined["odds_25"])

# BUILD/TEST window
joined["window"] = np.where(joined["race_date"] <= pd.Timestamp("2026-02-28"),
                            "BUILD", "TEST")
# guard: TEST is strictly 2026-03-01 .. 2026-07-19
joined = joined[joined["race_date"] <= pd.Timestamp("2026-07-19")].copy()
print("\nwindow race counts:")
print(joined.groupby("window")["race_id"].nunique())
print("date ranges:")
for w, sub in joined.groupby("window"):
    print(f"  {w}: {sub['race_date'].min().date()} -> {sub['race_date'].max().date()}")

joined.to_pickle(f"{OUT}/analysis_table.pkl")
print(f"\nsaved analysis_table.pkl: {len(joined)} rows, {n_races_after} races")
