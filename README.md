# SPC 설명기

반도체 증착 공정(막 두께) 관리도에서 **판정은 규칙 엔진, 설명은 LLM**이 맡는 데모 앱입니다.
SK하이닉스 AI 해커톤 2026 지원용 포트폴리오로 만들었습니다.

- 설계 문서: `docs/superpowers/specs/2026-09-25-spc-explainer-design.md`
- 구현 계획: `docs/superpowers/plans/2026-09-25-spc-explainer.md`
- 검증 리포트: `docs/validation_report.md`
- LLM 오류 기록: `docs/ai_errors.md`
- 사례 해설 (수동 분석): `docs/case_notes.md`
- 화면 설계 비교: `docs/design/2026-09-25-ui-comparison.md` (그래프 시안: `docs/design/ref/`)

## 동작 방식

1. **가상 데이터**: 20개 시리즈 × 100점. 정상 5개, 나머지 15개에 급변·추세·치우침을 규칙 정의대로 심고 위치를 정답으로 남깁니다.
2. **규칙 판정**: pycontrolcharts로 3패턴만 검사합니다. 독립 구현(shewhart)과 점 단위로 일치하는지 테스트합니다.
3. **LLM 설명**: 규칙 판정 결과(JSON)와 원인표만 받아 "어떤 패턴 / 점검 우선순위 / 근거 규칙"을 한국어 JSON으로 씁니다. 검증기가 형식 위반·원인표 밖 원인·판정 불일치를 잡습니다.
4. **비교 실험**: LLM에게 원시 데이터만 주고 직접 판정하게 해서 규칙 엔진과 같은 기준으로 채점합니다.
5. **실데이터 확인**: 공개 반도체 공정 데이터(UCI SECOM) 센서 2개에 같은 규칙 엔진을 적용합니다. 정답이 없어 탐지율 대신 작동 여부와 불량 라벨과의 겹침만 봅니다.

화면은 한 페이지 스토리형입니다: 머리말 → 01 문제 → 02 규칙 판정 → 03 AI 설명 → 04 검증 → 05 실데이터(SECOM) → 06 한계. 휴대폰에서는 같은 페이지가 한 줄로 쌓입니다.

## 실행 방법

준비 (한 번):

    python -m venv .venv
    .venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
    pip install -r requirements-dev.txt

`.env` 파일을 만들고 키를 넣습니다 (커밋 금지, `.gitignore`에 들어 있음):

    OPENAI_API_KEY=sk-...

앱 실행:

    streamlit run streamlit_app.py

테스트 (네트워크 호출 없음):

    python -m pytest

실험 다시 돌리기:

    python scripts/run_experiment.py            # LLM 호출. 이미 받은 결과는 캐시에서 재사용
    python scripts/run_experiment.py --no-llm   # LLM 없이 지표·리포트만 다시 생성
    python scripts/run_experiment.py --force    # 캐시를 무시하고 모두 다시 호출

SECOM 선정 센서 다시 받기 (선택, 결과 CSV는 저장소에 들어 있음):

    python scripts/fetch_secom.py

## 설정

`spc_explainer/config.py` 한 곳에서 바꿉니다: 모델명, temperature, 반복 수, `gpt-6-astra` 켜기/끄기, 실시간 호출 한도, 공정 상수, SECOM 센서 선정 조건.
`gpt-6-astra`는 OpenAI 대시보드에서 모델을 허용한 뒤 `enabled`를 `True`로 바꾸면 단독 판정 비교에 1회 들어갑니다.

## 배포

Streamlit Community Cloud: 레포 `HGK-lab/SPCEXPLANER`, 브랜치 `main`, 파일 `streamlit_app.py`. Streamlit 버전은 `requirements.txt`에서 1.64로 고정합니다 (화면 CSS가 이 버전에서 검증됨).
실시간 설명을 켜려면 App settings → Secrets에 다음을 넣습니다. 키가 없어도 저장된 결과로 모든 화면이 동작합니다.

    OPENAI_API_KEY = "sk-..."

## 가정과 한계

- 관리한계 고정값(중심 100nm, UCL 103nm, LCL 97nm) 사용 = 이미 안정화된 공정을 감시하는 상황을 가정합니다.
- 추세는 "연속 6점이 계속 증가/감소"(증가 5회)로 정의했습니다. pycontrolcharts 기본값(7점)과 달라 `test3_n=5`로 맞췄습니다.
- 원인표는 교과서 수준의 도메인 가정이며 실제 설비 데이터로 검증하지 않았습니다.
- 합성 데이터라 실제 공정의 잡음 구조를 반영하지 않고, 표본(시리즈 20개, 이상 21개)이 작습니다.
- SECOM은 정답이 없어 탐지율을 계산하지 않습니다. 앞 500점으로 한계를 추정하고 나머지를 감시해 "작동 확인 + 불량 라벨과의 겹침 관찰"만 보고합니다.

## 데이터 출처

- UCI SECOM: McCann, M. & Johnston, A. (2008). SECOM [Dataset]. UCI Machine Learning Repository. https://doi.org/10.24432/C54305 (CC BY 4.0). `data/secom/secom_selected.csv`는 이 데이터에서 센서 2개와 라벨·시각만 뽑은 것입니다.
