"""
horse_rating.py -- Rating Engine (마필 평가 모델)

Produces a 0-100 customer-facing per-horse ability score ("종합 능력 점수")
plus a race-relative win-expectancy ("우승 기대도") and a templated Korean
story, from the already-validated 10-variable fundamental model (baseline-9 +
CAREER_STARTS, ridge lambda=100).

Design (see Rating_Engine_Execution_Plan.md section 2 for the full rationale):
  - The score is built on the linear index V = ((X - mu) / sigma) @ beta_raw,
    NOT on fund_p. V is a global, race-independent quantity (mu/sigma/beta_raw
    are constants from the fit) so it is comparable across races, fields, and
    years. fund_p = softmax(V) within a race is field-dependent by
    construction and would make a horse's rating move because its opponents
    changed -- wrong for a FIFA-style overall.
  - Single locked variable set: baseline-9 + CAREER_STARTS (10 variables
    total). The earlier side-by-side 9-var comparison build has been
    retired per Jihwan's decision -- CAREER_STARTS stays in, this file only
    ever produces the 10-var score.
  - Scoring is a plain matrix product (V = X @ beta). No rank-order explosion,
    and build_estimation_sample() (fitting-only filters: 1600-2000m,
    track_condition in (건,양), age>=3, rank<90) is never called during
    scoring -- rank<90 in particular is an outcome variable and cannot exist
    before a race runs, so a scoring path that filters on it could never run
    in production.

IMPORTANT -- discrepancy found and worked around (documented in
Rating_Engine_Report.md, section "Notes on fit_engine.py / race_safe"):
  fit_engine.py as delivered into this project (and as copied into this
  engine's dependency) does NOT implement `race_safe=True` or
  `sample_diagnostics()`, despite Gate2_Report.md and README.md both
  describing it as already containing that fix. The corrected files the
  README points to (ablation2.py, select_lambda2.py, run_final_test2.py,
  deprecated_pre_audit/) are also not present in accessible project files.
  Rather than silently using the un-fixed build_estimation_sample() (which
  drops individual horses -- including sometimes the winner -- rather than
  the whole race), this module reimplements `build_estimation_sample_race_safe()`
  directly from the written spec in Gate2_Report.md section 1: "if any
  base-eligible horse in a race is missing a required feature, the whole race
  is dropped -- never just that horse." This is a "verify at the source"
  finding, not a design choice -- flagged per project's own standing rule.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd
from sortedcontainers import SortedList

from fit_engine import explode, fit_mnl_ridge, score_holdout, calibration_table

# ---------------------------------------------------------------------------
# Variable sets and blocks
# ---------------------------------------------------------------------------

VAR_10 = ["AVESPRAT", "LSPEDRAT", "LIFE_PCT_WIN", "W_PER_RACE", "JOCK_PCT_WIN",
          "JOCK_NUM_WIN", "WEIGHT", "POSTPOS", "NEWDIST", "CAREER_STARTS"]

BLOCKS_10 = {
    "스피드": ["AVESPRAT", "LSPEDRAT"],
    "전적": ["LIFE_PCT_WIN", "W_PER_RACE"],
    "기수": ["JOCK_PCT_WIN", "JOCK_NUM_WIN"],
    "경주 조건": ["WEIGHT", "POSTPOS", "NEWDIST"],
    "경험": ["CAREER_STARTS"],
}

LAMBDA = 100.0
TRAIN_CUTOFF = "2023-12-31"
ROLLING_MONTHS = 36
MIN_REFERENCE_ROWS = 5000


# ---------------------------------------------------------------------------
# 1. Estimation sample (fitting only -- never used for scoring)
# ---------------------------------------------------------------------------

def build_estimation_sample_race_safe(df: pd.DataFrame, var_list: list[str],
                                       extra_filters: Optional[pd.Series] = None) -> pd.DataFrame:
    """Same base-eligibility filters as fit_engine.build_estimation_sample
    (distance 1600-2000, track_condition in (건,양), horse_age>=3, rank<90),
    but with race_safe=True semantics reimplemented per Gate2_Report.md: if
    ANY base-eligible horse in a race is missing a required feature, the
    WHOLE race is dropped, not just that horse. This guarantees the true
    winner is never silently dropped from a race that otherwise survives.
    """
    df = df.copy()
    df["race_date"] = pd.to_datetime(df["race_date"])

    mask = (
        (df["distance"] >= 1600) & (df["distance"] <= 2000) &
        (df["track_condition"].isin(["건", "양"])) &
        (df["horse_age"] >= 3) &
        (df["rank"] < 90)
    )
    if extra_filters is not None:
        mask = mask & extra_filters

    base = df.loc[mask].copy()
    has_null = base[var_list].isna().any(axis=1)
    races_with_null = set(base.loc[has_null, "race_id"].unique())
    sample = base[~base["race_id"].isin(races_with_null)].copy()

    field_size = sample.groupby("race_id")["race_id"].transform("size")
    sample = sample[field_size >= 2].copy()
    return sample


def sample_diagnostics(df: pd.DataFrame, sample: pd.DataFrame, var_list: list[str]) -> dict:
    """Transparency report for a race_safe estimation sample: race/starter
    counts, missing-winner rate, field size before/after."""
    n_races_before = df["race_id"].nunique()
    n_races_after = sample["race_id"].nunique()
    winners = df[df["is_win"] == 1]
    winners_in_sample = winners["race_id"].isin(set(sample["race_id"])) & \
        winners.set_index(["race_id", "horse_id"]).index.isin(
            sample.set_index(["race_id", "horse_id"]).index
        ) if len(winners) else pd.Series(dtype=bool)
    return {
        "n_races_before_filter": int(n_races_before),
        "n_races_after_race_safe": int(n_races_after),
        "n_rows_after_race_safe": int(len(sample)),
        "field_size_mean": float(sample.groupby("race_id").size().mean()) if len(sample) else None,
    }


# ---------------------------------------------------------------------------
# 2. Fit (validation + production)
# ---------------------------------------------------------------------------

def fit_validation(df: pd.DataFrame, var_list: list[str], lam: float = LAMBDA) -> dict:
    """5.1 -- train on race_date <= TRAIN_CUTOFF, score 2024-01-01 .. end OOS."""
    df = df.copy()
    df["race_date"] = pd.to_datetime(df["race_date"])
    train_mask = df["race_date"] <= pd.Timestamp(TRAIN_CUTOFF)
    test_mask = df["race_date"] > pd.Timestamp(TRAIN_CUTOFF)

    train_sample = build_estimation_sample_race_safe(df, var_list, train_mask)
    test_sample = build_estimation_sample_race_safe(df, var_list, test_mask)

    train_exploded = explode(train_sample, max_depth=1, var_list=var_list)
    test_exploded = explode(test_sample, max_depth=1, var_list=var_list)

    fit = fit_mnl_ridge(train_exploded, var_list, lam=lam)
    test_r2, test_logloss, test_n = score_holdout(
        test_exploded, var_list, fit["beta_raw"], fit["mu"], fit["sigma"], lam=lam
    )
    return {
        "fit": fit,
        "train_diag": sample_diagnostics(df[train_mask], train_sample, var_list),
        "test_diag": sample_diagnostics(df[test_mask], test_sample, var_list),
        "train_pseudo_r2": fit["pseudo_r2"],
        "test_pseudo_r2": test_r2,
        "test_log_loss": test_logloss,
        "test_n_choice_sets": test_n,
    }


def fit_production(df: pd.DataFrame, var_list: list[str], lam: float = LAMBDA) -> dict:
    """5.2 -- refit on full history through the max date present, same lambda."""
    df = df.copy()
    df["race_date"] = pd.to_datetime(df["race_date"])
    sample = build_estimation_sample_race_safe(df, var_list, None)
    exploded = explode(sample, max_depth=1, var_list=var_list)
    fit = fit_mnl_ridge(exploded, var_list, lam=lam)
    return {
        "fit": fit,
        "diag": sample_diagnostics(df, sample, var_list),
        "fit_date": str(df["race_date"].max().date()),
        "lambda": lam,
        "var_list": var_list,
    }


def save_params(fit_result: dict, path: str):
    payload = {
        "beta_raw": fit_result["fit"]["beta_raw"].tolist(),
        "mu": fit_result["fit"]["mu"].tolist(),
        "sigma": fit_result["fit"]["sigma"].tolist(),
        "var_list": fit_result["var_list"],
        "fit_date": fit_result["fit_date"],
        "lambda": fit_result["lambda"],
        "train_pseudo_r2": fit_result["fit"]["pseudo_r2"],
        "n_choice_sets": fit_result["fit"]["n_choice_sets"],
        "n_rows": fit_result["fit"]["n_rows"],
    }
    with open(path, "w") as f:
        json.dump(payload, f, indent=2)


def load_params(path: str) -> dict:
    with open(path) as f:
        payload = json.load(f)
    payload["beta_raw"] = np.array(payload["beta_raw"])
    payload["mu"] = np.array(payload["mu"])
    payload["sigma"] = np.array(payload["sigma"])
    return payload


# ---------------------------------------------------------------------------
# 3. Scoring -- V for every horse-row (NO fitting-sample filters, NO explode)
# ---------------------------------------------------------------------------

def compute_V(df: pd.DataFrame, var_list: list[str], beta_raw: np.ndarray,
              mu: np.ndarray, sigma: np.ndarray) -> pd.DataFrame:
    """Plain matrix product V = ((X - mu) / sigma) @ beta_raw for every row
    with non-null values across var_list. No distance/age/track_condition/
    rank filters -- those are fitting-sample-only concerns (see module
    docstring and plan section 2)."""
    df = df.copy()
    valid = df[var_list].notna().all(axis=1)
    scored = df.loc[valid].copy()
    X = scored[var_list].to_numpy(dtype=float)
    Xs = (X - mu) / sigma
    scored["V"] = Xs @ beta_raw
    return scored


def compute_fund_p(scored: pd.DataFrame) -> pd.DataFrame:
    """fund_p = softmax(V) within race_id -- the secondary, race-relative
    '우승 기대도'. Field-dependent by design; not the headline score."""
    scored = scored.copy()

    def _softmax(v):
        m = v.max()
        e = np.exp(v - m)
        return e / e.sum()

    scored["fund_p"] = scored.groupby("race_id")["V"].transform(_softmax)
    return scored


# ---------------------------------------------------------------------------
# 4. Rolling-reference percentile score (0-100)
# ---------------------------------------------------------------------------

def rolling_percentile_score(scored: pd.DataFrame, value_col: str,
                              months: int = ROLLING_MONTHS,
                              min_rows: int = MIN_REFERENCE_ROWS,
                              out_col: str = None) -> pd.Series:
    """For each row, percentile rank of value_col against a rolling reference
    population: trailing `months` months as of that row's race_date
    (inclusive), falling back to an expanding window (all rows up to and
    including that date) if the trailing window has fewer than `min_rows`.
    Uses a sliding SortedList so this is O(n log n), not O(n^2)."""
    out_col = out_col or f"{value_col}_pctile"
    s = scored[["race_date", value_col]].copy()
    s["race_date"] = pd.to_datetime(s["race_date"])
    s = s.sort_values("race_date", kind="mergesort")
    order = s.index.to_numpy()

    dates = s["race_date"].to_numpy()
    values = s[value_col].to_numpy(dtype=float)

    pctile = np.empty(len(s), dtype=float)

    unique_dates, start_idx = np.unique(dates, return_index=True)
    start_idx = list(start_idx) + [len(dates)]

    cutoff_days = months * 30  # approx trailing window in days, consistent with "trailing N months"

    trailing_vals = SortedList()
    from collections import deque
    trailing_pairs = deque()  # (date, value), date-ordered since we process in date order
    expanding_vals = SortedList()

    for i in range(len(unique_dates)):
        lo, hi = start_idx[i], start_idx[i + 1]
        d = unique_dates[i]
        for j in range(lo, hi):
            v = values[j]
            trailing_vals.add(v)
            trailing_pairs.append((d, v))
            expanding_vals.add(v)

        cutoff = d - np.timedelta64(cutoff_days, "D")
        while trailing_pairs and trailing_pairs[0][0] < cutoff:
            _, old_v = trailing_pairs.popleft()
            trailing_vals.remove(old_v)

        use_trailing = len(trailing_vals) >= min_rows
        ref = trailing_vals if use_trailing else expanding_vals
        n = len(ref)
        for j in range(lo, hi):
            v = values[j]
            rank = ref.bisect_right(v)  # count of ref values <= v
            pctile[j] = rank / n if n > 0 else np.nan

    result = pd.Series(pctile, index=order, name=out_col).sort_index()
    return result


def ability_score_from_pctile(pctile: pd.Series) -> pd.Series:
    """0-100 integer, clipped to [1, 99] per plan section 3 (matches Racing
    Joy's existing 종합점수 display grammar, '-' reserved for no-score)."""
    score = np.round(100 * pctile).astype("Int64")
    score = score.clip(lower=1, upper=99)
    return score


# ---------------------------------------------------------------------------
# 5. Block decomposition
# ---------------------------------------------------------------------------

def block_contributions(scored: pd.DataFrame, var_list: list[str], blocks: dict,
                         beta_raw: np.ndarray, mu: np.ndarray, sigma: np.ndarray) -> pd.DataFrame:
    """V is an exact sum of standardized_x_j * beta_j. Group into blocks;
    sum of all block contributions reproduces V exactly (checked in caller).

    Also stores `zraw_{block}` = the mean STANDARDIZED (but NOT beta-weighted)
    value of that block's variables for this horse. This answers a different
    question than contrib_{block}: contrib tells you whether the block pushed
    V up or down; zraw tells you whether the horse's actual raw stats in that
    block are above or below average. The two can point opposite ways when a
    block's dominant variable has a negative coefficient (e.g. CAREER_STARTS
    in 경험 -- fewer starts is what drives a positive contribution). Needed so
    generate_story() can describe *why* a block helped/hurt instead of just
    asserting the block name is a "strength," which reads as false for
    negative-coefficient blocks (see conversation: a 1-start horse being
    described as having "경험 강점" is backwards).
    """
    scored = scored.copy()
    X = scored[var_list].to_numpy(dtype=float)
    Xs = (X - mu) / sigma
    contrib_by_var = Xs * beta_raw  # elementwise, columns aligned to var_list

    var_idx = {v: i for i, v in enumerate(var_list)}
    for block_name, block_vars in blocks.items():
        idxs = [var_idx[v] for v in block_vars]
        scored[f"contrib_{block_name}"] = contrib_by_var[:, idxs].sum(axis=1)
        scored[f"zraw_{block_name}"] = Xs[:, idxs].mean(axis=1)
    return scored


def add_block_subscores(scored: pd.DataFrame, blocks: dict,
                         months: int = ROLLING_MONTHS,
                         min_rows: int = MIN_REFERENCE_ROWS) -> pd.DataFrame:
    scored = scored.copy()
    for block_name in blocks:
        col = f"contrib_{block_name}"
        pctile = rolling_percentile_score(scored, col, months, min_rows, out_col=f"{col}_pctile")
        scored[f"subscore_{block_name}"] = ability_score_from_pctile(pctile)
    return scored


# ---------------------------------------------------------------------------
# 6. Story generation (templated, no LLM)
# ---------------------------------------------------------------------------

# Blocks where the dominant variable carries a NEGATIVE coefficient (currently
# just 경험 / CAREER_STARTS: fewer starts -> higher contribution). For these,
# a positive contribution is driven by a BELOW-average raw stat, and a
# negative contribution by an ABOVE-average raw stat -- the opposite of every
# other block. Saying "{block} 부문이 강점" in that situation is backwards: it
# reads as "this horse has a lot of X and that's good," when what's actually
# true is "this horse has little X, and the model treats that as upside."
# These phrase pairs describe the real direction instead. Sourced against how
# Korean racing coverage actually talks about lightly-raced horses (신예,
# 성장세, 잠재력 all appear in racing-press previews for this exact situation;
# "저출주" does not seem to be an attested term, so it's avoided).
INVERTED_STRENGTH_PHRASES = {
    "경험": "출전 경험이 적은 신예로, 그 성장 잠재력이 종합 지수에는 강점으로 반영되었으며",
}
INVERTED_WEAKNESS_PHRASES = {
    "경험": "출전 경험이 많은 편이지만, 종합 지수에는 상대적으로 낮게 반영되었으며",
}
_INVERT_THRESHOLD = 0.1  # deadzone on the raw z-score; below this, direction is too noisy to call


def _strength_clause(block: str, sub_score: int, contrib: float, zraw: float) -> str:
    if contrib > 0 and zraw < -_INVERT_THRESHOLD:
        phrase = INVERTED_STRENGTH_PHRASES.get(
            block, f"{block} 관련 수치는 평균 이하이지만 종합 지수에는 강점으로 반영되었으며"
        )
        return f"{phrase} ({sub_score}점)"
    return f"{block} 부문이 강점이며 ({sub_score}점)"


def _weakness_clause(block: str, sub_score: int, contrib: float, zraw: float) -> str:
    if contrib < 0 and zraw > _INVERT_THRESHOLD:
        phrase = INVERTED_WEAKNESS_PHRASES.get(
            block, f"{block} 관련 수치는 평균 이상이지만 종합 지수에는 상대적으로 낮게 반영되었습니다"
        )
        return f"{phrase} ({sub_score}점)"
    return f"{block} 부문은 상대적으로 낮습니다 ({sub_score}점)"


def generate_story(score: int, block_scores: dict[str, int], block_contribs: dict[str, float],
                    block_zraw: Optional[dict[str, float]] = None) -> str:
    """Rules, in order, per plan section 7:
      1. Largest positive contribution -> 강점.
      2. Largest negative contribution -> 약점.
      3. If one block's |contribution| > 50% of total |contribution| -> 편중형.
      4. If all blocks within a narrow band -> 균형형.
    Descriptive only. No causal/predictive language.

    block_zraw: mean standardized (not beta-weighted) raw value per block, from
    block_contributions()'s zraw_{block} columns. Used to phrase 강점/약점
    correctly when a block's dominant variable has a negative coefficient (see
    INVERTED_STRENGTH_PHRASES above) -- optional for backward compatibility,
    but strongly recommended; omitting it falls back to the old "{block} 부문이
    강점" wording for every block, which is known to misdescribe 경험 for
    lightly-raced horses.
    """
    strongest = max(block_contribs, key=lambda k: block_contribs[k])
    weakest = min(block_contribs, key=lambda k: block_contribs[k])
    block_zraw = block_zraw or {}

    total_abs = sum(abs(v) for v in block_contribs.values())
    lopsided = None
    if total_abs > 0:
        max_share = max(abs(v) for v in block_contribs.values()) / total_abs
        if max_share > 0.5:
            lopsided = max(block_contribs, key=lambda k: abs(block_contribs[k]))

    vals = list(block_contribs.values())
    balanced = (max(vals) - min(vals)) < 0.15 * (max(abs(v) for v in vals) + 1e-9) if vals else False

    strength_clause = _strength_clause(
        strongest, block_scores[strongest], block_contribs[strongest], block_zraw.get(strongest, 0.0)
    )
    weakness_clause = _weakness_clause(
        weakest, block_scores[weakest], block_contribs[weakest], block_zraw.get(weakest, 0.0)
    )

    lines = [f"종합 능력 {score}점 (상위 {100 - score}%)."]
    lines.append(f"{strength_clause}, {weakness_clause}.")
    if lopsided:
        lines.append(f"{lopsided} 부문 비중이 커서 편중형 유형에 가깝습니다.")
    elif balanced:
        lines.append("각 부문 점수가 고르게 분포된 균형형입니다.")
    return " ".join(lines)


# ---------------------------------------------------------------------------
# 7. Production interface -- mirrors market_tags.tag_race()
# ---------------------------------------------------------------------------

@dataclass
class RatingResult:
    horse_num: int
    horse_id: Optional[int]
    ability_score: int          # 종합 능력 점수, 0-100 (1-99 in practice)
    win_expectancy: float       # 우승 기대도 (fund_p), race-relative
    sub_scores: dict            # block name -> 0-100 int
    story: str
    var_set: str = "10var"       # kept for output-schema stability; always "10var" now

    def explain(self) -> str:
        return self.story


def build_reference_snapshot(scored: pd.DataFrame, blocks: dict,
                              months: int = ROLLING_MONTHS,
                              min_rows: int = MIN_REFERENCE_ROWS) -> dict:
    """Freeze the rolling reference population as of the LATEST date present
    in `scored`, for use scoring brand-new races in production (races that
    aren't in the historical file at all, so there's nothing to compute a
    rolling window from at request time). Stores sorted arrays for V and
    every block's contribution -- exactly the columns score_race() needs
    percentiles for.

    This is a frozen point-in-time snapshot, not a live rolling window. It
    WILL go stale as real time passes the `as_of_date` baked into it -- see
    DEPLOYMENT.md for the refresh cadence. Rebuilding it is just: re-run the
    scoring pipeline on updated data and call this function again.
    """
    scored = scored.copy()
    scored["race_date"] = pd.to_datetime(scored["race_date"])
    as_of = scored["race_date"].max()
    cutoff = as_of - pd.DateOffset(months=months)
    window = scored[scored["race_date"] > cutoff]
    used_expanding = len(window) < min_rows
    if used_expanding:
        window = scored

    cols = ["V"] + [f"contrib_{b}" for b in blocks]
    snapshot = {
        "as_of_date": str(as_of.date()),
        "window_months": months,
        "used_expanding_fallback": bool(used_expanding),
        "n_reference_rows": int(len(window)),
        "columns": {c: sorted(window[c].dropna().astype(float).tolist()) for c in cols},
    }
    return snapshot


def save_reference_snapshot(snapshot: dict, path: str):
    with open(path, "w") as f:
        json.dump(snapshot, f)


def load_reference_snapshot(path: str) -> dict:
    with open(path) as f:
        return json.load(f)


def _make_pctile_fn(sorted_vals: list[float]):
    arr = np.array(sorted_vals)
    n = len(arr)

    def fn(values: np.ndarray) -> np.ndarray:
        ranks = np.searchsorted(arr, values, side="right")
        return ranks / n if n > 0 else np.full_like(values, np.nan, dtype=float)

    return fn


def score_race(horses: list[dict], var_list: list[str], blocks: dict,
               beta_raw: np.ndarray, mu: np.ndarray, sigma: np.ndarray,
               reference_snapshot: Optional[dict] = None,
               var_set_label: str = "10var") -> list["RatingResult"]:
    """horses: list of dicts, each with 'horse_num', 'horse_id', and the
    features in var_list. reference_snapshot: output of
    build_reference_snapshot() / load_reference_snapshot() -- supplies a
    separate percentile reference for V AND for each block's contribution
    (these are different distributions; using one function for both, as an
    earlier version of this file did, silently produced wrong sub-scores).
    If omitted, percentiles are computed within just this race (degrades
    gracefully for ad-hoc use, NOT recommended for real display -- always
    supply reference_snapshot in production)."""
    if len(horses) < 2:
        raise ValueError("need at least 2 horses to compute a race")

    df = pd.DataFrame(horses)
    missing = [v for v in var_list if v not in df.columns]
    if missing:
        raise ValueError(f"missing required features: {missing}")

    X = df[var_list].to_numpy(dtype=float)
    Xs = (X - mu) / sigma
    V = Xs @ beta_raw

    var_idx = {v: i for i, v in enumerate(var_list)}
    contrib_by_var = Xs * beta_raw

    e = np.exp(V - V.max())
    fund_p = e / e.sum()

    if reference_snapshot is not None:
        v_fn = _make_pctile_fn(reference_snapshot["columns"]["V"])
        pctile = v_fn(V)
        block_fns = {b: _make_pctile_fn(reference_snapshot["columns"][f"contrib_{b}"]) for b in blocks}
    else:
        pctile = pd.Series(V).rank(pct=True).to_numpy()
        block_fns = None

    scores = np.clip(np.round(100 * pctile), 1, 99).astype(int)

    results = []
    for i, row in df.iterrows():
        block_contribs = {}
        block_zraw = {}
        block_scores = {}
        for bname, bvars in blocks.items():
            idxs = [var_idx[v] for v in bvars]
            block_contribs[bname] = float(contrib_by_var[i, idxs].sum())
            block_zraw[bname] = float(Xs[i, idxs].mean())
        if block_fns is not None:
            block_pctiles = {b: block_fns[b](np.array([block_contribs[b]]))[0] for b in blocks}
        else:
            block_pctiles = {b: 0.5 for b in blocks}  # neutral fallback, single race has no ref
        for b in blocks:
            block_scores[b] = int(np.clip(round(100 * block_pctiles[b]), 1, 99))

        story = generate_story(int(scores[i]), block_scores, block_contribs, block_zraw)
        results.append(RatingResult(
            horse_num=row.get("horse_num"),
            horse_id=row.get("horse_id"),
            ability_score=int(scores[i]),
            win_expectancy=float(fund_p[i]),
            sub_scores=block_scores,
            story=story,
            var_set=var_set_label,
        ))
    return results
