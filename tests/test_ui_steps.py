# 규칙 판정 카드·AI 설명 카드: 규칙 번호, 구간 표기, 검증 배지, 점검 우선순위 펼치기, HTML 이스케이프
import json

from spc_explainer.explain import build_input
from spc_explainer.patterns import Event
from spc_explainer.ui_steps import (ai_body_html, ai_head_html, issues_html, priority_items, rule_card_html,
                                    run_line_html)

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
    assert "규칙 판정 결과" in h and "확정" in h and "2건 감지" in h
    assert "#14" in h and "#40–49" in h and ">R1<" in h and ">R2<" in h
    assert "관리한계 밖 1점" in h and "결정적 계산 — 동일 입력이면 항상 동일 결과" in h


def test_rule_card_without_events():
    h = rule_card_html([], VALUES)
    assert "이상 없음" in h and "0건 감지" in h


def test_ai_head_badges():
    assert "✓ 검증 통과" in ai_head_html([])
    assert "⚠ 문제 있음: 원인표 밖 원인" in ai_head_html([{"type": "cause", "detail": "x"}])
    none_head = ai_head_html(None)
    assert "spc-tag-pass" not in none_head and "spc-tag-fail" not in none_head
    assert "AI 생성" in none_head and "판정은 규칙 기준" in none_head


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


def test_run_line_shows_llm_ids_as_plain_text():
    # 반복 결과 줄: LLM이 준 사건·원인 id는 마크다운 링크·HTML로 해석되지 않고 글자 그대로 보인다
    items = [{"event_id": "E1", "cause_id": "[눌러](http://evil.example)"}, {"event_id": "<b>E2</b>", "cause_id": "SP-1"}]
    h = run_line_html(2, "원인표 밖 원인", items)
    assert "2회차" in h and "원인표 밖 원인" in h and "E1:[눌러](http://evil.example)" in h
    assert "&lt;b&gt;E2&lt;/b&gt;:SP-1" in h and "<b>E2" not in h and "<a " not in h
    assert run_line_html(1, "호출 오류", None).endswith("호출 오류</div>")

