# 인수인계 (세션 간 이어가기용)

마지막 갱신: 2026-09-24

## 현재 단계
설계(brainstorming) 진행 중 — 이해 요약 제시, 첫 질문(LLM 모델 구성) 답변 대기.

## 완료
- GitHub 레포 생성: https://github.com/HGK-lab/SPCEXPLANER (private)
- `docs/brief.md` 작성 (배포 항목 반영, 공고 확인 사항 추가)
- `.env`에 OPENAI_API_KEY 저장 (gitignore 처리)
- `CLAUDE.md`에 '작업 중지' 규칙 정의
- 배포 연결 확인용 임시 `streamlit_app.py` + `requirements.txt` 추가 (로컬 실행 확인: health ok). Streamlit 배포 설정 = 레포 `HGK-lab/SPCEXPLANER`, 브랜치 `main`, 파일 `streamlit_app.py`. private 레포라 Streamlit Settings → Linked accounts에서 private 접근 권한 필요. 실제 앱으로 교체 예정
- 규칙 엔진 비교 실험 완료 → `docs/research/2026-09-24-spc-library-comparison.md` (추천: pycontrolcharts 판정 + shewhart 교차 검증)

## 진행 중
없음

## 다음 할 일
0. brainstorming 재개. 사용자에게 이미 보여준 것: 이해 요약(정해진 것/가정), 질문 1(LLM 모델 구성 — A: OpenAI 2모델 [추천, 대시보드에서 상위 모델 허용 필요] / B: gpt-4.1-mini만 / C: OpenAI+Anthropic). 답변 대기 중. 가정: 시리즈 20×100점, 이상 0~2개, 고정 seed, 고정 한계 σ=1, 탐지=구간 겹침, 한국어 JSON 설명(패턴/우선순위/근거 규칙), 원인표를 프롬프트에 넣음
1. superpowers brainstorming으로 설계 확정 → `docs/superpowers/specs/`에 설계 문서 저장
2. writing-plans로 구현 계획 작성
3. 사용자 확인 후 구현 시작 (executing-plans)

## 사용자 결정 사항
- LLM: OpenAI 키 사용 (이전 해커톤 키 재사용). 2026-09-24 확인: 호출 정상, 접근 가능 모델은 `gpt-4.1-mini` 1개뿐
- 배포: Streamlit Community Cloud
- 작업마다 커밋 + 푸시 (상시 허락)
- 필요하면 OpenAI 프로젝트의 허용 모델 변경 가능

## 막힌 점
없음
