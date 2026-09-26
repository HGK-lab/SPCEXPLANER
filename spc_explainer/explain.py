# 설명 LLM: 규칙 판정 결과(JSON)와 원인표를 받아 한국어 설명 JSON을 만든다. 출력 검증기 포함.
import json

from . import config
from .causes import CAUSES, rows_for
from .patterns import FROM_KOREAN, KOREAN, Event
from .rules import SPIKE_LISTED, describe

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


def build_input(values, events: list[Event], limits: dict | None = None) -> dict:
    """설명 LLM 입력: 공정 정보 + 규칙 사건 요약 + 해당 패턴의 원인표. 원시 시계열은 넣지 않는다.
    limits = {"center", "ucl", "lcl"} (06 내 데이터 판정). 없으면 설정값 — 저장된 실험 입력과 글자까지 같다."""
    lim = limits or {"center": config.CENTER, "ucl": config.UCL, "lcl": config.LCL}
    items = []
    for i, ev in enumerate(events, start=1):
        seg = [float(v) for v in values[ev.start:ev.end + 1]]
        item = {
            "event_id": f"E{i}",
            "pattern": KOREAN[ev.pattern],
            "direction": DIRECTION_KO[ev.pattern][ev.direction],
            "start": ev.start,
            "end": ev.end,
            "rule": describe(ev, values, lim["ucl"], lim["lcl"]),
        }
        if ev.pattern == "spike" and len(seg) > SPIKE_LISTED:  # 원시 시계열을 넣지 않도록 요약
            item["values"] = seg[:SPIKE_LISTED]
            item["n_points"], item["min"], item["max"] = len(seg), min(seg), max(seg)
        elif ev.pattern == "spike":
            item["values"] = seg
        elif ev.pattern == "trend":
            item["first_value"], item["last_value"] = seg[0], seg[-1]
        else:
            item["mean"] = round(sum(seg) / len(seg), 2)
        items.append(item)
    table = rows_for({ev.pattern for ev in events})
    return {
        "process": {"name": config.PROCESS_NAME, "unit": config.UNIT, "target": lim["center"],
                    "ucl": lim["ucl"], "lcl": lim["lcl"]},
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
