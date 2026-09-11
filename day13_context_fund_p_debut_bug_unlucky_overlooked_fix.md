# Day 13 Context — fund_p 데뷔마 버그 발견 및 수정 (Unlucky/Overlooked)

**작성:** Claude (Opus-tier 세션) | **일자:** 2026-08-06
**세션 목적:** BB 지수의 데뷔마 처리 브레인스토밍 → market_tags.py의 실제 프로덕션 버그 발견 → 진단 → 두 번의 실패한 패치 → 성공한 수정 → 커버리지 보완 → 최종 산출물(zip, 이메일)

---

## 0. 세션에서 실제로 달성한 것 (한눈에)

1. **BB 지수 자체는 건드리지 않음.** 데뷔마 능력 추정 모델은 브레인스토밍만 하고 시간 부족으로 미착수.
2. **market_tags.py에서 진짜 프로덕션 버그를 발견.** `fund_p_race_rank`가 실제 출전두수가 아니라 채점된 말의 수로 나뉘고 있었음.
3. **두 번의 잘못된 패치를 시도하고 스스로 잡아냄** — 둘 다 "누락 없는 경주에서는 아무것도 안 바뀌어야 한다"는 no-op 검증을 먼저 안 하고 진행해서 발생.
4. **성공한 수정**: 부분식별(partial identification) 경계법. no-op 검증을 코드 내 assert로 강제.
5. **경계법의 부작용으로 태그 커버리지가 16.3%까지 하락** → 2단계 신뢰도(low_confidence) 폴백 추가로 19.7%까지 회복.
6. **태그의 성격을 "예측" → "이견 표시(descriptive)"로 명확히 재정의** — 이 재정의가 세션 후반부 전체를 구원함.
7. 최종 zip(`market_tags_bugfix_20260806.zip`)과 최에게 보낼 이메일 초안 완성 및 코드 재실행으로 교차검증.

---

## 1. 시작점 — BB 지수 데뷔마 브레인스토밍 (해결되지 않은 채로 남음)

### 문제 제기
BB 지수는 과거 경주 데이터가 있어야 강도 점수(V)를 산출 → percentile(BB 지수) → fund_p 순서로 작동. 데뷔마는 과거 데이터가 없어 이 파이프라인에 들어갈 수 없음 (`정보부족`/NaN).

### 사용자의 최초 아이디어
"데뷔마 전용 별도 지수를 만들어서 나중에 BB 지수와 결합하면 어떨까?"

### Claude의 반박 (유효함, 채택되지 않았지만 기록 가치 있음)
Conditional logit은 경주 내에서만 V를 식별함 — 절대 영점이 없음. 별도 모델로 데뷔마를 학습시켜도 그 V는 독립적인 임의의 스케일에 있어, BB 지수와 결합하려면 데뷔마와 경험마가 섞인 경주가 필요한데, 그런 경주가 있다면애초에 하나의 모델로 같이 학습시키는게 나음. 별도 모델은 식별력이 더 나쁜 버전 + 추가 캘리브레이션 비용만 생김.

### 제안했던 대안 (미착수)
- **Tier 1 (미착수)**: 확률질량 예약 — 데뷔마의 과거 평균 승률만큼 fund_p 질량을 떼어놓고 나머지를 재정규화
- **Tier 2 (미착수)**: `IS_DEBUT` 더미 변수를 fit_engine.py에 추가해서 하나의 모델로 처리. CAREER_STARTS=0에서 다른 4개 변수(AVESPRAT, LSPEDRAT, LIFE_PCT_WIN, W_PER_RACE, NEWDIST)를 train-fold 평균으로 impute하고, JOCK/WEIGHT/POSTPOS는 실제값 사용
- **go/no-go 체크 (미실행)**: 1600-2000m, 건/양, age≥3 필터에 데뷔마가 얼마나 남는지 SQL로 확인 필요 — 한국 신마 경주는 짧고 2세마 위주라 표본이 거의 없을 위험 있음

**이 브레인스토밍은 실행되지 않았고, 다음 세션에서 이어갈 수 있는 상태로 남음.** 대신 세션은 완전히 다른 방향(market_tags.py의 실제 버그)으로 흘러갔음.

---

## 2. 실제 버그 발견 — fund_p_race_rank 계산 오류

### 진단 과정
`unified_dataset.csv`에서 `n_starters`(실제 출전두수)와 실제 존재하는 행 수를 비교 → 5,878개 경주 중 1,935개(32.9%)에서 갭 발견.

**4개 조인 소스별 분해** (핵심 진단):
- 누락된 4,638개 행 중 배당(odds) 보유: 100%
- 전문가 점수 보유: 100%
- **fund_p 보유: 0%**

→ 조인 문제 아님. 전적으로 기본모델이 채점 못한 것 (데뷔마 등).

**결정적 사실**: 누락된 말은 약한 말이 아님.
- 경주 내 배당순위 백분위: 미채점 0.49 (median 0.45) vs 채점됨 0.55
- 복승 적중률: 미채점 30.5% vs 채점됨 28.0%

→ 중상위권 말들을 조용히 삭제하고 있었음. 남은 말들의 백분위가 위로 밀려 올라감.

### 수학적 프레이밍
```
E[진짜 순위_i] = 관측순위_i + (N - n) · F_miss(능력_i)
```
`F_miss == F_obs`(무작위 누락)면 기존 코드가 이미 정확. 진단 결과 `F_miss ≠ F_obs` 확인 → 수정 필요.

---

## 3. 두 번의 실패한 패치 (교훈으로서 중요)

### 패치 1 — 확률질량 재배분 (수학적으로 완전히 무효)
경주 내 fund_p를 `n_present/n_starters`로 균등하게 축소한 뒤 rank(pct=True) 계산.

**실패 이유**: 같은 그룹 내 모든 값을 동일한 양수로 스케일해도 순위는 절대 바뀌지 않음. `rank(fund_p * 0.8) == rank(fund_p)`가 항상 성립. max diff = 0.000000 — 기계적으로 보장된 결과였음.

### 패치 2 — n/(N+1) 분모 교체 (전역적으로 캘리브레이션을 깨뜨림)
서수 순위를 `n_starters + 1`로 나누는 방식 시도.

**실패 이유**: 누락이 전혀 없는 경주(clean races)에서도 값이 바뀜을 발견 — 평균 percentile이 0.547 → 0.500으로 이동. 데뷔마 효과가 아니라 공식 자체의 전역적 편향.

### 공통 원인
**두 패치 모두 "누락 없는 경주에서는 아무것도 안 바뀌어야 한다"는 no-op 검증을 먼저 하지 않고 진행**해서 발생. 이 교훈이 최종 수정의 설계 원칙이 됨 — 최종본은 이 검증을 코드 내 `assert`로 강제.

---

## 4. 성공한 수정 — 부분식별(Partial Identification) 경계법

`m = N - n` (N=실제 출전두수, n=채점두수), `r` = 채점된 말들 사이의 서수 순위:

```python
pct_lo = r / N        # 최선: 미채점 말이 전부 위에 있다고 가정
pct_hi = (r + m) / N  # 최악: 미채점 말이 전부 아래에 있다고 가정
```

각 태그는 **자신에게 불리한 쪽 경계**에서도 조건을 만족할 때만 발동:
- Unlucky (통계 나쁨, pct ≤ 0.333) → `pct_hi` 검사
- Overlooked (통계 좋음, pct ≥ 0.667) → `pct_lo` 검사

`m == 0`이면 두 경계 모두 `r/N`으로 수렴 → 기존 동작과 완전히 동일. **오차 1e-12 수준으로 확인, assert로 강제.**

`market_tags.py`의 `tag_race()`에 `n_starters` 파라미터 추가 (옵셔널, 하위호환 — 안 넘기면 기존 버그 동작 그대로).

---

## 5. 검증 여정 — 통계적 유의성에 대한 여러 차례의 재평가

### 5.1 첫 시도: ratio vs 1.0 (배당 대비 적중)
- Unlucky: 0.913 → 0.881 (경계법), 0.888 (참고: 배당보정 imputation, R²=0.47)
- Overlooked: 0.780 → 0.994

두 방식(경계법/imputation)이 0.881, 0.888로 독립적으로 수렴 — 처음엔 이게 강한 증거라고 판단.

### 5.2 사용자의 핵심 지적 — "경계법 vs imputation 모두 favourite-longshot bias(FLB)를 통제 못한다"
사용자가 Overlooked를 originally 선호했던 이유(위험이 적다 — "안될 것 같은 말이 잘 되면 좋고, 안돼도 원래 기대 안했으니 리스크 없음")를 설명하며, 0.780이라는 숫자가 "안될 것"이라는 그 컨셉과 모순됨을 지적.

**FLB 검증**: 배당 십분위별 population ratio를 계산한 결과, 2.5배당 그룹은 ratio 0.937, 89배당 그룹은 ratio 0.609 — 장외마는 원래 배당보다 못한 성적을 냄 (모델과 무관하게).

odds-matched lift 재계산 결과:
| 태그 | ratio | odds-matched baseline | lift |
|---|---|---|---|
| Unlucky corrected | 0.881 | 0.974 | -0.093 |
| Overlooked corrected | 0.994 | 0.913 | **+0.081** (방향은 맞으나 미검증) |

Bootstrap CI 적용 결과 **모든 lift의 CI가 0을 포함** — 어느 것도 통계적으로 증명되지 않음. Claude가 한 번 "Unlucky는 실재한다"고 과신했다가 스스로 정정.

### 5.3 사용자의 재정의 — "이 태그들은 예측이 아니다"
> "none of these are predictive but just descriptive contents tags... a simple 'caution alert'... Just an added bonus fun... nothing predictive"

이 재정의로 5.2의 예측력 검증(ratio, lift, FLB-adjusted ratio)은 전부 **선택적 참고 자료**로 격하됨. 진짜 필요한 검증은: "라벨링 규칙이 정확한가"(수정됨) + "그 라벨이 가리키는 이견 현상이 실재하는가".

### 5.4 이견 비율 검증 — 한 번의 계산 오류와 정정
**첫 계산 (틀림)**: 느슨한 tercile 기준(`expert_pct<=0.333 or >=0.667`, `pct_hi`)으로 "강한 이견"을 정의해 39.8% vs 우연 기대치 22.2% — "우연보다 2배 자주 갈린다"고 잘못 보고.

**실제 배포된 `tag_race()` 함수로 직접 재실행한 결과 (정정)**: 실제 임계값(`EXPERT_HIGH_MIN=97`, `EXPERT_LOW_MAX=23`, `FUND_RANK_WORSE_MAX=0.333`, `FUND_RANK_BETTER_MIN=0.667`) 기준으로는 전체의 **1.9%**만 해당, 우연 기대치는 **약 21%** — 정반대 방향, 즉 **우연보다 훨씬 드물게** 갈림.

해석: 전문가와 모델은 대체로 강하게 일치(Spearman rho=0.717, 유의함) → 그렇기 때문에 강하게 갈리는 경우가 드묾. 이건 태그가 무의미하다는 뜻이 아니라 "두 신호가 평소 잘 맞기 때문에 갈리는 순간이 통계적으로 특정 가능한 소수 사례"라는 뜻으로, 오히려 "캐치할 만한 소수 사례" 컨셉에 부합.

**교훈**: 이메일과 README 양쪽에 이 정정 사실을 명시적으로 남김 — 이전에 틀린 숫자(39.8%)를 사용자가 이미 봤기 때문.

---

## 6. 커버리지 문제와 2단계 신뢰도 구조

### 문제 제기
사용자가 "20~25% 미만이면 상품으로 부적합하다"는 기존 우려를 상기시킴 (Overlooked 33%/40% 임계값 논쟁의 원래 배경).

### 측정 결과
| | 경계법 적용 전(추정) | 경계법만 적용 | 
|---|---|---|
| 태그 붙는 경주 비율 | ~22-24% | **16.3%** |

경계법이 보수적이라 커버리지를 깎아먹음이 확인됨.

### 해결책 — 2단계 신뢰도
- **Full confidence**: 경계법(`pct_hi`/`pct_lo`) 통과 (기존과 동일)
- **Low confidence**: 경계법은 실패했지만, 올바른 분모(N)를 쓴 점추정치(`fund_p_race_rank = r/N`)로는 조건 만족 → 태그 발동, `TagResult.low_confidence=True` 플래그, `explain()`에 자동 안내문 추가

### 결과 (57,753행 전체 실행으로 검증됨)
| | full-confidence | low-confidence | 합계 |
|---|---|---|---|
| Unlucky | 404 | 241 | 645 |
| Overlooked | 722 | 0 | 722 |

태그 붙는 경주: 958 (16.3%) → **1,159 (19.7%)**

### 핵심 발견 — 회복은 전부 Unlucky에서만 발생 (수식적 필연, 버그 아님)
점추정치의 분모가 n→N으로 커지면 값은 항상 같거나 작아짐. 이는:
- "통계가 나쁘다"(Unlucky, ≤0.333) → 더 쉽게 통과
- "통계가 좋다"(Overlooked, ≥0.667) → 더 어렵게 통과

→ Overlooked는 이 폴백으로 구제될 수 없음. Overlooked의 커버리지 손실(16.2%→11.3%)은 그대로 유지됨. 이걸 README와 이메일에 명시적으로 설명함 (버그처럼 보일 수 있어서).

### no-op 게이트 재확인
low_confidence 태그가 clean race(m=0)에서 발동한 건수 = 0 (57,753행 전체 실행으로 확인).

---

## 7. 최종 산출물

### 코드
`market_tags.py`의 `tag_race()` 함수:
- `n_starters` 파라미터 추가 (옵셔널, 하위호환)
- `fund_p_rank_lo`, `fund_p_rank_hi`, `fund_p_race_rank`(점추정치), `n_unscored` 계산
- 2단계 신뢰도 로직: full-confidence 경계 → 실패시 low-confidence 점추정치 폴백
- `TagResult`에 `low_confidence: bool` 필드 추가, `explain()`에 자동 안내문

### zip 구조 (`market_tags_bugfix_20260806.zip`)
```
bugfix/
  README.md (한글, 상세 문서)
  code/
    market_tags.py            <- 최종 수정본
    market_tags_ORIGINAL.py   <- 대조용 원본
    debut_rank_fix.py         <- 진단+검증 재현 스크립트
  results/
    debut_fix_comparison.csv
    overlooked_fix_comparison.csv
    final_tag_output_all_races.csv  <- 최종본으로 57,753행 전체 실행한 실제 출력
  docs/
    BUGFIX_NOTE_ko.md (README와 동일 내용)
```

**독립 검증 완료**: zip을 별도 폴더에 압축 해제 후 처음부터 재실행하여 1,126 full + 241 low-confidence, 19.7% 커버리지를 재현 확인.

### 이메일 ([program supervisor] 앞, 초안 완성)
구조: 태그 성격 정의 → 원인 → 1차 수정(경계법) → 2차 보완(커버리지) → Unlucky-only 비대칭 설명 → 최종 태그 개수표 → 이견 비율 통계(1.9% vs 21%, 이전 오류 정정 포함) → 참고용 ratio 표 → BB 지수 미수정 참고 → 반영 방법(`n_starters` 필수 전달).

---

## 8. 다음 세션을 위한 열린 항목

- **BB 지수 데뷔마 처리는 여전히 미착수.** 2절의 Tier 1/Tier 2 아이디어와 go/no-go SQL 체크가 다음 세션의 시작점이 될 수 있음.
- **Overlooked의 예측적 주장(배당 대비 우위)은 검증되지 않은 채로 out of scope 처리됨.** 서술형 태그로만 유지한다면 문제 없으나, 나중에 예측력을 다시 claim하고 싶다면 별도 검증 필요.
- **odds-matched FLB 통제는 십분위 기반이라 거칠음** (프로젝트의 기존 원칙 "bucketed controls leak"과 동일한 한계). 연속형 통제(로지스틱 회귀 기반)로 한 번 더 해봤으나 이것도 최종 결론에는 채택되지 않음 — 서술형 재정의로 필요성이 사라짐.
- **low_confidence 태그의 UI 표시 방식**은 제안만 하고 실제 프론트 작업은 안 함 ("추정" 배지 등).
- 반영 시 `tag_race()` 호출부에 `n_starters` 전달을 빠뜨리지 않도록 운영팀에 재확인 필요 — 인자 생략 시 조용히 기존 버그 동작으로 돌아감.

---

## 9. 재현 방법

```bash
cd bugfix/code
python3 debut_rank_fix.py  # 진단 + 경계법 검증, no-op assert 포함
```

전체 57,753행에 최종 태그 로직을 돌려보려면 (zip 안에 없는 임시 검증 스크립트, 이 문서의 §6 결과를 재현):
```python
import pandas as pd
import market_tags as M
d = pd.read_csv('unified_dataset.csv', dtype={'race_id':str})
for race_id, g in d.groupby('race_id'):
    horses = g[['horse_num','odds_final','expert_score']].to_dict('records')
    fund_p = g['fund_p'].tolist()
    N = max(int(g['n_starters'].iloc[0]), len(horses))
    results = M.tag_race(horses, fund_p, n_starters=N)
    # results[i].tag, results[i].low_confidence 확인
```
(`unified_dataset.csv`, `unlucky_reference_pool.csv`, `overlooked_reference_pool.csv`가 `code/` 폴더에 있어야 함 — `_load_pool()`이 상대경로로 읽음)
