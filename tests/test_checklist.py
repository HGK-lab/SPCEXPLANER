# 체크리스트: 항목은 원인표에서만, AI는 검증을 통과했을 때 순서만. 인수인계 메모 글자
from spc_explainer.causes import CAUSES
from spc_explainer.checklist import ai_order, build, handover_md, item_label
from spc_explainer.explain import build_input
from spc_explainer.patterns import Event
from spc_explainer.ui_steps import check_head_html

VALUES = [104.2 if i == 14 else 99.0 if 40 <= i <= 49 else 100.0 for i in range(100)]
EVENTS = [Event("spike", 14, 14, "up"), Event("shift", 40, 49, "down")]
INP = build_input(VALUES, EVENTS)
DATA = {
    "summary": "요약\n두 줄",
    "priority": ["E2", "E1"],
    "events": [
        {"event_id": "E1", "pattern": "급변", "rule": "r",
         "checks": [{"cause_id": "XX-9", "reason": "지어낸 원인"}, {"cause_id": "TR-1", "reason": "다른 패턴"},
                    {"cause_id": "SP-3", "reason": "유량\n로그"}]},
        {"event_id": "E2", "pattern": "치우침", "rule": "r", "checks": [{"cause_id": "SH-2", "reason": "로트"}]},
    ],
}


def test_ai_order_keeps_only_table_ids_of_the_same_pattern():
    order = ai_order(DATA, INP)
    assert order == {"E1": [("SP-3", "유량 로그")], "E2": [("SH-2", "로트")]}
    assert ai_order(None, INP) == {} and ai_order({"events": "x"}, INP) == {}
    assert ai_order({"events": [1, {"event_id": "E1", "checks": "x"}]}, INP) == {"E1": []}


def test_items_come_only_from_cause_table():
    cards = build(EVENTS, VALUES, order=ai_order(DATA, INP))
    for card, pattern in zip(cards, ("spike", "shift")):
        ids = [it["cause_id"] for it in card["items"]]
        assert sorted(ids) == sorted(c for c, r in CAUSES.items() if r["pattern"] == pattern)  # 원인표 행 전부, 그 외는 없음
    first = cards[0]["items"][0]
    assert first["cause_id"] == "SP-3" and first["ai_rank"] == 1 and first["ai_reason"] == "유량 로그"
    assert all(it["ai_rank"] is None for it in cards[0]["items"][1:])
    assert cards[0]["title"] == "E1 · ◆ 급변 #14" and "관리한계 밖 1점" in cards[0]["rule"]


def test_without_ai_the_table_order_is_kept():
    cards = build(EVENTS, VALUES)
    assert [it["cause_id"] for it in cards[1]["items"]] == ["SH-1", "SH-2", "SH-3", "SH-4", "SH-5"]
    assert item_label(cards[1]["items"][0]) == "PM 이력과 치우침 시작 시점 비교 — 부품 교체·PM 후 조건 변화"


def test_limits_change_the_rule_text():
    cards = build([Event("spike", 3, 3, "up")], [10.0, 10.0, 10.0, 20.0], limits={"ucl": 15.0, "lcl": 5.0})
    assert "UCL 15nm 초과" in cards[0]["rule"]


def test_check_head_says_when_ai_order_is_not_used():
    # AI 순서는 검증을 통과한 설명일 때만 쓴다. 설명이 있는데 못 쓰면 그 이유를 적는다
    assert "원인표 기준" in check_head_html(False, False)
    assert "원인표 순서로 보여줍니다" in check_head_html(True, False)
    assert "원인표 순서로 보여줍니다" not in check_head_html(True, True)
    assert "원인표 순서로 보여줍니다" not in check_head_html(False, False)


def test_handover_memo():
    cards = build(EVENTS, VALUES, order=ai_order(DATA, INP))
    memo = handover_md("시리즈 99", "2026-09-26 10:00", cards, {("E1", "SP-3")},
                       {"model": "gpt-4.1-mini", "status": "검증 통과", "summary": DATA["summary"]})
    assert memo.startswith("# SPC 판정 인수인계 — 시리즈 99")
    assert "판정은 규칙 엔진(확정), 설명은 AI(참고용)" in memo and "요약: 요약 두 줄" in memo
    assert "- [x] 해당 런의 MFC 유량 로그 확인 — 가스 유량 순간 이상 (MFC 스파이크) · AI 추천 1순위 (AI: 유량 로그)" in memo
    assert "- [ ] 같은 웨이퍼 재측정" in memo and "### E2 · ■ 치우침 #40–49" in memo
    assert "## AI 설명 (참고용)\n\n- 없음" in handover_md("t", "n", cards, set(), None)
