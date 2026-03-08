"""Tests for creativity_mcp.llm async OpenRouter client."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

import creativity_mcp.llm as llm_mod


@pytest.fixture(autouse=True)
def _reset_client():
    """Reset shared client between tests."""
    llm_mod._client = None
    yield
    llm_mod._client = None


def _mock_client_with_response(content="hello world"):
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "choices": [{"message": {"content": content}}]
    }
    client = AsyncMock()
    client.post.return_value = mock_response
    client.is_closed = False
    return client, mock_response


@pytest.mark.anyio
async def test_acall_success():
    """acall returns content string on successful response."""
    client, _ = _mock_client_with_response("hello world")

    with patch.object(llm_mod, "_get_client", new_callable=AsyncMock, return_value=client), \
         patch.object(llm_mod, "_get_api_key", return_value="test-key"):
        result = await llm_mod.acall("google/gemini-2.0-flash-001", "test prompt")

    assert result == "hello world"
    client.post.assert_called_once()


@pytest.mark.anyio
async def test_acall_retry_on_http_error():
    """acall retries once on HTTPStatusError, returns on second success."""
    _, mock_response = _mock_client_with_response("retried ok")
    client = AsyncMock()
    client.is_closed = False
    client.post.side_effect = [
        httpx.HTTPStatusError("500", request=MagicMock(), response=MagicMock()),
        mock_response,
    ]

    with patch.object(llm_mod, "_get_client", new_callable=AsyncMock, return_value=client), \
         patch.object(llm_mod, "_get_api_key", return_value="test-key"), \
         patch("creativity_mcp.llm.asyncio.sleep", new_callable=AsyncMock):
        result = await llm_mod.acall("google/gemini-2.0-flash-001", "test prompt")

    assert result == "retried ok"
    assert client.post.call_count == 2


@pytest.mark.anyio
async def test_acall_retry_on_transport_error():
    """acall retries once on TransportError, returns on second success."""
    _, mock_response = _mock_client_with_response("retried ok")
    client = AsyncMock()
    client.is_closed = False
    client.post.side_effect = [
        httpx.ConnectError("connection refused"),
        mock_response,
    ]

    with patch.object(llm_mod, "_get_client", new_callable=AsyncMock, return_value=client), \
         patch.object(llm_mod, "_get_api_key", return_value="test-key"), \
         patch("creativity_mcp.llm.asyncio.sleep", new_callable=AsyncMock):
        result = await llm_mod.acall("google/gemini-2.0-flash-001", "test prompt")

    assert result == "retried ok"
    assert client.post.call_count == 2


@pytest.mark.anyio
async def test_acall_raises_after_both_http_errors():
    """acall raises after both attempts fail with HTTPStatusError."""
    client = AsyncMock()
    client.is_closed = False
    client.post.side_effect = httpx.HTTPStatusError(
        "500", request=MagicMock(), response=MagicMock()
    )

    with patch.object(llm_mod, "_get_client", new_callable=AsyncMock, return_value=client), \
         patch.object(llm_mod, "_get_api_key", return_value="test-key"), \
         patch("creativity_mcp.llm.asyncio.sleep", new_callable=AsyncMock):
        with pytest.raises(httpx.HTTPStatusError):
            await llm_mod.acall("google/gemini-2.0-flash-001", "test prompt")
        assert client.post.call_count == 2


@pytest.mark.anyio
async def test_acall_raises_after_both_transport_errors():
    """acall raises after both attempts fail with TransportError."""
    client = AsyncMock()
    client.is_closed = False
    client.post.side_effect = httpx.ConnectError("connection refused")

    with patch.object(llm_mod, "_get_client", new_callable=AsyncMock, return_value=client), \
         patch.object(llm_mod, "_get_api_key", return_value="test-key"), \
         patch("creativity_mcp.llm.asyncio.sleep", new_callable=AsyncMock):
        with pytest.raises(httpx.ConnectError):
            await llm_mod.acall("google/gemini-2.0-flash-001", "test prompt")
        assert client.post.call_count == 2


@pytest.mark.anyio
async def test_acall_batch_all_succeed():
    """acall_batch returns all results when all succeed."""
    with patch("creativity_mcp.llm.acall", new_callable=AsyncMock) as mock_acall:
        mock_acall.side_effect = ["result1", "result2", "result3"]
        results = await llm_mod.acall_batch("model", ["p1", "p2", "p3"])
        assert results == ["result1", "result2", "result3"]


@pytest.mark.anyio
async def test_acall_batch_partial_failures():
    """acall_batch returns only successes, filters out exceptions."""
    with patch("creativity_mcp.llm.acall", new_callable=AsyncMock) as mock_acall:
        mock_acall.side_effect = [
            "result1",
            RuntimeError("failed"),
            "result3",
        ]
        results = await llm_mod.acall_batch("model", ["p1", "p2", "p3"])
        assert results == ["result1", "result3"]


@pytest.mark.anyio
async def test_acall_batch_all_fail_raises():
    """acall_batch raises RuntimeError when all calls fail."""
    with patch("creativity_mcp.llm.acall", new_callable=AsyncMock) as mock_acall:
        mock_acall.side_effect = RuntimeError("failed")
        with pytest.raises(RuntimeError, match="All .* calls failed"):
            await llm_mod.acall_batch("model", ["p1", "p2"])


def test_extract_json_plain():
    """extract_json parses plain JSON string."""
    result = llm_mod.extract_json('{"key": "value"}')
    assert result == {"key": "value"}


def test_extract_json_markdown_block():
    """extract_json handles ```json markdown fenced blocks."""
    text = '```json\n{"key": "value"}\n```'
    result = llm_mod.extract_json(text)
    assert result == {"key": "value"}


def test_extract_json_malformed_raises():
    """extract_json raises on malformed input."""
    with pytest.raises(json.JSONDecodeError):
        llm_mod.extract_json("not json at all")


def test_get_api_key_raises_when_missing():
    """_get_api_key raises when env var is empty."""
    with patch.dict("os.environ", {"OPENROUTER_API_KEY": ""}):
        with pytest.raises(RuntimeError, match="OPENROUTER_API_KEY not set"):
            llm_mod._get_api_key()


@pytest.mark.anyio
async def test_acall_non_retryable_raises_immediately():
    """acall raises immediately on 401/403 without retrying."""
    client = AsyncMock()
    client.is_closed = False
    resp_mock = MagicMock()
    resp_mock.status_code = 401
    client.post.side_effect = httpx.HTTPStatusError(
        "401", request=MagicMock(), response=resp_mock,
    )

    with patch.object(llm_mod, "_get_client", new_callable=AsyncMock, return_value=client), \
         patch.object(llm_mod, "_get_api_key", return_value="test-key"):
        with pytest.raises(httpx.HTTPStatusError):
            await llm_mod.acall("model", "prompt")
    # Only one attempt — no retry on 401
    assert client.post.call_count == 1


@pytest.mark.anyio
async def test_close_client():
    """close_client shuts down the shared client."""
    client = AsyncMock()
    client.is_closed = False
    llm_mod._client = client

    await llm_mod.close_client()

    client.aclose.assert_awaited_once()
    assert llm_mod._client is None


@pytest.mark.anyio
async def test_close_client_noop_when_none():
    """close_client is safe to call when no client exists."""
    llm_mod._client = None
    await llm_mod.close_client()  # Should not raise
    assert llm_mod._client is None
