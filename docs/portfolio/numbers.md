# 핵심 수치 요약 (포트폴리오용 1쪽)

모든 숫자는 아래 결과 파일에서만 뽑았다. 괄호 안이 출처(파일 · 필드)다. 실험 실행: 2026-09-25 23:46(설명) · 23:48(단독 판정), 집계: 2026-09-26 09:53 (`results/metrics.json` · `generated_at`).

## 실험 조건
- 가상 관리도 20개 시리즈 × 100점, 정상 5개, 심은 이상 21개 (급변 7 · 추세 7 · 치우침 7), 시드 20260925 (`results/metrics.json` · `dataset`)
- 관리 기준: 중심선 100.0 · UCL 103.0 · LCL 97.0 nm, 고정값 = 안정화된 공정 감시 가정 (`data/synthetic/series.json` · `center`·`ucl`·`lcl`)

## 1. 규칙 엔진 판정 (결정적, 1회)
| 항목 | 값 | 출처 |
|---|---|---|
| 탐지 | 21 / 21 (100%) — 급변 7/7, 추세 7/7, 치우침 7/7 | `metrics.json` · `rules.detected`·`rules.per_pattern` |
| 정상 시리즈 경보 | 5개 중 1개 | `rules.normal.alarmed_series` |
| 오탐 사건 | 6건 (정상 시리즈 급변 1 + 이상 시리즈 급변 2·추세 2·치우침 1) | `rules.normal.false_events`·`rules.anomalous.false_events`·`rules.false_list` |
| 패턴 혼동 | 0건 | `rules.anomalous.confusions` |
| 시리즈 1개(100점) 판정 시간 | 평균 0.48ms (중앙값 0.44ms, 400회, Python 3.10.11, 2026-09-27 측정) | `results/rule_timing.json` (`scripts/measure_rules.py`) |

## 2. LLM 단독 판정 비교 (규칙 정의 + 원시값만 주고 직접 판정, 모델별 3회)
| 항목 | gpt-4.1-mini (temperature 0) | gpt-6-sol (기본값) | 출처 |
|---|---|---|---|
| 탐지율 (3회) | 67% · 67% · 67% (14/21) | 100% · 100% · 100% (21/21) | `metrics.json` · `detect[].runs[].rate`·`detected` |
| 추세 탐지 (3회) | 6 · 5 · 6 / 7 (평균 5.7) | 7 · 7 · 7 / 7 | `detect[].runs[].per_pattern.trend` |
| 치우침 탐지 (3회) | 1 · 2 · 1 / 7 (평균 1.3) | 7 · 7 · 7 / 7 | `detect[].runs[].per_pattern.shift` |
| 정상 시리즈 경보 | 5 / 5 (3회 모두) | 1 / 5 (3회 모두) | `detect[].runs[].normal.alarmed_series` |
| 오탐 사건 (회당) | 115 · 98 · 96 (평균 103) | 6 · 6 · 6 | `detect[].runs[].normal·anomalous.false_events` 합 |
| 패턴 혼동 (회당) | 28 · 18 · 23 (평균 23) | 0 · 0 · 0 | `detect[].runs[].anomalous.confusions` |
| 형식 위반 · 호출 오류 | 0 · 0 | 0 · 0 | `detect[].runs[].format_violations`·`call_errors` |
| 호출 수 | 60 (20 시리즈 × 3회) | 60 | `results/llm_detections.json` · `models.*.series.*.runs` |
| 응답 시간 평균 (중앙값, 최소~최대) | 2.05초 (1.70, 1.05~4.50) | 10.82초 (10.08, 7.36~18.09) | `llm_detections.json` · `runs[].latency_s` |
| 토큰 합계 (입력 / 출력) | 56,880 / 10,449 | 56,820 / 34,625 | `llm_detections.json` · `runs[].usage` |
| 비용 (60회) | $0.039 | $0.46 | 위 토큰 × `config.PRICES_USD_PER_1M` (OpenAI 가격표, 2026-09-27 확인) |

gpt-6-sol의 오탐 6건은 규칙 엔진의 오탐 6건과 같은 사건이다 (`detect[1].runs[].false_list` = `rules.false_list`, 방향 필드만 없음).

## 3. 설명 LLM 검증 (gpt-4.1-mini, temperature 0, 같은 입력 3회)
| 항목 | 값 | 출처 |
|---|---|---|
| 호출 | 사건 있는 시리즈 16개 × 3회 = 48 | `metrics.json` · `explain.series_called`·`outputs` |
| 검증 통과 | 48 / 48 | `explain.passed` |
| JSON 형식 위반 · 원인표 밖 원인 · 판정 불일치 | 0 · 0 · 0 | `explain.issue_outputs` |
| 호출 오류 | 0 | `explain.call_errors` |
| 반복마다 1순위 원인·점검 순서가 바뀐 시리즈 | 0 / 16 | `explain.repeat_changed_series` |
| 응답 시간 평균 (중앙값) | 3.38초 (3.30) | `results/explanations.json` · `runs[].latency_s` |
| 토큰 합계 (입력 / 출력) | 45,210 / 17,843 | `explanations.json` · `runs[].usage` |
| 비용 (48회) | $0.047 | 위 토큰 × `config.PRICES_USD_PER_1M` |

실험 전체 호출: 60 + 60 + 48 = 168회, 호출 오류 0. 비용 합계 $0.546 ($0.039 + $0.460 + $0.047).

## 4. 실데이터 확인 (UCI SECOM, 정답 없음 — 탐지율 계산 안 함)
시간순 1,567행 중 앞 500점(Phase I)으로 한계 추정, 나머지 1,067점(Phase II)을 같은 규칙으로 감시 (`metrics.json` · `secom.n`·`secom.phase1_n`).

| 센서 | 중심선 · σ | 알람 사건 (급변/추세/치우침) | 불량 포함 사건 | 알람 점 중 불량 비율 | Phase II 전체 불량 비율 |
|---|---|---|---|---|---|
| sensor_88 | 1813.7 · 49.96 | 24 (15/3/6) | 4 | 6.1% (알람 점 98개) | 4.2% |
| sensor_115 | 745.8 · 49.36 | 10 (7/3/0) | 1 | 3.8% (알람 점 26개) | 4.2% |

출처: `metrics.json` · `secom.sensors.*` (`limits`, `events`, `by_pattern`, `events_with_fail`, `flagged_points`, `fail_rate_flagged`, `fail_rate_phase2`). 겹침은 관찰일 뿐, 인과나 탐지 성능으로 해석하지 않는다.

## 계산 기준
- 비용: 결과 파일의 토큰 수에 `spc_explainer/config.py`의 단가표(USD / 100만 토큰 — gpt-4.1-mini 입력 $0.40·출력 $1.60, gpt-6-sol 입력 $2.00·출력 $10.00, https://developers.openai.com/api/docs/pricing 2026-09-27 확인)를 곱했다. 결과 파일에는 캐시 입력 구분이 없어 입력은 모두 캐시 안 된 단가로 계산했다 (실제 청구액과 같거나 조금 크다). 04 화면의 KPI 카드도 같은 계산이다.
- 사례 해설의 "한계 안 값을 급변이라고 한 점 262개(보고한 293개 중)": `python scripts/case_counts.py`가 `results/llm_detections.json`에서 센 값 (`tests/test_case_notes.py`가 해설 글과 대조).
