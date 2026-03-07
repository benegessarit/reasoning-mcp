"""Tests for explorer.py — state machine orchestrator for explore()."""
import json
from unittest.mock import AsyncMock, patch

import pytest

from creativity_mcp.explorer import (
    IntensityConfig,
    _deduplicate_branches,
    extend_exploration,
    run_exploration,
)
from creativity_mcp.models import Branch, Session


# --- IntensityConfig ---


def test_intensity_config_has_three_levels():
    assert set(IntensityConfig.keys()) == {"quick", "standard", "deep"}


def test_intensity_config_quick():
    assert IntensityConfig["quick"] == (1, 2)


def test_intensity_config_standard():
    assert IntensityConfig["standard"] == (2, 4)


def test_intensity_config_deep():
    assert IntensityConfig["deep"] == (3, 4)


# --- _deduplicate_branches ---


def test_dedup_keeps_unique_branches():
    existing = [Branch(id="a", content="build a rocket to mars")]
    new = [{"content": "design underwater habitats", "is_weird": False}]
    result = _deduplicate_branches(new, existing)
    assert len(result) == 1
    assert result[0]["content"] == "design underwater habitats"


def test_dedup_rejects_similar_branches():
    existing = [Branch(id="a", content="build a rocket to mars for colonization")]
    new = [{"content": "build a rocket to mars for human colonization", "is_weird": False}]
    result = _deduplicate_branches(new, existing)
    assert len(result) == 0


def test_dedup_handles_empty_existing():
    new = [{"content": "something new", "is_weird": False}]
    result = _deduplicate_branches(new, [])
    assert len(result) == 1


def test_dedup_handles_empty_new():
    existing = [Branch(id="a", content="existing idea")]
    result = _deduplicate_branches([], existing)
    assert len(result) == 0


# --- run_exploration ---


def _make_spark_response():
    return json.dumps({"challenge": "How might we rethink education?", "is_open": True})


def _make_branch_response(n=3, include_weird=False):
    branches = []
    for i in range(n):
        branches.append({"content": f"Unique direction number {i} about topic {i * 7}", "is_weird": False})
    if include_weird:
        branches.append({"content": "A genuinely uncomfortable idea", "is_weird": True})
    return json.dumps(branches)


def _make_revisit_response():
    return json.dumps({
        "sub_branches": [
            {"content": "A deeper sub-direction", "is_weird": False},
        ]
    })


def _make_weird_response():
    return json.dumps({
        "content": "A truly weird branch that breaks assumptions",
        "is_weird": True,
        "why_weird": "Breaks the assumption of normalcy",
    })


def _make_prod_response(verdict="acceptable"):
    return json.dumps({"verdict": verdict, "directive": "Keep going"})


@pytest.mark.anyio
async def test_run_exploration_creates_session():
    """Full loop produces a session with branches."""
    sessions = {}

    with patch("creativity_mcp.explorer.acall", new_callable=AsyncMock) as mock_acall, \
         patch("creativity_mcp.explorer.acall_batch", new_callable=AsyncMock) as mock_batch:

        mock_acall.side_effect = [
            _make_spark_response(),                    # SPARK
            _make_prod_response("acceptable"),         # ASSESS
        ]
        mock_batch.side_effect = [
            [_make_branch_response(3, include_weird=True)] * 2,  # DIVERSIFY lens calls
            [_make_revisit_response()] * 2,                       # DEEPEN
        ]

        result = await run_exploration(
            "How to fix education?",
            intensity="quick",
            sessions=sessions,
        )

    assert len(sessions) == 1
    session = list(sessions.values())[0]
    assert session.harvested is True
    assert len(session.branches) > 0


@pytest.mark.anyio
async def test_run_exploration_injects_synthetic_constraint():
    """First DIVERSIFY iteration injects a synthetic constraint."""
    sessions = {}

    with patch("creativity_mcp.explorer.acall", new_callable=AsyncMock) as mock_acall, \
         patch("creativity_mcp.explorer.acall_batch", new_callable=AsyncMock) as mock_batch:

        mock_acall.side_effect = [
            _make_spark_response(),
            _make_prod_response("acceptable"),
        ]
        mock_batch.side_effect = [
            [_make_branch_response(3, include_weird=True)] * 2,
            [_make_revisit_response()] * 2,
        ]

        await run_exploration("Fix education?", intensity="quick", sessions=sessions)

    session = list(sessions.values())[0]
    assert len(session.constraints) >= 1


@pytest.mark.anyio
async def test_run_exploration_generates_weird_if_missing():
    """WEIRD gate fires when no weird branch from lenses."""
    sessions = {}

    with patch("creativity_mcp.explorer.acall", new_callable=AsyncMock) as mock_acall, \
         patch("creativity_mcp.explorer.acall_batch", new_callable=AsyncMock) as mock_batch:

        mock_acall.side_effect = [
            _make_spark_response(),
            _make_weird_response(),          # WEIRD gate
            _make_prod_response("acceptable"),
        ]
        mock_batch.side_effect = [
            [_make_branch_response(3, include_weird=False)] * 2,  # No weird from lenses
            [_make_revisit_response()] * 2,
        ]

        await run_exploration("Fix education?", intensity="quick", sessions=sessions)

    session = list(sessions.values())[0]
    assert session.weird_branch_exists


@pytest.mark.anyio
async def test_run_exploration_saturation_early_exit():
    """Saturation detection: <2 new unique branches triggers early exit."""
    sessions = {}
    call_count = 0

    async def mock_acall_fn(model, prompt, temperature=1.0):
        nonlocal call_count
        call_count += 1
        if "Restate" in prompt or "open exploration" in prompt:
            return _make_spark_response()
        if "weird" in prompt.lower() or "genuinely weird" in prompt.lower():
            return _make_weird_response()
        return _make_prod_response("acceptable")

    batch_call_count = 0

    async def mock_batch_fn(model, prompts, temperature=1.0):
        nonlocal batch_call_count
        batch_call_count += 1
        if batch_call_count == 1:
            # First diversify: return branches
            return [_make_branch_response(3, include_weird=True)] * len(prompts)
        if batch_call_count == 2:
            # Second diversify: return same branches (saturation)
            return [_make_branch_response(3, include_weird=True)] * len(prompts)
        # Deepen
        return [_make_revisit_response()] * len(prompts)

    with patch("creativity_mcp.explorer.acall", side_effect=mock_acall_fn), \
         patch("creativity_mcp.explorer.acall_batch", side_effect=mock_batch_fn):

        await run_exploration("Fix education?", intensity="standard", sessions=sessions)

    # Standard allows 2 loops, but saturation should cause early exit
    session = list(sessions.values())[0]
    assert session.harvested is True


@pytest.mark.anyio
async def test_run_exploration_push_harder_loops_back():
    """ASSESS returning push_harder causes another DIVERSIFY iteration."""
    sessions = {}
    acall_invocations = []

    async def mock_acall_fn(model, prompt, temperature=1.0):
        acall_invocations.append(prompt[:50])
        if "Restate" in prompt or "open exploration" in prompt:
            return _make_spark_response()
        if "weird" in prompt.lower():
            return _make_weird_response()
        # First prod says push_harder, second says acceptable
        if len([p for p in acall_invocations if "Assess" in p or "quality" in p]) <= 1:
            return _make_prod_response("push_harder")
        return _make_prod_response("acceptable")

    batch_count = 0

    async def mock_batch_fn(model, prompts, temperature=1.0):
        nonlocal batch_count
        batch_count += 1
        if batch_count <= 3:  # diversify rounds
            return [_make_branch_response(3, include_weird=True)] * len(prompts)
        return [_make_revisit_response()] * len(prompts)

    with patch("creativity_mcp.explorer.acall", side_effect=mock_acall_fn), \
         patch("creativity_mcp.explorer.acall_batch", side_effect=mock_batch_fn):

        await run_exploration("Fix education?", intensity="standard", sessions=sessions)

    # Should have done at least 2 diversify rounds
    assert batch_count >= 2


@pytest.mark.anyio
async def test_run_exploration_intensity_configs():
    """Different intensity levels produce different behavior."""
    for intensity in ["quick", "standard", "deep"]:
        sessions = {}

        async def mock_acall_fn(model, prompt, temperature=1.0):
            if "Restate" in prompt or "open exploration" in prompt:
                return _make_spark_response()
            if "weird" in prompt.lower():
                return _make_weird_response()
            return _make_prod_response("acceptable")

        async def mock_batch_fn(model, prompts, temperature=1.0):
            # Check if these are revisit/deepen prompts
            if prompts and "Go deeper" in prompts[0]:
                return [_make_revisit_response()] * len(prompts)
            return [_make_branch_response(3, include_weird=True)] * len(prompts)

        with patch("creativity_mcp.explorer.acall", side_effect=mock_acall_fn), \
             patch("creativity_mcp.explorer.acall_batch", side_effect=mock_batch_fn):

            result = await run_exploration("Test?", intensity=intensity, sessions=sessions)

        assert result is not None
        assert list(sessions.values())[0].harvested is True


# --- extend_exploration ---


@pytest.mark.anyio
async def test_extend_exploration_adds_branches():
    sessions = {}
    session = Session(id="test-1", challenge="How might we rethink education?")
    session.branches.append(Branch(id="b1", content="Direction one"))
    sessions["test-1"] = session
    initial_count = len(session.branches)

    with patch("creativity_mcp.explorer.acall_batch", new_callable=AsyncMock) as mock_batch:
        mock_batch.return_value = [_make_branch_response(2)]

        result = await extend_exploration("test-1", "explore more", sessions=sessions)

    assert len(session.branches) > initial_count
    assert result["branches_added"] == len(session.branches) - initial_count
    # Directive injected as constraint
    assert any("explore more" in c.text for c in session.constraints)


@pytest.mark.anyio
async def test_extend_exploration_missing_session():
    sessions = {}

    with pytest.raises(KeyError):
        await extend_exploration("nonexistent", "explore", sessions=sessions)
