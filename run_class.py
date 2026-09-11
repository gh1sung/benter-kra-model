import boot_lib as B, numpy as np, time
t=time.time()
names,kn,pt,out=B.bootstrap("class",1000,seed=42)
np.save("boot_class.npy",out); 
import json; json.dump({"keep":kn,"point":pt.tolist()},open("class_pt.json","w"))
print("class done in %.0fs"%(time.time()-t))
lo,hi=np.percentile(out,[2.5,97.5],axis=0)
for i,n in enumerate(kn):
    sig="  SIG" if (lo[i]>0 or hi[i]<0) else "  ns"
    print(f"  {n:20} pt={pt[i]:+.4f}  95%CI[{lo[i]:+.4f},{hi[i]:+.4f}]{sig}")
