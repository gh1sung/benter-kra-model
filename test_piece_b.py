"""
test_piece_b.py

Cheap, data-independent unit tests for Piece B's analysis functions
(run_piece_b.py) plus the EV-formula worked example from the plan (§3).
None of these need piece_b_dataset.csv, exotic_odds_5yr.csv, or the raw
finish-rank pull -- everything here runs on synthetic data or bare
arithmetic, so it can be run and trusted before those inputs exist.
"""
import numpy as np
import pandas as pd

from run_piece_b import ev_backtest, log_loss, winning_pair_log_loss
from harville_engine import quinella_probs


# ---------------------------------------------------------------------------
# EV formula -- worked example from the plan (§3): pair (1,4),
# q_model=0.215, d=4.7 -> EV = 0.215*4.7 - 1 = +0.010
# ---------------------------------------------------------------------------

def test_ev_worked_example_arithmetic():
    ev = 0.215 * 4.7 - 1
    assert np.isclose(ev, 0.0105, atol=1e-4)


def test_ev_worked_example_via_backtest_helper():
    df = pd.DataFrame([{"race_id": "r1", "year": 2026, "q_model": 0.215, "d": 4.7, "y": 0}])
    result = ev_backtest(df, tau=0.0)
    assert result["n_bets"] == 1
    assert np.isclose(result["staked"], 1.0)


def test_ev_worked_example_skip_pair():
    """Contrast pair (1,3) from the same worked example: q_model=0.054,
    d=10.2 -> EV = -0.446, should NOT clear tau=0."""
    df = pd.DataFrame([{"race_id": "r1", "year": 2026, "q_model": 0.054, "d": 10.2, "y": 0}])
    result = ev_backtest(df, tau=0.0)
    assert result["n_bets"] == 0


# ---------------------------------------------------------------------------
# Gate B0 checks -- sum-to-1 and one-hit-per-race, on synthetic data
# ---------------------------------------------------------------------------

def test_q_model_sums_to_one_synthetic_race():
    p = {1: 0.319, 4: 0.242, 6: 0.173, 2: 0.10, 3: 0.09, 5: 0.076}
    q = quinella_probs(p, lam=0.8)
    assert np.isclose(sum(q.values()), 1.0, atol=1e-9)


def test_exactly_one_y_per_race_synthetic():
    df = pd.DataFrame([
        {"race_id": "r1", "pair": "1|4", "y": 0},
        {"race_id": "r1", "pair": "1|6", "y": 1},
        {"race_id": "r1", "pair": "4|6", "y": 0},
        {"race_id": "r2", "pair": "2|3", "y": 1},
    ])
    per_race_y = df.groupby("race_id")["y"].sum()
    assert (per_race_y == 1).all()


def test_multiple_y_per_race_is_caught():
    """A buggy join could double-count the realized pair -- confirm the
    Gate B0 check would actually flag it rather than silently pass."""
    df = pd.DataFrame([
        {"race_id": "r1", "pair": "1|4", "y": 1},
        {"race_id": "r1", "pair": "1|4", "y": 1},  # duplicate row = bug
    ])
    per_race_y = df.groupby("race_id")["y"].sum()
    assert (per_race_y != 1).any()


# ---------------------------------------------------------------------------
# log-loss sanity
# ---------------------------------------------------------------------------

def test_log_loss_prefers_correct_model():
    df_good = pd.DataFrame([
        {"q_good": 0.8, "y": 1}, {"q_good": 0.1, "y": 0}, {"q_good": 0.1, "y": 0},
    ])
    df_bad = pd.DataFrame([
        {"q_bad": 0.2, "y": 1}, {"q_bad": 0.4, "y": 0}, {"q_bad": 0.4, "y": 0},
    ])
    assert log_loss(df_good, "q_good") < log_loss(df_bad, "q_bad")


def test_winning_pair_log_loss_only_uses_hits():
    df = pd.DataFrame([
        {"q_model": 0.5, "y": 1},
        {"q_model": 0.01, "y": 0},
        {"q_model": 0.01, "y": 0},
    ])
    ll = winning_pair_log_loss(df, "q_model")
    assert np.isclose(ll, -np.log(0.5), atol=1e-9)


# ---------------------------------------------------------------------------
# EV backtest edge cases
# ---------------------------------------------------------------------------

def test_ev_backtest_no_qualifying_bets_returns_nan_roi():
    df = pd.DataFrame([{"race_id": "r1", "year": 2026, "q_model": 0.05, "d": 2.0, "y": 0}])
    result = ev_backtest(df, tau=1.0)  # EV = 0.05*2-1 = -0.9, well below tau=1.0
    assert result["n_bets"] == 0
    assert np.isnan(result["roi"])


def test_ev_backtest_roi_matches_hand_calc():
    """2 bets, 1 hit at dividend 4.7: staked=2, returned=4.7, ROI = (4.7-2)/2 = 1.35."""
    df = pd.DataFrame([
        {"race_id": "r1", "year": 2026, "q_model": 0.215, "d": 4.7, "y": 1},
        {"race_id": "r2", "year": 2026, "q_model": 0.215, "d": 4.7, "y": 0},
    ])
    result = ev_backtest(df, tau=0.0)
    assert result["n_bets"] == 2
    assert np.isclose(result["roi"], 1.35, atol=1e-9)
