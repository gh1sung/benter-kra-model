"""
test_harville_engine.py

Gate A0 (plumbing sanity) for Piece A. Two kinds of checks:

1. Self-consistency: do the returned distributions sum to what they should
   (1 for exacta/quinella/trifecta/trio, `top` for place)?
2. Independent correctness: a from-scratch brute-force implementation
   (full-permutation enumeration, coded independently of harville_engine's
   closed-form _cond helper) that the closed-form results must match. This
   catches bugs the self-consistency checks can't (e.g. a systematically
   wrong-but-still-normalized formula).
"""
from itertools import permutations

import numpy as np
import pytest

from harville_engine import (
    exacta_probs,
    quinella_probs,
    trifecta_probs,
    trio_probs,
    place_probs,
)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def random_probs(n, seed):
    rng = np.random.default_rng(seed)
    raw = rng.uniform(0.1, 1.0, size=n)
    return raw / raw.sum()


def brute_force_ranking_prob(order, probs, lam=1.0):
    """P(this exact full ranking), built independently from the module:
    win draw uses raw probs; every draw after uses probs**lam among the
    still-remaining horses. This is the textbook Plackett-Luce / Harville
    chain-rule definition, coded from scratch (no shared helper with
    harville_engine.py)."""
    n = len(order)
    excluded = set()
    prob = 1.0
    for t, idx in enumerate(order):
        weights = probs if t == 0 else (probs if lam == 1.0 else probs ** lam)
        denom = sum(weights[k] for k in range(n) if k not in excluded)
        prob *= weights[idx] / denom
        excluded.add(idx)
    return prob


def brute_force_prefix_prob(prefix, n, probs, lam=1.0):
    """P(ranking starts with exactly this prefix, any order for the rest),
    by summing the joint probability over every full-permutation extension
    of the prefix. Independent of harville_engine's closed-form shortcut."""
    remaining = [i for i in range(n) if i not in prefix]
    if not remaining:
        return brute_force_ranking_prob(list(prefix), probs, lam)
    total = 0.0
    for tail in permutations(remaining):
        total += brute_force_ranking_prob(list(prefix) + list(tail), probs, lam)
    return total


# ---------------------------------------------------------------------------
# 1. sum-to-1 checks, n = 3, 5, 8, 12
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("n", [3, 5, 8, 12])
def test_exacta_sums_to_one(n):
    p = random_probs(n, seed=n)
    ex = exacta_probs(p)
    assert np.isclose(sum(ex.values()), 1.0, atol=1e-9)
    assert len(ex) == n * (n - 1)  # every ordered pair


@pytest.mark.parametrize("n", [3, 5, 8, 12])
def test_quinella_sums_to_one(n):
    p = random_probs(n, seed=n + 100)
    q = quinella_probs(p)
    assert np.isclose(sum(q.values()), 1.0, atol=1e-9)
    assert len(q) == n * (n - 1) // 2  # every unordered pair


@pytest.mark.parametrize("n", [3, 5, 8, 12])
def test_trifecta_sums_to_one(n):
    p = random_probs(n, seed=n + 200)
    tf = trifecta_probs(p)
    assert np.isclose(sum(tf.values()), 1.0, atol=1e-9)
    assert len(tf) == n * (n - 1) * (n - 2)  # every ordered triple


@pytest.mark.parametrize("n", [3, 5, 8, 12])
def test_trio_sums_to_one(n):
    p = random_probs(n, seed=n + 300)
    tr = trio_probs(p)
    assert np.isclose(sum(tr.values()), 1.0, atol=1e-9)
    assert len(tr) == n * (n - 1) * (n - 2) // 6  # every unordered triple


# ---------------------------------------------------------------------------
# 2. worked example from the Piece A spec (A=0.50, B=0.30, C=0.20)
# ---------------------------------------------------------------------------

def test_worked_example_quinella():
    p = {"A": 0.50, "B": 0.30, "C": 0.20}
    q = quinella_probs(p)
    assert np.isclose(q[frozenset({"A", "B"})], 0.514285714, atol=1e-6)
    assert np.isclose(q[frozenset({"A", "C"})], 0.325, atol=1e-6)
    assert np.isclose(q[frozenset({"B", "C"})], 0.160714286, atol=1e-6)
    assert np.isclose(sum(q.values()), 1.0, atol=1e-9)


def test_worked_example_exacta_matches_hand_calc():
    p = {"A": 0.50, "B": 0.30, "C": 0.20}
    ex = exacta_probs(p)
    assert np.isclose(ex[("A", "B")], 0.30, atol=1e-9)
    assert np.isclose(ex[("B", "A")], 0.30 * 0.5 / 0.7, atol=1e-9)


# ---------------------------------------------------------------------------
# 3. quinella(i,j) == exacta(i,j) + exacta(j,i)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("n", [4, 6, 9])
def test_quinella_equals_sum_of_exactas(n):
    p = random_probs(n, seed=n + 400)
    ex = exacta_probs(p)
    q = quinella_probs(p)
    for (i, j), pij in ex.items():
        key = frozenset((i, j))
        assert np.isclose(q[key], ex[(i, j)] + ex[(j, i)], atol=1e-9)


# ---------------------------------------------------------------------------
# 4. place_probs(top=2) sums to 2.0 (and top=1 / top=3 sanity)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("n", [3, 5, 8, 12])
def test_place_top2_sums_to_two(n):
    p = random_probs(n, seed=n + 500)
    pl = place_probs(p, top=2)
    assert np.isclose(sum(pl.values()), 2.0, atol=1e-9)


@pytest.mark.parametrize("n", [4, 6])
def test_place_top1_equals_win_probs(n):
    p = random_probs(n, seed=n + 600)
    pl = place_probs(p, top=1)
    for idx, val in enumerate(pl.values()):
        assert np.isclose(val, p[idx], atol=1e-9)


@pytest.mark.parametrize("n", [4, 6])
def test_place_top3_sums_to_three(n):
    p = random_probs(n, seed=n + 700)
    pl = place_probs(p, top=3)
    assert np.isclose(sum(pl.values()), 3.0, atol=1e-9)


def test_place_top_out_of_range_raises():
    with pytest.raises(ValueError):
        place_probs([0.5, 0.3, 0.2], top=4)


# ---------------------------------------------------------------------------
# 5. lam=1.0 reproduces plain Harville exactly
# ---------------------------------------------------------------------------

def test_lam_one_matches_default():
    p = random_probs(6, seed=999)
    assert exacta_probs(p) == exacta_probs(p, lam=1.0)
    assert trifecta_probs(p) == trifecta_probs(p, lam=1.0)


# ---------------------------------------------------------------------------
# 6. independent brute-force cross-check (the real correctness test) --
#    small n only, since it enumerates (n - len(prefix))! permutations
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("lam", [1.0, 0.8])
@pytest.mark.parametrize("n", [4, 5, 6])
def test_exacta_matches_brute_force(n, lam):
    p = random_probs(n, seed=n * 13 + 1)
    ex = exacta_probs(p, lam=lam)
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            expected = brute_force_prefix_prob((i, j), n, p, lam=lam)
            assert np.isclose(ex[(i, j)], expected, atol=1e-9), (n, lam, i, j)


@pytest.mark.parametrize("lam", [1.0, 0.8])
@pytest.mark.parametrize("n", [4, 5, 6])
def test_trifecta_matches_brute_force(n, lam):
    p = random_probs(n, seed=n * 17 + 2)
    tf = trifecta_probs(p, lam=lam)
    for i in range(n):
        for j in range(n):
            if j == i:
                continue
            for k in range(n):
                if k in (i, j):
                    continue
                expected = brute_force_prefix_prob((i, j, k), n, p, lam=lam)
                assert np.isclose(tf[(i, j, k)], expected, atol=1e-9), (n, lam, i, j, k)


@pytest.mark.parametrize("lam", [1.0, 0.8])
def test_place_matches_brute_force(lam):
    n = 5
    p = random_probs(n, seed=42)
    pl2 = place_probs(p, top=2, lam=lam)
    for i in range(n):
        # P(i in top 2) = P(i 1st) + sum_j P(j,i) prefix
        expected = p[i] + sum(
            brute_force_prefix_prob((j, i), n, p, lam=lam) for j in range(n) if j != i
        )
        assert np.isclose(pl2[i], expected, atol=1e-9)
