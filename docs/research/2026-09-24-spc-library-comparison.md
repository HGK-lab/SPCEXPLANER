# 규칙 판정 라이브러리 비교 (2026-09-24)

설계 단계에서 규칙 엔진 후보 2개를 실제로 설치해 같은 데이터로 돌려본 기록.
재현: `probe_spc_libs.py` (Python 3.10, `pip install pycontrolcharts shewhart`).

## 실험 데이터
- 증착 막 두께 100점, 중심 100nm, σ=1 → 관리한계 97~103nm (고정 한계)
- 심은 이상 (정답 라벨)
  - 급변: 30번 점 = 104.2
  - 추세: 50~56번 7점 연속 상승
  - 치우침: 75~84번 10점이 중심선 위

## 결과

| 패턴 | 정답 | pycontrolcharts | shewhart |
|---|---|---|---|
| 급변 | 30 | 30 (type 1, "Point beyond upper control limit") | 30 (nelson_1) |
| 추세 | 50~56 | 51~56 (type 5, "6 consecutive increasing points") | 50~56 (nelson_3) |
| 치우침 | 75~84 | 74~84 (type 3, "9 consecutive points above center line") | 74~84 (nelson_2) |

두 라이브러리 모두 3패턴을 전부 탐지했고 판정이 일치했다. 표시하는 점 범위만 조금 다르다:
- 추세: pycontrolcharts는 "증가한 점"(51~)만, shewhart는 런 전체(50~)를 표시.
- 치우침: 74번 점이 우연히 중심선 위에 있어 둘 다 74부터 표시 (정상 동작).
→ 탐지율 계산은 "정답 구간과 탐지 구간이 겹치면 탐지"로 정의해야 한다.

## 비교

| 기준 | pycontrolcharts 0.1.2 | shewhart 0.1.1 |
|---|---|---|
| 3패턴 지원 | O (테스트 1·2·3, 개별 on/off 가능) | O (nelson_1·2·3, 규칙은 세트 단위 선택이라 필터 필요) |
| 고정 관리한계 | `CustomLimits` + `run_tests_with_custom_limits` | `limits={i_center, sigma_within, mr_center}` |
| 출력 | 점별 DataFrame, `violations`에 `{type, description}` (방향 포함: 위/아래, 증가/감소) | `Signal{rule, points, note}`, `to_json()`, 사람용 `summary()` |
| 범위 밖 신호 | 끈 테스트는 안 나옴 | nelson 4~8, MR 한계 신호가 함께 나옴 |
| 의존성 | pandas | numpy, pandas, scipy, matplotlib |
| 실행 시간 (100점) | 0.8ms | 277ms (첫 호출) |
| 유지보수 | MIT, 2026-03 최종 릴리스, ★1 | MIT, 2026-06 최종 릴리스, ★3, 공개 기준값 대조 검증 표방 |

## 결론
- **판정 엔진: pycontrolcharts.** 3패턴만 정확히 켤 수 있고, 위반마다 방향이 담긴 유형 코드와 설명이 붙어 LLM 입력으로 바로 쓸 수 있다. 의존성이 가벼워 배포에 유리.
- **교차 검증: shewhart (개발·테스트 전용 의존성).** 테스트에서 두 엔진의 판정이 일치하는지 확인해 "규칙 판정 자체도 독립 구현으로 검증했다"는 근거로 쓴다.
- 두 라이브러리 모두 신생(스타 1~3개)이라, 판정 결과를 교차 검증하는 테스트가 더 중요하다.
