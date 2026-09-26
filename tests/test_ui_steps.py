# 규칙 판정 카드·AI 설명 카드: 규칙 번호, 구간 표기, 검증 배지, 점검 우선순위 펼치기, HTML 이스케이프
import json

from spc_explainer.explain import build_input
from spc_explainer.patterns import Event
from spc_explainer.ui_steps import (ai_body_html, ai_head_html, event_index_at, event_option, issues_html,
                                    pick_note_html, priority_items, rule_card_html, run_line_html, selected_x,
                                    upload_limits_html)

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


def test_rule_card_pattern_names_have_tooltips():
    h = rule_card_html(EVENTS, VALUES)
    assert 'class="spc-term"' in h and ">급변</span>" in h and ">치우침</span>" in h


def test_selected_x_reads_the_clicked_point():
    assert selected_x({"selection": {"points": [{"x": 52.0, "y": 101.2}]}}) == 52
    assert selected_x({"selection": {"points": []}}) is None
    assert selected_x(None) is None and selected_x({}) is None and selected_x({"selection": {"points": "x"}}) is None
    assert selected_x({"selection": {"points": [{"x": True}, {"x": 7}]}}) == 7


def test_event_lookup_option_and_note():
    assert event_index_at(EVENTS, 14) == 0 and event_index_at(EVENTS, 45) == 1 and event_index_at(EVENTS, 13) is None
    assert event_option(EVENTS, 1) == "E2 · ■ 치우침 #40–49" and event_option(EVENTS, -1) == "선택 안 함"
    assert pick_note_html(EVENTS, None, 63) == '<div class="spc-pick out">#63 · 이 점은 판정된 사건에 속하지 않습니다.</div>'
    note = pick_note_html(EVENTS, 1, None)
    assert "E2 · ■ 치우침 #40–49 선택" in note and 'href="#spc-ai"' in note
    assert pick_note_html(EVENTS, None, None) == ""


def test_selected_event_is_highlighted_in_rule_card_and_ai_body():
    h = rule_card_html(EVENTS, VALUES, selected=1)
    assert h.count("spc-rule-row sel") == 1 and h.index("spc-rule-row sel") > h.index("#14")
    body = ai_body_html(DATA, INP, selected="E2")
    assert body.count("spc-prio-row sel") == 2  # E2의 점검 항목 2개
    assert "spc-prio-row sel" not in ai_body_html(DATA, INP)


def test_rule_card_uses_given_limits():
    h = rule_card_html([Event("spike", 3, 3, "up")], [10.0, 10.0, 10.0, 20.0], limits={"ucl": 15.0, "lcl": 5.0})
    assert "UCL 15nm 초과" in h


def test_upload_limits_line():
    est = {"mode": "estimated", "phase1_n": 50, "limits": {"center": 0.5, "ucl": 3.16, "lcl": -2.16, "sigma": 0.8865}}
    assert "앞 50점으로 추정한 한계 · CL 0.5 · UCL 3.16 · LCL -2.16 · σ 0.8865" in upload_limits_html(est)
    assert "50번 점부터 (Phase II)" in upload_limits_html(est)
    fixed = {"mode": "fixed", "phase1_n": None, "limits": {"center": 100, "ucl": 103, "lcl": 97}}
    assert "직접 입력한 한계 · CL 100 · UCL 103 · LCL 97 · 모든 점을 판정" in upload_limits_html(fixed)
