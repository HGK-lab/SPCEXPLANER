# OpenAI 호출을 한 곳에 모은다. JSON 모드로 부르고 원문·소요 시간·토큰 수를 돌려준다.
import os
import time
from dataclasses import dataclass

from . import config


@dataclass
class LLMReply:
    text: str | None  # 모델 원문. 호출 실패면 None
    error: str | None  # 호출 오류(네트워크·권한·모델 없음 등). 성공이면 None
    latency_s: float
    usage: dict | None


def get_api_key() -> str | None:
    """로컬은 .env, 배포는 환경변수(앱이 Streamlit Secrets에서 옮겨 넣음)에서 읽는다."""
    try:
        from dotenv import load_dotenv

        load_dotenv(config.ROOT / ".env")  # 이미 있는 환경변수는 덮어쓰지 않는다
    except ImportError:
        pass
    return os.environ.get("OPENAI_API_KEY") or None


_client = None


def _get_client():
    """OpenAI 클라이언트를 한 번만 만든다. 네트워크·429·5xx 재시도는 SDK가 한다."""
    global _client
    if _client is None:
        from openai import OpenAI

        _client = OpenAI(api_key=get_api_key(), max_retries=config.API_MAX_RETRIES, timeout=config.API_TIMEOUT_S)
    return _client


def call_json(model: dict, system: str, user: str) -> LLMReply:
    """model은 config의 모델 설정. temperature가 None이면 요청에 넣지 않는다(모델 기본값)."""
    kwargs = {
        "model": model["name"],
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "response_format": {"type": "json_object"},
    }
    if model.get("temperature") is not None:
        kwargs["temperature"] = model["temperature"]
    t0 = time.perf_counter()
    try:
        r = _get_client().chat.completions.create(**kwargs)
    except Exception as e:  # SDK 재시도 후에도 실패 → 예외 대신 기록으로 돌려준다
        return LLMReply(None, f"{type(e).__name__}: {e}", time.perf_counter() - t0, None)
    usage = None
    if r.usage is not None:
        usage = {"prompt_tokens": r.usage.prompt_tokens, "completion_tokens": r.usage.completion_tokens}
    return LLMReply(r.choices[0].message.content, None, time.perf_counter() - t0, usage)
