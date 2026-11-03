"""Test lớp LLM bằng mock (không gọi mạng): cache, giới hạn tốc độ, retry 429, validate + retry 1 lần,
Ollama format JSON, đọc retryDelay của Gemini."""

from __future__ import annotations

import json

import pytest
from pydantic import BaseModel

from src.llm.client import (
    DiskCache,
    LLMClient,
    OllamaClient,
    RateLimiter,
    RateLimitError,
    StructuredOutputError,
    TransientError,
    _gemini_retry_delay,
)


class Out(BaseModel):
    ten: str
    so: int


class FakeClient(LLMClient):
    provider = "fake"

    def __init__(self, script, tmp_path, **kw):
        kw.setdefault("max_rpm", 0)
        super().__init__("fake-model", cache=DiskCache(tmp_path), sleep=self._sleep, **kw)
        self.script = list(script)
        self.sleeps: list[float] = []
        self.prompts: list[str] = []

    def _sleep(self, s):
        self.sleeps.append(s)

    def _call(self, prompt, system, json_schema, schema_model):
        self.prompts.append(prompt)
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def test_cache_hit(tmp_path):
    c = FakeClient(['{"ten": "a", "so": 1}'], tmp_path)
    assert c.generate_structured("p", Out) == Out(ten="a", so=1)
    assert c.generate_structured("p", Out) == Out(ten="a", so=1)     # lần 2: từ cache, không gọi
    assert c.stats["calls"] == 1 and c.stats["cache_hits"] == 1
    # khóa cache phụ thuộc model/provider/prompt
    k1 = DiskCache.key(provider="gemini", model="m1", prompt="p")
    assert k1 != DiskCache.key(provider="gemini", model="m2", prompt="p")
    assert k1 != DiskCache.key(provider="ollama", model="m1", prompt="p")


def test_retry_on_429_uses_server_delay_then_backoff(tmp_path):
    c = FakeClient([RateLimitError("429", retry_after=7), RateLimitError("429"), "ok"], tmp_path,
                   backoff_base_s=2)
    assert c.generate("p", use_cache=False) == "ok"
    assert 7 <= c.sleeps[0] < 7.6 and 4 <= c.sleeps[1] < 4.6      # retryDelay, rồi 2*2^1
    assert c.stats["retries"] == 2


def test_retry_gives_up(tmp_path):
    c = FakeClient([TransientError("503")] * 3, tmp_path, max_retries=2)
    with pytest.raises(TransientError):
        c.generate("p", use_cache=False)


def test_structured_retry_once_then_ok(tmp_path):
    c = FakeClient(['{"ten": "a"}', '```json\n{"ten": "a", "so": 2}\n```'], tmp_path)
    assert c.generate_structured("p", Out) == Out(ten="a", so=2)
    assert "KHÔNG hợp lệ" in c.prompts[1]


def test_structured_fails_after_one_retry(tmp_path):
    c = FakeClient(['{"x": 1}', '{"y": 2}'], tmp_path)
    with pytest.raises(StructuredOutputError):
        c.generate_structured("p", Out)


def test_rate_limiter_sliding_window():
    t = [0.0]
    slept = []

    def sleep(s):
        slept.append(s)
        t[0] += s
    rl = RateLimiter(2, clock=lambda: t[0], sleep=sleep)
    rl.acquire(); rl.acquire()
    assert slept == []
    rl.acquire()                                    # lần 3 trong cùng phút → phải chờ ~60s
    assert 59 < slept[0] <= 60.1


def test_gemini_retry_delay_parse():
    class E(Exception):
        details = {"error": {"details": [{"@type": "RetryInfo", "retryDelay": "23s"}]}}
    assert _gemini_retry_delay(E("RESOURCE_EXHAUSTED")) == 23.0
    assert _gemini_retry_delay(Exception("x")) is None


def test_ollama_json_format_and_validation(tmp_path, monkeypatch):
    sent = {}

    class R:
        status_code = 200

        def json(self):
            return {"message": {"content": json.dumps({"ten": "b", "so": 3})}}

    def fake_post(url, json, timeout):        # noqa: A002
        sent.update(url=url, body=json)
        return R()
    import httpx

    monkeypatch.setattr(httpx, "post", fake_post)
    c = OllamaClient("qwen2.5:7b", cache=DiskCache(tmp_path), max_rpm=0)
    assert c.generate_structured("p", Out, system="s") == Out(ten="b", so=3)
    assert sent["url"].endswith("/api/chat") and sent["body"]["format"] == "json"
    assert sent["body"]["messages"][0] == {"role": "system", "content": "s"}
    assert '"so"' in sent["body"]["messages"][1]["content"]          # schema đính kèm trong prompt


def test_ollama_429_maps_to_rate_limit(tmp_path, monkeypatch):
    import httpx

    class R:
        status_code = 429
        text = "busy"
    monkeypatch.setattr(httpx, "post", lambda *a, **k: R())
    c = OllamaClient("m", cache=DiskCache(tmp_path), max_rpm=0, max_retries=0)
    with pytest.raises(RateLimitError):
        c.generate("p", use_cache=False)


def test_factory_rejects_unknown_provider():
    from src.llm.client import LLMError, get_llm_client

    with pytest.raises(LLMError):
        get_llm_client("anthropic")
