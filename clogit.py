import pandas as pd, numpy as np
from scipy.optimize import minimize
U="/sessions/lucid-eloquent-euler/mnt/uploads/"
df=pd.read_csv(U+"gate2_features_built.csv", low_memory=False)
df=df.sort_values(["race_id"]).reset_index(drop=True)

FEATS=["AVESPRAT","LSPEDRAT","NEWDIST","WEIGHT","POSTPOS","JOCK_PCT_WIN",
       "TRAINER_PCT_WIN","LIFE_PCT_WIN","CAREER_STARTS","DAYS_SINCE_LAST_RACE"]

# standardize (z), impute missing -> 0 (=mean). race_safe: keep all rows.
X=np.zeros((len(df),len(FEATS)))
for j,c in enumerate(FEATS):
    v=pd.to_numeric(df[c],errors="coerce").astype(float).values
    mu=np.nanmean(v); sd=np.nanstd(v)
    z=(v-mu)/sd
    z[np.isnan(z)]=0.0
    X[:,j]=z
y=df.is_win.values.astype(float)

# race blocks
codes,uniq=pd.factorize(df.race_id.values)
R=len(uniq)
# precompute group index arrays
order=np.argsort(codes,kind="stable")
Xs=X[order]; ys=y[order]; cs=codes[order]
# boundaries
bounds=np.searchsorted(cs,np.arange(R))
bounds=np.append(bounds,len(cs))

lam=1e-4
def nll_grad(beta):
    eta=Xs@beta
    # per-race softmax normalizer via segment
    nll=0.0; grad=np.zeros_like(beta)
    # vectorized using np.add.reduceat
    m=np.empty(R)
    ex=np.empty(len(eta))
    # compute max per group for stability
    for r in range(R):
        a,b=bounds[r],bounds[r+1]
        seg=eta[a:b]
        mx=seg.max()
        e=np.exp(seg-mx)
        Z=e.sum()
        p=e/Z
        wsel=ys[a:b]
        nll-=(wsel*(seg-mx-np.log(Z))).sum()
        grad-=Xs[a:b].T@(wsel- wsel.sum()*p)
    nll+=lam*beta@beta; grad+=2*lam*beta
    return nll,grad

import time
t=time.time()
res=minimize(nll_grad,np.zeros(len(FEATS)),jac=True,method="L-BFGS-B",
             options={"maxiter":200})
print("fit time %.1fs, success=%s, iters=%d"%(time.time()-t,res.success,res.nit))
print("\n  feature                coef")
for c,b in zip(FEATS,res.x):
    print(f"  {c:22} {b:+.4f}")
print("\nCAREER_STARTS coef target ~ -0.4037")
