import numpy as np, json
from scipy.optimize import minimize
U="/sessions/lucid-eloquent-euler/mnt/uploads/"
import pandas as pd
years=pd.read_csv(U+"gate2_features_built.csv",usecols=["race_id","race_date"]).sort_values("race_id")
yr=years.race_date.str[:4].astype(int).values  # row-aligned to sorted race_id? need same sort as cache

def fit(X,y,starts,codes,x0=None):
    def ng(b):
        eta=X@b; mx=np.maximum.reduceat(eta,starts); em=eta-mx[codes]
        e=np.exp(em); Zs=np.add.reduceat(e,starts); logZ=np.log(Zs)+mx
        nll=-(y*(eta-logZ[codes])).sum(); p=e/Zs[codes]
        sc=np.add.reduceat(y,starts); grad=-X.T@(y-sc[codes]*p)
        return nll+1e-4*b@b, grad+2e-4*b
    if x0 is None: x0=np.zeros(X.shape[1])
    return minimize(ng,x0,jac=True,method="L-BFGS-B",options={"maxiter":300}).x

def logloss_by_race(X,beta,y,starts,codes):
    eta=X@beta; mx=np.maximum.reduceat(eta,starts); em=eta-mx[codes]
    e=np.exp(em); Zs=np.add.reduceat(e,starts); p=e/Zs[codes]
    # winner rows: y==1; per race -log p of winner (avg if dead heat)
    ll=-np.log(np.clip(p,1e-12,1))*y
    per_race=np.add.reduceat(ll,starts)/np.add.reduceat(y,starts)
    return per_race  # length R

for tag in ["class","career"]:
    d=np.load(f"cache_{tag}.npz",allow_pickle=True)
    X=d["X"]; y=d["y"]; starts=d["starts"].astype(int); codes=d["codes"].astype(int); R=int(d["R"])
    names=list(d["names"])
    # race-level year: take year of first row of each race
    ryear=yr[starts]
    base_cols=list(range(10))         # 10-var base
    full_cols=list(range(X.shape[1])) # +low_info +3 interactions
    test_years=range(2010,2027)       # need a few years of history first
    diffs=[]; base_ll=[]; full_ll=[]
    for Y in test_years:
        tr=ryear<Y; te=ryear==Y
        if te.sum()==0: continue
        # build row masks from race masks
        row_year=yr  # row aligned (same sort)
        rtr=row_year<Y; rte=row_year==Y
        def sub(mask_rows):
            Xs=X[mask_rows]; ys=y[mask_rows]; cds=codes[mask_rows]
            u,newc=np.unique(cds,return_inverse=True)
            st=np.searchsorted(newc,np.arange(len(u)))
            return Xs,ys,st,newc
        Xtr,ytr,str_,ctr=sub(rtr)
        Xte,yte,ste,cte=sub(rte)
        bb=fit(Xtr[:,base_cols],ytr,str_,ctr)
        bf=fit(Xtr[:,full_cols],ytr,str_,ctr)
        llb=logloss_by_race(Xte[:,base_cols],bb,yte,ste,cte)
        llf=logloss_by_race(Xte[:,full_cols],bf,yte,ste,cte)
        base_ll.append(llb); full_ll.append(llf)
        diffs.append(llb-llf)  # positive => full better (lower loss)
    base_ll=np.concatenate(base_ll); full_ll=np.concatenate(full_ll); diffs=np.concatenate(diffs)
    md=diffs.mean(); se=diffs.std(ddof=1)/np.sqrt(len(diffs))
    print(f"\n==== {tag} cut: walk-forward OOS log loss (2010-2026, {len(diffs)} test races) ====")
    print(f"  base 10-var mean log loss: {base_ll.mean():.5f}")
    print(f"  +interaction  mean log loss: {full_ll.mean():.5f}")
    print(f"  improvement (base-full): {md:+.6f}  SE {se:.6f}  95%CI[{md-1.96*se:+.6f},{md+1.96*se:+.6f}]")
    print(f"  {'SIGNIFICANT improvement' if md-1.96*se>0 else ('significant WORSE' if md+1.96*se<0 else 'no significant OOS difference')}")
    json.dump({"base_ll":float(base_ll.mean()),"full_ll":float(full_ll.mean()),
               "delta":float(md),"se":float(se),"n":int(len(diffs))},open(f"wf_{tag}.json","w"))
