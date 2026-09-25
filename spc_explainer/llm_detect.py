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
