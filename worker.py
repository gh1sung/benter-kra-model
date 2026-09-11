import numpy as np, sys, os, time
from scipy.optimize import minimize
tag=sys.argv[1]; target=int(sys.argv[2]); budget=float(sys.argv[3])
d=np.load(f"cache_{tag}.npz", allow_pickle=True)
X=d["X"]; y=d["y"]; starts=d["starts"]; codes=d["codes"]; lens=d["lens"]; row_start=d["row_start"]
names=list(d["names"]); R=int(d["R"])
keep=[i for i,n in enumerate(names) if n.startswith("low")]
def fit(Xm,yv,ss,sid,x0,maxiter=60):
    def ng(b):
        eta=Xm@b; mx=np.maximum.reduceat(eta,ss); em=eta-mx[sid]
        e=np.exp(em); Zs=np.add.reduceat(e,ss); logZ=np.log(Zs)+mx
        nll=-(yv*(eta-logZ[sid])).sum(); p=e/Zs[sid]
        sc=np.add.reduceat(yv,ss); grad=-Xm.T@(yv-sc[sid]*p)
        return nll+1e-4*b@b, grad+2e-4*b
    return minimize(ng,x0,jac=True,method="L-BFGS-B",
                    options={"maxiter":maxiter,"ftol":1e-9,"gtol":1e-6}).x
# base (full) estimate
basef=f"base_{tag}.npy"
if os.path.exists(basef): base=np.load(basef)
else:
    base=fit(X,y,starts,codes,np.zeros(X.shape[1]),maxiter=300); np.save(basef,base)
ckpt=f"boot_{tag}.npy"
done=np.load(ckpt) if os.path.exists(ckpt) else np.zeros((0,len(keep)))
n0=len(done)
rng=np.random.default_rng(10000+n0)  # seed varies by progress
t=time.time(); newrows=[]
while len(newrows)+n0<target and time.time()-t<budget:
    samp=rng.integers(0,R,R)
    L=lens[samp]; tot=int(L.sum())
    ss=np.zeros(R,dtype=int); ss[1:]=np.cumsum(L)[:-1]
    sid=np.repeat(np.arange(R),L)
    idx=row_start[samp][sid]+(np.arange(tot)-ss[sid])
    b=fit(X[idx],y[idx],ss,sid,base)
    newrows.append(b[keep])
if newrows:
    done=np.vstack([done,np.array(newrows)])
    np.save(ckpt,done)
print(f"{tag}: {len(done)}/{target} done (+{len(newrows)} this call, {time.time()-t:.0f}s)")
