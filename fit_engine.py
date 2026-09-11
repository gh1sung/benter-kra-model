"""
Gate 2 fitting engine -- extends fit_bc_checksum.py / run_bc_checksum_fast.py
with:
  (a) an arbitrary variable list (not hardcoded to the original 9 B&C vars),
      so candidate blocks can be added/removed for ablation testing.
  (b) ridge (L2) regularization: adds lambda * sum(beta_j^2) to the negative
      log-likelihood and 2*lambda*beta to the gradient.
Otherwise reuses the exact same explosion, standardization, MNL log-likelihood,
and BFGS optimizer already validated in fit_bc_checksum.py -- not rewritten.
"""
import numpy as np
import pandas as pd
from scipy.optimize import minimize


def build_estimation_sample(df, var_list, extra_filters=None):
    """Same estimation-sample logic as fit_bc_checksum.py (1600-2000m, 건/양,
    age>=3, real finish rank<90), generalized to drop-NA on an arbitrary
    var_list instead of the hardcoded 9. extra_filters: optional boolean mask
    to AND in (e.g. a chronological pool restriction)."""
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

    sample = df.loc[mask].dropna(subset=var_list).copy()
    field_size = sample.groupby("race_id")["race_id"].transform("size")
    sample = sample[field_size >= 2].copy()
    return sample


def explode(sample, max_depth, var_list):
    """Chapman-Staelin rank-order explosion, generalized to an arbitrary
    var_list. Identical algorithm to fit_bc_checksum.explode()."""
    records = []
    choice_set_id = 0
    for race_id, grp in sample.groupby("race_id", sort=False):
        grp = grp.sort_values("rank")
        horses = grp.to_dict("records")
        n = len(horses)
        depth = min(max_depth, n - 1)
        for k in range(depth):
            candidates = horses[k:]
            if len(candidates) < 2:
                break
            choice_set_id += 1
            for pos, h in enumerate(candidates):
                rec = {col: h[col] for col in var_list}
                rec["choice_set_id"] = choice_set_id
                rec["race_id"] = race_id
                rec["chosen"] = 1 if pos == 0 else 0
                records.append(rec)
    return pd.DataFrame(records)


def fast_nll_grad_ridge(beta, X, starts, lam):
    """Vectorized (contiguous-group) MNL negative log-likelihood + gradient,
    same math as run_bc_checksum_fast.py, plus an L2 ridge penalty:
      NLL_ridge = NLL + lambda * sum(beta_j^2)
      grad_ridge = grad + 2 * lambda * beta
    Note: standardized features (mean 0, sd 1) make penalizing all betas
    uniformly (including what would be an intercept-like term) reasonable --
    there is no intercept here (conditional logit, cancels out in softmax)."""
    scores = X @ beta
    max_per_group = np.maximum.reduceat(scores, starts)
    shifted = scores - np.repeat(max_per_group, np.diff(np.r_[starts, len(scores)]))
    exp_scores = np.exp(shifted)
    sums = np.add.reduceat(exp_scores, starts)
    repeated_sums = np.repeat(sums, np.diff(np.r_[starts, len(scores)]))
    probs = exp_scores / repeated_sums

    ll = np.sum(shifted[starts] - np.log(sums))
    expected = np.add.reduceat(X * probs[:, None], starts, axis=0)
    grad = -np.sum(X[starts] - expected, axis=0)

    nll = -ll + lam * np.sum(beta ** 2)
    grad = grad + 2 * lam * beta
    return nll, grad


def fit_mnl_ridge(exploded, var_list, lam=0.0, mu=None, sigma=None):
    """Fit (or score, if mu/sigma passed in from a train fit) an MNL with
    ridge penalty lam. Returns beta, mu, sigma, convergence info, and
    (unpenalized) pseudo-R^2 computed against the null model -- the ridge
    penalty affects optimization/betas but pseudo-R^2 is always reported on
    the raw log-likelihood, so it stays comparable to Gate 1's numbers and
    across different lambda values."""
    exploded = exploded.reset_index(drop=True)
    gids = exploded["choice_set_id"].to_numpy()
    starts = np.r_[0, np.flatnonzero(gids[1:] != gids[:-1]) + 1]
    sizes = np.diff(np.r_[starts, len(exploded)])

    Xraw = exploded[var_list].to_numpy(dtype=float)
    if mu is None:
        mu = Xraw.mean(axis=0)
        sigma = Xraw.std(axis=0)
        sigma = np.where(sigma == 0, 1.0, sigma)
    X = (Xraw - mu) / sigma

    beta0 = np.zeros(len(var_list))
    res = minimize(fast_nll_grad_ridge, beta0, args=(X, starts, lam),
                    method="BFGS", jac=True, options={"maxiter": 500})

    # unpenalized log-likelihood for reporting (strip the ridge term back out)
    nll_penalized, _ = fast_nll_grad_ridge(res.x, X, starts, lam)
    ll_model = -(nll_penalized - lam * np.sum(res.x ** 2))
    ll_null = -np.log(sizes).sum()
    pseudo_r2 = 1 - ll_model / ll_null

    return {
        "beta": dict(zip(var_list, res.x)),
        "beta_raw": res.x,
        "mu": mu, "sigma": sigma,
        "converged": bool(res.success),
        "n_choice_sets": len(starts),
        "n_rows": len(exploded),
        "ll_model": ll_model,
        "ll_null": ll_null,
        "pseudo_r2": pseudo_r2,
    }


def score_holdout(exploded, var_list, beta_raw, mu, sigma, lam=0.0):
    """Apply an already-fit beta to a held-out exploded set. Returns
    (pseudo_r2, log_loss, n_choice_sets). log_loss = -sum(log p_chosen), the
    primary Gate 2 metric (lower is better)."""
    exploded = exploded.reset_index(drop=True)
    gids = exploded["choice_set_id"].to_numpy()
    starts = np.r_[0, np.flatnonzero(gids[1:] != gids[:-1]) + 1]
    sizes = np.diff(np.r_[starts, len(exploded)])

    Xraw = exploded[var_list].to_numpy(dtype=float)
    X = (Xraw - mu) / sigma

    nll, _ = fast_nll_grad_ridge(beta_raw, X, starts, 0.0)  # lam=0 for pure LL reporting
    ll_model = -nll
    ll_null = -np.log(sizes).sum()
    pseudo_r2 = 1 - ll_model / ll_null
    log_loss = nll  # = -sum(log p_chosen) since chosen row is first in each contiguous group
    return pseudo_r2, log_loss, len(starts)


def calibration_table(exploded, var_list, beta_raw, mu, sigma):
    """Benter (1994)-style calibration: bucket predicted win probabilities
    (only for choice sets AT FULL DEPTH, i.e. the actual win-probability
    stage, not intermediate explosion stages) and compare to actual frequency
    of winning within each bucket, with a z-score for the difference."""
    exploded = exploded.reset_index(drop=True)
    gids = exploded["choice_set_id"].to_numpy()
    starts = np.r_[0, np.flatnonzero(gids[1:] != gids[:-1]) + 1]
    Xraw = exploded[var_list].to_numpy(dtype=float)
    X = (Xraw - mu) / sigma
    scores = X @ beta_raw
    max_per_group = np.maximum.reduceat(scores, starts)
    shifted = scores - np.repeat(max_per_group, np.diff(np.r_[starts, len(scores)]))
    exp_scores = np.exp(shifted)
    sums = np.add.reduceat(exp_scores, starts)
    repeated_sums = np.repeat(sums, np.diff(np.r_[starts, len(scores)]))
    probs = exp_scores / repeated_sums

    chosen = exploded["chosen"].to_numpy()
    bins = [0, .010, .025, .05, .075, .10, .125, .15, .175, .20, .25, .30, .40, .50, 1.01]
    cal = pd.DataFrame({"p": probs, "won": chosen})
    cal["bucket"] = pd.cut(cal["p"], bins, right=False)
    g = cal.groupby("bucket", observed=True)
    tab = g.agg(n=("won", "size"), pred_mean=("p", "mean"), actual_freq=("won", "mean")).reset_index()
    tab["se"] = np.sqrt(tab["pred_mean"] * (1 - tab["pred_mean"]) / tab["n"])
    tab["z"] = (tab["actual_freq"] - tab["pred_mean"]) / tab["se"]
    return tab
