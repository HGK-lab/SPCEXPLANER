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
