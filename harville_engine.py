"""
harville_engine.py

Pure Harville-formula engine: converts a vector of per-horse WIN probabilities
into exotic-bet probabilities (exacta, quinella, trifecta, trio, place).

Input-agnostic by design: this module knows nothing about odds, files, or
Korea. It takes a win-probability vector in and returns exotic probabilities
out. That is the whole point of Piece A -- once this engine is validated on
public win probabilities, Piece B and the combined model can feed it any
calibrated win-prob vector (public, model-derived, or blended) with zero
rework here.

Formulas implemented (Harville 1973), with an optional Stern (1990) /
Lo & Bacon-Shone lambda discount on the 2nd/3rd-place conditional draws
(the standard correction for Harville's known favorite-place overestimate):

    Exacta(i,j)     = p_i * cond(j | exclude={i})
    Quinella(i,j)   = Exacta(i,j) + Exacta(j,i)
    Trifecta(i,j,k) = p_i * cond(j | exclude={i}) * cond(k | exclude={i,j})
    Trio({i,j,k})   = sum of Trifecta(...) over all 6 orderings of {i,j,k}
    Place(i, top)   = sum over ranks r = 1..top of P(i finishes EXACTLY at rank r)

where cond(x | exclude=S), the (possibly lambda-discounted) conditional draw
probability of horse x being drawn next given the horses in S are already
placed, is:

    cond(x | exclude=S) = p_x^lam / sum_{y not in S} p_y^lam

lam=1.0 (the default) recovers plain Harville exactly:
    cond(x | exclude=S) = p_x / sum_{y not in S} p_y

The win draw itself (the leading p_i factor in Exacta/Trifecta) is NEVER
discounted -- only the subsequent 2nd-place and 3rd-place conditional draws
are, per the documented correction. Discounting the win draw too would not
match Stern / Lo & Bacon-Shone and would also break sum-to-1 for the win
market itself.
"""

from itertools import permutations
import numpy as np


def _normalize_input(p):
    """Accepts a dict {label: prob} or a plain list/array of probs.
    Returns (labels: list, probs: np.ndarray). Does NOT re-normalize the
    probabilities -- callers are responsible for passing a vector that
    already sums to 1 for a given race (Piece A's join step re-normalizes
    after dropping scratches, per the standing project rule)."""
    if isinstance(p, dict):
        labels = list(p.keys())
        probs = np.array([p[l] for l in labels], dtype=float)
    else:
        probs = np.asarray(p, dtype=float)
        labels = list(range(len(probs)))
    return labels, probs


def _cond(probs, target_idx, excluded, lam):
    """P(horse `target_idx` is drawn next | horses in `excluded` already
    drawn), with the lambda discount applied to the remaining pool."""
    if lam == 1.0:
        weights = probs
    else:
        weights = probs ** lam
    denom = sum(weights[k] for k in range(len(probs)) if k not in excluded)
    return weights[target_idx] / denom


def exacta_probs(p, lam=1.0):
    """P(i finishes 1st AND j finishes 2nd), for every ordered pair i != j.
    Returns dict {(label_i, label_j): prob}."""
    labels, probs = _normalize_input(p)
    n = len(probs)
    out = {}
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            cond_j = _cond(probs, j, {i}, lam)
            out[(labels[i], labels[j])] = probs[i] * cond_j
    return out


def quinella_probs(p, lam=1.0):
    """P(i and j fill the top two spots, in either order), for every
    unordered pair. Returns dict {frozenset({label_i, label_j}): prob}."""
    ex = exacta_probs(p, lam=lam)
    out = {}
    seen = set()
    for (i, j) in ex:
        key = frozenset((i, j))
        if key in seen:
            continue
        seen.add(key)
        out[key] = ex[(i, j)] + ex[(j, i)]
    return out


def trifecta_probs(p, lam=1.0):
    """P(i 1st, j 2nd, k 3rd, exact order), for every ordered triple.
    Returns dict {(label_i, label_j, label_k): prob}."""
    labels, probs = _normalize_input(p)
    n = len(probs)
    out = {}
    for i in range(n):
        for j in range(n):
            if j == i:
                continue
            cond_j = _cond(probs, j, {i}, lam)
            pij = probs[i] * cond_j
            for k in range(n):
                if k == i or k == j:
                    continue
                cond_k = _cond(probs, k, {i, j}, lam)
                out[(labels[i], labels[j], labels[k])] = pij * cond_k
    return out


def trio_probs(p, lam=1.0):
    """P({i,j,k} fill the top three spots, any order), for every unordered
    triple. Returns dict {frozenset({label_i, label_j, label_k}): prob}."""
    tri = trifecta_probs(p, lam=lam)
    out = {}
    seen = set()
    for (i, j, k) in tri:
        key = frozenset((i, j, k))
        if key in seen:
            continue
        seen.add(key)
        out[key] = sum(tri[perm] for perm in permutations((i, j, k)))
    return out


def place_probs(p, top=2, lam=1.0):
    """P(horse i finishes in the top `top` positions), for every horse.
    Sums to `top` (not 1) because `top` spots get filled each race.
    top=1 is just the win probabilities passed in. top=2 uses exacta;
    top=3 additionally uses trifecta. Returns dict {label: prob}."""
    labels, probs = _normalize_input(p)
    if top not in (1, 2, 3):
        raise ValueError("place_probs only supports top in {1, 2, 3}")

    out = {label: 0.0 for label in labels}
    for idx, label in enumerate(labels):
        out[label] += probs[idx]  # P(exactly 1st)
    if top == 1:
        return out

    ex = exacta_probs(p, lam=lam)
    for (i, j), pij in ex.items():
        out[j] += pij  # P(exactly 2nd): j is 2nd when i won
    if top == 2:
        return out

    tri = trifecta_probs(p, lam=lam)
    for (i, j, k), pijk in tri.items():
        out[k] += pijk  # P(exactly 3rd): k is 3rd when i,j went 1st,2nd
    return out
