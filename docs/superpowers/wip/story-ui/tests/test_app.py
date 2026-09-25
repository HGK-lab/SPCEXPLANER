# 스토리형 앱이 예외 없이 그려지는지 (Streamlit AppTest, 네트워크 없음)
import json
from pathlib import Path

from streamlit.testing.v1 import AppTest

from spc_explainer import config, llm_client
from spc_explainer.experiment import compute_metrics
from spc_explainer.generator import generate_dataset

APP = str(Path(__file__).resolve().parent.parent / "streamlit_app.py")


def run_app() -> AppTest:
    return AppTest.from_file(APP, default_timeout=60).run()


def test_app_renders_and_switches_series():
    at = run_app()
    assert not at.exception
    for sid in (0, 5, 14, 19):
        at.selectbox[0].set_value(sid).run()
        assert not at.exception, sid


def test_app_without_saved_files(monkeypatch, tmp_path):
    for name in ("SERIES_PATH", "EXPLANATIONS_PATH", "METRICS_PATH", "REPORT_PATH", "SECOM_PATH", "CASE_NOTES_PATH"):
        monkeypatch.setattr(config, name, tmp_path / f"none_{name}")
    at = run_app()
    assert not at.exception
    at.selectbox[0].set_value(5).run()  # 급변을 심은 시리즈 → 규칙 사건은 있음
    assert not at.exception
    infos = [m.value for m in at.info]
    assert any("저장된 설명이 없습니다" in v for v in infos)
    assert any("검증 결과가 아직 없습니다" in v for v in infos)
    assert any("SECOM 데이터가 없습니다" in v for v in infos)


def test_live_button_disabled_without_key(monkeypatch):
    monkeypatch.setattr(llm_client, "get_api_key", lambda: None)
    at = run_app()
    at.selectbox[0].set_value(5).run()
    assert not at.exception
    assert at.button[0].proto.disabled


def test_verification_renders_from_metrics_without_llm_results(monkeypatch, tmp_path):
    # LLM 결과가 없는 지표 파일로도 04 검증이 그려져야 한다 (숫자는 파일에서만 읽음)
    metrics_path = tmp_path / "metrics.json"
    metrics_path.write_text(json.dumps(compute_metrics(generate_dataset(), {}, {}), ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(config, "METRICS_PATH", metrics_path)
    monkeypatch.setattr(config, "EXPLANATIONS_PATH", tmp_path / "none.json")
    notes = tmp_path / "notes.md"
    notes.write_text("### 사례 1\n수동 해설 본문", encoding="utf-8")
    monkeypatch.setattr(config, "CASE_NOTES_PATH", notes)
    at = run_app()
    assert not at.exception
    assert any("수동 해설 본문" in m.value for m in at.markdown)
