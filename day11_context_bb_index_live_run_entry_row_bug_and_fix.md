# Day 11 Context — BB 지수 첫 실전(출마표) 라이브 런, Entry-Row 버그 발견 및 수정

> Continuation of prior day-context docs (day1~day10). 이 세션은: BB 지수를 실제
> 이번주(2026-08-07~09) 서울·부산 출마표에 처음으로 라이브로 돌린 과정, 그 과정에서
> 발견된 심각한 buggy fix(v1)와 이를 대체한 올바른 수정(v2), 데뷔마 처리 문제,
> fund_p 왜곡과 Unlucky/Overlooked 태그에 대한 영향 여부까지 다룬다.

---

## 세션 개요

이전 세션(handoff 직후)에서 [program supervisor]이 "내일 출마표 뜨면 실전처럼 돌려보고, 결과
비교 준비를 해두라"고 요청 → 이번 세션에서 실제로 그 요청을 실행했다. 흐름:

1. BB 지수를 위한 SQL pull 확정 (schema 재확인 포함)
2. 출마표가 아직 안 들어온 첫 pull → 대기
3. 출마표 반영된 재풀 확보 → 검증 → 첫 실행 (v1) → **버그 있는 결과**
4. 사용자가 drop된 말 목록과 fund_p 합=1 로직에 의문 제기 → 재검증 → **v1의 carry-forward
   fix 자체가 틀렸음을 발견**
5. 올바른 fix(v2)로 재작성, 전체 재실행, 노트북/zip/PDF 전부 교체
6. 데뷔마(과거 전적 없는 말) 처리 문제 발견 — 별도 미해결 과제로 명시
7. 노트북 표 포맷 개선 (전체 출전마 표 + Top-5 표 분리, fund_p 과대평가 플래그 추가)
8. 이메일 초안 작성 (실행 결과 + 버그 수정 + 데뷔마 이슈 보고)
9. "혹시 Unlucky/Overlooked 태그도 fund_p 버그의 영향을 받나?" 질문 → 코드 직접
   확인 후 **태그 로직은 영향 없음**을 수학적으로 증명

---

## 1. 이번주 출마표 SQL — 최종 확정 버전

`race_info.prize1~5`가 실제 존재하는 컬럼임을 스키마 문서(day4 컨텍스트,
`rds_data_request_v2.pdf`)에서 재확인. 이전에 `race_result_of_horse`에
있다고 잘못 추측했던 것을 수정.

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

- 전체 히스토리 재풀(날짜 필터 없음) — 롤링 피처 계산에 전체 과거 데이터 필요.
- 실제 pull 결과: 61,142행, 13,494경주, 2008-01-06~2026-08-09.
- 검증: `rank IS NULL` + 날짜가 최근인 행 = 실제 출마표(아직 안 뛴 경주).
  2026-08-07(부산 8경주), 08-08(서울 10경주), 08-09(서울 10경주+부산 7경주) = 총 35경주,
  241마리. 서울/부산만, 제주 없음 — 정상.
- 오래된 `rank IS NULL` 행 127개(2012~2025년 산재)는 과거 취소/제외 경주 —
  출마표와 무관, 정상 노이즈.

---

## 2. v1 — 첫 실행, 겉보기엔 정상, 실제로는 버그

### v1이 한 일
`horse_rating_10var_v2.py` + `build_bc_features.py` + (기존 handoff zip의)
`build_tier1_features.py`를 그대로 사용해 35경주 채점 시도 → 31/35경주 성공, 40/241마리
제외("누락값으로 제외됨" 또는 "채점 가능한 말 2마리 미만").

### 사용자가 제기한 두 가지 의문 (핵심 트리거)
1. "왜 이렇게 많은 말이 drop됐나 — 로직에 결함이 있던 건 아닌가?"
2. **"fund_p 합이 항상 1이 되도록 짜여 있는데, drop된 말들도 실제로는 승리 확률이
   0이 아닌데 왜 0으로 취급되는 건가 — 로직이 깨진 거 아닌가?"**

### 실제로 발견된 것 (2가지 별개의 문제)

**(a) v1의 "handoff zip" carry-forward fix 자체가 틀렸음 (심각)**

`AVESPRAT`/`LSPEDRAT`/`NEWDIST`/`CAREER_STARTS`는 전부 `shift(1)` 기반으로 계산됨 —
즉 특정 행에 저장된 값은 "그 경주 **이전**까지의 이력"만 반영. v1의 carry-forward는
말의 가장 최근 **이미 계산된** 값을 그대로 복사해서 출마표 행에 붙였는데, 이는
그 말의 **가장 최근 실제 경주 자체를 누락**시키는 결과를 낳음.

실증 사례 (실제 데이터, horse_id 18877): 8/7 출전 예정, 마지막 실제 경주는 7/26
(race_speed_z=1.2901). v1의 LSPEDRAT = 0.7125 (7/10 경주값, 틀림). 올바른 값은
1.2901.

**측정된 피해**: 채점된 말의 **90%의 BB 지수가 변경**됨 (평균 9.6점, 최대 42점 차이),
**31개 경주 중 12개(39%)에서 1위 픽이 바뀜**.

**(b) fund_p 합=1 우려는 정당했음 — 그러나 원인은 다름**

`fund_p`는 `score_race()` 내부에서 `e = np.exp(V - V.max()); fund_p = e / e.sum()`로
계산됨 — **그 경주에 실제로 입력된 말들 사이에서만** softmax. drop된 말이 있으면
남은 말들끼리 100%를 나눠 가지므로, 채점된 말들의 fund_p가 실제보다 부풀려짐.
사용자의 우려가 정확했음.

- **BB 지수(0~100점)는 영향 없음** — 경주 내 분배가 아니라, 최근 36개월 전체
  모집단 대비 백분위이기 때문.
- fund_p만 영향받음. 11/35경주에 정보부족 말이 섞여 있었음 (부산 8/9 01R은
  6마리 중 2마리만 채점 가능해 최악의 경우).

---

## 3. v2 — 올바른 수정

### 핵심 아이디어
값을 복사(carry-forward)하는 대신, **출마표 행 자체를 원래 계산 로직의 시퀀스
안에 포함시켜서** 동일한 `shift(1)`/`rolling(4)`/`cumcount()`를 다시 돌림. 이렇게
하면 출마표 행의 위치에서 shift(1)이 자연스럽게 "그 말의 모든 실제 과거 경주
(가장 최근 것 포함)"를 정확히 되돌아봄.

새 파일: **`entry_features_fix.py`**
```python
def flag_upcoming(df):
    """rank IS NULL이면서 가장 최근 실제 결과 날짜보다 이후인 행만 '출마표
    entry'로 간주. 과거에 흩어진 취소/결측 행은 절대 포함시키지 않음 —
    그렇지 않으면 그 행들이 다른 말의 'last 4' 슬롯을 부당하게 차지해서
    과거 데이터의 롤링 피처를 조용히 왜곡시킬 수 있음."""
    last_real = df.loc[df["rank"].notna(), "race_date"].max()
    return df["rank"].isna() & (df["race_date"] > last_real)

def recompute_entry_features(df, verbose=True):
    # is_start==1 인 행 + is_upcoming인 행을 합쳐서 시퀀스 구성 후
    # 동일 로직(shift(1)/rolling(4)/cumcount)을 재실행.
    # 결과는 오직 is_upcoming 행에만 기록 — 실제 경주 행은 절대 건드리지 않음.
    ...
```

`build_tier1_features.py`도 이 함수를 import하도록 재작성 (원본 로직 자체는
안 건드림 — 여전히 `build_trainer_features()`/`build_career_starts_and_recency()`
는 그대로).

### 검증 (실제 데이터 기준, synthetic 아님)
1. **실제 과거 경주 행 0개 변경** (byte-identical, `np.isclose` 1e-9 허용오차)
2. **과거 결측/취소 행 0개 변경** (is_start==1과 is_upcoming이 절대 겹치지 않음 확인)
3. horse_id 18877 수동 계산과 정확히 일치 (AVESPRAT/LSPEDRAT/CAREER_STARTS 전부)
4. **부수 효과**: drop 40→23마리로 감소, 채점 가능 경주 31→**35/35 전부** 채점 가능
   (v1의 ffill이 진짜 첫 실전(1경기만 뛴 말)의 저장값 자체가 NaN인 경우를 못 살렸던
   것도 같이 해결됨)

### 남은 23마리 정보부족의 구성
- 19마리: 진짜 데뷔전 (과거 실제 출전 0회)
- 4마리: 과거 출전은 있으나 특정 변수 하나가 우연히 NaN (예: 얇은 speed bucket)

---

## 4. 데뷔마(정보부족) 처리 — 미해결, 별도 과제로 명시

### 왜 이 모델로는 원천적으로 불가능한가
모델의 10개 변수는 전부 "그 말의 과거 경주 기록"에서 파생됨. 데뷔마는 과거 경주가
0개이므로 계산할 **입력값 자체가 없음** — "구하기 어렵다"가 아니라 "존재하지 않는다."

### 무엇을 하지 않았나 (중요)
- fund_p/BB 지수를 **0으로 채우지 않음** — 승리 확률이 실제로 0이라는 거짓 주장이
  되기 때문.
- 임의의 평균값이나 추정치도 넣지 않음 — 모델이 실제로 학습한 적 없는 값을
  마치 예측인 것처럼 보이게 만드는 것이므로 0보다 나을 것 없는 조작.

### 실제로 한 것
- `status = "정보부족"`으로 명시, `ability_score`/`fund_p` = `NaN`.
- 해당 말이 포함된 경주는 표 위에 "⚠️ fund_p 과대평가 플래그" 자동 표시
  (PDF와 노트북 양쪽 다 동일하게 적용).

### 진짜 해결책 (향후 별도 프로젝트, 이번 스코프 아님)
1. 혈통(sire/dam)·조교사 데뷔마 승률 등 데뷔 전에도 존재하는 변수로 **별도 모델** 구축
2. 라이브 배당 데이터 연동 후, "unratable horse"에 대해 Benter 식으로 **시장 배당
   implied probability로 대체**하는 fallback

사용자가 "지금 메인 모델과는 완전히 다른 스코프"라고 명확히 인지하고 있고, 시간
되면 다음 주부터 검토할 수도 있다는 정도로만 열어둠 — 결정된 것 아님.

---

## 5. Unlucky/Overlooked 태그 — fund_p 버그의 영향을 받는가? → **받지 않음**

세션 막바지, 사용자가 패닉하며 질문: "fund_p가 부풀려진 채로 태그 로직에 쓰이면
태그도 다 잘못된 거 아닌가?"

`market_tags.py` 코드를 직접 확인:
```python
df["fund_p_race_rank"] = df["fund_p"].rank(pct=True)
```

태그 판정(`stats_worse`/`stats_better`, `FUND_RANK_WORSE_MAX`/`FUND_RANK_BETTER_MIN`)은
fund_p의 **절대값이 아니라 경주 내 percentile rank만** 사용. 실제로 수학적으로
증명함: 채점된 말들의 fund_p를 동일한 비율로 전부 스케일해도(= 정보부족 말 제외로
인한 softmax 재정규화와 동일한 효과) `rank(pct=True)` 결과는 **완전히 동일**
(`np.allclose` 확인, 실제 데이터로 시연).

**결론: Unlucky/Overlooked 태그 판정 로직은 이번 fund_p 이슈에 안전.** 태그의
historical reference pool 자체도 이미 실제로 뛴 경주에서 만들어진 것이라
이 문제와 무관.

---

## 6. 이번 세션에서 만든/교체한 산출물

### 최종본 (v2 — 현재 유효)
- `entry_features_fix.py` — 올바른 entry-row 재계산 로직 (신규)
- `build_tier1_features.py` — `entry_features_fix.py`를 import하도록 재작성
- `BUGFIX_v2_entry_row_features.md` — v1이 왜 틀렸는지, v2가 왜 맞는지 GPT가
  읽고 바로 이해할 수 있도록 정리한 상세 문서 (v1 문서는 폐기 표시)
- `bugfix_v2_entry_row_features.zip` — 위 3개 파일 압축, [program supervisor]/[data team lead]에게
  재전달할 최종 버전
- `bb_index_2026_08_08_09_v2_실행완료.ipynb` — 전체 파이프라인 실제 재실행 완료본.
  Section 5(경주별 전체 출전마 표, 정보부족 포함)와 Section 5.5(Top-5 요약표)를
  분리했고, 정보부족 말이 있는 경주마다 fund_p 과대평가 경고를 표 바로 위에 표시.
- `BB지수_주간결과_20260807_09_v2.pdf` — 최종 시니어 배포용. 표지 요약 →
  "fund_p 해석 주의가 필요한 경주" 목록 페이지 → Top-5 요약 → 경주별 상세,
  순서로 구성. 한글 폰트는 NanumGothic (Google Fonts 저장소에서 실제 TTF
  다운로드 — 시스템의 Noto CJK는 reportlab이 못 읽는 CFF/OTF 윤곽선이라 실패).
- `bb_index_full_v2.csv`, `bb_index_top5_v2.csv`, `bb_index_race_coverage_v2.csv`

### 폐기됨 (v1, 더 이상 사용 금지)
- `bugfix_carry_forward_entry_rows.zip` — 잘못된 carry-forward fix 포함, 대체됨
- `run_tomorrow_bb_index.ipynb` — 실행 전 템플릿, 이번 세션 목적엔 더 이상
  관련 없음
- `bb_index_2026_08_08_09_실행완료.ipynb` — v1으로 실행된 버전, 결과 90% 틀림
- `BB지수_주간결과_20260807_09.pdf` (v2 없는 버전) — 잘못된 결과 기반, [program supervisor]에게
  보내면 안 됨

---

## 7. 이메일 (초안 완료, 발송은 사용자 몫)

제목: "BB 지수 이번주 실행 결과 및 데뷔마 처리 개선 (8/7~8/9 서울·부산)"

구성: (1) 실행 결과 요약 (35/35 경주, PDF 첨부, 7/20-26 사후검증과 성격이
다르다는 점 명시) → (2) 발견/수정된 버그 (실전 전에 잡혀서 결과에 영향 없었음
강조) → (3) 데뷔마 fund_p 이슈를 결정이 필요한 open question으로 명시.

---

## 8. 다음 세션에서 참고할 핵심 규칙 (신규)

- **`shift(1)` 기반 피처를 다루는 모든 향후 수정은 반드시 "실제 과거 경주 행이
  0개 변경되는지"를 데이터로 직접 검증할 것.** 이번 v1 버그가 바로 이 검증을
  건너뛰어서 생긴 문제.
- **데이터가 없는 대상에게 0이나 평균값을 채우는 것은 항상 금지.** 정보부족은
  정보부족으로 명시하고, 그로 인해 왜곡되는 다른 값(이번엔 fund_p)이 있다면
  반드시 표에 플래그.
- **percentile rank 기반 로직(예: market_tags.py)은 절대 스케일에 강건하다**는
  걸 이번에 실증적으로 확인함 — 향후 비슷한 "이 버그가 다른 시스템도 오염시켰나?"
  질문이 나오면, 그 시스템이 절대값을 쓰는지 rank/percentile을 쓰는지부터
  확인하는 게 빠른 첫 진단.
