"""
lucky_engine.py — M0/M1/M2 similarity scoring for the Lucky Engine test.

Fingerprint features (plan §0.3, all knowable 25min before post):
    ln_odds_25, rank_25, exp_rank_in_race, fund_p, n_starters

Methods (plan §2):
    M1 = Mahalanobis distance to the BUILD-reference centroid  (similarity = -dist)
    M2 = kNN: negative mean Euclidean distance to the k nearest BUILD refs,
         k = round(sqrt(n_refs_build))  (plan §0.4, fixed by rule not tuned)
    M0 = random shuffle of the M1 scores within TEST (fixed seed) — null floor
"""
import numpy as np

FEATURES = ["ln_odds_25", "rank_25", "exp_rank_in_race", "fund_p", "n_starters"]


def standardize(build_pool, *frames):
    """Standardize FEATURES using mean/sd from the BUILD-window ELIGIBLE pool
    only (plan §3.2). Returns standardized numpy matrices for each frame."""
    mu = build_pool[FEATURES].mean().to_numpy(float)
    sd = build_pool[FEATURES].std(ddof=0).to_numpy(float)
    sd = np.where(sd == 0, 1.0, sd)
    return [((f[FEATURES].to_numpy(float) - mu) / sd) for f in frames], mu, sd


def m1_mahalanobis(refs_std, test_std):
    """Similarity = -Mahalanobis distance from each TEST row to the reference
    centroid. Covariance estimated from BUILD references."""
    centroid = refs_std.mean(axis=0)
    cov = np.cov(refs_std, rowvar=False)
    cov += np.eye(cov.shape[0]) * 1e-6            # numerical stabiliser
    inv = np.linalg.pinv(cov)
    diff = test_std - centroid
    d2 = np.einsum("ij,jk,ik->i", diff, inv, diff)
    d2 = np.clip(d2, 0, None)
    return -np.sqrt(d2)


def m2_knn(refs_std, test_std, k):
    """Similarity = -mean Euclidean distance to the k nearest BUILD references."""
    # (n_test x n_ref) pairwise squared distances
    a2 = (test_std ** 2).sum(1)[:, None]
    b2 = (refs_std ** 2).sum(1)[None, :]
    d2 = np.clip(a2 + b2 - 2 * test_std @ refs_std.T, 0, None)
    d = np.sqrt(d2)
    kk = min(k, d.shape[1])
    part = np.partition(d, kk - 1, axis=1)[:, :kk]
    return -part.mean(axis=1)


def m0_shuffle(scores, seed=20260727):
    """Null baseline: shuffle the M1 similarity scores within TEST."""
    rng = np.random.default_rng(seed)
    out = scores.copy()
    rng.shuffle(out)
    return out


def k_for(n_refs_build):
    return int(round(np.sqrt(n_refs_build)))
