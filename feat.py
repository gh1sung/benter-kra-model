import pandas as pd, numpy as np
U="/sessions/lucid-eloquent-euler/mnt/uploads/"
df=pd.read_csv(U+"gate2_features_built.csv", low_memory=False)
cands=["horse_rating","class_dist_avg_time","LIFE_PCT_WIN","W_PER_RACE","JOCK_PCT_WIN","JOCK_NUM_WIN",
"AVESPRAT","LSPEDRAT","NEWDIST","WEIGHT","POSTPOS","TRAINER_PCT_WIN","TRAINER_NUM_WIN",
"CAREER_STARTS","DAYS_SINCE_LAST_RACE","HAS_RATING","ROUTE_RESIDUAL"]
print("col                    dtype     nulls   null%    mean       std")
for c in cands:
    s=df[c]
    print(f"{c:22} {str(s.dtype):8} {s.isna().sum():7} {100*s.isna().mean():5.1f}  {pd.to_numeric(s,errors='coerce').mean():9.3f} {pd.to_numeric(s,errors='coerce').std():9.3f}")
print("\nHAS_RATING values:", df.HAS_RATING.value_counts(dropna=False).to_dict())
