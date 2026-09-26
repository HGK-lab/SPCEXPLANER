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


def test_stale_saved_explanation_shows_warning(monkeypatch, tmp_path):
    # 규칙·설정을 바꾸고 실험을 다시 안 돌린 경우: 저장된 설명의 입력이 지금 판정과 달라도 화면은 그대로, 경고만 뜬다
    saved = json.loads(config.EXPLANATIONS_PATH.read_text(encoding="utf-8"))
    saved["series"]["5"]["input"]["events"][0]["start"] += 1
    stale = tmp_path / "explanations.json"
    stale.write_text(json.dumps(saved, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(config, "EXPLANATIONS_PATH", stale)
    at = run_app()
    at.selectbox[0].set_value(5).run()
    assert not at.exception
    assert any("입력이 현재 규칙 판정과 다릅니다" in m.value for m in at.warning)


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
