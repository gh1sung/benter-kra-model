"""
lucky_evaluate.py — the actual test (plan §3.3-3.6, §4).

For each (definition D1/D2/D3, method M0/M1/M2):
  - references = BUILD-window dismissed AND placed
  - standardize FEATURES on the BUILD-window eligible pool (§3.2)
  - score every TEST-window eligible horse
  - tiers: top10% / top25% (cumulative) / rest   (§3.4)
  - per tier: n, actual_place_rate, base_rate, lift, odds_implied_rate,
    ratio=actual/implied, bootstrap 95% CI on ratio (2000 reps), mean_final_odds
Plus: §2.1 shape check, §3.5 odds_25>=20 filter robustness (D3),
      §3.6 BUILD/TEST stability swap.
Writes lucky_results.json for the report.
"""
import json
import numpy as np
import pandas as pd
from lucky_engine import (FEATURES, standardize, m1_mahalanobis, m2_knn,
                          m0_shuffle, k_for)

OUT = "/sessions/sweet-eager-noether/mnt/outputs"
BOOT = 2000
SEED = 20260727
BUILD_END = pd.Timestamp("2026-02-28")

df = pd.read_pickle(f"{OUT}/analysis_table.pkl")


def eligible_mask(d, D, odds_col="odds"):
    if D == "D1":
        return d["exp_rank_in_race"] <= 0.20
    if D == "D2":
        return d["exp_rank_in_race"] <= 1/3
    if D == "D3":
        return (d["exp_rank_in_race"] <= 1/3) & (d[odds_col] >= 20)
    raise ValueError(D)


def bootstrap_ratio_ci(placed, implied, reps=BOOT, seed=SEED):
    placed = np.asarray(placed, float); implied = np.asarray(implied, float)
    n = len(placed)
    if n == 0 or implied.sum() == 0:
        return (np.nan, np.nan)
    rng = np.random.default_rng(seed)
    out = np.empty(reps)
    for b in range(reps):
        idx = rng.integers(0, n, n)
        im = implied[idx].mean()
        out[b] = placed[idx].mean() / im if im > 0 else np.nan
    return (float(np.nanpercentile(out, 2.5)), float(np.nanpercentile(out, 97.5)))


def tier_table(test_df, scores, base_rate):
    """top10% / top25% (cumulative) / rest by similarity score (higher=closer)."""
    t = test_df.copy()
    t["score"] = scores
    order = t.sort_values("score", ascending=False).reset_index(drop=True)
    n = len(order)
    cut10 = max(1, int(round(0.10 * n)))
    cut25 = max(1, int(round(0.25 * n)))
    tiers = {"top10": order.iloc[:cut10],
             "top25": order.iloc[:cut25],
             "rest":  order.iloc[cut25:]}
    rows = {}
    for name, sub in tiers.items():
        pr = sub["placed"].mean()
        imp = sub["implied"].mean()
        lo, hi = bootstrap_ratio_ci(sub["placed"], sub["implied"])
        rows[name] = {
            "n": int(len(sub)),
            "actual_place_rate": round(float(pr), 4),
            "base_rate": round(float(base_rate), 4),
            "lift": round(float(pr / base_rate), 3) if base_rate > 0 else None,
            "odds_implied_rate": round(float(imp), 4),
            "ratio": round(float(pr / imp), 3) if imp > 0 else None,
            "ratio_CI95": [round(lo, 3), round(hi, 3)],
            "mean_final_odds": round(float(sub["odds"].mean()), 1),
        }
    return rows


def shape_check(refs_std):
    """§2.1 one-blob-or-two check via 2-means on standardized refs."""
    from numpy.random import default_rng
    rng = default_rng(SEED)
    X = refs_std
    # simple k=2 Lloyd's
    c = X[rng.choice(len(X), 2, replace=False)]
    for _ in range(50):
        d = ((X[:, None, :] - c[None, :, :]) ** 2).sum(2)
        lab = d.argmin(1)
        newc = np.array([X[lab == j].mean(0) if (lab == j).any() else c[j] for j in range(2)])
        if np.allclose(newc, c): break
        c = newc
    sizes = [int((lab == 0).sum()), int((lab == 1).sum())]
    sep = float(np.sqrt(((c[0] - c[1]) ** 2).sum()))   # centroid separation (sd units)
    return {"cluster_sizes": sizes, "centroid_separation_sd": round(sep, 2)}


def run_combo(d, D, build_end=BUILD_END, odds_col="odds", label=""):
    elig = d[eligible_mask(d, D, odds_col)].copy()
    build_pool = elig[elig["race_date"] <= build_end]
    test_pool  = elig[elig["race_date"] >  build_end]
    refs = build_pool[build_pool["placed"] == 1]
    n_refs = len(refs)
    base_rate = float(test_pool["placed"].mean())   # peer base rate on the tiered pop
    if n_refs < 100:
        return {"definition": D, "label": label, "n_refs_build": n_refs,
                "DROPPED": "n_refs_build < 100", "base_rate_test": round(base_rate, 4)}
    (refs_std, test_std), mu, sd = standardize(build_pool, refs, test_pool)
    k = k_for(n_refs)
    s_m1 = m1_mahalanobis(refs_std, test_std)
    s_m2 = m2_knn(refs_std, test_std, k)
    s_m0 = m0_shuffle(s_m1)
    res = {"definition": D, "label": label, "n_refs_build": n_refs,
           "k": k, "n_test_eligible": int(len(test_pool)),
           "base_rate_test": round(base_rate, 4),
           "base_rate_pool_all": round(float(elig["placed"].mean()), 4),
           "shape_check": shape_check(refs_std),
           "M1": tier_table(test_pool, s_m1, base_rate),
           "M2": tier_table(test_pool, s_m2, base_rate),
           "M0": tier_table(test_pool, s_m0, base_rate)}
    return res


results = {"primary": {}, "filter_robustness_3_5": {}, "stability_3_6": {}}

print("="*70); print("PRIMARY RUN (plan §3.3-3.4)"); print("="*70)
for D in ["D1", "D2", "D3"]:
    r = run_combo(df, D, label="odds>=20" if D == "D3" else "")
    results["primary"][D] = r
    if "DROPPED" in r:
        print(f"{D}: DROPPED ({r['DROPPED']})"); continue
    print(f"\n{D}  refs_build={r['n_refs_build']}  k={r['k']}  "
          f"test_elig={r['n_test_eligible']}  base(TEST)={r['base_rate_test']}  "
          f"shape={r['shape_check']}")
    for M in ["M1", "M2", "M0"]:
        t10, t25 = r[M]["top10"], r[M]["top25"]
        print(f"   {M} top10: n={t10['n']:4d} lift={t10['lift']} "
              f"ratio={t10['ratio']} CI{t10['ratio_CI95']} odds={t10['mean_final_odds']}"
              f"  | top25 lift={t25['lift']} ratio={t25['ratio']}")

print("\n" + "="*70); print("§3.5 FILTER ROBUSTNESS — D3 with odds_25>=20"); print("="*70)
r35 = run_combo(df, "D3", odds_col="odds_25", label="odds_25>=20")
results["filter_robustness_3_5"]["D3_odds25"] = r35
if "DROPPED" not in r35:
    print(f"D3(odds_25>=20)  refs_build={r35['n_refs_build']}  k={r35['k']}  "
          f"test_elig={r35['n_test_eligible']}  base={r35['base_rate_test']}")
    for M in ["M1", "M2"]:
        t10 = r35[M]["top10"]
        print(f"   {M} top10: n={t10['n']} lift={t10['lift']} ratio={t10['ratio']} CI{t10['ratio_CI95']}")

print("\n" + "="*70); print("§3.6 STABILITY SWAP — fit on LATE window, test on EARLY"); print("="*70)
# swap: 'BUILD' becomes the late window (>2026-02-28), 'TEST' the early one.
def run_combo_swapped(d, D):
    elig = d[eligible_mask(d, D)].copy()
    late_pool  = elig[elig["race_date"] >  BUILD_END]   # now the reference window
    early_pool = elig[elig["race_date"] <= BUILD_END]   # now the eval window
    refs = late_pool[late_pool["placed"] == 1]
    n_refs = len(refs); base_rate = float(early_pool["placed"].mean())
    if n_refs < 100:
        return {"definition": D, "n_refs": n_refs, "DROPPED": "n_refs<100",
                "base_rate": round(base_rate, 4)}
    (refs_std, eval_std), mu, sd = standardize(late_pool, refs, early_pool)
    k = k_for(n_refs)
    out = {"definition": D, "n_refs": n_refs, "k": k,
           "n_eval": int(len(early_pool)), "base_rate": round(base_rate, 4)}
    for M, sc in [("M1", m1_mahalanobis(refs_std, eval_std)),
                  ("M2", m2_knn(refs_std, eval_std, k))]:
        out[M] = tier_table(early_pool, sc, base_rate)
    return out

for D in ["D1", "D2", "D3"]:
    r = run_combo_swapped(df, D)
    results["stability_3_6"][D] = r
    if "DROPPED" in r:
        print(f"{D}: DROPPED ({r['DROPPED']})"); continue
    print(f"\n{D}(swap) refs={r['n_refs']} k={r['k']} eval={r['n_eval']} base={r['base_rate']}")
    for M in ["M1", "M2"]:
        t10 = r[M]["top10"]
        print(f"   {M} top10: n={t10['n']} lift={t10['lift']} ratio={t10['ratio']} CI{t10['ratio_CI95']}")

json.dump(results, open(f"{OUT}/lucky_results.json", "w"), indent=2)
print(f"\nsaved lucky_results.json")
