# 스토리형 앱이 예외 없이 그려지는지 (Streamlit AppTest, 네트워크 없음)
from pathlib import Path

from streamlit.testing.v1 import AppTest

from spc_explainer import config, llm_client

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
    for name in ("SERIES_PATH", "EXPLANATIONS_PATH", "METRICS_PATH", "REPORT_PATH"):
        monkeypatch.setattr(config, name, tmp_path / f"none_{name}")
    at = run_app()
    assert not at.exception
    at.selectbox[0].set_value(5).run()  # 급변을 심은 시리즈 → 규칙 사건은 있음
    assert not at.exception
    assert any("저장된 설명이 없습니다" in m.value for m in at.info)


def test_live_button_disabled_without_key(monkeypatch):
    monkeypatch.setattr(llm_client, "get_api_key", lambda: None)
    at = run_app()
    at.selectbox[0].set_value(5).run()
    assert not at.exception
    assert at.button[0].proto.disabled


def test_live_button_click_shows_reply_without_error(monkeypatch):
    # 클릭이 전체 재실행으로 들어와도 예외 없이 실시간 결과가 카드에 뜬다 (가짜 키·가짜 LLM, 네트워크 없음)
    monkeypatch.setattr(llm_client, "get_api_key", lambda: "test-key")
    monkeypatch.setattr(llm_client, "call_json",
                        lambda model, system, user: llm_client.LLMReply(None, "가짜 호출 오류", 0.1, None))
    at = run_app()
    at.selectbox[0].set_value(5).run()
    at.button[0].click().run()
    assert not at.exception
    assert any("가짜 호출 오류" in m.value for m in at.error)
