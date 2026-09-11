import pandas as pd, numpy as np
from scipy.optimize import minimize
U="/sessions/lucid-eloquent-euler/mnt/uploads/"
df=pd.read_csv(U+"gate2_features_built.csv", low_memory=False).sort_values("race_id").reset_index(drop=True)
codes,uniq=pd.factorize(df.race_id.values); R=len(uniq)
order=np.argsort(codes,kind="stable"); cs=codes[order]
bounds=np.append(np.searchsorted(cs,np.arange(R)),len(cs))
y=df.is_win.values.astype(float); ys=y[order]

def make_X(FEATS):
    X=np.zeros((len(df),len(FEATS)))
    for j,c in enumerate(FEATS):
        v=pd.to_numeric(df[c],errors="coerce").astype(float).values
        mu=np.nanmean(v); sd=np.nanstd(v); z=(v-mu)/sd; z[np.isnan(z)]=0.0
        X[:,j]=z
    return X[order]

def fit(FEATS,lam=1e-4):
    Xs=make_X(FEATS)
    def ng(beta):
        eta=Xs@beta; nll=0.0; grad=np.zeros_like(beta)
        for r in range(R):
            a,b=bounds[r],bounds[r+1]; seg=eta[a:b]; mx=seg.max()
            e=np.exp(seg-mx); Z=e.sum(); p=e/Z; w=ys[a:b]
            nll-=(w*(seg-mx-np.log(Z))).sum(); grad-=Xs[a:b].T@(w-w.sum()*p)
        return nll+lam*beta@beta, grad+2*lam*beta
    r=minimize(ng,np.zeros(len(FEATS)),jac=True,method="L-BFGS-B",options={"maxiter":300})
    return dict(zip(FEATS,r.x))

sets={
 "A: +horse_rating+HAS+ROUTE": ["horse_rating","HAS_RATING","ROUTE_RESIDUAL","AVESPRAT","LSPEDRAT","JOCK_PCT_WIN","TRAINER_PCT_WIN","WEIGHT","CAREER_STARTS","DAYS_SINCE_LAST_RACE"],
 "B: +class_dist+ROUTE": ["class_dist_avg_time","ROUTE_RESIDUAL","AVESPRAT","LSPEDRAT","NEWDIST","JOCK_PCT_WIN","TRAINER_PCT_WIN","WEIGHT","CAREER_STARTS","DAYS_SINCE_LAST_RACE"],
 "C: num_win variants": ["AVESPRAT","LSPEDRAT","NEWDIST","WEIGHT","POSTPOS","JOCK_NUM_WIN","TRAINER_NUM_WIN","W_PER_RACE","CAREER_STARTS","DAYS_SINCE_LAST_RACE"],
}
for name,F in sets.items():
    c=fit(F)
    biggest=max(c,key=lambda k:abs(c[k]))
    print(f"\n{name}")
    print(f"  CAREER_STARTS={c['CAREER_STARTS']:+.4f}   largest=|{biggest}|={c[biggest]:+.4f}")
