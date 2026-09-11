"""
drift_recheck.py — CORRECTED price-controlled test.

Fixes the §4.3 spec bug: the original criterion was "does a cell's ratio
(actual/implied) have a 95% CI excluding 1.0?". That is invalid inside an odds
band whose *whole* baseline ratio is already off 1.0 — e.g. the [1,3) favorite
band sits at ratio 0.898 for ALL horses because the Harville place engine still
overestimates favorites even at lambda=0.8. So every cell in that band clears
"excludes 1.0" regardless of drift; the test detects engine bias, not drift.

CORRECT test: does drift move placement WITHIN a band, relative to the band's
own baseline? i.e. the gradient top-25%-drift vs bottom-25%-drift. Bootstrap is
RACE-CLUSTERED (place outcomes are correlated within a race — favorites compete
for the same finite place slots), which is the honest resampling unit.
"""
import json
import numpy as np
import pandas as pd

OUT = "/sessions/sweet-eager-noether/mnt/outputs"
SEED = 20260727; REPS = 2000
BANDS = [(1,3),(3,6),(6,12),(12,25),(25,60),(60,np.inf)]

df = pd.read_pickle(f"{OUT}/drift_table.pkl").dropna(subset=["implied_place"]).copy()
d0, d1 = df.race_date.min(), df.race_date.max(); mid = d0 + (d1 - d0) / 2
late = df[df.race_date > mid].copy()
rng = np.random.default_rng(SEED)

def band_gradient(b):
    """observed gradient + race-clustered bootstrap CI of (top25 - bot25) place rate."""
    b = b.reset_index(drop=True)
    races = b.race_id.unique()
    race_rows = [b.index[b.race_id == r].to_numpy() for r in races]
    MI = b.MONEY_IN.to_numpy(); PL = b.placed.to_numpy()
    def grad(ridx):
        mi = MI[ridx]; pl = PL[ridx]; o = np.argsort(mi); n = len(mi)
        k = max(1, int(round(0.25 * n)))
        return pl[o[-k:]].mean() - pl[o[:k]].mean()
    obs = grad(b.index.to_numpy())
    nr = len(races)
    boot = np.array([grad(np.concatenate([race_rows[i] for i in rng.integers(0, nr, nr)]))
                     for _ in range(REPS)])
    return obs, np.percentile(boot, 2.5), np.percentile(boot, 97.5), (boot < 0).mean()

rows = []
print(f"{'band':>10} {'n':>5} {'base_ratio':>10} {'mid50_ratio':>11} | "
      f"{'grad(top-bot)':>13} {'clustered 95% CI':>22} {'frac_neg':>8} {'sig?':>5}")
for lo, hi in BANDS:
    b = late[(late.odds_final >= lo) & (late.odds_final < hi)]
    if len(b) < 40: continue
    base_ratio = b.placed.sum() / b.implied_place.sum()
    r = b.MONEY_IN.rank(pct=True)
    mid = b[(r > 0.25) & (r < 0.75)]
    mid_ratio = mid.placed.sum() / mid.implied_place.sum()
    obs, clo, chi, fneg = band_gradient(b)
    sig = (clo > 0 or chi < 0)
    rows.append({"band": f"[{lo},{hi})", "n": int(len(b)),
                 "band_baseline_ratio": round(float(base_ratio), 3),
                 "mid50_cell_ratio": round(float(mid_ratio), 3),
                 "gradient_top_minus_bot": round(float(obs), 3),
                 "clustered_CI95": [round(float(clo), 3), round(float(chi), 3)],
                 "frac_negative": round(float(fneg), 2),
                 "gradient_significant": bool(sig)})
    print(f"{f'[{lo},{hi})':>10} {len(b):>5} {base_ratio:>10.3f} {mid_ratio:>11.3f} | "
          f"{obs:>+13.3f} [{clo:>+7.3f},{chi:>+7.3f}] {fneg:>8.2f} {str(sig):>5}")

json.dump(rows, open(f"{OUT}/drift_within_band_gradient.json", "w"), indent=2)
pd.DataFrame(rows).to_csv(f"{OUT}/drift_within_band_gradient.csv", index=False)
n_sig = sum(r["gradient_significant"] for r in rows)
print(f"\nbands with a significant within-band drift gradient: {n_sig} of {len(rows)}")
print("(the [1,3) flicker is borderline and method-dependent; see report)")
print("saved drift_within_band_gradient.csv / .json")
