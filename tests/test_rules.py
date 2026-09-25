# 규칙 엔진 래퍼: type 코드 매핑, 사건 묶기, 추세 정의(6점) 확인
from spc_explainer import config
from spc_explainer.generator import generate_dataset, truth_events
from spc_explainer.patterns import Event, overlaps
from spc_explainer.rules import _runs, describe, detect

# 중심선 위아래를 번갈아 오가는 평탄한 기본 시리즈 (그 자체로는 어떤 규칙에도 안 걸림)
BASE = [100.2, 99.8] * 30


def test_runs_groups_consecutive_indices():
    assert _runs([1, 2, 3, 7, 9, 10]) == [(1, 3), (7, 7), (9, 10)]
    assert _runs([]) == []


def test_flat_series_has_no_events():
    assert detect(BASE) == []


def test_spike_up_and_down():
    x = list(BASE)
    x[5], x[20] = 104.2, 96.1
    assert detect(x) == [Event("spike", 5, 5, "up"), Event("spike", 20, 20, "down")]


def test_trend_six_points_detected_five_not():
    x = list(BASE)
    x[10:16] = [99.0, 99.4, 99.8, 100.2, 100.6, 101.0]  # 6점 상승
    assert detect(x) == [Event("trend", 10, 15, "up")]
    y = list(BASE)
    y[10:15] = [99.0, 99.4, 99.8, 100.2, 100.6]  # 5점 상승 → 규칙 미달
    assert detect(y) == []


def test_trend_down_covers_whole_run():
    x = list(BASE)
    x[20:28] = [102.0 - 0.5 * i for i in range(8)]
    assert detect(x) == [Event("trend", 20, 27, "down")]


def test_shift_nine_points_below():
    x = list(BASE)
    x[40:50] = [99.0, 99.2] * 5  # 10점 중심선 아래 (39번도 99.8이라 런은 39~49)
    assert detect(x) == [Event("shift", 39, 49, "down")]


def test_rules_find_every_injected_anomaly():
    for seed in (config.SEED, 1, 2, 3):
        for s in generate_dataset(seed)["series"]:
            found = detect(s["values"])
            for t in truth_events(s):
                assert any(f.pattern == t.pattern and overlaps(f, t) for f in found), (seed, s["id"], t)


def test_describe_sentences():
    x = list(BASE)
    x[5] = 104.2
    assert describe(Event("spike", 5, 5, "up"), x) == "관리한계 밖 1점 (5번 104.20nm, UCL 103nm 초과)"
    x[20:26] = [99.0, 99.4, 99.8, 100.2, 100.6, 101.0]
    assert describe(Event("trend", 20, 25, "up"), x) == "6점 연속 상승 (20~25번, 99.00→101.00nm)"
    assert describe(Event("shift", 40, 49, "down"), [99.0] * 60) == "10점 연속 중심선 아래 (40~49번, 평균 99.00nm)"
