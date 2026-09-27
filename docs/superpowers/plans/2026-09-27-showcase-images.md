# 포트폴리오 소개 이미지 6장 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 스펙대로 1920×1080 소개 이미지 6장(PNG)과 원본(캡처·선화·slides.html)을 `docs/portfolio/showcase/`에 만든다.

**Architecture:** 로컬 Streamlit 앱을 스킬의 `capture.mjs`로 몰아 데스크톱·모바일 원본을 찍고, SVG 선화 2장을 따로 그린 뒤, 한 장의 `slides.html`(`.slide` 섹션 6개)에 배치해 스킬의 `render.mjs`로 PNG를 만든다. 앱 코드는 건드리지 않는다(코드 동결).

**Tech Stack:** Node 24 + 스킬 스크립트(`capture.mjs`, `render.mjs`, 헤드리스 Chrome), HTML/CSS/SVG, Google Fonts(Hahmlet, IBM Plex Sans KR, Nanum Pen Script), Python(PIL, 점검 스크립트).

**Spec:** `docs/superpowers/specs/2026-09-27-showcase-images-design.md`

## Global Constraints

- 출력 1920×1080 PNG 6장 + `_overview.png`. 위치 `docs/portfolio/showcase/out/`.
- 글꼴: 제목 Hahmlet 600, 본문 IBM Plex Sans KR, 손글씨 Nanum Pen Script. 손글씨 색: 어두운 바탕 위 `#f2c95c`, 흰 캡처 위 `#d8443a`.
- 바탕: 1 `#26272b`+점 격자, 2 `#1d2733`, 3 `#2e2925`+흐린 관리도 선, 4 위 56% `#313944`/아래 `#26272b`, 5 `#342c1a`, 6 `#1b1c1f`.
- 금지: 대회·회사 이름, 모노 글꼴 작은 라벨, 영문 대문자 라벨, 가운뎃점 메타 문구, "A — B" 줄표 라벨, 제목 한 단어 색 강조, 알약 칩, 네온·빛 번짐, 대구형 표어, 결과 파일과 다른 숫자.
- 숫자는 `docs/portfolio/numbers.md`와 같아야 한다.
- LLM 호출 없음(저장된 설명 사용). 앱 코드 수정 없음.

## Review Focus

- 손글씨가 엉뚱한 곳을 가리킴(캡처를 다시 찍어 좌표가 바뀐 경우) → Task 3에서 캡처 좌표를 재서 배치하고 Task 4에서 장마다 확대 확인.
- 글꼴이 안 받아져 대체 글꼴로 렌더(오프라인·CDN 실패) → Task 4에서 `document.fonts.check`로 세 글꼴 로드 확인.
- 휴대폰 틀 안 캡처가 잘려 중요한 내용이 안 보임 → Task 1에서 모바일은 전체 화면 캡처, Task 4에서 눈 확인.
- 문구에 금지 표현이 섞임 → Task 4의 점검 스크립트(금지 문자열 검색).
- 숫자 오타 → Task 4의 점검 스크립트(숫자 목록 대조).

---

### Task 1: 원본 캡처

**Files:**
- Create: `docs/portfolio/showcase/flow-desktop.json`, `docs/portfolio/showcase/flow-mobile.json`
- Output: `docs/portfolio/showcase/shots/*.png`

- [ ] 로컬 앱을 띄운다: `.venv/Scripts/python -m streamlit run streamlit_app.py --server.headless true --server.port 8540` (백그라운드)
- [ ] 데스크톱(1440×900, dpr 2): 가이드 닫기 → 시리즈 11 선택 → 사건 선택 E1 → 요소로 스크롤하며 `d-02-chart`(관리도+규칙 표), `d-03-ai`(AI 설명 카드), `d-04-bars`(패턴별 탐지율), `d-05-secom`, 예시 CSV 붙여넣기 후 `d-06-upload`
- [ ] 모바일(390×844, dpr 2, 전체 화면): `m-hero`(첫 화면), `m-02-chart`, `m-02-rule`, `m-02-pick`(사건 선택 안내), `m-03-check`(체크리스트), `m-03-ai`(AI 설명), `m-04-kpi`
- [ ] 찍은 것을 모두 눈으로 확인(흐림, 가이드·툴바 가림, 빈 화면 없음). 앱 서버 종료

### Task 2: 선화 SVG

**Files:**
- Create: `docs/portfolio/showcase/art/chamber.svg`, `docs/portfolio/showcase/art/wafer.svg`

- [ ] 브레인스토밍 시안 `line-art-v5.html`의 두 `<symbol>`을 독립 SVG 파일로 옮긴다(손떨림 필터 포함, 글자는 fill·font-family 속성으로)
- [ ] 브라우저로 두 파일을 열어 글자가 잘리지 않는지 확인

### Task 3: slides.html 조판

**Files:**
- Create: `docs/portfolio/showcase/slides.html`

- [ ] 템플릿의 기본 골격(`.deck`, `.slide` 1920×1080, keep-all)만 가져오고 스펙 3·4절대로 6장을 새로 쓴다(`id`: cover, rules, explain, verify, realdata, closing)
- [ ] 캡처 위 손글씨(1장 #45 동그라미, 2장 휴대폰 관리도 #45)는 PIL로 캡처 속 점 좌표를 재서 배치
- [ ] 선화는 `<img src="art/…svg">`로 넣는다

### Task 4: 렌더와 점검

**Files:**
- Create: `docs/portfolio/showcase/check.py` (문구·숫자 점검)
- Output: `docs/portfolio/showcase/out/`

- [ ] `node <skill>/scripts/render.mjs docs/portfolio/showcase/slides.html` → 경고 0
- [ ] `check.py`: slides.html 글자에서 금지 문자열(해커톤, SK, 하이닉스, 심사, " · " 메타, 대문자 라벨 패턴) 0건, 숫자 목록(21/21, 14/21, 6건, 103건, 0.48ms, 2.1초, 10.8초, $0.46, 1.3개, 24건, 48개)이 numbers.md에 모두 있는지
- [ ] 세 글꼴 로드 확인, 장마다 전체 크기로 눈 확인, `_overview.png`로 한 틀 반복 없는지 확인. 고치고 다시 렌더

### Task 5: 마무리

- [ ] `.gitignore`에 `.superpowers/brainstorm/` 추가
- [ ] showcase 폴더(원본·html·PNG) 커밋·푸시 (사용자가 미리 승인)
- [ ] HANDOFF·portfolio README 갱신
- [ ] 스킬 `showcase-images` 개선(이번 과정에서 배운 것) — Task 6

### Task 6: 스킬 개선

**Files:**
- Modify: `~/.claude/skills/showcase-images/SKILL.md`, `references/styles.md`, `references/slide-patterns.md`

- [ ] 반영: 시작 시 방향 합의(브레인스토밍 + 표지 시안 비교), 장마다 다른 장면 규칙과 밀착 인화지 검토, 라이트 테마 앱엔 어두운 바탕, 손글씨 주석 기법, AI 티 금지 목록, 사진·생성 이미지 대신 직접 그린 선화(저작권·정확성), 기존 스타일 표에 "annotated"(어두운 바탕 + 손글씨 + 선화) 행
- [ ] 스킬 파일은 저장소 밖이라 커밋 대상 아님. 바꾼 내용을 보고에 요약
