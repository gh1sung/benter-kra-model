# EXECUTION FILE — BB 지수 이번주(8/7~8/9) 실전 런, 현재 블로커: RDS 출마표 데이터 공백

> 이 문서는 메모리가 초기화된 새 채팅에서 이 작업을 이어받기 위한 실행 문서입니다.
> 위에서부터 순서대로 읽으면 지금까지 뭘 했고, 뭐가 막혀 있고, 다음에 정확히 뭘
> 해야 하는지 전부 파악됩니다. `day11_context_bb_index_live_run_entry_row_bug_and_fix.md`
> (같은 프로젝트 파일에 있음)가 이전 세션 요약이고, 이 문서는 그 이후 — 즉 v2 완료
> 후 발견된 새로운 심각한 문제부터 다룹니다.

---

## 지금 당장 막혀 있는 것 (TL;DR)

**RDS의 `race_info_of_horse` 테이블이 이번 주(8/7~8/9) 출마표 출전마의 약 35%를
아직 안 가지고 있습니다.** 이건 코드 버그가 아니라 순수 데이터 공백입니다.
2시간 간격으로 두 번 pull했는데 완전히 동일한 파일(MD5 해시 일치)이 나왔습니다 —
즉 이 시간 동안 RDS 쪽에서 전혀 채워지지 않았습니다.

**사용자(성지환)가 [data team lead]에게 직접 문의하기로 했고, 새로 진짜 업데이트된 CSV를
받으면 재실행을 요청할 예정**입니다. 이 문서를 읽는 세션의 역할은: 새 CSV가
오면 완전성 체크부터 먼저 하고, 통과하면 전체 파이프라인을 처음부터 다시 돌려서
v3 산출물(노트북/PDF/CSV)을 만드는 것입니다.

---

## 1. 배경 — 이 작업이 왜 시작됐나

레이싱조이(한국 경마 정보 서비스) 인턴 성지환이 BB 지수(0-100 마필 능력 점수
엔진)를 개발 완료 후, 상급자 [program supervisor]이 "내일(8/6) 출마표 뜨면 실전처럼 돌려보고
결과를 저장해서 나중에 실제 경주 결과와 비교해보자"고 요청. 이번 세션들은 그
요청을 실제로 실행하는 과정.

**전체 시스템 배경** (자세한 건 project knowledge의 다른 day-context 문서들 참고):
- BB 지수: Bolton & Chapman(1986) 컨디셔널 로짓 모델 + Benter 방식 보정. 10개
  고정 변수(`AVESPRAT`, `LSPEDRAT`, `LIFE_PCT_WIN`, `W_PER_RACE`, `JOCK_PCT_WIN`,
  `JOCK_NUM_WIN`, `WEIGHT`, `POSTPOS`, `NEWDIST`, `CAREER_STARTS`), 계수는
  `rating_model_params_10var.json`에 고정(frozen)되어 있음.
- Unlucky/Overlooked 태그: 별도 시스템, 이번 주 작업과 무관 (전문가 예상 데이터
  업데이트 완료되는 금요일 이후 별도 진행 예정).
- RDS 접근: DBeaver, read-only, [data team lead]가 스키마 소유자.

---

## 2. 이번 세션들에서 실제로 벌어진 일 (시간 순)

### 2-1. v1 실행 — 성공한 것처럼 보였으나 버그 있었음

첫 실행에서 35경주 중 31경주 채점, 40/241마리 제외. 사용자가 두 가지 의문 제기:
(a) 왜 이렇게 많이 drop됐나, (b) fund_p가 경주 내 100% 합이 되도록 계산되는데
drop된 말들은 실제 승리확률이 0이 아닌데 왜 무시되나.

**(b)에 대한 조사 중 (a)의 진짜 원인을 발견**: `carry_forward_entry_features()`가
`shift(1)` 구조를 잘못 이해하고 있었음 — 아직 안 뛴 출전마 행에 값을 복사할 때,
그 말의 **가장 최근 실제 경주 자체가 누락된** 과거 값을 복사하고 있었음. 측정
결과: 채점된 말의 **90%의 BB 지수가 바뀌었고**, **31경주 중 12경주(39%)에서 1위
픽이 바뀜**. 심각한 버그였고 v1으로 만든 모든 산출물(zip, 노트북, PDF, 이메일
초안)은 폐기됨.

### 2-2. v2 — 올바른 fix로 재작성 및 전체 재실행

`entry_features_fix.py`(신규 파일)에 `recompute_entry_features()`를 만들어서,
값을 복사하는 대신 출마표 행 자체를 시퀀스에 포함시켜 `shift(1)`/`cumcount()`를
재계산하도록 고침. 검증: 실제 과거 경주 행 0개 변경(byte-identical), 특정 말의
수동 계산과 정확히 일치, 35/35 경주 전부 채점 가능해짐(v1은 31/35).

**데뷔마(과거 전적 0)는 이 모델로 원천적으로 채점 불가능** — 10개 변수가 전부
과거 경주 기록 기반이라 계산할 입력값 자체가 없음. `status="정보부족"`,
`ability_score`/`fund_p`=NaN으로 명시적으로 처리(0이나 평균값으로 채우지 않음).
이 말이 낀 경주는 fund_p가 과대평가된다는 경고를 표 위에 자동 표시.

**Unlucky/Overlooked 태그 안전성 확인**: `market_tags.py`가 fund_p의 절대값이
아니라 `fund_p.rank(pct=True)`(경주 내 percentile rank)만 쓰기 때문에, 정보부족
말로 인한 fund_p 왜곡(전체가 비례해서 커지는 것)은 rank 결과에 영향을 주지 않음 —
수학적으로 증명함(`np.allclose` 확인). 태그 로직은 이 문제와 무관.

노트북 표 포맷: Section 5(경주별 전체 출전마 표, 정보부족 포함) + Section 5.5
(Top-5 요약표), 정보부족 말이 있는 경주마다 "⚠️ fund_p 과대평가 플래그" 표시.

**v2 산출물** (이 시점까지는 최신이라고 믿었음 — 아래 2-3에서 뒤집힘):
- `bb_index_2026_08_08_09_v2_실행완료.ipynb`
- `BB지수_주간결과_20260807_09_v2.pdf`
- `bugfix_v2_entry_row_features.zip` (build_bc_features.py, build_tier1_features.py,
  entry_features_fix.py, BUGFIX_v2_entry_row_features.md)
- `bb_index_full_v2.csv`, `bb_index_top5_v2.csv`, `bb_index_race_coverage_v2.csv`
- `day11_context_bb_index_live_run_entry_row_bug_and_fix.md` (이전 세션 요약)

### 2-3. 훨씬 더 심각한 문제 발견 — RDS 자체의 출전마 데이터 공백

사용자가 KRA 공식 출마표 PDF(`s_run_hr_260808_07.pdf`, 서울 7경주)를 캡쳐해서
보내줌 — 실제로는 **마번 1~10, 10마리**가 출전. 그런데 우리 파이프라인 결과에는
**마번 2, 3, 7, 8 — 4마리만** 있었음.

**원인 조사 결과 (raw_pull_latest.csv 직접 확인):**
```
race_id 202608080107의 raw pull 원본 데이터:
- horse_count 컬럼(race_info 테이블 자체 값) = 10  <- RDS는 10마리인 걸 앎
- 실제 race_info_of_horse에 존재하는 행 = 4개뿐 (back_num 2,3,7,8)
```

**즉 `race_info` 테이블은 이 경주가 10마리라는 걸 알고 있는데,
`race_info_of_horse`(개별 출전마 상세)에는 6마리가 아직 안 들어가 있음.**

**전체 이번 주 스캔 결과 — 이건 이 경주 하나만의 문제가 아니라 이번 주 전체
경주 100%에 해당하는 문제:**

| 날짜 | horse_count 합 (RDS가 안다고 주장하는 총원) | 실제 존재하는 행 | 공백 |
|---|---:|---:|---:|
| 2026-08-07 | 88 | 52 | 36 |
| 2026-08-08 | 107 | 70 | 37 |
| 2026-08-09 | 177 | 119 | 58 |
| **합계** | **372** | **241** | **131 (약 35%)** |

**35경주 전부 공백 있음. 공백 0인 경주 = 0개.**

### 2-4. 재확인 시도 — 시간 경과로 채워지는지 확인

같은 SQL을 2시간 간격(15:26 → 16:46)으로 두 번 pull → **완전히 동일한 파일**
(MD5 해시 일치, `62a0120fa885433a8edf1cc02ae75033`). 즉 이 시간 동안 RDS
`race_info_of_horse`에 전혀 새로운 행이 추가되지 않음. "조금만 기다리면
채워진다"는 가설은 최소 이 2시간 창에서는 틀렸음.

### 2-5. 사용자의 결정

- [data team lead]에게 직접 문의해서 왜 이 시점에 데이터가 비어있는지, 언제 채워지는지
  확인하기로 함.
- 새로 실제로 업데이트된 CSV를 받으면, 이 문서를 읽는 새 세션에게 재실행을
  요청할 예정.
- **v2 산출물(노트북/PDF/CSV)은 [program supervisor]에게 아직 전달되지 않은 것으로 보임** —
  이 공백 문제가 발견된 게 이메일 초안까지 다 써놓은 다음이었음. [program supervisor]에게
  아직 안 보냈다면, 이 데이터 공백 문제가 해결되기 전까지는 보내면 안 됨
  (v2가 "버그는 고쳤지만 입력 데이터 자체가 35% 비어있는" 상태의 결과이기 때문).

---

## 3. 다음 세션이 정확히 해야 할 일

### 새 CSV가 도착하면, 순서대로:

**Step 1 — 완전성 체크부터 (제일 중요, 절대 건너뛰지 말 것)**

지난 세션에서 이 체크를 처음에 안 해서 v1→v2 버그 수정 후에도 한참 지나서야
훨씬 큰 문제를 발견했음. 이번엔 반드시 맨 처음에:

```python
import pandas as pd
raw = pd.read_csv("새CSV경로", dtype={"race_id": str}, low_memory=False)
raw["race_date"] = pd.to_datetime(raw["race_date"])

# 타겟 날짜는 그 시점 기준 실제 출마표 날짜로 교체할 것
week = raw[raw["race_date"].dt.strftime("%Y-%m-%d").isin(["YYYY-MM-DD", ...])].copy()

summary = week.groupby(["race_id","race_date"])["horse_count"].first().reset_index()
actual = week.groupby("race_id").size().rename("actual_rows")
summary = summary.merge(actual, on="race_id")
summary["gap"] = summary["horse_count"] - summary["actual_rows"]

print(summary.groupby(summary["race_date"].dt.date)[["horse_count","actual_rows","gap"]].sum())
print("공백 있는 경주:", (summary["gap"]>0).sum(), "/", len(summary))
```

**gap이 0이 아닌 경주가 여전히 있다면**, 그 경주들은 부분 데이터로 스코어링하게
되므로 사용자에게 먼저 보고하고 어떻게 할지 확인할 것 (예: 부분 채점 후 명시적
플래그를 달지, 아니면 그 경주는 아예 제외할지). **절대 조용히 넘어가지 말 것.**

**Step 2 — SQL (변경 없음, 그대로 사용)**

```sql
SELECT
    ri.race_id, ri.race_date, ri.distance, ri.race_class, ri.track_condition,
    ri.track_moisture, ri.region, ri.horse_count,
    ri.prize1, ri.prize2, ri.prize3, ri.prize4, ri.prize5,
    rio.horse_id, rio.jockey_id, rio.trainer_id, rio.impost, rio.back_num,
    rio.horse_age, rio.horse_weight, rio.kit, rio.req_inc_impost, rio.horse_rating,
    h.birth_date, h.total_race, h.rating AS horse_base_rating,
    rrh.rank, rrh.goal_time
FROM kra_data.race_info ri
JOIN kra_data.race_info_of_horse rio ON rio.race_id = ri.race_id
JOIN kra_data.horse h ON h.kra_id = rio.horse_id
LEFT JOIN kra_data.race_result_of_horse rrh
    ON rrh.race_id = ri.race_id AND rrh.horse_id = rio.horse_id
WHERE ri.region IN ('서울', '부산')
ORDER BY ri.race_id, rio.horse_id;
```

**Step 3 — 파이프라인 실행 (v2 코드 그대로 재사용, 로직 변경 없음)**

v2에서 검증 완료된 코드를 그대로 씁니다. 아래 파일들이 project knowledge에
이미 올라가 있음 (`bugfix_v2_entry_row_features.zip` 안에 있거나 개별 파일로):
- `build_bc_features.py` (원본, 변경 없음)
- `build_tier1_features.py` (entry_features_fix.py를 import하도록 이미 수정됨)
- `entry_features_fix.py` (v2의 핵심 수정 로직 — 검증 완료, 재사용만 하면 됨)
- `horse_rating_10var_v2.py`, `fit_engine.py`, `rating_model_params_10var.json`
  (전부 변경 없음)

실행 순서:
1. raw CSV 로드 → `is_start`/`is_win` 플래그
2. `build_bc_features.py`: `build_race_speed_z` → `build_time_windowed_features`
   → `build_last4_features` → `WEIGHT`/`POSTPOS` 설정
3. `build_tier1_features.py`: `build_trainer_features` → `build_career_starts_and_recency`
4. `entry_features_fix.py`의 `recompute_entry_features()` 호출 (v2의 핵심 수정)
5. `horse_rating_10var_v2.py`: `compute_V` → `block_contributions` →
   `build_reference_snapshot` → 이번 주 각 경주에 대해 `score_race()`
6. 정보부족 말(10개 변수 중 하나라도 NaN)은 status="정보부족"으로 명시, NaN 유지
   (0이나 평균값 채우지 말 것 — 이건 절대 규칙)
7. 경주당 정보부족 말이 있으면 fund_p 과대평가 플래그 자동 표시

**Step 4 — 산출물 재생성**

- 노트북: `bb_index_2026_08_08_09_v2.ipynb`의 구조를 그대로 복사해서 새로 실행
  (Section 5 전체 출전마 표 + Section 5.5 Top-5 표, 둘 다 fund_p 플래그 포함).
  파일명은 v3로 버전 표시.
- PDF: `build_pdf_v2.py`의 구조를 그대로 재사용 (NanumGothic 폰트 —
  `/usr/share/fonts`의 시스템 Noto CJK는 reportlab이 못 읽으므로 반드시
  Google Fonts 저장소에서 실제 TTF를 받아써야 함, 아래 4번 참고).
  파일명 v3로.
- **PDF 표지에 이번 주가 겪은 데이터 공백 이슈를 한 줄 언급할지 사용자에게 확인**
  (이전엔 없었던 새로운 이슈이므로).

**Step 5 — 사용자에게 보고**

새 pull이 실제로 얼마나 개선됐는지 (이전 35%공백 대비) 반드시 먼저 요약해서
보여줄 것. 완전히 해결됐는지, 부분적으로만 개선됐는지 명확히.

---

## 4. 재사용 가능한 기술 세부사항 (놓치기 쉬운 것들)

### PDF 폰트
```bash
curl -sL -o fonts/NanumGothic-Regular.ttf \
  "https://raw.githubusercontent.com/google/fonts/main/ofl/nanumgothic/NanumGothic-Regular.ttf"
curl -sL -o fonts/NanumGothic-Bold.ttf \
  "https://raw.githubusercontent.com/google/fonts/main/ofl/nanumgothic/NanumGothic-Bold.ttf"
```
시스템에 이미 있는 `/usr/share/fonts/opentype/noto/NotoSansCJK-*.ttc`는
reportlab의 `TTFont`가 못 읽음 (`postscript outlines are not supported` 에러) —
CFF/OTF 윤곽선이라 그럼. 반드시 진짜 TrueType 파일을 새로 받을 것.

### 노트북 작성 시 흔한 실수 (이번 세션에서 반복적으로 발생)
멀티라인 f-string이나 print문 마지막에서 닫는 괄호를 빠뜨리는 syntax error가
여러 번 발생했음. 노트북 JSON을 조립할 때, 각 code cell을 실행 전에 반드시:
```python
import json
nb = json.load(open("notebook.ipynb"))
for i, c in enumerate(nb["cells"]):
    if c["cell_type"] == "code":
        try: compile("".join(c["source"]), f"cell{i}", "exec")
        except SyntaxError as e: print(f"cell {i}:", e)
```
이 체크를 실행 전에 항상 먼저 돌릴 것.

### 검증 없이 믿지 말 것 (이번 세션의 핵심 교훈)
- 코드가 에러 없이 돌았다고 결과가 맞다는 뜻이 아님 (v1이 정확히 이 케이스).
- pull된 데이터의 날짜/지역이 맞다고 완전하다는 뜻이 아님 (이번 공백 사태가
  정확히 이 케이스 — 날짜/지역 체크만 하고 필드 수는 안 봤음).
- 앞으로 모든 라이브 pull은 **완전성 체크(actual rows vs horse_count)를 반드시
  1순위로 먼저 수행**할 것.

### 절대 규칙 (반복 확인됨)
- shift(1) 기반 피처를 만지는 모든 수정은 "실제 과거 경주 행 0개 변경"을 데이터로
  직접 검증할 것.
- 데이터 없는 대상(데뷔마, 혹은 이번처럼 아예 pull에 없는 말)에게 0이나 평균값을
  채우지 말 것 — 항상 명시적 결측 처리 + 영향받는 다른 값에 플래그.
- percentile rank 기반 로직(market_tags.py 등)은 절대 스케일 왜곡에 강건함 —
  비슷한 "이 버그가 다른 시스템도 오염시켰나" 질문이 나오면 그 시스템이 절대값을
  쓰는지 rank를 쓰는지부터 확인.

---

## 5. project knowledge에 있는 관련 파일 (참고용)

- `day11_context_bb_index_live_run_entry_row_bug_and_fix.md` — v1→v2 버그 발견/수정
  전체 기록 (이 문서의 앞부분, 2-1/2-2 섹션의 소스)
- `bugfix_v2_entry_row_features.zip` — v2 수정 코드 3종 + 상세 버그 리포트
- `BB지수_주간결과_20260807_09_v2.pdf`, `bb_index_2026_08_08_09_v2_실행완료.ipynb` —
  v2 산출물 (RDS 공백 문제 발견 전이라 **불완전한 입력 데이터 기반** — 새 pull
  받기 전까지는 [program supervisor]에게 전달 보류 상태)
- `bb_index_full_v2.csv`, `bb_index_top5_v2.csv`, `bb_index_race_coverage_v2.csv`
