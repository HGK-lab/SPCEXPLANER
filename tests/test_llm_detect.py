# 단독 판정 프롬프트와 출력 파서
from spc_explainer.llm_detect import build_messages, parse
from spc_explainer.patterns import Event


def test_messages_contain_definitions_and_indexed_values():
    system, user = build_messages([100.0, 104.25])
    assert "6개 이상" in system and "UCL 103" in system and "JSON" in system
    assert user.splitlines() == ["데이터 (번호: 값)", "0: 100.00", "1: 104.25"]


def test_parse_valid():
    text = '{"detections": [{"pattern": "추세", "start": 60, "end": 67}, {"pattern": "급변", "start": 3, "end": 3}]}'
    assert parse(text) == ([Event("trend", 60, 67), Event("spike", 3, 3)], [])
    assert parse('{"detections": []}') == ([], [])


def test_parse_format_violations_score_as_no_detection():
    bad_outputs = [
        '{"detections": [{"pattern": "추세", "start": 60}]}',  # end 누락
        '{"detections": [{"pattern": "추세", "start": 70, "end": 60}]}',  # start > end
        '{"detections": [{"pattern": "추세", "start": 95, "end": 100}]}',  # 번호 범위 밖
        '{"detections": [{"pattern": "trend", "start": 1, "end": 2}]}',  # 패턴 이름 틀림
        '{"result": []}',
        "not json",
        None,
    ]
    for bad in bad_outputs:
        events, issues = parse(bad)
        assert events == [] and [i["type"] for i in issues] == ["format"], bad


def test_parse_wrong_types_do_not_raise():
    for weird in ["[]", '{"detections": {"a": 1}}', '{"detections": [1]}',
                  '{"detections": [{"pattern": "추세", "start": 1.5, "end": 3}]}',
                  '{"detections": [{"pattern": "추세", "start": true, "end": 3}]}']:
        events, issues = parse(weird)
        assert events == [] and issues[0]["type"] == "format", weird
