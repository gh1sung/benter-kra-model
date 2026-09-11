import boot_lib as B, numpy as np, json, time
for name,seed in [("class",42),("career",43)]:
    t=time.time()
    names,kn,pt,out=B.bootstrap(name,1000,seed=seed)
    np.save(f"boot_{name}.npy",out)
    json.dump({"keep":kn,"point":pt.tolist()},open(f"{name}_pt.json","w"))
    print(f"{name} done {time.time()-t:.0f}s",flush=True)
print("ALL DONE",flush=True)
