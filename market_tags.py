"""
market_tags.py

v2 of the product tagging layer. Supports BOTH proven binary tags:

  - Unlucky:    experts like it, stats rate it below the field.
                n=478 (this join), ratio=0.913, CI excludes 1. Full-sample
                and holdout-replicated in the original archetype grid
                (n=15,222, ratio=0.950). PROVEN.
  - Overlooked: nobody picked it, stats rate it above the field.
                n=1,033, ratio=0.779, CI excludes 1 in full sample.
                CAUTION: year-split check shows <=2023 ratio=0.587 (strong)
                vs >=2024 ratio=0.867 (CI crosses 1.0 -- not distinguishable
                from noise in the recent window). Ship with a visible
                caveat, not with the same confidence as Unlucky.

Both tags now carry a DENSITY-BASED confidence tier (S/A/B/C), separate
from the tag itself. The tier says how much historical evidence backs the
specific comps box for THIS horse's odds level -- it does not grade how
dangerous/promising the horse is. That distinction matters: tiering by
density is honest, tiering by outcome would just be the graded index we
already ruled out for lacking a real dose-response.

Usage:
    from market_tags import tag_race

    horses = [{"horse_num": 1, "odds_final": 5.5, "expert_score": 130}, ...]
    fund_p = [0.28, 0.11, ...]  # per-horse win prob, same order, race-normalized

    results = tag_race(horses, fund_p)
    for r in results:
        if r.tag is not None:
            print(r.explain())
"""
import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from typing import Optional

MIN_COMPS = 5
DEFAULT_K = 10
TIGHT_WINDOW = 0.3  # default log-odds distance used for the density/tier calculation

# Default tier cutpoints (comps needed within TIGHT_WINDOW to earn each tier).
# These were reasonable defaults from a first pass, NOT hand-tuned per dataset.
# [program supervisor] asked to be able to adjust these directly while testing new data, so
# every function below accepts overrides -- change these dict values for a
# permanent default change, or pass tier_cutpoints= / tight_window= per call
# for one-off testing.
DEFAULT_TIER_CUTPOINTS = {"S": 100, "A": 30, "B": 10}  # C = anything below B

# thresholds locked from the validated builds (03/05 scripts). If a
# reference pool is rebuilt on a bigger join, recompute these from that
# same run rather than hand-editing independently.
EXPERT_HIGH_MIN = 97     # expert_score >= this -> "experts like" (top tercile)
EXPERT_LOW_MAX = 23      # expert_score <= this -> "nobody picked" (bottom tercile)
FUND_RANK_WORSE_MAX = 0.333   # field-relative fund_p rank <= this -> "stats worse"
FUND_RANK_BETTER_MIN = 0.667  # field-relative fund_p rank >= this -> "stats better"

TAG_CONFIG = {
    "unlucky": {
        "pool_path": "unlucky_reference_pool.csv",
        "label": "UNLUCKY",
        "caveat": None,
    },
    "overlooked": {
        "pool_path": "overlooked_reference_pool.csv",
        "label": "OVERLOOKED",
        "caveat": ("this pattern was strong in 2022-23 data but weaker and "
                    "not statistically distinguishable from noise in 2024+ "
                    "data -- show with lower confidence than Unlucky"),
    },
}


@dataclass
class TagResult:
    horse_num: int
    tag: Optional[str]  # "unlucky", "overlooked", or None
    odds_final: float
    expert_score: float
    fund_p_race_rank: float
    tier: Optional[str] = None
    n_comps: int = 0
    n_tight_comps: int = 0
    comps_placed_rate: Optional[float] = None
    pool_placed_rate: Optional[float] = None
    comps: Optional[pd.DataFrame] = field(default=None, repr=False)
    reason: str = ""

    def explain(self) -> str:
        if self.tag is None:
            return f"Horse {self.horse_num}: no tag ({self.reason})"

        cfg = TAG_CONFIG[self.tag]
        if self.n_comps < MIN_COMPS:
            return (f"Horse {self.horse_num}: qualifies as {cfg['label']} but only "
                    f"{self.n_comps} close historical matches found -- comps box suppressed.")

        tier_note = {
            "S": "strong evidence base",
            "A": "solid evidence base",
            "B": "thinner evidence base -- fewer close historical matches",
            "C": "sparse evidence base -- treat with caution",
        }[self.tier]

        base = (f"Horse {self.horse_num}: {cfg['label']} [{self.tier} confidence, "
                f"{tier_note}]. Looked at the {self.n_comps} most similar past horses: "
                f"{self.comps_placed_rate*100:.0f}% placed, vs {self.pool_placed_rate*100:.0f}% "
                f"for the {cfg['label'].lower()} group overall.")
        if cfg["caveat"]:
            base += f" [Caveat: {cfg['caveat']}]"
        return base


def _load_pool(tag_name):
    cfg = TAG_CONFIG[tag_name]
    pool = pd.read_csv(cfg["pool_path"], dtype={"race_id": str})
    if "log_odds" not in pool.columns:
        pool["log_odds"] = np.log(pool["odds_final"])
    feat_cols = ["log_odds", "fund_p_race_rank"]
    mu = pool[feat_cols].mean()
    sigma = pool[feat_cols].std()
    return pool, mu, sigma, feat_cols


def _tier_from_density(n_tight, tier_cutpoints=None):
    cp = tier_cutpoints or DEFAULT_TIER_CUTPOINTS
    if n_tight >= cp["S"]:
        return "S"
    elif n_tight >= cp["A"]:
        return "A"
    elif n_tight >= cp["B"]:
        return "B"
    return "C"


def _find_comps_and_tier(odds_final, fund_p_race_rank, pool, mu, sigma, feat_cols, k,
                          tight_window=TIGHT_WINDOW, tier_cutpoints=None):
    q_log_odds = np.log(odds_final)
    q = pd.DataFrame({"log_odds": [q_log_odds], "fund_p_race_rank": [fund_p_race_rank]})
    qz = ((q[feat_cols] - mu) / sigma).to_numpy()
    poolz = ((pool[feat_cols] - mu) / sigma).to_numpy()
    dist = np.sqrt(((poolz - qz) ** 2).sum(axis=1))

    out = pool.copy()
    out["distance"] = dist
    n_tight = int((np.abs(pool["log_odds"] - q_log_odds) < tight_window).sum())
    tier = _tier_from_density(n_tight, tier_cutpoints)

    comps = out.nsmallest(k, "distance")[
        ["race_id", "race_date", "region", "horse_num", "odds_final",
         "expert_score", "fund_p_race_rank", "placed", "distance"]
    ]
    return comps, n_tight, tier


def tag_race(horses: list[dict], fund_p: list[float], k: int = DEFAULT_K,
             min_comps: int = MIN_COMPS, tight_window: float = TIGHT_WINDOW,
             tier_cutpoints: dict = None) -> list[TagResult]:
    """
    horses: list of dicts with 'horse_num', 'odds_final', 'expert_score'
    fund_p: list of floats, same order, race-normalized fundamental win prob
    tight_window: log-odds distance defining a "close" comp for tiering.
                  Smaller = stricter matching = fewer comps counted as tight.
                  Default 0.3 (~+/-35% relative odds). Adjust to taste when
                  testing new data -- no need to edit code, just pass a value.
    tier_cutpoints: dict like {"S": 100, "A": 30, "B": 10} -- comps needed
                    within tight_window to earn each tier. Anything below
                    "B" is tier C. Pass a custom dict to override defaults
                    per call, e.g. tier_cutpoints={"S": 50, "A": 15, "B": 5}
                    for a smaller/newer dataset where 100 is unreachable.
    """
    if len(horses) != len(fund_p):
        raise ValueError("horses and fund_p must be the same length")
    if len(horses) < 2:
        raise ValueError("need at least 2 horses to compute field-relative rank")

    df = pd.DataFrame(horses)
    df["fund_p"] = fund_p
    df["fund_p_race_rank"] = df["fund_p"].rank(pct=True)

    pools = {name: _load_pool(name) for name in TAG_CONFIG}

    results = []
    for _, row in df.iterrows():
        experts_like = row["expert_score"] >= EXPERT_HIGH_MIN
        nobody_picked = row["expert_score"] <= EXPERT_LOW_MAX
        stats_worse = row["fund_p_race_rank"] <= FUND_RANK_WORSE_MAX
        stats_better = row["fund_p_race_rank"] >= FUND_RANK_BETTER_MIN

        tag_name = None
        if experts_like and stats_worse:
            tag_name = "unlucky"
        elif nobody_picked and stats_better:
            tag_name = "overlooked"

        if tag_name is None:
            results.append(TagResult(
                horse_num=row["horse_num"], tag=None,
                odds_final=row["odds_final"], expert_score=row["expert_score"],
                fund_p_race_rank=row["fund_p_race_rank"],
                reason="doesn't meet the expert-vs-stats mismatch pattern for either tag"
            ))
            continue

        pool, mu, sigma, feat_cols = pools[tag_name]
        comps, n_tight, tier = _find_comps_and_tier(
            row["odds_final"], row["fund_p_race_rank"], pool, mu, sigma, feat_cols, k,
            tight_window=tight_window, tier_cutpoints=tier_cutpoints
        )
        n_comps = len(comps)
        comps_rate = comps["placed"].mean() if n_comps > 0 else None
        pool_rate = pool["placed"].mean()

        results.append(TagResult(
            horse_num=row["horse_num"], tag=tag_name,
            odds_final=row["odds_final"], expert_score=row["expert_score"],
            fund_p_race_rank=row["fund_p_race_rank"],
            tier=tier, n_comps=n_comps, n_tight_comps=n_tight,
            comps_placed_rate=comps_rate, pool_placed_rate=pool_rate, comps=comps,
            reason="" if n_comps >= min_comps else f"only {n_comps} comps found, floor is {min_comps}"
        ))
    return results


def tier_distribution_preview(tag_name: str, tight_window: float = TIGHT_WINDOW,
                                tier_cutpoints: dict = None, n_grid_points: int = 15):
    """
    Utility for threshold-tuning: sweep the pool's own odds range and show
    how many horses would land in each tier under a given (tight_window,
    tier_cutpoints) setting. Use this to manually dial in cutpoints for a
    new/smaller dataset before committing to defaults -- exactly the
    "수동으로 수치를 조정" workflow requested.

    Returns a DataFrame with one row per grid point: odds level, comp count,
    assigned tier. Also prints the overall tier distribution.
    """
    pool, mu, sigma, feat_cols = _load_pool(tag_name)
    lo_min, lo_max = pool["log_odds"].min(), pool["log_odds"].max()
    grid = np.linspace(lo_min, lo_max, n_grid_points)

    rows = []
    for g in grid:
        n_tight = int((np.abs(pool["log_odds"] - g) < tight_window).sum())
        tier = _tier_from_density(n_tight, tier_cutpoints)
        rows.append({"odds_level": round(np.exp(g), 1), "tight_comps_n": n_tight, "tier": tier})
    table = pd.DataFrame(rows)
    print(f"=== {tag_name} tier preview (tight_window={tight_window}, "
          f"cutpoints={tier_cutpoints or DEFAULT_TIER_CUTPOINTS}) ===")
    print(table.to_string(index=False))
    print(f"\nTier distribution: {table['tier'].value_counts().to_dict()}")
    return table


if __name__ == "__main__":
    d = pd.read_csv("unified_dataset.csv", dtype={"race_id": str})
    d["expert_tercile"] = pd.qcut(d["expert_score"], 3, labels=["low", "mid", "high"])
    d["fund_p_race_rank"] = d.groupby("race_id")["fund_p"].rank(pct=True)

    # find a race with at least one of each tag for a clean demo
    has_unlucky = d[(d["expert_tercile"] == "high") & (d["fund_p_race_rank"] <= 0.333)]["race_id"]
    has_overlooked = d[(d["expert_tercile"] == "low") & (d["fund_p_race_rank"] >= 0.667)]["race_id"]

    demo_race = d[d["race_id"] == has_unlucky.iloc[0]]
    print(f"=== DEMO: Unlucky race {demo_race['race_id'].iloc[0]} ({len(demo_race)} horses) ===")
    horses = demo_race[["horse_num", "odds_final", "expert_score"]].to_dict("records")
    fund_p = demo_race["fund_p"].tolist()
    for r in tag_race(horses, fund_p, k=10):
        if r.tag:
            print(r.explain())

    demo_race2 = d[d["race_id"] == has_overlooked.iloc[0]]
    print(f"\n=== DEMO: Overlooked race {demo_race2['race_id'].iloc[0]} ({len(demo_race2)} horses) ===")
    horses2 = demo_race2[["horse_num", "odds_final", "expert_score"]].to_dict("records")
    fund_p2 = demo_race2["fund_p"].tolist()
    for r in tag_race(horses2, fund_p2, k=10):
        if r.tag:
            print(r.explain())
