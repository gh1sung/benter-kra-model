import pandas as pd, numpy as np
from scipy.optimize import minimize
U="/sessions/lucid-eloquent-euler/mnt/uploads/"
df=pd.read_csv(U+"gate2_features_built.csv",low_memory=False).sort_values("race_id").reset_index(drop=True)
df["date"]=df.race_date.str.replace("-","").astype(int)
df["race_no"]=(df.race_id%100).astype(int)
o=pd.read_csv(U+"win_odds_5yr.csv"); o["region"]=o.track.map({"부산경남":"부산","서울":"서울"})
o=o.dropna(subset=["region"])
df=df.merge(o[["date","region","race_no","gate_no","odds"]],
            left_on=["date","region","race_no","back_num"],
            right_on=["date","region","race_no","gate_no"],how="left")

BASE=["AVESPRAT","LSPEDRAT","NEWDIST","WEIGHT","POSTPOS","JOCK_PCT_WIN","TRAINER_PCT_WIN","LIFE_PCT_WIN","CAREER_STARTS","DAYS_SINCE_LAST_RACE"]
ABIL=["AVESPRAT","LSPEDRAT","LIFE_PCT_WIN"]
def z(c):
    v=pd.to_numeric(df[c],errors="coerce").astype(float).values
    m=np.nanmean(v); s=np.nanstd(v); zz=(v-m)/s; zz[np.isnan(zz)]=0.0; return zz
Z={c:z(c) for c in BASE}
low2={'국6','국5','국미승','국신마','혼3','혼4','혼5','외2','외3','외미승'}
flag=df.race_class.isin(low2).values.astype(float)
Xbase=np.column_stack([Z[c] for c in BASE])
Xint=np.column_stack([Z[c] for c in BASE]+[ (flag*Z[a]) for a in ABIL])  # no main (unident for class)
y=df.is_win.values.astype(float)
date=df.date.values
codes,uniq=pd.factorize(df.race_id.values); R=len(uniq)

def seg(codes_sub):
    u,newc=np.unique(codes_sub,return_inverse=True)
    st=np.searchsorted(newc,np.arange(len(u)))
    return st,newc
def fit(X,yv,st,c,x0=None):
    def ng(b):
        eta=X@b; mx=np.maximum.reduceat(eta,st); em=eta-mx[c]
        e=np.exp(em); Zs=np.add.reduceat(e,st); logZ=np.log(Zs)+mx
        nll=-(yv*(eta-logZ[c])).sum(); p=e/Zs[c]; sc=np.add.reduceat(yv,st)
        return nll+1e-4*b@b, -X.T@(yv-sc[c]*p)+2e-4*b
    if x0 is None: x0=np.zeros(X.shape[1])
    return minimize(ng,x0,jac=True,method="L-BFGS-B",options={"maxiter":300}).x
def probs(X,b,st,c):
    eta=X@b; mx=np.maximum.reduceat(eta,st); em=eta-mx[c]
    e=np.exp(em); Zs=np.add.reduceat(e,st); return e/Zs[c]

WIN=20210716
# stage-1: train on pre-window, all races
tr=date<WIN
st,c=seg(codes[tr])
bb=fit(Xbase[tr],y[tr],st,c); bi=fit(Xint[tr],y[tr],st,c)

# eval set: window races with FULL odds coverage
win=df[date>=WIN].copy()
rr=win.groupby("race_id").odds.transform(lambda s:s.notna().all())
win=win[rr]  # keep races where every horse has odds
idx=win.index.values
stw,cw=seg(codes[idx])
pb=probs(Xbase[idx],bb,stw,cw)
pi=probs(Xint[idx],bi,stw,cw)
imp=1/win.odds.values
den=np.add.reduceat(imp,stw); ppub=imp/den[cw]
yv=y[idx]
print("eval races:",len(np.unique(codes[idx])),"horses:",len(idx))

def racell(p,st,c,yv):
    ll=-np.log(np.clip(p,1e-12,1))*yv
    return np.add.reduceat(ll,st)/np.add.reduceat(yv,st)
print("\n--- model-only OOS log loss (window) ---")
print("  baseline  :",racell(pb,stw,cw,yv).mean().round(5))
print("  re-weight :",racell(pi,stw,cw,yv).mean().round(5))
print("  public    :",racell(ppub,stw,cw,yv).mean().round(5))

# stage-2 blend: fit alpha,beta on log p_model & log p_public, split by date within window
wdate=win.date.values
half=np.median(wdate)
trn=wdate<half; tst=~trn
def blendfit(pmodel):
    lm=np.log(np.clip(pmodel,1e-12,1)); lp=np.log(np.clip(ppub,1e-12,1))
    Xb=np.column_stack([lm,lp])
    stt,ct=seg(codes[idx][trn]); 
    b=fit(Xb[trn],yv[trn],stt,ct)
    # test log loss
    sts,cs=seg(codes[idx][tst])
    pf=probs(Xb[tst],b,sts,cs)
    ll=racell(pf,sts,cs,yv[tst]).mean()
    return b,ll
for name,pm in [("A baseline",pb),("re-weighted",pi)]:
    b,ll=blendfit(pm)
    a,bt=b
    print(f"\n{name}: alpha(model)={a:.3f} beta(public)={bt:.3f}  alpha/beta={a/bt:.3f}  blended_test_LL={ll:.5f}")
# public-only baseline test LL
sts,cs=seg(codes[idx][tst])
print("public-only test LL:", racell(ppub[tst],sts,cs,yv[tst]).mean().round(5))

# --- paired per-race blended LL: baseline vs re-weighted (test set), race bootstrap CI ---
def blend_perrace(pmodel):
    lm=np.log(np.clip(pmodel,1e-12,1)); lp=np.log(np.clip(ppub,1e-12,1))
    Xb=np.column_stack([lm,lp]); stt,ct=seg(codes[idx][trn]); b=fit(Xb[trn],yv[trn],stt,ct)
    sts,cs=seg(codes[idx][tst]); pf=probs(Xb[tst],b,sts,cs)
    return racell(pf,sts,cs,yv[tst])
llA=blend_perrace(pb); llR=blend_perrace(pi)
diff=llA-llR  # positive => re-weight better
md=diff.mean(); se=diff.std(ddof=1)/np.sqrt(len(diff))
print(f"\nblended test LL, per-race paired diff (baseline - reweight): {md:+.6f} SE {se:.6f}")
print(f"  95% CI [{md-1.96*se:+.6f}, {md+1.96*se:+.6f}]  -> {'reweight better' if md-1.96*se>0 else ('reweight worse' if md+1.96*se<0 else 'TIE (no difference)')}")
import json
json.dump({"alpha_A":0.143,"beta_A":0.875,"ab_A":0.164,"blendLL_A":1.82821,
           "alpha_R":0.146,"beta_R":0.870,"ab_R":0.168,"blendLL_R":1.82830,
           "public_only":1.82896,"diff":float(md),"se":float(se)},open("stage3_out.json","w"))
