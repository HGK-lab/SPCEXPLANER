# 사건별 "지금 확인할 것" 체크리스트와 교대 인수인계 메모.
# 항목은 원인표(causes)에서만 가져온다. AI 설명은 검증을 통과했을 때 점검 순서만 바꾼다 (항목을 새로 만들지 않는다).
from . import config
from .causes import CAUSES
from .patterns import FROM_KOREAN, KOREAN, Event
from .rules import describe
from .ui_html import SYMBOL, span_text


def ai_order(data: dict | None, inp: dict) -> dict[str, list[tuple[str, str]]]:
    """AI 설명에서 사건별 (원인 id, 이유) 순서. 원인표에 있고 사건과 같은 패턴인 id만 남긴다.
    모양이 틀린 출력도 예외 없이 처리한다. 검증을 통과한 설명에만 쓴다 (호출하는 쪽이 판단)."""
    if not isinstance(data, dict):
        return {}
    patterns = {e["event_id"]: FROM_KOREAN.get(e["pattern"]) for e in inp["events"]}
    order: dict[str, list[tuple[str, str]]] = {}
    for ev in data.get("events") if isinstance(data.get("events"), list) else []:
        if not isinstance(ev, dict) or str(ev.get("event_id")) in order:
            continue
        eid = str(ev.get("event_id"))
        picked: list[tuple[str, str]] = []
        for c in ev.get("checks") if isinstance(ev.get("checks"), list) else []:
            cid = c.get("cause_id") if isinstance(c, dict) else None
            if (isinstance(cid, str) and cid in CAUSES and CAUSES[cid]["pattern"] == patterns.get(eid)
                    and cid not in [p[0] for p in picked]):
                reason = c.get("reason")
                picked.append((cid, " ".join(reason.split()) if isinstance(reason, str) else ""))
        order[eid] = picked
    return order


def build(events: list[Event], values, limits: dict | None = None,
          order: dict[str, list[tuple[str, str]]] | None = None) -> list[dict]:
    """사건마다 {event_id, pattern, title, rule, items}. items는 그 패턴의 원인표 행 전부:
    AI 순서에 있는 원인이 먼저(ai_rank 1부터, ai_reason 포함), 나머지는 원인표 순서."""
    lim = limits or {"ucl": config.UCL, "lcl": config.LCL}
    cards = []
    for i, ev in enumerate(events, start=1):
        eid = f"E{i}"
        ranked = [(cid, why) for cid, why in (order or {}).get(eid, [])
                  if cid in CAUSES and CAUSES[cid]["pattern"] == ev.pattern]
        ranked_ids = [cid for cid, _ in ranked]
        rest = [cid for cid, row in CAUSES.items() if row["pattern"] == ev.pattern and cid not in ranked_ids]
        items = []
        for cid in ranked_ids + rest:
            rank = ranked_ids.index(cid) + 1 if cid in ranked_ids else None
            items.append({"cause_id": cid, "check": CAUSES[cid]["check"], "cause": CAUSES[cid]["cause"],
                          "ai_rank": rank, "ai_reason": ranked[rank - 1][1] if rank else ""})
        cards.append({"event_id": eid, "pattern": ev.pattern,
                      "title": f"{eid} · {SYMBOL[ev.pattern]} {KOREAN[ev.pattern]} {span_text(ev.start, ev.end)}",
                      "rule": describe(ev, values, lim["ucl"], lim["lcl"]), "items": items})
    return cards


def item_label(item: dict) -> str:
    """체크박스 글자: 원인표의 점검 항목과 원인 (+ AI 추천 순위)."""
    rank = f" · AI 추천 {item['ai_rank']}순위" if item["ai_rank"] else ""
    return f"{item['check']} — {item['cause']}{rank}"


def handover_md(title: str, now: str, cards: list[dict], checked: set[tuple[str, str]], ai: dict | None) -> str:
    """교대 인수인계 메모(마크다운 글자). checked = {(사건 id, 원인 id)}.
    ai = {"model", "status", "summary"} 또는 None. 판정은 규칙 엔진, 설명은 AI(참고)라고 적는다."""
    lines = [f"# SPC 판정 인수인계 — {title}", "",
             f"작성 {now} · 판정은 규칙 엔진(확정), 설명은 AI(참고용)", "", "## 규칙 판정 (확정)", ""]
    lines += [f"- {c['title']} — {c['rule']}" for c in cards] or ["- 이상 없음"]
    lines += ["", "## AI 설명 (참고용)", ""]
    if ai:
        lines += [f"- 모델: {ai['model']} · {ai['status']}", f"- 요약: {' '.join(str(ai['summary']).split())}"]
    else:
        lines.append("- 없음")
    lines += ["", "## 지금 확인할 것 (원인표 기준)"]
    for c in cards:
        lines += ["", f"### {c['title']}"]
        for it in c["items"]:
            mark = "x" if (c["event_id"], it["cause_id"]) in checked else " "
            why = f" (AI: {it['ai_reason']})" if it["ai_reason"] else ""
            lines.append(f"- [{mark}] {item_label(it)}{why}")
    return "\n".join(lines) + "\n"
