"""Fast, mathematically equivalent full-sample checksum runner.
Uses the same Chapman-Staelin explosion, feature standardization, MNL log-
likelihood, BFGS optimizer, and McFadden pseudo-R2 as fit_bc_checksum.py.
The only change is using contiguous-group reductions instead of np.add.at.
"""
import importlib.util
import numpy as np
import pandas as pd
from scipy.optimize import minimize

FEATURE_PATH = '/mnt/data/bc_features_track_record.csv'
OUT_PATH = '/mnt/data/bc_checksum_results_track_record.csv'
ORIGINAL_SCRIPT = '/mnt/data/fit_bc_checksum.py'

spec=importlib.util.spec_from_file_location('fitbc', ORIGINAL_SCRIPT)
fitbc=importlib.util.module_from_spec(spec)
spec.loader.exec_module(fitbc)
BC_VARS=fitbc.BC_VARS


def fast_nll_grad(beta, X, starts):
    scores = X @ beta
    max_per_group = np.maximum.reduceat(scores, starts)
    shifted = scores - np.repeat(max_per_group, np.diff(np.r_[starts, len(scores)]))
    exp_scores = np.exp(shifted)
    sums = np.add.reduceat(exp_scores, starts)
    repeated_sums = np.repeat(sums, np.diff(np.r_[starts, len(scores)]))
    probs = exp_scores / repeated_sums

    # chosen row is first in each contiguous choice set by construction
    ll = np.sum(shifted[starts] - np.log(sums))
    expected = np.add.reduceat(X * probs[:, None], starts, axis=0)
    grad = -np.sum(X[starts] - expected, axis=0)
    return -ll, grad


def fast_fit(exploded):
    exploded = exploded.reset_index(drop=True)
    gids = exploded['choice_set_id'].to_numpy()
    starts = np.r_[0, np.flatnonzero(gids[1:] != gids[:-1]) + 1]
    sizes = np.diff(np.r_[starts, len(exploded)])

    Xraw = exploded[BC_VARS].to_numpy(float)
    mu = Xraw.mean(axis=0)
    sigma = Xraw.std(axis=0)
    sigma[sigma == 0] = 1.0
    X = (Xraw - mu) / sigma

    res = minimize(fast_nll_grad, np.zeros(len(BC_VARS)), args=(X, starts),
                   method='BFGS', jac=True, options={'maxiter':500})
    ll_model = -res.fun
    ll_null = -np.log(sizes).sum()
    return {
        'beta': dict(zip(BC_VARS, res.x)),
        'pseudo_r2': 1 - ll_model / ll_null,
        'll_model': ll_model,
        'll_null': ll_null,
        'n_choice_sets': len(starts),
        'n_rows': len(exploded),
        'converged': bool(res.success),
        'message': str(res.message),
        'nit': int(res.nit),
    }


def main():
    sample = fitbc.build_estimation_sample(FEATURE_PATH)
    rows=[]
    published={1:0.091,2:0.064,3:0.055}
    print(f'Estimation sample: {len(sample):,} horse-rows, {sample.race_id.nunique():,} races', flush=True)
    for depth in (1,2,3):
        exploded=fitbc.explode(sample, depth)
        result=fast_fit(exploded)
        row={
            'explosion_depth':depth,
            'n_choice_sets_full':result['n_choice_sets'],
            'n_rows_exploded':result['n_rows'],
            'in_sample_pseudo_r2':result['pseudo_r2'],
            'bc_published_pseudo_r2':published[depth],
            'converged':result['converged'],
            'optimizer_message':result['message'],
            'iterations':result['nit'],
            'll_model':result['ll_model'],
            'll_null':result['ll_null'],
        }
        for v,b in result['beta'].items(): row[f'beta_{v}']=b
        rows.append(row)
        print(f"E={depth}: sets={result['n_choice_sets']:,}, R2={result['pseudo_r2']:.6f}, "
              f"converged={result['converged']}, iterations={result['nit']}", flush=True)
    out=pd.DataFrame(rows)
    out.to_csv(OUT_PATH,index=False)
    print(out[['explosion_depth','n_choice_sets_full','in_sample_pseudo_r2','bc_published_pseudo_r2','beta_AVESPRAT','beta_WEIGHT']].to_string(index=False), flush=True)
    print(f'Saved {OUT_PATH}',flush=True)

if __name__=='__main__': main()
