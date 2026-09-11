# Benter-style handicapping model — Korean horse racing (KRA)

A research project applying William Benter's (1994) horse-race handicapping approach —
built on Bolton & Chapman's (1986) conditional/multinomial logit model — to Korea Racing
Authority (KRA) data, to test whether a fundamentals-based factor model can find
predictive signal beyond what's already priced into the public odds (i.e., whether ΔR²
against a pure-market baseline is positive).

The core idea, in one line: build a fundamentals model, blend its predictions with the
market's own (the odds) in log-odds space, and only bet where the blended probability
still beats the market price. The research question isn't "can I build a model" — it's
"does my model know anything the crowd doesn't."

## What's in this repo

- **Modeling code** — conditional logit / multinomial fitting engines (`clogit.py`,
  `clogit2.py`, `fit_engine.py`, `harville_engine.py`), feature construction
  (`build_bc_features.py`, `build_tier1_features.py`, `build_dist_residual.py`), ridge
  regularization + lambda selection, walk-forward validation, ablation testing.
- **Diagnostic / signal-hunting code** — market-drift analysis, "lucky/unlucky/overlooked
  horse" tagging based on gaps between expert consensus and market odds, a SURGE detector,
  and calibration checking throughout.
- **Working logs** (`day1_...md` through `day13_...md`) — a real day-by-day research diary:
  hypotheses, bugs found and fixed, null results, and pivots. Kept because the negative and
  null results are as informative as the positive ones.
- **Stage reports** (`Gate2_Report.md`, `PieceA_Report.md`, `PieceB_Report.md`,
  `Step0_Report.md`, `Rating_Engine_Report.md`, `Lucky_Engine_Report.md`,
  `DRIFT_Tag_Report.md`, etc.) — formal write-ups per milestone: methodology, results,
  verdict.
- **Result artifacts** — calibration tables, ablation grids, lambda-selection grids, fitted
  model coefficients (as JSON), backtest-by-year tables. These are aggregated outputs, not
  raw data.
- **Notebooks** — pipeline walkthroughs (cell outputs stripped; see note below).

## What's *not* in this repo

- **Raw KRA race/horse/odds data.** It comes from a licensed data source and can't be
  redistributed. `DATA_DICTIONARY.md` documents the schema (columns, row counts) of every
  raw/per-record file the code was actually run against, so the pipeline is reproducible
  against an equivalent data source.
- **Two published academic papers** used as methodology references (Bolton & Chapman 1986,
  Benter 1994) — omitted for copyright reasons; both are findable via a quick search if
  you want the originals.
- A couple of internal, data-provider-specific documents (a schema/data-request doc, one
  internal results report) and one internal meeting-transcript file — omitted as
  operational/confidential detail with no bearing on the methodology.
- A live API key and a database hostname that appeared in the original working notes have
  been redacted from the docs that are included.

## Notebooks

Cell outputs were stripped before publishing (some had been run against real data and
would have re-leaked exactly what's excluded above). The code itself is intact — re-run
against your own data source to regenerate outputs.

## Status

This was an active, iterative research process — most of the individual signal hypotheses
tested (drift timing, lucky/unlucky horse patterns, various derived tags) came back null
or too weak to trade on, which is itself the honest finding: Korean KRA odds appear to be
close to informationally efficient. See the day-logs and stage reports for the full
reasoning trail rather than just the headline result.
