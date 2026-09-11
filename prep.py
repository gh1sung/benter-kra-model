import pandas as pd, numpy as np
U="/sessions/lucid-eloquent-euler/mnt/uploads/"
df=pd.read_csv(U+"gate2_features_built.csv", low_memory=False).sort_values("race_id").reset_index(drop=True)
BASE=["AVESPRAT","LSPEDRAT","NEWDIST","WEIGHT","POSTPOS","JOCK_PCT_WIN","TRAINER_PCT_WIN","LIFE_PCT_WIN","CAREER_STARTS","DAYS_SINCE_LAST_RACE"]
ABIL=["AVESPRAT","LSPEDRAT","LIFE_PCT_WIN"]
def z(col):
    v=pd.to_numeric(df[col],errors="coerce").astype(float).values
    mu=np.nanmean(v); sd=np.nanstd(v); zz=(v-mu)/sd; zz[np.isnan(zz)]=0.0; return zz
Z={c:z(c) for c in BASE}
low2={'국6','국5','국미승','국신마','혼3','혼4','혼5','외2','외3','외미승'}
flags={"class":df.race_class.isin(low2).values.astype(float),
       "career":(df.CAREER_STARTS.fillna(0).values<5).astype(float)}
y=df.is_win.values.astype(float)
codes,uniq=pd.factorize(df.race_id.values); R=len(uniq)
starts=np.searchsorted(codes,np.arange(R)); bounds=np.append(starts,len(codes))
lens=(bounds[1:]-bounds[:-1]).astype(int)
Zmat=np.column_stack([Z[c] for c in BASE])
names_base=list(BASE)
for tag,flag in flags.items():
    cols=[Zmat, flag[:,None]]
    inames=[]
    for a in ABIL:
        cols.append((flag*Z[a])[:,None]); inames.append(f"low_x_{a}")
    X=np.hstack(cols)
    names=names_base+["low_info"]+inames
    np.savez(f"cache_{tag}.npz", X=X.astype(np.float64), y=y, starts=starts.astype(int),
             codes=codes.astype(int), lens=lens, row_start=starts.astype(int),
             names=np.array(names), R=R)
print("cached. X shape", X.shape, "R", R)
