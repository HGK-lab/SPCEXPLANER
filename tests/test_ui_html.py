# 화면 공통 조각: 머리말·섹션 제목·01 문제·06 한계 문구, 카드 CSS, 패턴 기호·규칙 번호, 이스케이프
import re

import pytest

from spc_explainer import config
from spc_explainer.glossary import GLOSSARY
from spc_explainer.ui_html import (CSS, PATTERN_COLORS, PROBLEM_HTML, RULE_ID, SYMBOL, esc, guide_html, hero_html,
                                   limits_html, section_html, span_text, term)


def text(h: str) -> str:
    """태그를 뺀 화면 글자 (툴팁 span이 끼어도 문장으로 비교하려고)."""
    return re.sub(r"<[^>]+>", "", h)


METRICS = {"generated_at": "2026-09-25T23:48:41",
           "dataset": {"n_series": 20, "injected": {"spike": 7, "trend": 7, "shift": 7}}}


def test_hero_states_principle_flow_limits_and_assumption():
    h = hero_html(100.0, 103.0, 97.0, "nm")
    assert "판정은 규칙이 하고 설명은 AI가 합니다" in h
    assert "① 규칙 판정" in h and "② AI 설명" in h and "③ 검증" in h
    assert "CL 100.0" in text(h) and "UCL 103.0" in text(h) and "LCL 97.0" in text(h)
    assert f'data-tip="{esc(GLOSSARY["UCL"])}"' in h and f'data-tip="{esc(GLOSSARY["중심선"])}"' in h
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


def test_glossary_covers_required_terms():
    assert {"중심선", "UCL", "LCL", "σ", "급변", "추세", "치우침", "오탐"} <= set(GLOSSARY)
    assert f"{config.TREND_POINTS}점" in GLOSSARY["추세"] and f"{config.SHIFT_POINTS}점" in GLOSSARY["치우침"]
    assert all(v and "\n" not in v for v in GLOSSARY.values())  # 한 줄 설명


def test_term_is_focusable_and_escaped():
    h = term("UCL")
    assert h.startswith('<span class="spc-term" tabindex="0"') and ">UCL</span>" in h
    assert term("CL", "중심선").endswith(">CL</span>") and esc(GLOSSARY["중심선"]) in term("CL", "중심선")
    assert ".spc-term:hover::after, .spc-term:focus::after" in CSS  # 모바일은 탭 → 포커스로 뜬다
    with pytest.raises(KeyError):
        term("없는 용어")


def test_guide_has_three_steps_in_order():
    steps = ["시리즈 고르기", "판정 보기", "설명·검증 보기"]
    h = guide_html(5, 15)
    assert "30초 가이드" in h and h.count("<li>") == 3 and "정상 5개와 이상을 심은 15개" in h
    assert [h.index(s) for s in steps] == sorted(h.index(s) for s in steps)
    assert "정상 2개와 이상을 심은 7개" in guide_html(2, 7)  # 숫자는 받은 값 그대로 (데이터에서 센 값)
    assert ".st-key-guide_card" in CSS
