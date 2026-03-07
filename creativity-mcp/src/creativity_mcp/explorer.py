"""State machine orchestrator for explore() — automated creative exploration."""
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


async def run_exploration(
    challenge: str,
    domain: str | None = None,
    intensity: str = "standard",
    *,
    sessions: dict[str, Session],
) -> dict:
    """Run a full creative exploration loop.

    Returns dict with session_id, branches, and summary.
    """
    max_loops, parallel_count = IntensityConfig.get(intensity, IntensityConfig["standard"])

    # INIT
    session_id = str(uuid.uuid4())[:8]
    session = Session(id=session_id, challenge=challenge, domain=domain)
    sessions[session_id] = session

    # SPARK
    domain_ctx = f"\nDOMAIN: {domain}" if domain else ""
    spark_raw = await acall(
        FLASH_MODEL,
        SPARK_INTERNAL_PROMPT.format(challenge=challenge, domain=domain_ctx),
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
            )
            for k in selected_keys
        ]

        # Call lenses in parallel
        results = await acall_batch(FLASH_MODEL, prompts)

        new_count_before = len(session.branches)

        for raw in results:
            try:
                parsed = extract_json(raw)
            except Exception:
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
                    constraints_applied=[c.id for c in session.constraints],
                ))

        new_unique = len(session.branches) - new_count_before

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
        except Exception:
            pass

    # DEEPEN: top 2-3 branches
    active = session.active_branches
    deepen_targets = active[:3] if len(active) >= 3 else active
    if deepen_targets:
        revisit_prompts = [
            REVISIT_INTERNAL_PROMPT.format(
                challenge=session.challenge,
                branch_content=b.content,
            )
            for b in deepen_targets
        ]
        deepen_results = await acall_batch(FLASH_MODEL, revisit_prompts)

        for i, raw in enumerate(deepen_results):
            if i >= len(deepen_targets):
                break
            target = deepen_targets[i]
            try:
                parsed = extract_json(raw)
            except Exception:
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
        ),
    )
    try:
        assess_data = extract_json(assess_raw)
        verdict = assess_data.get("verdict", "acceptable")
    except Exception:
        verdict = "acceptable"

    if verdict == "push_harder" and loop_count < max_loops:
        # One more diversify round
        existing_text = _format_branches_for_prompt(session.branches)
        constraints_text = _format_constraints_for_prompt(session.constraints)
        extra_prompts = [
            LENS_PROMPTS[k].format(
                challenge=session.challenge,
                existing_branches=existing_text,
                constraints=constraints_text,
            )
            for k in list(LENS_PROMPTS.keys())[:parallel_count]
        ]
        extra_results = await acall_batch(FLASH_MODEL, extra_prompts)
        for raw in extra_results:
            try:
                parsed = extract_json(raw)
            except Exception:
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
                ))

    # HARVEST
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
        )
        for k in lens_keys
    ]

    results = await acall_batch(FLASH_MODEL, prompts)

    for raw in results:
        try:
            parsed = extract_json(raw)
        except Exception:
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
            ))

    return {
        "session_id": session_id,
        "branches_added": len(session.branches) - initial_count,
        "directive": directive,
    }
