import boot_lib as B, numpy as np, time
t=time.time()
names,kn,pt,out=B.bootstrap("class",30,seed=1)
print("30 resamples in %.1fs -> ~%.1fs per 1000"%(time.time()-t,(time.time()-t)/30*1000))
print("keep names:",kn)
print("point est:",np.round(pt,4))
