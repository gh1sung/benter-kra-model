import pandas as pd, numpy as np, time
from scipy.optimize import minimize
U="/sessions/lucid-eloquent-euler/mnt/uploads/"
df=pd.read_csv(U+"gate2_features_built.csv", low_memory=False).sort_values("race_id").reset_index(drop=True)

BASE=["AVESPRAT","LSPEDRAT","NEWDIST","WEIGHT","POSTPOS","JOCK_PCT_WIN",
      "TRAINER_PCT_WIN","LIFE_PCT_WIN","CAREER_STARTS","DAYS_SINCE_LAST_RACE"]
ABIL=["AVESPRAT","LSPEDRAT","LIFE_PCT_WIN"]   # horse-ability features to interact

def z(col):
    v=pd.to_numeric(df[col],errors="coerce").astype(float).values
    mu=np.nanmean(v); sd=np.nanstd(v); zz=(v-mu)/sd; zz[np.isnan(zz)]=0.0
    return zz
Z={c:z(c) for c in set(BASE)}

# low-info flags
low2={'국6','국5','국미승','국신마','혼3','혼4','혼5','외2','외3','외미승'}
lowclass=df.race_class.isin(low2).values.astype(float)
lowcs=(df.CAREER_STARTS.fillna(0).values<5).astype(float)

y=df.is_win.values.astype(float)
codes,uniq=pd.factorize(df.race_id.values); R=len(uniq)
# already sorted by race_id so groups are contiguous
starts=np.searchsorted(codes,np.arange(R))
bounds=np.append(starts,len(codes))
seg_id=codes  # group id per row (contiguous 0..R-1)

def build_design(flag):
    cols=[Z[c] for c in BASE]
    names=list(BASE)
    cols.append(flag); names.append("low_info")
    for a in ABIL:
        cols.append(flag*Z[a]); names.append(f"low_x_{a}")
    return np.column_stack(cols), names

def fitter(X, lam=1e-4):
    starts_l=starts
    def ng(beta):
        eta=X@beta
        mx=np.maximum.reduceat(eta,starts_l)          # per-group max
        etam=eta-mx[seg_id]
        e=np.exp(etam)
        Zsum=np.add.reduceat(e,starts_l)
        logZ=np.log(Zsum)+mx
        nll=-(y*(eta-logZ[seg_id])).sum()
        p=e/Zsum[seg_id]
        schosen=np.add.reduceat(y,starts_l)           # winners per group
        grad=-X.T@(y - schosen[seg_id]*p)
        return nll+lam*beta@beta, grad+2*lam*beta
    r=minimize(ng,np.zeros(X.shape[1]),jac=True,method="L-BFGS-B",options={"maxiter":300})
    return r.x

for label,flag in [("CLASS cut (bottom2)",lowclass),("CAREER_STARTS cut (<5)",lowcs)]:
    X,names=build_design(flag)
    t=time.time(); beta=fitter(X); ft=time.time()-t
    print(f"\n==== {label} ====   (fit {ft:.2f}s)")
    d=dict(zip(names,beta))
    for n in names: print(f"  {n:22} {d[n]:+.4f}")
    # save point estimates
    np.save(f"beta_{label[:5]}.npy",beta)
