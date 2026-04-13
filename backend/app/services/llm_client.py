from __future__ import annotations

import asyncio
import logging
from typing import Any, TypedDict

import httpx

from app.config import get_settings


logger = logging.getLogger(__name__)
settings = get_settings()

MAX_429_RETRIES = 3
RETRY_BACKOFF_SCHEDULE_SECONDS: tuple[float, ...] = (1.0, 2.0, 4.0)
DEFAULT_TIMEOUT_SECONDS = 30.0


class LlmProviderConfig(TypedDict):
    provider: str
    base_url: str
    model: str
    api_key: str | None
    requires_api_key: bool


def retry_delay_for_attempt(retry_attempt: int) -> float:
    """Return delay in seconds for retry number 1..N (capped at final schedule entry)."""
    index = max(0, retry_attempt - 1)
    if index < len(RETRY_BACKOFF_SCHEDULE_SECONDS):
        return RETRY_BACKOFF_SCHEDULE_SECONDS[index]
    return RETRY_BACKOFF_SCHEDULE_SECONDS[-1]


def _resolve_provider_config() -> LlmProviderConfig:
    provider = (settings.llm_provider or "").strip().lower()
    model = (settings.llm_model or "").strip()

    if not provider:
        raise RuntimeError("LLM_PROVIDER is not configured.")
    if not model:
        raise RuntimeError("LLM_MODEL is not configured.")

    if provider == "groq":
        return LlmProviderConfig(
            provider=provider,
            base_url=settings.groq_base_url,
            model=model,
            api_key=settings.groq_api_key,
            requires_api_key=True,
        )

    if provider == "openrouter":
        return LlmProviderConfig(
            provider=provider,
            base_url=settings.openrouter_base_url,
            model=model,
            api_key=settings.openrouter_api_key,
            requires_api_key=True,
        )

    if provider == "ollama":
        return LlmProviderConfig(
            provider=provider,
            base_url=settings.ollama_base_url,
            model=model,
            api_key=None,
            requires_api_key=False,
        )

    raise RuntimeError(f"Unsupported LLM provider: {provider}")


def _extract_message_content(payload: dict[str, Any]) -> str:
    try:
        message_content = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError("LLM response did not contain choices[0].message.content") from exc

    if isinstance(message_content, str):
        return message_content.strip()

    if isinstance(message_content, list):
        chunks: list[str] = []
        for item in message_content:
            if isinstance(item, dict) and "text" in item:
                chunks.append(str(item["text"]))
            elif isinstance(item, str):
                chunks.append(item)
        return "\n".join(chunks).strip()

    return str(message_content).strip()


async def call_llm(
    *,
    messages: list[dict[str, str]],
    temperature: float,
    max_tokens: int | None = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> str:
    """Call configured provider via OpenAI-compatible chat completions API."""
    config = _resolve_provider_config()
    if config["requires_api_key"] and not config["api_key"]:
        raise RuntimeError(f"{config['provider']} API key is not configured.")

    payload: dict[str, Any] = {
        "model": config["model"],
        "messages": messages,
        "temperature": temperature,
    }
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens

    headers = {"Content-Type": "application/json"}
    if config["api_key"]:
        headers["Authorization"] = f"Bearer {config['api_key']}"

    request_url = f"{config['base_url'].rstrip('/')}/chat/completions"
    timeout = httpx.Timeout(timeout_seconds, connect=min(10.0, timeout_seconds))

    async with httpx.AsyncClient(timeout=timeout) as client:
        retry_count = 0
        while True:
            response = await client.post(request_url, headers=headers, json=payload)
            if response.status_code == 429 and retry_count < MAX_429_RETRIES:
                retry_count += 1
                wait_seconds = retry_delay_for_attempt(retry_count)
                logger.warning(
                    "LLM provider returned 429 (provider=%s, retry %s/%s). Retrying in %.1fs.",
                    config["provider"],
                    retry_count,
                    MAX_429_RETRIES,
                    wait_seconds,
                )
                await asyncio.sleep(wait_seconds)
                continue

            response.raise_for_status()
            return _extract_message_content(response.json())
