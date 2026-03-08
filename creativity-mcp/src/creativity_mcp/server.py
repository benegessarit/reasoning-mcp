"""Creativity MCP server — automated creative exploration via LLM calls."""
import json

from mcp.server.fastmcp import FastMCP

from creativity_mcp.models import Session

mcp = FastMCP("creativity_mcp")
sessions: dict[str, Session] = {}


def _json(obj: dict) -> str:
    return json.dumps(obj, indent=2)


@mcp.tool()
async def explore(
    challenge: str,
    domain: str | None = None,
    intensity: str = "standard",
    context: str | None = None,
    output_file: str | None = None,
) -> str:
    """Run a full automated creative exploration.

    Executes the complete explore loop: spark, multi-lens branching,
    weird generation, deepening, and assessment — all in one call.

    Args:
        challenge: The creative challenge to explore
        domain: Optional domain context
        intensity: quick (1 loop, 2 lenses) | standard (2 loops, 4 lenses) | deep (3 loops, 4 lenses)
        context: Free-text background context injected into all LLM prompts (1-3 paragraphs recommended)
        output_file: If set, write full branch JSON to this path and return summary-only

    Returns:
        JSON with session_id, branches, and exploration summary
    """
    from creativity_mcp.explorer import run_exploration

    result = await run_exploration(
        challenge, domain, intensity, context=context, output_file=output_file,
        sessions=sessions,
    )
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


@mcp.tool()
async def get_session_state(session_id: str) -> str:
    """Get current state of a creativity session.

    Args:
        session_id: Session ID from explore()

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
        "summary": {
            "branch_count": len(session.active_branches),
            "weird_branches": sum(1 for b in session.branches if b.is_weird),
            "max_depth": max((b.depth for b in session.branches), default=1),
            "constraints_applied": len(session.constraints),
        },
        "harvested": session.harvested,
    })
