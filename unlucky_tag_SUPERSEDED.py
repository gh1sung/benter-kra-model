"""
unlucky_tag.py

The reusable, callable version of the Unlucky product feature. Given a
race's worth of horses (odds, expert_score, fund_p per horse), this:

  1. Tags which horses qualify as "Unlucky" (experts-like tercile AND
     bottom-tercile fund_p rank within this race) -- same definition
     validated in the archetype grid (ratio 0.950, n=15,222 original;
     re-confirmed 0.913 on this join's scope, n=478).
  2. For each tagged horse, pulls the K nearest historical comps from the
     reference pool (built once, cached to CSV) and reports their outcomes.
  3. Enforces a MIN_COMPS floor -- refuses to show a comps box built on too
     few matches, so nothing gets presented as evidence when it isn't.

This is a communication layer over an already-proven population effect, not
a new statistical claim. The 0.950 ratio + CI is the actual evidence,
the comps box is how you explain it to a customer without showing z-scores.

Usage:
    from unlucky_tag import tag_race, UnluckyResult

    horses = [
        {"horse_num": 1, "odds_final": 5.5, "expert_score": 130},
        {"horse_num": 2, "odds_final": 8.2, "expert_score": 40},
        ...
    ]
    results = tag_race(horses, fund_p=[0.28, 0.11, ...])  # per-horse win prob, same order

    for r in results:
        if r.is_unlucky:
            print(r.explain())
"""
import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from typing import Optional

REFERENCE_POOL_PATH = "unlucky_reference_pool.csv"
MIN_COMPS = 5          # floor: below this, don't show a comps box at all
DEFAULT_K = 10          # default number of comps to pull

# thresholds locked from the validated build (03/04 scripts). If the
# reference pool is ever rebuilt on a bigger join, these should be
# recomputed from that same run, not hand-edited independently.
EXPERT_HIGH_TERCILE_MIN = 97      # expert_score >= this -> "experts like"
FUND_RANK_WORSE_MAX = 0.333       # field-relative fund_p rank <= this -> "stats say worse"


@dataclass
class UnluckyResult:
    horse_num: int
    is_unlucky: bool
    odds_final: float
    expert_score: float
    fund_p_race_rank: float
    n_comps: int = 0
    comps_placed_rate: Optional[float] = None
    pool_placed_rate: Optional[float] = None
    comps: Optional[pd.DataFrame] = field(default=None, repr=False)
    reason: str = ""  # why not tagged, if not tagged / why comps suppressed

    def explain(self) -> str:
        if not self.is_unlucky:
            return f"Horse {self.horse_num}: not tagged Unlucky ({self.reason})"
        if self.n_comps < MIN_COMPS:
            return (f"Horse {self.horse_num}: qualifies as Unlucky (experts like it, "
                    f"stats rate it below the field) but only {self.n_comps} close "
                    f"historical matches found -- not enough to show a reliable comps box.")
        return (f"Horse {self.horse_num}: UNLUCKY. Experts favor it (score "
                f"{self.expert_score:.0f}) but our model rates it below this field. "
                f"Looked at the {self.n_comps} most similar past horses (same odds "
                f"range, same size of expert-vs-stats gap): "
                f"{self.comps_placed_rate*100:.0f}% placed, vs {self.pool_placed_rate*100:.0f}% "
                f"for the Unlucky group overall.")


def _load_reference_pool():
    pool = pd.read_csv(REFERENCE_POOL_PATH, dtype={"race_id": str})
    feat_cols = ["log_odds", "fund_p_race_rank"]
    mu = pool[feat_cols].mean()
    sigma = pool[feat_cols].std()
    return pool, mu, sigma, feat_cols


def _find_comps(odds_final, fund_p_race_rank, pool, mu, sigma, feat_cols, k):
    q = pd.DataFrame({"log_odds": [np.log(odds_final)],
                       "fund_p_race_rank": [fund_p_race_rank]})
    qz = ((q[feat_cols] - mu) / sigma).to_numpy()
    poolz = ((pool[feat_cols] - mu) / sigma).to_numpy()
    dist = np.sqrt(((poolz - qz) ** 2).sum(axis=1))
    out = pool.copy()
    out["distance"] = dist
    return out.nsmallest(k, "distance")[
        ["race_id", "race_date", "region", "horse_num", "odds_final",
         "expert_score", "fund_p_race_rank", "placed", "distance"]
    ]


def tag_race(horses: list[dict], fund_p: list[float], k: int = DEFAULT_K,
             min_comps: int = MIN_COMPS) -> list[UnluckyResult]:
    """
    horses: list of dicts, each with 'horse_num', 'odds_final', 'expert_score'
    fund_p: list of floats, same order as horses, the fundamental-model win
            probability for each horse (must sum to ~1 across the race --
            this is what the Gate 2 model outputs per race already)
    k: how many historical comps to pull per tagged horse
    min_comps: floor below which comps are suppressed (see MIN_COMPS)

    Returns one UnluckyResult per horse in the race.
    """
    if len(horses) != len(fund_p):
        raise ValueError("horses and fund_p must be the same length (one fund_p per horse)")
    if len(horses) < 2:
        raise ValueError("need at least 2 horses in a race to compute field-relative rank")

    df = pd.DataFrame(horses)
    df["fund_p"] = fund_p
    df["fund_p_race_rank"] = df["fund_p"].rank(pct=True)

    pool, mu, sigma, feat_cols = _load_reference_pool()

    results = []
    for _, row in df.iterrows():
        experts_like = row["expert_score"] >= EXPERT_HIGH_TERCILE_MIN
        stats_worse = row["fund_p_race_rank"] <= FUND_RANK_WORSE_MAX

        if not (experts_like and stats_worse):
            missing = []
            if not experts_like:
                missing.append("expert_score below the 'experts like it' threshold")
            if not stats_worse:
                missing.append("fundamentals not below the rest of this field")
            results.append(UnluckyResult(
                horse_num=row["horse_num"], is_unlucky=False,
                odds_final=row["odds_final"], expert_score=row["expert_score"],
                fund_p_race_rank=row["fund_p_race_rank"],
                reason="; ".join(missing)
            ))
            continue

        comps = _find_comps(row["odds_final"], row["fund_p_race_rank"],
                             pool, mu, sigma, feat_cols, k)
        n_comps = len(comps)
        comps_rate = comps["placed"].mean() if n_comps > 0 else None
        pool_rate = pool["placed"].mean()

        results.append(UnluckyResult(
            horse_num=row["horse_num"], is_unlucky=True,
            odds_final=row["odds_final"], expert_score=row["expert_score"],
            fund_p_race_rank=row["fund_p_race_rank"],
            n_comps=n_comps, comps_placed_rate=comps_rate,
            pool_placed_rate=pool_rate, comps=comps,
            reason="" if n_comps >= min_comps else f"only {n_comps} comps found, floor is {min_comps}"
        ))
    return results


if __name__ == "__main__":
    # smoke test: reconstruct one real race from unified_dataset.csv end to end
    d = pd.read_csv("unified_dataset.csv", dtype={"race_id": str})
    sample_race_id = d[d["race_id"].map(d["race_id"].value_counts()) >= 6]["race_id"].iloc[0]
    race = d[d["race_id"] == sample_race_id].copy()
    print(f"Smoke test on race {sample_race_id} ({len(race)} horses)\n")

    horses = race[["horse_num", "odds_final", "expert_score"]].to_dict("records")
    fund_p = race["fund_p"].tolist()

    results = tag_race(horses, fund_p, k=10)
    for r in results:
        print(r.explain())
        actual = race[race["horse_num"] == r.horse_num]["placed"].iloc[0]
        print(f"   (this horse's actual result: {'placed' if actual else 'did not place'})\n")
