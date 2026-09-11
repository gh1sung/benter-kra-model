"""
build_exotic_outcomes.py

Piece A, deliverable 3. Reads the raw KRA finish-rank pull (the same source
build_bc_features.py uses) and emits, per race, the realized top-2 pair and
top-3 triple (by back_num / gate number) plus the full starter list needed
to build the matching win-prob choice set on the odds side.

Only needs 6 columns: race_id, race_date, region, race_no, back_num, rank.
Works whether you point it at the full raw pull or the slim 6-column
DBeaver re-export described in the Piece A spec (§2, Input 2) -- extra
columns are simply ignored.

Rank-code handling (from the B&C build rules, unchanged here):
    1, 2, 3, ...  -> real finish position, usable for top-2/top-3 outcomes
    91 (DQ), 92 (pulled up) -> the horse STARTED (counts toward the field /
        choice set) but has no valid finish position -- cannot be part of a
        realized top-2/top-3 outcome.
    93, 95, null  -> never started (scratched) -- excluded entirely, does
        not count toward the field either.

Because a DQ'd/pulled-up horse has no numeric rank, a race is only usable
for a given exotic bet if a horse with rank == 1 (and == 2, and == 3 for
trio-scoped output) actually exists. Races missing one of those are simply
skipped for that outcome type; counts are logged so nothing silently
disappears.
"""
import argparse
import sys

import pandas as pd

DEFAULT_IN_PATH = (
    "/mnt/user-data/uploads/"
    "race_info_race_info_of_horse_race_result_of_horse_record_by_clas_202607200918.csv"
)
DEFAULT_OUT_PATH = "/mnt/user-data/outputs/exotic_outcomes.csv"

NON_START_RANKS = {93, 95}
NO_FINISH_POSITION_RANKS = {91, 92}
BASE_REQUIRED_COLS = ["race_id", "race_date", "region", "back_num", "rank"]


def load_raw(path):
    df = pd.read_csv(path, dtype={"race_id": str}, low_memory=False)
    missing = set(BASE_REQUIRED_COLS) - set(df.columns)
    if missing:
        raise ValueError(
            f"Input file is missing required columns {sorted(missing)}. "
            f"Need at least: {BASE_REQUIRED_COLS} (+ race_no, or a race_id "
            f"that encodes it in the last 2 digits)"
        )
    if "race_no" in df.columns:
        df["race_no"] = df["race_no"].astype(int)
    else:
        # This raw pull's race_id encodes (date, track_code, race_no) as
        # YYYYMMDD + 2-digit track code + 2-digit race number (e.g.
        # 200801050101 = 2008-01-05, track 01, race 01). Verified against
        # the file's own `region` column: track code 01<->서울, 03<->부산,
        # 1:1 for every race_id in this pull -- no ambiguity.
        df["race_no"] = df["race_id"].str[-2:].astype(int)

    df = df[BASE_REQUIRED_COLS + ["race_no"]].copy()
    df["race_date"] = pd.to_datetime(df["race_date"])
    return df


def restrict_to_seoul_busan(df):
    """Standing project rule: Jeju always dropped. RDS-side region values
    are already '서울' / '부산' (not '부산경남' -- that's the odds-side
    label; the mapping happens later, in validate_piece_a.py's join)."""
    before = df["race_id"].nunique()
    df = df[df["region"].isin(["서울", "부산"])].copy()
    after = df["race_id"].nunique()
    print(f"[region filter] races before={before}, after={after} (Jeju dropped)")
    return df


def build_outcomes(df):
    df = df.copy()
    df["is_start"] = (~df["rank"].isin(NON_START_RANKS)) & df["rank"].notna()
    df["has_finish_position"] = df["is_start"] & (~df["rank"].isin(NO_FINISH_POSITION_RANKS))

    rows = []
    n_races = 0
    n_missing_top2 = 0
    n_missing_top3 = 0
    n_dq_or_pulled_up_races = 0

    group_cols = ["race_id", "race_date", "region", "race_no"]
    for keys, grp in df.groupby(group_cols, sort=False):
        n_races += 1
        starters = grp.loc[grp["is_start"], "back_num"].tolist()
        if grp["rank"].isin(NO_FINISH_POSITION_RANKS).any():
            n_dq_or_pulled_up_races += 1

        finishers = grp.loc[grp["has_finish_position"]]
        rank_to_horse = dict(zip(finishers["rank"], finishers["back_num"]))

        top2 = None
        if 1 in rank_to_horse and 2 in rank_to_horse:
            top2 = tuple(sorted((rank_to_horse[1], rank_to_horse[2])))
        else:
            n_missing_top2 += 1

        top3 = None
        if 1 in rank_to_horse and 2 in rank_to_horse and 3 in rank_to_horse:
            top3 = tuple(sorted((rank_to_horse[1], rank_to_horse[2], rank_to_horse[3])))
        else:
            n_missing_top3 += 1

        race_id, race_date, region, race_no = keys
        rows.append({
            "race_id": race_id,
            "race_date": race_date,
            "region": region,
            "race_no": race_no,
            "n_starters": len(starters),
            "starters": "|".join(str(s) for s in sorted(starters)),
            "winner": rank_to_horse.get(1),
            "second": rank_to_horse.get(2),
            "third": rank_to_horse.get(3),
            "top2_pair": "|".join(str(x) for x in top2) if top2 else None,
            "top3_triple": "|".join(str(x) for x in top3) if top3 else None,
        })

    out = pd.DataFrame(rows)
    print(f"[outcomes] races total={n_races}")
    print(f"[outcomes] races with a DQ(91)/pulled-up(92) starter={n_dq_or_pulled_up_races}")
    print(f"[outcomes] races missing a usable top-2 (no valid rank1/rank2)={n_missing_top2}")
    print(f"[outcomes] races missing a usable top-3 (no valid rank1/2/3)={n_missing_top3}")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in-path", default=DEFAULT_IN_PATH,
                     help="Raw finish-rank CSV (full pull or slim 6-col re-export)")
    ap.add_argument("--out-path", default=DEFAULT_OUT_PATH)
    args = ap.parse_args()

    try:
        df = load_raw(args.in_path)
    except FileNotFoundError:
        print(f"ERROR: input file not found at {args.in_path}", file=sys.stderr)
        print(
            "Piece A Input 2 (finish rank data) isn't present in this session. "
            "Either upload the raw pull to /mnt/user-data/uploads/, or re-export "
            "the slim (race_id, race_date, region, race_no, back_num, rank) table "
            "from DBeaver per the spec, §2.",
            file=sys.stderr,
        )
        sys.exit(1)

    df = restrict_to_seoul_busan(df)
    out = build_outcomes(df)
    out.to_csv(args.out_path, index=False)
    print(f"[done] wrote {len(out)} races to {args.out_path}")


if __name__ == "__main__":
    main()
