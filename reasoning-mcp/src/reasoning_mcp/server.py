"""Reasoning MCP server.

Enforces multi-turn ensemble reasoning: Claude generates personas,
role-plays each in separate turns, then synthesizes.
"""
import json
import uuid
from typing import Literal

from mcp.server.fastmcp import FastMCP

from reasoning_mcp.models import Agent, Invocation, Perturbation, Session
from reasoning_mcp.prompts import (
    CHAOS_INSTRUCTION,
    DEPTH_PROBE_PROMPTS,
    ENSEMBLE_PROMPT,
    INVOKE_PROMPT,
    ORCHESTRATOR_INSTRUCTION,
    ORCHESTRATOR_INVOKE_PROMPT,
    PERTURB_PROMPT,
    PERTURBATIONS_CONTEXT,
    PRIOR_CONTEXT_TEMPLATE,
    SYNTHESIZE_PROMPT,
)

mcp = FastMCP("reasoning_mcp")
sessions: dict[str, Session] = {}


def _json(obj: dict) -> str:
    return json.dumps(obj, indent=2)


def _normalize_json(value: str | dict | list) -> dict | list:
    """Normalize JSON input - handles both strings and already-parsed objects.

    MCP clients may pass JSON as strings OR as already-parsed dicts/lists.
    This function handles both cases uniformly.
    """
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON: {e}")


def _parse_agents(agents_input: str | dict | list) -> list[Agent]:
    """Parse agents from JSON string or already-parsed object."""
    data = _normalize_json(agents_input)

    if isinstance(data, dict) and "agents" in data:
        agents_list = data["agents"]
    elif isinstance(data, list):
        agents_list = data
    else:
        raise ValueError("Expected JSON array of agents or object with 'agents' key")

    agents = []
    for i, a in enumerate(agents_list):
        if not isinstance(a, dict):
            raise ValueError(f"Agent {i} must be an object")
        for field in ("name", "role", "purpose", "perspective"):
            if field not in a:
                raise ValueError(f"Agent {i} missing required field '{field}'")
        agents.append(Agent(
            name=a["name"],
            role=a["role"],
            purpose=a["purpose"],
            perspective=a["perspective"],
            is_chaos=a.get("is_chaos", False),
            is_orchestrator=a.get("is_orchestrator", False),
        ))
    return agents


def _collect_unanswered_questions(session: Session) -> list[str]:
    """Collect questions raised but not addressed in subsequent invocations."""
    all_raised: list[str] = []
    all_responses = " ".join(inv.response.lower() for inv in session.invocations)

    for inv in session.invocations:
        for q in inv.raises:
            # Simple heuristic: if keywords from question appear in later responses, consider addressed
            keywords = [w for w in q.lower().split() if len(w) > 4]
            addressed = any(kw in all_responses for kw in keywords) if keywords else False
            if not addressed:
                all_raised.append(f"{inv.agent} asked: {q}")

    return all_raised


def _format_invocations(invocations: list[Invocation]) -> str:
    """Format invocations for context."""
    if not invocations:
        return "(No prior discussion)"
    lines = []
    for inv in invocations:
        lines.append(f"**{inv.agent}**: {inv.response}")
        if inv.raises:
            lines.append(f"  Raised: {', '.join(inv.raises)}")
    return "\n\n".join(lines)


def _format_perturbations(perturbations: list[Perturbation]) -> str:
    """Format perturbations for context."""
    if not perturbations:
        return ""
    lines = []
    for p in perturbations:
        lines.append(f"- **{p.target}** ({p.mode}): {p.impact} — {p.explanation}")
    return PERTURBATIONS_CONTEXT.format(perturbations="\n".join(lines))


@mcp.tool()
async def ensemble(
    question: str,
    agents: str | dict | list | None = None,
    min_agents: int = 3,
    include_chaos: bool = True,
    include_orchestrator: bool = True,
) -> str:
    """Generate or register an ensemble of personas for reasoning about a question.

    Call without agents to get the generation prompt.
    Call with agents JSON to register the ensemble and get session ID.

    Args:
        question: The question/problem to reason about
        agents: JSON string of generated agents (call without this first to get prompt)
        min_agents: Minimum personas required (default 3)
        include_chaos: Whether to require a chaos/perturbation agent (default True)
        include_orchestrator: Whether to require an orchestrator agent (default True)

    Returns:
        Without agents: Prompt for generating personas
        With agents: Session info including session_id and registered agents
    """
    if agents is None:
        # Return prompt for generating personas
        chaos_instruction = CHAOS_INSTRUCTION if include_chaos else ""
        orchestrator_instruction = ORCHESTRATOR_INSTRUCTION if include_orchestrator else ""
        prompt = ENSEMBLE_PROMPT.format(
            question=question,
            min_agents=min_agents,
            chaos_instruction=chaos_instruction,
            orchestrator_instruction=orchestrator_instruction,
        )
        return _json({
            "action": "generate_personas",
            "prompt": prompt,
            "next_step": "Call ensemble again with the 'agents' parameter containing your generated JSON",
        })

    # Parse and validate agents
    parsed_agents = _parse_agents(agents)

    if len(parsed_agents) < min_agents:
        return _json({
            "error": f"Need at least {min_agents} agents, got {len(parsed_agents)}",
            "action": "Add more personas with distinct perspectives",
        })

    if include_chaos and not any(a.is_chaos for a in parsed_agents):
        return _json({
            "error": "Missing chaos/perturbation agent (is_chaos: true)",
            "action": "Add one agent with is_chaos: true to stress-test assumptions",
        })

    if include_orchestrator and not any(a.is_orchestrator for a in parsed_agents):
        return _json({
            "error": "Missing orchestrator agent (is_orchestrator: true)",
            "action": "Add one agent with is_orchestrator: true to assess discussion progress and push for depth",
        })

    # Create session
    session_id = str(uuid.uuid4())[:8]
    session = Session(
        id=session_id,
        question=question,
        agents=parsed_agents,
        min_agents=min_agents,
    )
    sessions[session_id] = session

    chaos_agent = next((a.name for a in parsed_agents if a.is_chaos), None)
    orchestrator_agent = next((a.name for a in parsed_agents if a.is_orchestrator), None)

    return _json({
        "session_id": session_id,
        "agents": [a.to_dict() for a in parsed_agents],
        "suggested_order": [a.name for a in parsed_agents],
        "chaos_agent": chaos_agent,
        "orchestrator_agent": orchestrator_agent,
        "next_step": f"Call invoke with session_id='{session_id}' and agent='<name>' to role-play each persona",
    })


@mcp.tool()
async def invoke(
    session_id: str,
    agent: str,
    response: str | dict | None = None,
    context: str | None = None,
) -> str:
    """Role-play as a specific persona for ONE turn.

    Call without response to get the role-play prompt.
    Call with response JSON to register the invocation.

    Args:
        session_id: Session ID from ensemble()
        agent: Name of the persona to invoke
        response: JSON string of the agent's response (call without this first to get prompt)
        context: Optional additional context for this turn

    Returns:
        Without response: Prompt for role-playing this persona
        With response: Confirmation and suggestion for next step
    """
    if session_id not in sessions:
        return _json({"error": f"Session '{session_id}' not found"})

    session = sessions[session_id]

    if session.synthesized:
        return _json({"error": "Session already synthesized. Start a new session for new questions."})

    agent_obj = next((a for a in session.agents if a.name == agent), None)
    if agent_obj is None:
        available = [a.name for a in session.agents]
        return _json({
            "error": f"Agent '{agent}' not in ensemble",
            "available_agents": available,
        })

    if response is None:
        # Return prompt for role-playing
        prior_context = _format_invocations(session.invocations) if session.invocations else "(No prior discussion)"

        # Use special prompt for orchestrator
        if agent_obj.is_orchestrator:
            agents_spoken = list(set(i.agent for i in session.invocations))
            available_agents = [a.name for a in session.agents if not a.is_orchestrator]
            unanswered = _collect_unanswered_questions(session)

            prompt = ORCHESTRATOR_INVOKE_PROMPT.format(
                question=session.question,
                prior_context=prior_context,
                available_agents=", ".join(available_agents),
                agents_spoken=", ".join(agents_spoken) if agents_spoken else "(none yet)",
                unanswered_questions="\n".join(f"- {q}" for q in unanswered) if unanswered else "(none tracked)",
            )
        else:
            formatted_prior = ""
            if session.invocations:
                formatted_prior = PRIOR_CONTEXT_TEMPLATE.format(invocations=prior_context)

            prompt = INVOKE_PROMPT.format(
                agent_name=agent_obj.name,
                agent_role=agent_obj.role,
                agent_purpose=agent_obj.purpose,
                agent_perspective=agent_obj.perspective,
                question=session.question,
                prior_context=formatted_prior,
                additional_context=context or "",
            )

        return _json({
            "action": "role_play" if not agent_obj.is_orchestrator else "orchestrate",
            "agent": agent_obj.to_dict(),
            "prompt": prompt,
            "invocations_so_far": len(session.invocations),
            "next_step": f"Role-play as {agent}, then call invoke again with 'response' parameter containing JSON",
        })

    # Parse and register response
    try:
        data = _normalize_json(response)
    except ValueError as e:
        return _json({"error": f"Invalid response JSON: {e}"})

    if not isinstance(data, dict):
        return _json({"error": "Response must be a JSON object, not an array"})

    if "response" not in data:
        return _json({"error": "Response JSON must include 'response' field"})

    invocation = Invocation(
        agent=agent,
        response=data["response"],
        raises=data.get("raises", []),
        suggests_next=data.get("suggests_next"),
    )
    session.invocations.append(invocation)

    unique_agents = set(i.agent for i in session.invocations)
    can_synthesize = len(unique_agents) >= session.min_agents

    result: dict = {
        "registered": True,
        "agent": agent,
        "invocation_number": len(session.invocations),
        "unique_agents_invoked": len(unique_agents),
        "min_agents_required": session.min_agents,
        "can_synthesize": can_synthesize,
    }

    if invocation.raises:
        result["raises"] = invocation.raises

    if invocation.suggests_next:
        if invocation.suggests_next.lower() == "synthesize":
            if can_synthesize:
                result["next_step"] = f"Call synthesize(session_id='{session_id}')"
            else:
                result["next_step"] = f"Need {session.min_agents - len(unique_agents)} more unique agents before synthesize"
        else:
            result["suggests_next"] = invocation.suggests_next
            result["next_step"] = f"Call invoke with agent='{invocation.suggests_next}'"
    else:
        remaining = [a.name for a in session.agents if a.name not in unique_agents]
        if remaining:
            result["remaining_agents"] = remaining
            result["next_step"] = f"Continue with: {remaining[0]} or another agent"
        elif can_synthesize:
            result["next_step"] = f"All agents heard. Call synthesize(session_id='{session_id}')"

    return _json(result)


@mcp.tool()
async def perturb(
    session_id: str,
    target: str,
    mode: Literal["negate", "remove", "extreme", "opposite"] = "negate",
    result: str | dict | None = None,
) -> str:
    """Apply chaos engineering to test reasoning robustness.

    Call without result to get the perturbation prompt.
    Call with result JSON to register the perturbation.

    Args:
        session_id: Session ID from ensemble()
        target: The assumption/claim to perturb
        mode: Perturbation mode (negate, remove, extreme, opposite)
        result: JSON string of perturbation result (call without this first to get prompt)

    Returns:
        Without result: Prompt for applying the perturbation
        With result: Confirmation of registered perturbation
    """
    if session_id not in sessions:
        return _json({"error": f"Session '{session_id}' not found"})

    session = sessions[session_id]

    if session.synthesized:
        return _json({"error": "Session already synthesized"})

    if result is None:
        # Return prompt for perturbation
        context = _format_invocations(session.invocations)
        prompt = PERTURB_PROMPT.format(
            target=target,
            mode=mode,
            context=context,
        )

        return _json({
            "action": "perturb",
            "target": target,
            "mode": mode,
            "prompt": prompt,
            "next_step": "Apply perturbation, then call perturb again with 'result' parameter containing JSON",
        })

    # Parse and register perturbation
    try:
        data = _normalize_json(result)
    except ValueError as e:
        return _json({"error": f"Invalid result JSON: {e}"})

    if not isinstance(data, dict):
        return _json({"error": "Result must be a JSON object, not an array"})

    for field in ("perturbation", "impact", "explanation"):
        if field not in data:
            return _json({"error": f"Result JSON must include '{field}' field"})

    if data["impact"] not in ("survives", "breaks", "weakens"):
        return _json({"error": "impact must be 'survives', 'breaks', or 'weakens'"})

    perturbation = Perturbation(
        target=target,
        mode=mode,
        impact=data["impact"],
        explanation=data["explanation"],
    )
    session.perturbations.append(perturbation)

    return _json({
        "registered": True,
        "perturbation_number": len(session.perturbations),
        "target": target,
        "impact": data["impact"],
        "next_step": "Continue invoking agents, perturb more assumptions, or synthesize when ready",
    })


@mcp.tool()
async def synthesize(
    session_id: str,
    synthesis: str | dict | None = None,
) -> str:
    """Forced synthesis of all perspectives into a conclusion.

    Call without synthesis to get the synthesis prompt (blocked until min_agents invoked).
    Call with synthesis JSON to complete the session.

    Args:
        session_id: Session ID from ensemble()
        synthesis: JSON string of synthesis result (call without this first to get prompt)

    Returns:
        Without synthesis: Prompt for synthesizing perspectives
        With synthesis: Final session summary
    """
    if session_id not in sessions:
        return _json({"error": f"Session '{session_id}' not found"})

    session = sessions[session_id]

    if session.synthesized:
        return _json({"error": "Session already synthesized"})

    # Enforce min_agents
    unique_agents = set(i.agent for i in session.invocations)
    if len(unique_agents) < session.min_agents:
        return _json({
            "error": f"Must invoke at least {session.min_agents} unique agents before synthesizing",
            "invoked": list(unique_agents),
            "count": len(unique_agents),
            "required": session.min_agents,
            "remaining": [a.name for a in session.agents if a.name not in unique_agents],
        })

    if synthesis is None:
        # Return prompt for synthesis
        invocations_text = _format_invocations(session.invocations)
        perturbations_text = _format_perturbations(session.perturbations)

        prompt = SYNTHESIZE_PROMPT.format(
            question=session.question,
            invocations=invocations_text,
            perturbations=perturbations_text,
        )

        return _json({
            "action": "synthesize",
            "agents_heard": list(unique_agents),
            "perturbations_applied": len(session.perturbations),
            "prompt": prompt,
            "next_step": "Synthesize all perspectives, then call synthesize again with 'synthesis' parameter containing JSON",
        })

    # Parse and complete session
    try:
        data = _normalize_json(synthesis)
    except ValueError as e:
        return _json({"error": f"Invalid synthesis JSON: {e}"})

    if not isinstance(data, dict):
        return _json({"error": "Synthesis must be a JSON object, not an array"})

    for field in ("conclusion", "confidence", "key_tensions", "assumptions"):
        if field not in data:
            return _json({"error": f"Synthesis JSON must include '{field}' field"})

    session.synthesized = True

    return _json({
        "workflow_complete": True,
        "session_id": session_id,
        "question": session.question,
        "conclusion": data["conclusion"],
        "confidence": data["confidence"],
        "dissent": data.get("dissent"),
        "key_tensions": data["key_tensions"],
        "assumptions": data["assumptions"],
        "agents_heard": [i.agent for i in session.invocations],
        "total_invocations": len(session.invocations),
        "perturbations_applied": len(session.perturbations),
    })


@mcp.tool()
async def get_session_state(session_id: str) -> str:
    """Get current state of a reasoning session.

    Args:
        session_id: Session ID from ensemble()

    Returns:
        Session state including agents, invocations, and progress
    """
    if session_id not in sessions:
        return _json({"error": f"Session '{session_id}' not found"})

    session = sessions[session_id]
    unique_agents = set(i.agent for i in session.invocations)

    return _json({
        "session_id": session_id,
        "question": session.question,
        "agents": [a.to_dict() for a in session.agents],
        "invocations": [
            {"agent": i.agent, "raises": i.raises, "suggests_next": i.suggests_next}
            for i in session.invocations
        ],
        "perturbations": [
            {"target": p.target, "mode": p.mode, "impact": p.impact}
            for p in session.perturbations
        ],
        "unique_agents_invoked": len(unique_agents),
        "min_agents_required": session.min_agents,
        "can_synthesize": len(unique_agents) >= session.min_agents,
        "synthesized": session.synthesized,
    })


@mcp.tool()
async def depth_probe(
    question: str,
    mode: Literal["vanilla", "failure", "assumption", "stakeholder", "meta"] = "vanilla",
    prior: str | dict | None = None,
    result: str | dict | None = None,
) -> str:
    """Metacognitive audit of reasoning process before executing.

    Forces examination of the thinking itself from different cognitive orientations.

    Modes:
    - vanilla: Is the framing right? Where will reasoning be shallow?
    - failure: What are the most plausible wrong answers?
    - assumption: What unstated assumptions does this question bake in?
    - stakeholder: Who would disagree with the obvious answer and why?
    - meta: Re-probe using findings from a previous probe (requires prior)

    Call without result to get the self-interrogation prompt.
    Call with result JSON to capture the reflection.

    Args:
        question: The question/problem to probe
        mode: Cognitive orientation for the probe (default: vanilla)
        prior: Previous probe findings for meta mode (string or dict, ignored by other modes)
        result: JSON with reframing, thinking_required, shallow_spots, missing_dimensions, process_critique
    """
    if mode == "meta" and prior is None and result is None:
        return _json({"error": "meta mode requires 'prior' parameter with previous probe findings"})

    if result is None:
        # Use .replace() instead of .format() to avoid KeyError on user braces
        prompt = DEPTH_PROBE_PROMPTS[mode].replace("{question}", question)
        if mode == "meta":
            prior_text = json.dumps(prior, indent=2) if isinstance(prior, dict) else prior
            prompt = prompt.replace("{prior}", prior_text)

        return _json({
            "action": "depth_probe",
            "mode": mode,
            "prompt": prompt,
            "next_step": "Audit your reasoning process, then call depth_probe with result JSON",
        })

    try:
        data = _normalize_json(result)
    except ValueError as e:
        return _json({"error": f"Invalid result JSON: {e}"})

    if not isinstance(data, dict):
        return _json({"error": "Result must be a JSON object"})

    required = ("reframing", "thinking_required", "shallow_spots", "missing_dimensions", "process_critique")
    for field in required:
        if field not in data:
            return _json({"error": f"Missing required field: '{field}'"})

    return _json({
        "probed": True,
        "mode": mode,
        "reframing": data["reframing"],
        "thinking_required": data["thinking_required"],
        "shallow_spots": data["shallow_spots"],
        "missing_dimensions": data["missing_dimensions"],
        "process_critique": data["process_critique"],
    })
