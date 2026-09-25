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
