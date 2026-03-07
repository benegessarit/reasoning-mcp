"""Async OpenRouter client for LLM calls."""

import asyncio
import json
import os

import httpx

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")

FLASH_MODEL = "google/gemini-2.0-flash-001"
SONNET_MODEL = "anthropic/claude-sonnet-4-20250514"


async def acall(model: str, prompt: str, temperature: float = 1.0) -> str:
    """Single async OpenRouter call with 1 retry."""
    last_exc = None
    for attempt in range(2):
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    OPENROUTER_URL,
                    headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}"},
                    json={
                        "model": model,
                        "temperature": temperature,
                        "messages": [{"role": "user", "content": prompt}],
                    },
                )
                response.raise_for_status()
                return response.json()["choices"][0]["message"]["content"]
        except Exception as exc:
            last_exc = exc
            if attempt == 0:
                await asyncio.sleep(2)
    raise last_exc


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
        lines = text.split("\n")
        text = "\n".join(lines[1:-1])
    return json.loads(text)
