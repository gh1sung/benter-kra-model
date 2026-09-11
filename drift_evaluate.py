"""
drift_evaluate.py — DRIFT plan §4 (primary test) + §5 (robustness).
Deciles, price-banded terciles, bootstrap CIs, §4.4 stability swap.
Writes drift_results.json, drift_decile_table.csv, drift_price_banded.csv.
"""
import json
import numpy as np
import pandas as pd

OUT = "/sessions/sweet-eager-noether/mnt/outputs"
BOOT = 2000; SEED = 20260727
df = pd.read_pickle(f"{OUT}/drift_table.pkl").dropna(subset=["implied_place"]).copy()

# ---- §4.1 time split: chronological halves of the date range ----
d0, d1 = df["race_date"].min(), df["race_date"].max()
mid = d0 + (d1 - d0) / 2
df["window"] = np.where(df["race_date"] <= mid, "EARLY", "LATE")
# within-race percentile of MONEY_IN (removes race-level effects)
df["drift_pct_in_race"] = df.groupby("race_id")["MONEY_IN"].rank(pct=True)

split_info = {"range": [str(d0.date()), str(d1.date())], "split_date": str(mid.date()),
              "EARLY_races": int(df[df.window=="EARLY"].race_id.nunique()),
              "LATE_races":  int(df[df.window=="LATE"].race_id.nunique()),
              "EARLY_starts": int((df.window=="EARLY").sum()),
              "LATE_starts":  int((df.window=="LATE").sum())}
print("§4.1 split:", split_info)

def boot_ci_ratio(num, den, reps=BOOT, seed=SEED):
    num=np.asarray(num,float); den=np.asarray(den,float); n=len(num)
    if n==0 or den.sum()==0: return (np.nan,np.nan)
    rng=np.random.default_rng(seed); out=np.empty(reps)
    for b in range(reps):
        idx=rng.integers(0,n,n); dd=den[idx].sum()
        out[b]= num[idx].sum()/dd if dd>0 else np.nan
    return float(np.nanpercentile(out,2.5)), float(np.nanpercentile(out,97.5))

def decile_table(sub, outcome):
    imp_col = "implied_place" if outcome=="placed" else "implied_win"
    base = sub[outcome].mean()
    sub = sub.copy()
    sub["dec"] = np.clip((sub["drift_pct_in_race"]*10).astype(int),0,9)
    rows=[]
    for dcl in range(10):
        s = sub[sub.dec==dcl]
        if len(s)==0: continue
        act=s[outcome].mean(); imp=s[imp_col].mean()
        lo,hi=boot_ci_ratio(s[outcome], s[imp_col])
        rows.append({"decile":dcl+1,"n":int(len(s)),
            "mean_odds_final":round(float(s.odds_final.replace(9999.9,np.nan).mean()),1),
            "actual_rate":round(float(act),4),"implied_rate":round(float(imp),4),
            "ratio":round(float(act/imp),3) if imp>0 else None,
            "ratio_CI95":[round(lo,3),round(hi,3)],
            "lift_vs_base":round(float(act/base),3) if base>0 else None})
    return rows, float(base)

BANDS = [(1,3),(3,6),(6,12),(12,25),(25,60),(60,np.inf)]
def price_banded(sub):
    out=[]
    for lo,hi in BANDS:
        b = sub[(sub.odds_final>=lo)&(sub.odds_final<hi)].copy()
        if len(b)==0: continue
        # MONEY_IN terciles WITHIN band: bottom25 / mid50 / top25
        b["r"]=b["MONEY_IN"].rank(pct=True)
        b["tier"]=np.where(b.r<=0.25,"bottom25",np.where(b.r>=0.75,"top25","mid50"))
        for tier in ["bottom25","mid50","top25"]:
            c=b[b.tier==tier]
            if len(c)==0: continue
            act=c.placed.mean(); imp=c.implied_place.mean()
            lo_ci,hi_ci=boot_ci_ratio(c.placed,c.implied_place)
            out.append({"band":f"[{lo},{hi})","tier":tier,"n":int(len(c)),
                "mean_odds_final":round(float(c.odds_final.replace(9999.9,np.nan).mean()),1),
                "actual_place":round(float(act),4),"implied_place":round(float(imp),4),
                "ratio":round(float(act/imp),3) if imp>0 else None,
                "ratio_CI95":[round(lo_ci,3),round(hi_ci,3)],
                "CI_excludes_1": bool(hi_ci<1.0 or lo_ci>1.0),
                "eligible_n>=300": bool(len(c)>=300)})
    return out

results={"split":split_info,"deciles":{},"price_banded":{},"swap":{}}

print("\n"+"="*70); print("§4.2 DECILE TABLES"); print("="*70)
for win in ["LATE","EARLY"]:
    sub=df[df.window==win]
    for outcome in ["placed","won"]:
        rows,base=decile_table(sub,outcome)
        results["deciles"][f"{win}_{outcome}"]={"base":round(base,4),"rows":rows}
    # quick print: placed, decile 1 vs 10
    rp=results["deciles"][f"{win}_placed"]["rows"]
    d1r=next(r for r in rp if r["decile"]==1); d10r=next(r for r in rp if r["decile"]==10)
    print(f"{win} placed base={results['deciles'][f'{win}_placed']['base']}: "
          f"D1(money out) rate={d1r['actual_rate']} ratio={d1r['ratio']} | "
          f"D10(money in) rate={d10r['actual_rate']} ratio={d10r['ratio']} | "
          f"D10-D1={d10r['actual_rate']-d1r['actual_rate']:+.4f}")

print("\n"+"="*70); print("§4.3 PRICE-BANDED (placed), LATE window"); print("="*70)
for win in ["LATE","EARLY"]:
    results["price_banded"][win]=price_banded(df[df.window==win])
for r in results["price_banded"]["LATE"]:
    flag="" if r["eligible_n>=300"] else " [UNDERPOWERED]"
    star=" ***CI excl 1***" if r["CI_excludes_1"] and r["eligible_n>=300"] else ""
    print(f"  {r['band']:>10} {r['tier']:>8} n={r['n']:4d} odds~{r['mean_odds_final']:>6} "
          f"place={r['actual_place']:.3f} impl={r['implied_place']:.3f} ratio={r['ratio']} "
          f"CI{r['ratio_CI95']}{flag}{star}")

print("\n"+"="*70); print("§4.4 STABILITY SWAP — top-vs-bottom sign both directions"); print("="*70)
def top_bottom_diff(win):
    rows=results["deciles"][f"{win}_placed"]["rows"]
    d1r=next(r for r in rows if r["decile"]==1); d10r=next(r for r in rows if r["decile"]==10)
    return d10r["actual_rate"]-d1r["actual_rate"]
diff_late=top_bottom_diff("LATE"); diff_early=top_bottom_diff("EARLY")
flip = (diff_late*diff_early)<0
results["swap"]={"D10_minus_D1_LATE":round(diff_late,4),
                 "D10_minus_D1_EARLY":round(diff_early,4),
                 "sign_flip":bool(flip)}
print(f"  D10-D1 place-rate diff:  LATE={diff_late:+.4f}   EARLY={diff_early:+.4f}")
print(f"  sign flip between directions? {'YES -> result is DEAD (§4.4)' if flip else 'NO -> direction holds'}")

# ---- §5 robustness (only meaningful if §4.4 holds; computed regardless, reported conditionally) ----
def money_signal(sub, feat, outcome="placed"):
    sub=sub.copy(); sub["pct"]=sub.groupby("race_id")[feat].rank(pct=True)
    sub["dec"]=np.clip((sub["pct"]*10).astype(int),0,9)
    base=sub[outcome].mean()
    d1=sub[sub.dec==0][outcome].mean(); d10=sub[sub.dec==9][outcome].mean()
    return round(d10-d1,4), round(d10/base,3), round(d1/base,3)
rob={}
late=df[df.window=="LATE"]
rob["MONEY_IN_prob"]=money_signal(late,"MONEY_IN")
rob["MONEY_IN_RAW"]=money_signal(late,"MONEY_IN_RAW")
for reg in ["서울","부산"]:
    rob[f"region_{reg}"]=money_signal(late[late.region==reg],"MONEY_IN")
for lab,(a,b) in {"fs_5_7":(5,7),"fs_8_10":(8,10),"fs_11p":(11,99)}.items():
    rob[lab]=money_signal(late[(late.n_starters>=a)&(late.n_starters<=b)],"MONEY_IN")
results["robustness_5"]=rob
print("\n"+"="*70); print("§5 ROBUSTNESS (LATE, placed): (D10-D1 diff, D10 lift, D1 lift)"); print("="*70)
for k,v in rob.items(): print(f"  {k:>16}: {v}")

json.dump(results, open(f"{OUT}/drift_results.json","w"), indent=2)
# CSVs
dec_rows=[]
for key,blk in results["deciles"].items():
    for r in blk["rows"]:
        dec_rows.append({"window_outcome":key,"base":blk["base"],**r})
pd.DataFrame(dec_rows).to_csv(f"{OUT}/drift_decile_table.csv",index=False)
pb_rows=[]
for win,lst in results["price_banded"].items():
    for r in lst: pb_rows.append({"window":win,**r})
pd.DataFrame(pb_rows).to_csv(f"{OUT}/drift_price_banded.csv",index=False)
print("\nsaved drift_results.json, drift_decile_table.csv, drift_price_banded.csv")
