"""Creativity MCP server.

Enforces anti-convergence through structural forcing functions:
- PROD demands more until genuine exhaustion
- Harvest blocked until conditions met
- Prompts push Claude to explore genuinely different directions
"""
import json
import uuid

from mcp.server.fastmcp import FastMCP

from creativity_mcp.models import Branch, Constraint, PruneRecord, Session
from creativity_mcp.oracle import get_concept_for_session
from creativity_mcp.prompts import (
    BRANCH_PROMPT,
    CONSTRAIN_PROMPT,
    HARVEST_PROMPT,
    MUTATE_PROMPT,
    PROD_PROMPT,
    PRUNE_PROMPT,
    REVISIT_PROMPT,
    SPARK_PROMPT,
    WEIRD_PROMPT,
)

mcp = FastMCP("creativity_mcp")
sessions: dict[str, Session] = {}


def _json(obj: dict) -> str:
    return json.dumps(obj, indent=2)


def _normalize_json(value: str | dict | list) -> dict | list:
    """Normalize JSON input - handles both strings and already-parsed objects."""
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON: {e}")


def _format_branches(branches: list[Branch]) -> str:
    """Format branches for prompt context (skips archived)."""
    active = [b for b in branches if not b.archived]
    if not active:
        return "(No branches yet)"
    lines = []
    for b in active:
        weird_marker = " [WEIRD]" if b.is_weird else ""
        lines.append(f"- [{b.id}]{weird_marker} (depth {b.depth}): {b.content}")
    return "\n".join(lines)


def _format_constraints(constraints: list[Constraint]) -> str:
    """Format constraints for prompt context."""
    if not constraints:
        return "(No constraints applied)"
    return "\n".join(f"- {c.text}" for c in constraints)


@mcp.tool()
async def spark(
    challenge: str,
    domain: str | None = None,
) -> str:
    """Open a creative exploration space.

    Args:
        challenge: The creative challenge to explore
        domain: Optional domain context

    Returns:
        Prompt for sparking the exploration, or session info if spark is valid
    """
    domain_context = f"DOMAIN: {domain}" if domain else ""
    prompt = SPARK_PROMPT.format(challenge=challenge, domain_context=domain_context)

    return _json({
        "action": "spark",
        "prompt": prompt,
        "next_step": "Evaluate the challenge and call spark_register with the result",
    })


@mcp.tool()
async def spark_register(
    challenge: str,
    result: str | dict,
    domain: str | None = None,
) -> str:
    """Register the spark evaluation result.

    Args:
        challenge: The original challenge
        result: JSON with spark, is_open, rejection_reason
        domain: Optional domain context

    Returns:
        Session info if valid, error if solution-shaped
    """
    try:
        data = _normalize_json(result)
    except ValueError as e:
        return _json({"error": str(e)})

    if not isinstance(data, dict):
        return _json({"error": "Result must be a JSON object"})

    if not data.get("is_open", False):
        return _json({
            "error": "Challenge is solution-shaped",
            "rejection_reason": data.get("rejection_reason", "No reason provided"),
            "action": "Rephrase the challenge to be more open-ended",
        })

    session_id = str(uuid.uuid4())[:8]
    session = Session(
        id=session_id,
        challenge=data.get("spark", challenge),
        domain=domain,
    )
    sessions[session_id] = session

    return _json({
        "session_id": session_id,
        "spark": session.challenge,
        "domain": domain,
        "next_step": f"Call branch(session_id='{session_id}') to generate initial branches",
    })


@mcp.tool()
async def branch(
    session_id: str,
    branches: str | dict | list | None = None,
    min_branches: int = 3,
) -> str:
    """Generate or register creative branches.

    Call without branches to get the generation prompt.
    Call with branches JSON to register them (rejects similar ones).

    Args:
        session_id: Session ID from spark
        branches: JSON of branches to register (optional)
        min_branches: Minimum branches required (default 3)

    Returns:
        Without branches: Prompt for generation
        With branches: Registration result with novelty scores
    """
    if session_id not in sessions:
        return _json({"error": f"Session '{session_id}' not found"})

    session = sessions[session_id]

    if session.harvested:
        return _json({"error": "Session already harvested. Start a new session."})

    if branches is None:
        existing = _format_branches(session.branches)
        constraint_ctx = ""
        if session.constraints:
            constraint_ctx = f"\nACTIVE CONSTRAINTS:\n{_format_constraints(session.constraints)}"

        # Fetch distant concept for orthogonal exploration
        distant_concept = get_concept_for_session(
            session.challenge,
            used_domains=session.used_concept_domains,
        )

        distant_ctx = ""
        distant_instruction = ""
        concept_info = None

        if distant_concept:
            session.used_concept_domains.append(distant_concept.domain)
            distant_ctx = f"\nDISTANT CONCEPT INJECTION:\nConcept: {distant_concept.concept}\nDomain: {distant_concept.domain}\nStructural pattern: {distant_concept.structural_pattern}"
            distant_instruction = f"""MANDATORY: At least ONE branch must STRUCTURALLY integrate the concept "{distant_concept.concept}" from {distant_concept.domain}.
Not just mention it - borrow its PATTERN or PROCESS and apply it to the challenge.
Example: If the concept is "tidal cycles", don't say "like tides" - design something with actual ebb/flow rhythms."""
            concept_info = {
                "concept": distant_concept.concept,
                "domain": distant_concept.domain,
                "pattern": distant_concept.structural_pattern,
                "distance_score": distant_concept.distance_score,
            }

        prompt = BRANCH_PROMPT.format(
            challenge=session.challenge,
            existing_branches=existing if session.branches else "(Starting fresh)",
            constraint_context=constraint_ctx,
            distant_concept_context=distant_ctx,
            distant_concept_instruction=distant_instruction,
            min_branches=min_branches,
        )

        result = {
            "action": "branch",
            "prompt": prompt,
            "existing_count": len(session.branches),
            "min_required": min_branches,
            "next_step": "Generate branches, then call branch again with 'branches' parameter",
        }

        if concept_info:
            result["injected_concept"] = concept_info

        return _json(result)

    # Parse and validate branches
    try:
        data = _normalize_json(branches)
    except ValueError as e:
        return _json({"error": str(e)})

    if isinstance(data, dict) and "branches" in data:
        branch_list = data["branches"]
    elif isinstance(data, list):
        branch_list = data
    else:
        return _json({"error": "Expected JSON array of branches or object with 'branches' key"})

    registered_count = 0

    for item in branch_list:
        if not isinstance(item, dict) or "content" not in item:
            continue

        branch_id = str(uuid.uuid4())[:6]
        new_branch = Branch(
            id=branch_id,
            content=item["content"],
            is_weird=item.get("is_weird", False),
            constraints_applied=[c.id for c in session.constraints],
        )
        session.branches.append(new_branch)
        registered_count += 1

    return _json({
        "registered": registered_count,
        "total_branches": len(session.branches),
        "weird_branch_exists": session.weird_branch_exists,
        "next_step": "Continue branching, add constraints, or check with prod()",
    })


@mcp.tool()
async def constrain(
    session_id: str,
    constraint: str,
) -> str:
    """Inject a constraint to force new creative directions.

    Args:
        session_id: Session ID from spark
        constraint: The constraint to apply

    Returns:
        Confirmation and prompt for branching under constraint
    """
    if session_id not in sessions:
        return _json({"error": f"Session '{session_id}' not found"})

    session = sessions[session_id]

    if session.harvested:
        return _json({"error": "Session already harvested."})

    constraint_id = str(uuid.uuid4())[:6]
    new_constraint = Constraint(
        id=constraint_id,
        text=constraint,
        branches_before=len(session.branches),
    )
    session.constraints.append(new_constraint)

    existing = _format_branches(session.branches)
    prompt = CONSTRAIN_PROMPT.format(
        challenge=session.challenge,
        constraint=constraint,
        existing_branches=existing,
        min_branches=2,
    )

    return _json({
        "constraint_id": constraint_id,
        "constraint": constraint,
        "total_constraints": len(session.constraints),
        "prompt": prompt,
        "next_step": "Generate new branches under this constraint using branch()",
    })


@mcp.tool()
async def weird(
    session_id: str,
    branch_data: str | dict | None = None,
) -> str:
    """Generate or register a weird branch.

    Call without branch_data to get the prompt.
    Call with branch_data to register (validates weirdness).

    Args:
        session_id: Session ID from spark
        branch_data: JSON with weird branch (optional)

    Returns:
        Without branch_data: Prompt for weird generation
        With branch_data: Registration result
    """
    if session_id not in sessions:
        return _json({"error": f"Session '{session_id}' not found"})

    session = sessions[session_id]

    if session.harvested:
        return _json({"error": "Session already harvested."})

    if branch_data is None:
        existing = _format_branches(session.branches)
        prompt = WEIRD_PROMPT.format(
            challenge=session.challenge,
            existing_branches=existing,
        )

        return _json({
            "action": "weird",
            "prompt": prompt,
            "current_weird_exists": session.weird_branch_exists,
            "next_step": "Generate a genuinely weird branch, then call weird again with 'branch_data'",
        })

    try:
        data = _normalize_json(branch_data)
    except ValueError as e:
        return _json({"error": str(e)})

    if not isinstance(data, dict):
        return _json({"error": "Result must be a JSON object"})

    branch_info = data.get("branch", data)
    if "content" not in branch_info:
        return _json({"error": "Branch must have 'content' field"})

    if not data.get("weird_enough", False):
        return _json({
            "error": "Branch not weird enough",
            "feedback": data.get("feedback", "Push harder"),
            "action": "Try again with something more surprising",
        })

    branch_id = str(uuid.uuid4())[:6]
    new_branch = Branch(
        id=branch_id,
        content=branch_info["content"],
        is_weird=True,
    )
    session.branches.append(new_branch)

    return _json({
        "registered": True,
        "branch_id": branch_id,
        "why_weird": branch_info.get("why_weird", "Not specified"),
        "total_branches": len(session.branches),
        "weird_branch_exists": True,
        "next_step": "Continue exploring or check with prod()",
    })


@mcp.tool()
async def prod(session_id: str) -> str:
    """The demanding creative director that assesses exploration quality.

    Args:
        session_id: Session ID from spark

    Returns:
        Assessment and verdict (push_harder | acceptable)
    """
    if session_id not in sessions:
        return _json({"error": f"Session '{session_id}' not found"})

    session = sessions[session_id]

    if session.harvested:
        return _json({"error": "Session already harvested."})

    branches_summary = _format_branches(session.branches)
    constraints_summary = _format_constraints(session.constraints)

    prompt = PROD_PROMPT.format(
        challenge=session.challenge,
        branch_count=session.branch_count,
        weird_exists=session.weird_branch_exists,
        min_depth=session.min_branch_depth,
        constraint_count=session.constraint_count,
        branches_summary=branches_summary,
        constraints_summary=constraints_summary,
    )

    can_harvest = session.can_harvest()

    return _json({
        "action": "prod",
        "prompt": prompt,
        "metrics": {
            "branch_count": session.branch_count,
            "min_required": 5,
            "weird_branch_exists": session.weird_branch_exists,
            "min_branch_depth": session.min_branch_depth,
            "depth_required": 2,
            "constraint_count": session.constraint_count,
            "constraints_required": 1,
        },
        "can_harvest": can_harvest,
        "next_step": "Evaluate and provide verdict via prod_verdict()" if can_harvest else "Metrics not met - continue exploring",
    })


@mcp.tool()
async def prod_verdict(
    session_id: str,
    verdict: str,
    directive: str | dict | None = None,
) -> str:
    """Register PROD's verdict on the exploration.

    Args:
        session_id: Session ID
        verdict: push_harder | constrain_more | go_weirder | go_deeper | acceptable
        directive: Optional directive for next action

    Returns:
        Confirmation and next steps
    """
    if session_id not in sessions:
        return _json({"error": f"Session '{session_id}' not found"})

    session = sessions[session_id]

    valid_verdicts = ["push_harder", "constrain_more", "go_weirder", "go_deeper", "acceptable"]
    if verdict not in valid_verdicts:
        return _json({"error": f"Invalid verdict. Must be one of: {valid_verdicts}"})

    if verdict == "acceptable" and not session.can_harvest():
        return _json({
            "error": "Cannot accept - harvest conditions not met",
            "missing": {
                "branches": session.branch_count < 5,
                "weird": not session.weird_branch_exists,
                "depth": session.min_branch_depth < 2,
                "constraints": session.constraint_count < 1,
            },
        })

    if verdict == "acceptable":
        return _json({
            "verdict": "acceptable",
            "can_harvest": True,
            "next_step": f"Call harvest(session_id='{session_id}') to collect branches",
        })

    directive_text = ""
    if directive:
        if isinstance(directive, dict):
            directive_text = directive.get("push", directive.get("action", ""))
        else:
            directive_text = str(directive)

    next_actions = {
        "push_harder": f"Call branch(session_id='{session_id}') with more diverse ideas",
        "constrain_more": f"Call constrain(session_id='{session_id}', constraint='...')",
        "go_weirder": f"Call weird(session_id='{session_id}')",
        "go_deeper": f"Call revisit(session_id='{session_id}', branch_id='...')",
    }

    return _json({
        "verdict": verdict,
        "directive": directive_text,
        "next_step": next_actions.get(verdict, "Continue exploring"),
    })


@mcp.tool()
async def prune(
    session_id: str,
    prune_targets: str | list | None = None,
) -> str:
    """Prune branches with FATAL flaws only.

    Call without prune_targets to get prompt with current branches.
    Call with prune_targets to evaluate pruning requests.

    Args:
        session_id: Session ID
        prune_targets: List of {branch_id, fatal_flaw} to evaluate

    Returns:
        Evaluation results - only truly fatal flaws are pruned
    """
    if session_id not in sessions:
        return _json({"error": f"Session '{session_id}' not found"})

    session = sessions[session_id]

    if session.harvested:
        return _json({"error": "Session already harvested."})

    if prune_targets is None:
        branches = _format_branches(session.branches)
        return _json({
            "action": "prune",
            "branches": branches,
            "prompt": PRUNE_PROMPT.format(
                challenge=session.challenge,
                prune_targets="[Specify branches to prune with fatal_flaw reason]",
            ),
            "next_step": "Identify branches with FATAL flaws, then call prune with prune_targets",
        })

    try:
        data = _normalize_json(prune_targets)
    except ValueError as e:
        return _json({"error": str(e)})

    if isinstance(data, dict) and "evaluations" in data:
        evaluations = data["evaluations"]
    elif isinstance(data, list):
        evaluations = data
    else:
        return _json({"error": "Expected list of evaluations"})

    pruned = []
    rejected_prunes = []

    for eval_item in evaluations:
        branch_id = eval_item.get("branch_id")
        fatal_flaw = eval_item.get("fatal_flaw", "")
        actually_fatal = eval_item.get("actually_fatal", False)

        branch = session.get_branch(branch_id)
        if not branch:
            continue

        record = PruneRecord(
            branch_id=branch_id,
            fatal_flaw=fatal_flaw,
            rejected=not actually_fatal,
            rejection_reason=eval_item.get("rejection_reason"),
        )
        session.pruned.append(record)

        if actually_fatal:
            session.branches = [b for b in session.branches if b.id != branch_id]
            pruned.append({"branch_id": branch_id, "fatal_flaw": fatal_flaw})
        else:
            rejected_prunes.append({
                "branch_id": branch_id,
                "claimed_flaw": fatal_flaw,
                "rejection_reason": record.rejection_reason or "Not actually fatal",
            })

    return _json({
        "pruned": pruned,
        "rejected_prunes": rejected_prunes,
        "remaining_branches": len(session.branches),
        "next_step": "Continue exploring or check with prod()",
    })


@mcp.tool()
async def harvest(
    session_id: str,
    force: bool = False,
) -> str:
    """Collect viable branches from the exploration.

    BLOCKED until prod() returns verdict: acceptable (unless force=True).

    Args:
        session_id: Session ID
        force: Override blocking (logs premature termination)

    Returns:
        All viable branches for user selection
    """
    if session_id not in sessions:
        return _json({"error": f"Session '{session_id}' not found"})

    session = sessions[session_id]

    if session.harvested:
        return _json({"error": "Session already harvested."})

    if not session.can_harvest() and not force:
        return _json({
            "error": "Cannot harvest - conditions not met",
            "missing": {
                "branches": f"{session.branch_count}/5 required",
                "weird": "missing" if not session.weird_branch_exists else "present",
                "depth": f"{session.min_branch_depth}/2 required",
                "constraints": f"{session.constraint_count}/1 required",
            },
            "action": "Continue exploring or use force=True to override",
        })

    session.harvested = True

    active = session.active_branches
    branches_data = [b.to_dict() for b in active]

    result = {
        "session_complete": True,
        "branches": branches_data,
        "archived_branches": [b.to_dict() for b in session.branches if b.archived],
        "summary": {
            "active_branches": len(active),
            "archived_branches": len(session.branches) - len(active),
            "weird_branches": sum(1 for b in active if b.is_weird),
            "constraints_applied": len(session.constraints),
            "branches_pruned": len([p for p in session.pruned if not p.rejected]),
        },
    }

    if force and not session.can_harvest():
        result["warning"] = "Premature termination - exploration incomplete"
        result["missing_at_termination"] = {
            "branches": session.branch_count < 5,
            "weird": not session.weird_branch_exists,
            "depth": session.min_branch_depth < 2,
            "constraints": session.constraint_count < 1,
        }

    return _json(result)


@mcp.tool()
async def revisit(
    session_id: str,
    branch_id: str,
) -> str:
    """Revisit a branch to explore it deeper.

    Args:
        session_id: Session ID
        branch_id: ID of branch to revisit

    Returns:
        Prompt for deeper exploration
    """
    if session_id not in sessions:
        return _json({"error": f"Session '{session_id}' not found"})

    session = sessions[session_id]
    branch = session.get_branch(branch_id)

    if not branch:
        return _json({
            "error": f"Branch '{branch_id}' not found",
            "available": [b.id for b in session.branches],
        })

    if branch.archived:
        return _json({"error": f"Branch '{branch_id}' is archived. Steer to unarchive first."})

    prompt = REVISIT_PROMPT.format(
        challenge=session.challenge,
        branch_content=branch.content,
        current_depth=branch.depth,
    )

    return _json({
        "action": "revisit",
        "branch_id": branch_id,
        "current_depth": branch.depth,
        "prompt": prompt,
        "next_step": f"Explore deeper, then call revisit_register(session_id='{session_id}', branch_id='{branch_id}', result=...)",
    })


@mcp.tool()
async def revisit_register(
    session_id: str,
    branch_id: str,
    result: str | dict,
) -> str:
    """Register the result of revisiting a branch.

    Args:
        session_id: Session ID
        branch_id: Branch that was revisited
        result: JSON with deeper_exploration, sub_branches, new_depth

    Returns:
        Confirmation with updated depth
    """
    if session_id not in sessions:
        return _json({"error": f"Session '{session_id}' not found"})

    session = sessions[session_id]
    branch = session.get_branch(branch_id)

    if not branch:
        return _json({"error": f"Branch '{branch_id}' not found"})

    try:
        data = _normalize_json(result)
    except ValueError as e:
        return _json({"error": str(e)})

    if not isinstance(data, dict):
        return _json({"error": "Result must be a JSON object"})

    # Server controls depth - increment by 1, ignore Claude's claimed value
    branch.depth = branch.depth + 1

    # Register any sub-branches
    sub_branches = data.get("sub_branches", [])
    sub_count = 0

    for sub in sub_branches:
        if not isinstance(sub, dict) or "content" not in sub:
            continue

        sub_id = str(uuid.uuid4())[:6]
        new_branch = Branch(
            id=sub_id,
            content=sub["content"],
            is_weird=sub.get("is_weird", False),
            parent_id=branch_id,
            depth=branch.depth,
        )
        session.branches.append(new_branch)
        sub_count += 1

    return _json({
        "branch_id": branch_id,
        "new_depth": branch.depth,
        "sub_branches_registered": sub_count,
        "total_branches": len(session.branches),
        "min_branch_depth": session.min_branch_depth,
    })


@mcp.tool()
async def mutate(
    session_id: str,
    branch_id: str,
    mutation_type: str = "element",
) -> str:
    """Mutate an existing branch to create a variation.

    Args:
        session_id: Session ID
        branch_id: Branch to mutate
        mutation_type: element | audience | scale | opposite

    Returns:
        Prompt for mutation
    """
    if session_id not in sessions:
        return _json({"error": f"Session '{session_id}' not found"})

    session = sessions[session_id]
    branch = session.get_branch(branch_id)

    if not branch:
        return _json({
            "error": f"Branch '{branch_id}' not found",
            "available": [b.id for b in session.branches],
        })

    valid_types = ["element", "audience", "scale", "opposite"]
    if mutation_type not in valid_types:
        return _json({"error": f"Invalid mutation_type. Must be one of: {valid_types}"})

    prompt = MUTATE_PROMPT.format(
        branch_content=branch.content,
        mutation_type=mutation_type,
    )

    return _json({
        "action": "mutate",
        "branch_id": branch_id,
        "mutation_type": mutation_type,
        "prompt": prompt,
        "next_step": f"Generate mutation, then call mutate_register(session_id='{session_id}', branch_id='{branch_id}', result=...)",
    })


@mcp.tool()
async def mutate_register(
    session_id: str,
    branch_id: str,
    result: str | dict,
) -> str:
    """Register a mutation result as a new branch.

    Args:
        session_id: Session ID
        branch_id: Original branch
        result: JSON with mutation content

    Returns:
        Confirmation with new branch ID
    """
    if session_id not in sessions:
        return _json({"error": f"Session '{session_id}' not found"})

    session = sessions[session_id]

    try:
        data = _normalize_json(result)
    except ValueError as e:
        return _json({"error": str(e)})

    if not isinstance(data, dict):
        return _json({"error": "Result must be a JSON object"})

    mutation = data.get("mutation", data)
    if not isinstance(mutation, dict) or "content" not in mutation:
        return _json({"error": "Mutation must have 'content' field"})

    new_id = str(uuid.uuid4())[:6]
    new_branch = Branch(
        id=new_id,
        content=mutation["content"],
        is_weird=mutation.get("is_weird", False),
        parent_id=branch_id,
    )
    session.branches.append(new_branch)

    return _json({
        "registered": True,
        "new_branch_id": new_id,
        "parent_branch_id": branch_id,
        "delta": data.get("delta", "Not specified"),
        "total_branches": len(session.branches),
    })


@mcp.tool()
async def get_session_state(session_id: str) -> str:
    """Get current state of a creativity session.

    Args:
        session_id: Session ID from spark

    Returns:
        Session state including branches, constraints, and metrics
    """
    if session_id not in sessions:
        return _json({"error": f"Session '{session_id}' not found"})

    session = sessions[session_id]

    return _json({
        "session_id": session_id,
        "challenge": session.challenge,
        "domain": session.domain,
        "branches": [b.to_dict() for b in session.branches],
        "constraints": [c.to_dict() for c in session.constraints],
        "metrics": {
            "branch_count": session.branch_count,
            "total_branch_count": session.total_branch_count,
            "weird_branch_exists": session.weird_branch_exists,
            "min_branch_depth": session.min_branch_depth,
            "constraint_count": session.constraint_count,
        },
        "can_harvest": session.can_harvest(),
        "harvested": session.harvested,
    })


@mcp.tool()
async def steer(
    session_id: str,
    direction: str,
    branch_ids: list[str] | None = None,
    archive_others: bool = False,
) -> str:
    """Steer the exploration by tagging branches with lanes and optionally archiving others.

    Args:
        session_id: Session ID from spark
        direction: Lane name to tag branches with
        branch_ids: Specific branch IDs to tag (if None, tags all untagged branches)
        archive_others: If True, archive branches with a different lane

    Returns:
        JSON summary of tagged, archived, and active counts
    """
    if session_id not in sessions:
        return _json({"error": f"Session '{session_id}' not found"})

    session = sessions[session_id]

    if session.harvested:
        return _json({"error": "Session already harvested."})

    tagged = 0
    archived = 0

    if branch_ids is not None:
        for b in session.branches:
            if b.id in branch_ids:
                b.lane = direction
                tagged += 1
    else:
        for b in session.branches:
            if b.lane is None:
                b.lane = direction
                tagged += 1

    if archive_others:
        for b in session.branches:
            if b.lane is not None and b.lane != direction and not b.archived:
                b.archived = True
                archived += 1

    active_remaining = len(session.active_branches)

    return _json({
        "tagged": tagged,
        "archived": archived,
        "active_remaining": active_remaining,
    })


@mcp.tool()
async def explore(
    challenge: str,
    domain: str | None = None,
    intensity: str = "standard",
) -> str:
    """Run a full automated creative exploration.

    Executes the complete explore loop: spark, multi-lens branching,
    weird generation, deepening, and assessment — all in one call.

    Args:
        challenge: The creative challenge to explore
        domain: Optional domain context
        intensity: quick (1 loop, 2 lenses) | standard (2 loops, 4 lenses) | deep (3 loops, 4 lenses)

    Returns:
        JSON with session_id, branches, and exploration summary
    """
    from creativity_mcp.explorer import run_exploration

    result = await run_exploration(challenge, domain, intensity, sessions=sessions)
    return _json(result)


@mcp.tool()
async def explore_more(
    session_id: str,
    directive: str,
) -> str:
    """Extend an existing exploration with more branches.

    Args:
        session_id: Session ID from a previous explore() call
        directive: What direction to explore further

    Returns:
        JSON with new branches added to the session
    """
    from creativity_mcp.explorer import extend_exploration

    if session_id not in sessions:
        return _json({"error": f"Session '{session_id}' not found"})

    result = await extend_exploration(session_id, directive, sessions=sessions)
    return _json(result)
