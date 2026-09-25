# 가짜 LLM으로 실험 전 과정을 네트워크 없이 돌려 본다
import json
import runpy
import sys

import pytest

from spc_explainer import config, explain, llm_client
from spc_explainer.experiment import Paths, run_all
from spc_explainer.llm_client import LLMReply


class FakeLLM:
    """설명은 규칙 입력을 그대로 따르는 모범 답을, 단독 판정은 4.1-mini엔 빈 결과·sol엔 깨진 출력을 준다."""

    def __init__(self):
        self.calls = 0

    def __call__(self, model, system, user):
        self.calls += 1
        if system == explain.SYSTEM:
            inp = json.loads(user.split("\n", 1)[1])
            events = []
            for e in inp["events"]:
                cid = next(c["cause_id"] for c in inp["cause_table"] if c["pattern"] == e["pattern"])
                events.append({"event_id": e["event_id"], "pattern": e["pattern"], "rule": e["rule"],
                               "checks": [{"cause_id": cid, "reason": "이유"}]})
            out = {"summary": "요약", "events": events, "priority": [e["event_id"] for e in inp["events"]]}
            return LLMReply(json.dumps(out, ensure_ascii=False), None, 0.01, None)
        if model["name"] == "gpt-6-sol":
            return LLMReply("깨진 출력", None, 0.01, None)
        return LLMReply('{"detections": []}', None, 0.01, None)


def failing_llm(model, system, user):
    return LLMReply(None, "APIConnectionError: down", 0.0, None)


def test_run_all_with_fake_llm(tmp_path):
    fake, paths = FakeLLM(), Paths.under(tmp_path)
    m = run_all(fake, paths)
    explained = m["explain"]["series_called"]
    enabled = [d for d in config.DETECT_MODELS if d["enabled"]]
    assert fake.calls == explained * config.EXPLAIN_MODEL["repeats"] + sum(d["repeats"] * 20 for d in enabled)
    assert m["explain"]["passed"] == m["explain"]["outputs"] == explained * config.EXPLAIN_MODEL["repeats"]
    assert m["rules"]["detected"] == m["rules"]["injected"] == 21  # 규칙은 심은 이상을 모두 찾는다
    by_model = {d["model"]: d for d in m["detect"]}
    assert all(r["rate"] == 0 for r in by_model["gpt-4.1-mini"]["runs"])  # 빈 결과 → 탐지 0
    assert all(r["format_violations"] == 20 for r in by_model["gpt-6-sol"]["runs"])
    for p in (paths.series, paths.explanations, paths.detections, paths.metrics, paths.report, paths.ai_errors):
        assert p.exists(), p
    log = paths.ai_errors.read_text(encoding="utf-8")
    assert log.startswith("# LLM 오류 기록") and "JSON 형식 위반" in log and "놓침" in log


def test_cache_avoids_repeat_calls_and_log_is_not_duplicated(tmp_path):
    paths = Paths.under(tmp_path)
    run_all(FakeLLM(), paths)
    log = paths.ai_errors.read_text(encoding="utf-8")
    fake = FakeLLM()
    run_all(fake, paths)
    assert fake.calls == 0  # 전부 캐시에서 꺼냄
    assert paths.ai_errors.read_text(encoding="utf-8") == log  # 새 출력이 없으니 섹션도 안 늘어남


def test_force_calls_again_and_appends_new_section(tmp_path):
    paths = Paths.under(tmp_path)
    run_all(FakeLLM(), paths)
    fake = FakeLLM()
    run_all(fake, paths, force=True)
    assert fake.calls > 0
    assert paths.ai_errors.read_text(encoding="utf-8").count("## 실행 ") == 2  # 이전 기록은 지우지 않음


def test_call_errors_are_counted_and_retried_next_time(tmp_path):
    paths = Paths.under(tmp_path)
    m = run_all(failing_llm, paths)
    assert m["explain"]["call_errors"] == m["explain"]["outputs"] > 0
    assert all(r["call_errors"] == 20 for d in m["detect"] for r in d["runs"])
    assert not paths.ai_errors.exists()  # 호출 오류는 LLM 출력 오류가 아니다
    fake = FakeLLM()
    run_all(fake, paths)
    assert fake.calls > 0  # 실패한 호출은 다음 실행에서 다시 부른다


def test_no_llm_rebuilds_report_from_saved_results(tmp_path):
    paths = Paths.under(tmp_path)
    run_all(FakeLLM(), paths)
    paths.report.unlink()
    m = run_all(None, paths)
    assert paths.report.exists() and m["explain"]["outputs"] > 0


def test_script_exits_with_message_without_key(monkeypatch):
    monkeypatch.setattr(llm_client, "get_api_key", lambda: None)
    monkeypatch.setattr(sys, "argv", ["run_experiment.py"])
    with pytest.raises(SystemExit) as exc:
        runpy.run_path(str(config.ROOT / "scripts" / "run_experiment.py"), run_name="__main__")
    assert "OPENAI_API_KEY" in str(exc.value)
