import pickle, numpy as np
np.random.seed(7)
R=pickle.load(open("/sessions/admiring-zealous-brahmagupta/mnt/outputs/surge_rows.pkl","rb"))
def a(s,k): return np.array([r[k] for r in s])

def ratio_ci(sub, reps=2000):
    if len(sub)==0: return (0,0,0,float("nan"),(float("nan"),float("nan")))
    placed=a(sub,"placed").astype(float); implied=a(sub,"implied").astype(float)
    act=placed.sum(); exp=implied.sum(); rat=act/exp if exp>0 else float("nan")
    n=len(sub); out=np.empty(reps)
    for b in range(reps):
        s=np.random.randint(0,n,n); e=implied[s].sum()
        out[b]=placed[s].sum()/e if e>0 else np.nan
    lo,hi=np.nanpercentile(out,[2.5,97.5])
    return n,act,exp,rat,(lo,hi)

print("SCOPE: 1,955 races (25분전 snapshot overlap), horse-starts:",len(R))
UNR=[r for r in R if r["is_unranked"]==1]
print(f"is_unranked=1 in scope: {len(UNR)}")

# ---- pipeline sanity in this scope ----
n,act,exp,rat,ci=ratio_ci(R)
print(f"\nCALIBRATION (all {n}): actual={act:.0f} implied={exp:.1f} ratio={rat:.4f} CI[{ci[0]:.3f},{ci[1]:.3f}]")

# ---- SURGE definitions at several rank thresholds ----
print("\n"+"="*70)
print("SURGE = is_unranked=1 AND rank_25 <= T   (rank_25: 1=shortest 25분전 odds)")
print("="*70)
print(f"{'T':>3} {'n_SURGE':>8} {'actual':>7} {'implied':>8} {'ratio':>7} {'95% CI':>18} {'naive_pl%':>10}")
for T in [3,5,8]:
    surge=[r for r in UNR if r["rank_25"]<=T]
    n,act,exp,rat,ci=ratio_ci(surge)
    plrate=a(surge,"placed").mean() if surge else float("nan")
    print(f"{T:>3} {n:>8} {act:>7.0f} {exp:>8.1f} {rat:>7.3f}  [{ci[0]:.3f}, {ci[1]:.3f}]  {plrate:>9.3f}")

# ---- primary definition T=5 ----
T=5
SURGE=[r for r in UNR if r["rank_25"]<=T]
NOSURGE=[r for r in UNR if r["rank_25"]>T]
print("\n"+"="*70)
print(f"PRIMARY: SURGE = is_unranked=1 AND rank_25<=5   (n={len(SURGE)})")
print("="*70)
print("\nNAIVE (uncorrected):")
print(f"  SURGE=1                  : n={len(SURGE):4d}  placed%={a(SURGE,'placed').mean():.4f}  mean_final_odds={a(SURGE,'odds').mean():.1f}  mean_25odds={a(SURGE,'odds_25').mean():.1f}")
print(f"  is_unranked=1 & SURGE=0  : n={len(NOSURGE):4d}  placed%={a(NOSURGE,'placed').mean():.4f}  mean_final_odds={a(NOSURGE,'odds').mean():.1f}  mean_25odds={a(NOSURGE,'odds_25').mean():.1f}")

print("\nODDS-IMPLIED (the real test):")
n,act,exp,rat,ci=ratio_ci(SURGE)
print(f"  n={n}")
print(f"  actual placed         = {act:.0f}  ({a(SURGE,'placed').mean():.4f})")
print(f"  final-odds-implied    = {exp:.1f}  ({exp/n:.4f})")
print(f"  RATIO actual/implied  = {rat:.4f}   95% CI [{ci[0]:.3f}, {ci[1]:.3f}]")
print(f"  CI excludes 1.0? {'YES' if (ci[0]>1 or ci[1]<1) else 'NO'}")

# non-surge dismissed for contrast
n2,act2,exp2,rat2,ci2=ratio_ci(NOSURGE)
print(f"\n  CONTRAST is_unranked & NON-surge (rank_25>5): n={n2} ratio={rat2:.3f} CI[{ci2[0]:.3f},{ci2[1]:.3f}]")
# all is_unranked in scope
n3,act3,exp3,rat3,ci3=ratio_ci(UNR)
print(f"  CONTRAST all is_unranked in scope:           n={n3} ratio={rat3:.3f} CI[{ci3[0]:.3f},{ci3[1]:.3f}]")

# ---- region split for SURGE ----
print("\n"+"="*70); print("CONFOUND — region split (SURGE, T=5)"); print("="*70)
for reg in ["서울","부산"]:
    sub=[r for r in SURGE if r["region"]==reg]
    n,act,exp,rat,ci=ratio_ci(sub)
    print(f"  {reg}: n={n} actual={act:.0f} implied={exp:.1f} ratio={rat:.3f} CI[{ci[0]:.3f},{ci[1]:.3f}]")

# ---- win (top-1) conversion, since Jihwan asked 'which horses win their final odds' ----
print("\n"+"="*70); print("WIN-market view (SURGE, T=5): do they win at their final-odds rate?"); print("="*70)
# implied win prob = normalized 1/final_odds within race; approximate via 1/odds share not stored per race here,
# so report simple: actual win via results? we only have placed; report placed already above.
# Provide the naive win proxy: fraction that were 1st is not in rows; skip. (placed is the 연승 metric.)
print("  (metric used throughout = 연승식 placed; win-only not separately stored)")

# save a compact SURGE table for hand-off
import csv as _csv
with open("/sessions/admiring-zealous-brahmagupta/mnt/outputs/surge_horses_T5.csv","w",newline="") as fh:
    w=_csv.DictWriter(fh,fieldnames=["race_id","horse_num","region","n_starters","rank_25","odds_25","final_odds","implied_placed_prob","placed"])
    w.writeheader()
    for r in SURGE:
        w.writerow({"race_id":r["race_id"],"horse_num":r["horse_num"],"region":r["region"],
            "n_starters":r["n_starters"],"rank_25":r["rank_25"],"odds_25":r["odds_25"],
            "final_odds":r["odds"],"implied_placed_prob":round(r["implied"],4),"placed":r["placed"]})
print("\nwrote surge_horses_T5.csv")
print("DONE")
