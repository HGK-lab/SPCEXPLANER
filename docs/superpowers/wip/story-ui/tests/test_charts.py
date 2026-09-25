# 관리도 스타일: 한계선(점선+오른쪽 라벨)·중심선(실선), 패턴별 마커, 규칙 구간 음영+라벨, 정답은 테두리만
from spc_explainer.charts import chart_footer_html, chart_header_html, control_chart
from spc_explainer.patterns import Event

VALUES = [100.0 + (0.3 if i % 2 else -0.3) for i in range(100)]
VALUES[14] = 103.6
EVENTS = [Event("spike", 14, 14, "up"), Event("trend", 24, 29, "up")]


def test_rule_bands_labels_and_limit_lines():
    fig = control_chart(VALUES, EVENTS, 100, 103, 97, show_legend=False)
    texts = [a.text for a in fig.layout.annotations]
    assert "<b>◆ 급변 #14</b>" in texts and "<b>▲ 추세 #24–29</b>" in texts
    assert {"UCL 103", "CL 100", "LCL 97"} <= set(texts)
    assert sorted(s.line.dash for s in fig.layout.shapes if s.type == "line") == ["dash", "dash", "solid"]
    bands = [s for s in fig.layout.shapes if s.type == "rect"]
    assert len(bands) == 2 and all(b.fillcolor.startswith("rgba(") for b in bands)
    assert not fig.layout.showlegend


def test_pattern_markers_and_zero_based_x():
    fig = control_chart(VALUES, EVENTS, 100, 103, 97)
    symbols = {t.name: t.marker.symbol for t in fig.data if t.name != "측정값"}
    assert symbols == {"급변": "diamond", "추세": "triangle-up"}
    assert list(fig.data[0].x) == list(range(100))
    assert list(fig.data[2].x) == list(range(24, 30))  # 추세 구간의 모든 점


def test_truth_is_outline_only():
    fig = control_chart(VALUES, EVENTS, 100, 103, 97, truth=[Event("trend", 24, 31, "up")])
    outlines = [s for s in fig.layout.shapes if s.type == "rect" and s.line.dash == "dot"]
    assert len(outlines) == 1 and outlines[0].fillcolor == "rgba(0,0,0,0)"


def test_many_events_hide_band_labels_and_secom_arguments_still_work():
    many = [Event("spike", i, i, "up") for i in range(0, 90, 9)]
    fig = control_chart(VALUES, many, 100, 103, 97, phase_boundary=50, fail_idx=[3], y_title="sensor_88")
    texts = [a.text for a in fig.layout.annotations]
    assert not any("급변 #" in t for t in texts) and "Phase I | Phase II" in texts
    assert "불량 라벨" in [t.name for t in fig.data] and fig.layout.showlegend


def test_header_reads_stats_from_values():
    h = chart_header_html([99.0, 101.0, 100.0], "관리도 · 증착 막 두께 (nm)", show_truth=True)
    assert "n=3" in h and "x̄=100.00" in h and "σ=1.00" in h
    assert "◆" in h and "▲" in h and "■" in h and "관리한계" in h and "정답" in h
    assert "정답" not in chart_header_html([100.0, 100.0], "t", show_truth=False)


def test_footer_mentions_rule_bands_and_zero_based_index():
    f = chart_footer_html()
    assert "세로 음영 = 규칙이 판정한 이상 구간" in f and "0부터" in f
    assert "점선 테두리" in chart_footer_html(show_truth=True)


def test_close_band_labels_are_staggered():
    # 시작점이 가까운 사건의 라벨은 두 줄로 엇갈린다 (겹침 방지), 먼 사건은 첫 줄
    evs = [Event("spike", 45, 45, "up"), Event("shift", 48, 59, "up"), Event("trend", 76, 81, "up")]
    fig = control_chart(VALUES, evs, 100, 103, 97, show_legend=False)
    shifts = {a.text: a.yshift for a in fig.layout.annotations if "#" in a.text}
    assert shifts == {"<b>◆ 급변 #45</b>": 0, "<b>■ 치우침 #48–59</b>": 16, "<b>▲ 추세 #76–81</b>": 0}
