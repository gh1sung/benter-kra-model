import numpy as np, json
def analyze(tag):
    d=np.load(f"cache_{tag}.npz",allow_pickle=True)
    X=d["X"]; y=d["y"]; starts=d["starts"].astype(int); codes=d["codes"].astype(int)
    names=list(d["names"]); R=int(d["R"]); lam=1e-4
    base=np.load(f"base_{tag}.npy")
    eta=X@base; mx=np.maximum.reduceat(eta,starts); em=eta-mx[codes]
    e=np.exp(em); Zs=np.add.reduceat(e,starts); p=e/Zs[codes]
    r=y-p
    # score per race (R x k)
    Xr=X*r[:,None]
    S=np.add.reduceat(Xr,starts,axis=0)
    meat=S.T@S
    # Hessian
    term1=X.T@(p[:,None]*X)
    M=np.add.reduceat(p[:,None]*X,starts,axis=0)
    term2=M.T@M
    H=term1-term2+2*lam*np.eye(X.shape[1])
    Hinv=np.linalg.inv(H)
    V=Hinv@meat@Hinv
    se=np.sqrt(np.diag(V))
    return names,base,se
for tag in ["class","career"]:
    names,base,se=analyze(tag)
    print(f"\n==== {tag} cut — race-clustered robust CIs ====")
    d=dict(zip(names,zip(base,se)))
    for n in names:
        b,s=d[n]; lo,hi=b-1.96*s,b+1.96*s
        star=" SIG" if (lo>0 or hi<0) else " ns"
        mark="  <<" if n.startswith("low") else ""
        print(f"  {n:22} {b:+.4f}  SE {s:.4f}  95%CI[{lo:+.4f},{hi:+.4f}]{star}{mark}")
    json.dump({"names":names,"beta":base.tolist(),"se":se.tolist()},open(f"robust_{tag}.json","w"))
