# SPC 설명기 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 규칙 엔진이 증착 막 두께 관리도를 판정하고 LLM이 그 판정을 설명하는 Streamlit 앱, 그리고 규칙과 LLM을 같은 기준으로 잰 검증 리포트를 만든다.

**Architecture:** `spc_explainer` 패키지에 책임별 모듈(설정·패턴·생성기·규칙·채점·LLM 호출·설명·단독 판정·리포트·실험·그림·SECOM)을 둔다. 오프라인 실험 스크립트가 LLM 결과를 `results/*.json`에 캐시하고, `streamlit_app.py`는 캐시를 먼저 보여주며 실시간 호출은 횟수를 제한한다. LLM을 부르는 함수는 호출 함수를 인자로 받으므로 테스트는 가짜 함수로 네트워크 없이 돈다.

**Tech Stack:** Python 3.10, pycontrolcharts 0.1.2, shewhart 0.1.1(테스트 전용), numpy, pandas, OpenAI Python SDK(Chat Completions + JSON 모드), Streamlit 1.64, Plotly, pytest

**Spec:** `docs/superpowers/specs/2026-09-25-spc-explainer-design.md`

## Global Constraints

- Python 3.10 호환. 쓰지 말 것: `tomllib`, f-string 안에서 바깥과 같은 종류의 따옴표 재사용, f-string 중괄호 안의 백슬래시.
- 모든 코드에 한국어 주석 (CLAUDE.md). 테스트 함수 이름은 영어(윈도 콘솔 인코딩 문제 회피), 주석은 한국어.
- 판정은 규칙 엔진, 설명은 LLM. 설명 LLM 입력에는 원시 시계열을 넣지 않는다.
- 모델명·temperature·반복 수·켜고 끄기·실시간 호출 한도는 `spc_explainer/config.py`에서만 정한다.
- 관리한계 고정값: 중심선 100nm, UCL 103nm, LCL 97nm = 이미 안정화된 공정을 감시하는 상황을 가정.
- 점 번호는 코드·JSON·프롬프트·화면 모두 0부터. (반복 회차만 화면에 1부터 표시)
- 추세 = 연속 6점이 계속 증가/감소 = pycontrolcharts `test3_n=5`.
- 테스트는 네트워크를 쓰지 않는다. LLM은 가짜 함수로 바꾼다.
- API 키는 `.env`(로컬)와 Streamlit Secrets(배포)에만. 결과 파일·로그에 남기지 않는다. 커밋 전 `git status`로 `.env`가 없는지 확인.
- 배포 의존성(`requirements.txt`): streamlit, pycontrolcharts==0.1.2, numpy, pandas, plotly, openai, python-dotenv. 개발 의존성(`requirements-dev.txt`): 여기에 pytest, shewhart==0.1.1.
- Streamlit 1.64: `use_container_width`는 폐기 예정이므로 `width="stretch"`를 쓴다.
- 명령은 저장소 루트에서 실행. `.venv/Scripts/python`은 윈도 기준이고, macOS/Linux는 `.venv/bin/python`.
- 태스크마다 커밋 후 `git push origin main` (사용자 상시 허락). 커밋 메시지 끝에 `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` 줄을 붙인다.
- LLM이 틀린 출력은 지우지 않고 `docs/ai_errors.md`에 남긴다 (실험 스크립트가 자동으로 덧붙임).
- 화면의 숫자(n·x̄·σ, 탐지율, 분수, 건수)는 결과 파일에서만 읽는다. Claude Design 시안의 값(50점, 20건, 60건, 63.3% 등)은 쓰지 않는다.
- LLM이 만든 문자열을 HTML에 넣을 때는 `ui_html.esc()`를 거친다 (Task 11-1부터).
- 구현 마감 기준선: 9/26 18시. Task 11-1~11-4는 비교 문서 5절 순서대로 하고, 기준선에 걸리면 그 태스크에서 멈춘다.

## Review Focus

1. 배포 환경의 최신 Streamlit에서 앱이 안 뜨는 경우(폐기된 API 등) → 앱은 예외 없이 그려져야 한다. Task 11의 AppTest 스모크 테스트가 막는다.
2. `results/` 파일이 없거나, 저장된 설명의 입력이 현재 규칙 판정과 다른 경우 → 그래프·규칙 판정은 그대로 보이고 안내·경고만 뜬다. Task 11 `test_app_without_saved_files`.
3. API 키가 없거나 실시간 호출 한도를 다 쓴 경우 → 실시간 버튼만 비활성, 저장된 설명은 그대로 보인다. Task 11 `test_live_button_disabled_without_key`.
4. JSON으로는 읽히지만 타입이 엉뚱한 LLM 출력(최상위 배열, events가 객체, checks가 문자열, 번호가 실수) → 검증기·파서·화면이 예외 없이 형식 위반으로 처리. Task 6 `test_parseable_but_wrong_types_do_not_raise`, Task 7 `test_parse_wrong_types_do_not_raise`.
5. LLM 설명에 `<`·`&`·HTML 태그가 섞인 경우 → `st.html`은 iframe이 아니라서 그대로 넣으면 화면이 깨진다. 글자 그대로 보여야 한다. Task 11-2 `test_llm_text_is_escaped`, Task 11-4 `test_error_cases_come_from_saved_explanations`.

(키 없이 실험 스크립트를 실행하는 경우는 Task 9 `test_script_exits_with_message_without_key`가 막는다.)

## 파일 구조

| 파일 | 책임 | 태스크 |
|---|---|---|
| `requirements.txt`, `requirements-dev.txt`, `pytest.ini` | 의존성, 테스트 설정 | 1 |
| `spc_explainer/config.py` | 모든 설정 (공정 상수, 시나리오, 모델, 한도, 경로) | 1 |
| `spc_explainer/patterns.py` | 패턴 이름·정의 문장, `Event` 자료형, 구간 겹침 | 1 |
| `spc_explainer/generator.py` | 가상 시리즈 + 정답 라벨 | 2 |
| `spc_explainer/rules.py` | pycontrolcharts 래퍼 → `Event` 목록, 근거 규칙 문장 | 3 |
| `spc_explainer/matching.py` | 구간 겹침 채점, 탐지율·오탐 집계 | 4 |
| `spc_explainer/llm_client.py` | OpenAI 호출 한 곳 (JSON 모드, 모델별 temperature) | 5 |
| `spc_explainer/causes.py` | 원인표 | 6 |
| `spc_explainer/explain.py` | 설명 입력·프롬프트·출력 검증기 | 6 |
| `spc_explainer/llm_detect.py` | 단독 판정 프롬프트·파서 | 7 |
| `spc_explainer/report.py` | 지표 → `docs/validation_report.md` | 8 |
| `spc_explainer/experiment.py`, `scripts/run_experiment.py` | 반복 호출·캐시·지표·ai_errors | 9 |
| `data/synthetic/series.json`, `results/*.json`, `docs/validation_report.md`, `docs/ai_errors.md` | 실험 산출물 (커밋) | 10 |
| `spc_explainer/charts.py`, `streamlit_app.py` | 관리도 그림, 화면 | 11 (11-3에서 관리도 스타일 교체) |
| `.streamlit/config.toml`, `spc_explainer/ui_html.py` | 테마, 전역 CSS, 패턴 색·기호·규칙 번호, 머리말 | 11-1 |
| `spc_explainer/ui_steps.py` | STEP 1 규칙 판정·STEP 2 AI 설명 카드, 점검 우선순위 펼치기 | 11-2 |
| `spc_explainer/ui_dashboard.py` | 검증 탭 KPI·탐지율 막대·설명 오답 사례 | 11-4 |
| `README.md`, `docs/HANDOFF.md` | 실행 방법, 인수인계 | 12 |
| `spc_explainer/secom.py`, `scripts/fetch_secom.py`, `data/secom/secom_selected.csv` | SECOM 실데이터 확인 (시간 부족 시 제외) | 13 |

스펙 8절 구조에 `charts.py`를 더했다. 그림 코드를 화면 코드에서 떼어 두 탭이 같이 쓰게 하기 위해서다. Task 11-1~11-4의 `ui_*.py` 세 개는 화면 설계 비교(`docs/design/2026-09-25-ui-comparison.md`)의 절충안 C를 위한 화면 전용 모듈이다(순수 함수라 pytest로 확인).

---

### Task 1: 프로젝트 뼈대, 설정, 패턴 자료형

**Files:**
- Modify: `requirements.txt` (전체 교체)
- Create: `requirements-dev.txt`, `pytest.ini`, `spc_explainer/__init__.py`, `spc_explainer/config.py`, `spc_explainer/patterns.py`
- Test: `tests/test_patterns.py`

**Interfaces:**
- Consumes: 없음
- Produces:
  - `config` 상수: `ROOT`, `SERIES_PATH`, `SECOM_PATH`, `EXPLANATIONS_PATH`, `DETECTIONS_PATH`, `METRICS_PATH`, `REPORT_PATH`, `AI_ERRORS_PATH`, `PROCESS_NAME`, `UNIT`, `CENTER`, `SIGMA`, `UCL`, `LCL`, `TREND_POINTS`, `SHIFT_POINTS`, `SEED`, `N_POINTS`, `SCENARIOS`, `WARMUP`, `MIN_GAP`, `SPIKE_OFFSET`, `TREND_LEN`, `TREND_START_OFFSET`, `TREND_TOTAL`, `SHIFT_LEN`, `SHIFT_MEAN_OFFSET`, `EXPLAIN_MODEL`, `DETECT_MODELS`, `MAX_WORKERS`, `API_MAX_RETRIES`, `API_TIMEOUT_S`, `LIVE_CALLS_PER_SESSION`, `LIVE_CALLS_PER_DAY`, `SECOM_URL`, `SECOM_PHASE1_N`, `SECOM_N_SENSORS`, `SECOM_MIN_UNIQUE`, `SECOM_MAX_ABS_SKEW`
  - 모델 설정 dict 형태: `{"name": str, "temperature": float | None, "repeats": int}` (+ 단독 판정은 `"enabled": bool`)
  - `patterns.PATTERNS: tuple[str, ...]`, `KOREAN: dict[str, str]`, `FROM_KOREAN: dict[str, str]`
  - `patterns.Event(pattern: str, start: int, end: int, direction: str | None = None)` — frozen dataclass, `.to_dict() -> dict`, `Event.from_dict(d) -> Event`
  - `patterns.overlaps(a: Event, b: Event) -> bool`
  - `patterns.definitions_text(center=CENTER, ucl=UCL, lcl=LCL) -> str`

- [ ] **Step 1: 가상환경과 의존성 파일 만들기**

Create `requirements.txt`:

```text
# 배포(Streamlit Community Cloud)용 의존성
streamlit
pycontrolcharts==0.1.2
numpy
pandas
plotly
openai
python-dotenv
```

Create `requirements-dev.txt`:

```text
# 개발·테스트 전용 의존성 (배포에는 들어가지 않는다)
-r requirements.txt
pytest
shewhart==0.1.1
```

Create `pytest.ini`:

```ini
[pytest]
pythonpath = .
testpaths = tests
```

Run:

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -q -r requirements-dev.txt
.venv/Scripts/python -c "import pycontrolcharts, shewhart, streamlit, plotly, openai; print(streamlit.__version__)"
```

Expected: 버전 번호 출력 (1.64 이상), 오류 없음.

- [ ] **Step 2: 실패하는 테스트 작성**

Create `tests/test_patterns.py`:

```python
# 패턴 자료형과 정의 문장 확인
from spc_explainer.patterns import Event, definitions_text, overlaps


def test_overlap_needs_only_one_shared_point():
    assert overlaps(Event("trend", 10, 17), Event("trend", 17, 20))
    assert not overlaps(Event("trend", 10, 17), Event("trend", 18, 20))


def test_event_dict_roundtrip():
    ev = Event("shift", 40, 49, "down")
    assert Event.from_dict(ev.to_dict()) == ev
    assert Event.from_dict({"pattern": "spike", "start": 3, "end": 3}) == Event("spike", 3, 3)


def test_definitions_use_rule_numbers():
    text = definitions_text()
    assert "UCL(103)" in text and "LCL(97)" in text and "중심선(100)" in text
    assert "6개 이상" in text and "5회 이상" in text and "9개 이상" in text
```

- [ ] **Step 3: 실패 확인**

Run: `.venv/Scripts/python -m pytest tests/test_patterns.py -v`
Expected: 수집 오류 `ModuleNotFoundError: No module named 'spc_explainer'`

- [ ] **Step 4: 패키지·설정·패턴 구현**

Create `spc_explainer/__init__.py`:

```python
# SPC 설명기: 판정은 규칙 엔진, 설명은 LLM
```

Create `spc_explainer/config.py`:

```python
# 모든 설정을 모아 두는 곳. 모델명·호출 한도·실험 크기는 여기서만 바꾼다.
from pathlib import Path

# ── 경로 ──
ROOT = Path(__file__).resolve().parent.parent
SERIES_PATH = ROOT / "data" / "synthetic" / "series.json"
SECOM_PATH = ROOT / "data" / "secom" / "secom_selected.csv"
EXPLANATIONS_PATH = ROOT / "results" / "explanations.json"
DETECTIONS_PATH = ROOT / "results" / "llm_detections.json"
METRICS_PATH = ROOT / "results" / "metrics.json"
REPORT_PATH = ROOT / "docs" / "validation_report.md"
AI_ERRORS_PATH = ROOT / "docs" / "ai_errors.md"

# ── 공정: 증착 막 두께 ──
# 관리한계 고정값 사용 = 이미 안정화된 공정을 감시하는 상황(Phase II)을 가정한다.
PROCESS_NAME = "증착 막 두께"
UNIT = "nm"
CENTER = 100.0
SIGMA = 1.0
UCL = CENTER + 3 * SIGMA  # 103nm
LCL = CENTER - 3 * SIGMA  # 97nm

# ── 판정 규칙 ──
TREND_POINTS = 6  # 추세: 연속 6점이 계속 증가/감소 (= 5회 연속 증가)
SHIFT_POINTS = 9  # 치우침: 연속 9점이 중심선 한쪽

# ── 가상 데이터 ──
SEED = 20260925
N_POINTS = 100
# 시리즈별로 심을 이상. 0~4번은 정상(이상 없음) → 오탐을 따로 잰다.
SCENARIOS = [
    [], [], [], [], [],
    ["spike"], ["spike"], ["spike"],
    ["trend"], ["trend"], ["trend"],
    ["shift"], ["shift"], ["shift"],
    ["spike", "trend"], ["spike", "trend"],
    ["spike", "shift"], ["spike", "shift"],
    ["trend", "shift"], ["trend", "shift"],
]
WARMUP = 10  # 앞 10점은 항상 정상
MIN_GAP = 10  # 이상끼리 최소 간격(점)
SPIKE_OFFSET = (3.5, 5.0)  # 급변: 중심에서 떨어진 거리(σ 배수)
TREND_LEN = 8  # 추세: 8점 엄격한 단조
TREND_START_OFFSET = (1.0, 1.5)  # 추세 시작점의 중심 반대쪽 거리(σ 배수)
TREND_TOTAL = (2.5, 3.5)  # 추세 전체 변화량(σ 배수)
SHIFT_LEN = 10  # 치우침: 10점 연속 한쪽
SHIFT_MEAN_OFFSET = 1.5  # 치우침 평균 이동(σ 배수)

# ── LLM (모델명은 여기서만 관리) ──
# temperature가 None이면 요청에 넣지 않는다(모델 기본값). gpt-6-sol은 0을 거부한다 (2026-09-25 확인).
EXPLAIN_MODEL = {"name": "gpt-4.1-mini", "temperature": 0, "repeats": 3}
DETECT_MODELS = [
    {"name": "gpt-4.1-mini", "temperature": 0, "repeats": 3, "enabled": True},
    {"name": "gpt-6-sol", "temperature": None, "repeats": 3, "enabled": True},
    # 비교 실험 1회만. OpenAI 대시보드에서 이 모델을 허용한 뒤 True로 바꾼다.
    {"name": "gpt-6-astra", "temperature": None, "repeats": 1, "enabled": False},
]
MAX_WORKERS = 6  # 실험 때 동시 호출 수
API_MAX_RETRIES = 3  # 네트워크·429·5xx 재시도 (SDK가 수행)
API_TIMEOUT_S = 180

# ── 배포 앱의 실시간 설명 한도 ──
LIVE_CALLS_PER_SESSION = 3
LIVE_CALLS_PER_DAY = 50

# ── SECOM 실데이터 ──
SECOM_URL = "https://archive.ics.uci.edu/static/public/179/secom.zip"
SECOM_PHASE1_N = 500  # 시간순 앞 500점으로 한계 추정
SECOM_N_SENSORS = 2
SECOM_MIN_UNIQUE = 200  # Phase I 고유값 개수 하한 (연속형 센서만)
SECOM_MAX_ABS_SKEW = 0.5  # Phase I 왜도 절댓값 상한
```

Create `spc_explainer/patterns.py`:

```python
# 패턴 이름·정의 문장과 판정 사건(Event) 자료형. 규칙 엔진, LLM, 채점이 같이 쓴다.
from dataclasses import asdict, dataclass

from . import config

PATTERNS = ("spike", "trend", "shift")
KOREAN = {"spike": "급변", "trend": "추세", "shift": "치우침"}
FROM_KOREAN = {v: k for k, v in KOREAN.items()}


@dataclass(frozen=True)
class Event:
    """판정 사건 또는 심은 이상 하나. 점 번호는 0부터, 구간은 양끝 포함."""

    pattern: str  # "spike" | "trend" | "shift"
    start: int
    end: int
    direction: str | None = None  # "up" | "down". LLM 단독 판정은 방향을 주지 않으므로 None

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "Event":
        return Event(d["pattern"], int(d["start"]), int(d["end"]), d.get("direction"))


def overlaps(a: Event, b: Event) -> bool:
    """두 구간이 한 점이라도 겹치면 True (허용 오차 없음)."""
    return a.start <= b.end and b.start <= a.end


def definitions_text(center: float = config.CENTER, ucl: float = config.UCL, lcl: float = config.LCL) -> str:
    """3패턴 정의 문장. 규칙 엔진 설정과 같은 정의를 LLM에게도 준다."""
    t, s = config.TREND_POINTS, config.SHIFT_POINTS
    return (
        f"1. 급변: 값이 UCL({ucl:g}) 초과 또는 LCL({lcl:g}) 미만인 점.\n"
        f"2. 추세: 연속된 {t}개 이상의 점이 매번 직전 점보다 커지거나(상승) 매번 작아짐(하강). "
        f"즉 {t - 1}회 이상 연속 증가 또는 감소.\n"
        f"3. 치우침: 연속된 {s}개 이상의 점이 모두 중심선({center:g})보다 위이거나 모두 아래."
    )
```

- [ ] **Step 5: 통과 확인**

Run: `.venv/Scripts/python -m pytest tests/test_patterns.py -v`
Expected: 3 passed

- [ ] **Step 6: 커밋**

```bash
git status --short   # .env가 없어야 함
git add requirements.txt requirements-dev.txt pytest.ini spc_explainer/__init__.py spc_explainer/config.py spc_explainer/patterns.py tests/test_patterns.py
git commit -m "feat: 프로젝트 뼈대, 설정, 패턴 자료형" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
git push origin main
```

---

### Task 2: 가상 데이터 생성기

**Files:**
- Create: `spc_explainer/generator.py`
- Test: `tests/test_generator.py`

**Interfaces:**
- Consumes: `config`(Task 1), `patterns.Event`
- Produces:
  - `generator.generate_dataset(seed: int = config.SEED) -> dict` — `{"seed", "center", "ucl", "lcl", "series": [{"id": int, "values": list[float], "anomalies": list[dict]}]}`. `anomalies`의 각 항목은 `Event.to_dict()`
  - `generator.save_dataset(dataset: dict, path: Path = config.SERIES_PATH) -> None`
  - `generator.load_dataset(path: Path = config.SERIES_PATH) -> dict`
  - `generator.truth_events(series: dict) -> list[Event]`

- [ ] **Step 1: 실패하는 테스트 작성**

Create `tests/test_generator.py`:

```python
# 생성기가 규칙 정의를 만족하는 이상을 심는지, 시드가 재현되는지 확인
from spc_explainer import config
from spc_explainer.generator import generate_dataset, load_dataset, save_dataset, truth_events

SEEDS = (config.SEED, 1, 2, 3)  # 기본 시드 말고 다른 시드에서도 성립해야 한다


def test_same_seed_same_data():
    assert generate_dataset(1) == generate_dataset(1)
    assert generate_dataset(1) != generate_dataset(2)


def test_scenario_counts():
    ds = generate_dataset()
    assert len(ds["series"]) == 20
    assert all(len(s["values"]) == 100 for s in ds["series"])
    assert [s["anomalies"] for s in ds["series"][:5]] == [[]] * 5  # 정상 시리즈 5개
    kinds = [a["pattern"] for s in ds["series"] for a in s["anomalies"]]
    assert {p: kinds.count(p) for p in ("spike", "trend", "shift")} == {"spike": 7, "trend": 7, "shift": 7}


def test_injected_anomalies_satisfy_rule_definitions():
    for seed in SEEDS:
        for s in generate_dataset(seed)["series"]:
            x = s["values"]
            for ev in truth_events(s):
                seg = x[ev.start:ev.end + 1]
                up = ev.direction == "up"
                if ev.pattern == "spike":
                    assert len(seg) == 1
                    assert seg[0] > config.UCL if up else seg[0] < config.LCL
                elif ev.pattern == "trend":
                    diffs = [b - a for a, b in zip(seg, seg[1:])]
                    assert len(seg) == config.TREND_LEN
                    assert all(d > 0 for d in diffs) if up else all(d < 0 for d in diffs)
                    assert all(config.LCL < v < config.UCL for v in seg)
                else:
                    assert len(seg) == config.SHIFT_LEN
                    if up:
                        assert all(config.CENTER < v < config.UCL for v in seg)
                    else:
                        assert all(config.LCL < v < config.CENTER for v in seg)


def test_anomalies_skip_warmup_and_keep_gap():
    for seed in SEEDS:
        for s in generate_dataset(seed)["series"]:
            evs = sorted(truth_events(s), key=lambda e: e.start)
            assert all(e.start >= config.WARMUP for e in evs)
            assert all(b.start - a.end - 1 >= config.MIN_GAP for a, b in zip(evs, evs[1:]))


def test_values_have_two_decimals():
    for s in generate_dataset()["series"]:
        assert all(round(v, 2) == v for v in s["values"])


def test_save_and_load_roundtrip(tmp_path):
    ds = generate_dataset()
    path = tmp_path / "sub" / "series.json"
    save_dataset(ds, path)
    assert load_dataset(path) == ds
```

- [ ] **Step 2: 실패 확인**

Run: `.venv/Scripts/python -m pytest tests/test_generator.py -v`
Expected: 수집 오류 `ModuleNotFoundError: No module named 'spc_explainer.generator'`

- [ ] **Step 3: 구현**

Create `spc_explainer/generator.py`:

```python
# 가상 시리즈 생성기: 정상 잡음 위에 3패턴을 규칙 정의를 만족하도록 심고, 위치를 정답 라벨로 남긴다.
import json
from pathlib import Path

import numpy as np

from . import config
from .patterns import Event

LENGTHS = {"spike": 1, "trend": config.TREND_LEN, "shift": config.SHIFT_LEN}


def _place(rng: np.random.Generator, kinds: list[str], n: int) -> list[tuple[int, int, str]]:
    """이상들의 구간 [(start, end, kind)]을 무작위로 정한다. 앞 WARMUP점은 비우고 이상끼리 MIN_GAP점 이상 띄운다."""
    for _ in range(10_000):
        spans = []
        for kind in kinds:
            start = int(rng.integers(config.WARMUP, n - LENGTHS[kind] + 1))
            spans.append((start, start + LENGTHS[kind] - 1, kind))
        spans.sort()
        if all(b[0] - a[1] - 1 >= config.MIN_GAP for a, b in zip(spans, spans[1:])):
            return spans
    raise RuntimeError("이상 위치를 정하지 못했습니다")


def _inject(rng: np.random.Generator, x: np.ndarray, kind: str, start: int, sign: int) -> None:
    """x[start:]에 이상 하나를 심는다. sign=+1이면 위/상승, -1이면 아래/하강. 값은 소수 둘째 자리."""
    c, sd = config.CENTER, config.SIGMA
    if kind == "spike":
        x[start] = round(c + sign * sd * rng.uniform(*config.SPIKE_OFFSET), 2)
    elif kind == "trend":
        base = c - sign * sd * rng.uniform(*config.TREND_START_OFFSET)
        total = sd * rng.uniform(*config.TREND_TOTAL)
        weights = rng.uniform(0.5, 1.5, config.TREND_LEN - 1)
        steps = total * weights / weights.sum()  # 증가분이 모두 양수(최소 약 0.13) → 반올림해도 엄격한 단조
        seg = base + sign * np.concatenate([[0.0], np.cumsum(steps)])
        x[start:start + config.TREND_LEN] = np.round(seg, 2)
    elif kind == "shift":
        lo, hi = (c, config.UCL) if sign > 0 else (config.LCL, c)
        for i in range(start, start + config.SHIFT_LEN):
            while True:  # 중심선 한쪽이면서 한계 안인 값만 쓴다 (기각 표집)
                v = round(float(rng.normal(c + sign * sd * config.SHIFT_MEAN_OFFSET, sd)), 2)
                if lo < v < hi:
                    x[i] = v
                    break
    else:
        raise ValueError(f"알 수 없는 패턴: {kind}")


def generate_series(series_id: int, kinds: list[str], rng: np.random.Generator) -> dict:
    """시리즈 하나: 정상 잡음 N(CENTER, SIGMA²) 위에 kinds의 이상을 심는다."""
    x = np.round(rng.normal(config.CENTER, config.SIGMA, config.N_POINTS), 2)
    anomalies = []
    for start, end, kind in (_place(rng, kinds, config.N_POINTS) if kinds else []):
        sign = 1 if rng.random() < 0.5 else -1
        _inject(rng, x, kind, start, sign)
        anomalies.append(Event(kind, start, end, "up" if sign > 0 else "down").to_dict())
    return {"id": series_id, "values": [float(v) for v in x], "anomalies": anomalies}


def generate_dataset(seed: int = config.SEED) -> dict:
    """SCENARIOS 순서대로 전체 시리즈를 만든다. 같은 시드면 항상 같은 결과."""
    rng = np.random.default_rng(seed)
    return {
        "seed": seed,
        "center": config.CENTER,
        "ucl": config.UCL,
        "lcl": config.LCL,
        "series": [generate_series(i, kinds, rng) for i, kinds in enumerate(config.SCENARIOS)],
    }


def save_dataset(dataset: dict, path: Path = config.SERIES_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dataset, ensure_ascii=False, indent=1), encoding="utf-8")


def load_dataset(path: Path = config.SERIES_PATH) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def truth_events(series: dict) -> list[Event]:
    """시리즈에 심은 이상(정답)을 Event 목록으로."""
    return [Event.from_dict(a) for a in series["anomalies"]]
```

- [ ] **Step 4: 통과 확인**

Run: `.venv/Scripts/python -m pytest tests/test_generator.py -v`
Expected: 6 passed

- [ ] **Step 5: 커밋**

```bash
git add spc_explainer/generator.py tests/test_generator.py
git commit -m "feat: 정답 라벨을 남기는 가상 데이터 생성기" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
git push origin main
```

---

### Task 3: 규칙 판정과 교차 검증

**Files:**
- Create: `spc_explainer/rules.py`
- Test: `tests/test_rules.py`, `tests/test_crosscheck.py`

**Interfaces:**
- Consumes: `config`, `patterns.Event`, `patterns.overlaps`, `generator.generate_dataset`, `generator.truth_events`
- Produces:
  - `rules.detect(values, center=config.CENTER, ucl=config.UCL, lcl=config.LCL) -> list[Event]` — 시작 번호 순, 방향 포함
  - `rules.describe(ev: Event, values, ucl=config.UCL, lcl=config.LCL) -> str` — 근거 규칙 문장
  - `rules._runs(idx: list[int]) -> list[tuple[int, int]]` — 연속 번호 묶기 (교차 검증 테스트도 사용)

- [ ] **Step 1: 실패하는 테스트 작성**

Create `tests/test_rules.py`:

```python
# 규칙 엔진 래퍼: type 코드 매핑, 사건 묶기, 추세 정의(6점) 확인
from spc_explainer import config
from spc_explainer.generator import generate_dataset, truth_events
from spc_explainer.patterns import Event, overlaps
from spc_explainer.rules import _runs, describe, detect

# 중심선 위아래를 번갈아 오가는 평탄한 기본 시리즈 (그 자체로는 어떤 규칙에도 안 걸림)
BASE = [100.2, 99.8] * 30


def test_runs_groups_consecutive_indices():
    assert _runs([1, 2, 3, 7, 9, 10]) == [(1, 3), (7, 7), (9, 10)]
    assert _runs([]) == []


def test_flat_series_has_no_events():
    assert detect(BASE) == []


def test_spike_up_and_down():
    x = list(BASE)
    x[5], x[20] = 104.2, 96.1
    assert detect(x) == [Event("spike", 5, 5, "up"), Event("spike", 20, 20, "down")]


def test_trend_six_points_detected_five_not():
    x = list(BASE)
    x[10:16] = [99.0, 99.4, 99.8, 100.2, 100.6, 101.0]  # 6점 상승
    assert detect(x) == [Event("trend", 10, 15, "up")]
    y = list(BASE)
    y[10:15] = [99.0, 99.4, 99.8, 100.2, 100.6]  # 5점 상승 → 규칙 미달
    assert detect(y) == []


def test_trend_down_covers_whole_run():
    x = list(BASE)
    x[20:28] = [102.0 - 0.5 * i for i in range(8)]
    assert detect(x) == [Event("trend", 20, 27, "down")]


def test_shift_nine_points_below():
    x = list(BASE)
    x[40:50] = [99.0, 99.2] * 5  # 10점 중심선 아래 (39번도 99.8이라 런은 39~49)
    assert detect(x) == [Event("shift", 39, 49, "down")]


def test_rules_find_every_injected_anomaly():
    for seed in (config.SEED, 1, 2, 3):
        for s in generate_dataset(seed)["series"]:
            found = detect(s["values"])
            for t in truth_events(s):
                assert any(f.pattern == t.pattern and overlaps(f, t) for f in found), (seed, s["id"], t)


def test_describe_sentences():
    x = list(BASE)
    x[5] = 104.2
    assert describe(Event("spike", 5, 5, "up"), x) == "관리한계 밖 1점 (5번 104.20nm, UCL 103nm 초과)"
    x[20:26] = [99.0, 99.4, 99.8, 100.2, 100.6, 101.0]
    assert describe(Event("trend", 20, 25, "up"), x) == "6점 연속 상승 (20~25번, 99.00→101.00nm)"
    assert describe(Event("shift", 40, 49, "down"), [99.0] * 60) == "10점 연속 중심선 아래 (40~49번, 평균 99.00nm)"
```

Create `tests/test_crosscheck.py`:

```python
# 교차 검증: 독립 구현(shewhart)으로 같은 데이터를 판정해 점 단위로 일치하는지 본다
import numpy as np
import pytest

from spc_explainer import config
from spc_explainer.generator import generate_dataset
from spc_explainer.rules import detect

shewhart = pytest.importorskip("shewhart")  # 개발 전용 의존성

RULE_MAP = {"nelson_1": "spike", "nelson_2": "shift", "nelson_3": "trend"}


def shewhart_points(values) -> set[tuple[str, int]]:
    """shewhart가 표시한 (패턴, 점 번호) 집합. 3패턴 외 규칙은 버린다."""
    limits = {"i_center": config.CENTER, "sigma_within": config.SIGMA, "mr_center": config.SIGMA * 1.128}
    result = shewhart.imr(np.asarray(values, dtype=float), rules="nelson", limits=limits)
    return {(RULE_MAP[s.rule], int(i)) for s in result.signals if s.rule in RULE_MAP for i in s.points}


def our_points(values) -> set[tuple[str, int]]:
    return {(e.pattern, i) for e in detect(values) for i in range(e.start, e.end + 1)}


@pytest.mark.parametrize("seed", [config.SEED, 1, 2])
def test_same_points_as_shewhart(seed):
    for s in generate_dataset(seed)["series"]:
        assert our_points(s["values"]) == shewhart_points(s["values"]), f"seed {seed} series {s['id']}"
```

- [ ] **Step 2: 실패 확인**

Run: `.venv/Scripts/python -m pytest tests/test_rules.py tests/test_crosscheck.py -v`
Expected: 수집 오류 `ModuleNotFoundError: No module named 'spc_explainer.rules'`

- [ ] **Step 3: 구현**

Create `spc_explainer/rules.py`:

```python
# 규칙 판정: pycontrolcharts로 3패턴만 검사하고, 점별 위반을 사건(Event)으로 묶는다.
import pycontrolcharts as pcc

from . import config
from .patterns import Event

# pycontrolcharts 위반 type 코드 → (패턴, 방향)
TYPE_MAP = {
    1: ("spike", "up"), 2: ("spike", "down"),
    3: ("shift", "up"), 4: ("shift", "down"),
    5: ("trend", "up"), 6: ("trend", "down"),
}

# test3_n은 '점 개수'가 아니라 '증가 횟수'다. 연속 6점 = 증가 5회 → TREND_POINTS - 1.
# test5·test6(2σ·1σ 구역 규칙)은 이번 범위 밖이라 끈다.
RUN_CONFIG = pcc.RunTestConfig(
    test1=True, test2=True, test3=True, test5=False, test6=False,
    test2_n=config.SHIFT_POINTS, test3_n=config.TREND_POINTS - 1,
)


def _runs(idx: list[int]) -> list[tuple[int, int]]:
    """정렬된 점 번호를 연속 구간 [(start, end), ...]으로 묶는다."""
    runs: list[tuple[int, int]] = []
    for i in idx:
        if runs and i == runs[-1][1] + 1:
            runs[-1] = (runs[-1][0], i)
        else:
            runs.append((i, i))
    return runs


def detect(values, center: float = config.CENTER, ucl: float = config.UCL, lcl: float = config.LCL) -> list[Event]:
    """values를 고정 관리한계로 판정해 사건 목록을 돌려준다 (시작 번호 순)."""
    df = pcc.run_tests_with_custom_limits(
        [float(v) for v in values],
        limits=pcc.CustomLimits(center_line=center, ucl=ucl, lcl=lcl),
        run_tests=RUN_CONFIG,
    )
    flagged: dict[tuple[str, str], set[int]] = {}
    for i, violations in enumerate(df["violations"]):
        for v in violations or []:
            if v["type"] in TYPE_MAP:
                flagged.setdefault(TYPE_MAP[v["type"]], set()).add(i)
    events = []
    for (pattern, direction), idx in flagged.items():
        for start, end in _runs(sorted(idx)):
            if pattern == "trend":
                start = max(start - 1, 0)  # 라이브러리는 둘째 점부터 표시 → 런의 첫 점을 포함시킨다
            events.append(Event(pattern, start, end, direction))
    return sorted(events, key=lambda e: (e.start, e.pattern))


def describe(ev: Event, values, ucl: float = config.UCL, lcl: float = config.LCL) -> str:
    """사건의 근거 규칙 문장 (설명 LLM 입력과 화면 표시용)."""
    seg = [float(v) for v in values[ev.start:ev.end + 1]]
    n, u = len(seg), config.UNIT
    span = f"{ev.start}번" if n == 1 else f"{ev.start}~{ev.end}번"
    if ev.pattern == "spike":
        limit = f"UCL {ucl:g}{u} 초과" if ev.direction == "up" else f"LCL {lcl:g}{u} 미만"
        vals = ", ".join(f"{v:.2f}" for v in seg)
        return f"관리한계 밖 {n}점 ({span} {vals}{u}, {limit})"
    if ev.pattern == "trend":
        word = "상승" if ev.direction == "up" else "하강"
        return f"{n}점 연속 {word} ({span}, {seg[0]:.2f}→{seg[-1]:.2f}{u})"
    side = "위" if ev.direction == "up" else "아래"
    return f"{n}점 연속 중심선 {side} ({span}, 평균 {sum(seg) / n:.2f}{u})"
```

- [ ] **Step 4: 통과 확인**

Run: `.venv/Scripts/python -m pytest tests/test_rules.py tests/test_crosscheck.py -v`
Expected: 11 passed (test_rules 8 + test_crosscheck 3)

교차 검증이 실패하면 규칙을 고치기 전에 어느 점에서 다른지 출력해 원인(동점·중심선 위 값 처리 차이 등)을 확인하고, 사용자에게 보고한다.

- [ ] **Step 5: 커밋**

```bash
git add spc_explainer/rules.py tests/test_rules.py tests/test_crosscheck.py
git commit -m "feat: pycontrolcharts 규칙 판정 래퍼와 shewhart 교차 검증" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
git push origin main
```

---

### Task 4: 채점 (규칙·LLM 공통)

**Files:**
- Create: `spc_explainer/matching.py`
- Test: `tests/test_matching.py`

**Interfaces:**
- Consumes: `patterns.PATTERNS`, `patterns.Event`, `patterns.overlaps`
- Produces:
  - `matching.classify(truth: list[Event], found: list[Event]) -> tuple[list[bool], list[str]]` — (정답별 탐지 여부, 탐지 사건별 `"hit" | "confusion" | "false"`)
  - `matching.summarize(truths: list[list[Event]], founds: list[list[Event]]) -> dict` — 형태:
    `{"per_pattern": {p: {"injected": int, "detected": int}}, "injected": int, "detected": int, "rate": float | None, "normal": {"series": int, "alarmed_series": int, "false_events": {p: int}}, "anomalous": {"false_events": {p: int}, "confusions": int}, "false_list": [{"series": int, "pattern", "start", "end", "direction"}]}`
    (`series`는 목록 안의 위치 = 시리즈 번호)

- [ ] **Step 1: 실패하는 테스트 작성**

Create `tests/test_matching.py`:

```python
# 구간 겹침 채점: 정탐·패턴 혼동·오탐 분류와 집계
from spc_explainer.matching import classify, summarize
from spc_explainer.patterns import Event

T = Event("trend", 10, 17, "up")
S = Event("shift", 40, 49, "down")


def test_classify_hit_confusion_false():
    found = [Event("trend", 16, 20), Event("spike", 45, 45), Event("spike", 80, 80)]
    detected, kinds = classify([T, S], found)
    assert detected == [True, False]  # 치우침은 같은 패턴으로 찾지 못함
    assert kinds == ["hit", "confusion", "false"]


def test_classify_no_overlap_is_miss_and_false():
    detected, kinds = classify([T], [Event("trend", 18, 25)])
    assert detected == [False] and kinds == ["false"]


def test_summarize_counts_normal_and_anomalous_separately():
    truths = [[], [], [T, S]]
    founds = [[Event("spike", 3, 3)], [], [Event("trend", 12, 15), Event("shift", 60, 70)]]
    m = summarize(truths, founds)
    assert m["injected"] == 2 and m["detected"] == 1 and m["rate"] == 0.5
    assert m["per_pattern"]["trend"] == {"injected": 1, "detected": 1}
    assert m["per_pattern"]["shift"] == {"injected": 1, "detected": 0}
    assert m["normal"] == {"series": 2, "alarmed_series": 1, "false_events": {"spike": 1, "trend": 0, "shift": 0}}
    assert m["anomalous"] == {"false_events": {"spike": 0, "trend": 0, "shift": 1}, "confusions": 0}
    assert m["false_list"] == [
        {"series": 0, "pattern": "spike", "start": 3, "end": 3, "direction": None},
        {"series": 2, "pattern": "shift", "start": 60, "end": 70, "direction": None},
    ]


def test_summarize_without_injections_has_no_rate():
    assert summarize([[]], [[]])["rate"] is None
```

- [ ] **Step 2: 실패 확인**

Run: `.venv/Scripts/python -m pytest tests/test_matching.py -v`
Expected: 수집 오류 `ModuleNotFoundError: No module named 'spc_explainer.matching'`

- [ ] **Step 3: 구현**

Create `spc_explainer/matching.py`:

```python
# 채점: 정답 이상과 탐지 사건을 구간 겹침으로 맞춰 본다 (규칙·LLM 공통 기준)
from .patterns import PATTERNS, Event, overlaps


def classify(truth: list[Event], found: list[Event]) -> tuple[list[bool], list[str]]:
    """(정답별 탐지 여부, 탐지 사건별 분류). 분류: "hit" 정탐 | "confusion" 패턴 혼동 | "false" 오탐."""
    detected = [any(f.pattern == t.pattern and overlaps(f, t) for f in found) for t in truth]
    kinds = []
    for f in found:
        if any(f.pattern == t.pattern and overlaps(f, t) for t in truth):
            kinds.append("hit")
        elif any(overlaps(f, t) for t in truth):
            kinds.append("confusion")
        else:
            kinds.append("false")
    return detected, kinds


def summarize(truths: list[list[Event]], founds: list[list[Event]]) -> dict:
    """전체 시리즈 채점 요약. truths[i]·founds[i]는 i번 시리즈의 정답·탐지 사건."""
    per_pattern = {p: {"injected": 0, "detected": 0} for p in PATTERNS}
    normal = {"series": 0, "alarmed_series": 0, "false_events": dict.fromkeys(PATTERNS, 0)}
    anomalous = {"false_events": dict.fromkeys(PATTERNS, 0), "confusions": 0}
    false_list = []
    for sid, (truth, found) in enumerate(zip(truths, founds)):
        detected, kinds = classify(truth, found)
        for t, hit in zip(truth, detected):
            per_pattern[t.pattern]["injected"] += 1
            per_pattern[t.pattern]["detected"] += int(hit)
        if not truth:
            normal["series"] += 1
            normal["alarmed_series"] += int(bool(found))
        for f, kind in zip(found, kinds):
            if kind == "false":
                (normal if not truth else anomalous)["false_events"][f.pattern] += 1
                false_list.append({"series": sid, **f.to_dict()})
            elif kind == "confusion":
                anomalous["confusions"] += 1
    injected = sum(v["injected"] for v in per_pattern.values())
    detected_total = sum(v["detected"] for v in per_pattern.values())
    return {
        "per_pattern": per_pattern,
        "injected": injected,
        "detected": detected_total,
        "rate": detected_total / injected if injected else None,
        "normal": normal,
        "anomalous": anomalous,
        "false_list": false_list,
    }
```

- [ ] **Step 4: 통과 확인**

Run: `.venv/Scripts/python -m pytest tests/test_matching.py -v`
Expected: 4 passed

- [ ] **Step 5: 커밋**

```bash
git add spc_explainer/matching.py tests/test_matching.py
git commit -m "feat: 구간 겹침 채점과 오탐 집계" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
git push origin main
```

---

### Task 5: LLM 호출부

**Files:**
- Create: `spc_explainer/llm_client.py`
- Test: `tests/test_llm_client.py`

**Interfaces:**
- Consumes: `config.ROOT`, `config.API_MAX_RETRIES`, `config.API_TIMEOUT_S`
- Produces:
  - `llm_client.LLMReply(text: str | None, error: str | None, latency_s: float, usage: dict | None)` — dataclass
  - `llm_client.call_json(model: dict, system: str, user: str) -> LLMReply` — 예외를 던지지 않고 `error`에 담는다
  - `llm_client.get_api_key() -> str | None`
  - `llm_client._get_client()` — 테스트에서 가짜로 바꿔 끼우는 지점

- [ ] **Step 1: 실패하는 테스트 작성**

Create `tests/test_llm_client.py`:

```python
# 네트워크 없이 호출부의 요청 구성과 오류 처리만 확인
from types import SimpleNamespace

from spc_explainer import llm_client


class FakeCompletions:
    def __init__(self, fail: bool = False):
        self.kwargs, self.fail = None, fail

    def create(self, **kwargs):
        self.kwargs = kwargs
        if self.fail:
            raise RuntimeError("boom")
        message = SimpleNamespace(content='{"ok": true}')
        usage = SimpleNamespace(prompt_tokens=10, completion_tokens=3)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)], usage=usage)


def use_fake(monkeypatch, fail: bool = False) -> FakeCompletions:
    completions = FakeCompletions(fail)
    fake_client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    monkeypatch.setattr(llm_client, "_get_client", lambda: fake_client)
    return completions


def test_json_mode_and_temperature_zero(monkeypatch):
    completions = use_fake(monkeypatch)
    r = llm_client.call_json({"name": "gpt-4.1-mini", "temperature": 0}, "sys", "user")
    assert r.text == '{"ok": true}' and r.error is None
    assert r.usage == {"prompt_tokens": 10, "completion_tokens": 3}
    assert completions.kwargs["model"] == "gpt-4.1-mini"
    assert completions.kwargs["response_format"] == {"type": "json_object"}
    assert completions.kwargs["temperature"] == 0
    assert completions.kwargs["messages"] == [{"role": "system", "content": "sys"}, {"role": "user", "content": "user"}]


def test_temperature_none_is_not_sent(monkeypatch):
    completions = use_fake(monkeypatch)
    llm_client.call_json({"name": "gpt-6-sol", "temperature": None}, "s", "u")
    assert "temperature" not in completions.kwargs


def test_call_error_is_returned_not_raised(monkeypatch):
    use_fake(monkeypatch, fail=True)
    r = llm_client.call_json({"name": "x", "temperature": None}, "s", "u")
    assert r.text is None and r.error == "RuntimeError: boom" and r.usage is None
```

- [ ] **Step 2: 실패 확인**

Run: `.venv/Scripts/python -m pytest tests/test_llm_client.py -v`
Expected: 수집 오류 `ModuleNotFoundError: No module named 'spc_explainer.llm_client'`

- [ ] **Step 3: 구현**

Create `spc_explainer/llm_client.py`:

```python
# OpenAI 호출을 한 곳에 모은다. JSON 모드로 부르고 원문·소요 시간·토큰 수를 돌려준다.
import os
import time
from dataclasses import dataclass

from . import config


@dataclass
class LLMReply:
    text: str | None  # 모델 원문. 호출 실패면 None
    error: str | None  # 호출 오류(네트워크·권한·모델 없음 등). 성공이면 None
    latency_s: float
    usage: dict | None


def get_api_key() -> str | None:
    """로컬은 .env, 배포는 환경변수(앱이 Streamlit Secrets에서 옮겨 넣음)에서 읽는다."""
    try:
        from dotenv import load_dotenv

        load_dotenv(config.ROOT / ".env")  # 이미 있는 환경변수는 덮어쓰지 않는다
    except ImportError:
        pass
    return os.environ.get("OPENAI_API_KEY") or None


_client = None


def _get_client():
    """OpenAI 클라이언트를 한 번만 만든다. 네트워크·429·5xx 재시도는 SDK가 한다."""
    global _client
    if _client is None:
        from openai import OpenAI

        _client = OpenAI(api_key=get_api_key(), max_retries=config.API_MAX_RETRIES, timeout=config.API_TIMEOUT_S)
    return _client


def call_json(model: dict, system: str, user: str) -> LLMReply:
    """model은 config의 모델 설정. temperature가 None이면 요청에 넣지 않는다(모델 기본값)."""
    kwargs = {
        "model": model["name"],
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "response_format": {"type": "json_object"},
    }
    if model.get("temperature") is not None:
        kwargs["temperature"] = model["temperature"]
    t0 = time.perf_counter()
    try:
        r = _get_client().chat.completions.create(**kwargs)
    except Exception as e:  # SDK 재시도 후에도 실패 → 예외 대신 기록으로 돌려준다
        return LLMReply(None, f"{type(e).__name__}: {e}", time.perf_counter() - t0, None)
    usage = None
    if r.usage is not None:
        usage = {"prompt_tokens": r.usage.prompt_tokens, "completion_tokens": r.usage.completion_tokens}
    return LLMReply(r.choices[0].message.content, None, time.perf_counter() - t0, usage)
```

- [ ] **Step 4: 통과 확인**

Run: `.venv/Scripts/python -m pytest tests/test_llm_client.py -v`
Expected: 3 passed

- [ ] **Step 5: 실제 API 연결 한 번 확인 (네트워크, 수동)**

Run:

```bash
.venv/Scripts/python -c "from spc_explainer import llm_client as c; r = c.call_json({'name': 'gpt-4.1-mini', 'temperature': 0}, 'JSON으로만 답해.', '{\"ok\": true}를 그대로 돌려줘'); print(r.text, r.error)"
```

Expected: `{"ok": true}` 비슷한 JSON과 `None`. 오류면 `.env`의 `OPENAI_API_KEY`를 확인한다.

- [ ] **Step 6: 커밋**

```bash
git add spc_explainer/llm_client.py tests/test_llm_client.py
git commit -m "feat: OpenAI JSON 모드 호출부 (모델별 temperature)" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
git push origin main
```

---

### Task 6: 원인표와 설명 LLM (입력·프롬프트·검증기)

**Files:**
- Create: `spc_explainer/causes.py`, `spc_explainer/explain.py`
- Test: `tests/test_explain.py`

**Interfaces:**
- Consumes: `config`, `patterns.KOREAN`, `patterns.FROM_KOREAN`, `patterns.Event`, `rules.describe`
- Produces:
  - `causes.CAUSES: dict[str, dict]` — `{"SP-1": {"pattern": "spike", "cause": str, "check": str}, ...}` 15행
  - `causes.rows_for(patterns: set[str]) -> dict[str, dict]`
  - `explain.PROMPT_VERSION = "explain-v1"`, `explain.SYSTEM: str`, `explain.ISSUE_KO = {"format": "JSON 형식 위반", "cause": "원인표 밖 원인", "mismatch": "판정 불일치"}`
  - `explain.build_input(values, events: list[Event]) -> dict` — `{"process", "events", "cause_table"}`
  - `explain.build_messages(inp: dict) -> tuple[str, str]` — (system, user). user는 `"다음 판정 결과를 설명해 줘.\n"` + 입력 JSON
  - `explain.validate(text: str | None, inp: dict) -> tuple[dict | None, list[dict]]` — 문제는 `{"type": "format" | "cause" | "mismatch", "detail": str}`
  - `explain.signature(data: dict | None) -> str | None` — 반복 간 비교용

- [ ] **Step 1: 실패하는 테스트 작성**

Create `tests/test_explain.py`:

```python
# 설명 입력 구성과 출력 검증기: 형식 위반·원인표 밖 원인·판정 불일치를 각각 잡아내는지
import json

from spc_explainer.causes import CAUSES, rows_for
from spc_explainer.explain import build_input, build_messages, signature, validate
from spc_explainer.patterns import Event

VALUES = [104.2 if i == 30 else 99.0 if 50 <= i <= 59 else 100.0 for i in range(100)]
EVENTS = [Event("spike", 30, 30, "up"), Event("shift", 50, 59, "down")]
INP = build_input(VALUES, EVENTS)

GOOD = {
    "summary": "30번 급변과 50~59번 아래 치우침이 있습니다.",
    "events": [
        {"event_id": "E1", "pattern": "급변", "rule": "관리한계 밖 1점",
         "checks": [{"cause_id": "SP-1", "reason": "재측정이 가장 빠름"}]},
        {"event_id": "E2", "pattern": "치우침", "rule": "10점 연속 중심선 아래",
         "checks": [{"cause_id": "SH-1", "reason": "PM 직후인지 확인"}, {"cause_id": "SH-2", "reason": "로트 확인"}]},
    ],
    "priority": ["E2", "E1"],
}


def variant(change) -> dict:
    """GOOD을 깊은 복사한 뒤 change(obj)로 한 곳만 바꾼다."""
    obj = json.loads(json.dumps(GOOD, ensure_ascii=False))
    change(obj)
    return obj


def issue_types(obj) -> list[str]:
    _, issues = validate(json.dumps(obj, ensure_ascii=False), INP)
    return sorted({i["type"] for i in issues})


def test_input_has_rule_events_and_only_relevant_causes():
    assert set(INP) == {"process", "events", "cause_table"}  # 원시 시계열은 넣지 않는다
    assert [e["event_id"] for e in INP["events"]] == ["E1", "E2"]
    assert INP["events"][0]["pattern"] == "급변" and INP["events"][0]["values"] == [104.2]
    assert INP["events"][1]["direction"] == "아래" and INP["events"][1]["mean"] == 99.0
    assert INP["events"][1]["rule"] == "10점 연속 중심선 아래 (50~59번, 평균 99.00nm)"
    assert {c["cause_id"][:2] for c in INP["cause_table"]} == {"SP", "SH"}  # 추세 원인은 주지 않음


def test_cause_table_rows():
    assert len(CAUSES) == 15
    assert set(rows_for({"trend"})) == {f"TR-{i}" for i in range(1, 6)}


def test_messages_mention_json_and_events():
    system, user = build_messages(INP)
    assert "JSON" in system
    assert user.startswith("다음 판정 결과를 설명해 줘.\n") and '"E1"' in user


def test_good_output_passes():
    assert issue_types(GOOD) == []


def test_broken_json_is_format_violation():
    for bad in ['{"summary": "끊김', None, "[]"]:
        _, issues = validate(bad, INP)
        assert [i["type"] for i in issues] == ["format"], bad


def test_missing_key_or_bad_values_are_format_violations():
    assert issue_types(variant(lambda o: o.pop("summary"))) == ["format"]
    assert issue_types(variant(lambda o: o["events"][0].update(checks=[]))) == ["format"]
    assert issue_types(variant(lambda o: o["events"][0].update(pattern="스파이크"))) == ["format"]


def test_cause_outside_table_or_from_other_pattern():
    assert issue_types(variant(lambda o: o["events"][0]["checks"][0].update(cause_id="XX-9"))) == ["cause"]
    assert issue_types(variant(lambda o: o["events"][0]["checks"][0].update(cause_id="TR-1"))) == ["cause"]


def test_verdict_mismatch_cases():
    assert issue_types(variant(lambda o: o["events"][1].update(pattern="추세"))) == ["mismatch"]
    assert issue_types(variant(lambda o: o["events"].pop())) == ["mismatch"]  # E2 누락
    assert issue_types(variant(lambda o: o["events"].append(dict(o["events"][0], event_id="E3")))) == ["mismatch"]
    assert issue_types(variant(lambda o: o.update(priority=["E1"]))) == ["mismatch"]


def test_parseable_but_wrong_types_do_not_raise():
    weird_outputs = [
        '{"events": {"E1": 1}}',
        '{"events": [{"event_id": "E1", "checks": "SP-1"}]}',
        '{"summary": 1, "events": [1, null], "priority": "E1"}',
        '{"events": [{"event_id": "E1", "checks": [1, {"cause_id": ["SP-1"], "reason": "x"}]}]}',
        '{"events": 5, "priority": [1, 2]}',
    ]
    for weird in weird_outputs:
        data, issues = validate(weird, INP)
        assert "format" in {i["type"] for i in issues}, weird
        signature(data)  # 예외가 나면 안 된다


def test_signature_ignores_reason_wording():
    other = variant(lambda o: o["events"][0]["checks"][0].update(reason="다른 문장"))
    assert signature(GOOD) == signature(other)
    assert signature(variant(lambda o: o.update(priority=["E1", "E2"]))) != signature(GOOD)
    assert signature(None) is None
```

- [ ] **Step 2: 실패 확인**

Run: `.venv/Scripts/python -m pytest tests/test_explain.py -v`
Expected: 수집 오류 `ModuleNotFoundError: No module named 'spc_explainer.causes'`

- [ ] **Step 3: 원인표 구현**

Create `spc_explainer/causes.py`:

```python
# 원인표: 패턴별 후보 원인과 점검 항목.
# 교과서 수준의 도메인 가정이며 실제 설비 데이터로 검증한 것이 아니다 (README·리포트에 명시).
CAUSES = {
    "SP-1": {"pattern": "spike", "cause": "계측 오류 (측정 위치 오정렬, 계측기 순간 오류)", "check": "같은 웨이퍼 재측정"},
    "SP-2": {"pattern": "spike", "cause": "파티클·이물로 인한 국부 이상", "check": "파티클·결함 검사 결과 확인"},
    "SP-3": {"pattern": "spike", "cause": "가스 유량 순간 이상 (MFC 스파이크)", "check": "해당 런의 MFC 유량 로그 확인"},
    "SP-4": {"pattern": "spike", "cause": "웨이퍼 로딩·척(chuck) 이상", "check": "로딩 로그와 척 상태 확인"},
    "SP-5": {"pattern": "spike", "cause": "레시피·작업 입력 오류", "check": "해당 런의 레시피·작업 이력 확인"},
    "TR-1": {"pattern": "trend", "cause": "챔버 벽 증착물 누적 (클리닝 주기 도래)", "check": "마지막 챔버 클리닝 이후 처리 매수 확인"},
    "TR-2": {"pattern": "trend", "cause": "히터·온도의 점진적 변화", "check": "온도 센서 로그 추이 확인"},
    "TR-3": {"pattern": "trend", "cause": "소스 소모 (전구체 잔량, 타깃 수명)", "check": "소모품 사용량과 교체 시점 확인"},
    "TR-4": {"pattern": "trend", "cause": "펌프 성능 저하로 인한 압력 변화", "check": "챔버 압력 로그 추이 확인"},
    "TR-5": {"pattern": "trend", "cause": "계측기 드리프트", "check": "표준 시편으로 계측기 점검"},
    "SH-1": {"pattern": "shift", "cause": "부품 교체·PM 후 조건 변화", "check": "PM 이력과 치우침 시작 시점 비교"},
    "SH-2": {"pattern": "shift", "cause": "원료 가스·전구체 로트 변경", "check": "원료 로트 변경 이력 확인"},
    "SH-3": {"pattern": "shift", "cause": "레시피 변경", "check": "레시피 변경 이력 확인"},
    "SH-4": {"pattern": "shift", "cause": "계측기 교정값 변경", "check": "계측기 교정 이력 확인"},
    "SH-5": {"pattern": "shift", "cause": "다른 챔버·장비로 전환", "check": "설비 배정 이력 확인"},
}


def rows_for(patterns: set[str]) -> dict[str, dict]:
    """주어진 패턴들의 원인표 행만 뽑는다 (설명 LLM 입력용)."""
    return {cid: row for cid, row in CAUSES.items() if row["pattern"] in patterns}
```

- [ ] **Step 4: 설명 입력·프롬프트·검증기 구현**

Create `spc_explainer/explain.py`:

```python
# 설명 LLM: 규칙 판정 결과(JSON)와 원인표를 받아 한국어 설명 JSON을 만든다. 출력 검증기 포함.
import json

from . import config
from .causes import CAUSES, rows_for
from .patterns import FROM_KOREAN, KOREAN, Event
from .rules import describe

PROMPT_VERSION = "explain-v1"  # 프롬프트를 바꾸면 올린다 (캐시가 새로 호출하게 됨)
DIRECTION_KO = {
    "spike": {"up": "위", "down": "아래"},
    "trend": {"up": "상승", "down": "하강"},
    "shift": {"up": "위", "down": "아래"},
}
ISSUE_KO = {"format": "JSON 형식 위반", "cause": "원인표 밖 원인", "mismatch": "판정 불일치"}

SYSTEM = """너는 반도체 증착 공정의 관리도(SPC) 판정 결과를 공정 엔지니어에게 설명하는 도우미다.
판정은 규칙 엔진이 이미 끝냈다. 너의 일은 설명뿐이다.
지킬 것:
1. 입력의 사건(events)을 추가·삭제·변경하지 않는다. 모든 사건을 같은 event_id와 pattern으로 빠짐없이 설명한다.
2. 원인은 입력의 원인표(cause_table)에서, 그 사건과 같은 패턴의 cause_id만 고른다. 원인표에 없는 원인을 만들지 않는다.
3. 사건마다 점검할 원인을 1~3개, 먼저 점검할 순서대로 적는다.
4. priority에는 모든 event_id를 먼저 점검할 사건 순서대로 한 번씩 적는다.
5. 한국어로 쓰고, 아래 형식의 JSON 객체 하나만 출력한다.
{"summary": "전체 요약 1~2문장",
 "events": [{"event_id": "E1", "pattern": "급변|추세|치우침 중 하나", "rule": "근거 규칙",
             "checks": [{"cause_id": "원인표의 cause_id", "reason": "이 순서로 점검하는 이유"}]}],
 "priority": ["E1"]}"""


def build_input(values, events: list[Event]) -> dict:
    """설명 LLM 입력: 공정 정보 + 규칙 사건 요약 + 해당 패턴의 원인표. 원시 시계열은 넣지 않는다."""
    items = []
    for i, ev in enumerate(events, start=1):
        seg = [float(v) for v in values[ev.start:ev.end + 1]]
        item = {
            "event_id": f"E{i}",
            "pattern": KOREAN[ev.pattern],
            "direction": DIRECTION_KO[ev.pattern][ev.direction],
            "start": ev.start,
            "end": ev.end,
            "rule": describe(ev, values),
        }
        if ev.pattern == "spike":
            item["values"] = seg
        elif ev.pattern == "trend":
            item["first_value"], item["last_value"] = seg[0], seg[-1]
        else:
            item["mean"] = round(sum(seg) / len(seg), 2)
        items.append(item)
    table = rows_for({ev.pattern for ev in events})
    return {
        "process": {"name": config.PROCESS_NAME, "unit": config.UNIT, "target": config.CENTER,
                    "ucl": config.UCL, "lcl": config.LCL},
        "events": items,
        "cause_table": [{"cause_id": cid, "pattern": KOREAN[r["pattern"]], "cause": r["cause"], "check": r["check"]}
                        for cid, r in table.items()],
    }


def build_messages(inp: dict) -> tuple[str, str]:
    """(system, user) 메시지. JSON 모드는 메시지에 'JSON'이라는 말이 있어야 한다."""
    return SYSTEM, "다음 판정 결과를 설명해 줘.\n" + json.dumps(inp, ensure_ascii=False, indent=1)


def validate(text: str | None, inp: dict) -> tuple[dict | None, list[dict]]:
    """설명 출력을 검사한다. (파싱된 JSON 또는 None, 문제 목록[{"type", "detail"}]). 예외를 던지지 않는다."""
    issues: list[dict] = []

    def add(kind: str, detail: str) -> None:
        issues.append({"type": kind, "detail": detail})

    try:
        data = json.loads(text)
    except (TypeError, ValueError) as e:
        add("format", f"JSON 파싱 실패: {e}")
        return None, issues
    if not isinstance(data, dict):
        add("format", "최상위가 JSON 객체가 아님")
        return None, issues

    expected = {e["event_id"]: e["pattern"] for e in inp["events"]}  # 규칙 판정: 사건 id → 패턴 이름
    if not isinstance(data.get("summary"), str):
        add("format", "summary 누락 또는 문자열 아님")
    events = data.get("events")
    if not isinstance(events, list):
        add("format", "events 누락 또는 배열 아님")
        events = []
    seen = []
    for ev in events:
        if not isinstance(ev, dict) or not isinstance(ev.get("event_id"), str):
            add("format", "사건 항목에 event_id가 없음")
            continue
        eid = ev["event_id"]
        seen.append(eid)
        pattern = ev.get("pattern")
        if pattern not in FROM_KOREAN:
            add("format", f"{eid}: pattern '{pattern}'은 급변/추세/치우침이 아님")
        elif eid in expected and pattern != expected[eid]:
            add("mismatch", f"{eid}: 패턴 '{pattern}' ≠ 규칙 판정 '{expected[eid]}'")
        if not isinstance(ev.get("rule"), str):
            add("format", f"{eid}: rule 누락")
        checks = ev.get("checks")
        if not isinstance(checks, list) or not 1 <= len(checks) <= 3:
            add("format", f"{eid}: checks는 1~3개 배열이어야 함")
            checks = checks if isinstance(checks, list) else []
        for c in checks:
            if not isinstance(c, dict) or not isinstance(c.get("cause_id"), str) or not isinstance(c.get("reason"), str):
                add("format", f"{eid}: checks 항목에 cause_id·reason이 없음")
                continue
            cid = c["cause_id"]
            if cid not in CAUSES:
                add("cause", f"{eid}: '{cid}'는 원인표에 없음")
            elif eid in expected and KOREAN[CAUSES[cid]["pattern"]] != expected[eid]:
                other = KOREAN[CAUSES[cid]["pattern"]]
                add("cause", f"{eid}: '{cid}'는 {other} 원인인데 사건은 {expected[eid]}")
    missing = [e for e in expected if e not in seen]
    extra = [e for e in seen if e not in expected]
    if missing:
        add("mismatch", f"사건 누락: {', '.join(missing)}")
    if extra:
        add("mismatch", f"없는 사건 추가: {', '.join(extra)}")
    priority = data.get("priority")
    if not isinstance(priority, list):
        add("format", "priority 누락 또는 배열 아님")
    elif sorted(map(str, priority)) != sorted(expected):
        add("mismatch", f"priority {priority}가 사건 {list(expected)}을 한 번씩 담지 않음")
    return data, issues


def signature(data: dict | None) -> str | None:
    """반복 간 비교용 요약: 사건별 1순위 원인과 priority. 파싱 실패면 None."""
    if not isinstance(data, dict):
        return None
    first = {}
    events = data.get("events") if isinstance(data.get("events"), list) else []
    for ev in events:
        if isinstance(ev, dict):
            checks = ev.get("checks") if isinstance(ev.get("checks"), list) else []
            top = checks[0] if checks and isinstance(checks[0], dict) else {}
            first[str(ev.get("event_id"))] = str(top.get("cause_id"))
    return json.dumps({"first": first, "priority": str(data.get("priority"))}, ensure_ascii=False, sort_keys=True)
```

- [ ] **Step 5: 통과 확인**

Run: `.venv/Scripts/python -m pytest tests/test_explain.py -v`
Expected: 10 passed

- [ ] **Step 6: 커밋**

```bash
git add spc_explainer/causes.py spc_explainer/explain.py tests/test_explain.py
git commit -m "feat: 원인표와 설명 LLM 입력·검증기" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
git push origin main
```

---

### Task 7: LLM 단독 판정 (비교 실험용 프롬프트·파서)

**Files:**
- Create: `spc_explainer/llm_detect.py`
- Test: `tests/test_llm_detect.py`

**Interfaces:**
- Consumes: `config`, `patterns.FROM_KOREAN`, `patterns.Event`, `patterns.definitions_text`
- Produces:
  - `llm_detect.PROMPT_VERSION = "detect-v1"`, `llm_detect.SYSTEM: str`
  - `llm_detect.build_messages(values) -> tuple[str, str]` — user는 `"데이터 (번호: 값)"` 다음 줄부터 `"i: v"` (소수 둘째 자리)
  - `llm_detect.parse(text: str | None, n_points: int = config.N_POINTS) -> tuple[list[Event], list[dict]]` — 형식 위반이 하나라도 있으면 `([], [{"type": "format", "detail": str}])`

- [ ] **Step 1: 실패하는 테스트 작성**

Create `tests/test_llm_detect.py`:

```python
# 단독 판정 프롬프트와 출력 파서
from spc_explainer.llm_detect import build_messages, parse
from spc_explainer.patterns import Event


def test_messages_contain_definitions_and_indexed_values():
    system, user = build_messages([100.0, 104.25])
    assert "6개 이상" in system and "UCL 103" in system and "JSON" in system
    assert user.splitlines() == ["데이터 (번호: 값)", "0: 100.00", "1: 104.25"]


def test_parse_valid():
    text = '{"detections": [{"pattern": "추세", "start": 60, "end": 67}, {"pattern": "급변", "start": 3, "end": 3}]}'
    assert parse(text) == ([Event("trend", 60, 67), Event("spike", 3, 3)], [])
    assert parse('{"detections": []}') == ([], [])


def test_parse_format_violations_score_as_no_detection():
    bad_outputs = [
        '{"detections": [{"pattern": "추세", "start": 60}]}',  # end 누락
        '{"detections": [{"pattern": "추세", "start": 70, "end": 60}]}',  # start > end
        '{"detections": [{"pattern": "추세", "start": 95, "end": 100}]}',  # 번호 범위 밖
        '{"detections": [{"pattern": "trend", "start": 1, "end": 2}]}',  # 패턴 이름 틀림
        '{"result": []}',
        "not json",
        None,
    ]
    for bad in bad_outputs:
        events, issues = parse(bad)
        assert events == [] and [i["type"] for i in issues] == ["format"], bad


def test_parse_wrong_types_do_not_raise():
    for weird in ["[]", '{"detections": {"a": 1}}', '{"detections": [1]}',
                  '{"detections": [{"pattern": "추세", "start": 1.5, "end": 3}]}',
                  '{"detections": [{"pattern": "추세", "start": true, "end": 3}]}']:
        events, issues = parse(weird)
        assert events == [] and issues[0]["type"] == "format", weird
```

- [ ] **Step 2: 실패 확인**

Run: `.venv/Scripts/python -m pytest tests/test_llm_detect.py -v`
Expected: 수집 오류 `ModuleNotFoundError: No module named 'spc_explainer.llm_detect'`

- [ ] **Step 3: 구현**

Create `spc_explainer/llm_detect.py`:

```python
# LLM 단독 판정(비교 실험): 규칙 정의와 원시 데이터만 주고 LLM이 직접 판정하게 한다.
import json

from . import config
from .patterns import FROM_KOREAN, Event, definitions_text

PROMPT_VERSION = "detect-v1"  # 프롬프트를 바꾸면 올린다 (캐시가 새로 호출하게 됨)

SYSTEM = (
    "너는 관리도(SPC) 판정기다. 아래 규칙 정의대로 데이터에서 이상 사건을 빠짐없이 찾아라.\n"
    f"중심선 {config.CENTER:g}, UCL {config.UCL:g}, LCL {config.LCL:g}. 점 번호는 0부터 센다.\n"
    + definitions_text()
    + "\n같은 패턴이 이어지는 점들은 사건 하나로 묶고, 시작·끝 번호(양끝 포함)를 적는다.\n"
    + '출력은 JSON 객체 하나: {"detections": [{"pattern": "급변|추세|치우침 중 하나", "start": 0, "end": 0}]}. '
    + '사건이 없으면 {"detections": []}.'
)


def build_messages(values) -> tuple[str, str]:
    """(system, user). 값은 규칙 엔진이 보는 값과 똑같이 소수 둘째 자리로 준다."""
    lines = [f"{i}: {float(v):.2f}" for i, v in enumerate(values)]
    return SYSTEM, "\n".join(["데이터 (번호: 값)"] + lines)


def parse(text: str | None, n_points: int = config.N_POINTS) -> tuple[list[Event], list[dict]]:
    """출력 파싱. (사건 목록, 문제 목록). 형식 위반이 하나라도 있으면 사건 0개로 채점한다."""

    def fail(detail: str) -> tuple[list[Event], list[dict]]:
        return [], [{"type": "format", "detail": detail}]

    try:
        data = json.loads(text)
    except (TypeError, ValueError) as e:
        return fail(f"JSON 파싱 실패: {e}")
    detections = data.get("detections") if isinstance(data, dict) else None
    if not isinstance(detections, list):
        return fail("detections 누락 또는 배열 아님")
    events = []
    for d in detections:
        if not isinstance(d, dict):
            return fail("사건 항목이 객체가 아님")
        pattern, start, end = d.get("pattern"), d.get("start"), d.get("end")
        if pattern not in FROM_KOREAN:
            return fail(f"pattern '{pattern}'은 급변/추세/치우침이 아님")
        if type(start) is not int or type(end) is not int:  # bool·실수 제외
            return fail(f"번호가 정수가 아님: {start}, {end}")
        if not 0 <= start <= end < n_points:
            return fail(f"번호 범위 오류: {start}~{end}")
        events.append(Event(FROM_KOREAN[pattern], start, end))
    return events, []
```

- [ ] **Step 4: 통과 확인**

Run: `.venv/Scripts/python -m pytest tests/test_llm_detect.py -v`
Expected: 4 passed

- [ ] **Step 5: 커밋**

```bash
git add spc_explainer/llm_detect.py tests/test_llm_detect.py
git commit -m "feat: LLM 단독 판정 프롬프트와 파서" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
git push origin main
```

---

### Task 8: 검증 리포트 생성

**Files:**
- Create: `spc_explainer/report.py`
- Test: `tests/test_report.py`

**Interfaces:**
- Consumes: `config`, `patterns.KOREAN`, `patterns.PATTERNS`, `matching.summarize` 출력 형태(Task 4)
- Produces:
  - `report.render(m: dict) -> str`, `report.write(m: dict, path: Path = config.REPORT_PATH) -> None`
  - `report.secom_section(s: dict | None) -> list[str]` (Task 13 테스트가 사용), `report.pct(x, digits=0) -> str`
  - 입력 지표 `m`의 형태 (Task 9 `compute_metrics`가 만든다):

    ```text
    {"generated_at": str,
     "dataset": {"seed", "n_series", "n_normal", "n_points", "injected": {p: int}},
     "rules": <matching.summarize 결과>,
     "detect": [{"model", "temperature", "repeats", "prompt_version",
                 "runs": [<summarize 결과> + {"format_violations": int, "call_errors": int}, ...]}],
     "explain": None | {"model", "temperature", "repeats", "prompt_version", "series_called", "outputs", "passed",
                        "issue_outputs": {"format", "cause", "mismatch"}, "call_errors", "repeat_changed_series"},
     "secom": None | {"n", "phase1_n", "sensors": {name: {"limits": {"center", "sigma", "ucl", "lcl"}, "events",
                      "by_pattern": {p: int}, "events_with_fail", "flagged_points", "fail_rate_flagged", "fail_rate_phase2"}}}}
    ```

- [ ] **Step 1: 실패하는 테스트 작성**

Create `tests/test_report.py`:

```python
# 지표 → 마크다운 리포트: 가정 문구, 섹션, 핵심 수치가 들어가는지
from spc_explainer.matching import summarize
from spc_explainer.patterns import Event
from spc_explainer.report import render, write

RULES = summarize([[], [Event("spike", 5, 5, "up")]], [[Event("trend", 20, 25, "up")], [Event("spike", 5, 5, "up")]])
METRICS = {
    "generated_at": "2026-09-25T21:00:00",
    "dataset": {"seed": 1, "n_series": 2, "n_normal": 1, "n_points": 100, "injected": {"spike": 1, "trend": 0, "shift": 0}},
    "rules": RULES,
    "detect": [{"model": "gpt-4.1-mini", "temperature": 0, "repeats": 2, "prompt_version": "detect-v1",
                "runs": [dict(RULES, format_violations=0, call_errors=0),
                         dict(RULES, rate=0.0, format_violations=1, call_errors=0)]},
               {"model": "gpt-6-sol", "temperature": None, "repeats": 1, "prompt_version": "detect-v1",
                "runs": [dict(RULES, format_violations=0, call_errors=2)]}],
    "explain": {"model": "gpt-4.1-mini", "temperature": 0, "repeats": 3, "prompt_version": "explain-v1",
                "series_called": 2, "outputs": 6, "passed": 5,
                "issue_outputs": {"format": 0, "cause": 1, "mismatch": 0},
                "call_errors": 0, "repeat_changed_series": 1},
    "secom": None,
}


def test_report_has_assumption_and_all_sections():
    md = render(METRICS)
    assert "이미 안정화된 공정을 감시하는 상황을 가정" in md
    for title in ("## 1. 실험 조건", "## 2. 규칙 판정", "## 3. LLM 단독 판정 비교", "## 4. LLM 설명 검증",
                  "## 5. 실데이터 확인", "## 6. 해석 시 주의"):
        assert title in md


def test_report_numbers():
    md = render(METRICS)
    assert "| 급변 | 1 / 1 | 100% |" in md
    assert "정상 시리즈: 1개 중 1개에서 경보" in md
    assert "| 규칙 엔진 | 1 | 100% | 1/1 | 0/0 | 0/0 | 1/1 | 1 | 0 | - | - |" in md
    assert "| gpt-4.1-mini (temperature 0) | 2 | 50% (0%~100%) |" in md
    assert "| gpt-6-sol (temperature 기본값) | 1 | 100% |" in md
    assert "| 원인표 밖 원인 | 1 |" in md
    assert "데이터가 없어 건너뜀" in md
    assert "gpt-6-sol은(는) temperature를 바꿀 수 없어" in md


def test_write_creates_file(tmp_path):
    path = tmp_path / "docs" / "report.md"
    write(METRICS, path)
    assert path.read_text(encoding="utf-8").startswith("# 검증 리포트")
```

- [ ] **Step 2: 실패 확인**

Run: `.venv/Scripts/python -m pytest tests/test_report.py -v`
Expected: 수집 오류 `ModuleNotFoundError: No module named 'spc_explainer.report'`

- [ ] **Step 3: 구현**

Create `spc_explainer/report.py`:

```python
# 지표(metrics.json) → 검증 리포트 마크다운. 앱의 "검증 리포트" 탭도 이 파일을 그대로 보여준다.
from pathlib import Path

from . import config
from .patterns import KOREAN, PATTERNS


def pct(x, digits: int = 0) -> str:
    return "-" if x is None else f"{x * 100:.{digits}f}%"


def num(x) -> str:
    """7.0 → "7", 6.333 → "6.3"."""
    return f"{x:.1f}".rstrip("0").rstrip(".")


def _mean(xs: list) -> float | None:
    return sum(xs) / len(xs) if xs else None


def _counts(d: dict) -> str:
    return ", ".join(f"{KOREAN[p]} {d[p]}" for p in PATTERNS)


def _temp(t) -> str:
    return "기본값" if t is None else str(t)


def rules_section(r: dict) -> list[str]:
    lines = ["## 2. 규칙 판정", "", "| 패턴 | 탐지 / 심은 수 | 탐지율 |", "|---|---|---|"]
    for p in PATTERNS:
        d = r["per_pattern"][p]
        rate = d["detected"] / d["injected"] if d["injected"] else None
        lines.append(f"| {KOREAN[p]} | {d['detected']} / {d['injected']} | {pct(rate)} |")
    lines.append(f"| 전체 | {r['detected']} / {r['injected']} | {pct(r['rate'])} |")
    n, a = r["normal"], r["anomalous"]
    lines += [
        "",
        "오탐 (심은 이상과 겹치지 않는 경보):",
        f"- 정상 시리즈: {n['series']}개 중 {n['alarmed_series']}개에서 경보. 오탐 사건: {_counts(n['false_events'])}",
        f"- 이상 시리즈: 오탐 사건 {_counts(a['false_events'])}. 패턴 혼동 {a['confusions']}건",
    ]
    if r["false_list"]:
        items = "; ".join(f"시리즈 {f['series']} {KOREAN[f['pattern']]} {f['start']}~{f['end']}번" for f in r["false_list"])
        lines.append(f"- 오탐 목록: {items}")
    lines += [
        "- 정상 점을 N(100, 1²)로 만들었으므로 정상 구간에서도 규칙 정의를 실제로 만족하는 경보가 생길 수 있다. "
        "규칙 판정에도 오탐이 있다는 뜻이다.",
        "- 교차 검증: 독립 구현(shewhart)과 점 단위 판정이 같은지 `tests/test_crosscheck.py`에서 확인한다.",
        "",
    ]
    return lines


def _detect_row(name: str, runs: list[dict], llm: bool) -> str:
    rates = [r["rate"] for r in runs if r["rate"] is not None]
    if len(rates) > 1:
        rate = f"{pct(_mean(rates))} ({pct(min(rates))}~{pct(max(rates))})"
    else:
        rate = pct(rates[0]) if rates else "-"
    per = " | ".join(
        f"{num(_mean([r['per_pattern'][p]['detected'] for r in runs]))}/{runs[0]['per_pattern'][p]['injected']}"
        for p in PATTERNS
    )
    alarmed = f"{num(_mean([r['normal']['alarmed_series'] for r in runs]))}/{runs[0]['normal']['series']}"
    false = num(_mean([sum(r["normal"]["false_events"].values()) + sum(r["anomalous"]["false_events"].values())
                       for r in runs]))
    conf = num(_mean([r["anomalous"]["confusions"] for r in runs]))
    fmt = str(sum(r["format_violations"] for r in runs)) if llm else "-"
    err = str(sum(r["call_errors"] for r in runs)) if llm else "-"
    return f"| {name} | {len(runs)} | {rate} | {per} | {alarmed} | {false} | {conf} | {fmt} | {err} |"


def detect_section(rules: dict, detect: list[dict]) -> list[str]:
    lines = [
        "## 3. LLM 단독 판정 비교",
        "",
        "LLM에게 규칙 정의와 원시 데이터(번호: 값)만 주고 직접 판정하게 했다. 채점 기준은 규칙 엔진과 같다. "
        "패턴별 탐지 수·경보·오탐·혼동은 반복 평균, 형식 위반·호출 오류는 반복 합계다.",
        "",
        "| 판정 방식 | 반복 | 탐지율 평균 (최소~최대) | 급변 | 추세 | 치우침 | 정상 시리즈 경보 | 오탐 사건 | 패턴 혼동 | 형식 위반 | 호출 오류 |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
        _detect_row("규칙 엔진", [rules], llm=False),
    ]
    for d in detect:
        lines.append(_detect_row(f"{d['model']} (temperature {_temp(d['temperature'])})", d["runs"], llm=True))
    if not detect:
        lines += ["", "LLM 단독 판정은 아직 실행하지 않았다."]
    lines += ["", "- 형식 위반 출력과 호출 오류는 탐지 0개로 채점했다. 호출 오류가 있으면 실험을 다시 돌려 채운다.", ""]
    return lines


def explain_section(e: dict | None) -> list[str]:
    title = "## 4. LLM 설명 검증"
    if not e:
        return [title, "", "아직 실행하지 않았다.", ""]
    return [
        f"{title} ({e['model']}, temperature {_temp(e['temperature'])}, 같은 입력 {e['repeats']}회)",
        "",
        f"사건이 있는 시리즈 {e['series_called']}개 × {e['repeats']}회 = 출력 {e['outputs']}개. "
        "한 출력에 여러 유형의 문제가 있으면 유형마다 센다.",
        "",
        "| 항목 | 출력 수 |",
        "|---|---|",
        f"| 검증 통과 | {e['passed']} |",
        f"| JSON 형식 위반 | {e['issue_outputs']['format']} |",
        f"| 원인표 밖 원인 | {e['issue_outputs']['cause']} |",
        f"| 판정 불일치 | {e['issue_outputs']['mismatch']} |",
        f"| 호출 오류 | {e['call_errors']} |",
        "",
        f"- 반복 간 차이: {e['series_called']}개 시리즈 중 {e['repeat_changed_series']}개에서 "
        "사건별 1순위 원인이나 점검 순서가 반복마다 달랐다.",
        "- 틀린 출력의 원문 발췌는 `docs/ai_errors.md`에 있다.",
        "- 이번 실험은 JSON 모드 + 자체 검증기를 썼다. 운영에서는 strict 스키마와 원인 id enum으로 "
        "형식 위반·원인표 밖 원인을 원천 차단할 수 있다.",
        "- 원인표는 교과서 수준의 도메인 가정이며 실제 설비 데이터로 검증하지 않았다.",
        "",
    ]


def secom_section(s: dict | None) -> list[str]:
    lines = ["## 5. 실데이터 확인 (UCI SECOM)", ""]
    if not s:
        return lines + ["선택 항목 — 데이터가 없어 건너뜀 (`python scripts/fetch_secom.py`).", ""]
    lines += [
        f"시간순 앞 {s['phase1_n']}점(Phase I)으로 한계를 추정하고 나머지 {s['n'] - s['phase1_n']}점(Phase II)을 "
        "같은 규칙으로 감시했다. 정답이 없어 탐지율은 계산하지 않는다.",
        "",
        "| 센서 | 중심선 | σ | 알람 사건 (급변/추세/치우침) | 불량 포함 사건 | 알람 점 중 불량 비율 | Phase II 전체 불량 비율 |",
        "|---|---|---|---|---|---|---|",
    ]
    for name, d in s["sensors"].items():
        bp, lim = d["by_pattern"], d["limits"]
        lines.append(
            f"| {name} | {lim['center']:.4g} | {lim['sigma']:.4g} | {d['events']} ({bp['spike']}/{bp['trend']}/{bp['shift']}) "
            f"| {d['events_with_fail']} | {pct(d['fail_rate_flagged'], 1)} | {pct(d['fail_rate_phase2'], 1)} |"
        )
    lines += [
        "",
        "- 겹침은 관찰일 뿐이다. 인과관계나 탐지 성능으로 해석하지 않는다.",
        "- 출처: UCI SECOM (McCann & Johnston, 2008), CC BY 4.0, DOI 10.24432/C54305.",
        "",
    ]
    return lines


def caution_section(m: dict) -> list[str]:
    d = m["dataset"]
    lines = [
        "## 6. 해석 시 주의",
        "",
        "- 합성 데이터라 실제 공정의 잡음 구조(자기상관, 비정규성 등)를 반영하지 않는다.",
        f"- 시리즈 {d['n_series']}개, 심은 이상 {sum(d['injected'].values())}개로 표본이 작다. 비율은 참고치다.",
    ]
    fixed = [x["model"] for x in m["detect"] if x["temperature"] is None]
    if fixed:
        lines.append(f"- {', '.join(fixed)}은(는) temperature를 바꿀 수 없어 기본값으로 실행했다.")
    return lines + [""]


def render(m: dict) -> str:
    d = m["dataset"]
    injected = ", ".join(f"{KOREAN[p]} {d['injected'][p]}" for p in PATTERNS)
    u = config.UNIT
    limits = f"중심 {config.CENTER:g}{u}, UCL {config.UCL:g}{u}, LCL {config.LCL:g}{u}"
    lines = [
        "# 검증 리포트",
        "",
        f"> 자동 생성: `python scripts/run_experiment.py` · {m['generated_at']}  ",
        f"> 관리한계 고정값({limits}) 사용 = 이미 안정화된 공정을 감시하는 상황을 가정한다.",
        "",
        "## 1. 실험 조건",
        "",
        f"- 가상 데이터: {d['n_series']}개 시리즈 × {d['n_points']}점, 시드 {d['seed']}. "
        f"정상 시리즈 {d['n_normal']}개, 심은 이상 {sum(d['injected'].values())}개 ({injected}).",
        f"- 심은 이상은 규칙 정의를 만족하도록 만들었다: 급변 = 한계 밖 1점, 추세 = {config.TREND_LEN}점 연속 단조, "
        f"치우침 = {config.SHIFT_LEN}점 연속 중심선 한쪽.",
        "- 채점: 같은 패턴의 탐지 구간이 정답 구간과 한 점이라도 겹치면 탐지. "
        "어떤 정답과도 겹치지 않으면 오탐, 다른 패턴의 정답과만 겹치면 패턴 혼동.",
        "",
    ]
    lines += rules_section(m["rules"])
    lines += detect_section(m["rules"], m["detect"])
    lines += explain_section(m["explain"])
    lines += secom_section(m["secom"])
    lines += caution_section(m)
    return "\n".join(lines)


def write(m: dict, path: Path = config.REPORT_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render(m), encoding="utf-8")
```

- [ ] **Step 4: 통과 확인**

Run: `.venv/Scripts/python -m pytest tests/test_report.py -v`
Expected: 3 passed

- [ ] **Step 5: 커밋**

```bash
git add spc_explainer/report.py tests/test_report.py
git commit -m "feat: 검증 리포트 마크다운 생성" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
git push origin main
```

---

### Task 9: 실험 실행기 (반복 호출·캐시·지표·ai_errors)

**Files:**
- Create: `spc_explainer/experiment.py`, `scripts/run_experiment.py`
- Test: `tests/test_experiment.py`

**Interfaces:**
- Consumes: `generator.generate_dataset/save_dataset/truth_events`, `rules.detect`, `explain.build_input/build_messages/validate/signature/PROMPT_VERSION/SYSTEM/ISSUE_KO`, `llm_detect.build_messages/parse/PROMPT_VERSION`, `matching.classify/summarize`, `report.write`, `llm_client.LLMReply/call_json/get_api_key`
- Produces:
  - `experiment.LLMFn = Callable[[dict, str, str], LLMReply]`
  - `experiment.Paths` dataclass (`series, explanations, detections, metrics, report, ai_errors`), `Paths.under(root) -> Paths`
  - `experiment.run_all(llm: LLMFn | None, paths: Paths | None = None, force: bool = False) -> dict` — 지표 dict (Task 8 형태)
  - `experiment.compute_metrics(dataset: dict, explanations: dict, detections: dict) -> dict`
  - `results/explanations.json` 형태: `{"prompt_version", "model", "series": {"<id>": {"input", "input_hash", "runs": [{"run", "text", "error", "latency_s", "usage", "issues", "created"}]}}}`
  - `results/llm_detections.json` 형태: `{"prompt_version", "models": {"<name>": {"config", "series": {"<id>": {"input_hash", "runs": [{... , "events": [Event.to_dict()]}]}}}}}`

- [ ] **Step 1: 실패하는 테스트 작성**

Create `tests/test_experiment.py`:

```python
# 가짜 LLM으로 실험 전 과정을 네트워크 없이 돌려 본다
import json
import runpy
import sys

import pytest

from spc_explainer import config, explain, llm_client
from spc_explainer.experiment import Paths, run_all
from spc_explainer.llm_client import LLMReply


class FakeLLM:
    """설명은 규칙 입력을 그대로 따르는 모범 답을, 단독 판정은 4.1-mini엔 빈 결과·sol엔 깨진 출력을 준다."""

    def __init__(self):
        self.calls = 0

    def __call__(self, model, system, user):
        self.calls += 1
        if system == explain.SYSTEM:
            inp = json.loads(user.split("\n", 1)[1])
            events = []
            for e in inp["events"]:
                cid = next(c["cause_id"] for c in inp["cause_table"] if c["pattern"] == e["pattern"])
                events.append({"event_id": e["event_id"], "pattern": e["pattern"], "rule": e["rule"],
                               "checks": [{"cause_id": cid, "reason": "이유"}]})
            out = {"summary": "요약", "events": events, "priority": [e["event_id"] for e in inp["events"]]}
            return LLMReply(json.dumps(out, ensure_ascii=False), None, 0.01, None)
        if model["name"] == "gpt-6-sol":
            return LLMReply("깨진 출력", None, 0.01, None)
        return LLMReply('{"detections": []}', None, 0.01, None)


def failing_llm(model, system, user):
    return LLMReply(None, "APIConnectionError: down", 0.0, None)


def test_run_all_with_fake_llm(tmp_path):
    fake, paths = FakeLLM(), Paths.under(tmp_path)
    m = run_all(fake, paths)
    explained = m["explain"]["series_called"]
    enabled = [d for d in config.DETECT_MODELS if d["enabled"]]
    assert fake.calls == explained * config.EXPLAIN_MODEL["repeats"] + sum(d["repeats"] * 20 for d in enabled)
    assert m["explain"]["passed"] == m["explain"]["outputs"] == explained * config.EXPLAIN_MODEL["repeats"]
    assert m["rules"]["detected"] == m["rules"]["injected"] == 21  # 규칙은 심은 이상을 모두 찾는다
    by_model = {d["model"]: d for d in m["detect"]}
    assert all(r["rate"] == 0 for r in by_model["gpt-4.1-mini"]["runs"])  # 빈 결과 → 탐지 0
    assert all(r["format_violations"] == 20 for r in by_model["gpt-6-sol"]["runs"])
    for p in (paths.series, paths.explanations, paths.detections, paths.metrics, paths.report, paths.ai_errors):
        assert p.exists(), p
    log = paths.ai_errors.read_text(encoding="utf-8")
    assert log.startswith("# LLM 오류 기록") and "JSON 형식 위반" in log and "놓침" in log


def test_cache_avoids_repeat_calls_and_log_is_not_duplicated(tmp_path):
    paths = Paths.under(tmp_path)
    run_all(FakeLLM(), paths)
    log = paths.ai_errors.read_text(encoding="utf-8")
    fake = FakeLLM()
    run_all(fake, paths)
    assert fake.calls == 0  # 전부 캐시에서 꺼냄
    assert paths.ai_errors.read_text(encoding="utf-8") == log  # 새 출력이 없으니 섹션도 안 늘어남


def test_force_calls_again_and_appends_new_section(tmp_path):
    paths = Paths.under(tmp_path)
    run_all(FakeLLM(), paths)
    fake = FakeLLM()
    run_all(fake, paths, force=True)
    assert fake.calls > 0
    assert paths.ai_errors.read_text(encoding="utf-8").count("## 실행 ") == 2  # 이전 기록은 지우지 않음


def test_call_errors_are_counted_and_retried_next_time(tmp_path):
    paths = Paths.under(tmp_path)
    m = run_all(failing_llm, paths)
    assert m["explain"]["call_errors"] == m["explain"]["outputs"] > 0
    assert all(r["call_errors"] == 20 for d in m["detect"] for r in d["runs"])
    assert not paths.ai_errors.exists()  # 호출 오류는 LLM 출력 오류가 아니다
    fake = FakeLLM()
    run_all(fake, paths)
    assert fake.calls > 0  # 실패한 호출은 다음 실행에서 다시 부른다


def test_no_llm_rebuilds_report_from_saved_results(tmp_path):
    paths = Paths.under(tmp_path)
    run_all(FakeLLM(), paths)
    paths.report.unlink()
    m = run_all(None, paths)
    assert paths.report.exists() and m["explain"]["outputs"] > 0


def test_script_exits_with_message_without_key(monkeypatch):
    monkeypatch.setattr(llm_client, "get_api_key", lambda: None)
    monkeypatch.setattr(sys, "argv", ["run_experiment.py"])
    with pytest.raises(SystemExit) as exc:
        runpy.run_path(str(config.ROOT / "scripts" / "run_experiment.py"), run_name="__main__")
    assert "OPENAI_API_KEY" in str(exc.value)
```

- [ ] **Step 2: 실패 확인**

Run: `.venv/Scripts/python -m pytest tests/test_experiment.py -v`
Expected: 수집 오류 `ModuleNotFoundError: No module named 'spc_explainer.experiment'`

- [ ] **Step 3: 실험 모듈 구현**

Create `spc_explainer/experiment.py`:

```python
# 오프라인 실험: 가상 데이터 → 규칙 판정 → LLM 설명·단독 판정(반복, 캐시) → 지표·리포트·ai_errors
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

from . import config, explain, generator, llm_detect, report, rules
from .llm_client import LLMReply
from .matching import classify, summarize
from .patterns import KOREAN, PATTERNS, Event

LLMFn = Callable[[dict, str, str], LLMReply]  # (모델 설정, system, user) → 응답. 실패는 예외 대신 error로

AI_ERRORS_HEADER = """# LLM 오류 기록

규칙(CLAUDE.md): LLM이 틀린 출력을 내면 지우지 않고 입력·출력·틀린 점을 여기에 남긴다.

- 입력: 시리즈 번호와 시드로 재현된다 (`data/synthetic/series.json`).
- 출력: 전체 원문은 같은 커밋의 `results/explanations.json`, `results/llm_detections.json`에 있다.
- 단독 판정의 "틀린 점"은 규칙 엔진 판정과 다른 부분이다.
- `scripts/run_experiment.py`가 실행마다 섹션을 덧붙인다. 캐시에서 꺼낸 결과는 다시 적지 않는다.
"""


@dataclass
class Paths:
    """실험이 읽고 쓰는 파일들. 기본값은 저장소 안의 실제 위치."""

    series: Path = config.SERIES_PATH
    explanations: Path = config.EXPLANATIONS_PATH
    detections: Path = config.DETECTIONS_PATH
    metrics: Path = config.METRICS_PATH
    report: Path = config.REPORT_PATH
    ai_errors: Path = config.AI_ERRORS_PATH

    @staticmethod
    def under(root: Path) -> "Paths":
        """테스트용: 모든 파일을 root 아래에 둔다."""
        return Paths(root / "series.json", root / "explanations.json", root / "llm_detections.json",
                     root / "metrics.json", root / "report.md", root / "ai_errors.md")


@dataclass
class Job:
    key: tuple  # (모델 이름, 시리즈 번호 문자열, 반복 번호)
    model: dict
    system: str
    user: str


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _hash(model: dict, system: str, user: str) -> str:
    """캐시 키: 모델·temperature·프롬프트 전체가 같아야 같은 입력으로 본다."""
    raw = "\n\n".join([model["name"], str(model.get("temperature")), system, user])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")


def _run_jobs(jobs: list[Job], llm: LLMFn) -> list[tuple[Job, LLMReply]]:
    """작업들을 동시에 호출한다 (MAX_WORKERS개씩)."""
    if not jobs:
        return []
    with ThreadPoolExecutor(max_workers=config.MAX_WORKERS) as pool:
        replies = list(pool.map(lambda j: llm(j.model, j.system, j.user), jobs))
    return list(zip(jobs, replies))


def _record(run: int, reply: LLMReply, issues: list[dict]) -> dict:
    return {"run": run, "text": reply.text, "error": reply.error, "latency_s": round(reply.latency_s, 2),
            "usage": reply.usage, "issues": issues, "created": _now()}


def _reusable(prev: dict, h: str, force: bool) -> dict:
    """캐시에서 다시 쓸 반복 {반복 번호: 기록}. 입력이 달라졌거나 호출 오류였던 반복은 버린다."""
    if force or prev.get("input_hash") != h:
        return {}
    return {r["run"]: r for r in prev.get("runs", []) if r["error"] is None}


def _error_row(kind: str, model: str, sid: str, run: int, types: str, detail: str, text: str | None) -> dict:
    excerpt = (text or "").replace("\n", " ").replace("`", "'")[:160]
    return {"kind": kind, "model": model, "series": sid, "run": run, "types": types,
            "detail": detail[:300], "excerpt": excerpt}


def run_explanations(dataset: dict, llm: LLMFn, cache: dict, force: bool = False) -> tuple[dict, list[dict]]:
    """사건이 있는 시리즈마다 설명을 repeats번 받는다. (저장할 결과, 새로 받은 출력의 오류 목록)."""
    model = config.EXPLAIN_MODEL
    old = cache.get("series", {}) if cache.get("prompt_version") == explain.PROMPT_VERSION else {}
    out = {"prompt_version": explain.PROMPT_VERSION, "model": model, "series": {}}
    jobs = []
    for s in dataset["series"]:
        events = rules.detect(s["values"])
        if not events:
            continue  # 이상 없음 → LLM을 부르지 않는다
        sid = str(s["id"])
        inp = explain.build_input(s["values"], events)
        system, user = explain.build_messages(inp)
        h = _hash(model, system, user)
        runs = _reusable(old.get(sid, {}), h, force)
        out["series"][sid] = {"input": inp, "input_hash": h, "runs": runs}
        jobs += [Job((model["name"], sid, k), model, system, user) for k in range(model["repeats"]) if k not in runs]
    errors = []
    for job, reply in _run_jobs(jobs, llm):
        _, sid, k = job.key
        entry = out["series"][sid]
        issues = explain.validate(reply.text, entry["input"])[1] if reply.error is None else []
        entry["runs"][k] = _record(k, reply, issues)
        if issues:
            types = ", ".join(sorted({explain.ISSUE_KO[i["type"]] for i in issues}))
            detail = "; ".join(i["detail"] for i in issues)
            errors.append(_error_row("설명", model["name"], sid, k, types, detail, reply.text))
    for entry in out["series"].values():
        entry["runs"] = [entry["runs"][k] for k in sorted(entry["runs"])]
    return out, errors


def _detect_mistakes(reference: list[Event], found: list[Event]) -> str:
    """단독 판정 출력이 규칙 엔진 판정과 다른 점. 같으면 빈 문자열."""
    detected, kinds = classify(reference, found)
    parts = [f"놓침 {KOREAN[r.pattern]} {r.start}~{r.end}번" for r, hit in zip(reference, detected) if not hit]
    label = {"confusion": "패턴 다름", "false": "없는 사건"}
    parts += [f"{label[k]} {KOREAN[f.pattern]} {f.start}~{f.end}번" for f, k in zip(found, kinds) if k != "hit"]
    return "; ".join(parts)


def run_detections(dataset: dict, llm: LLMFn, cache: dict, force: bool = False) -> tuple[dict, list[dict]]:
    """켜진 모델마다 모든 시리즈를 repeats번 단독 판정한다. (저장할 결과, 새로 받은 출력의 오류 목록)."""
    same_version = cache.get("prompt_version") == llm_detect.PROMPT_VERSION
    out = {"prompt_version": llm_detect.PROMPT_VERSION, "models": {}}
    reference = {str(s["id"]): rules.detect(s["values"]) for s in dataset["series"]}
    jobs = []
    for model in [m for m in config.DETECT_MODELS if m["enabled"]]:
        old = cache.get("models", {}).get(model["name"], {}).get("series", {}) if same_version else {}
        entry = {"config": model, "series": {}}
        for s in dataset["series"]:
            sid = str(s["id"])
            system, user = llm_detect.build_messages(s["values"])
            h = _hash(model, system, user)
            runs = _reusable(old.get(sid, {}), h, force)
            entry["series"][sid] = {"input_hash": h, "runs": runs}
            jobs += [Job((model["name"], sid, k), model, system, user) for k in range(model["repeats"]) if k not in runs]
        out["models"][model["name"]] = entry
    errors = []
    for job, reply in _run_jobs(jobs, llm):
        name, sid, k = job.key
        events, issues = llm_detect.parse(reply.text) if reply.error is None else ([], [])
        rec = _record(k, reply, issues)
        rec["events"] = [e.to_dict() for e in events]
        out["models"][name]["series"][sid]["runs"][k] = rec
        if reply.error is not None:
            continue  # 호출 오류는 LLM 출력 오류가 아니므로 ai_errors에 적지 않는다
        if issues:
            errors.append(_error_row("단독 판정", name, sid, k, "JSON 형식 위반", issues[0]["detail"], reply.text))
        else:
            detail = _detect_mistakes(reference[sid], events)
            if detail:
                errors.append(_error_row("단독 판정", name, sid, k, "판정 오류", detail, reply.text))
    for entry in out["models"].values():
        for s in entry["series"].values():
            s["runs"] = [s["runs"][k] for k in sorted(s["runs"])]
    return out, errors


def append_ai_errors(errors: list[dict], path: Path, label: str) -> None:
    """새 오류를 실행 단위 섹션으로 덧붙인다. 기존 내용은 지우지 않는다."""
    if not errors:
        return
    text = path.read_text(encoding="utf-8") if path.exists() else AI_ERRORS_HEADER
    rows = ["", f"## 실행 {label}", "",
            "| 구분 | 모델 | 시리즈 | 반복 | 유형 | 틀린 점 | 출력 발췌 |", "|---|---|---|---|---|---|---|"]
    for e in errors:
        cells = [e["kind"], e["model"], e["series"], str(e["run"] + 1), e["types"], e["detail"], "`" + e["excerpt"] + "`"]
        rows.append("| " + " | ".join(c.replace("|", "\\|") for c in cells) + " |")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip("\n") + "\n" + "\n".join(rows) + "\n", encoding="utf-8")


def _explain_metrics(explanations: dict) -> dict | None:
    series = explanations.get("series") or {}
    if not series:
        return None
    model = explanations["model"]
    outputs = passed = call_errors = changed = 0
    issue_outputs = {"format": 0, "cause": 0, "mismatch": 0}
    for entry in series.values():
        signatures = set()
        for r in entry["runs"]:
            outputs += 1
            if r["error"] is not None:
                call_errors += 1
                continue
            types = {i["type"] for i in r["issues"]}
            for t in types:
                issue_outputs[t] += 1
            passed += int(not types)
            signatures.add(explain.signature(explain.validate(r["text"], entry["input"])[0]))
        changed += int(len(signatures) > 1)
    return {"model": model["name"], "temperature": model.get("temperature"), "repeats": model["repeats"],
            "prompt_version": explanations.get("prompt_version"), "series_called": len(series),
            "outputs": outputs, "passed": passed, "issue_outputs": issue_outputs,
            "call_errors": call_errors, "repeat_changed_series": changed}


def _detect_metrics(detections: dict, series: list[dict], truths: list[list[Event]]) -> list[dict]:
    result = []
    for name, entry in (detections.get("models") or {}).items():
        cfg = entry["config"]
        runs = []
        for k in range(cfg["repeats"]):
            founds, fmt, err = [], 0, 0
            for s in series:
                recs = entry["series"].get(str(s["id"]), {}).get("runs", [])
                rec = next((r for r in recs if r["run"] == k), None)
                if rec is None or rec["error"] is not None:
                    err += 1  # 결과가 없거나 호출 오류 → 탐지 0개로 채점
                    founds.append([])
                    continue
                fmt += int(bool(rec["issues"]))
                founds.append([Event.from_dict(e) for e in rec["events"]])
            runs.append(dict(summarize(truths, founds), format_violations=fmt, call_errors=err))
        result.append({"model": name, "temperature": cfg.get("temperature"), "repeats": cfg["repeats"],
                       "prompt_version": detections.get("prompt_version"), "runs": runs})
    return result


def compute_metrics(dataset: dict, explanations: dict, detections: dict) -> dict:
    """저장된 결과로 리포트용 지표를 계산한다 (LLM을 부르지 않는다)."""
    series = dataset["series"]
    truths = [generator.truth_events(s) for s in series]
    return {
        "generated_at": _now(),
        "dataset": {
            "seed": dataset["seed"],
            "n_series": len(series),
            "n_normal": sum(1 for t in truths if not t),
            "n_points": len(series[0]["values"]),
            "injected": {p: sum(1 for t in truths for e in t if e.pattern == p) for p in PATTERNS},
        },
        "rules": summarize(truths, [rules.detect(s["values"]) for s in series]),
        "detect": _detect_metrics(detections, series, truths),
        "explain": _explain_metrics(explanations),
        "secom": None,
    }


def run_all(llm: LLMFn | None, paths: Paths | None = None, force: bool = False) -> dict:
    """전체 실험. llm이 None이면 LLM을 부르지 않고 저장된 결과로 지표·리포트만 다시 만든다."""
    paths = paths or Paths()
    dataset = generator.generate_dataset()
    generator.save_dataset(dataset, paths.series)
    explanations = _read_json(paths.explanations)
    detections = _read_json(paths.detections)
    if llm is not None:
        explanations, explain_errors = run_explanations(dataset, llm, explanations, force)
        detections, detect_errors = run_detections(dataset, llm, detections, force)
        _write_json(paths.explanations, explanations)
        _write_json(paths.detections, detections)
        label = f"{_now()} (설명 {explain.PROMPT_VERSION}, 단독 판정 {llm_detect.PROMPT_VERSION})"
        append_ai_errors(explain_errors + detect_errors, paths.ai_errors, label)
    metrics = compute_metrics(dataset, explanations, detections)
    _write_json(paths.metrics, metrics)
    report.write(metrics, paths.report)
    return metrics
```

- [ ] **Step 4: 실행 스크립트 구현**

Create `scripts/run_experiment.py`:

```python
# 실험 실행: 가상 데이터 → 규칙 판정 → LLM 설명·단독 판정(캐시 사용) → 지표·리포트·ai_errors
# 사용법: python scripts/run_experiment.py [--no-llm] [--force]
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # 저장소 루트를 import 경로에 추가

from spc_explainer import experiment, llm_client  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="SPC 설명기 검증 실험")
    parser.add_argument("--no-llm", action="store_true", help="LLM을 부르지 않고 저장된 결과로 지표·리포트만 다시 만든다")
    parser.add_argument("--force", action="store_true", help="캐시를 무시하고 LLM을 다시 부른다")
    args = parser.parse_args()
    llm = None
    if not args.no_llm:
        if not llm_client.get_api_key():
            sys.exit("OPENAI_API_KEY가 없습니다. .env를 확인하거나 --no-llm으로 실행하세요.")
        llm = llm_client.call_json
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # 윈도 콘솔에서도 한글이 깨지지 않게
    m = experiment.run_all(llm, force=args.force)
    print(f"규칙 탐지 {m['rules']['detected']}/{m['rules']['injected']}")
    for d in m["detect"]:
        rates = ", ".join("-" if r["rate"] is None else f"{r['rate']:.0%}" for r in d["runs"])
        fmt = sum(r["format_violations"] for r in d["runs"])
        err = sum(r["call_errors"] for r in d["runs"])
        print(f"단독 판정 {d['model']}: 반복별 탐지율 {rates} (형식 위반 {fmt}, 호출 오류 {err})")
    e = m["explain"]
    if e:
        io = e["issue_outputs"]
        print(f"설명 출력 {e['outputs']}개 중 통과 {e['passed']} (형식 위반 {io['format']}, 원인표 밖 {io['cause']}, "
              f"판정 불일치 {io['mismatch']}, 호출 오류 {e['call_errors']}, 반복 간 차이 {e['repeat_changed_series']}개 시리즈)")
    print(f"리포트: {experiment.Paths().report}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: 통과 확인**

Run: `.venv/Scripts/python -m pytest tests/test_experiment.py -v`
Expected: 6 passed

Run: `.venv/Scripts/python -m pytest -q`
Expected: 전체 통과 (지금까지 50개)

- [ ] **Step 6: 커밋**

```bash
git add spc_explainer/experiment.py scripts/run_experiment.py tests/test_experiment.py
git commit -m "feat: 반복 호출·캐시·지표·ai_errors 실험 실행기" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
git push origin main
```

---

### Task 10: 실제 실험 실행과 결과 커밋 (API 호출)

**Files:**
- Create (스크립트 산출물): `data/synthetic/series.json`, `results/explanations.json`, `results/llm_detections.json`, `results/metrics.json`, `docs/validation_report.md`
- Modify (스크립트가 덧붙임): `docs/ai_errors.md` (설계 때 만든 스모크 호출 기록 아래에 실행 섹션이 붙는다)

**Interfaces:**
- Consumes: `scripts/run_experiment.py` (Task 9), `.env`의 `OPENAI_API_KEY`
- Produces: 앱이 읽는 캐시 파일들 (Task 11)

- [ ] **Step 1: 실험 실행**

Run: `.venv/Scripts/python scripts/run_experiment.py`
Expected (수치는 실행마다 다름, 형태만):

```text
규칙 탐지 21/21
단독 판정 gpt-4.1-mini: 반복별 탐지율 ..%, ..%, ..% (형식 위반 N, 호출 오류 0)
단독 판정 gpt-6-sol: 반복별 탐지율 ..%, ..%, ..% (형식 위반 N, 호출 오류 0)
설명 출력 N개 중 통과 N (형식 위반 N, 원인표 밖 N, 판정 불일치 N, 호출 오류 0, 반복 간 차이 N개 시리즈)
```

호출 수는 168회(설명 16개 시리즈 × 3 = 48, 단독 판정 4.1-mini 60, sol 60). 설계 때 스모크 호출에서 sol은 회당 약 10초, 4.1-mini는 3~8초였으므로 동시 6개로 몇 분 걸린다.

- [ ] **Step 2: 호출 오류가 있으면 다시 실행**

호출 오류가 0이 아니면 같은 명령을 다시 실행한다. 성공한 결과는 캐시에서 꺼내고 실패한 호출만 다시 보낸다. 두 번 해도 남으면 오류 문구(`results/*.json`의 `error`)를 확인한다. `gpt-6-sol`이 권한 오류면 사용자에게 보고한다.

- [ ] **Step 3: 결과 점검**

- `docs/validation_report.md`를 열어 6개 섹션과 표가 채워졌는지 본다.
- `docs/ai_errors.md`에서 설명 오류 항목 2~3개를 골라 `results/explanations.json`의 원문과 대조해, 검증기가 제대로 잡았는지 확인한다.
- 설명 출력의 30% 이상이 같은 형식 위반이면 프롬프트가 모호할 가능성이 크다. 원문을 보고 `explain.SYSTEM`을 고친 뒤 `PROMPT_VERSION`을 `"explain-v2"`로 올리고 다시 실행한다. v1 오류 기록은 `ai_errors.md`에 남는다(덧붙이기). 이 경우 사용자에게 무엇을 고쳤는지 보고한다.

- [ ] **Step 4: 전체 테스트 재확인**

Run: `.venv/Scripts/python -m pytest -q`
Expected: 전체 통과

- [ ] **Step 5: 커밋**

```bash
git status --short   # .env가 없어야 함
git add data/synthetic/series.json results/ docs/validation_report.md docs/ai_errors.md
git commit -m "chore: 검증 실험 실행 결과 (가상 데이터, LLM 캐시, 리포트, ai_errors)" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
git push origin main
```

---

### Task 11: 관리도 그림과 Streamlit 화면

**Files:**
- Create: `spc_explainer/charts.py`, `tests/test_charts.py`, `tests/test_app.py`
- Modify: `streamlit_app.py` (전체 교체)

**Interfaces:**
- Consumes: `config`, `explain.build_input/build_messages/validate/ISSUE_KO`, `generator.generate_dataset/truth_events`, `llm_client.call_json/get_api_key`, `rules.detect/describe`, `causes.CAUSES`, `patterns.KOREAN`, 캐시 파일(Task 10)
- Produces:
  - `charts.control_chart(values, events, center, ucl, lcl, truth=None, phase_boundary=None, fail_idx=None, y_title="") -> plotly Figure` — SECOM 탭(Task 13)도 사용
  - 앱 탭 변수 `tab_main`, `tab_report` (Task 13이 탭을 하나 더한다)

- [ ] **Step 1: 실패하는 테스트 작성**

Create `tests/test_charts.py`:

```python
# 관리도 그림: 필요한 선·점·음영이 들어가는지
from spc_explainer.charts import control_chart
from spc_explainer.patterns import Event


def test_chart_traces_and_shapes():
    values = [100.0] * 20
    values[5] = 104.0
    fig = control_chart(values, [Event("spike", 5, 5, "up")], 100, 103, 97,
                        truth=[Event("spike", 5, 5, "up")], phase_boundary=10, fail_idx=[3])
    assert [t.name for t in fig.data] == ["측정값", "규칙: 급변", "불량 라벨"]
    assert len(fig.layout.shapes) == 5  # 한계선 3 + 정답 음영 1 + Phase 경계 1


def test_chart_without_events():
    fig = control_chart([100.0] * 10, [], 100, 103, 97)
    assert [t.name for t in fig.data] == ["측정값"]
```

Create `tests/test_app.py`:

```python
# 앱이 예외 없이 그려지는지 (Streamlit AppTest, 네트워크 없음)
from pathlib import Path

from streamlit.testing.v1 import AppTest

from spc_explainer import config, llm_client

APP = str(Path(__file__).resolve().parent.parent / "streamlit_app.py")


def run_app() -> AppTest:
    return AppTest.from_file(APP, default_timeout=60).run()


def test_app_renders_and_switches_series():
    at = run_app()
    assert not at.exception
    assert at.title[0].value == "SPC 설명기"
    for sid in (0, 5, 14, 19):
        at.selectbox[0].set_value(sid).run()
        assert not at.exception, sid


def test_app_without_saved_files(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "SERIES_PATH", tmp_path / "none.json")
    monkeypatch.setattr(config, "EXPLANATIONS_PATH", tmp_path / "none2.json")
    monkeypatch.setattr(config, "REPORT_PATH", tmp_path / "none.md")
    at = run_app()
    assert not at.exception
    at.selectbox[0].set_value(5).run()  # 급변을 심은 시리즈 → 규칙 사건은 있음
    assert not at.exception
    assert any("저장된 설명이 없습니다" in m.value for m in at.info)
    assert any("리포트가 아직 없습니다" in m.value for m in at.info)


def test_live_button_disabled_without_key(monkeypatch):
    monkeypatch.setattr(llm_client, "get_api_key", lambda: None)
    at = run_app()
    at.selectbox[0].set_value(5).run()
    assert not at.exception
    assert at.button[0].proto.disabled
```

- [ ] **Step 2: 실패 확인**

Run: `.venv/Scripts/python -m pytest tests/test_charts.py tests/test_app.py -v`
Expected: test_charts는 수집 오류 `No module named 'spc_explainer.charts'`, test_app은 임시 페이지라 `at.selectbox[0]`에서 IndexError로 실패

- [ ] **Step 3: 그림 구현**

Create `spc_explainer/charts.py`:

```python
# 관리도 그림(plotly). 가상 데이터 탭과 SECOM 탭이 같이 쓴다.
import plotly.graph_objects as go

from .patterns import KOREAN, PATTERNS, Event

COLORS = {"spike": "#d62728", "trend": "#ff7f0e", "shift": "#9467bd"}


def control_chart(values, events: list[Event], center: float, ucl: float, lcl: float,
                  truth: list[Event] | None = None, phase_boundary: int | None = None,
                  fail_idx: list[int] | None = None, y_title: str = "") -> go.Figure:
    """측정값 + 중심선·한계선 + 규칙 사건(패턴별 색) + 정답 구간 음영 + (선택) Phase 경계·불량 표시."""
    xs = list(range(len(values)))
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=xs, y=list(values), mode="lines+markers", name="측정값",
                             line={"color": "#9e9e9e", "width": 1}, marker={"size": 4, "color": "#616161"}))
    for label, y, dash in (("UCL", ucl, "dash"), ("중심선", center, "solid"), ("LCL", lcl, "dash")):
        fig.add_hline(y=y, line_dash=dash, line_color="#1f77b4" if label == "중심선" else "#d62728",
                      annotation_text=f"{label} {y:.4g}", annotation_position="top right")
    for t in truth or []:
        fig.add_vrect(x0=t.start - 0.5, x1=t.end + 0.5, fillcolor="#2ca02c", opacity=0.12, line_width=0)
    for p in PATTERNS:
        idx = sorted({i for e in events if e.pattern == p for i in range(e.start, e.end + 1)})
        if idx:
            fig.add_trace(go.Scatter(x=idx, y=[values[i] for i in idx], mode="markers", name=f"규칙: {KOREAN[p]}",
                                     marker={"color": COLORS[p], "size": 9}))
    if fail_idx:
        fig.add_trace(go.Scatter(x=list(fail_idx), y=[values[i] for i in fail_idx], mode="markers", name="불량 라벨",
                                 marker={"symbol": "x", "color": "black", "size": 7}))
    if phase_boundary is not None:
        fig.add_vline(x=phase_boundary - 0.5, line_dash="dot", line_color="#555555",
                      annotation_text="Phase I | Phase II", annotation_position="top")
    fig.update_layout(height=420, margin={"l": 10, "r": 10, "t": 30, "b": 10}, legend={"orientation": "h"},
                      xaxis_title="점 번호 (0부터)", yaxis_title=y_title)
    return fig
```

- [ ] **Step 4: 화면 구현**

Modify `streamlit_app.py` — 전체를 다음으로 교체:

```python
# SPC 설명기 화면. 판정은 규칙 엔진, 설명은 LLM(저장된 결과 우선, 실시간 호출은 횟수 제한).
import json
import os
from datetime import date

import pandas as pd
import streamlit as st

from spc_explainer import config, explain, generator, llm_client, rules
from spc_explainer.causes import CAUSES
from spc_explainer.charts import control_chart
from spc_explainer.patterns import KOREAN

st.set_page_config(page_title="SPC 설명기", layout="wide")

# 배포 환경: Streamlit Secrets의 키를 환경변수로 옮긴다 (로컬은 llm_client가 .env를 읽는다)
try:
    if "OPENAI_API_KEY" in st.secrets and not os.environ.get("OPENAI_API_KEY"):
        os.environ["OPENAI_API_KEY"] = st.secrets["OPENAI_API_KEY"]
except Exception:  # secrets.toml이 없는 로컬 실행
    pass


@st.cache_data
def load_json(path):
    """JSON 파일을 읽는다. 없으면 None."""
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


@st.cache_data
def load_text(path):
    return path.read_text(encoding="utf-8") if path.exists() else None


@st.cache_resource
def daily_counter() -> dict:
    """서버 프로세스 전체가 공유하는 오늘의 실시간 호출 수 (앱이 재시작되면 초기화)."""
    return {"date": date.today(), "n": 0}


def series_label(s: dict) -> str:
    kinds = [KOREAN[a["pattern"]] for a in s["anomalies"]]
    kind_text = "정상 (심은 이상 없음)" if not kinds else "심은 이상: " + ", ".join(kinds)
    return f"시리즈 {s['id']:02d} — {kind_text}"


def issue_names(issues: list[dict]) -> str:
    return ", ".join(sorted({explain.ISSUE_KO[i["type"]] for i in issues}))


def show_explanation(text, inp: dict) -> None:
    """설명 출력 하나를 검증 결과와 함께 보여준다. 판정은 항상 규칙 결과가 기준."""
    data, issues = explain.validate(text, inp)
    if issues:
        lines = [f"- {explain.ISSUE_KO[i['type']]}: {i['detail']}" for i in issues]
        st.error("검증에서 문제가 발견됐습니다. 판정은 위 규칙 결과를 따르세요.\n\n" + "\n".join(lines))
    else:
        st.success("검증 통과: JSON 형식, 원인표, 규칙 판정과 모두 일치")
    if not isinstance(data, dict):
        st.code(text or "", language="json")
        return
    st.markdown(f"**요약** {data.get('summary', '')}")
    priority = data.get("priority") if isinstance(data.get("priority"), list) else []
    if priority:
        st.markdown("**점검 순서** " + " → ".join(map(str, priority)))
    events = data.get("events") if isinstance(data.get("events"), list) else []
    for ev in events:
        if not isinstance(ev, dict):
            continue
        st.markdown(f"**{ev.get('event_id')} · {ev.get('pattern')}** — {ev.get('rule', '')}")
        checks = ev.get("checks") if isinstance(ev.get("checks"), list) else []
        for n, c in enumerate(checks, start=1):
            if not isinstance(c, dict):
                continue
            cid = c.get("cause_id")
            row = CAUSES.get(cid, {}) if isinstance(cid, str) else {}
            cause = row.get("cause", "(원인표에 없음)")
            check = row.get("check", "-")
            st.markdown(f"{n}. `{cid}` {cause} — 점검: {check}  \n이유: {c.get('reason', '')}")


st.title("SPC 설명기")
st.caption(
    f"{config.PROCESS_NAME} 관리도에서 판정은 규칙 엔진(pycontrolcharts), 설명은 LLM이 맡습니다. "
    f"관리한계 고정값({config.LCL:g}~{config.UCL:g}{config.UNIT}) 사용 = 이미 안정화된 공정을 감시하는 상황을 가정합니다."
)
tab_main, tab_report = st.tabs(["판정·설명", "검증 리포트"])

with tab_main:
    dataset = load_json(config.SERIES_PATH) or generator.generate_dataset()
    series = dataset["series"]
    sid = st.selectbox("시리즈", range(len(series)), format_func=lambda i: series_label(series[i]))
    s = series[sid]
    values = s["values"]
    events = rules.detect(values)
    show_truth = st.toggle("정답(심은 이상) 구간 표시", value=True)
    truth = generator.truth_events(s) if show_truth else None
    fig = control_chart(values, events, config.CENTER, config.UCL, config.LCL, truth=truth,
                        y_title=f"{config.PROCESS_NAME} ({config.UNIT})")
    st.plotly_chart(fig, width="stretch")

    if not events:
        st.success("규칙 판정: 이상 없음 — LLM을 호출하지 않습니다.")
    else:
        st.subheader("규칙 판정")
        table = [{"사건": f"E{i}", "패턴": KOREAN[e.pattern], "구간": f"{e.start}~{e.end}",
                  "근거 규칙": rules.describe(e, values)} for i, e in enumerate(events, start=1)]
        st.dataframe(pd.DataFrame(table), hide_index=True, width="stretch")

        st.subheader("LLM 설명")
        model = config.EXPLAIN_MODEL
        inp = explain.build_input(values, events)
        saved = load_json(config.EXPLANATIONS_PATH) or {}
        cached = (saved.get("series") or {}).get(str(sid))
        if not cached or not cached.get("runs"):
            st.info("저장된 설명이 없습니다. `python scripts/run_experiment.py`로 만들 수 있습니다.")
        else:
            if cached["input"] != inp:
                st.warning("저장된 설명의 입력이 현재 규칙 판정과 다릅니다. 실험을 다시 돌려야 합니다.")
            runs = cached["runs"]
            st.caption(f"저장된 결과 · {model['name']} · 같은 입력 {len(runs)}회 중 1회차")
            if runs[0]["error"]:
                st.error(f"호출 오류: {runs[0]['error']}")
            else:
                show_explanation(runs[0]["text"], cached["input"])
            with st.expander(f"같은 입력 {len(runs)}회 반복 결과"):
                for r in runs:
                    if r["error"]:
                        st.markdown(f"**{r['run'] + 1}회차** · 호출 오류")
                        continue
                    data, issues = explain.validate(r["text"], cached["input"])
                    status = issue_names(issues) if issues else "검증 통과"
                    order = data.get("priority") if isinstance(data, dict) else None
                    order_text = " → ".join(map(str, order)) if isinstance(order, list) and order else "-"
                    st.markdown(f"**{r['run'] + 1}회차** · {status} · 점검 순서 {order_text}")

        # 실시간 설명: 세션당·하루 호출 수를 제한하고, 키가 없으면 끈다
        counter = daily_counter()
        if counter["date"] != date.today():
            counter.update(date=date.today(), n=0)
        used = st.session_state.get("live_used", 0)
        left = max(0, min(config.LIVE_CALLS_PER_SESSION - used, config.LIVE_CALLS_PER_DAY - counter["n"]))
        has_key = bool(llm_client.get_api_key())
        clicked = st.button(f"실시간 설명 받기 ({model['name']}, 남은 횟수 {left})", key="live_button",
                            disabled=not has_key or left == 0)
        if not has_key:
            st.caption("API 키가 설정되지 않아 실시간 설명은 꺼져 있습니다. 저장된 결과는 위에서 볼 수 있습니다.")
        if clicked:
            st.session_state["live_used"] = used + 1
            counter["n"] += 1
            with st.spinner("LLM 호출 중…"):
                st.session_state["live"] = (sid, llm_client.call_json(model, *explain.build_messages(inp)))
        live = st.session_state.get("live")
        if live and live[0] == sid:
            reply = live[1]
            st.caption(f"실시간 결과 · {model['name']} · {reply.latency_s:.1f}초")
            if reply.error:
                st.error(f"호출 오류: {reply.error}")
            else:
                show_explanation(reply.text, inp)

with tab_report:
    report_md = load_text(config.REPORT_PATH)
    if report_md:
        st.markdown(report_md)
    else:
        st.info("리포트가 아직 없습니다. `python scripts/run_experiment.py`로 만들 수 있습니다.")
```

- [ ] **Step 5: 통과 확인**

Run: `.venv/Scripts/python -m pytest tests/test_charts.py tests/test_app.py -v`
Expected: 5 passed

Run: `.venv/Scripts/python -m pytest -q`
Expected: 전체 통과

- [ ] **Step 6: 로컬에서 직접 띄워 보기**

Run (백그라운드): `.venv/Scripts/python -m streamlit run streamlit_app.py --server.headless true --server.port 8501`
확인: `curl -s http://localhost:8501/_stcore/health` → `ok`. 브라우저로 시리즈 0, 5, 14번을 열어 그래프·규칙 표·설명·반복 결과·리포트 탭을 눈으로 확인한 뒤 서버를 끈다. 실시간 버튼은 한 번만 눌러 동작을 확인한다(호출 1회).

- [ ] **Step 7: 커밋, 배포 확인**

```bash
git add spc_explainer/charts.py streamlit_app.py tests/test_charts.py tests/test_app.py
git commit -m "feat: 관리도 그림과 Streamlit 화면 (캐시 우선, 실시간 호출 제한)" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
git push origin main
```

푸시하면 Streamlit Community Cloud가 다시 배포한다. 사용자에게 두 가지를 요청한다: (1) 배포 URL을 알려주기(README에 넣음), (2) 실시간 설명을 켜려면 App settings → Secrets에 `OPENAI_API_KEY = "..."` 추가. URL을 받으면 브라우저로 두 탭이 뜨는지 확인한다.

---

> **Task 11-1 ~ 11-4 공통.** 화면 설계 비교(`docs/design/2026-09-25-ui-comparison.md`)의 절충안 C를 5절 순서대로 적용한다. 그래프 스타일 출처는 `docs/design/ref/control-chart.png`(관리도), `docs/design/ref/detection-bars.png`(탐지율 막대).
> - 태스크마다 앱이 동작하는 상태로 커밋한다. 9/26 18시 기준선에 걸리면 그 자리에서 멈춘다 (최악의 경우 Task 11 화면).
> - 화면의 숫자는 결과 파일(`data/synthetic/series.json`, `results/*.json`)에서만 읽는다. 시안의 값(50점, 20건, 60건, 63.3% 등)은 쓰지 않는다. 점 번호는 0부터, 100점.
> - LLM이 만든 문자열은 `ui_html.esc()`를 거쳐 HTML에 넣는다. `st.html`은 iframe 없이 페이지에 바로 들어간다.
> - Task 13(SECOM)이 찾아 바꾸는 세 줄은 그대로 둔다: `from spc_explainer import config, explain, generator, llm_client, rules`, `tab_main, tab_report = st.tabs(["판정·설명", "검증 리포트"])`, 파일 마지막 줄 `st.info("리포트가 아직 없습니다. ...")`. `control_chart`의 기존 인자도 그대로 받는다.
> - 비교 문서 5절의 9번(화면용 가공 함수)은 처음 필요한 곳에서 만든다: 점검 우선순위 펼치기는 11-2의 `ui_steps.py`, KPI·막대·오답 사례는 11-4의 `ui_dashboard.py`.

### Task 11-1: 테마·카드 CSS·머리말 (5절 1~3번)

**Files:**
- Create: `.streamlit/config.toml`, `spc_explainer/ui_html.py`, `tests/test_ui_html.py`
- Modify: `streamlit_app.py`

**Interfaces:**
- Consumes: `config.UNIT`, 데이터셋의 `center`·`ucl`·`lcl` (Task 2)
- Produces:
  - `ui_html.PATTERN_COLORS: dict[str, {"fill": str, "text": str}]`, `ui_html.SYMBOL`(◆▲■), `ui_html.RULE_ID`(spike R1, shift R2, trend R3)
  - `ui_html.esc(text) -> str`, `ui_html.span_text(start: int, end: int) -> str` (`#14`, `#45–52`)
  - `ui_html.header_html(center, ucl, lcl, unit) -> str`, `ui_html.CSS: str`
  - 카드 키(= CSS 클래스 `st-key-<키>`): `chart_card`, `rule_card`, `ai_card`, `ai_body`, `ai_warn`, `ai_runs`, `ai_foot`, `kpi_rule`, `kpi_llm`, `kpi_ai`, `bars_card`, `cases_card`

- [ ] **Step 1: 실패하는 테스트 작성**

Create `tests/test_ui_html.py`:

```python
# 화면 공통 조각: 머리말 문구, 카드 CSS, 패턴 기호·규칙 번호, 이스케이프
from spc_explainer.ui_html import CSS, PATTERN_COLORS, RULE_ID, SYMBOL, esc, header_html, span_text


def test_header_shows_roles_limits_and_assumption():
    h = header_html(100.0, 103.0, 97.0, "nm")
    assert "판정 · 정확성" in h and "설명 · 해석력" in h
    assert "CL 100.0" in h and "UCL 103.0" in h and "LCL 97.0" in h
    assert "이미 안정화된 공정을 감시하는 상황을 가정" in h


def test_css_targets_keyed_cards():
    for key in ("chart_card", "rule_card", "ai_card", "ai_foot", "kpi_rule", "bars_card", "cases_card"):
        assert f".st-key-{key}" in CSS
    assert CSS.startswith("<style>") and CSS.rstrip().endswith("</style>")


def test_pattern_vocabulary():
    assert RULE_ID == {"spike": "R1", "shift": "R2", "trend": "R3"}  # Nelson 규칙 번호
    assert SYMBOL == {"spike": "◆", "trend": "▲", "shift": "■"}
    assert set(PATTERN_COLORS) == {"spike", "trend", "shift"}


def test_span_and_escape():
    assert span_text(14, 14) == "#14" and span_text(45, 52) == "#45–52"
    assert esc('<b>&"') == "&lt;b&gt;&amp;&quot;"
```

- [ ] **Step 2: 실패 확인**

Run: `.venv/Scripts/python -m pytest tests/test_ui_html.py -v`
Expected: 수집 오류 `ModuleNotFoundError: No module named 'spc_explainer.ui_html'`

- [ ] **Step 3: 테마와 공통 조각 구현**

Create `.streamlit/config.toml`:

```toml
# 화면 테마: Claude Design 시안(docs/design/)의 색·글꼴
[theme]
base = "light"
primaryColor = "#0068a7"
backgroundColor = "#f3f4f5"
secondaryBackgroundColor = "#ffffff"
textColor = "#16191d"
borderColor = "#d9dcdf"
baseRadius = "small"
font = "IBM Plex Sans KR:https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+KR:wght@400;500;600;700&display=swap"
codeFont = "IBM Plex Mono:https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&display=swap"
```

Create `spc_explainer/ui_html.py`:

```python
# 화면 공통 조각: 패턴 색·기호·규칙 번호, 전역 CSS, 머리말 HTML.
# 스타일 출처: Claude Design 시안(docs/design/). LLM이 만든 문자열은 반드시 esc()를 거쳐 넣는다
# (st.html은 iframe 없이 페이지에 바로 들어간다).
import html

PATTERN_COLORS = {
    "spike": {"fill": "#d02c2a", "text": "#b7191c"},
    "trend": {"fill": "#c5770f", "text": "#915200"},
    "shift": {"fill": "#8048b6", "text": "#703ba1"},
}
SYMBOL = {"spike": "◆", "trend": "▲", "shift": "■"}
RULE_ID = {"spike": "R1", "shift": "R2", "trend": "R3"}  # Nelson 규칙 번호


def esc(text) -> str:
    """HTML 특수문자를 이스케이프한다."""
    return html.escape(str(text), quote=True)


def span_text(start: int, end: int) -> str:
    """구간 표기: #14 또는 #45–52 (점 번호는 0부터)."""
    return f"#{start}" if start == end else f"#{start}–{end}"


def header_html(center: float, ucl: float, lcl: float, unit: str) -> str:
    """제목 아래 머리말: 역할 띠(규칙 → AI) + 관리 기준 + 고정 한계 가정."""
    return (
        '<div class="spc-top">'
        '<span class="spc-roles"><span class="b-rule">규칙</span>판정 · 정확성'
        '<span class="spc-arrow-s">→</span><span class="b-ai">AI</span>설명 · 해석력</span>'
        f"<span>관리 기준 <b>CL {center:.1f}</b> · <b>UCL {ucl:.1f}</b> · <b>LCL {lcl:.1f}</b> {esc(unit)}</span>"
        '<span class="spc-note">관리한계 고정값 사용 = 이미 안정화된 공정을 감시하는 상황을 가정</span>'
        "</div>"
    )


CSS = """<style>
/* ── 카드: 키 달린 st.container에 Streamlit이 붙이는 st-key-* 클래스를 꾸민다 ── */
.st-key-chart_card, .st-key-bars_card, .st-key-cases_card,
.st-key-kpi_rule, .st-key-kpi_llm, .st-key-kpi_ai {
  background: #ffffff !important; border: 1px solid #d9dcdf !important; border-radius: 4px !important;
  padding: 16px 20px !important; gap: 8px !important;
}
.st-key-rule_card {
  background: #ffffff !important; border: 1px solid #16191d !important; border-radius: 4px !important;
  padding: 0 !important; gap: 0 !important; overflow: hidden;
}
.st-key-ai_card {
  background: #f7fbfe !important; border: 1px dashed #6da4d3 !important; border-radius: 4px !important;
  padding: 0 !important; gap: 0 !important; overflow: hidden;
}
.st-key-ai_body, .st-key-ai_warn, .st-key-ai_runs { padding: 10px 18px !important; }
.st-key-ai_foot { padding: 8px 18px !important; border-top: 1px solid #e3e5e8 !important; }

/* ── 머리말 ── */
.spc-top { display: flex; flex-wrap: wrap; align-items: center; gap: 8px 28px; font-size: 13px; color: #4d545c; }
.spc-top b { color: #16191d; font-weight: 600; }
.spc-roles { display: inline-flex; align-items: center; gap: 8px; }
.spc-arrow-s { color: #8a9098; }
.spc-note { font-size: 12px; color: #6b727b; }
.b-rule { font-size: 11px; font-weight: 600; background: #16191d; color: #fff; padding: 2px 7px; border-radius: 3px; }
.b-ai { font-size: 11px; font-weight: 600; background: #dff1ff; color: #00508e; border: 1px solid #92c4ee;
  padding: 1px 7px; border-radius: 3px; }
.b-ai-solid { font-size: 11px; font-weight: 600; background: #0068a7; color: #fff; padding: 2px 7px; border-radius: 3px; }
.spc-mono { font-family: 'IBM Plex Mono', monospace; }

/* ── 관리도 머리말·꼬리말 ── */
.spc-chart-head { display: flex; flex-wrap: wrap; align-items: baseline; gap: 6px 16px; }
.spc-chart-title { font-size: 16px; font-weight: 600; }
.spc-chart-stats { display: inline-flex; gap: 14px; font-family: 'IBM Plex Mono', monospace; font-size: 12.5px; color: #4d545c; }
.spc-chart-legend { margin-left: auto; display: inline-flex; flex-wrap: wrap; align-items: center; gap: 16px; font-size: 13px; }
.spc-lg-line { display: inline-block; width: 18px; border-top: 1.5px dashed #5b626b; margin-right: 5px; vertical-align: middle; }
.spc-lg-truth { display: inline-block; width: 12px; height: 12px; border: 1.5px dotted #16191d; margin-right: 5px;
  vertical-align: middle; }
.spc-chart-foot { display: flex; justify-content: space-between; gap: 8px; font-size: 12px; color: #5b626b; }

/* ── STEP 카드 ── */
.spc-step-head { display: flex; flex-wrap: wrap; align-items: center; gap: 8px 10px; padding: 12px 18px; }
.spc-step-head b { font-size: 16px; font-weight: 600; }
.spc-step-head.rule { background: #16191d; color: #fff; }
.spc-step-head.ai { color: #004072; }
.spc-step { font-size: 12px; opacity: .75; }
.spc-muted { font-size: 12px; }
.spc-step-head.rule .spc-muted { color: #c9cdd2; }
.spc-step-head.ai .spc-muted { color: #4d545c; }
.spc-tag-fixed { font-size: 11px; font-weight: 600; border: 1px solid #6b727b; padding: 1px 7px; border-radius: 3px; }
.spc-tag-ai { font-size: 11px; font-weight: 600; background: #0068a7; color: #fff; padding: 2px 7px; border-radius: 3px; }
.spc-tag-pass { font-size: 11px; font-weight: 600; background: #e7f5ec; color: #1e6b34; border: 1px solid #a3d4b2;
  padding: 1px 7px; border-radius: 3px; }
.spc-tag-fail { font-size: 11px; font-weight: 600; background: #fdecea; color: #b7191c; border: 1px solid #f1a9a5;
  padding: 1px 7px; border-radius: 3px; }
.spc-rule-row { display: grid; grid-template-columns: 92px 84px minmax(0, 1fr) 40px; gap: 10px; padding: 12px 18px;
  border-top: 1px solid #eceef0; font-size: 13.5px; align-items: start; }
.spc-rule-th { background: #f6f7f8; color: #5b626b; font-size: 12px; padding: 8px 18px; border-top: none; }
.spc-rule-row small { display: block; font-size: 12px; color: #5b626b; }
.spc-pat { font-weight: 600; }
.spc-rid { font-size: 12px; font-weight: 600; border: 1px solid #16191d; border-radius: 3px; text-align: center; }
.spc-rule-empty { padding: 14px 18px; font-size: 13.5px; color: #3b424a; }
.spc-foot { display: flex; justify-content: space-between; gap: 8px; background: #f6f7f8; padding: 9px 18px;
  font-size: 12px; color: #4d545c; border-top: 1px solid #eceef0; }
.spc-flow { display: flex; flex-direction: column; align-items: center; gap: 4px; margin-top: 110px; color: #5b626b;
  font-size: 20px; }
.spc-flow small { font-size: 11px; text-align: center; line-height: 1.3; }
.spc-ai-body { display: flex; flex-direction: column; gap: 8px; padding: 12px 18px 14px; }
.spc-label { font-size: 12px; font-weight: 600; color: #5b626b; }
.spc-summary { font-size: 14px; line-height: 1.6; }
.spc-checks { display: grid; grid-template-columns: repeat(auto-fill, minmax(190px, 1fr)); gap: 10px; }
.spc-check { background: #fff; border: 1px solid #cfe3f3; border-radius: 4px; padding: 12px; display: flex;
  flex-direction: column; gap: 5px; }
.spc-check.unknown { border-color: #d02c2a; }
.spc-check-top { display: flex; align-items: center; gap: 4px; }
.spc-rank { width: 22px; height: 22px; background: #0068a7; color: #fff; border-radius: 3px; display: inline-grid;
  place-items: center; font-size: 12px; font-weight: 600; margin-right: 4px; }
.spc-chip { font-family: 'IBM Plex Mono', monospace; font-size: 11px; border: 1px solid #9aa0a7; border-radius: 3px; padding: 0 5px; }
.spc-check-title { font-size: 14px; font-weight: 600; }
.spc-check-cause { font-size: 12px; color: #5b626b; }
.spc-check-reason { font-size: 12.5px; color: #4d545c; line-height: 1.5; }
.spc-issues { margin: 10px 18px 0; padding: 10px 12px; background: #fdecea; border: 1px solid #f1a9a5; border-radius: 4px;
  font-size: 12.5px; color: #7a1512; }
.spc-issues ul { margin: 6px 0 0; padding-left: 18px; }
.spc-status { display: flex; align-items: center; gap: 6px; font-size: 12px; color: #4d545c; }
.spc-dot { width: 7px; height: 7px; border-radius: 50%; background: #6b727b; display: inline-block; flex: none; }

/* ── 검증 탭 ── */
.spc-dash-title { display: flex; flex-wrap: wrap; align-items: baseline; gap: 6px 16px; }
.spc-dash-title b { font-size: 20px; }
.spc-dash-title span { font-size: 13px; color: #4d545c; }
.spc-kpi { display: flex; flex-direction: column; gap: 8px; }
.spc-kpi-top { display: flex; align-items: center; gap: 8px; font-size: 14px; color: #3b424a; }
.spc-kpi-num { font-size: 40px; font-weight: 600; line-height: 1.1; }
.spc-kpi-num.sm { font-size: 28px; }
.spc-kpi-unit { font-size: 22px; color: #5b626b; }
.spc-kpi-sub { font-size: 12.5px; color: #4d545c; }
.spc-kpi-model { display: flex; flex-wrap: wrap; align-items: baseline; gap: 2px 10px; }
.spc-kpi-name { width: 100%; font-family: 'IBM Plex Mono', monospace; font-size: 12px; color: #3b424a; }
.spc-kpi-delta { font-size: 14px; font-weight: 600; color: #b7191c; }
.spc-bars-head { display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; gap: 8px;
  padding-bottom: 10px; border-bottom: 1px solid #eceef0; }
.spc-bars-head b { font-size: 16px; }
.spc-lg { display: inline-flex; align-items: center; gap: 6px; margin-left: 14px; font-size: 13px; }
.spc-lg i { width: 12px; height: 12px; display: inline-block; }
.spc-bar-group { display: grid; grid-template-columns: 120px minmax(0, 1fr); gap: 16px; padding: 12px 0;
  border-bottom: 1px solid #eceef0; }
.spc-bar-group.total { border-bottom: none; border-top: 1px solid #c9cdd2; }
.spc-bar-name b { display: block; font-size: 14px; }
.spc-bar-name small { font-family: 'IBM Plex Mono', monospace; font-size: 11.5px; color: #5b626b; }
.spc-bar-rows { display: flex; flex-direction: column; gap: 6px; }
.spc-bar-row { display: grid; grid-template-columns: 96px minmax(0, 1fr) 190px; gap: 10px; align-items: center; }
.spc-bar-who { font-size: 11.5px; color: #5b626b; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.spc-track { position: relative; height: 14px; background: #f0f1f3; }
.spc-fill { height: 100%; }
.spc-range { position: absolute; top: 50%; height: 2px; margin-top: -1px; background: #0b2e4f; }
.spc-range::before, .spc-range::after { content: ""; position: absolute; top: -4px; width: 2px; height: 10px; background: #0b2e4f; }
.spc-range::before { left: 0; }
.spc-range::after { right: 0; }
.spc-bar-val { font-family: 'IBM Plex Mono', monospace; font-size: 12.5px; white-space: nowrap; }
.spc-bar-val span { color: #5b626b; }
.spc-facts { border-left: 1px solid #eceef0; padding-left: 16px; display: flex; flex-direction: column; gap: 8px; }
.spc-facts p { font-size: 14px; line-height: 1.55; margin: 0; }
.spc-cases-head { display: flex; flex-wrap: wrap; align-items: baseline; gap: 6px 14px; padding-bottom: 8px; }
.spc-cases-head b { font-size: 16px; }
.spc-cases-head span { font-size: 12.5px; color: #4d545c; }
.spc-case-row { display: grid; grid-template-columns: 36px 220px minmax(0, 1fr) minmax(0, 1fr); gap: 16px;
  padding: 12px 0; border-top: 1px solid #eceef0; font-size: 13.5px; }
.spc-case-row.th { font-size: 12px; font-weight: 600; color: #4d545c; background: #f6f7f8; padding: 8px 0; }
.spc-case-row small { display: block; font-size: 12px; color: #4d545c; }
.spc-quote { color: #3b424a; font-size: 12.5px; word-break: break-all; }  /* 모노 글꼴엔 한글이 없어 산세리프 */
.spc-cases-empty { font-size: 13.5px; color: #3b424a; padding: 8px 0; }
</style>"""
```

- [ ] **Step 4: 앱에 CSS·머리말 넣기**

Modify `streamlit_app.py` — 찾을 코드:

```python
from spc_explainer.charts import control_chart
```

바꿀 코드:

```python
from spc_explainer import ui_html
from spc_explainer.charts import control_chart
```

Modify `streamlit_app.py` — 찾을 코드:

```python
st.title("SPC 설명기")
st.caption(
    f"{config.PROCESS_NAME} 관리도에서 판정은 규칙 엔진(pycontrolcharts), 설명은 LLM이 맡습니다. "
    f"관리한계 고정값({config.LCL:g}~{config.UCL:g}{config.UNIT}) 사용 = 이미 안정화된 공정을 감시하는 상황을 가정합니다."
)
tab_main, tab_report = st.tabs(["판정·설명", "검증 리포트"])

with tab_main:
    dataset = load_json(config.SERIES_PATH) or generator.generate_dataset()
    series = dataset["series"]
```

바꿀 코드:

```python
dataset = load_json(config.SERIES_PATH) or generator.generate_dataset()
st.html(ui_html.CSS)
st.title("SPC 설명기")
st.html(ui_html.header_html(dataset["center"], dataset["ucl"], dataset["lcl"], config.UNIT))
tab_main, tab_report = st.tabs(["판정·설명", "검증 리포트"])

with tab_main:
    series = dataset["series"]
```

- [ ] **Step 5: 통과 확인**

Run: `.venv/Scripts/python -m pytest tests/test_ui_html.py tests/test_app.py -v`
Expected: 7 passed

- [ ] **Step 6: 커밋**

```bash
git add .streamlit/config.toml spc_explainer/ui_html.py tests/test_ui_html.py streamlit_app.py
git commit -m "feat: 화면 테마·카드 CSS·역할 머리말 (Claude Design 절충안 1단계)" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
git push origin main
```

---

### Task 11-2: STEP 1 규칙 판정 → 화살표 → STEP 2 AI 설명 (5절 4~6번)

**Files:**
- Create: `spc_explainer/ui_steps.py`, `tests/test_ui_steps.py`
- Modify: `streamlit_app.py`

**Interfaces:**
- Consumes: `ui_html.*`(Task 11-1), `rules.describe`, `explain.ISSUE_KO/validate/build_input/build_messages`, `causes.CAUSES`, `patterns.*`
- Produces:
  - `ui_steps.ARROW_HTML: str`
  - `ui_steps.rule_card_html(events: list[Event], values) -> str`
  - `ui_steps.ai_head_html(issues: list[dict] | None) -> str` (None = 배지 없음, [] = 검증 통과)
  - `ui_steps.issues_html(issues) -> str`, `ui_steps.status_html(text) -> str`
  - `ui_steps.priority_items(data: dict, inp: dict) -> list[dict]` — `{"rank", "event_id", "rule_id", "cause_id", "title", "cause", "reason", "known"}`
  - `ui_steps.ai_body_html(data: dict, inp: dict) -> str`

- [ ] **Step 1: 실패하는 테스트 작성**

Create `tests/test_ui_steps.py`:

```python
# STEP 1·STEP 2 카드: 규칙 번호, 구간 표기, 검증 배지, 점검 우선순위 펼치기, HTML 이스케이프
import json

from spc_explainer.explain import build_input
from spc_explainer.patterns import Event
from spc_explainer.ui_steps import ai_body_html, ai_head_html, issues_html, priority_items, rule_card_html

VALUES = [104.2 if i == 14 else 99.0 if 40 <= i <= 49 else 100.0 for i in range(100)]
EVENTS = [Event("spike", 14, 14, "up"), Event("shift", 40, 49, "down")]
INP = build_input(VALUES, EVENTS)
DATA = {
    "summary": "요약",
    "priority": ["E2", "E1"],
    "events": [
        {"event_id": "E1", "pattern": "급변", "rule": "r", "checks": [{"cause_id": "SP-1", "reason": "재측정"}]},
        {"event_id": "E2", "pattern": "치우침", "rule": "r",
         "checks": [{"cause_id": "SH-1", "reason": "PM"}, {"cause_id": "SH-2", "reason": "로트"}]},
    ],
}


def test_rule_card_lists_events_with_rule_ids():
    h = rule_card_html(EVENTS, VALUES)
    assert "STEP 1" in h and "확정" in h and "2건 감지" in h
    assert "#14" in h and "#40–49" in h and ">R1<" in h and ">R2<" in h
    assert "관리한계 밖 1점" in h and "결정적 계산 — 동일 입력이면 항상 동일 결과" in h


def test_rule_card_without_events():
    h = rule_card_html([], VALUES)
    assert "이상 없음" in h and "0건 감지" in h


def test_ai_head_badges():
    assert "검증 통과" in ai_head_html([])
    assert "검증 문제: 원인표 밖 원인" in ai_head_html([{"type": "cause", "detail": "x"}])
    none_head = ai_head_html(None)
    assert "spc-tag-pass" not in none_head and "spc-tag-fail" not in none_head
    assert "새로운 판정을 만들지 않음" in none_head


def test_priority_items_follow_priority_then_checks():
    items = priority_items(DATA, INP)
    assert [(i["event_id"], i["cause_id"]) for i in items] == [("E2", "SH-1"), ("E2", "SH-2"), ("E1", "SP-1")]
    assert [i["rank"] for i in items] == [1, 2, 3]
    assert items[0]["rule_id"] == "R2" and items[2]["rule_id"] == "R1"  # 규칙 번호는 규칙 판정에서 가져온다
    assert items[2]["title"] == "같은 웨이퍼 재측정"


def test_priority_items_tolerate_bad_shapes():
    weird = {"events": [{"event_id": "E1", "checks": [1, {"cause_id": "XX-9", "reason": "?"}]}, "x"], "priority": "E1"}
    items = priority_items(weird, INP)
    assert len(items) == 1 and items[0]["known"] is False and items[0]["title"] == "원인표에 없는 원인"
    assert priority_items({}, INP) == []


def test_llm_text_is_escaped():
    bad = json.loads(json.dumps(DATA))
    bad["summary"] = "<script>alert(1)</script> & <b>굵게</b>"
    bad["events"][0]["checks"][0]["reason"] = "<img src=x onerror=alert(1)>"
    h = ai_body_html(bad, INP)
    assert "<script>" not in h and "&lt;script&gt;" in h and "<img" not in h
    assert "&lt;b&gt;" in issues_html([{"type": "format", "detail": "<b>"}])
```

- [ ] **Step 2: 실패 확인**

Run: `.venv/Scripts/python -m pytest tests/test_ui_steps.py -v`
Expected: 수집 오류 `ModuleNotFoundError: No module named 'spc_explainer.ui_steps'`

- [ ] **Step 3: 카드 조각 구현**

Create `spc_explainer/ui_steps.py`:

```python
# STEP 1(규칙 판정)·STEP 2(AI 설명) 카드의 HTML과 점검 우선순위 가공. 판정은 항상 규칙 결과가 기준이다.
from .causes import CAUSES
from .explain import ISSUE_KO
from .patterns import FROM_KOREAN, KOREAN, Event
from .rules import describe
from .ui_html import PATTERN_COLORS, RULE_ID, SYMBOL, esc, span_text

ARROW_HTML = '<div class="spc-flow">→<small>판정 결과만<br>전달</small></div>'


def _split_rule(sentence: str) -> tuple[str, str]:
    """rules.describe 문장을 주문장과 괄호 속 세부로 나눈다."""
    main, _, rest = sentence.partition(" (")
    return main, rest[:-1] if rest.endswith(")") else rest


def rule_card_html(events: list[Event], values) -> str:
    """STEP 1 카드: 머리줄(확정·건수) + 사건 표(패턴·구간·판정 근거·규칙 번호) + 결정적 계산 문구."""
    head = ('<div class="spc-step-head rule"><span class="spc-step">STEP 1</span><b>규칙 판정</b>'
            f'<span class="spc-tag-fixed">확정</span><span class="spc-muted">{len(events)}건 감지</span></div>')
    rows = ['<div class="spc-rule-row spc-rule-th"><span>패턴</span><span>구간</span><span>판정 근거</span><span>규칙</span></div>']
    for ev in events:
        main, detail = _split_rule(describe(ev, values))
        color = PATTERN_COLORS[ev.pattern]["text"]
        rows.append(
            f'<div class="spc-rule-row"><span class="spc-pat" style="color:{color}">{SYMBOL[ev.pattern]} {KOREAN[ev.pattern]}</span>'
            f'<span class="spc-mono">{span_text(ev.start, ev.end)}</span>'
            f"<span>{esc(main)}<small>{esc(detail)}</small></span>"
            f'<span class="spc-rid">{RULE_ID[ev.pattern]}</span></div>'
        )
    if not events:
        rows = ['<div class="spc-rule-empty">이상 없음 — 세 규칙 모두 해당하지 않습니다.</div>']
    foot = ('<div class="spc-foot"><span>결정적 계산 — 동일 입력이면 항상 동일 결과</span>'
            "<span>Nelson R1–R3</span></div>")
    return head + "".join(rows) + foot


def ai_head_html(issues: list[dict] | None) -> str:
    """STEP 2 머리줄. issues가 None이면 검증 배지 없음(보여줄 출력 없음), []이면 검증 통과."""
    if issues is None:
        badge = ""
    elif not issues:
        badge = '<span class="spc-tag-pass">검증 통과</span>'
    else:
        names = ", ".join(sorted({ISSUE_KO[i["type"]] for i in issues}))
        badge = f'<span class="spc-tag-fail">검증 문제: {esc(names)}</span>'
    return ('<div class="spc-step-head ai"><span class="spc-step">STEP 2</span><b>AI 설명</b>'
            f'<span class="spc-tag-ai">AI 생성</span>{badge}'
            '<span class="spc-muted">참고용 해석 · 새로운 판정을 만들지 않음</span></div>')


def issues_html(issues: list[dict]) -> str:
    """검증 문제 목록. 판정은 STEP 1을 따르라고 적는다."""
    items = "".join(f"<li>{esc(ISSUE_KO[i['type']])}: {esc(i['detail'])}</li>" for i in issues)
    return ('<div class="spc-issues">검증에서 문제가 발견됐습니다. 판정은 STEP 1 규칙 결과를 따르세요.'
            f"<ul>{items}</ul></div>")


def status_html(text: str) -> str:
    return f'<div class="spc-status"><span class="spc-dot"></span>{esc(text)}</div>'


def priority_items(data: dict, inp: dict) -> list[dict]:
    """priority 순서대로 사건별 checks를 펼친 점검 목록. 규칙 번호는 LLM이 아니라 규칙 판정에서 가져온다.
    모양이 틀린 출력도 예외 없이 처리한다."""
    patterns = {e["event_id"]: FROM_KOREAN.get(e["pattern"]) for e in inp["events"]}
    events = data.get("events") if isinstance(data.get("events"), list) else []
    by_id = {}
    for ev in events:
        if isinstance(ev, dict):
            by_id.setdefault(str(ev.get("event_id")), ev)
    priority = data.get("priority") if isinstance(data.get("priority"), list) else []
    order = [str(e) for e in priority if str(e) in by_id]
    order = list(dict.fromkeys(order)) + [eid for eid in by_id if eid not in order]  # priority에 빠진 사건은 뒤에
    items = []
    for eid in order:
        checks = by_id[eid].get("checks")
        for c in checks if isinstance(checks, list) else []:
            if not isinstance(c, dict):
                continue
            cid = c.get("cause_id")
            row = CAUSES.get(cid) if isinstance(cid, str) else None
            items.append({
                "rank": len(items) + 1,
                "event_id": eid,
                "rule_id": RULE_ID.get(patterns.get(eid), "-"),
                "cause_id": str(cid),
                "title": row["check"] if row else "원인표에 없는 원인",
                "cause": row["cause"] if row else str(cid),
                "reason": str(c.get("reason", "")),
                "known": row is not None,
            })
    return items


def ai_body_html(data: dict, inp: dict) -> str:
    """패턴 해석(summary) + 점검 우선순위 카드. LLM 문자열은 모두 이스케이프한다."""
    summary = data.get("summary") if isinstance(data.get("summary"), str) else ""
    cards = []
    for it in priority_items(data, inp):
        cls = "spc-check" if it["known"] else "spc-check unknown"
        cards.append(
            f'<div class="{cls}"><div class="spc-check-top"><span class="spc-rank">{it["rank"]}</span>'
            f'<span class="spc-chip">{esc(it["rule_id"])}</span><span class="spc-chip">{esc(it["event_id"])}</span></div>'
            f'<div class="spc-check-title">{esc(it["title"])}</div>'
            f'<div class="spc-check-cause">{esc(it["cause_id"])} · {esc(it["cause"])}</div>'
            f'<div class="spc-check-reason">{esc(it["reason"])}</div></div>'
        )
    checks_html = "".join(cards) or '<div class="spc-check-cause">점검 항목 없음</div>'
    return ('<div class="spc-ai-body"><div class="spc-label">패턴 해석</div>'
            f'<div class="spc-summary">{esc(summary)}</div>'
            f'<div class="spc-label">점검 우선순위</div><div class="spc-checks">{checks_html}</div></div>')
```

- [ ] **Step 4: 앱의 판정·설명 영역을 STEP 카드로 교체**

Modify `streamlit_app.py` — 찾을 코드:

```python
import pandas as pd
import streamlit as st

from spc_explainer import config, explain, generator, llm_client, rules
from spc_explainer.causes import CAUSES
from spc_explainer import ui_html
from spc_explainer.charts import control_chart
```

바꿀 코드:

```python
import streamlit as st

from spc_explainer import config, explain, generator, llm_client, rules
from spc_explainer import ui_html, ui_steps
from spc_explainer.charts import control_chart
```

Modify `streamlit_app.py` — 찾을 코드:

```python
def issue_names(issues: list[dict]) -> str:
    return ", ".join(sorted({explain.ISSUE_KO[i["type"]] for i in issues}))


def show_explanation(text, inp: dict) -> None:
    """설명 출력 하나를 검증 결과와 함께 보여준다. 판정은 항상 규칙 결과가 기준."""
    data, issues = explain.validate(text, inp)
    if issues:
        lines = [f"- {explain.ISSUE_KO[i['type']]}: {i['detail']}" for i in issues]
        st.error("검증에서 문제가 발견됐습니다. 판정은 위 규칙 결과를 따르세요.\n\n" + "\n".join(lines))
    else:
        st.success("검증 통과: JSON 형식, 원인표, 규칙 판정과 모두 일치")
    if not isinstance(data, dict):
        st.code(text or "", language="json")
        return
    st.markdown(f"**요약** {data.get('summary', '')}")
    priority = data.get("priority") if isinstance(data.get("priority"), list) else []
    if priority:
        st.markdown("**점검 순서** " + " → ".join(map(str, priority)))
    events = data.get("events") if isinstance(data.get("events"), list) else []
    for ev in events:
        if not isinstance(ev, dict):
            continue
        st.markdown(f"**{ev.get('event_id')} · {ev.get('pattern')}** — {ev.get('rule', '')}")
        checks = ev.get("checks") if isinstance(ev.get("checks"), list) else []
        for n, c in enumerate(checks, start=1):
            if not isinstance(c, dict):
                continue
            cid = c.get("cause_id")
            row = CAUSES.get(cid, {}) if isinstance(cid, str) else {}
            cause = row.get("cause", "(원인표에 없음)")
            check = row.get("check", "-")
            st.markdown(f"{n}. `{cid}` {cause} — 점검: {check}  \n이유: {c.get('reason', '')}")
```

바꿀 코드:

```python
def render_ai_card(sid: int, values, events) -> None:
    """STEP 2 카드: 설명(실시간 결과가 있으면 그것, 없으면 저장된 1회차) + 검증 배지 + 캐시 상태·실시간 재생성."""
    model = config.EXPLAIN_MODEL
    inp = explain.build_input(values, events)
    saved = load_json(config.EXPLANATIONS_PATH) or {}
    cached = (saved.get("series") or {}).get(str(sid))
    runs = cached.get("runs", []) if cached else []
    live = st.session_state.get("live")
    reply = live[1] if live and live[0] == sid else None

    if reply is not None:
        text, error, shown_inp = reply.text, reply.error, inp
        status = f"실시간 결과 · {model['name']} · {reply.latency_s:.1f}초"
    elif runs:
        text, error, shown_inp = runs[0]["text"], runs[0]["error"], cached["input"]
        created = str(runs[0].get("created", "")).replace("T", " ")[:16]
        status = f"캐시된 결과 · {created} 생성 · 같은 입력 {len(runs)}회 중 1회차"
    else:
        text, error, shown_inp = None, None, None
        status = "저장된 결과 없음"

    if shown_inp is None or error:
        st.html(ui_steps.ai_head_html(None))
        with st.container(key="ai_body"):
            if error:
                st.error(f"호출 오류: {error}")
            else:
                st.info("저장된 설명이 없습니다. `python scripts/run_experiment.py`로 만들 수 있습니다.")
    else:
        data, issues = explain.validate(text, shown_inp)
        st.html(ui_steps.ai_head_html(issues))
        if issues:
            st.html(ui_steps.issues_html(issues))
        if isinstance(data, dict):
            st.html(ui_steps.ai_body_html(data, shown_inp))
        else:
            with st.container(key="ai_body"):
                st.code(text or "", language="json")
    if cached and cached.get("input") != inp:
        with st.container(key="ai_warn"):
            st.warning("저장된 설명의 입력이 현재 규칙 판정과 다릅니다. 실험을 다시 돌려야 합니다.")

    # 실시간 재생성: 세션당·하루 호출 수를 제한하고, 키가 없으면 끈다
    counter = daily_counter()
    if counter["date"] != date.today():
        counter.update(date=date.today(), n=0)
    used = st.session_state.get("live_used", 0)
    left = max(0, min(config.LIVE_CALLS_PER_SESSION - used, config.LIVE_CALLS_PER_DAY - counter["n"]))
    has_key = bool(llm_client.get_api_key())
    if not has_key:
        limit_text = "API 키 없음 — 실시간 재생성 꺼짐"
    elif left == 0:
        limit_text = "실시간 호출 한도 소진"
    else:
        limit_text = f"남은 횟수 {left}/{config.LIVE_CALLS_PER_SESSION}"
    with st.container(key="ai_foot"):
        info_col, button_col = st.columns([3, 1.3], vertical_alignment="center")
        with info_col:
            st.html(ui_steps.status_html(f"{status} · {limit_text}"))
        with button_col:
            can_call = has_key and left > 0
            clicked = st.button("↻ 실시간 재생성" if can_call else "재생성 불가", key="live_button",
                                disabled=not can_call, width="stretch")
    if clicked:
        st.session_state["live_used"] = used + 1
        counter["n"] += 1
        with st.spinner("LLM 호출 중…"):
            st.session_state["live"] = (sid, llm_client.call_json(model, *explain.build_messages(inp)))
        st.rerun()
    if runs:
        with st.container(key="ai_runs"), st.expander(f"같은 입력 {len(runs)}회 반복 결과 (저장된 결과)"):
            for r in runs:
                if r["error"]:
                    st.markdown(f"**{r['run'] + 1}회차** · 호출 오류")
                    continue
                data, issues = explain.validate(r["text"], cached["input"])
                state = ", ".join(sorted({explain.ISSUE_KO[i["type"]] for i in issues})) if issues else "검증 통과"
                items = ui_steps.priority_items(data, cached["input"]) if isinstance(data, dict) else []
                order_text = " → ".join(f"{it['event_id']}:{it['cause_id']}" for it in items) or "-"
                st.markdown(f"**{r['run'] + 1}회차** · {state} · 점검 순서 {order_text}")
```

Modify `streamlit_app.py` — 찾을 코드:

```python
    if not events:
        st.success("규칙 판정: 이상 없음 — LLM을 호출하지 않습니다.")
    else:
        st.subheader("규칙 판정")
        table = [{"사건": f"E{i}", "패턴": KOREAN[e.pattern], "구간": f"{e.start}~{e.end}",
                  "근거 규칙": rules.describe(e, values)} for i, e in enumerate(events, start=1)]
        st.dataframe(pd.DataFrame(table), hide_index=True, width="stretch")

        st.subheader("LLM 설명")
        model = config.EXPLAIN_MODEL
        inp = explain.build_input(values, events)
        saved = load_json(config.EXPLANATIONS_PATH) or {}
        cached = (saved.get("series") or {}).get(str(sid))
        if not cached or not cached.get("runs"):
            st.info("저장된 설명이 없습니다. `python scripts/run_experiment.py`로 만들 수 있습니다.")
        else:
            if cached["input"] != inp:
                st.warning("저장된 설명의 입력이 현재 규칙 판정과 다릅니다. 실험을 다시 돌려야 합니다.")
            runs = cached["runs"]
            st.caption(f"저장된 결과 · {model['name']} · 같은 입력 {len(runs)}회 중 1회차")
            if runs[0]["error"]:
                st.error(f"호출 오류: {runs[0]['error']}")
            else:
                show_explanation(runs[0]["text"], cached["input"])
            with st.expander(f"같은 입력 {len(runs)}회 반복 결과"):
                for r in runs:
                    if r["error"]:
                        st.markdown(f"**{r['run'] + 1}회차** · 호출 오류")
                        continue
                    data, issues = explain.validate(r["text"], cached["input"])
                    status = issue_names(issues) if issues else "검증 통과"
                    order = data.get("priority") if isinstance(data, dict) else None
                    order_text = " → ".join(map(str, order)) if isinstance(order, list) and order else "-"
                    st.markdown(f"**{r['run'] + 1}회차** · {status} · 점검 순서 {order_text}")

        # 실시간 설명: 세션당·하루 호출 수를 제한하고, 키가 없으면 끈다
        counter = daily_counter()
        if counter["date"] != date.today():
            counter.update(date=date.today(), n=0)
        used = st.session_state.get("live_used", 0)
        left = max(0, min(config.LIVE_CALLS_PER_SESSION - used, config.LIVE_CALLS_PER_DAY - counter["n"]))
        has_key = bool(llm_client.get_api_key())
        clicked = st.button(f"실시간 설명 받기 ({model['name']}, 남은 횟수 {left})", key="live_button",
                            disabled=not has_key or left == 0)
        if not has_key:
            st.caption("API 키가 설정되지 않아 실시간 설명은 꺼져 있습니다. 저장된 결과는 위에서 볼 수 있습니다.")
        if clicked:
            st.session_state["live_used"] = used + 1
            counter["n"] += 1
            with st.spinner("LLM 호출 중…"):
                st.session_state["live"] = (sid, llm_client.call_json(model, *explain.build_messages(inp)))
        live = st.session_state.get("live")
        if live and live[0] == sid:
            reply = live[1]
            st.caption(f"실시간 결과 · {model['name']} · {reply.latency_s:.1f}초")
            if reply.error:
                st.error(f"호출 오류: {reply.error}")
            else:
                show_explanation(reply.text, inp)
```

바꿀 코드:

```python
    rule_col, arrow_col, ai_col = st.columns([5, 0.7, 7])
    with rule_col, st.container(key="rule_card"):
        st.html(ui_steps.rule_card_html(events, values))
    with arrow_col:
        st.html(ui_steps.ARROW_HTML)
    with ai_col, st.container(key="ai_card"):
        if events:
            render_ai_card(sid, values, events)
        else:
            st.html(ui_steps.ai_head_html(None))
            with st.container(key="ai_body"):
                st.success("규칙 판정이 없어 LLM을 호출하지 않습니다.")
```

- [ ] **Step 5: 통과 확인**

Run: `.venv/Scripts/python -m pytest tests/test_ui_steps.py tests/test_app.py -v`
Expected: 9 passed

- [ ] **Step 6: 커밋**

```bash
git add spc_explainer/ui_steps.py tests/test_ui_steps.py streamlit_app.py
git commit -m "feat: STEP 1 규칙 판정 → STEP 2 AI 설명 카드 (검증 배지, 캐시 상태)" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
git push origin main
```

---

### Task 11-3: 관리도 스타일 (5절 7번, 시안 `docs/design/ref/control-chart.png`)

**Files:**
- Modify: `spc_explainer/charts.py` (전체 교체), `tests/test_charts.py` (전체 교체), `streamlit_app.py`

**Interfaces:**
- Consumes: `ui_html.PATTERN_COLORS/SYMBOL/esc/span_text`(Task 11-1), `patterns.*`
- Produces:
  - `charts.control_chart(values, events, center, ucl, lcl, truth=None, phase_boundary=None, fail_idx=None, y_title="", show_legend=True, band_labels=None, height=440) -> go.Figure` — Task 11의 인자를 그대로 받으므로 Task 13(SECOM) 코드는 바뀌지 않는다. `band_labels=None`이면 사건이 8개 이하일 때만 음영 위 라벨을 단다.
  - `charts.chart_header_html(values, title: str, show_truth: bool = False) -> str` — n·x̄·σ는 넘겨받은 값에서 계산
  - `charts.chart_footer_html(show_truth: bool = False) -> str`

- [ ] **Step 1: 실패하는 테스트 작성**

Modify `tests/test_charts.py` — 전체를 다음으로 교체:

```python
# 관리도 스타일: 한계선(점선+오른쪽 라벨)·중심선(실선), 패턴별 마커, 규칙 구간 음영+라벨, 정답은 테두리만
from spc_explainer.charts import chart_footer_html, chart_header_html, control_chart
from spc_explainer.patterns import Event

VALUES = [100.0 + (0.3 if i % 2 else -0.3) for i in range(100)]
VALUES[14] = 103.6
EVENTS = [Event("spike", 14, 14, "up"), Event("trend", 24, 29, "up")]


def test_rule_bands_labels_and_limit_lines():
    fig = control_chart(VALUES, EVENTS, 100, 103, 97, show_legend=False)
    texts = [a.text for a in fig.layout.annotations]
    assert "<b>◆ 급변 #14</b>" in texts and "<b>▲ 추세 #24–29</b>" in texts
    assert {"UCL 103", "CL 100", "LCL 97"} <= set(texts)
    assert sorted(s.line.dash for s in fig.layout.shapes if s.type == "line") == ["dash", "dash", "solid"]
    bands = [s for s in fig.layout.shapes if s.type == "rect"]
    assert len(bands) == 2 and all(b.fillcolor.startswith("rgba(") for b in bands)
    assert not fig.layout.showlegend


def test_pattern_markers_and_zero_based_x():
    fig = control_chart(VALUES, EVENTS, 100, 103, 97)
    symbols = {t.name: t.marker.symbol for t in fig.data if t.name != "측정값"}
    assert symbols == {"급변": "diamond", "추세": "triangle-up"}
    assert list(fig.data[0].x) == list(range(100))
    assert list(fig.data[2].x) == list(range(24, 30))  # 추세 구간의 모든 점


def test_truth_is_outline_only():
    fig = control_chart(VALUES, EVENTS, 100, 103, 97, truth=[Event("trend", 24, 31, "up")])
    outlines = [s for s in fig.layout.shapes if s.type == "rect" and s.line.dash == "dot"]
    assert len(outlines) == 1 and outlines[0].fillcolor == "rgba(0,0,0,0)"


def test_many_events_hide_band_labels_and_secom_arguments_still_work():
    many = [Event("spike", i, i, "up") for i in range(0, 90, 9)]
    fig = control_chart(VALUES, many, 100, 103, 97, phase_boundary=50, fail_idx=[3], y_title="sensor_88")
    texts = [a.text for a in fig.layout.annotations]
    assert not any("급변 #" in t for t in texts) and "Phase I | Phase II" in texts
    assert "불량 라벨" in [t.name for t in fig.data] and fig.layout.showlegend


def test_header_reads_stats_from_values():
    h = chart_header_html([99.0, 101.0, 100.0], "관리도 · 증착 막 두께 (nm)", show_truth=True)
    assert "n=3" in h and "x̄=100.00" in h and "σ=1.00" in h
    assert "◆" in h and "▲" in h and "■" in h and "관리한계" in h and "정답" in h
    assert "정답" not in chart_header_html([100.0, 100.0], "t", show_truth=False)


def test_footer_mentions_rule_bands_and_zero_based_index():
    f = chart_footer_html()
    assert "세로 음영 = 규칙이 판정한 이상 구간" in f and "0부터" in f
    assert "점선 테두리" in chart_footer_html(show_truth=True)
```

- [ ] **Step 2: 실패 확인**

Run: `.venv/Scripts/python -m pytest tests/test_charts.py -v`
Expected: 수집 오류 `ImportError: cannot import name 'chart_footer_html' from 'spc_explainer.charts'`

- [ ] **Step 3: 관리도 구현**

Modify `spc_explainer/charts.py` — 전체를 다음으로 교체:

```python
# 관리도 그림(plotly)과 그림 머리말·꼬리말(HTML). 합성 데이터 탭과 SECOM 탭이 같이 쓴다.
# 스타일 출처: docs/design/ref/control-chart.png — CL 실선, UCL·LCL 점선과 오른쪽 라벨, 패턴별 마커(◆▲■),
# 규칙이 판정한 구간의 세로 음영 + 위쪽 라벨. 정답(심은 이상)은 테두리만 있는 점선 사각형으로 구분한다.
import statistics

import plotly.graph_objects as go

from .patterns import KOREAN, PATTERNS, Event
from .ui_html import PATTERN_COLORS, SYMBOL, esc, span_text

LINE = "#2a2f35"  # 측정값 선
LIMIT = "#5b626b"  # 중심선·관리한계
GRID = "#eceef0"
TICK = "#6b727b"
MONO = "IBM Plex Mono, monospace"
SANS = "IBM Plex Sans KR, sans-serif"
MARKERS = {"spike": ("diamond", 12), "trend": ("triangle-up", 11), "shift": ("square", 9)}
MAX_BAND_LABELS = 8  # 사건이 이보다 많으면(예: SECOM) 음영 위 라벨을 생략한다


def _rgba(hex_color: str, alpha: float) -> str:
    h = hex_color.lstrip("#")
    return f"rgba({int(h[0:2], 16)},{int(h[2:4], 16)},{int(h[4:6], 16)},{alpha})"


def control_chart(values, events: list[Event], center: float, ucl: float, lcl: float,
                  truth: list[Event] | None = None, phase_boundary: int | None = None,
                  fail_idx: list[int] | None = None, y_title: str = "", show_legend: bool = True,
                  band_labels: bool | None = None, height: int = 440) -> go.Figure:
    """측정값 + CL 실선·UCL/LCL 점선(오른쪽 라벨) + 패턴별 마커 + 규칙 판정 구간 음영(+ 위 라벨)."""
    vals = [float(v) for v in values]
    xs = list(range(len(vals)))
    if band_labels is None:
        band_labels = len(events) <= MAX_BAND_LABELS
    fig = go.Figure()
    # 규칙 판정 구간: 패턴 색의 옅은 음영 + 얇은 테두리 (점·선 아래)
    for e in events:
        color = PATTERN_COLORS[e.pattern]
        fig.add_vrect(x0=e.start - 0.5, x1=e.end + 0.5, fillcolor=_rgba(color["fill"], 0.10),
                      line={"color": _rgba(color["fill"], 0.35), "width": 1}, layer="below")
        if band_labels:
            fig.add_annotation(x=e.start - 0.5, y=1, xref="x", yref="paper", xanchor="left", yanchor="bottom",
                               text=f"<b>{SYMBOL[e.pattern]} {KOREAN[e.pattern]} {span_text(e.start, e.end)}</b>",
                               showarrow=False, font={"size": 12, "color": color["text"], "family": SANS})
    # 정답 구간: 테두리만 있는 점선 사각형 (규칙 음영과 구분)
    for t in truth or []:
        fig.add_shape(type="rect", x0=t.start - 0.5, x1=t.end + 0.5, y0=0, y1=1, xref="x", yref="paper",
                      line={"color": "#16191d", "width": 1.2, "dash": "dot"}, fillcolor="rgba(0,0,0,0)")
    # 중심선(실선)·관리한계(점선) + 오른쪽 라벨
    for label, y, dash in (("UCL", ucl, "dash"), ("CL", center, "solid"), ("LCL", lcl, "dash")):
        fig.add_hline(y=y, line={"color": LIMIT, "width": 1.2 if dash == "solid" else 1, "dash": dash}, layer="below")
        fig.add_annotation(x=1, y=y, xref="paper", yref="y", xanchor="left", yanchor="middle", xshift=8,
                           text=f"{label} {y:.4g}", showarrow=False, font={"size": 11, "color": "#3b424a", "family": MONO})
    # 측정값 선 + 정상 점(흰 원)
    dot = 6 if len(vals) <= 200 else 3
    fig.add_trace(go.Scatter(x=xs, y=vals, mode="lines+markers", name="측정값", showlegend=False,
                             line={"color": LINE, "width": 1.3},
                             marker={"size": dot, "color": "#ffffff", "line": {"color": LINE, "width": 1}},
                             hovertemplate="#%{x}: %{y:.2f}<extra></extra>"))
    # 규칙이 판정한 점: 패턴별 모양·색
    for p in PATTERNS:
        idx = sorted({i for e in events if e.pattern == p for i in range(e.start, e.end + 1)})
        if idx:
            symbol, size = MARKERS[p]
            fig.add_trace(go.Scatter(x=idx, y=[vals[i] for i in idx], mode="markers", name=KOREAN[p],  # 범례가 모양을 그림
                                     marker={"symbol": symbol, "size": size, "color": PATTERN_COLORS[p]["fill"],
                                             "line": {"color": PATTERN_COLORS[p]["text"], "width": 1}},
                                     hovertemplate="#%{x}: %{y:.2f}<extra>" + KOREAN[p] + "</extra>"))
    if fail_idx:
        fig.add_trace(go.Scatter(x=list(fail_idx), y=[vals[i] for i in fail_idx], mode="markers", name="불량 라벨",
                                 marker={"symbol": "x", "color": "black", "size": 7}))
    if phase_boundary is not None:
        fig.add_vline(x=phase_boundary - 0.5, line={"color": "#555555", "dash": "dot"})
        fig.add_annotation(x=phase_boundary - 0.5, y=1, xref="x", yref="paper", yanchor="bottom",
                           text="Phase I | Phase II", showarrow=False, font={"size": 11, "color": "#3b424a"})
    # 축: 값 범위가 좁으면 y는 정수 눈금, x는 10 간격. 눈금 글꼴은 모노
    lo, hi = min(vals + [lcl]), max(vals + [ucl])
    pad = (hi - lo) * 0.06 or 1.0
    yaxis = {"range": [lo - pad, hi + pad], "showgrid": True, "gridcolor": GRID, "zeroline": False,
             "tickfont": {"family": MONO, "size": 11, "color": TICK},
             "title": {"text": y_title, "font": {"size": 12, "color": TICK}}}
    if hi - lo + 2 * pad <= 14:
        yaxis["dtick"] = 1
    xaxis = {"range": [-0.8, len(vals) - 0.2], "showgrid": False, "zeroline": False, "showline": True,
             "linecolor": "#9aa0a7", "ticks": "outside", "ticklen": 4, "tickcolor": "#9aa0a7",
             "tickfont": {"family": MONO, "size": 11, "color": TICK}}
    if len(vals) <= 200:
        xaxis.update(tick0=0, dtick=10)
    top = 34 if (band_labels and events) or show_legend or phase_boundary is not None else 16
    fig.update_layout(height=height, margin={"l": 44, "r": 76, "t": top, "b": 30},
                      paper_bgcolor="#ffffff", plot_bgcolor="#ffffff", xaxis=xaxis, yaxis=yaxis,
                      showlegend=show_legend, legend={"orientation": "h", "x": 1, "xanchor": "right", "y": 1.02,
                                                      "yanchor": "bottom", "font": {"size": 12}},
                      font={"family": SANS, "color": "#16191d"}, hoverlabel={"font": {"family": MONO}})
    return fig


def chart_header_html(values, title: str, show_truth: bool = False) -> str:
    """그림 머리말: 제목 + n·x̄·σ(넘겨받은 값에서 계산) + 범례."""
    vals = [float(v) for v in values]
    mean = statistics.fmean(vals) if vals else 0.0
    sd = statistics.stdev(vals) if len(vals) > 1 else 0.0
    legend = "".join(f'<span><b style="color:{PATTERN_COLORS[p]["fill"]}">{SYMBOL[p]}</b> {KOREAN[p]}</span>'
                     for p in PATTERNS)
    legend += '<span><i class="spc-lg-line"></i>관리한계</span>'
    if show_truth:
        legend += '<span><i class="spc-lg-truth"></i>정답(심은 이상)</span>'
    return (f'<div class="spc-chart-head"><span class="spc-chart-title">{esc(title)}</span>'
            f'<span class="spc-chart-stats"><span>n={len(vals)}</span><span>x̄={mean:.2f}</span><span>σ={sd:.2f}</span></span>'
            f'<span class="spc-chart-legend">{legend}</span></div>')


def chart_footer_html(show_truth: bool = False) -> str:
    right = "세로 음영 = 규칙이 판정한 이상 구간"
    if show_truth:
        right += " · 점선 테두리 = 심은 이상(정답)"
    return f'<div class="spc-chart-foot"><span>x축 · 측정 순번 (0부터)</span><span>{right}</span></div>'
```

- [ ] **Step 4: 앱의 관리도 영역 교체**

Modify `streamlit_app.py` — 찾을 코드:

```python
from spc_explainer.charts import control_chart
```

바꿀 코드:

```python
from spc_explainer.charts import chart_footer_html, chart_header_html, control_chart
```

Modify `streamlit_app.py` — 찾을 코드:

```python
    sid = st.selectbox("시리즈", range(len(series)), format_func=lambda i: series_label(series[i]))
    s = series[sid]
    values = s["values"]
    events = rules.detect(values)
    show_truth = st.toggle("정답(심은 이상) 구간 표시", value=True)
    truth = generator.truth_events(s) if show_truth else None
    fig = control_chart(values, events, config.CENTER, config.UCL, config.LCL, truth=truth,
                        y_title=f"{config.PROCESS_NAME} ({config.UNIT})")
    st.plotly_chart(fig, width="stretch")
```

바꿀 코드:

```python
    pick_col, truth_col = st.columns([3, 1], vertical_alignment="bottom")
    with pick_col:
        sid = st.selectbox("샘플 시리즈", range(len(series)), format_func=lambda i: series_label(series[i]))
    with truth_col:
        show_truth = st.toggle("정답(심은 이상) 구간 표시", value=False)
    s = series[sid]
    values = s["values"]
    events = rules.detect(values)
    truth = generator.truth_events(s) if show_truth else None
    with st.container(key="chart_card"):
        st.html(chart_header_html(values, f"관리도 · {config.PROCESS_NAME} ({config.UNIT})", show_truth))
        fig = control_chart(values, events, dataset["center"], dataset["ucl"], dataset["lcl"],
                            truth=truth, show_legend=False)
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
        st.html(chart_footer_html(show_truth))
```

- [ ] **Step 5: 통과 확인**

Run: `.venv/Scripts/python -m pytest tests/test_charts.py tests/test_app.py -v`
Expected: 9 passed

- [ ] **Step 6: 시안과 눈으로 대조**

Run (백그라운드): `.venv/Scripts/python -m streamlit run streamlit_app.py --server.headless true --server.port 8501`
브라우저로 시리즈 14번(급변+추세)과 18번(추세+치우침)을 열어 `docs/design/ref/control-chart.png`와 대조한다: CL 실선, UCL·LCL 점선과 오른쪽 라벨, ◆▲■ 마커와 색, 음영 위 라벨(`▲ 추세 #…`), 머리말의 n·x̄·σ(n=100). 정답 토글을 켜서 점선 테두리가 음영과 구분되는지 본다. 확인 후 서버를 끈다.

- [ ] **Step 7: 커밋**

```bash
git add spc_explainer/charts.py tests/test_charts.py streamlit_app.py
git commit -m "feat: 관리도 스타일 (규칙 구간 음영·라벨, 패턴별 마커, n·x̄·σ 머리말)" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
git push origin main
```

---

### Task 11-4: 검증 대시보드·탐지율 막대·버전 고정 (5절 8~11번, 시안 `docs/design/ref/detection-bars.png`)

**Files:**
- Create: `spc_explainer/ui_dashboard.py`, `tests/test_ui_dashboard.py`
- Modify: `streamlit_app.py`, `tests/test_app.py` (테스트 1개 덧붙임), `requirements.txt`

**Interfaces:**
- Consumes: `results/metrics.json` 형태(Task 8·9), `results/explanations.json` 형태(Task 9), `ui_html.*`
- Produces:
  - `ui_dashboard.fmt_pct(x) -> str` ("63.3%", "100%"), `ui_dashboard.fmt_num(x) -> str`
  - `ui_dashboard.detection_groups(metrics) -> list[dict]` — 급변·추세·치우침·전체 순. `{"key", "label", "symbol", "rule_id", "injected", "rule": {"rate", "detected"}, "models": [{"name", "repeats", "mean", "min", "max", "mean_detected"}]}`
  - `ui_dashboard.kpi_summary(metrics) -> dict`, `ui_dashboard.fact_lines(metrics) -> list[str]`, `ui_dashboard.explain_error_cases(explanations, limit=8) -> list[dict]`
  - HTML: `title_html`, `kpi_rule_html`, `kpi_llm_html`, `kpi_ai_html`, `detection_bars_html`, `facts_html`, `cases_html`

- [ ] **Step 1: 실패하는 테스트 작성**

Create `tests/test_ui_dashboard.py`:

```python
# 검증 탭 가공: 숫자를 지표 파일에서만 읽는지, 모델별 반복 평균·최소~최대가 맞는지
from spc_explainer.matching import summarize
from spc_explainer.patterns import Event
from spc_explainer.ui_dashboard import (cases_html, detection_bars_html, detection_groups, explain_error_cases,
                                        fact_lines, fmt_num, fmt_pct, kpi_llm_html, kpi_summary)

T = [[Event("spike", 5, 5, "up"), Event("trend", 20, 27, "up")], [Event("shift", 40, 49, "down")], []]
RULES = summarize(T, T)  # 규칙: 3/3
RUN_A = summarize(T, [[Event("spike", 5, 5)], [], []])  # 1/3
RUN_B = summarize(T, [[Event("spike", 5, 5), Event("trend", 21, 22)], [], []])  # 2/3
METRICS = {
    "dataset": {"seed": 7, "n_series": 3, "n_normal": 1, "n_points": 100, "injected": {"spike": 1, "trend": 1, "shift": 1}},
    "rules": RULES,
    "detect": [{"model": "gpt-4.1-mini", "temperature": 0, "repeats": 2, "prompt_version": "detect-v1",
                "runs": [dict(RUN_A, format_violations=0, call_errors=0), dict(RUN_B, format_violations=1, call_errors=0)]}],
    "explain": {"model": "gpt-4.1-mini", "temperature": 0, "repeats": 3, "prompt_version": "explain-v1",
                "series_called": 2, "outputs": 6, "passed": 5, "issue_outputs": {"format": 0, "cause": 1, "mismatch": 0},
                "call_errors": 0, "repeat_changed_series": 1},
    "secom": None,
}


def test_formatting():
    assert fmt_pct(1.0) == "100%" and fmt_pct(0.6333) == "63.3%" and fmt_pct(None) == "-"
    assert fmt_num(3.0) == "3" and fmt_num(1.5) == "1.5"


def test_detection_groups_use_metrics_numbers():
    groups = detection_groups(METRICS)
    assert [g["key"] for g in groups] == ["spike", "trend", "shift", "all"]
    total = groups[-1]
    assert total["injected"] == 3 and total["rule"] == {"rate": 1.0, "detected": 3}
    m = total["models"][0]
    assert m["name"] == "gpt-4.1-mini" and m["repeats"] == 2 and m["mean_detected"] == 1.5
    assert abs(m["mean"] - 0.5) < 1e-9 and abs(m["min"] - 1 / 3) < 1e-9 and abs(m["max"] - 2 / 3) < 1e-9
    trend = groups[1]["models"][0]
    assert trend["min"] == 0.0 and trend["max"] == 1.0


def test_bars_show_rule_and_each_model_with_range():
    h = detection_bars_html(detection_groups(METRICS))
    assert "규칙 판정" in h and "gpt-4.1-mini" in h
    assert "50% (33.3%~66.7%)" in h and "1.5/3" in h and "3/3" in h
    assert "spc-range" in h  # 최소~최대 선
    assert "/20" not in h and "/60" not in h  # 시안 값은 쓰지 않는다


def test_kpis_and_facts():
    k = kpi_summary(METRICS)
    assert k["rule"]["rate"] == 1.0 and k["rule"]["false_events"] == 0
    assert k["models"][0]["format_violations"] == 1 and abs(k["models"][0]["mean"] - 0.5) < 1e-9
    assert "−50.0%p" in kpi_llm_html(k["models"], k["rule"]["rate"])
    lines = fact_lines(METRICS)
    assert lines[0] == "규칙 판정: 심은 이상 3개 중 3개 탐지."
    assert "gpt-4.1-mini" in lines[1] and "치우침" in lines[1]  # 평균 탐지율이 가장 낮은 패턴


def test_error_cases_come_from_saved_explanations():
    explanations = {"series": {"7": {
        "input": {"events": [{"event_id": "E1", "pattern": "급변", "start": 5, "end": 5}]},
        "runs": [{"run": 0, "error": None, "text": "{}", "issues": []},
                 {"run": 1, "error": None, "text": "<b>틀림</b>", "issues": [{"type": "cause", "detail": "'XX-9'는 원인표에 없음"}]}],
    }}}
    cases = explain_error_cases(explanations)
    assert len(cases) == 1 and cases[0]["run"] == 2 and cases[0]["types"] == "원인표 밖 원인"
    assert "◆ 급변 #5" in cases[0]["input"]
    h = cases_html(cases, METRICS["explain"])
    assert "&lt;b&gt;" in h and "문제가 나온 출력 1개 / 전체 6개" in h
    assert "문제가 나온 설명 출력이 없습니다" in cases_html([], METRICS["explain"])
```

Append to `tests/test_app.py` (파일 끝에 추가):

```python
def test_dashboard_renders_from_metrics_without_llm_results(monkeypatch, tmp_path):
    # LLM 결과가 없는 지표 파일로도 검증 탭이 그려져야 한다 (숫자는 파일에서만 읽음)
    import json

    from spc_explainer.experiment import compute_metrics
    from spc_explainer.generator import generate_dataset

    metrics_path = tmp_path / "metrics.json"
    metrics = compute_metrics(generate_dataset(), {}, {})
    metrics_path.write_text(json.dumps(metrics, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(config, "METRICS_PATH", metrics_path)
    monkeypatch.setattr(config, "EXPLANATIONS_PATH", tmp_path / "none.json")
    at = run_app()
    assert not at.exception
```

- [ ] **Step 2: 실패 확인**

Run: `.venv/Scripts/python -m pytest tests/test_ui_dashboard.py -v`
Expected: 수집 오류 `ModuleNotFoundError: No module named 'spc_explainer.ui_dashboard'`

- [ ] **Step 3: 대시보드 가공·HTML 구현**

Create `spc_explainer/ui_dashboard.py`:

```python
# 검증 탭(규칙 판정 vs LLM 단독 판정)의 지표 가공과 HTML.
# 스타일 출처: docs/design/ref/detection-bars.png. 모든 숫자는 metrics.json·explanations.json에서만 읽는다.
from .explain import ISSUE_KO
from .patterns import FROM_KOREAN, KOREAN, PATTERNS
from .ui_html import PATTERN_COLORS, RULE_ID, SYMBOL, esc, span_text

RULE_BAR = "#2a2f35"  # 규칙 판정 막대 (검정)
MODEL_BARS = ["#3e8cc9", "#8cbde6", "#1d5f94"]  # LLM 모델 순서대로 (파랑 계열)
PRINCIPLE = "이 앱은 판정을 규칙이 맡고, AI는 판정 결과를 받아 해석과 점검 순서만 만든다."


def fmt_pct(x) -> str:
    """0.6333 → "63.3%", 1.0 → "100%", None → "-"."""
    if x is None:
        return "-"
    return f"{x * 100:.1f}".rstrip("0").rstrip(".") + "%"


def fmt_num(x) -> str:
    """3.0 → "3", 1.5 → "1.5"."""
    return f"{x:.1f}".rstrip("0").rstrip(".")


def _pair(summary: dict, p: str) -> tuple[int, int]:
    """matching.summarize 결과에서 (탐지 수, 심은 수). p="all"이면 전체."""
    if p == "all":
        return summary["detected"], summary["injected"]
    d = summary["per_pattern"][p]
    return d["detected"], d["injected"]


def _stats(pairs: list[tuple[int, int]]) -> dict:
    """반복별 (탐지 수, 심은 수) → 평균·최소·최대 탐지율과 평균 탐지 수."""
    rates = [d / n for d, n in pairs if n]
    if not rates:
        return {"mean": None, "min": None, "max": None, "mean_detected": 0.0}
    return {"mean": sum(rates) / len(rates), "min": min(rates), "max": max(rates),
            "mean_detected": sum(d for d, _ in pairs) / len(pairs)}


def detection_groups(metrics: dict) -> list[dict]:
    """패턴별(+전체) 규칙 판정 vs 모델별 LLM 단독 판정 탐지율. 막대 그림의 입력."""
    groups = []
    for p in list(PATTERNS) + ["all"]:
        detected, injected = _pair(metrics["rules"], p)
        models = [dict(name=d["model"], repeats=len(d["runs"]), **_stats([_pair(r, p) for r in d["runs"]]))
                  for d in metrics["detect"]]
        groups.append({
            "key": p,
            "label": "전체" if p == "all" else KOREAN[p],
            "symbol": SYMBOL.get(p, ""),
            "rule_id": RULE_ID.get(p, ""),
            "injected": injected,
            "rule": {"rate": detected / injected if injected else None, "detected": detected},
            "models": models,
        })
    return groups


def kpi_summary(metrics: dict) -> dict:
    """KPI 카드 숫자: 규칙 판정, 모델별 LLM 단독 판정(반복 평균·범위), 설명 검증."""
    r = metrics["rules"]
    false_events = sum(r["normal"]["false_events"].values()) + sum(r["anomalous"]["false_events"].values())
    rule = {"rate": r["rate"], "detected": r["detected"], "injected": r["injected"], "false_events": false_events,
            "normal_alarmed": r["normal"]["alarmed_series"], "normal_series": r["normal"]["series"]}
    models = []
    for d in metrics["detect"]:
        stats = _stats([_pair(x, "all") for x in d["runs"]])
        models.append(dict(name=d["model"], repeats=len(d["runs"]), temperature=d["temperature"],
                           format_violations=sum(x["format_violations"] for x in d["runs"]),
                           call_errors=sum(x["call_errors"] for x in d["runs"]), **stats))
    return {"rule": rule, "models": models, "explain": metrics.get("explain")}


def fact_lines(metrics: dict) -> list[str]:
    """수치에서 바로 읽히는 사실만 문장으로 만든다 (결론·추측은 쓰지 않는다)."""
    groups = detection_groups(metrics)
    total = groups[-1]
    lines = [f"규칙 판정: 심은 이상 {total['injected']}개 중 {total['rule']['detected']}개 탐지."]
    for i, model in enumerate(total["models"]):
        per = [(g["models"][i]["mean"], g) for g in groups[:-1] if g["models"][i]["mean"] is not None]
        if not per:
            continue
        low, g = min(per, key=lambda t: t[0])
        if low >= 1:
            lines.append(f"{model['name']}: 모든 패턴에서 반복 평균 100%.")
        else:
            m = g["models"][i]
            lines.append(f"{model['name']}: 반복 평균 탐지율이 가장 낮은 패턴은 {g['label']} "
                         f"({fmt_pct(low)}, 평균 {fmt_num(m['mean_detected'])}/{g['injected']}).")
    lines.append(PRINCIPLE)
    return lines


def explain_error_cases(explanations: dict, limit: int = 8) -> list[dict]:
    """저장된 설명 출력 중 검증에서 문제가 나온 것 (실제 결과 파일만 쓴다)."""
    cases = []
    for sid, entry in (explanations.get("series") or {}).items():
        events = entry.get("input", {}).get("events", [])
        described = " · ".join(
            f'{SYMBOL.get(FROM_KOREAN.get(e["pattern"]), "")} {e["pattern"]} {span_text(e["start"], e["end"])}'
            for e in events)
        for r in entry.get("runs", []):
            if r.get("error") is None and r.get("issues"):
                cases.append({
                    "series": str(sid),
                    "run": r["run"] + 1,
                    "input": described,
                    "excerpt": (r.get("text") or "").replace("\n", " ")[:140],
                    "types": ", ".join(sorted({ISSUE_KO[i["type"]] for i in r["issues"]})),
                    "detail": "; ".join(i["detail"] for i in r["issues"])[:220],
                })
    cases.sort(key=lambda c: (int(c["series"]), c["run"]))
    return cases[:limit]


def title_html(metrics: dict) -> str:
    d = metrics["dataset"]
    counts = " · ".join(f"{KOREAN[p]} {d['injected'][p]}" for p in PATTERNS)
    return ('<div class="spc-dash-title"><b>규칙 판정 vs LLM 단독 판정</b>'
            f'<span>검증 세트 · 규칙 정의대로 이상을 심은 가상 시리즈 {d["n_series"]}개 × {d["n_points"]}점 '
            f'(정상 {d["n_normal"]}개, 심은 이상 {sum(d["injected"].values())}개: {counts}) · 심은 위치를 정답으로 사용</span></div>')


def kpi_rule_html(rule: dict) -> str:
    return ('<div class="spc-kpi"><div class="spc-kpi-top"><span class="b-rule">규칙</span>규칙 판정 탐지율</div>'
            f'<div class="spc-kpi-num">{fmt_pct(rule["rate"])}</div>'
            f'<div class="spc-kpi-sub">{rule["detected"]}/{rule["injected"]} 탐지 · 오탐 {rule["false_events"]}건 '
            f'(정상 시리즈 {rule["normal_alarmed"]}/{rule["normal_series"]}개 경보)</div></div>')


def kpi_llm_html(models: list[dict], rule_rate) -> str:
    rows = []
    for m in models:
        delta = ""
        if m["mean"] is not None and rule_rate is not None:
            diff = f"{(m['mean'] - rule_rate) * 100:+.1f}".replace("-", "−")
            delta = f'<span class="spc-kpi-delta">{diff}%p</span>'
        if m["repeats"] > 1:
            spread = f'반복 {m["repeats"]}회 {fmt_pct(m["min"])}~{fmt_pct(m["max"])}'
        else:
            spread = f'{m["repeats"]}회 실행'
        rows.append(f'<div class="spc-kpi-model"><span class="spc-kpi-name">{esc(m["name"])}</span>'
                    f'<span class="spc-kpi-num sm">{fmt_pct(m["mean"])}</span>{delta}'
                    f'<span class="spc-kpi-sub">{spread} · 형식 위반 {m["format_violations"]} · 호출 오류 {m["call_errors"]}</span></div>')
    body = "".join(rows) or '<div class="spc-kpi-sub">아직 실행하지 않았습니다.</div>'
    return ('<div class="spc-kpi"><div class="spc-kpi-top"><span class="b-ai">LLM</span>LLM 단독 판정 탐지율 (반복 평균)</div>'
            f"{body}</div>")


def kpi_ai_html(e: dict | None) -> str:
    if not e:
        body = '<div class="spc-kpi-sub">아직 실행하지 않았습니다.</div>'
    else:
        io = e["issue_outputs"]
        body = (f'<div class="spc-kpi-num">{e["passed"]}<span class="spc-kpi-unit">/{e["outputs"]}</span></div>'
                f'<div class="spc-kpi-sub">검증 통과 · 형식 위반 {io["format"]} · 원인표 밖 {io["cause"]} · '
                f'판정 불일치 {io["mismatch"]} · 호출 오류 {e["call_errors"]} · '
                f'반복 간 차이 {e["repeat_changed_series"]}/{e["series_called"]}개 시리즈</div>')
    return ('<div class="spc-kpi"><div class="spc-kpi-top"><span class="b-ai-solid">AI 생성</span>AI 설명 검증</div>'
            f"{body}</div>")


def _bar_row(who: str, color: str, rate, lo, hi, value_text: str, frac_text: str) -> str:
    """막대 한 줄: [누구] [회색 바탕 위 채운 막대 (+ 최소~최대 선)] [%·분수]."""
    width = 0.0 if rate is None else max(0.0, min(1.0, rate)) * 100
    whisker = ""
    if lo is not None and hi is not None and hi > lo:
        whisker = f'<span class="spc-range" style="left:{lo * 100:.1f}%;width:{(hi - lo) * 100:.1f}%"></span>'
    return (f'<div class="spc-bar-row"><span class="spc-bar-who">{esc(who)}</span>'
            f'<div class="spc-track"><div class="spc-fill" style="width:{width:.1f}%;background:{color}"></div>{whisker}</div>'
            f'<div class="spc-bar-val"><b>{esc(value_text)}</b> <span>{esc(frac_text)}</span></div></div>')


def detection_bars_html(groups: list[dict]) -> str:
    """패턴별 탐지율: 규칙 판정(검정) vs LLM 단독(모델별 파랑, 반복 평균 + 최소~최대 선)."""
    names = [m["name"] for m in groups[0]["models"]] if groups else []
    legend = f'<span class="spc-lg"><i style="background:{RULE_BAR}"></i>규칙 판정</span>'
    for i, name in enumerate(names):
        legend += f'<span class="spc-lg"><i style="background:{MODEL_BARS[i % len(MODEL_BARS)]}"></i>{esc(name)}</span>'
    parts = [f'<div class="spc-bars-head"><b>패턴별 탐지율</b><span>{legend}</span></div>']
    for g in groups:
        color = PATTERN_COLORS[g["key"]]["text"] if g["key"] in PATTERN_COLORS else "#16191d"
        title = f'{g["symbol"]} {g["label"]}'.strip()
        sub = f'{g["rule_id"]} · {g["injected"]}건' if g["rule_id"] else f'{g["injected"]}건'
        rows = [_bar_row("규칙 판정", RULE_BAR, g["rule"]["rate"], None, None,
                         fmt_pct(g["rule"]["rate"]), f'{g["rule"]["detected"]}/{g["injected"]}')]
        for i, m in enumerate(g["models"]):
            many = m["repeats"] > 1
            value = fmt_pct(m["mean"]) + (f' ({fmt_pct(m["min"])}~{fmt_pct(m["max"])})' if many else "")
            rows.append(_bar_row(m["name"], MODEL_BARS[i % len(MODEL_BARS)], m["mean"],
                                 m["min"] if many else None, m["max"] if many else None,
                                 value, f'{fmt_num(m["mean_detected"])}/{g["injected"]}'))
        cls = "spc-bar-group total" if g["key"] == "all" else "spc-bar-group"
        rows_html = "".join(rows)
        parts.append(f'<div class="{cls}"><div class="spc-bar-name"><b style="color:{color}">{esc(title)}</b>'
                     f'<small>{esc(sub)}</small></div><div class="spc-bar-rows">{rows_html}</div></div>')
    return "".join(parts)


def facts_html(lines: list[str]) -> str:
    items = "".join(f"<p>{esc(t)}</p>" for t in lines)
    return f'<div class="spc-facts"><div class="spc-label">수치로 본 사실</div>{items}</div>'


def cases_html(cases: list[dict], e: dict | None) -> str:
    """AI 설명 오답 사례 표. '수정 후' 열은 두지 않는다 (수정 이력은 docs/ai_errors.md)."""
    total = e["outputs"] if e else 0
    bad = e["outputs"] - e["passed"] - e["call_errors"] if e else 0
    head = ('<div class="spc-cases-head"><b>AI 설명 오답 사례</b>'
            f'<span>검증에서 문제가 나온 출력 {bad}개 / 전체 {total}개 · 최대 8개 표시 · 전체 기록은 docs/ai_errors.md</span></div>')
    if not cases:
        return head + '<div class="spc-cases-empty">검증에서 문제가 나온 설명 출력이 없습니다.</div>'
    rows = ['<div class="spc-case-row th"><span>#</span><span>입력 사건 (규칙 판정)</span><span>AI 출력 발췌</span><span>무엇이 틀렸나</span></div>']
    for n, c in enumerate(cases, start=1):
        rows.append(f'<div class="spc-case-row"><span class="spc-mono">{n:02d}</span>'
                    f'<span>시리즈 {esc(c["series"])} · {c["run"]}회차<small>{esc(c["input"])}</small></span>'
                    f'<span class="spc-quote">{esc(c["excerpt"])}</span>'
                    f'<span><b>{esc(c["types"])}</b><small>{esc(c["detail"])}</small></span></div>')
    return head + "".join(rows)
```

- [ ] **Step 4: 앱의 검증 탭을 대시보드로 교체**

Modify `streamlit_app.py` — 찾을 코드:

```python
from spc_explainer import ui_html, ui_steps
```

바꿀 코드:

```python
from spc_explainer import ui_dashboard, ui_html, ui_steps
```

Modify `streamlit_app.py` — 찾을 코드:

```python
dataset = load_json(config.SERIES_PATH) or generator.generate_dataset()
st.html(ui_html.CSS)
```

바꿀 코드:

```python
def render_dashboard(metrics: dict) -> None:
    """검증 탭 위쪽: KPI 3장, 패턴별 탐지율 막대 + 사실 문장, 설명 오답 사례. 숫자는 결과 파일에서만 읽는다."""
    kpi = ui_dashboard.kpi_summary(metrics)
    st.html(ui_dashboard.title_html(metrics))
    rule_col, llm_col, ai_col = st.columns(3)
    with rule_col, st.container(key="kpi_rule"):
        st.html(ui_dashboard.kpi_rule_html(kpi["rule"]))
    with llm_col, st.container(key="kpi_llm"):
        st.html(ui_dashboard.kpi_llm_html(kpi["models"], kpi["rule"]["rate"]))
    with ai_col, st.container(key="kpi_ai"):
        st.html(ui_dashboard.kpi_ai_html(kpi["explain"]))
    with st.container(key="bars_card"):
        bars_col, facts_col = st.columns([2.6, 1])
        with bars_col:
            st.html(ui_dashboard.detection_bars_html(ui_dashboard.detection_groups(metrics)))
        with facts_col:
            st.html(ui_dashboard.facts_html(ui_dashboard.fact_lines(metrics)))
    explanations = load_json(config.EXPLANATIONS_PATH) or {}
    with st.container(key="cases_card"):
        st.html(ui_dashboard.cases_html(ui_dashboard.explain_error_cases(explanations), kpi["explain"]))


dataset = load_json(config.SERIES_PATH) or generator.generate_dataset()
st.html(ui_html.CSS)
```

Modify `streamlit_app.py` — 찾을 코드:

```python
with tab_report:
    report_md = load_text(config.REPORT_PATH)
    if report_md:
        st.markdown(report_md)
    else:
        st.info("리포트가 아직 없습니다. `python scripts/run_experiment.py`로 만들 수 있습니다.")
```

바꿀 코드:

```python
with tab_report:
    metrics = load_json(config.METRICS_PATH)
    report_md = load_text(config.REPORT_PATH)
    if metrics:
        render_dashboard(metrics)
    if report_md:
        with st.expander("전체 리포트 (docs/validation_report.md)", expanded=not metrics):
            st.markdown(report_md)
    else:
        st.info("리포트가 아직 없습니다. `python scripts/run_experiment.py`로 만들 수 있습니다.")
```

- [ ] **Step 5: Streamlit 버전 고정 (5절 11번)**

화면 CSS가 `st-key-*` 클래스에 기대므로, 배포 환경이 검증한 버전을 쓰게 한다.

Modify `requirements.txt` — 찾을 코드:

```text
streamlit
pycontrolcharts==0.1.2
```

바꿀 코드:

```text
streamlit==1.64.*
pycontrolcharts==0.1.2
```

- [ ] **Step 6: 통과 확인**

Run: `.venv/Scripts/python -m pytest tests/test_ui_dashboard.py tests/test_app.py -v`
Expected: 9 passed

Run: `.venv/Scripts/python -m pytest -q`
Expected: 전체 통과

- [ ] **Step 7: 시안과 눈으로 대조**

Run (백그라운드): `.venv/Scripts/python -m streamlit run streamlit_app.py --server.headless true --server.port 8501`
"검증 리포트" 탭을 `docs/design/ref/detection-bars.png`와 대조한다: 패턴별로 규칙 판정(검정) 한 줄 + 모델별 파랑 막대, 오른쪽 %와 분수, 반복이 2회 이상인 모델의 최소~최대 선. 숫자가 `results/metrics.json`과 같은지 한두 개 대조한다. 확인 후 서버를 끈다.

- [ ] **Step 8: 커밋**

```bash
git add spc_explainer/ui_dashboard.py tests/test_ui_dashboard.py tests/test_app.py streamlit_app.py requirements.txt
git commit -m "feat: 검증 대시보드 (KPI, 모델별 탐지율 막대, 설명 오답 사례), Streamlit 버전 고정" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
git push origin main
```

---

### Task 12: README와 인수인계

**Files:**
- Create: `README.md`
- Modify: `docs/HANDOFF.md` (전체 교체)

**Interfaces:**
- Consumes: 지금까지의 모든 명령과 파일 위치
- Produces: 실행 방법 문서 (CLAUDE.md 요구)

- [ ] **Step 1: README 작성**

Create `README.md` (배포 URL은 Task 11에서 사용자에게 받은 값을 `배포:` 줄에 넣는다. 아직 모르면 그 줄을 빼고 커밋한 뒤, 받는 대로 한 줄을 더한다):

```markdown
# SPC 설명기

반도체 증착 공정(막 두께) 관리도에서 **판정은 규칙 엔진, 설명은 LLM**이 맡는 데모 앱입니다.
SK하이닉스 AI 해커톤 2026 지원용 포트폴리오로 만들었습니다.

- 설계 문서: `docs/superpowers/specs/2026-09-25-spc-explainer-design.md`
- 구현 계획: `docs/superpowers/plans/2026-09-25-spc-explainer.md`
- 검증 리포트: `docs/validation_report.md`
- LLM 오류 기록: `docs/ai_errors.md`
- 화면 설계 비교: `docs/design/2026-09-25-ui-comparison.md` (그래프 시안: `docs/design/ref/`)

## 동작 방식

1. **가상 데이터**: 20개 시리즈 × 100점. 정상 5개, 나머지 15개에 급변·추세·치우침을 규칙 정의대로 심고 위치를 정답으로 남깁니다.
2. **규칙 판정**: pycontrolcharts로 3패턴만 검사합니다. 독립 구현(shewhart)과 점 단위로 일치하는지 테스트합니다.
3. **LLM 설명**: 규칙 판정 결과(JSON)와 원인표만 받아 "어떤 패턴 / 점검 우선순위 / 근거 규칙"을 한국어 JSON으로 씁니다. 검증기가 형식 위반·원인표 밖 원인·판정 불일치를 잡습니다.
4. **비교 실험**: LLM에게 원시 데이터만 주고 직접 판정하게 해서 규칙 엔진과 같은 기준으로 채점합니다.

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

## 설정

`spc_explainer/config.py` 한 곳에서 바꿉니다: 모델명, temperature, 반복 수, `gpt-6-astra` 켜기/끄기, 실시간 호출 한도, 공정 상수.
`gpt-6-astra`는 OpenAI 대시보드에서 모델을 허용한 뒤 `enabled`를 `True`로 바꾸면 단독 판정 비교에 1회 들어갑니다.

## 배포

Streamlit Community Cloud: 레포 `HGK-lab/SPCEXPLANER`, 브랜치 `main`, 파일 `streamlit_app.py`.
실시간 설명을 켜려면 App settings → Secrets에 다음을 넣습니다. 키가 없어도 저장된 결과로 모든 화면이 동작합니다.

    OPENAI_API_KEY = "sk-..."

## 가정과 한계

- 관리한계 고정값(중심 100nm, UCL 103nm, LCL 97nm) 사용 = 이미 안정화된 공정을 감시하는 상황을 가정합니다.
- 추세는 "연속 6점이 계속 증가/감소"(증가 5회)로 정의했습니다. pycontrolcharts 기본값(7점)과 달라 `test3_n=5`로 맞췄습니다.
- 원인표는 교과서 수준의 도메인 가정이며 실제 설비 데이터로 검증하지 않았습니다.
- 합성 데이터라 실제 공정의 잡음 구조를 반영하지 않고, 표본(시리즈 20개, 이상 21개)이 작습니다.
```

- [ ] **Step 2: HANDOFF 갱신**

Modify `docs/HANDOFF.md` — 전체를 현재 상태로 교체한다. 들어갈 내용: 마지막 갱신 날짜, 현재 단계(구현 완료한 태스크 번호), 완료 목록, 다음 할 일(남은 태스크와 첫 명령), 사용자 결정 사항(기존 항목 + LLM 구성·추가 요구 4가지·추세 정의), 막힌 점. 기존 HANDOFF의 "사용자 결정 사항" 항목은 그대로 유지한다.

- [ ] **Step 3: 커밋**

```bash
git add README.md docs/HANDOFF.md
git commit -m "docs: README 실행 방법과 인수인계 갱신" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
git push origin main
```

---

### Task 13: SECOM 실데이터 확인 (시간이 부족하면 이 태스크 전체를 뺀다)

**Files:**
- Create: `spc_explainer/secom.py`, `scripts/fetch_secom.py`, `tests/test_secom.py`, `data/secom/secom_selected.csv`(스크립트 산출물)
- Modify: `spc_explainer/experiment.py`, `streamlit_app.py`, `README.md`

**Interfaces:**
- Consumes: `config.SECOM_*`, `rules.detect`, `patterns.Event/PATTERNS`, `charts.control_chart`, `report.secom_section`(Task 8)
- Produces:
  - `secom.select_sensors(X: DataFrame, phase1_n=..., k=..., min_unique=..., max_abs_skew=...) -> list`
  - `secom.phase1_limits(values) -> {"center", "sigma", "ucl", "lcl"}`
  - `secom.monitor(values, phase1_n=...) -> tuple[dict, list[Event]]` (사건 번호는 전체 시계열 기준)
  - `secom.overlap_summary(events, labels, phase1_n=...) -> dict`
  - `secom.load(path=config.SECOM_PATH) -> DataFrame | None`, `secom.summarize(df, phase1_n=...) -> dict` (Task 8의 `secom` 형태)

- [ ] **Step 1: 실패하는 테스트 작성**

Create `tests/test_secom.py`:

```python
# SECOM 확인 로직: 센서 선정(라벨 미사용), Phase I 한계, Phase II 번호 보정, 겹침 관찰
import numpy as np
import pandas as pd

from spc_explainer import secom
from spc_explainer.patterns import Event
from spc_explainer.report import secom_section


def test_phase1_limits_use_moving_range():
    lim = secom.phase1_limits([10, 12, 10, 12])
    assert lim["center"] == 11
    assert abs(lim["sigma"] - 2 / 1.128) < 1e-9
    assert abs(lim["ucl"] - (11 + 3 * 2 / 1.128)) < 1e-9


def test_select_sensors_uses_only_distribution():
    rng = np.random.default_rng(0)
    X = pd.DataFrame({
        0: rng.normal(0, 1, 600),  # 후보
        1: rng.exponential(1, 600),  # 왜도 큼 → 제외
        2: np.r_[[np.nan], rng.normal(0, 1, 599)],  # 결측 → 제외
        3: rng.integers(0, 5, 600).astype(float),  # 고유값 적음 → 제외
        4: rng.normal(5, 2, 600),  # 후보
        5: rng.normal(0, 1, 600),  # 후보지만 k=2라 제외
    })
    assert secom.select_sensors(X, phase1_n=500, k=2) == [0, 4]


def test_monitor_shifts_indices_to_full_series():
    values = [0.0, 1.0] * 250 + [10.0] + [0.5] * 20
    lim, evs = secom.monitor(values, phase1_n=500)
    assert Event("spike", 500, 500, "up") in evs
    assert all(e.start >= 500 for e in evs)


def test_overlap_summary_counts():
    labels = [-1] * 10 + [1, -1, -1, 1, -1]
    evs = [Event("spike", 10, 10, "up"), Event("trend", 12, 14, "down")]
    s = secom.overlap_summary(evs, labels, phase1_n=10)
    assert s["events"] == 2 and s["events_with_fail"] == 2
    assert s["by_pattern"] == {"spike": 1, "trend": 1, "shift": 0}
    assert s["flagged_points"] == 4
    assert s["fail_rate_flagged"] == 0.5 and s["fail_rate_phase2"] == 0.4


def test_summarize_feeds_report_section():
    df = pd.DataFrame({"label": [-1] * 510 + [1] * 10, "sensor_7": [0.0, 1.0] * 250 + [10.0] + [0.5] * 19})
    text = "\n".join(secom_section(secom.summarize(df, phase1_n=500)))
    assert "| sensor_7 |" in text and "탐지율은 계산하지 않는다" in text
```

- [ ] **Step 2: 실패 확인**

Run: `.venv/Scripts/python -m pytest tests/test_secom.py -v`
Expected: `ImportError: cannot import name 'secom' from 'spc_explainer'`

- [ ] **Step 3: SECOM 모듈 구현**

Create `spc_explainer/secom.py`:

```python
# UCI SECOM 실데이터 확인: 센서 선정(불량 라벨 미사용), Phase I 한계 추정, Phase II 감시, 불량 라벨과의 겹침 관찰
from pathlib import Path

import numpy as np
import pandas as pd

from . import config, rules
from .patterns import PATTERNS, Event

D2 = 1.128  # 크기 2 이동범위의 d2 상수 (σ = 평균 이동범위 / d2)


def select_sensors(X: pd.DataFrame, phase1_n: int = config.SECOM_PHASE1_N, k: int = config.SECOM_N_SENSORS,
                   min_unique: int = config.SECOM_MIN_UNIQUE,
                   max_abs_skew: float = config.SECOM_MAX_ABS_SKEW) -> list:
    """결측 0 + Phase I 고유값 min_unique 이상 + Phase I 왜도 절댓값 max_abs_skew 이하 → 번호 순 앞 k개.
    불량 라벨은 받지 않는다 (결과를 보고 센서를 고르는 것을 막기 위해)."""
    phase1 = X.iloc[:phase1_n]
    missing = X.isna().sum()
    ok = [c for c in X.columns
          if missing[c] == 0 and phase1[c].nunique() >= min_unique and abs(phase1[c].skew()) <= max_abs_skew]
    return ok[:k]


def phase1_limits(values) -> dict:
    """Phase I 구간으로 관리한계를 추정한다: 중심선 = 평균, σ = 평균 이동범위 / 1.128."""
    a = np.asarray(values, dtype=float)
    center = float(a.mean())
    sigma = float(np.abs(np.diff(a)).mean() / D2)
    return {"center": center, "sigma": sigma, "ucl": center + 3 * sigma, "lcl": center - 3 * sigma}


def monitor(values, phase1_n: int = config.SECOM_PHASE1_N) -> tuple[dict, list[Event]]:
    """앞 phase1_n점으로 한계를 정하고 나머지를 같은 규칙으로 감시한다. 사건 번호는 전체 시계열 기준."""
    v = [float(x) for x in values]
    limits = phase1_limits(v[:phase1_n])
    found = rules.detect(v[phase1_n:], center=limits["center"], ucl=limits["ucl"], lcl=limits["lcl"])
    return limits, [Event(e.pattern, e.start + phase1_n, e.end + phase1_n, e.direction) for e in found]


def overlap_summary(events: list[Event], labels, phase1_n: int = config.SECOM_PHASE1_N) -> dict:
    """알람과 불량 라벨(1)의 겹침 관찰. 탐지율이 아니다."""
    fail = np.asarray(labels) == 1
    flagged = np.zeros(len(fail), dtype=bool)
    for e in events:
        flagged[e.start:e.end + 1] = True
    fail2, flagged2 = fail[phase1_n:], flagged[phase1_n:]
    return {
        "events": len(events),
        "by_pattern": {p: sum(1 for e in events if e.pattern == p) for p in PATTERNS},
        "events_with_fail": sum(1 for e in events if fail[e.start:e.end + 1].any()),
        "flagged_points": int(flagged2.sum()),
        "fail_rate_flagged": float(fail2[flagged2].mean()) if flagged2.any() else None,
        "fail_rate_phase2": float(fail2.mean()),
    }


def load(path: Path = config.SECOM_PATH) -> pd.DataFrame | None:
    """선정 센서 CSV (timestamp, label, sensor_*). 없으면 None."""
    return pd.read_csv(path, parse_dates=["timestamp"]) if path.exists() else None


def summarize(df: pd.DataFrame, phase1_n: int = config.SECOM_PHASE1_N) -> dict:
    """센서별 Phase I 한계·Phase II 알람·불량 겹침 요약 (metrics.json·리포트용)."""
    labels = df["label"].tolist()
    sensors = {}
    for name in [c for c in df.columns if c.startswith("sensor_")]:
        limits, events = monitor(df[name].tolist(), phase1_n)
        sensors[name] = {"limits": limits, **overlap_summary(events, labels, phase1_n)}
    return {"n": len(df), "phase1_n": phase1_n, "sensors": sensors}
```

Run: `.venv/Scripts/python -m pytest tests/test_secom.py -v`
Expected: 5 passed

- [ ] **Step 4: 다운로드 스크립트 구현·실행**

Create `scripts/fetch_secom.py`:

```python
# UCI SECOM을 받아 선정 센서만 CSV로 저장한다. 한 번 실행하고 결과 CSV를 커밋한다.
# 사용법: python scripts/fetch_secom.py
import io
import sys
import urllib.request
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # 저장소 루트를 import 경로에 추가

import pandas as pd  # noqa: E402

from spc_explainer import config  # noqa: E402
from spc_explainer.secom import select_sensors  # noqa: E402


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # 윈도 콘솔에서도 한글이 깨지지 않게
    raw = urllib.request.urlopen(config.SECOM_URL, timeout=120).read()
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        X = pd.read_csv(z.open("secom.data"), sep=r"\s+", header=None)
        L = pd.read_csv(z.open("secom_labels.data"), sep=r"\s+", header=None, names=["label", "timestamp"])
    ts = pd.to_datetime(L["timestamp"], format="%d/%m/%Y %H:%M:%S")
    order = ts.argsort(kind="stable")  # 시간순 정렬 (원본도 이미 시간순)
    X = X.iloc[order].reset_index(drop=True)
    L = L.iloc[order].reset_index(drop=True)
    ts = ts.iloc[order].reset_index(drop=True)
    cols = select_sensors(X)
    if len(cols) < config.SECOM_N_SENSORS:
        sys.exit(f"조건에 맞는 센서가 {len(cols)}개뿐입니다: {cols}")
    out = pd.DataFrame({"timestamp": ts, "label": L["label"]})
    for c in cols:
        out[f"sensor_{c}"] = X[c]
    config.SECOM_PATH.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(config.SECOM_PATH, index=False)
    print(f"선정 센서 {cols} -> {config.SECOM_PATH} ({len(out)}행)")


if __name__ == "__main__":
    main()
```

Run: `.venv/Scripts/python scripts/fetch_secom.py`
Expected: `선정 센서 [88, 115] -> ...secom_selected.csv (1567행)` (2026-09-25 설계 때 확인한 결과와 같아야 한다)

- [ ] **Step 5: 실험 지표에 SECOM 연결**

Modify `spc_explainer/experiment.py` — 찾을 코드:

```python
from . import config, explain, generator, llm_detect, report, rules
```

바꿀 코드:

```python
from . import config, explain, generator, llm_detect, report, rules, secom
```

Modify `spc_explainer/experiment.py` — 찾을 코드:

```python
    ai_errors: Path = config.AI_ERRORS_PATH

    @staticmethod
    def under(root: Path) -> "Paths":
        """테스트용: 모든 파일을 root 아래에 둔다."""
        return Paths(root / "series.json", root / "explanations.json", root / "llm_detections.json",
                     root / "metrics.json", root / "report.md", root / "ai_errors.md")
```

바꿀 코드:

```python
    ai_errors: Path = config.AI_ERRORS_PATH
    secom: Path = config.SECOM_PATH

    @staticmethod
    def under(root: Path) -> "Paths":
        """테스트용: 모든 파일을 root 아래에 둔다."""
        return Paths(root / "series.json", root / "explanations.json", root / "llm_detections.json",
                     root / "metrics.json", root / "report.md", root / "ai_errors.md", root / "secom.csv")
```

Modify `spc_explainer/experiment.py` — 찾을 코드:

```python
def compute_metrics(dataset: dict, explanations: dict, detections: dict) -> dict:
```

바꿀 코드:

```python
def compute_metrics(dataset: dict, explanations: dict, detections: dict, secom_df=None) -> dict:
```

Modify `spc_explainer/experiment.py` — 찾을 코드:

```python
        "secom": None,
```

바꿀 코드:

```python
        "secom": secom.summarize(secom_df) if secom_df is not None else None,
```

Modify `spc_explainer/experiment.py` — 찾을 코드:

```python
    metrics = compute_metrics(dataset, explanations, detections)
```

바꿀 코드:

```python
    metrics = compute_metrics(dataset, explanations, detections, secom.load(paths.secom))
```

- [ ] **Step 6: 화면에 SECOM 탭 추가**

Modify `streamlit_app.py` — 찾을 코드:

```python
from spc_explainer import config, explain, generator, llm_client, rules
```

바꿀 코드:

```python
from spc_explainer import config, explain, generator, llm_client, rules, secom
```

Modify `streamlit_app.py` — 찾을 코드:

```python
tab_main, tab_report = st.tabs(["판정·설명", "검증 리포트"])
```

바꿀 코드:

```python
tab_main, tab_report, tab_secom = st.tabs(["판정·설명", "검증 리포트", "실데이터 (SECOM)"])
```

Modify `streamlit_app.py` — 찾을 코드 (파일 끝):

```python
        st.info("리포트가 아직 없습니다. `python scripts/run_experiment.py`로 만들 수 있습니다.")
```

바꿀 코드:

```python
        st.info("리포트가 아직 없습니다. `python scripts/run_experiment.py`로 만들 수 있습니다.")


def pct(x) -> str:
    return "-" if x is None else f"{x:.1%}"


with tab_secom:
    secom_df = secom.load()
    if secom_df is None:
        st.info("SECOM 데이터가 없습니다. `python scripts/fetch_secom.py`로 받을 수 있습니다.")
    else:
        sensors = [c for c in secom_df.columns if c.startswith("sensor_")]
        sensor = st.selectbox("센서", sensors)
        secom_values = secom_df[sensor].tolist()
        labels = secom_df["label"].tolist()
        limits, alarms = secom.monitor(secom_values)
        overlap = secom.overlap_summary(alarms, labels)
        fail_idx = [i for i, v in enumerate(labels) if v == 1]
        st.plotly_chart(control_chart(secom_values, alarms, limits["center"], limits["ucl"], limits["lcl"],
                                      phase_boundary=config.SECOM_PHASE1_N, fail_idx=fail_idx, y_title=sensor),
                        width="stretch")
        c1, c2, c3 = st.columns(3)
        c1.metric("Phase II 알람 사건", overlap["events"])
        c2.metric("불량이 포함된 알람 사건", overlap["events_with_fail"])
        c3.metric("알람 점 중 불량 비율", pct(overlap["fail_rate_flagged"]),
                  help=f"Phase II 전체 불량 비율 {pct(overlap['fail_rate_phase2'])}")
        st.caption(
            f"시간순 앞 {config.SECOM_PHASE1_N}점(Phase I)으로 한계를 추정하고 나머지를 같은 규칙으로 감시합니다. "
            "정답이 없어 탐지율은 계산하지 않으며, 불량 라벨과의 겹침은 관찰일 뿐 인과나 성능이 아닙니다. "
            "데이터: UCI SECOM (McCann & Johnston, 2008), CC BY 4.0."
        )
```

- [ ] **Step 7: 리포트 다시 만들고 전체 테스트**

Run: `.venv/Scripts/python scripts/run_experiment.py --no-llm`
Expected: LLM 호출 없이 끝나고, `docs/validation_report.md` 5절에 `sensor_88`, `sensor_115` 행이 생긴다.

Run: `.venv/Scripts/python -m pytest -q`
Expected: 전체 통과 (`test_app`이 SECOM 탭까지 그린다)

- [ ] **Step 8: README에 SECOM 추가**

Modify `README.md` — 찾을 코드:

```markdown
## 설정
```

바꿀 코드:

```markdown
SECOM 실데이터 (선택, 한 번만):

    python scripts/fetch_secom.py

## 설정
```

Modify `README.md` — 찾을 코드:

```markdown
- 합성 데이터라 실제 공정의 잡음 구조를 반영하지 않고, 표본(시리즈 20개, 이상 21개)이 작습니다.
```

바꿀 코드:

```markdown
- 합성 데이터라 실제 공정의 잡음 구조를 반영하지 않고, 표본(시리즈 20개, 이상 21개)이 작습니다.
- SECOM은 정답이 없어 탐지율을 계산하지 않습니다. 앞 500점으로 한계를 추정하고 나머지를 감시해 "작동 확인 + 불량 라벨과의 겹침 관찰"만 보고합니다.

## 데이터 출처

- UCI SECOM: McCann, M. & Johnston, A. (2008). SECOM [Dataset]. UCI Machine Learning Repository. https://doi.org/10.24432/C54305 (CC BY 4.0). `data/secom/secom_selected.csv`는 이 데이터에서 센서 2개와 라벨·시각만 뽑은 것입니다.
```

- [ ] **Step 9: 커밋**

```bash
git status --short   # .env가 없어야 함
git add spc_explainer/secom.py spc_explainer/experiment.py scripts/fetch_secom.py tests/test_secom.py data/secom/secom_selected.csv streamlit_app.py README.md results/metrics.json docs/validation_report.md
git commit -m "feat: SECOM 실데이터 확인 (Phase I 한계 추정, 불량 라벨 겹침 관찰)" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
git push origin main
```

---

## 자체 점검 기록

- 스펙 대응: 1절(성공 기준) → Task 10·11, 2절(원칙) → Global Constraints·Task 6·11, 3절(규칙) → Task 3, 4절(데이터) → Task 2, 5절(채점) → Task 4, 6.1(모델 설정) → Task 1·5, 6.2(설명) → Task 6, 6.3(단독 판정) → Task 7, 6.4(반복·캐시·ai_errors) → Task 9·10, 7절(SECOM) → Task 13, 9절(화면) → Task 11·13, 10절(오류 처리) → Task 5·9·11, 11절(테스트) → 각 태스크, 12절(배포) → Task 1·11·12, 13절(우선순위) → 태스크 순서.
- 이름 일관성: `Event`, `detect`, `describe`, `classify`, `summarize`, `build_input`, `build_messages`, `validate`, `signature`, `parse`, `call_json`, `LLMReply`, `run_all`, `Paths`, `control_chart`, `secom_section`을 정의한 태스크와 쓰는 태스크에서 같은 시그니처로 썼다.
- 실행 검증 (2026-09-25, 계획 작성 중): 이 문서의 코드 블록을 그대로 추출해 Python 3.10.11 + pycontrolcharts 0.1.2 + shewhart 0.1.1 + Streamlit 1.64.0 + openai 3.19.2로 실행했다.
  - Task 1~12 상태: 테스트 55개 통과 (shewhart 교차 검증 3개 시드 포함). Task 13 적용 후: 60개 통과.
  - `fetch_secom.py` 실제 다운로드 → 센서 [88, 115], 1567행. `run_experiment.py --no-llm` → 규칙 탐지 21/21, 정상 시리즈 5개 중 1개 경보, 오탐 사건 6개.
  - 가짜 LLM으로 `results/`를 채운 뒤 AppTest로 20개 시리즈·3개 탭을 모두 그려 예외 없음 확인.
  - 실제 모델 스모크 호출 3회(시리즈 14): 설명 4.1-mini 검증 통과, 단독 판정 sol 정확, 단독 판정 4.1-mini는 추세를 놓치고 없는 사건 7개를 냈다 (`docs/ai_errors.md`에 기록).
- 화면 절충안 C 추가 후 재검증 (2026-09-25): 태스크 경계마다 새로 추출해 전체 테스트 — Task 11 55개 → 11-1 59개 → 11-2 65개 → 11-3 69개 → 11-4 75개 → Task 13 80개, 모두 통과. Task 13의 찾아 바꾸기 세 곳이 11-1~11-4 이후에도 그대로 맞는 것을 확인.
  - 가짜 LLM(모델·반복별로 일부 사건을 빠뜨림)으로 결과를 채우고 실제 Streamlit 화면을 헤드리스 Chrome으로 캡처해 `docs/design/ref/` 시안과 대조했다: 관리도(음영+라벨, 점선 한계+오른쪽 라벨, ◆▲■, n·x̄·σ, 정답 점선 테두리), 탐지율 막대(규칙 검정 + 모델별 파랑 + 최소~최대 선), SECOM 탭(사건 24개 → 음영 라벨 자동 생략).
  - 대조 중 고친 것: 모노 글꼴에 한글이 없어 막대의 "규칙 판정"·오답 발췌가 벌어져 보임 → 두 클래스만 산세리프로. Plotly 범례에 기호가 겹쳐 "◆ ◆ 급변"으로 보임 → 트레이스 이름에서 기호 제거.
