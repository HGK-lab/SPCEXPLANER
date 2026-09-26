# SECOM 확인 로직: 센서 선정(라벨 미사용), Phase I 한계, Phase II 번호 보정, 겹침 관찰, 실험 지표 연결
import numpy as np
import pandas as pd

from spc_explainer import secom
from spc_explainer.experiment import Paths, run_all
from spc_explainer.patterns import Event
from spc_explainer.report import secom_section


def test_phase1_limits_use_moving_range():
    lim = secom.phase1_limits([10, 12, 10, 12])
    assert lim["center"] == 11
    assert abs(lim["sigma"] - 2 / 1.128) < 1e-9
    assert abs(lim["ucl"] - (11 + 3 * 2 / 1.128)) < 1e-9


def test_select_sensors_uses_only_distribution():
    rng = np.random.default_rng(0)
    X = pd.DataFrame({
        0: rng.normal(0, 1, 600),  # 후보
        1: rng.exponential(1, 600),  # 왜도 큼 → 제외
        2: np.r_[[np.nan], rng.normal(0, 1, 599)],  # 결측 → 제외
        3: rng.integers(0, 5, 600).astype(float),  # 고유값 적음 → 제외
        4: rng.normal(5, 2, 600),  # 후보
        5: rng.normal(0, 1, 600),  # 후보지만 k=2라 제외
    })
    assert secom.select_sensors(X, phase1_n=500, k=2) == [0, 4]


def test_monitor_shifts_indices_to_full_series():
    values = [0.0, 1.0] * 250 + [10.0] + [0.5] * 20
    lim, evs = secom.monitor(values, phase1_n=500)
    assert Event("spike", 500, 500, "up") in evs
    assert all(e.start >= 500 for e in evs)


def test_overlap_summary_counts():
    labels = [-1] * 10 + [1, -1, -1, 1, -1]
    evs = [Event("spike", 10, 10, "up"), Event("trend", 12, 14, "down")]
    s = secom.overlap_summary(evs, labels, phase1_n=10)
    assert s["events"] == 2 and s["events_with_fail"] == 2
    assert s["by_pattern"] == {"spike": 1, "trend": 1, "shift": 0}
    assert s["flagged_points"] == 4
    assert s["fail_rate_flagged"] == 0.5 and s["fail_rate_phase2"] == 0.4


def test_summarize_feeds_report_section():
    df = pd.DataFrame({"label": [-1] * 510 + [1] * 10, "sensor_7": [0.0, 1.0] * 250 + [10.0] + [0.5] * 19})
    text = "\n".join(secom_section(secom.summarize(df, phase1_n=500)))
    assert "| sensor_7 |" in text and "탐지율은 계산하지 않는다" in text


def test_run_all_adds_secom_summary_when_csv_exists(tmp_path):
    # 선정 센서 CSV가 있으면 LLM 없이 다시 만든 지표·리포트에 SECOM 요약이 들어간다
    paths = Paths.under(tmp_path)
    pd.DataFrame({
        "timestamp": pd.date_range("2008-07-19", periods=520, freq="h"),
        "label": [-1] * 510 + [1] * 10,
        "sensor_7": [0.0, 1.0] * 250 + [10.0] + [0.5] * 19,
    }).to_csv(paths.secom, index=False)
    m = run_all(None, paths)
    assert m["secom"]["n"] == 520 and m["secom"]["sensors"]["sensor_7"]["events"] >= 1
    assert "| sensor_7 |" in paths.report.read_text(encoding="utf-8")
