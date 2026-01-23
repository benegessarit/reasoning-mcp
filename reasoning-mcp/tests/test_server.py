"""Tests for the Generative Agent Ensemble MCP server."""
import json
import pytest
from reasoning_mcp.server import (
    ensemble,
    invoke,
    perturb,
    synthesize,
    get_session_state,
    sessions,
)


@pytest.fixture(autouse=True)
def clear_sessions():
    sessions.clear()
    yield
    sessions.clear()


def _sample_agents():
    """Sample agents JSON for testing."""
    return json.dumps({
        "agents": [
            {"name": "Performance Engineer", "role": "Speed advocate", "purpose": "Optimize latency", "perspective": "Speed is everything", "is_chaos": False},
            {"name": "Data Integrity Hawk", "role": "Durability advocate", "purpose": "Ensure data safety", "perspective": "Data loss is unacceptable", "is_chaos": False},
            {"name": "Chaos Gremlin", "role": "Failure analyst", "purpose": "Find failure modes", "perspective": "Everything will break", "is_chaos": True},
            {"name": "Discussion Director", "role": "Meta-observer", "purpose": "Assess progress", "perspective": "Push for depth", "is_orchestrator": True},
        ]
    })


def _sample_invoke_response(text: str, suggests: str | None = None):
    """Sample invoke response JSON."""
    return json.dumps({
        "response": text,
        "raises": ["What about edge cases?"],
        "suggests_next": suggests,
    })


def _sample_perturb_result(impact: str):
    """Sample perturb result JSON."""
    return json.dumps({
        "perturbation": "Assumed the opposite",
        "impact": impact,
        "explanation": "Because reasons",
    })


def _sample_synthesis():
    """Sample synthesis JSON."""
    return json.dumps({
        "conclusion": "Use Redis for caching with Postgres as source of truth",
        "confidence": 0.8,
        "dissent": "Data Integrity Hawk wants AOF if any persistence",
        "key_tensions": ["Speed vs durability tradeoff"],
        "assumptions": ["Data is reconstructible", "Team knows Redis"],
    })


# --- ensemble tests ---

@pytest.mark.asyncio
async def test_ensemble_returns_prompt_without_agents():
    """First call to ensemble returns generation prompt."""
    result = json.loads(await ensemble(question="Should we use Redis?"))
    assert result["action"] == "generate_personas"
    assert "prompt" in result
    assert "Redis" in result["prompt"]
    assert "next_step" in result


@pytest.mark.asyncio
async def test_ensemble_creates_session_with_agents():
    """Second call with agents creates session."""
    result = json.loads(await ensemble(
        question="Should we use Redis?",
        agents=_sample_agents(),
    ))
    assert "session_id" in result
    assert len(result["agents"]) == 4
    assert result["chaos_agent"] == "Chaos Gremlin"
    assert result["orchestrator_agent"] == "Discussion Director"


@pytest.mark.asyncio
async def test_ensemble_rejects_too_few_agents():
    """Ensemble rejects fewer agents than min_agents."""
    agents = json.dumps([
        {"name": "A", "role": "R", "purpose": "P", "perspective": "V"},
    ])
    result = json.loads(await ensemble(
        question="Test?",
        agents=agents,
        min_agents=3,
    ))
    assert "error" in result
    assert "at least 3" in result["error"]


@pytest.mark.asyncio
async def test_ensemble_rejects_missing_chaos_agent():
    """Ensemble rejects when include_chaos=True but no chaos agent."""
    agents = json.dumps([
        {"name": "A", "role": "R", "purpose": "P", "perspective": "V", "is_chaos": False},
        {"name": "B", "role": "R", "purpose": "P", "perspective": "V", "is_chaos": False},
        {"name": "C", "role": "R", "purpose": "P", "perspective": "V", "is_chaos": False, "is_orchestrator": True},
    ])
    result = json.loads(await ensemble(
        question="Test?",
        agents=agents,
        include_chaos=True,
    ))
    assert "error" in result
    assert "chaos" in result["error"].lower()


@pytest.mark.asyncio
async def test_ensemble_allows_no_chaos_when_disabled():
    """Ensemble accepts no chaos agent when include_chaos=False."""
    agents = json.dumps([
        {"name": "A", "role": "R", "purpose": "P", "perspective": "V"},
        {"name": "B", "role": "R", "purpose": "P", "perspective": "V"},
        {"name": "C", "role": "R", "purpose": "P", "perspective": "V"},
    ])
    result = json.loads(await ensemble(
        question="Test?",
        agents=agents,
        include_chaos=False,
        include_orchestrator=False,
    ))
    assert "session_id" in result
    assert result["chaos_agent"] is None


@pytest.mark.asyncio
async def test_ensemble_accepts_native_dict():
    """Ensemble accepts agents as native dict (not just JSON string).

    MCP clients may pass already-parsed JSON objects instead of strings.
    """
    agents_dict = {
        "agents": [
            {"name": "A", "role": "R", "purpose": "P", "perspective": "V", "is_chaos": True},
            {"name": "B", "role": "R", "purpose": "P", "perspective": "V"},
            {"name": "C", "role": "R", "purpose": "P", "perspective": "V"},
            {"name": "D", "role": "R", "purpose": "P", "perspective": "V", "is_orchestrator": True},
        ]
    }
    result = json.loads(await ensemble(
        question="Test?",
        agents=agents_dict,  # Native dict, not json.dumps()
    ))
    assert "session_id" in result
    assert len(result["agents"]) == 4


@pytest.mark.asyncio
async def test_ensemble_accepts_native_list():
    """Ensemble accepts agents as native list (not just JSON string)."""
    agents_list = [
        {"name": "A", "role": "R", "purpose": "P", "perspective": "V", "is_chaos": True},
        {"name": "B", "role": "R", "purpose": "P", "perspective": "V"},
        {"name": "C", "role": "R", "purpose": "P", "perspective": "V"},
        {"name": "D", "role": "R", "purpose": "P", "perspective": "V", "is_orchestrator": True},
    ]
    result = json.loads(await ensemble(
        question="Test?",
        agents=agents_list,  # Native list, not json.dumps()
    ))
    assert "session_id" in result
    assert len(result["agents"]) == 4


# --- invoke tests ---

@pytest.mark.asyncio
async def test_invoke_returns_prompt_without_response():
    """First call to invoke returns role-play prompt."""
    # Setup session
    session_result = json.loads(await ensemble(
        question="Should we use Redis?",
        agents=_sample_agents(),
    ))
    session_id = session_result["session_id"]

    result = json.loads(await invoke(
        session_id=session_id,
        agent="Performance Engineer",
    ))
    assert result["action"] == "role_play"
    assert "prompt" in result
    assert "Performance Engineer" in result["prompt"]


@pytest.mark.asyncio
async def test_invoke_registers_response():
    """Second call with response registers invocation."""
    # Setup session
    session_result = json.loads(await ensemble(
        question="Should we use Redis?",
        agents=_sample_agents(),
    ))
    session_id = session_result["session_id"]

    # Get prompt (first call)
    await invoke(session_id=session_id, agent="Performance Engineer")

    # Register response (second call)
    result = json.loads(await invoke(
        session_id=session_id,
        agent="Performance Engineer",
        response=_sample_invoke_response("Redis is fast, 0.1ms reads."),
    ))
    assert result["registered"] is True
    assert result["invocation_number"] == 1
    assert result["unique_agents_invoked"] == 1


@pytest.mark.asyncio
async def test_invoke_accepts_native_dict():
    """Invoke accepts response as native dict (not just JSON string)."""
    session_result = json.loads(await ensemble(
        question="Test?",
        agents=_sample_agents(),
    ))
    session_id = session_result["session_id"]

    # Pass response as native dict, not JSON string
    result = json.loads(await invoke(
        session_id=session_id,
        agent="Performance Engineer",
        response={"response": "Fast", "raises": [], "suggests_next": None},
    ))
    assert result["registered"] is True


@pytest.mark.asyncio
async def test_invoke_rejects_unknown_agent():
    """Invoke rejects agents not in ensemble."""
    session_result = json.loads(await ensemble(
        question="Test?",
        agents=_sample_agents(),
    ))
    session_id = session_result["session_id"]

    result = json.loads(await invoke(
        session_id=session_id,
        agent="Unknown Agent",
    ))
    assert "error" in result
    assert "not in ensemble" in result["error"]


@pytest.mark.asyncio
async def test_invoke_tracks_unique_agents():
    """Invoke tracks unique agents invoked."""
    session_result = json.loads(await ensemble(
        question="Test?",
        agents=_sample_agents(),
    ))
    session_id = session_result["session_id"]

    # Invoke same agent twice
    await invoke(session_id=session_id, agent="Performance Engineer",
                 response=_sample_invoke_response("First response"))
    result = json.loads(await invoke(
        session_id=session_id,
        agent="Performance Engineer",
        response=_sample_invoke_response("Second response"),
    ))

    assert result["invocation_number"] == 2
    assert result["unique_agents_invoked"] == 1  # Still 1


@pytest.mark.asyncio
async def test_invoke_session_not_found():
    """Invoke returns error for unknown session."""
    result = json.loads(await invoke(
        session_id="nonexistent",
        agent="Test",
    ))
    assert "error" in result
    assert "not found" in result["error"]


# --- perturb tests ---

@pytest.mark.asyncio
async def test_perturb_returns_prompt_without_result():
    """First call to perturb returns perturbation prompt."""
    session_result = json.loads(await ensemble(
        question="Test?",
        agents=_sample_agents(),
    ))
    session_id = session_result["session_id"]

    result = json.loads(await perturb(
        session_id=session_id,
        target="Redis is fast",
        mode="negate",
    ))
    assert result["action"] == "perturb"
    assert "prompt" in result
    assert "negate" in result["prompt"]


@pytest.mark.asyncio
async def test_perturb_registers_result():
    """Second call with result registers perturbation."""
    session_result = json.loads(await ensemble(
        question="Test?",
        agents=_sample_agents(),
    ))
    session_id = session_result["session_id"]

    result = json.loads(await perturb(
        session_id=session_id,
        target="Redis is fast",
        mode="negate",
        result=_sample_perturb_result("survives"),
    ))
    assert result["registered"] is True
    assert result["impact"] == "survives"


@pytest.mark.asyncio
async def test_perturb_validates_impact():
    """Perturb validates impact field."""
    session_result = json.loads(await ensemble(
        question="Test?",
        agents=_sample_agents(),
    ))
    session_id = session_result["session_id"]

    bad_result = json.dumps({
        "perturbation": "test",
        "impact": "invalid",
        "explanation": "test",
    })
    result = json.loads(await perturb(
        session_id=session_id,
        target="test",
        result=bad_result,
    ))
    assert "error" in result
    assert "survives" in result["error"]


# --- synthesize tests ---

@pytest.mark.asyncio
async def test_synthesize_blocked_until_min_agents():
    """Synthesize is blocked until min_agents invoked."""
    session_result = json.loads(await ensemble(
        question="Test?",
        agents=_sample_agents(),
        min_agents=3,
    ))
    session_id = session_result["session_id"]

    # Only invoke 2 agents
    await invoke(session_id=session_id, agent="Performance Engineer",
                 response=_sample_invoke_response("Fast"))
    await invoke(session_id=session_id, agent="Data Integrity Hawk",
                 response=_sample_invoke_response("Safe"))

    result = json.loads(await synthesize(session_id=session_id))
    assert "error" in result
    assert "at least 3" in result["error"]
    assert result["count"] == 2


@pytest.mark.asyncio
async def test_synthesize_returns_prompt_when_ready():
    """Synthesize returns prompt when min_agents met."""
    session_result = json.loads(await ensemble(
        question="Test?",
        agents=_sample_agents(),
        min_agents=3,
    ))
    session_id = session_result["session_id"]

    # Invoke all 3 agents
    await invoke(session_id=session_id, agent="Performance Engineer",
                 response=_sample_invoke_response("Fast"))
    await invoke(session_id=session_id, agent="Data Integrity Hawk",
                 response=_sample_invoke_response("Safe"))
    await invoke(session_id=session_id, agent="Chaos Gremlin",
                 response=_sample_invoke_response("What if it breaks?"))

    result = json.loads(await synthesize(session_id=session_id))
    assert result["action"] == "synthesize"
    assert "prompt" in result
    assert len(result["agents_heard"]) == 3


@pytest.mark.asyncio
async def test_synthesize_completes_session():
    """Synthesize with synthesis JSON completes session."""
    session_result = json.loads(await ensemble(
        question="Test?",
        agents=_sample_agents(),
        min_agents=3,
    ))
    session_id = session_result["session_id"]

    # Invoke all agents
    await invoke(session_id=session_id, agent="Performance Engineer",
                 response=_sample_invoke_response("Fast"))
    await invoke(session_id=session_id, agent="Data Integrity Hawk",
                 response=_sample_invoke_response("Safe"))
    await invoke(session_id=session_id, agent="Chaos Gremlin",
                 response=_sample_invoke_response("Breaks"))

    result = json.loads(await synthesize(
        session_id=session_id,
        synthesis=_sample_synthesis(),
    ))
    assert result["workflow_complete"] is True
    assert result["conclusion"] == "Use Redis for caching with Postgres as source of truth"
    assert result["confidence"] == 0.8


@pytest.mark.asyncio
async def test_synthesize_blocks_after_completion():
    """Synthesize blocks after session is complete."""
    session_result = json.loads(await ensemble(
        question="Test?",
        agents=_sample_agents(),
        min_agents=3,
    ))
    session_id = session_result["session_id"]

    # Complete session
    await invoke(session_id=session_id, agent="Performance Engineer",
                 response=_sample_invoke_response("Fast"))
    await invoke(session_id=session_id, agent="Data Integrity Hawk",
                 response=_sample_invoke_response("Safe"))
    await invoke(session_id=session_id, agent="Chaos Gremlin",
                 response=_sample_invoke_response("Breaks"))
    await synthesize(session_id=session_id, synthesis=_sample_synthesis())

    # Try again
    result = json.loads(await synthesize(session_id=session_id))
    assert "error" in result
    assert "already synthesized" in result["error"]


# --- get_session_state tests ---

@pytest.mark.asyncio
async def test_get_session_state():
    """get_session_state returns session info."""
    session_result = json.loads(await ensemble(
        question="Test?",
        agents=_sample_agents(),
    ))
    session_id = session_result["session_id"]

    await invoke(session_id=session_id, agent="Performance Engineer",
                 response=_sample_invoke_response("Fast"))

    state = json.loads(await get_session_state(session_id))
    assert state["session_id"] == session_id
    assert state["question"] == "Test?"
    assert len(state["agents"]) == 4
    assert len(state["invocations"]) == 1
    assert state["unique_agents_invoked"] == 1
    assert state["synthesized"] is False


@pytest.mark.asyncio
async def test_get_session_state_not_found():
    """get_session_state returns error for unknown session."""
    result = json.loads(await get_session_state("nonexistent"))
    assert "error" in result
    assert "not found" in result["error"]


# --- orchestrator tests ---

@pytest.mark.asyncio
async def test_ensemble_rejects_missing_orchestrator():
    """Ensemble rejects when include_orchestrator=True but no orchestrator agent."""
    agents = json.dumps([
        {"name": "A", "role": "R", "purpose": "P", "perspective": "V", "is_chaos": True},
        {"name": "B", "role": "R", "purpose": "P", "perspective": "V"},
        {"name": "C", "role": "R", "purpose": "P", "perspective": "V"},
    ])
    result = json.loads(await ensemble(
        question="Test?",
        agents=agents,
        include_orchestrator=True,
    ))
    assert "error" in result
    assert "orchestrator" in result["error"].lower()


@pytest.mark.asyncio
async def test_ensemble_allows_no_orchestrator_when_disabled():
    """Ensemble accepts no orchestrator when include_orchestrator=False."""
    agents = json.dumps([
        {"name": "A", "role": "R", "purpose": "P", "perspective": "V", "is_chaos": True},
        {"name": "B", "role": "R", "purpose": "P", "perspective": "V"},
        {"name": "C", "role": "R", "purpose": "P", "perspective": "V"},
    ])
    result = json.loads(await ensemble(
        question="Test?",
        agents=agents,
        include_orchestrator=False,
    ))
    assert "session_id" in result
    assert result["orchestrator_agent"] is None


@pytest.mark.asyncio
async def test_orchestrator_gets_special_prompt():
    """Orchestrator invocation returns orchestrate action with special prompt."""
    session_result = json.loads(await ensemble(
        question="Should we use Redis?",
        agents=_sample_agents(),
    ))
    session_id = session_result["session_id"]

    # First invoke a regular agent
    await invoke(session_id=session_id, agent="Performance Engineer",
                 response=_sample_invoke_response("Fast", "Data Integrity Hawk"))

    # Now invoke the orchestrator
    result = json.loads(await invoke(
        session_id=session_id,
        agent="Discussion Director",
    ))
    assert result["action"] == "orchestrate"
    assert "ORCHESTRATOR" in result["prompt"]
    assert "PROGRESS CHECK" in result["prompt"]
    assert "COVERAGE AUDIT" in result["prompt"]
    assert "TENSION DETECTOR" in result["prompt"]


@pytest.mark.asyncio
async def test_orchestrator_prompt_includes_context():
    """Orchestrator prompt includes agents spoken and unanswered questions."""
    session_result = json.loads(await ensemble(
        question="Should we use Redis?",
        agents=_sample_agents(),
    ))
    session_id = session_result["session_id"]

    # Invoke agents with questions
    await invoke(session_id=session_id, agent="Performance Engineer",
                 response=_sample_invoke_response("Redis is fast"))
    await invoke(session_id=session_id, agent="Data Integrity Hawk",
                 response=_sample_invoke_response("What about durability?"))

    # Orchestrator prompt should include context
    result = json.loads(await invoke(
        session_id=session_id,
        agent="Discussion Director",
    ))
    assert "Performance Engineer" in result["prompt"]
    assert "Data Integrity Hawk" in result["prompt"]
