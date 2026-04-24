from __future__ import annotations

import asyncio
import copy
from types import SimpleNamespace
from typing import Any

import httpx
import pytest

from app.services import llm_client


def _make_settings(
    *,
    provider: str = "groq",
    model: str = "qwen/qwen3-32b",
    groq_api_key: str | None = "gsk-test",
    openrouter_api_key: str | None = "sk-or-test",
    fallback_provider: str | None = None,
    fallback_model: str | None = None,
    retry_jitter_seconds: float = 0.0,
) -> SimpleNamespace:
    return SimpleNamespace(
        llm_provider=provider,
        llm_model=model,
        llm_fallback_provider=fallback_provider,
        llm_fallback_model=fallback_model,
        llm_retry_jitter_seconds=retry_jitter_seconds,
        groq_api_key=groq_api_key,
        groq_base_url="https://api.groq.com/openai/v1",
        openrouter_api_key=openrouter_api_key,
        openrouter_base_url="https://openrouter.ai/api/v1",
        ollama_base_url="http://localhost:11434/v1",
    )


class _FakeResponse:
    def __init__(
        self,
        status_code: int,
        *,
        payload: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status_code = status_code
        self._payload = payload or {}
        self.headers = headers or {}

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            request = httpx.Request("POST", "https://test.local/chat/completions")
            response = httpx.Response(self.status_code, request=request, json=self._payload, headers=self.headers)
            raise httpx.HTTPStatusError(
                f"HTTP {self.status_code}",
                request=request,
                response=response,
            )

    def json(self) -> dict[str, Any]:
        return self._payload


class _FakeAsyncClient:
    def __init__(self, responses: list[_FakeResponse]) -> None:
        self._responses = responses
        self.calls: list[dict[str, Any]] = []

    async def __aenter__(self) -> _FakeAsyncClient:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    async def post(self, url: str, *, headers: dict[str, str], json: dict[str, Any]) -> _FakeResponse:
        self.calls.append({"url": url, "headers": copy.deepcopy(headers), "json": copy.deepcopy(json)})
        index = len(self.calls) - 1
        if index >= len(self._responses):
            index = len(self._responses) - 1
        return self._responses[index]


class _AsyncClientFactory:
    def __init__(self, responses: list[_FakeResponse]) -> None:
        self._responses = responses
        self.instances: list[_FakeAsyncClient] = []

    def __call__(self, *args, **kwargs) -> _FakeAsyncClient:
        client = _FakeAsyncClient(self._responses)
        self.instances.append(client)
        return client


def test_resolve_provider_config_for_groq(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(llm_client, "settings", _make_settings(provider="groq"))
    resolved = llm_client._resolve_provider_config()

    assert resolved["provider"] == "groq"
    assert resolved["base_url"] == "https://api.groq.com/openai/v1"
    assert resolved["model"] == "qwen/qwen3-32b"
    assert resolved["requires_api_key"] is True


def test_resolve_provider_config_for_openrouter(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(llm_client, "settings", _make_settings(provider="openrouter"))
    resolved = llm_client._resolve_provider_config()

    assert resolved["provider"] == "openrouter"
    assert resolved["base_url"] == "https://openrouter.ai/api/v1"
    assert resolved["requires_api_key"] is True


def test_resolve_provider_config_for_ollama(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(llm_client, "settings", _make_settings(provider="ollama"))
    resolved = llm_client._resolve_provider_config()

    assert resolved["provider"] == "ollama"
    assert resolved["base_url"] == "http://localhost:11434/v1"
    assert resolved["api_key"] is None
    assert resolved["requires_api_key"] is False


def test_call_llm_retries_on_429_and_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(llm_client, "settings", _make_settings(provider="groq"))

    sleep_calls: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleep_calls.append(seconds)

    monkeypatch.setattr(llm_client.asyncio, "sleep", fake_sleep)

    factory = _AsyncClientFactory(
        [
            _FakeResponse(429),
            _FakeResponse(429),
            _FakeResponse(
                200,
                payload={
                    "choices": [
                        {
                            "message": {
                                "content": '[{"question_text":"Q","category":"technical","rationale":"R"}]'
                            }
                        }
                    ]
                },
            ),
        ]
    )
    monkeypatch.setattr(llm_client.httpx, "AsyncClient", factory)

    response_text = asyncio.run(
        llm_client.call_llm(
            messages=[{"role": "user", "content": "test"}],
            temperature=0.7,
        )
    )

    assert response_text.startswith("[")
    assert sleep_calls == [1.0, 2.0]
    assert len(factory.instances) == 1
    assert len(factory.instances[0].calls) == 3


def test_call_llm_raises_after_429_retries_exhausted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(llm_client, "settings", _make_settings(provider="groq"))

    sleep_calls: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleep_calls.append(seconds)

    monkeypatch.setattr(llm_client.asyncio, "sleep", fake_sleep)

    factory = _AsyncClientFactory([_FakeResponse(429)])
    monkeypatch.setattr(llm_client.httpx, "AsyncClient", factory)

    with pytest.raises(httpx.HTTPStatusError):
        asyncio.run(
            llm_client.call_llm(
                messages=[{"role": "user", "content": "test"}],
                temperature=0.7,
            )
        )

    # Retries occur 3 times with delays 1s, 2s, 4s, then the 4th 429 raises.
    assert sleep_calls == [1.0, 2.0, 4.0]
    assert len(factory.instances) == 1
    assert len(factory.instances[0].calls) == 4


def test_call_llm_requires_api_key_for_groq(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(llm_client, "settings", _make_settings(provider="groq", groq_api_key=None))

    with pytest.raises(RuntimeError, match="groq API key is not configured"):
        asyncio.run(
            llm_client.call_llm(
                messages=[{"role": "user", "content": "test"}],
                temperature=0.7,
            )
        )


def test_retry_after_delay_seconds_parses_numeric() -> None:
    request = httpx.Request("POST", "https://test.local/chat/completions")
    response = httpx.Response(429, request=request, headers={"Retry-After": "3.5"})
    assert llm_client.retry_after_delay_seconds(response) == pytest.approx(3.5)


def test_call_llm_respects_retry_after_header(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(llm_client, "settings", _make_settings(provider="groq"))

    sleep_calls: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleep_calls.append(seconds)

    monkeypatch.setattr(llm_client.asyncio, "sleep", fake_sleep)

    factory = _AsyncClientFactory(
        [
            _FakeResponse(429, headers={"Retry-After": "5"}),
            _FakeResponse(
                200,
                payload={"choices": [{"message": {"content": '{"ok": true}'}}]},
            ),
        ]
    )
    monkeypatch.setattr(llm_client.httpx, "AsyncClient", factory)

    response_text = asyncio.run(
        llm_client.call_llm(
            messages=[{"role": "user", "content": "test"}],
            temperature=0.2,
        )
    )

    assert response_text == '{"ok": true}'
    assert sleep_calls == [5.0]


def test_call_llm_includes_response_format_in_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(llm_client, "settings", _make_settings(provider="groq"))

    factory = _AsyncClientFactory(
        [
            _FakeResponse(
                200,
                payload={"choices": [{"message": {"content": '{"value": 1}'}}]},
            ),
        ]
    )
    monkeypatch.setattr(llm_client.httpx, "AsyncClient", factory)

    asyncio.run(
        llm_client.call_llm(
            messages=[{"role": "user", "content": "test"}],
            temperature=0.1,
            response_format={"type": "json_object"},
        )
    )

    assert len(factory.instances) == 1
    assert len(factory.instances[0].calls) == 1
    payload = factory.instances[0].calls[0]["json"]
    assert payload["response_format"] == {"type": "json_object"}


def test_call_llm_retries_without_response_format_on_400(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(llm_client, "settings", _make_settings(provider="groq"))

    factory = _AsyncClientFactory(
        [
            _FakeResponse(400),
            _FakeResponse(
                200,
                payload={"choices": [{"message": {"content": '{"value": 2}'}}]},
            ),
        ]
    )
    monkeypatch.setattr(llm_client.httpx, "AsyncClient", factory)

    response_text = asyncio.run(
        llm_client.call_llm(
            messages=[{"role": "user", "content": "test"}],
            temperature=0.1,
            response_format={"type": "json_object"},
        )
    )

    assert response_text == '{"value": 2}'
    assert len(factory.instances) == 1
    assert len(factory.instances[0].calls) == 2
    first_payload = factory.instances[0].calls[0]["json"]
    second_payload = factory.instances[0].calls[1]["json"]
    assert first_payload["response_format"] == {"type": "json_object"}
    assert "response_format" not in second_payload


def test_call_llm_adds_jitter_to_retry_delay(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        llm_client,
        "settings",
        _make_settings(provider="groq", retry_jitter_seconds=0.5),
    )

    sleep_calls: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleep_calls.append(seconds)

    monkeypatch.setattr(llm_client.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(llm_client.random, "uniform", lambda _a, _b: 0.25)

    factory = _AsyncClientFactory(
        [
            _FakeResponse(429),
            _FakeResponse(
                200,
                payload={"choices": [{"message": {"content": '{"ok": true}'}}]},
            ),
        ]
    )
    monkeypatch.setattr(llm_client.httpx, "AsyncClient", factory)

    response_text = asyncio.run(
        llm_client.call_llm(
            messages=[{"role": "user", "content": "test"}],
            temperature=0.2,
        )
    )

    assert response_text == '{"ok": true}'
    assert sleep_calls == [1.25]


def test_call_llm_uses_fallback_provider_after_primary_429_exhaustion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        llm_client,
        "settings",
        _make_settings(
            provider="groq",
            model="qwen/qwen3-32b",
            fallback_provider="openrouter",
            fallback_model="anthropic/claude-3.5-sonnet",
            retry_jitter_seconds=0.0,
        ),
    )

    sleep_calls: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleep_calls.append(seconds)

    monkeypatch.setattr(llm_client.asyncio, "sleep", fake_sleep)

    factory = _AsyncClientFactory(
        [
            _FakeResponse(429),
            _FakeResponse(429),
            _FakeResponse(429),
            _FakeResponse(429),
            _FakeResponse(
                200,
                payload={"choices": [{"message": {"content": '{"from":"fallback"}'}}]},
            ),
        ]
    )
    monkeypatch.setattr(llm_client.httpx, "AsyncClient", factory)

    response_text = asyncio.run(
        llm_client.call_llm(
            messages=[{"role": "user", "content": "test"}],
            temperature=0.2,
        )
    )

    assert response_text == '{"from":"fallback"}'
    assert sleep_calls == [1.0, 2.0, 4.0]
    assert len(factory.instances) == 1
    assert len(factory.instances[0].calls) == 5
    primary_call_model = factory.instances[0].calls[0]["json"]["model"]
    fallback_call_model = factory.instances[0].calls[-1]["json"]["model"]
    assert primary_call_model == "qwen/qwen3-32b"
    assert fallback_call_model == "anthropic/claude-3.5-sonnet"


def test_call_llm_sets_hidden_reasoning_for_groq_qwen3(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(llm_client, "settings", _make_settings(provider="groq", model="qwen/qwen3-32b"))

    factory = _AsyncClientFactory(
        [
            _FakeResponse(
                200,
                payload={"choices": [{"message": {"content": '{"ok": true}'}}]},
            ),
        ]
    )
    monkeypatch.setattr(llm_client.httpx, "AsyncClient", factory)

    response_text = asyncio.run(
        llm_client.call_llm(
            messages=[{"role": "user", "content": "test"}],
            temperature=0.2,
        )
    )

    assert response_text == '{"ok": true}'
    assert len(factory.instances) == 1
    payload = factory.instances[0].calls[0]["json"]
    assert payload["reasoning_format"] == "hidden"
    assert payload["reasoning_effort"] == "none"
