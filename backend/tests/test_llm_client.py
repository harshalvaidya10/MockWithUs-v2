from __future__ import annotations

import asyncio
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
) -> SimpleNamespace:
    return SimpleNamespace(
        llm_provider=provider,
        llm_model=model,
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
        self.calls.append({"url": url, "headers": headers, "json": json})
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
