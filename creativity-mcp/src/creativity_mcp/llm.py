"""Async OpenRouter client for LLM calls."""

import asyncio
import json
import os

import httpx

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

FLASH_MODEL = "openai/gpt-5.4"
SONNET_MODEL = "openai/gpt-5.4"

_client: httpx.AsyncClient | None = None

_NON_RETRYABLE = (401, 403)


def _get_api_key() -> str:
    key = os.environ.get("OPENROUTER_API_KEY", "")
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY not set")
    return key


async def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(timeout=120.0)
    return _client


async def close_client() -> None:
    """Shut down the shared httpx client. Call on server shutdown."""
    global _client
    if _client is not None and not _client.is_closed:
        await _client.aclose()
    _client = None


async def acall(model: str, prompt: str, temperature: float = 1.0) -> str:
    """Single async OpenRouter call with 1 retry."""
    api_key = _get_api_key()
    client = await _get_client()
    last_exc: Exception | None = None
    for attempt in range(2):
        try:
            response = await client.post(
                OPENROUTER_URL,
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": model,
                    "temperature": temperature,
                    "reasoning": {"effort": "high"},
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in _NON_RETRYABLE:
                raise
            last_exc = exc
        except httpx.TransportError as exc:
            last_exc = exc
        else:
            return response.json()["choices"][0]["message"]["content"]
        if attempt == 0:
            await asyncio.sleep(2)
    raise last_exc  # type: ignore[misc]  # loop guarantees last_exc is set if we reach here


async def acall_batch(
    model: str, prompts: list[str], temperature: float = 1.0
) -> list[str]:
    """Concurrent batch of acall. Raises if ALL fail."""
    results = await asyncio.gather(
        *[acall(model, p, temperature) for p in prompts],
        return_exceptions=True,
    )
    successes = [r for r in results if not isinstance(r, BaseException)]
    if not successes:
        raise RuntimeError(f"All {len(prompts)} calls failed")
    return successes


def extract_json(text: str) -> dict | list:
    """Extract JSON from text, handling markdown code blocks."""
    text = text.strip()
    if text.startswith("```"):
        first_newline = text.index("\n")
        text = text[first_newline + 1:]
        if text.endswith("```"):
            text = text[:-3]
    return json.loads(text)
