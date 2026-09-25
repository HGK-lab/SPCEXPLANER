# 구간 겹침 채점: 정탐·패턴 혼동·오탐 분류와 집계
from spc_explainer.matching import classify, summarize
from spc_explainer.patterns import Event

T = Event("trend", 10, 17, "up")
S = Event("shift", 40, 49, "down")


def test_classify_hit_confusion_false():
    found = [Event("trend", 16, 20), Event("spike", 45, 45), Event("spike", 80, 80)]
    detected, kinds = classify([T, S], found)
    assert detected == [True, False]  # 치우침은 같은 패턴으로 찾지 못함
    assert kinds == ["hit", "confusion", "false"]


def test_classify_no_overlap_is_miss_and_false():
    detected, kinds = classify([T], [Event("trend", 18, 25)])
    assert detected == [False] and kinds == ["false"]


def test_summarize_counts_normal_and_anomalous_separately():
    truths = [[], [], [T, S]]
    founds = [[Event("spike", 3, 3)], [], [Event("trend", 12, 15), Event("shift", 60, 70)]]
    m = summarize(truths, founds)
    assert m["injected"] == 2 and m["detected"] == 1 and m["rate"] == 0.5
    assert m["per_pattern"]["trend"] == {"injected": 1, "detected": 1}
    assert m["per_pattern"]["shift"] == {"injected": 1, "detected": 0}
    assert m["normal"] == {"series": 2, "alarmed_series": 1, "false_events": {"spike": 1, "trend": 0, "shift": 0}}
    assert m["anomalous"] == {"false_events": {"spike": 0, "trend": 0, "shift": 1}, "confusions": 0}
    assert m["false_list"] == [
        {"series": 0, "pattern": "spike", "start": 3, "end": 3, "direction": None},
        {"series": 2, "pattern": "shift", "start": 60, "end": 70, "direction": None},
    ]


def test_summarize_without_injections_has_no_rate():
    assert summarize([[]], [[]])["rate"] is None
