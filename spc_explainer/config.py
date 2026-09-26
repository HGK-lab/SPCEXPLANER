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
CASE_NOTES_PATH = ROOT / "docs" / "case_notes.md"  # 04 검증의 사례 해설(수동 분석)

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
