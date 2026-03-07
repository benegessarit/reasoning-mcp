"""Tests for creativity_mcp.llm async OpenRouter client."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest


@pytest.mark.anyio
async def test_acall_success():
    """acall returns content string on successful response."""
    from creativity_mcp.llm import acall

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "hello world"}}]
    }

    with patch("creativity_mcp.llm.httpx.AsyncClient") as MockClient:
        client_instance = AsyncMock()
        client_instance.post.return_value = mock_response
        MockClient.return_value.__aenter__ = AsyncMock(return_value=client_instance)
        MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await acall("google/gemini-2.0-flash-001", "test prompt")
        assert result == "hello world"
        client_instance.post.assert_called_once()


@pytest.mark.anyio
async def test_acall_retry_on_failure():
    """acall retries once on failure, returns on second success."""
    from creativity_mcp.llm import acall

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "retried ok"}}]
    }

    with patch("creativity_mcp.llm.httpx.AsyncClient") as MockClient:
        client_instance = AsyncMock()
        client_instance.post.side_effect = [
            httpx.HTTPStatusError("500", request=MagicMock(), response=MagicMock()),
            mock_response,
        ]
        MockClient.return_value.__aenter__ = AsyncMock(return_value=client_instance)
        MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("creativity_mcp.llm.asyncio.sleep", new_callable=AsyncMock):
            result = await acall("google/gemini-2.0-flash-001", "test prompt")
            assert result == "retried ok"
            assert client_instance.post.call_count == 2


@pytest.mark.anyio
async def test_acall_raises_after_both_fail():
    """acall raises after both attempts fail."""
    from creativity_mcp.llm import acall

    with patch("creativity_mcp.llm.httpx.AsyncClient") as MockClient:
        client_instance = AsyncMock()
        client_instance.post.side_effect = httpx.HTTPStatusError(
            "500", request=MagicMock(), response=MagicMock()
        )
        MockClient.return_value.__aenter__ = AsyncMock(return_value=client_instance)
        MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("creativity_mcp.llm.asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(httpx.HTTPStatusError):
                await acall("google/gemini-2.0-flash-001", "test prompt")
            assert client_instance.post.call_count == 2


@pytest.mark.anyio
async def test_acall_batch_all_succeed():
    """acall_batch returns all results when all succeed."""
    from creativity_mcp.llm import acall_batch

    with patch("creativity_mcp.llm.acall", new_callable=AsyncMock) as mock_acall:
        mock_acall.side_effect = ["result1", "result2", "result3"]
        results = await acall_batch("model", ["p1", "p2", "p3"])
        assert results == ["result1", "result2", "result3"]


@pytest.mark.anyio
async def test_acall_batch_partial_failures():
    """acall_batch returns only successes, filters out exceptions."""
    from creativity_mcp.llm import acall_batch

    with patch("creativity_mcp.llm.acall", new_callable=AsyncMock) as mock_acall:
        mock_acall.side_effect = [
            "result1",
            RuntimeError("failed"),
            "result3",
        ]
        results = await acall_batch("model", ["p1", "p2", "p3"])
        assert results == ["result1", "result3"]


@pytest.mark.anyio
async def test_acall_batch_all_fail_raises():
    """acall_batch raises RuntimeError when all calls fail."""
    from creativity_mcp.llm import acall_batch

    with patch("creativity_mcp.llm.acall", new_callable=AsyncMock) as mock_acall:
        mock_acall.side_effect = RuntimeError("failed")
        with pytest.raises(RuntimeError, match="All .* calls failed"):
            await acall_batch("model", ["p1", "p2"])


def test_extract_json_plain():
    """extract_json parses plain JSON string."""
    from creativity_mcp.llm import extract_json

    result = extract_json('{"key": "value"}')
    assert result == {"key": "value"}


def test_extract_json_markdown_block():
    """extract_json handles ```json markdown fenced blocks."""
    from creativity_mcp.llm import extract_json

    text = '```json\n{"key": "value"}\n```'
    result = extract_json(text)
    assert result == {"key": "value"}


def test_extract_json_malformed_raises():
    """extract_json raises on malformed input."""
    from creativity_mcp.llm import extract_json

    with pytest.raises(json.JSONDecodeError):
        extract_json("not json at all")
