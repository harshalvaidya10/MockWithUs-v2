from __future__ import annotations

import asyncio
import logging
import random
from typing import Any, TypedDict

import httpx

from app.config import get_settings


logger = logging.getLogger(__name__)
settings = get_settings()

MAX_429_RETRIES = 3
RETRY_BACKOFF_SCHEDULE_SECONDS: tuple[float, ...] = (1.0, 2.0, 4.0)
DEFAULT_429_JITTER_SECONDS = 0.5
DEFAULT_TIMEOUT_SECONDS = 30.0


class LlmProviderConfig(TypedDict):
    provider: str
    base_url: str
    model: str
    api_key: str | None
    requires_api_key: bool


def retry_delay_for_attempt(retry_attempt: int, *, jitter_seconds: float = 0.0) -> float:
    """Return delay in seconds for retry number 1..N (capped at final schedule entry)."""
    index = max(0, retry_attempt - 1)
    delay = RETRY_BACKOFF_SCHEDULE_SECONDS[-1]
    if index < len(RETRY_BACKOFF_SCHEDULE_SECONDS):
        delay = RETRY_BACKOFF_SCHEDULE_SECONDS[index]
    if jitter_seconds > 0:
        delay += random.uniform(0.0, jitter_seconds)
    return delay


def retry_after_delay_seconds(response: httpx.Response) -> float | None:
    """Parse HTTP Retry-After header (delta-seconds form only)."""
    raw_value = (response.headers.get("Retry-After") or "").strip()
    if not raw_value:
        return None

    try:
        parsed = float(raw_value)
    except ValueError:
        return None

    if parsed <= 0:
        return None
    return parsed


def _resolve_provider_config(
    *,
    provider_override: str | None = None,
    model_override: str | None = None,
) -> LlmProviderConfig:
    provider_source = provider_override if provider_override is not None else settings.llm_provider
    model_source = model_override if model_override is not None else settings.llm_model

    provider = (provider_source or "").strip().lower()
    model = (model_source or "").strip()

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


def _resolve_fallback_provider_config(primary_config: LlmProviderConfig) -> LlmProviderConfig | None:
    fallback_provider = (getattr(settings, "llm_fallback_provider", None) or "").strip().lower()
    fallback_model = (getattr(settings, "llm_fallback_model", None) or "").strip()
    if not fallback_provider or not fallback_model:
        return None

    if (
        fallback_provider == primary_config["provider"]
        and fallback_model == primary_config["model"]
    ):
        return None

    try:
        fallback_config = _resolve_provider_config(
            provider_override=fallback_provider,
            model_override=fallback_model,
        )
    except RuntimeError:
        logger.warning(
            "Configured LLM fallback provider/model is invalid (provider=%s, model=%s). Ignoring fallback.",
            fallback_provider,
            fallback_model,
        )
        return None

    if fallback_config["requires_api_key"] and not fallback_config["api_key"]:
        logger.warning(
            "Configured fallback provider is missing API key (provider=%s, model=%s). Ignoring fallback.",
            fallback_config["provider"],
            fallback_config["model"],
        )
        return None
    return fallback_config


def _configured_retry_jitter_seconds() -> float:
    configured = getattr(settings, "llm_retry_jitter_seconds", DEFAULT_429_JITTER_SECONDS)
    try:
        return max(0.0, float(configured))
    except (TypeError, ValueError):
        return DEFAULT_429_JITTER_SECONDS


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
    response_format: dict[str, Any] | None = None,
) -> str:
    """Call configured provider via OpenAI-compatible chat completions API."""
    primary_config = _resolve_provider_config()
    if primary_config["requires_api_key"] and not primary_config["api_key"]:
        raise RuntimeError(f"{primary_config['provider']} API key is not configured.")
    fallback_config = _resolve_fallback_provider_config(primary_config)

    timeout = httpx.Timeout(timeout_seconds, connect=min(10.0, timeout_seconds))
    retry_jitter_seconds = _configured_retry_jitter_seconds()

    async def _call_provider(config: LlmProviderConfig) -> str:
        payload: dict[str, Any] = {
            "model": config["model"],
            "messages": messages,
            "temperature": temperature,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if response_format is not None:
            payload["response_format"] = response_format

        headers = {"Content-Type": "application/json"}
        if config["api_key"]:
            headers["Authorization"] = f"Bearer {config['api_key']}"

        request_url = f"{config['base_url'].rstrip('/')}/chat/completions"

        retry_count = 0
        response_format_fallback_used = False
        while True:
            response = await client.post(request_url, headers=headers, json=payload)
            if response.status_code == 400 and "response_format" in payload and not response_format_fallback_used:
                logger.warning(
                    "LLM provider rejected response_format (provider=%s). Retrying once without it.",
                    config["provider"],
                )
                payload.pop("response_format", None)
                response_format_fallback_used = True
                continue

            if response.status_code == 429 and retry_count < MAX_429_RETRIES:
                retry_count += 1
                wait_seconds = retry_delay_for_attempt(
                    retry_count,
                    jitter_seconds=retry_jitter_seconds,
                )
                retry_after_seconds = retry_after_delay_seconds(response)
                if retry_after_seconds is not None:
                    wait_seconds = max(wait_seconds, retry_after_seconds)
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

    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            return await _call_provider(primary_config)
        except httpx.HTTPStatusError as exc:
            is_429 = exc.response is not None and exc.response.status_code == 429
            if fallback_config is None or not is_429:
                raise

            logger.warning(
                "Primary LLM provider exhausted 429 retries (provider=%s, model=%s). "
                "Trying fallback provider=%s model=%s.",
                primary_config["provider"],
                primary_config["model"],
                fallback_config["provider"],
                fallback_config["model"],
            )
            try:
                return await _call_provider(fallback_config)
            except httpx.HTTPStatusError:
                logger.warning(
                    "Fallback LLM provider also failed (provider=%s, model=%s).",
                    fallback_config["provider"],
                    fallback_config["model"],
                )
                raise
