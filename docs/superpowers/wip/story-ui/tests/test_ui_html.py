# 화면 공통 조각: 머리말·섹션 제목·01 문제·06 한계 문구, 카드 CSS, 패턴 기호·규칙 번호, 이스케이프
from spc_explainer.ui_html import (CSS, PATTERN_COLORS, PROBLEM_HTML, RULE_ID, SYMBOL, esc, hero_html, limits_html,
                                   section_html, span_text)

METRICS = {"generated_at": "2026-09-25T23:48:41",
           "dataset": {"n_series": 20, "injected": {"spike": 7, "trend": 7, "shift": 7}}}


def test_hero_states_principle_flow_limits_and_assumption():
    h = hero_html(100.0, 103.0, 97.0, "nm")
    assert "판정은 규칙이 하고 설명은 AI가 합니다" in h
    assert "① 규칙 판정" in h and "② AI 설명" in h and "③ 검증" in h
    assert "CL 100.0" in h and "UCL 103.0" in h and "LCL 97.0" in h
    assert "이미 안정화된 공정을 감시하는 상황을 가정" in h


def test_section_and_problem():
    s = section_html("02 규칙 판정", "제목", "<b>설명</b>")
    assert "02 규칙 판정" in s and "<h2>제목</h2>" in s and "&lt;b&gt;" in s
    assert "01 문제 상황" in PROBLEM_HTML and "경험" in PROBLEM_HTML


def test_limits_read_numbers_from_metrics():
    h = limits_html(METRICS)
    assert "06 한계" in h and "가상 데이터" in h and "교과서 수준" in h
    assert "가상 시리즈 20개 · 심은 이상 21건" in h and "2026-09-25T23:48:41" in h
    assert "검증 결과 파일이 아직 없습니다" in limits_html(None)


def test_css_targets_keyed_cards_and_mobile():
    for key in ("chart_card", "rule_card", "ai_card", "ai_foot", "notes_card", "counts_card", "bars_card", "secom_card"):
        assert f".st-key-{key}" in CSS
    assert '[class*="st-key-kpi_"]' in CSS and "@media (max-width: 640px)" in CSS
    assert CSS.startswith("<style>") and CSS.rstrip().endswith("</style>")


def test_pattern_vocabulary():
    assert RULE_ID == {"spike": "R1", "shift": "R2", "trend": "R3"}  # Nelson 규칙 번호
    assert SYMBOL == {"spike": "◆", "trend": "▲", "shift": "■"}
    assert set(PATTERN_COLORS) == {"spike", "trend", "shift"}


def test_span_and_escape():
    assert span_text(14, 14) == "#14" and span_text(45, 52) == "#45–52"
    assert esc('<b>&"') == "&lt;b&gt;&amp;&quot;"
