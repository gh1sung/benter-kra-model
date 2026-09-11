# class_mapping.md — resolved `race_class` encoding (§1.1)

**Source:** `race_class.csv` (= `race_info_202607291200.csv`, byte-identical duplicate).
33,145 races, Seoul + Busan, 2008–2026. Race-level attribute (one row per race).

## Distinct values + counts

| race_class | count | ladder | meaning |
|---|---|---|---|
| 국6 | 7,764 | 국산 (domestic) | group 6 — **bottom** |
| 국5 | 6,963 | 국산 | group 5 |
| 국4 | 4,403 | 국산 | group 4 |
| 국3 | 2,689 | 국산 | group 3 |
| 국2 | 970 | 국산 | group 2 |
| 국1 | 684 | 국산 | group 1 — top numbered |
| 국오 | 290 | 국산 | 오픈 (open) — above group 1 |
| 국미승 | 17 | 국산 | 미승리 (maiden / winless) |
| 국신마 | 3 | 국산 | 신마 (debut / newcomer) |
| 혼4 | 3,979 | 혼합 (mixed) | group 4 — bottom of mixed |
| 혼3 | 2,133 | 혼합 | group 3 |
| 혼2 | 1,742 | 혼합 | group 2 |
| 혼1 | 1,264 | 혼합 | group 1 |
| 혼오 | 216 | 혼합 | 오픈 (open) |
| 혼5 | 8 | 혼합 | group 5 (rare) |
| 외미승 | 8 | 외산 (foreign) | 미승리 (maiden) |
| 외3 | 5 | 외산 | group 3 |
| 외1 | 4 | 외산 | group 1 |
| 외2 | 3 | 외산 | group 2 |

Prefix = ladder: **국** = 국산 (domestic-bred), **외** = 외산 (foreign-bred), **혼** = 혼합 (mixed field, 국산+외산 run together). Suffix = group number (higher number = lower class), or 오 (오픈/open, top), 미승 (미승리/maiden), 신마 (debut).

## Resolved ordering (top → bottom), ladders kept separate

- **국산:** 국오 > 국1 > 국2 > 국3 > 국4 > 국5 > **국6** > {국미승, 국신마}
- **혼합:** 혼오 > 혼1 > 혼2 > 혼3 > **혼4** > 혼5
- **외산:** 외1 > 외2 > 외3 > 외미승  *(essentially defunct — see finding)*

미승리/신마 rows have the thinnest data of all (winless/debut horses) and sit at the true bottom of each ladder.

## ⚠ Structural finding — the ladder is 국산 / 혼합, NOT 국산 / 외산

The plan (§1.1) anticipated two live ladders, 국산 (6 groups) and 외산 (4 groups). The data says otherwise:

**외산 as a separate ladder is defunct.** All 20 외산 races are in **2008 only**; zero after. The second live ladder in this dataset is **혼합 (mixed)**, present every year (~450–650 races/yr). So the real instruction "keep the two ladders separate, never merge on group number" should read **국산 vs 혼합**, not 국산 vs 외산. This matters for §3's C-variant class_mean buckets: bucket on `(region, ladder=국산|혼합, group)`, and treat 외산 as a tiny 2008-only edge case.

## Low-class cutlines used (for the race-level audit)

| cut | 국산 | 혼합 | 외산 |
|---|---|---|---|
| bottom-1 | 국6, 국미승, 국신마 | 혼4, 혼5 | 외3, 외미승 |
| **bottom-2 (primary)** | 국6, 국5, 국미승, 국신마 | 혼3, 혼4, 혼5 | 외2, 외3, 외미승 |
| bottom-3 | 국6, 국5, 국4, 국미승, 국신마 | 혼2, 혼3, 혼4, 혼5 | 외1, 외2, 외3, 외미승 |

Ordering cross-checked against group-number monotonicity within each ladder. Confirming that bottom groups also have thinner data / weaker horses (§1.1 fallback check) **requires the horse-level feature table**, which is not yet available (see run notes).
