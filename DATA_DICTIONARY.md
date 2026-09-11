# Data dictionary (schemas only — no data included)

The raw KRA (Korea Racing Authority) race/horse/odds data used to build and test this
project's models is **not included in this repo** — it comes from a licensed data source
and can't be redistributed. What follows is the schema (columns + row counts) of each raw
or per-record dataset that the code in this repo was run against, so the pipeline is
reproducible against your own equivalent data pull. Aggregated results, model
coefficients, and calibration tables (the actual outputs) **are** included in the repo.

| File (not included) | Rows | Columns |
|---|---|---|
| `win_odds_5yr.csv` / `raw_win_odds.csv` | 127,202 | date, track, race_no, gate_no, horse_id, odds |
| `exotic_outcomes.csv` / `raw_exotic_outcomes.csv` | 33,110 | race_id, race_date, region, race_no, n_starters, starters, winner, second, third, top2_pair, top3_triple |
| `expert_score_seoul_busan.csv` / `raw_expert_score.csv` | 68,932 | race_id, horse_num, region, race_date, expert_score, n_picks, is_unranked |
| `unified_dataset.csv` / `04_unified_dataset_demo.csv` | 57,753 | race_id, race_date, region, horse_num, fund_p, expert_score, n_picks, is_unranked, odds_final, won, placed, n_starters, implied_win, implied_place, place_rule_top |
| `drift_table.csv` | 20,003 | race_id, race_date, region, horse_num, n_starters, top, odds_25, odds_2, odds_final, p_25, p_2, MONEY_IN, MONEY_IN_RAW, rank_25, q_final, implied_win, implied_place, won, placed |
| `02_outcomes_with_placed.csv` | 364,716 | race_id, horse_num, n_starters, placed, race_date, region |
| `01_odds_with_implied_win.csv` | 92,863 | date, track, race_no, horse_num, horse_id, odds, track_code, race_id, implied_win |
| `03_implied_place.csv` | 92,667 | race_id, horse_num, implied_place |
| `raw_fund_p_from_bb_rating.csv` | 57,753 | race_id, horse_num, fund_p |
| `unlucky_reference_pool.csv` | 425–478 (two versions) | race_id, race_date, region, horse_num, fund_p/log_odds/expert features, odds_final, won, placed, n_starters, implied_win/place, expert_tercile, fund_p_race_rank(_z) |
| `overlooked_reference_pool.csv` | 534–1,033 (two versions) | same shape as unlucky_reference_pool.csv |
| `05_unlucky_reference_pool_demo.csv` | 425 | race_id, race_date, region, horse_num, odds_final, log_odds, expert_score, fund_p_race_rank, placed |
| `05_overlooked_reference_pool_demo.csv` | 534 | (same as above) |
| `surge_horses_T5.csv` | 43 | race_id, horse_num, region, n_starters, rank_25, odds_25, final_odds, implied_placed_prob, placed |
| `bb_index_full_v3.csv` | 372 | race_id, race_date, region, race_class, distance, horse_num, horse_id, ability_score, fund_p, status, missing_vars |
| `bb_index_top5_v3.csv` | 173 | race_id, race_date, region, race_class, distance, top5_rank, horse_num, horse_id, ability_score, fund_p, n_unratable_in_race |
| `bb_index_race_coverage_v3.csv` | 35 | race_id, race_date, region, race_class, distance, n_total, n_ratable, n_unratable |
| `demo_output_3_races.txt` | — | plain-text sample of live per-race model output (real horse IDs) |

## Also not included (separate from data)
- Two published academic papers used as methodology references (Bolton & Chapman 1986;
  Benter 1994) — not redistributed for copyright reasons.
- An internal data-request/schema document and one internal weekly-results report — not
  included as they contain data-provider-specific operational detail.
- One internal meeting-transcript file — not included (unrelated personal/business content
  had no place in a public repo regardless of the technical work discussed alongside it).
- One piece of direct email correspondence with the data provider - not included; personal/
  business correspondence isn't appropriate for a public repo regardless of content.

## What *is* included
Every aggregated result, calibration table, ablation grid, model coefficient file, and the
full modeling/fitting/evaluation codebase — see the main `README.md`.
