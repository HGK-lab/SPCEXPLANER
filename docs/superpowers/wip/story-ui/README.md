# 2A 스토리형 화면 프로토타입 (작업 중, 2026-09-26 새벽)

계획서에 아직 들어가지 않은 화면 코드다. 다음 세션에서 이 파일들을 바탕으로 계획서의 화면 태스크를 다시 쓴 뒤 구현한다.
여기 있는 `.py`는 저장소 패키지가 아니다(`tests/`도 pytest 수집 대상이 아님).

## 무엇인가
- Claude Design 2A(데스크톱 스토리형)·2B(모바일) 시안을 Streamlit으로 옮긴 한 페이지 화면:
  머리말(원칙 한 문장 + ① 규칙 판정 → ② AI 설명 → ③ 검증) → 01 문제 → 02 규칙 판정 → 03 AI 설명 → 04 검증 → 05 SECOM → 06 한계
- 사용자 조건 반영: 결과 파일 읽기·SECOM 계산은 `st.cache_data`, 시리즈·센서 선택은 `st.fragment`로 그 섹션만 다시 그림,
  04에 "AI 오류 유형별 개수(자동 집계)"와 분리된 "사례 해설(수동 분석)" 칸(`docs/case_notes.md`),
  오류 분류는 검증기·채점기 기준, KPI에 실제 모델명(등급 표기는 `ui_dashboard.MODEL_TIER`), 시안의 예시 수치는 쓰지 않음
- 04 제목은 "AI가 판정까지 직접 하면 어떻게 될까"로 중립화 (실험에서 gpt-6-sol이 규칙 엔진과 같은 판정을 냈기 때문, 사용자 확인 전)

## 검증 상태 (scratchpad에서)
- 저장소 코드(Task 1~10) + 옛 계획의 SECOM 코드(`secom.py`, `fetch_secom.py`, experiment의 SECOM 연결) + 이 폴더의 파일로 전체 테스트 85개 통과
- 실제 결과 파일(results/, data/synthetic/series.json)로 앱을 띄워 헤드리스 Chrome으로 데스크톱(1440px)·모바일(400px) 캡처 확인
- 마지막 캡처 뒤에 고친 세 가지는 **테스트만 통과했고 화면 재확인 전**:
  1. `charts.py` 음영 라벨 두 줄 엇갈림 (`LABEL_GAP=25`, `LABEL_ROW_PX=16`)
  2. `ui_html.CSS`의 사례 해설 카드 소제목·본문 글자 크기
  3. "실험 …" → "지표 생성 …" 표기, 오류 개수 카드의 오탐 기준 각주

## 저장소에 넣을 때 필요한 변경
- `spc_explainer/config.py`에 한 줄 추가 (`config_change.txt`):
  `CASE_NOTES_PATH = ROOT / "docs" / "case_notes.md"  # 04 검증의 사례 해설(수동 분석)`
- 앱이 `secom`을 바로 import하므로 SECOM 태스크(옛 Task 13의 모듈·데이터 부분)를 화면 태스크보다 먼저 한다
- `docs/case_notes.md`는 실제 오답(`docs/ai_errors.md` 실행 2026-09-25T23:48:41)을 대조해 쓴 초안. 사용자 검토 필요

## 도구 (`tools/`)
- `extract_plan.py <plan.md> <out_dir> <마지막 태스크 번호>`: 계획서 코드 블록을 추출해 검증용 프로젝트를 만든다
- `apply_brief.py <brief.md> <repo> tests|impl`: 태스크 브리프의 코드를 저장소에 그대로 옮긴다 (테스트 먼저)
- `cdp_shot.py <chrome_profile_dir> <url> <out.png> ...`: Chrome 원격 디버깅으로 렌더링을 기다린 뒤 캡처. 크기는 환경변수 `SHOT_W`, `SHOT_H`
  (스크립트 안의 Chrome 경로는 `C:\Program Files\Google\Chrome\Application\chrome.exe`, 필요 패키지 `websocket-client`)
