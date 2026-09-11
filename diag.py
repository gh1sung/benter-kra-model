import pandas as pd, numpy as np
U="/sessions/lucid-eloquent-euler/mnt/uploads/"
df=pd.read_csv(U+"gate2_features_built.csv", low_memory=False)
df["year"]=df.race_date.str[:4]

# ---- low-info flags ----
# CLASS cut (bottom-2 primary), ladders separate
low2_classes={'국6','국5','국미승','국신마','혼3','혼4','혼5','외2','외3','외미승'}
low1_classes={'국6','국미승','국신마','혼4','혼5','외3','외미승'}
low3_classes={'국6','국5','국4','국미승','국신마','혼2','혼3','혼4','혼5','외1','외2','외3','외미승'}
df["low_class1"]=df.race_class.isin(low1_classes)
df["low_class2"]=df.race_class.isin(low2_classes)
df["low_class3"]=df.race_class.isin(low3_classes)

# CAREER_STARTS cut: null -> 0 (debut = low info)
cs=df.CAREER_STARTS.fillna(0)
df["low_cs5"]=cs<5
df["low_cs3"]=cs<3
df["low_cs10"]=cs<10

N=len(df)
print("=== §2.1 PREVALENCE (share of horse-rows low-info) ===")
for c in ["low_class1","low_class2","low_class3","low_cs3","low_cs5","low_cs10"]:
    print(f"  {c}: {100*df[c].mean():.1f}%")

print("\n=== §2.0 OVERLAP: class cut (bottom2) vs career-starts cut (<5) ===")
ct=pd.crosstab(df.low_class2, df.low_cs5)
print(ct)
a=df.low_class2; b=df.low_cs5
both=(a&b).sum(); onlyA=(a&~b).sum(); onlyB=(~a&b).sum()
print(f"  P(low_cs<5 | low_class): {100*both/a.sum():.1f}%   (of low-class horses, how many are also thin-data)")
print(f"  P(low_class | low_cs<5): {100*both/b.sum():.1f}%   (of thin-data horses, how many are also low-class)")
# Jaccard
union=(a|b).sum()
print(f"  Jaccard overlap: {100*both/union:.1f}%")
# phi correlation
phi=np.corrcoef(a.astype(int),b.astype(int))[0,1]
print(f"  phi correlation: {phi:.3f}")

print("\n=== §2.1 by region (bottom2 class / cs<5) ===")
for reg in ["서울","부산"]:
    s=df[df.region==reg]
    print(f"  {reg}: class {100*s.low_class2.mean():.1f}%  cs<5 {100*s.low_cs5.mean():.1f}%")

print("\n=== §2.1 by year ===")
g=df.groupby("year").agg(class2=("low_class2","mean"), cs5=("low_cs5","mean")).round(3)*100
print(g.astype(int))

print("\n=== §2.2 CRUX: races where >half the field is low-info -> lost if excluded ===")
rr=df.groupby("race_id").agg(n=("is_win","size"),
                             lc2=("low_class2","mean"),
                             cs5=("low_cs5","mean"))
tot_races=len(rr)
for name,col in [("class bottom2","lc2"),("career <5","cs5")]:
    lost=(rr[col]>0.5).sum()
    print(f"  {name}: {lost}/{tot_races} races are >50% low-info = {100*lost/tot_races:.1f}% of races would be dropped")
# also all-low
for name,col in [("class bottom2","lc2"),("career <5","cs5")]:
    alllow=(rr[col]==1.0).sum()
    print(f"  {name}: {alllow} races are 100% low-info = {100*alllow/tot_races:.1f}%")
