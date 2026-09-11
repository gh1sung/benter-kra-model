import pandas as pd, numpy as np, time, os
from scipy.optimize import minimize
U="/sessions/lucid-eloquent-euler/mnt/uploads/"
df=pd.read_csv(U+"gate2_features_built.csv", low_memory=False).sort_values("race_id").reset_index(drop=True)
BASE=["AVESPRAT","LSPEDRAT","NEWDIST","WEIGHT","POSTPOS","JOCK_PCT_WIN","TRAINER_PCT_WIN","LIFE_PCT_WIN","CAREER_STARTS","DAYS_SINCE_LAST_RACE"]
ABIL=["AVESPRAT","LSPEDRAT","LIFE_PCT_WIN"]
def z(col):
    v=pd.to_numeric(df[col],errors="coerce").astype(float).values
    mu=np.nanmean(v); sd=np.nanstd(v); zz=(v-mu)/sd; zz[np.isnan(zz)]=0.0; return zz
Z={c:z(c) for c in set(BASE)}
low2={'국6','국5','국미승','국신마','혼3','혼4','혼5','외2','외3','외미승'}
FLAGS={"class":df.race_class.isin(low2).values.astype(float),
       "career":(df.CAREER_STARTS.fillna(0).values<5).astype(float)}
y=df.is_win.values.astype(float)
codes,uniq=pd.factorize(df.race_id.values); R=len(uniq)
starts=np.searchsorted(codes,np.arange(R)); bounds=np.append(starts,len(codes))
lens=(bounds[1:]-bounds[:-1]).astype(int)
row_start=starts.astype(int)
def design(flag):
    cols=[Z[c] for c in BASE]; names=list(BASE)
    cols.append(flag); names.append("low_info")
    for a in ABIL: cols.append(flag*Z[a]); names.append(f"low_x_{a}")
    return np.column_stack(cols), names
def fit_on(X,yv,seg_starts,seg_id,x0,lam=1e-4):
    def ng(beta):
        eta=X@beta; mx=np.maximum.reduceat(eta,seg_starts); etam=eta-mx[seg_id]
        e=np.exp(etam); Zs=np.add.reduceat(e,seg_starts); logZ=np.log(Zs)+mx
        nll=-(yv*(eta-logZ[seg_id])).sum(); p=e/Zs[seg_id]
        sc=np.add.reduceat(yv,seg_starts); grad=-X.T@(yv-sc[seg_id]*p)
        return nll+lam*beta@beta, grad+2*lam*beta
    return minimize(ng,x0,jac=True,method="L-BFGS-B",options={"maxiter":300}).x
def build_idx(samp):
    L=lens[samp]; tot=L.sum()
    seg_starts=np.zeros(len(samp),dtype=int); seg_starts[1:]=np.cumsum(L)[:-1]
    seg_id=np.repeat(np.arange(len(samp)),L)
    within=np.arange(tot)-seg_starts[seg_id]
    idx=row_start[samp][seg_id]+within
    return idx,seg_starts,seg_id
def point_estimate(flagname):
    flag=FLAGS[flagname]; X,names=design(flag)
    base=fit_on(X,y,starts,codes,np.zeros(X.shape[1]))
    return names,base,X
def run_chunk(flagname,n,seed):
    flag=FLAGS[flagname]; X,names=design(flag)
    base=fit_on(X,y,starts,codes,np.zeros(X.shape[1]))
    keep=[i for i,nm in enumerate(names) if nm.startswith("low")]
    rng=np.random.default_rng(seed)
    out=np.zeros((n,len(keep)))
    for k in range(n):
        samp=rng.integers(0,R,R)
        idx,ss,sid=build_idx(samp)
        out[k]=fit_on(X[idx],y[idx],ss,sid,base)[keep]
    return names,[names[i] for i in keep],base[keep],out
