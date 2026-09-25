# 인수인계 (세션 간 이어가기용)

마지막 갱신: 2026-09-25

## 현재 단계
설계 문서·구현 계획 작성 완료. 화면은 절충안 C(`docs/design/2026-09-25-ui-comparison.md`)로, 그래프 시안 2장(`docs/design/ref/`)을 반영해 계획에 Task 11-1~11-4를 추가함(계획서 코드 실행 검증: 테스트 80개 통과, 실제 화면 캡처로 시안 대조). 사용자 승인 대기 — 승인하면 Task 1부터 바로 구현.

## 완료
- GitHub 레포 생성: https://github.com/HGK-lab/SPCEXPLANER (private)
- `docs/brief.md` 작성 (배포 항목 반영, 공고 확인 사항 추가)
- `.env`에 OPENAI_API_KEY 저장 (gitignore 처리)
- `CLAUDE.md`에 '작업 중지' 규칙 정의
- 배포 연결 확인용 임시 `streamlit_app.py` + `requirements.txt`. Streamlit Community Cloud에 임시 배포 완료(사용자 확인, 2026-09-25). 배포 설정 = 레포 `HGK-lab/SPCEXPLANER`, 브랜치 `main`, 파일 `streamlit_app.py`
- 규칙 엔진 비교 실험 → `docs/research/2026-09-24-spc-library-comparison.md`
- 설계 문서 → `docs/superpowers/specs/2026-09-25-spc-explainer-design.md`
- 구현 계획(13개 태스크, 전체 코드 포함) → `docs/superpowers/plans/2026-09-25-spc-explainer.md`
  - 계획서 코드를 scratchpad에 추출해 실제 실행으로 검증: Task 1~12 테스트 55개, Task 13 적용 후 60개 통과
- `docs/ai_errors.md` 생성: 설계 검증 스모크 호출에서 나온 gpt-4.1-mini 단독 판정 오답 1건 기록

## 진행 중
없음

## 다음 할 일
1. 사용자 승인을 받는다: 계획(Task 1~13, 11-1~11-4 포함)과 실행 방식(추천: 네이티브 — 이 세션에서 순서대로 구현, 끝에 리뷰어 1회). 순서: Task 1~11 → 11-1 → 11-2 → 11-3 → 11-4 → 12 → 13. 9/26 18시 기준선에 걸리면 그 자리에서 멈춘다(SECOM부터 뺌).
2. 계획서 Task 1부터 구현. 첫 명령: `python -m venv .venv` → `.venv/Scripts/python -m pip install -q -r requirements-dev.txt` (requirements 파일은 Task 1 Step 1에서 먼저 만든다)
3. Task 10에서 실제 실험(API 168회) 실행 후 결과 커밋
4. Task 11 푸시 후 사용자에게 받을 것: 배포 URL(README에 넣음), Streamlit Secrets에 `OPENAI_API_KEY` 추가(실시간 설명용)
5. 시간이 부족하면 Task 13(SECOM)부터 뺀다

## 사용자 결정 사항
- LLM: OpenAI 키 사용 (이전 해커톤 키 재사용)
- 배포: Streamlit Community Cloud
- 작업마다 커밋 + 푸시 (상시 허락)
- 필요하면 OpenAI 프로젝트의 허용 모델 변경 가능
- 2026-09-25 LLM 구성(A안): 설명 = gpt-4.1-mini, 단독 판정 비교 = gpt-4.1-mini vs gpt-6-sol, gpt-6-astra는 설정으로 켜고 끄는 1회 비교(현재 비활성 → 기본 끔). 모델명은 `spc_explainer/config.py` 한 곳에서 관리
- 2026-09-25 가정 전부 승인 + 추가 요구 4가지: (1) 20개 중 정상 시리즈 5개 이상, 오탐 따로 보고 (2) LLM 출력 3회 반복, 형식 위반·원인표 밖 원인·판정 불일치 기록 (3) UCI SECOM 실데이터 확인(결측 적은 센서 1~2개, 앞 구간으로 한계 추정, 탐지율 없이 작동 확인 + 불량 라벨 겹침 관찰, 시간 부족 시 가장 먼저 제외) (4) 설계 문서에 "관리한계 고정값 = 안정화된 공정 감시 가정" 명시
- 2026-09-25 화면: 절충안 C, 비교 문서 5절 순서 유지. 그래프 시안 2장(관리도, 패턴별 탐지율 막대)의 스타일만 따르고 숫자는 결과 파일에서만 읽음. 점 번호 0부터·100점. 정답 구간은 테두리만 있는 점선. LLM 단독 막대는 모델별로 반복 평균 + 최소~최대
- 구현 마감 기준선: 9/26 18시
- 설계 중 확인 후 정한 것 (사용자가 바꿀 수 있음): 추세 = 연속 6점(증가 5회, pycontrolcharts `test3_n=5`, 라이브러리 기본값 7점과 다름), temperature는 4.1-mini 0 / sol 기본값(sol이 0을 거부)

## 막힌 점
없음. 참고: 2026-09-25 기준 키로 보이는 모델은 gpt-4.1-mini, gpt-6-sol 둘뿐 (astra는 대시보드에서 허용해야 함)
