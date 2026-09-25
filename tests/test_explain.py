# 설명 입력 구성과 출력 검증기: 형식 위반·원인표 밖 원인·판정 불일치를 각각 잡아내는지
import json

from spc_explainer.causes import CAUSES, rows_for
from spc_explainer.explain import build_input, build_messages, signature, validate
from spc_explainer.patterns import Event

VALUES = [104.2 if i == 30 else 99.0 if 50 <= i <= 59 else 100.0 for i in range(100)]
EVENTS = [Event("spike", 30, 30, "up"), Event("shift", 50, 59, "down")]
INP = build_input(VALUES, EVENTS)

GOOD = {
    "summary": "30번 급변과 50~59번 아래 치우침이 있습니다.",
    "events": [
        {"event_id": "E1", "pattern": "급변", "rule": "관리한계 밖 1점",
         "checks": [{"cause_id": "SP-1", "reason": "재측정이 가장 빠름"}]},
        {"event_id": "E2", "pattern": "치우침", "rule": "10점 연속 중심선 아래",
         "checks": [{"cause_id": "SH-1", "reason": "PM 직후인지 확인"}, {"cause_id": "SH-2", "reason": "로트 확인"}]},
    ],
    "priority": ["E2", "E1"],
}


def variant(change) -> dict:
    """GOOD을 깊은 복사한 뒤 change(obj)로 한 곳만 바꾼다."""
    obj = json.loads(json.dumps(GOOD, ensure_ascii=False))
    change(obj)
    return obj


def issue_types(obj) -> list[str]:
    _, issues = validate(json.dumps(obj, ensure_ascii=False), INP)
    return sorted({i["type"] for i in issues})


def test_input_has_rule_events_and_only_relevant_causes():
    assert set(INP) == {"process", "events", "cause_table"}  # 원시 시계열은 넣지 않는다
    assert [e["event_id"] for e in INP["events"]] == ["E1", "E2"]
    assert INP["events"][0]["pattern"] == "급변" and INP["events"][0]["values"] == [104.2]
    assert INP["events"][1]["direction"] == "아래" and INP["events"][1]["mean"] == 99.0
    assert INP["events"][1]["rule"] == "10점 연속 중심선 아래 (50~59번, 평균 99.00nm)"
    assert {c["cause_id"][:2] for c in INP["cause_table"]} == {"SP", "SH"}  # 추세 원인은 주지 않음


def test_cause_table_rows():
    assert len(CAUSES) == 15
    assert set(rows_for({"trend"})) == {f"TR-{i}" for i in range(1, 6)}


def test_messages_mention_json_and_events():
    system, user = build_messages(INP)
    assert "JSON" in system
    assert user.startswith("다음 판정 결과를 설명해 줘.\n") and '"E1"' in user


def test_good_output_passes():
    assert issue_types(GOOD) == []


def test_broken_json_is_format_violation():
    for bad in ['{"summary": "끊김', None, "[]"]:
        _, issues = validate(bad, INP)
        assert [i["type"] for i in issues] == ["format"], bad


def test_missing_key_or_bad_values_are_format_violations():
    assert issue_types(variant(lambda o: o.pop("summary"))) == ["format"]
    assert issue_types(variant(lambda o: o["events"][0].update(checks=[]))) == ["format"]
    assert issue_types(variant(lambda o: o["events"][0].update(pattern="스파이크"))) == ["format"]


def test_cause_outside_table_or_from_other_pattern():
    assert issue_types(variant(lambda o: o["events"][0]["checks"][0].update(cause_id="XX-9"))) == ["cause"]
    assert issue_types(variant(lambda o: o["events"][0]["checks"][0].update(cause_id="TR-1"))) == ["cause"]


def test_verdict_mismatch_cases():
    assert issue_types(variant(lambda o: o["events"][1].update(pattern="추세"))) == ["mismatch"]
    assert issue_types(variant(lambda o: o["events"].pop())) == ["mismatch"]  # E2 누락
    assert issue_types(variant(lambda o: o["events"].append(dict(o["events"][0], event_id="E3")))) == ["mismatch"]
    assert issue_types(variant(lambda o: o.update(priority=["E1"]))) == ["mismatch"]


def test_parseable_but_wrong_types_do_not_raise():
    weird_outputs = [
        '{"events": {"E1": 1}}',
        '{"events": [{"event_id": "E1", "checks": "SP-1"}]}',
        '{"summary": 1, "events": [1, null], "priority": "E1"}',
        '{"events": [{"event_id": "E1", "checks": [1, {"cause_id": ["SP-1"], "reason": "x"}]}]}',
        '{"events": 5, "priority": [1, 2]}',
    ]
    for weird in weird_outputs:
        data, issues = validate(weird, INP)
        assert "format" in {i["type"] for i in issues}, weird
        signature(data)  # 예외가 나면 안 된다


def test_signature_ignores_reason_wording():
    other = variant(lambda o: o["events"][0]["checks"][0].update(reason="다른 문장"))
    assert signature(GOOD) == signature(other)
    assert signature(variant(lambda o: o.update(priority=["E1", "E2"]))) != signature(GOOD)
    assert signature(None) is None
