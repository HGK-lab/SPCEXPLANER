# 네트워크 없이 호출부의 요청 구성과 오류 처리만 확인
from types import SimpleNamespace

from spc_explainer import llm_client


class FakeCompletions:
    def __init__(self, fail: bool = False):
        self.kwargs, self.fail = None, fail

    def create(self, **kwargs):
        self.kwargs = kwargs
        if self.fail:
            raise RuntimeError("boom")
        message = SimpleNamespace(content='{"ok": true}')
        usage = SimpleNamespace(prompt_tokens=10, completion_tokens=3)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)], usage=usage)


def use_fake(monkeypatch, fail: bool = False) -> FakeCompletions:
    completions = FakeCompletions(fail)
    fake_client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    monkeypatch.setattr(llm_client, "_get_client", lambda: fake_client)
    return completions


def test_json_mode_and_temperature_zero(monkeypatch):
    completions = use_fake(monkeypatch)
    r = llm_client.call_json({"name": "gpt-4.1-mini", "temperature": 0}, "sys", "user")
    assert r.text == '{"ok": true}' and r.error is None
    assert r.usage == {"prompt_tokens": 10, "completion_tokens": 3}
    assert completions.kwargs["model"] == "gpt-4.1-mini"
    assert completions.kwargs["response_format"] == {"type": "json_object"}
    assert completions.kwargs["temperature"] == 0
    assert completions.kwargs["messages"] == [{"role": "system", "content": "sys"}, {"role": "user", "content": "user"}]


def test_temperature_none_is_not_sent(monkeypatch):
    completions = use_fake(monkeypatch)
    llm_client.call_json({"name": "gpt-6-sol", "temperature": None}, "s", "u")
    assert "temperature" not in completions.kwargs


def test_call_error_is_returned_not_raised(monkeypatch):
    use_fake(monkeypatch, fail=True)
    r = llm_client.call_json({"name": "x", "temperature": None}, "s", "u")
    assert r.text is None and r.error == "RuntimeError: boom" and r.usage is None
