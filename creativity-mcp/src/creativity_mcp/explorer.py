"""State machine orchestrator for explore() — automated creative exploration."""
import asyncio
import json
import logging
import os
import uuid

from creativity_mcp.explore_prompts import (
    LENS_PROMPTS,
    PROD_INTERNAL_PROMPT,
    REVISIT_INTERNAL_PROMPT,
    SPARK_INTERNAL_PROMPT,
    WEIRD_INTERNAL_PROMPT,
)
from creativity_mcp.llm import FLASH_MODEL, SONNET_MODEL, acall, acall_batch, extract_json
from creativity_mcp.models import Branch, Constraint, Session

logger = logging.getLogger(__name__)

IntensityConfig: dict[str, tuple[int, int]] = {
    "quick": (1, 2),
    "standard": (2, 4),
    "deep": (3, 4),
}

SYNTHETIC_CONSTRAINTS = [
    "What if this had to work with zero budget?",
    "What if the solution had to be invisible to users?",
    "What if this had to be completed in 24 hours?",
    "What if the target audience were children under 5?",
    "What if this could only use technology from the 1990s?",
]


def _deduplicate_branches(
    new: list[dict], existing: list[Branch]
) -> list[dict]:
    """Reject new branches that overlap >50% with existing (20-word window)."""
    existing_word_sets = [set(b.content.lower().split()[:20]) for b in existing]
    kept = []
    for item in new:
        new_words = set(item.get("content", "").lower().split()[:20])
        if not new_words:
            continue
        is_dup = False
        for ew in existing_word_sets:
            if not ew:
                continue
            overlap = len(new_words & ew) / max(len(new_words), len(ew))
            if overlap > 0.5:
                is_dup = True
                break
        if not is_dup:
            kept.append(item)
            existing_word_sets.append(new_words)
    return kept


def _pick_constraint(session: Session) -> str:
    """Pick a synthetic constraint not yet used in this session."""
    used_texts = {c.text for c in session.constraints}
    for c in SYNTHETIC_CONSTRAINTS:
        if c not in used_texts:
            return c
    return SYNTHETIC_CONSTRAINTS[0]


def _format_branches_for_prompt(branches: list[Branch]) -> str:
    if not branches:
        return "(No branches yet)"
    lines = []
    for b in branches:
        weird = " [WEIRD]" if b.is_weird else ""
        lines.append(f"- {weird}{b.content}")
    return "\n".join(lines)


def _format_constraints_for_prompt(constraints: list[Constraint]) -> str:
    if not constraints:
        return "(None)"
    return "\n".join(f"- {c.text}" for c in constraints)


def _format_context_block(context: str | None) -> str:
    """Format context as a block for prompt injection. Returns '' if no context."""
    if context:
        return f"\nCONTEXT:\n{context}"
    return ""


def _ingest_branches(
    raw_results: list[str],
    session: Session,
    constraints_applied: list[str] | None = None,
) -> int:
    """Parse LLM results, dedup, append to session. Returns count added."""
    added = 0
    for raw in raw_results:
        try:
            parsed = extract_json(raw)
        except (json.JSONDecodeError, ValueError) as exc:
            logger.warning("Failed to parse branch response: %s", exc)
            continue
        if isinstance(parsed, dict) and "branches" in parsed:
            branch_list = parsed["branches"]
        elif isinstance(parsed, list):
            branch_list = parsed
        else:
            continue

        unique = _deduplicate_branches(branch_list, session.branches)
        for item in unique:
            if not isinstance(item, dict) or "content" not in item:
                continue
            bid = str(uuid.uuid4())[:6]
            session.branches.append(Branch(
                id=bid,
                content=item["content"],
                is_weird=item.get("is_weird", False),
                constraints_applied=constraints_applied or [],
            ))
            added += 1
    return added


async def run_exploration(
    challenge: str,
    domain: str | None = None,
    intensity: str = "standard",
    context: str | None = None,
    output_file: str | None = None,
    *,
    sessions: dict[str, Session],
) -> dict:
    """Run a full creative exploration loop.

    Args:
        context: Free-text background context injected into all LLM prompts.
        output_file: If set, write full branch JSON to this path and return summary-only.

    Returns dict with session_id, branches, and summary.
    """
    max_loops, parallel_count = IntensityConfig.get(intensity, IntensityConfig["standard"])

    # INIT
    session_id = str(uuid.uuid4())[:8]
    session = Session(id=session_id, challenge=challenge, domain=domain)

    try:
        result = await _run_exploration_inner(
            session, sessions, max_loops, parallel_count, challenge, domain, context,
        )
    except Exception:
        sessions.pop(session_id, None)
        raise

    if output_file:
        try:
            tmp_path = output_file + ".tmp"
            with open(tmp_path, "w") as f:
                json.dump(result, f, indent=2)
            os.rename(tmp_path, output_file)
            return {
                "session_id": result["session_id"],
                "challenge": result["challenge"],
                "branch_count": len(result["branches"]),
                "output_file": output_file,
                "summary": result["summary"],
            }
        except OSError as exc:
            logger.warning("Failed to write output file %s: %s", output_file, exc)

    return result


async def _run_exploration_inner(
    session: Session,
    sessions: dict[str, Session],
    max_loops: int,
    parallel_count: int,
    challenge: str,
    domain: str | None,
    context: str | None = None,
) -> dict:
    """Inner exploration loop. Session is published only on success."""
    session_id = session.id
    sessions[session_id] = session
    context_block = _format_context_block(context)

    # SPARK
    domain_ctx = f"\nDOMAIN: {domain}" if domain else ""
    spark_raw = await acall(
        FLASH_MODEL,
        SPARK_INTERNAL_PROMPT.format(
            challenge=challenge, domain=domain_ctx, context_block=context_block,
        ),
    )
    spark_data = extract_json(spark_raw)
    session.challenge = spark_data.get("challenge", challenge)

    # DIVERSIFY loop
    loop_count = 0
    while loop_count < max_loops:
        # First iteration: inject synthetic constraint
        if loop_count == 0:
            constraint_text = _pick_constraint(session)
            constraint_id = str(uuid.uuid4())[:6]
            session.constraints.append(Constraint(
                id=constraint_id,
                text=constraint_text,
                branches_before=len(session.branches),
            ))

        # Pick lens prompts
        lens_keys = list(LENS_PROMPTS.keys())
        selected_keys = lens_keys[:parallel_count]

        existing_text = _format_branches_for_prompt(session.branches)
        constraints_text = _format_constraints_for_prompt(session.constraints)

        prompts = [
            LENS_PROMPTS[k].format(
                challenge=session.challenge,
                existing_branches=existing_text,
                constraints=constraints_text,
                context_block=context_block,
            )
            for k in selected_keys
        ]

        results = await acall_batch(FLASH_MODEL, prompts)
        constraint_ids = [c.id for c in session.constraints]

        before = len(session.branches)
        _ingest_branches(results, session, constraints_applied=constraint_ids)
        new_unique = len(session.branches) - before

        # Saturation check
        if new_unique < 2:
            break

        loop_count += 1

    # WEIRD gate
    if not session.weird_branch_exists:
        existing_text = _format_branches_for_prompt(session.branches)
        weird_raw = await acall(
            FLASH_MODEL,
            WEIRD_INTERNAL_PROMPT.format(
                challenge=session.challenge,
                existing_branches=existing_text,
                context_block=context_block,
            ),
        )
        try:
            weird_data = extract_json(weird_raw)
            if isinstance(weird_data, dict) and "content" in weird_data:
                bid = str(uuid.uuid4())[:6]
                session.branches.append(Branch(
                    id=bid,
                    content=weird_data["content"],
                    is_weird=True,
                ))
        except (json.JSONDecodeError, ValueError) as exc:
            logger.warning("Failed to parse weird branch response: %s", exc)

    # DEEPEN: top 2-3 branches (index-aligned gather for correct pairing)
    active = session.active_branches
    deepen_targets = active[:3] if len(active) >= 3 else active
    if deepen_targets:
        revisit_prompts = [
            REVISIT_INTERNAL_PROMPT.format(
                challenge=session.challenge,
                branch_content=b.content,
                context_block=context_block,
            )
            for b in deepen_targets
        ]
        # Use gather directly to preserve index alignment
        raw_results = await asyncio.gather(
            *[acall(FLASH_MODEL, p) for p in revisit_prompts],
            return_exceptions=True,
        )

        for i, raw in enumerate(raw_results):
            if isinstance(raw, BaseException):
                logger.warning("Deepen call %d failed: %s", i, raw)
                continue
            target = deepen_targets[i]
            try:
                parsed = extract_json(raw)
            except (json.JSONDecodeError, ValueError) as exc:
                logger.warning("Failed to parse deepen response %d: %s", i, exc)
                continue
            if not isinstance(parsed, dict):
                continue

            target.depth += 1

            for sub in parsed.get("sub_branches", []):
                if not isinstance(sub, dict) or "content" not in sub:
                    continue
                sid = str(uuid.uuid4())[:6]
                session.branches.append(Branch(
                    id=sid,
                    content=sub["content"],
                    is_weird=sub.get("is_weird", False),
                    parent_id=target.id,
                    depth=target.depth,
                ))

    # ASSESS
    branches_summary = _format_branches_for_prompt(session.branches)
    assess_raw = await acall(
        SONNET_MODEL,
        PROD_INTERNAL_PROMPT.format(
            challenge=session.challenge,
            branches_summary=branches_summary,
            context_block=context_block,
        ),
    )
    assess_data = {}
    try:
        assess_data = extract_json(assess_raw)
        verdict = assess_data.get("verdict", "acceptable")
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning("Failed to parse assessment: %s", exc)
        verdict = "acceptable"

    if verdict == "push_harder" and loop_count < max_loops:
        # Inject assessor directive as constraint
        directive = assess_data.get("directive", "")
        if directive:
            cid = str(uuid.uuid4())[:6]
            session.constraints.append(Constraint(
                id=cid,
                text=directive,
                branches_before=len(session.branches),
            ))

        existing_text = _format_branches_for_prompt(session.branches)
        constraints_text = _format_constraints_for_prompt(session.constraints)
        extra_prompts = [
            LENS_PROMPTS[k].format(
                challenge=session.challenge,
                existing_branches=existing_text,
                constraints=constraints_text,
                context_block=context_block,
            )
            for k in list(LENS_PROMPTS.keys())[:parallel_count]
        ]
        extra_results = await acall_batch(FLASH_MODEL, extra_prompts)
        constraint_ids = [c.id for c in session.constraints]
        _ingest_branches(extra_results, session, constraints_applied=constraint_ids)

    # HARVEST — guard against empty session
    if not session.branches:
        raise RuntimeError(
            f"Exploration produced no branches for challenge: {challenge!r}"
        )

    session.harvested = True

    active = session.active_branches
    return {
        "session_id": session_id,
        "challenge": session.challenge,
        "branches": [b.to_dict() for b in active],
        "summary": {
            "total_branches": len(active),
            "weird_branches": sum(1 for b in active if b.is_weird),
            "constraints_applied": len(session.constraints),
            "max_depth": max((b.depth for b in active), default=1),
        },
    }


async def extend_exploration(
    session_id: str,
    directive: str,
    *,
    sessions: dict[str, Session],
) -> dict:
    """Add more branches to an existing session based on a directive."""
    if session_id not in sessions:
        raise KeyError(f"Session '{session_id}' not found")

    session = sessions[session_id]

    # Un-harvest if extending a completed session
    if session.harvested:
        session.harvested = False

    # Inject directive as constraint
    constraint_id = str(uuid.uuid4())[:6]
    session.constraints.append(Constraint(
        id=constraint_id,
        text=directive,
        branches_before=len(session.branches),
    ))

    initial_count = len(session.branches)

    existing_text = _format_branches_for_prompt(session.branches)
    constraints_text = _format_constraints_for_prompt(session.constraints)

    # Use 2 lenses to extend, incorporating directive
    lens_keys = list(LENS_PROMPTS.keys())[:2]
    prompts = [
        LENS_PROMPTS[k].format(
            challenge=f"{session.challenge}\n\nDIRECTIVE: {directive}",
            existing_branches=existing_text,
            constraints=constraints_text,
            context_block="",
        )
        for k in lens_keys
    ]

    results = await acall_batch(FLASH_MODEL, prompts)
    constraint_ids = [c.id for c in session.constraints]
    _ingest_branches(results, session, constraints_applied=constraint_ids)

    return {
        "session_id": session_id,
        "branches_added": len(session.branches) - initial_count,
        "directive": directive,
    }
