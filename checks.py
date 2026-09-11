import pandas as pd, numpy as np
U="/sessions/lucid-eloquent-euler/mnt/uploads/"
df=pd.read_csv(U+"gate2_features_built.csv", low_memory=False)
print("rows",len(df),"races",df.race_id.nunique())
print("\n--- winner flag check (is_win) ---")
print("is_win counts:\n", df.is_win.value_counts(dropna=False))
# winners per race should be ~1
wpr=df.groupby("race_id").is_win.sum()
print("races with exactly 1 winner:", (wpr==1).sum(), "/", len(wpr))
print("races with 0 winners:", (wpr==0).sum(), " >1 winners:", (wpr>1).sum())

print("\n--- region strings ---")
print(df.region.value_counts(dropna=False))

print("\n--- CAREER_STARTS ---")
print(df.CAREER_STARTS.describe())
print("nulls:", df.CAREER_STARTS.isna().sum())

print("\n--- race_class already in feature table? join check ---")
print("race_class nulls in feature table:", df.race_class.isna().sum())
# load class file
rc=pd.read_csv(U+"race_class.csv")
print("class file races:", rc.race_id.nunique())
feat_races=set(df.race_id.unique())
class_races=set(rc.race_id.unique())
joined=feat_races & class_races
print(f"feature races joined to class file: {len(joined)}/{len(feat_races)} = {100*len(joined)/len(feat_races):.2f}%")
unjoined=feat_races-class_races
print("unjoined feature races:", len(unjoined))
if unjoined:
    sub=df[df.race_id.isin(unjoined)]
    print("  unjoined by year:\n", sub.race_date.str[:4].value_counts().sort_index())
    print("  unjoined by region:\n", sub.region.value_counts())
# but feature table already has race_class column - compare consistency
m=df[["race_id","race_class"]].drop_duplicates().merge(rc[["race_id","race_class"]], on="race_id", suffixes=("_feat","_file"))
mismatch=(m.race_class_feat!=m.race_class_file).sum()
print("class label mismatches feat-vs-file:", mismatch, "/", len(m))
print("\ndate range:", df.race_date.min(), df.race_date.max())
