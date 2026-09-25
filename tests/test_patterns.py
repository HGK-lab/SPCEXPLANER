# 패턴 자료형과 정의 문장 확인
from spc_explainer.patterns import Event, definitions_text, overlaps


def test_overlap_needs_only_one_shared_point():
    assert overlaps(Event("trend", 10, 17), Event("trend", 17, 20))
    assert not overlaps(Event("trend", 10, 17), Event("trend", 18, 20))


def test_event_dict_roundtrip():
    ev = Event("shift", 40, 49, "down")
    assert Event.from_dict(ev.to_dict()) == ev
    assert Event.from_dict({"pattern": "spike", "start": 3, "end": 3}) == Event("spike", 3, 3)


def test_definitions_use_rule_numbers():
    text = definitions_text()
    assert "UCL(103)" in text and "LCL(97)" in text and "중심선(100)" in text
    assert "6개 이상" in text and "5회 이상" in text and "9개 이상" in text
