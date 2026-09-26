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
    assert at.button(key="live_button").proto.disabled


def test_live_button_click_shows_reply_without_error(monkeypatch):
    # 클릭이 전체 재실행으로 들어와도 예외 없이 실시간 결과가 카드에 뜬다 (가짜 키·가짜 LLM, 네트워크 없음)
    monkeypatch.setattr(llm_client, "get_api_key", lambda: "test-key")
    monkeypatch.setattr(llm_client, "call_json",
                        lambda model, system, user: llm_client.LLMReply(None, "가짜 호출 오류", 0.1, None))
    at = run_app()
    at.selectbox[0].set_value(5).run()
    at.button(key="live_button").click().run()
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


def test_repeat_runs_show_llm_ids_as_plain_text(monkeypatch, tmp_path):
    # 03의 "같은 입력 반복 결과": LLM이 준 id에 링크 서식이 있어도 마크다운으로 해석되지 않는다
    saved = json.loads(config.EXPLANATIONS_PATH.read_text(encoding="utf-8"))
    entry = saved["series"]["5"]
    bad = {"summary": "요약", "priority": ["E1"],
           "events": [{"event_id": "E1", "pattern": "급변", "rule": "r",
                       "checks": [{"cause_id": "[눌러](http://evil.example)", "reason": "이유"}]}]}
    entry["runs"][1]["text"] = json.dumps(bad, ensure_ascii=False)
    path = tmp_path / "explanations.json"
    path.write_text(json.dumps(saved, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(config, "EXPLANATIONS_PATH", path)
    at = run_app()
    at.selectbox[0].set_value(5).run()
    assert not at.exception
    assert not any("evil.example" in m.value for m in at.markdown)
    assert any("E1:[눌러](http://evil.example)" in e.proto.body for e in at.get("html"))



def download_keys(at) -> list[str]:
    """내려받기 버튼들의 키 (AppTest는 요소 id 끝에 키를 붙인다)."""
    return [e.proto.id.rsplit("-", 1)[-1] for e in at.get("download_button")]


def ai_ranked_labels(at, prefix: str) -> list[str]:
    return [c.label for c in at.checkbox if (c.key or "").startswith(prefix) and "AI 추천" in c.label]


def test_checklist_uses_ai_order_only_when_the_explanation_passes(monkeypatch, tmp_path):
    # 저장된 설명이 검증을 통과하면 AI 추천 순서가 붙고, 원인표 밖 원인이 섞여 통과하지 못하면 원인표 순서만
    at = run_app()
    at.selectbox[0].set_value(5).run()
    assert any("AI 추천 1순위" in label for label in ai_ranked_labels(at, "chk_s05_"))
    saved = json.loads(config.EXPLANATIONS_PATH.read_text(encoding="utf-8"))
    run0 = saved["series"]["5"]["runs"][0]
    data = json.loads(run0["text"])
    data["events"][0]["checks"][0]["cause_id"] = "XX-9"
    run0["text"] = json.dumps(data, ensure_ascii=False)
    path = tmp_path / "explanations.json"
    path.write_text(json.dumps(saved, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(config, "EXPLANATIONS_PATH", path)
    at = run_app()
    at.selectbox[0].set_value(5).run()
    assert not at.exception and ai_ranked_labels(at, "chk_s05_") == []
    assert any("원인표 순서로 보여줍니다" in e.proto.body for e in at.get("html"))


def test_checklist_and_handover_memo():
    # 03 아래 '지금 확인할 것': 사건의 원인표 항목이 체크박스로 나오고, 체크하면 인수인계 메모에 [x]로 남는다
    at = run_app()
    at.selectbox[0].set_value(5).run()
    assert not at.exception
    boxes = [c for c in at.checkbox if (c.key or "").startswith("chk_s05_")]
    assert len(boxes) == 5  # 시리즈 5는 급변 1건 → 원인표의 급변 원인 5개
    boxes[0].check().run()
    memo = next(c.value for c in at.code if c.value.startswith("# SPC 판정 인수인계"))
    assert "memo_s05" in download_keys(at)
    assert "- [x] " in memo and "시리즈 05" in memo and "## 지금 확인할 것 (원인표 기준)" in memo
    assert len(at.get("download_button")) >= 1


def pick_notes(at) -> list[str]:
    return [e.proto.body for e in at.get("html") if 'class="spc-pick' in e.proto.body]


def click_point(at, sid: int, x: int) -> None:
    """관리도에서 점 하나를 누른 것과 같은 선택 상태를 넣는다 (AppTest는 차트를 직접 누를 수 없다)."""
    at.session_state[f"chart_{sid:02d}"] = {"selection": {"points": [{"x": x}], "point_indices": [x],
                                                          "box": [], "lasso": []}}
    at.run()


def test_chart_click_picks_the_event_and_highlights_it():
    at = run_app()
    at.selectbox[0].set_value(11).run()  # 시리즈 11: 급변 #45, 치우침 #48–59, 추세 #76–81
    click_point(at, 11, 52)
    assert not at.exception
    assert at.selectbox(key="pick_11").value == 1
    assert any("E2 · ■ 치우침 #48–59 선택" in b and 'href="#spc-ai"' in b for b in pick_notes(at))
    assert any("spc-rule-row sel" in e.proto.body for e in at.get("html"))
    assert [x.proto.expanded for x in at.expander if "E2 ·" in x.label] == [True]
    # 드롭다운으로 바꾸면 차트 선택이 남아 있어도 덮어쓰지 않는다
    at.selectbox(key="pick_11").set_value(2).run()
    assert at.selectbox(key="pick_11").value == 2


def test_click_outside_events_says_so():
    at = run_app()
    at.selectbox[0].set_value(11).run()
    click_point(at, 11, 63)
    assert not at.exception
    assert at.selectbox(key="pick_11").value == -1  # "선택 안 함"
    assert any("#63 · 이 점은 판정된 사건에 속하지 않습니다." in b for b in pick_notes(at))


def guide_shown(at) -> bool:
    return any("30초 가이드" in e.proto.body for e in at.get("html"))


def test_guide_closes_and_stays_closed_in_the_session():
    at = run_app()
    assert guide_shown(at)
    series = json.loads(config.SERIES_PATH.read_text(encoding="utf-8"))["series"]
    n_normal = sum(1 for s in series if not s["anomalies"])
    assert any(f"정상 {n_normal}개와 이상을 심은 {len(series) - n_normal}개" in e.proto.body for e in at.get("html"))
    at.button(key="guide_close").click().run()
    assert not at.exception and not guide_shown(at)
    at.selectbox[0].set_value(11).run()  # 다른 곳을 눌러 다시 그려도 닫힌 채로
    assert not guide_shown(at)


def test_false_alarm_feedback_is_kept_in_the_session():
    at = run_app()
    at.selectbox[0].set_value(11).run()
    assert any("시연용: 실제 운영에서는 이 피드백으로 규칙·원인표를 개선한다" in e.proto.body for e in at.get("html"))
    at.button(key="fb_s11_E1").click().run()
    assert not at.exception
    assert [(e["series"], e["event_id"], e["span"]) for e in at.session_state["feedback"]] == [("시리즈 11", "E1", "#45")]
    assert at.button(key="fb_s11_E1").label == "오탐 표시 취소"
    assert len(at.dataframe) == 1 and "feedback_csv" in download_keys(at)
    at.button(key="fb_s11_E1").click().run()  # 다시 누르면 취소
    assert at.session_state["feedback"] == []
