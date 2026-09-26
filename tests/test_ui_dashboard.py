# 04 검증 가공: 숫자를 지표 파일에서만 읽는지, 모델별 반복 평균·최소~최대, 자동 집계와 수동 분석의 구분
from spc_explainer.matching import summarize
from spc_explainer.patterns import Event
from spc_explainer.ui_dashboard import (NOTES_HEAD_HTML, cases_html, detection_bars_html, detection_groups,
                                        error_counts_html, explain_error_cases, fact_lines, fmt_num, fmt_pct,
                                        kpi_model_html, kpi_rule_html, kpi_summary, subtitle_text)

T = [[Event("spike", 5, 5, "up"), Event("trend", 20, 27, "up")], [Event("shift", 40, 49, "down")], []]
RULES = summarize(T, T)  # 규칙: 3/3
RUN_A = summarize(T, [[Event("spike", 5, 5)], [], [Event("spike", 60, 60)]])  # 1/3, 오탐 1
RUN_B = summarize(T, [[Event("spike", 5, 5), Event("trend", 21, 22)], [], []])  # 2/3
METRICS = {
    "generated_at": "2026-09-25T23:48:41",
    "dataset": {"seed": 7, "n_series": 3, "n_normal": 1, "n_points": 100, "injected": {"spike": 1, "trend": 1, "shift": 1}},
    "rules": RULES,
    "detect": [{"model": "gpt-4.1-mini", "temperature": 0, "repeats": 2, "prompt_version": "detect-v1",
                "runs": [dict(RUN_A, format_violations=0, call_errors=0), dict(RUN_B, format_violations=1, call_errors=0)]}],
    "explain": {"model": "gpt-4.1-mini", "temperature": 0, "repeats": 3, "prompt_version": "explain-v1",
                "series_called": 2, "outputs": 6, "passed": 5, "issue_outputs": {"format": 0, "cause": 1, "mismatch": 0},
                "call_errors": 0, "repeat_changed_series": 1},
    "secom": None,
}


def test_formatting():
    assert fmt_pct(1.0) == "100%" and fmt_pct(0.6333) == "63.3%" and fmt_pct(None) == "-"
    assert fmt_num(3.0) == "3" and fmt_num(1.5) == "1.5"


def test_detection_groups_use_metrics_numbers():
    groups = detection_groups(METRICS)
    assert [g["key"] for g in groups] == ["spike", "trend", "shift", "all"]
    total = groups[-1]
    assert total["injected"] == 3 and total["rule"] == {"rate": 1.0, "detected": 3}
    m = total["models"][0]
    assert m["name"] == "gpt-4.1-mini" and m["repeats"] == 2 and m["mean_detected"] == 1.5
    assert abs(m["mean"] - 0.5) < 1e-9 and abs(m["min"] - 1 / 3) < 1e-9 and abs(m["max"] - 2 / 3) < 1e-9


def test_bars_show_rule_and_each_model_with_range():
    h = detection_bars_html(detection_groups(METRICS))
    assert "규칙 판정" in h and "gpt-4.1-mini" in h
    assert "50% (33.3%~66.7%)" in h and "1.5/3" in h and "3/3" in h and "spc-range" in h
    assert "/20" not in h and "/60" not in h  # 시안 값은 쓰지 않는다


def test_kpi_cards_show_tier_and_real_model_name():
    k = kpi_summary(METRICS)
    m = k["models"][0]
    assert m["missed_total"] == 3 and m["false_total"] == 1 and m["false_mean"] == 0.5 and m["format_violations"] == 1
    h = kpi_model_html(m, k["rule"]["rate"])
    assert "AI · 소형" in h and "gpt-4.1-mini" in h and "50%" in h and "−50.0%p" in h
    assert "100%" in kpi_rule_html(k["rule"]) and "매번 같은 결과" in kpi_rule_html(k["rule"])


def test_error_counts_are_automatic_and_labeled():
    h = error_counts_html(kpi_summary(METRICS))
    assert "자동 집계" in h and "원인표 밖 원인" in h and "놓친 심은 이상" in h
    assert "같은 기준으로 규칙 엔진은 0건" in h
    assert "수동 분석" in NOTES_HEAD_HTML and "자동 집계가 아닙니다" in NOTES_HEAD_HTML


def test_subtitle_and_facts_from_metrics():
    assert "가상 시리즈 3개 × 100점" in subtitle_text(METRICS) and "2026-09-25T23:48:41" in subtitle_text(METRICS)
    assert "아직 없습니다" in subtitle_text(None)
    lines = fact_lines(METRICS)
    assert lines[0] == "규칙 판정: 심은 이상 3개 중 3개 탐지."
    assert "gpt-4.1-mini" in lines[1] and "치우침" in lines[1]


def test_error_cases_come_from_saved_explanations():
    explanations = {"series": {"7": {
        "input": {"events": [{"event_id": "E1", "pattern": "급변", "start": 5, "end": 5}]},
        "runs": [{"run": 0, "error": None, "text": "{}", "issues": []},
                 {"run": 1, "error": None, "text": "<b>틀림</b>", "issues": [{"type": "cause", "detail": "'XX-9'는 원인표에 없음"}]}],
    }}}
    cases = explain_error_cases(explanations)
    assert len(cases) == 1 and cases[0]["run"] == 2 and cases[0]["types"] == "원인표 밖 원인"
    assert "◆ 급변 #5" in cases[0]["input"]
    h = cases_html(cases, METRICS["explain"])
    assert "&lt;b&gt;" in h and "문제가 나온 설명 출력 1개 / 전체 6개" in h
    assert "문제가 나온 설명 출력이 없습니다" in cases_html([], METRICS["explain"])


def test_false_alarm_term_has_tooltip_in_kpi_and_counts():
    k = kpi_summary(METRICS)
    for h in (kpi_rule_html(k["rule"]), kpi_model_html(k["models"][0], k["rule"]["rate"]), error_counts_html(k)):
        assert ">오탐</span>" in h and 'data-tip="' in h
    assert ">급변</span>" in detection_bars_html(detection_groups(METRICS))

