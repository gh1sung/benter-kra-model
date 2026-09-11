"""
Re-run of the original toy perfectly-predictive-feature unit test, extended to
cover the new fit_engine.py (arbitrary var list + ridge). Per Section 6 of the
runbook: confirm the ridge extension didn't break anything before trusting any
real numbers.

Synthetic setup: 400 races of 4-8 horses each. `dominant` feature perfectly
determines finish order (higher dominant = better rank); `noise1`/`noise2` are
pure random noise, uncorrelated with outcome; `constant` is literally constant
(zero variance) to check the sigma==0 guard doesn't blow up.

Checks:
  1. lambda=0: pseudo-R^2 lands near 1.0 (dominant perfectly predicts order).
  2. lambda=0: |beta_dominant| >> |beta_noise1|, |beta_noise2| (noise betas
     near 0).
  3. Ridge shrinkage sanity: as lambda increases, |beta_dominant| shrinks
     monotonically (standard ridge behavior) while in-sample pseudo-R^2
     degrades gracefully rather than exploding/NaN-ing.
  4. score_holdout on a fresh synthetic sample using the lambda=0 beta also
     lands near pseudo-R^2 ~= 1.0 (out-of-sample generalization for a
     perfectly-predictive feature).
"""
import numpy as np
import pandas as pd
from fit_engine import explode, fit_mnl_ridge, score_holdout

rng = np.random.default_rng(42)


def make_toy_sample(n_races=400, seed=0):
    rng = np.random.default_rng(seed)
    rows = []
    for race_id in range(n_races):
        n_horses = rng.integers(4, 9)
        dominant = rng.normal(size=n_horses)
        noise1 = rng.normal(size=n_horses)
        noise2 = rng.normal(size=n_horses)
        # rank 1 = best = highest dominant value
        order = np.argsort(-dominant)
        ranks = np.empty(n_horses, dtype=int)
        ranks[order] = np.arange(1, n_horses + 1)
        for i in range(n_horses):
            rows.append({
                "race_id": f"toy_{race_id}",
                "dominant": dominant[i],
                "noise1": noise1[i],
                "noise2": noise2[i],
                "constant": 1.0,
                "rank": ranks[i],
            })
    return pd.DataFrame(rows)


def main():
    var_list = ["dominant", "noise1", "noise2", "constant"]
    train = make_toy_sample(n_races=400, seed=0)
    test = make_toy_sample(n_races=150, seed=1)

    exploded_train = explode(train, max_depth=1, var_list=var_list)
    exploded_test = explode(test, max_depth=1, var_list=var_list)

    print("=== Check 1+2: lambda=0 fit ===")
    fit0 = fit_mnl_ridge(exploded_train, var_list, lam=0.0)
    print(f"converged={fit0['converged']}  pseudo_r2={fit0['pseudo_r2']:.4f}")
    for v in var_list:
        print(f"  beta_{v:<10} {fit0['beta'][v]:+.4f}")
    assert fit0["pseudo_r2"] > 0.85, "FAIL: pseudo-R2 should be near 1.0 for a perfectly-predictive feature"
    assert abs(fit0["beta"]["dominant"]) > 5 * abs(fit0["beta"]["noise1"]), "FAIL: dominant should dwarf noise1"
    assert abs(fit0["beta"]["dominant"]) > 5 * abs(fit0["beta"]["noise2"]), "FAIL: dominant should dwarf noise2"
    assert abs(fit0["beta"]["constant"]) < 1e-6, "FAIL: zero-variance feature should get ~0 beta (sigma guard)"
    print("PASS\n")

    print("=== Check 3: ridge shrinkage sanity ===")
    prev_abs_beta = None
    for lam in [0.0, 1.0, 10.0, 100.0, 1000.0]:
        fit = fit_mnl_ridge(exploded_train, var_list, lam=lam)
        b = abs(fit["beta"]["dominant"])
        print(f"  lambda={lam:<8} |beta_dominant|={b:.4f}  pseudo_r2={fit['pseudo_r2']:.4f}  converged={fit['converged']}")
        if prev_abs_beta is not None:
            assert b <= prev_abs_beta + 1e-6, f"FAIL: beta magnitude should shrink (or stay flat) as lambda grows, got {b} > {prev_abs_beta}"
        prev_abs_beta = b
    print("PASS\n")

    print("=== Check 4: holdout generalization (lambda=0 beta on fresh data) ===")
    r2_holdout, log_loss, n_sets = score_holdout(
        exploded_test, var_list, fit0["beta_raw"], fit0["mu"], fit0["sigma"]
    )
    print(f"holdout pseudo_r2={r2_holdout:.4f}  log_loss={log_loss:.2f}  n_choice_sets={n_sets}")
    assert r2_holdout > 0.85, "FAIL: holdout pseudo-R2 should also be near 1.0"
    print("PASS\n")

    print("ALL CHECKS PASSED")


if __name__ == "__main__":
    main()
