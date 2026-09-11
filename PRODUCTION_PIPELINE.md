# Production Pipeline — bb_rating → market_tags, end to end

Written for [data team lead] / [program supervisor]. This traces every step from a raw RDS pull to a finished Unlucky/Overlooked tag on a live race, in the exact order data flows through the code, based on what's actually in the delivered scripts (not a guess at what "should" exist).

**The most important thing to know up front: none of this has ever run as an automated daily job.** Every step below has so far been run manually, once at a time, inside interactive chat sessions. Turning it into something that runs unattended every morning before the first race is real new engineering work — this doc tells you exactly what pieces already exist to wire together, and exactly what's still missing.

---

## The two-tier shape of the pipeline

There are two genuinely different pipelines here, running on two different clocks:

1. **BUILD pipeline (periodic — daily is overkill).** Rebuilds the model's frozen parameters and the two tag reference pools from *settled, historical* race results. This has to look backward at races that already happened, so it can't run same-day. Cadence hasn't been decided (flagged open below) — my own read is monthly or quarterly is plenty, since these are population-level patterns, not something that goes stale in 24 hours, but that's a recommendation, not a decision anyone's made.
2. **SCORE pipeline (daily — must finish before the first race).** Takes the frozen artifacts from step 1 and scores *today's* unsettled card. This is the part that actually needs to run every racing day.

```
BUILD pipeline (periodic)                    SCORE pipeline (daily, before first race)
──────────────────────────                   ──────────────────────────────────────────
raw RDS pull (manual today)                  today's card + full horse histories (RDS)
        ↓                                              ↓
build_bc_features.py                         same feature-engineering code,
        ↓                                    run on today's field only
build_tier1_features.py                                ↓
        ↓                                    horse_rating.py: score_race()
horse_rating.py: fit_production()            (frozen params, no refit)
        ↓                                              ↓
rating_model_params_10var.json               fund_p per horse  ──────┐
   + rolling 36-month reference pop.                                 │
        ↓                                    expert_score pull (~3 days pre-race)
score history, join expert/odds/results                │             │
        ↓                                    live pre-race odds pull │
unlucky_reference_pool.csv                   (⚠ open question, see below)
overlooked_reference_pool.csv                           ↓            ↓
                    └──────────────────→  market_tags.py: tag_race(horses, fund_p)
                                                          ↓
                                          tags + tiers + comps, pushed to product surface
```

---

## Part 1 — BUILD pipeline (periodic, produces the frozen artifacts)

| # | Step | Script | Input | Output |
|---|---|---|---|---|
| 1 | Raw RDS pull | **manual today** — DBeaver, joins `race_info` + `race_info_of_horse` + `race_result_of_horse` + class-record tables | RDS `kra_data` | one wide CSV (369,139 rows as of the last pull) |
| 2 | Feature engineering, part 1 | `build_bc_features.py` | step 1's CSV | `bc_features_built.csv` — adds AVESPRAT, LSPEDRAT, LIFE_PCT_WIN, W_PER_RACE, JOCK_PCT_WIN, JOCK_NUM_WIN, NEWDIST (WEIGHT/POSTPOS pass through as-is) |
| 3 | Feature engineering, part 2 | `build_tier1_features.py` | `bc_features_built.csv` | `gate2_features_tier1.csv` — adds CAREER_STARTS (+ trainer features, not used in the locked spec) → merged, this is `gate2_features_built.csv` |
| 4 | Fit the frozen model | `horse_rating.py` → `fit_production()` + `save_params()` | `gate2_features_built.csv` | `rating_model_params_10var.json` (beta_raw, mu, sigma — this is what daily scoring loads, no refit needed day to day) |
| 4b | Rebuild the rolling reference population | `horse_rating.py` → `rolling_percentile_score()`'s reference set | `gate2_features_built.csv` | trailing-36-month reference population (currently **manual, no script owns this as a standalone step** — see gaps below) |
| 5 | Score fund_p for the whole population | `horse_rating.py` → `compute_V()` + `compute_fund_p()` | `gate2_features_built.csv` + params | `fund_p_scored.csv` |
| 6 | Pull expert picks | manual RDS pull from `expect_5horse`, aggregated 5/4/3/2/1 points per rank1–5 across ~57–77 qualifying experts (조's exclusion list already applied) — **no standalone reusable script found for this step, it's been done ad hoc** | RDS `expect_5horse` | `expert_score_seoul_busan.csv` |
| 7 | Pull settled win odds | `extract_win_odds.py` | data.go.kr public API (확정/settled odds only, **post-race**) | `win_odds_5yr.csv` |
| 8 | Join everything + compute implied place | (day-10 session's `02_build_unified.py`, or its successor) | steps 5+6+7 + `harville_engine.py` | `unified_dataset.csv` |
| 9 | Carve out the two tag pools | (day-10 session's `05_overlooked_tag.py` / the Unlucky equivalent) | `unified_dataset.csv` | `unlucky_reference_pool.csv`, `overlooked_reference_pool.csv` — **the two files market_tags.py actually reads** |
| 10 | (sanity check only) tier density recheck | `06_confidence_tiers.py` | the two pools above | `unlucky_density_by_odds.csv`, `overlooked_density_by_odds.csv` |

**Output of this whole pipeline = 3 things the daily pipeline depends on:** `rating_model_params_10var.json`, the rolling reference population, and the two `*_reference_pool.csv` files.

---

## Part 2 — SCORE pipeline (daily, must finish before the first race)

| # | Step | What runs | Depends on |
|---|---|---|---|
| 1 | Pull today's card + each runner's full prior history | scripted RDS query (**needs to be a real script with credentials, not a DBeaver GUI export** — this is new work) | RDS access |
| 2 | Run the same feature engineering on today's field | `build_bc_features.py` + `build_tier1_features.py` logic, applied to today's rows (CAREER_STARTS etc. need each horse's full history, not just today) | step 1 |
| 3 | Score today's field | `horse_rating.py` → `score_race()`, using the **frozen** `rating_model_params_10var.json` and the rolling reference population from Part 1 | step 2, Part 1 outputs |
| 4 | Pull today's expert scores | same aggregation as Part 1 step 6. Useful detail: expert picks are typically **published ~3 days before race day**, so this can usually be pulled well ahead of the race-day run, not last minute | RDS `expect_5horse` |
| 5 | Pull today's pre-race odds | ⚠️ **this is the one real open question, see below** | RDS live odds |
| 6 | Tag the race | `market_tags.py` → `tag_race(horses, fund_p)`, using the **static** pools from Part 1 (no rebuild needed here) | steps 3, 4, 5 |
| 7 | Push output somewhere customer-facing | not yet defined in any doc — probably the same surface 최's test server (`61.36.136.176:5050`) already uses for the `/horse-ability` 종합점수 page | — |

Step 3's `fund_p` (bb_rating's `win_expectancy` output) is the exact same number that would feed bb_rating's own daily product — so if bb_rating is already scoring races daily, **market_tags can just consume that existing output** rather than duplicating the scoring step.

---

## The real gaps — don't let anyone assume these are solved

1. **Live pre-race odds substitute — genuinely unresolved.** Every ratio in this project (Unlucky 0.913–0.950, Overlooked 0.779) was validated against **settled/final** odds (`extract_win_odds.py` pulls only 확정 post-race odds from the public API). A pipeline that must finish *before* the first race can't use final odds — they don't exist yet. RDS has pre-race snapshots (`odd_best_snapshots`, 5 timepoints: 25/15/10/6/2분전), so production would need to pick one (probably the closest available, 2분전) as a stand-in for `odds_final`. **This substitution has never been tested** — it's a real methodology decision, not a solved detail, and it could shift the tag thresholds (`EXPERT_HIGH_MIN=97` etc. were calibrated against final odds).
2. **Reference population refresh isn't a script yet.** `rolling_percentile_score()` needs a precomputed rolling 36-month population to be meaningful in production (falling back to within-race-only percentiles otherwise, which the code's own docstring says isn't fit for real display). Rebuilding this is currently manual and undocumented as a standalone step.
3. **Expert-score aggregation has no standalone script.** The formula is documented (5/4/3/2/1 points per rank1–5, summed across qualifying experts, 조's exclusion list applied) but I couldn't find a reusable `.py` file that implements it — it's been done inline, session to session.
4. **RDS access for unattended runs.** Today's constraint (per project notes) is that persistent pulls go through DBeaver's GUI, manually. A scheduled job needs real scripted DB credentials — that's 조's call, since he owns RDS access.
5. **No refit/rebuild cadence has been decided.** Nobody's picked how often Part 1 needs to re-run. My own guess (monthly/quarterly) is a suggestion, not a decision.
6. **No orchestration exists.** There's no cron job, no Airflow DAG, no scheduler of any kind anywhere in this project. Someone needs to write the script that calls all of the above in order and handles failures — that script doesn't exist yet.

---

## Where this needs to actually run

Not on a laptop, and not on my Mac session. It needs:

- **Real RDS credentials with scripted (non-GUI) access** — 조's infrastructure to set up.
- **A machine that can run Python on a schedule** — a cron job on an internal server, or wherever the existing `61.36.136.176:5050` test server already lives (that server is already serving a `/horse-ability` page, so it may be the natural home for this rather than standing up something new).
- **Two realistic run windows**, not one: expert scores can be prepped days ahead, but the odds-dependent final tagging step (once gap #1 above is resolved) has to run close to each race's post time.
