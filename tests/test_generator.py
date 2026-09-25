# 생성기가 규칙 정의를 만족하는 이상을 심는지, 시드가 재현되는지 확인
from spc_explainer import config
from spc_explainer.generator import generate_dataset, load_dataset, save_dataset, truth_events

SEEDS = (config.SEED, 1, 2, 3)  # 기본 시드 말고 다른 시드에서도 성립해야 한다


def test_same_seed_same_data():
    assert generate_dataset(1) == generate_dataset(1)
    assert generate_dataset(1) != generate_dataset(2)


def test_scenario_counts():
    ds = generate_dataset()
    assert len(ds["series"]) == 20
    assert all(len(s["values"]) == 100 for s in ds["series"])
    assert [s["anomalies"] for s in ds["series"][:5]] == [[]] * 5  # 정상 시리즈 5개
    kinds = [a["pattern"] for s in ds["series"] for a in s["anomalies"]]
    assert {p: kinds.count(p) for p in ("spike", "trend", "shift")} == {"spike": 7, "trend": 7, "shift": 7}


def test_injected_anomalies_satisfy_rule_definitions():
    for seed in SEEDS:
        for s in generate_dataset(seed)["series"]:
            x = s["values"]
            for ev in truth_events(s):
                seg = x[ev.start:ev.end + 1]
                up = ev.direction == "up"
                if ev.pattern == "spike":
                    assert len(seg) == 1
                    assert seg[0] > config.UCL if up else seg[0] < config.LCL
                elif ev.pattern == "trend":
                    diffs = [b - a for a, b in zip(seg, seg[1:])]
                    assert len(seg) == config.TREND_LEN
                    assert all(d > 0 for d in diffs) if up else all(d < 0 for d in diffs)
                    assert all(config.LCL < v < config.UCL for v in seg)
                else:
                    assert len(seg) == config.SHIFT_LEN
                    if up:
                        assert all(config.CENTER < v < config.UCL for v in seg)
                    else:
                        assert all(config.LCL < v < config.CENTER for v in seg)


def test_anomalies_skip_warmup_and_keep_gap():
    for seed in SEEDS:
        for s in generate_dataset(seed)["series"]:
            evs = sorted(truth_events(s), key=lambda e: e.start)
            assert all(e.start >= config.WARMUP for e in evs)
            assert all(b.start - a.end - 1 >= config.MIN_GAP for a, b in zip(evs, evs[1:]))


def test_values_have_two_decimals():
    for s in generate_dataset()["series"]:
        assert all(round(v, 2) == v for v in s["values"])


def test_save_and_load_roundtrip(tmp_path):
    ds = generate_dataset()
    path = tmp_path / "sub" / "series.json"
    save_dataset(ds, path)
    assert load_dataset(path) == ds
