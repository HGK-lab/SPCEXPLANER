# 지표 → 마크다운 리포트: 가정 문구, 섹션, 핵심 수치가 들어가는지
from spc_explainer.matching import summarize
from spc_explainer.patterns import Event
from spc_explainer.report import render, write

RULES = summarize([[], [Event("spike", 5, 5, "up")]], [[Event("trend", 20, 25, "up")], [Event("spike", 5, 5, "up")]])
METRICS = {
    "generated_at": "2026-09-25T21:00:00",
    "dataset": {"seed": 1, "n_series": 2, "n_normal": 1, "n_points": 100, "injected": {"spike": 1, "trend": 0, "shift": 0}},
    "rules": RULES,
    "detect": [{"model": "gpt-4.1-mini", "temperature": 0, "repeats": 2, "prompt_version": "detect-v1",
                "runs": [dict(RULES, format_violations=0, call_errors=0),
                         dict(RULES, rate=0.0, format_violations=1, call_errors=0)]},
               {"model": "gpt-6-sol", "temperature": None, "repeats": 1, "prompt_version": "detect-v1",
                "runs": [dict(RULES, format_violations=0, call_errors=2)]}],
    "explain": {"model": "gpt-4.1-mini", "temperature": 0, "repeats": 3, "prompt_version": "explain-v1",
                "series_called": 2, "outputs": 6, "passed": 5,
                "issue_outputs": {"format": 0, "cause": 1, "mismatch": 0},
                "call_errors": 0, "repeat_changed_series": 1},
    "secom": None,
}


def test_report_has_assumption_and_all_sections():
    md = render(METRICS)
    assert "이미 안정화된 공정을 감시하는 상황을 가정" in md
    for title in ("## 1. 실험 조건", "## 2. 규칙 판정", "## 3. LLM 단독 판정 비교", "## 4. LLM 설명 검증",
                  "## 5. 실데이터 확인", "## 6. 해석 시 주의"):
        assert title in md


def test_report_numbers():
    md = render(METRICS)
    assert "| 급변 | 1 / 1 | 100% |" in md
    assert "정상 시리즈: 1개 중 1개에서 경보" in md
    assert "| 규칙 엔진 | 1 | 100% | 1/1 | 0/0 | 0/0 | 1/1 | 1 | 0 | - | - |" in md
    assert "| gpt-4.1-mini (temperature 0) | 2 | 50% (0%~100%) |" in md
    assert "| gpt-6-sol (temperature 기본값) | 1 | 100% |" in md
    assert "| 원인표 밖 원인 | 1 |" in md
    assert "데이터가 없어 건너뜀" in md
    assert "gpt-6-sol은(는) temperature를 바꿀 수 없어" in md


def test_write_creates_file(tmp_path):
    path = tmp_path / "docs" / "report.md"
    write(METRICS, path)
    assert path.read_text(encoding="utf-8").startswith("# 검증 리포트")
