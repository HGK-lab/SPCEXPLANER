# 02 규칙 판정 카드와 03 AI 설명 카드의 HTML, 점검 우선순위 가공. 판정은 항상 규칙 결과가 기준이다.
from .causes import CAUSES
from .explain import ISSUE_KO
from .patterns import FROM_KOREAN, KOREAN, Event
from .rules import describe
from .ui_html import PATTERN_COLORS, RULE_ID, SYMBOL, esc, span_text


def _split_rule(sentence: str) -> tuple[str, str]:
    """rules.describe 문장을 주문장과 괄호 속 세부로 나눈다."""
    main, _, rest = sentence.partition(" (")
    return main, rest[:-1] if rest.endswith(")") else rest


def rule_card_html(events: list[Event], values) -> str:
    """규칙 판정 결과 카드: 머리줄(확정·건수) + 사건 표(패턴·구간·판정 근거·규칙 번호) + 결정적 계산 문구."""
    head = ('<div class="spc-step-head rule"><b>규칙 판정 결과</b>'
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
    """AI 설명 머리줄. issues가 None이면 검증 배지 없음(보여줄 출력 없음), []이면 검증 통과."""
    if issues is None:
        badge = ""
    elif not issues:
        badge = '<span class="spc-tag-pass">✓ 검증 통과</span>'
    else:
        names = ", ".join(sorted({ISSUE_KO[i["type"]] for i in issues}))
        badge = f'<span class="spc-tag-fail">⚠ 문제 있음: {esc(names)}</span>'
    return ('<div class="spc-step-head ai"><b>AI 설명</b>'
            f'<span class="spc-tag-ai">AI 생성</span>{badge}'
            '<span class="spc-muted">참고용 해석 · 판정은 규칙 기준</span></div>')


def issues_html(issues: list[dict]) -> str:
    """검증 문제 목록. 판정은 규칙 판정 결과를 따르라고 적는다."""
    items = "".join(f"<li>{esc(ISSUE_KO[i['type']])}: {esc(i['detail'])}</li>" for i in issues)
    return ('<div class="spc-issues">검증에서 문제가 발견됐습니다. 판정은 위 규칙 판정 결과를 따르세요.'
            f"<ul>{items}</ul></div>")


def status_html(text: str) -> str:
    return f'<div class="spc-status"><span class="spc-dot"></span>{esc(text)}</div>'


def run_line_html(run_no: int, state: str, items: list[dict] | None) -> str:
    """'같은 입력 반복 결과'의 한 줄. LLM이 준 사건·원인 id는 이스케이프해 글자 그대로 보인다
    (st.markdown에 넣으면 링크 서식이 해석된다). items가 None이면 호출 오류 줄."""
    head = f'<div class="spc-run"><b>{run_no}회차</b> · {esc(state)}'
    if items is None:
        return head + "</div>"
    order = " → ".join(f"{it['event_id']}:{it['cause_id']}" for it in items) or "-"
    return head + f" · 점검 순서 {esc(order)}</div>"


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
    """패턴 해석(summary) + 점검 우선순위 목록. LLM 문자열은 모두 이스케이프한다."""
    summary = data.get("summary") if isinstance(data.get("summary"), str) else ""
    rows = []
    for it in priority_items(data, inp):
        cls = "spc-prio-row" if it["known"] else "spc-prio-row unknown"
        rows.append(
            f'<div class="{cls}"><span class="spc-rank">{it["rank"]}</span>'
            f'<div><div class="spc-prio-title">{esc(it["title"])}</div>'
            f'<div class="spc-prio-sub">{esc(it["cause_id"])} · {esc(it["cause"])} — {esc(it["reason"])}</div></div>'
            f'<span class="spc-chips"><span class="spc-chip">{esc(it["rule_id"])}</span>'
            f'<span class="spc-chip">{esc(it["event_id"])}</span></span></div>'
        )
    rows_html = "".join(rows) or '<div class="spc-prio-sub">점검 항목 없음</div>'
    return ('<div class="spc-ai-body"><div class="spc-label">패턴 해석</div>'
            f'<div class="spc-summary">{esc(summary)}</div>'
            f'<div class="spc-label">점검 우선순위</div><div class="spc-prio">{rows_html}</div></div>')
