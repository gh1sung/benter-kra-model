import pickle, numpy as np
np.random.seed(7)
rows = pickle.load(open("/sessions/admiring-zealous-brahmagupta/mnt/outputs/rows.pkl","rb"))
R = rows
def arr(sub, k): return np.array([r[k] for r in sub])

def block(sub, label):
    placed = arr(sub,"placed").astype(float)
    implied = arr(sub,"implied").astype(float)
    n = len(sub)
    act = placed.sum(); exp = implied.sum()
    ratio = act/exp if exp>0 else float("nan")
    return n, act, exp, placed.mean(), implied.mean(), ratio

def boot_ratio(sub, reps=2000):
    placed = arr(sub,"placed").astype(float)
    implied = arr(sub,"implied").astype(float)
    n = len(sub); idx = np.arange(n)
    out = np.empty(reps)
    for b in range(reps):
        s = np.random.randint(0, n, n)
        e = implied[s].sum()
        out[b] = placed[s].sum()/e if e>0 else np.nan
    lo, hi = np.nanpercentile(out, [2.5, 97.5])
    return lo, hi

print("="*70)
print("SANITY / CALIBRATION — ALL horse-starts (pipeline check)")
print("="*70)
n,act,exp,pa,pi,rat = block(R,"all")
print(f"n={n}  actual_placed={act:.0f}  implied_placed={exp:.1f}  "
      f"actual%={pa:.4f}  implied%={pi:.4f}  ratio={rat:.4f}")
lo,hi = boot_ratio(R)
print(f"  ratio 95% CI [{lo:.4f}, {hi:.4f}]  (should straddle ~1.0 if odds calibrated)")

UNR = [r for r in R if r["is_unranked"]==1]
RANK = [r for r in R if r["is_unranked"]==0]

print("\n"+"="*70)
print("NAIVE — placed% by group (uncorrected, expected to differ by odds)")
print("="*70)
print(f"is_unranked=1 (expert-dismissed): n={len(UNR)}  placed%={arr(UNR,'placed').mean():.4f}  mean_odds={arr(UNR,'odds').mean():.1f}")
print(f"is_unranked=0 (expert-picked)  : n={len(RANK)}  placed%={arr(RANK,'placed').mean():.4f}  mean_odds={arr(RANK,'odds').mean():.1f}")

print("\n"+"="*70)
print("ODDS-IMPLIED TEST — is_unranked=1 (the real question)")
print("="*70)
n,act,exp,pa,pi,rat = block(UNR,"unr")
lo,hi = boot_ratio(UNR)
print(f"n={n}")
print(f"actual placed count   = {act:.0f}   ({pa:.4f})")
print(f"odds-implied expected = {exp:.1f}   ({pi:.4f})")
print(f"RATIO actual/implied  = {rat:.4f}   95% CI [{lo:.4f}, {hi:.4f}]")
print(f"CI excludes 1.0? {'YES' if (lo>1 or hi<1) else 'NO'}")

print("\n"+"="*70)
print("CONFOUND 0d-1 — general favorite/longshot bias (ALL horses, by odds bucket)")
print("odds bucket : n : actual% : implied% : ratio  (ratio>1 = underbet/overperforms price)")
print("="*70)
edges = [1,2,3,5,8,15,30,1e9]
labels = ["<2","2-3","3-5","5-8","8-15","15-30","30+"]
odds = arr(R,"odds"); placed=arr(R,"placed").astype(float); implied=arr(R,"implied").astype(float)
for i in range(len(edges)-1):
    m = (odds>=edges[i])&(odds<edges[i+1])
    if m.sum()==0: continue
    a=placed[m].sum(); e=implied[m].sum()
    print(f"{labels[i]:>6} : {m.sum():6d} : {placed[m].mean():.4f} : {implied[m].mean():.4f} : {a/e:.4f}")

print("\n"+"="*70)
print("CONFOUND 0d-2 — field size (is_unranked=1 only)")
print("field : n : actual% : implied% : ratio")
print("="*70)
ns = arr(UNR,"n_starters")
for fs in sorted(set(ns.tolist())):
    sub=[r for r in UNR if r["n_starters"]==fs]
    if len(sub)<20: continue
    a=arr(sub,"placed").sum(); e=arr(sub,"implied").sum()
    print(f"{fs:5d} : {len(sub):5d} : {arr(sub,'placed').mean():.4f} : {arr(sub,'implied').mean():.4f} : {a/e:.4f}")

print("\n"+"="*70)
print("CONFOUND 0d-3 — region split (is_unranked=1)")
print("="*70)
for reg in ["서울","부산"]:
    sub=[r for r in UNR if r["region"]==reg]
    if not sub: continue
    n,act,exp,pa,pi,rat = block(sub,reg)
    lo,hi=boot_ratio(sub)
    print(f"{reg}: n={n}  actual={act:.0f}  implied={exp:.1f}  ratio={rat:.4f}  CI[{lo:.4f},{hi:.4f}]")

# sensitivity: lam=1.0 rerun would need re-derive; report note only.
print("\nDONE")
