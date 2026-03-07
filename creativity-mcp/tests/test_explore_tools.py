"""Tests for explore and explore_more MCP tools."""
import json
from unittest.mock import AsyncMock, patch

import pytest

from creativity_mcp.server import explore, explore_more, sessions


@pytest.fixture(autouse=True)
def _clear():
    sessions.clear()
    yield
    sessions.clear()


def _make_spark_response():
    return json.dumps({"challenge": "How might we rethink education?", "is_open": True})


def _make_branch_response(n=3, include_weird=True):
    branches = []
    for i in range(n):
        branches.append({"content": f"Direction {i} on topic {i * 7}", "is_weird": False})
    if include_weird:
        branches.append({"content": "A weird idea", "is_weird": True})
    return json.dumps(branches)


def _make_revisit_response():
    return json.dumps({"sub_branches": [{"content": "Deeper sub", "is_weird": False}]})


def _make_weird_response():
    return json.dumps({"content": "Truly weird", "is_weird": True, "why_weird": "breaks norms"})


def _make_prod_response(verdict="acceptable"):
    return json.dumps({"verdict": verdict, "directive": "ok"})


async def _mock_acall(model, prompt, temperature=1.0):
    if "Restate" in prompt or "open exploration" in prompt:
        return _make_spark_response()
    if "weird" in prompt.lower():
        return _make_weird_response()
    return _make_prod_response("acceptable")


async def _mock_batch(model, prompts, temperature=1.0):
    if prompts and "Go deeper" in prompts[0]:
        return [_make_revisit_response()] * len(prompts)
    return [_make_branch_response()] * len(prompts)


@pytest.mark.anyio
async def test_explore_tool_returns_json_with_session():
    with patch("creativity_mcp.explorer.acall", side_effect=_mock_acall), \
         patch("creativity_mcp.explorer.acall_batch", side_effect=_mock_batch):
        raw = await explore("How to fix education?")

    result = json.loads(raw)
    assert "session_id" in result
    assert "branches" in result
    assert len(result["branches"]) > 0
    assert result["session_id"] in sessions


@pytest.mark.anyio
async def test_explore_tool_with_intensity():
    with patch("creativity_mcp.explorer.acall", side_effect=_mock_acall), \
         patch("creativity_mcp.explorer.acall_batch", side_effect=_mock_batch):
        raw = await explore("Test?", intensity="quick")

    result = json.loads(raw)
    assert result["session_id"] in sessions


@pytest.mark.anyio
async def test_explore_tool_with_domain():
    with patch("creativity_mcp.explorer.acall", side_effect=_mock_acall), \
         patch("creativity_mcp.explorer.acall_batch", side_effect=_mock_batch):
        raw = await explore("Test?", domain="healthcare")

    result = json.loads(raw)
    assert result["session_id"] in sessions


@pytest.mark.anyio
async def test_explore_more_adds_to_session():
    # First create a session via explore
    with patch("creativity_mcp.explorer.acall", side_effect=_mock_acall), \
         patch("creativity_mcp.explorer.acall_batch", side_effect=_mock_batch):
        raw = await explore("Test?", intensity="quick")

    result = json.loads(raw)
    sid = result["session_id"]
    # Un-harvest so extend can work
    sessions[sid].harvested = False
    initial_count = len(sessions[sid].branches)

    with patch("creativity_mcp.explorer.acall_batch", side_effect=_mock_batch):
        raw2 = await explore_more(sid, "go deeper")

    result2 = json.loads(raw2)
    assert result2["session_id"] == sid


@pytest.mark.anyio
async def test_explore_more_missing_session():
    raw = await explore_more("nonexistent", "go deeper")
    result = json.loads(raw)
    assert "error" in result
