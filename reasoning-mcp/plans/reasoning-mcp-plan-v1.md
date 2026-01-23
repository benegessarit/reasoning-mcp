# Plan: Reasoning MCP

## Original Goal

> "Force Claude to take discrete thinking steps via tool calls AND build distributable thinking workflow for others"

## Discovery Summary

| Source | Finding |
|--------|---------|
| `skills/compose-thinking/SKILL.md:8` | 5 modes: divergent, sequential, adversarial, branching, checkpoint |
| `skills/compose-thinking/SKILL.md:8` | Named phases: WILD_OPTIONS, HYPOTHESES, ANTIREZ_TEST, PREMORTEM, etc. |
| `skills/developing-mcp-servers/reference/python_mcp_server.md:436-446` | FastMCP tool pattern with annotations |
| `hooks/promptsubmit/think_composer.py:307-313` | Mode hint mapping exists (divergent→"generate multiple options") |
| Prior conversation | Three-layer model: stance/relation/tactic grounded in Lean tactics, DSPy signatures |

## Requirements

**Problem:** Current compose-thinking skill fails in 4 ways:
1. Claude compresses phases into one response (no discrete steps)
2. Branching is fake (explored superficially, not via separate tool calls)
3. Mode signatures ignored (no enforcement)
4. Can't share with others (local skill only)

**Success Criteria:**
- [ ] Claude makes multiple tool calls per complex question (discrete steps enforced)
- [ ] Installable via `claude mcp add reasoning-mcp` or equivalent
- [ ] Tactic-specific outputs match signatures (ANTIREZ_TEST → can_delete, two_use_cases, simplest_solution, verdict)

**Scope:**

| IN | OUT |
|----|-----|
| Single `think` tool with stance/relation/tactic | Multi-tool design (5+ tools) |
| All 19 compose-thinking tactics | Custom user-defined tactics |
| In-memory session state | Persistent state across restarts |
| FastMCP Python implementation (TS port ~4hrs if needed) | TypeScript-first |
| Standard MCP distribution | Custom installation |

## Risk Analysis

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Claude ignores tactic signatures | HIGH | Return structured prompts with required output fields; include `guidance` field |
| Session state lost | MEDIUM | Auto-generate session_id; document that restarts clear sessions |
| Too many parameters confuse Claude | MEDIUM | Tactic implies defaults; only stance+content required |
| 19 tactics overwhelming | LOW | Group by style; META_ANALYSIS always first; let Claude pick based on context |

## Architecture

### Three-Layer Model (grounded in CS theory)

```
Layer 1: Stance (required)
├── expand   → Generate options, no filtering
├── refine   → Build on/critique existing thoughts
└── commit   → Make decision, verify, conclude

Layer 2: Relation (optional)
├── builds   → Extends prior thought
├── revises  → Corrects prior thought
├── forks    → Explores alternative path
├── attacks  → Challenges/stress-tests
├── synthesizes → Combines multiple thoughts
└── concludes → Final decision

Layer 3: Tactic (optional - 19 total, grouped by style)
├── divergent: META_ANALYSIS, WILD_OPTIONS, HYPOTHESES, ALTERNATIVES, INVERSION, PRIOR_ART
├── sequential: EVIDENCE_AUDIT, COMPLEXITY_INVENTORY, STEEL_MAN_OPPOSITE, GAP_ANALYSIS, CONTRADICTION, META_AUDIT
├── adversarial: PREMORTEM, FAILURE_MODES
├── branching: BRANCH_EXPLORE
└── checkpoint: ANTIREZ_TEST, VERDICT, PICK, NEXT_ACTION
```

**WHY this structure:**
- Maps to Lean/Coq tactics (named procedures that transform goal state)
- Tactics carry defaults (ANTIREZ_TEST implies stance=commit)
- Extensible without changing tool signature

### Tool Signature

```python
@mcp.tool()
async def think(
    stance: Literal["expand", "refine", "commit"],  # Required
    content: str,  # Required - the actual thought
    relation: str | None = None,  # builds, revises, forks, attacks, synthesizes, concludes
    targets: list[int] | None = None,  # Thought numbers being referenced
    tactic: str | None = None,  # ANTIREZ_TEST, PREMORTEM, etc.
    session_id: str | None = None,  # Auto-generated if not provided
    next_needed: bool = True,  # Signal more thinking needed
) -> ThinkResult
```

**WHY single tool:**
- Sequential-thinking MCP uses 1 tool successfully (77k stars)
- Fewer tools = less confusion
- Parameters provide sufficient routing

### Tactic Registry (All 19)

| Tactic | Style | Default Stance | Outputs | Guidance |
|--------|-------|----------------|---------|----------|
| **META_ANALYSIS** | special | expand | surface_ask, real_need, unstated_context, failure_modes, optimal_response | "What did they literally ask? What do they actually need?" |
| **WILD_OPTIONS** | divergent | expand | options[], weird_one | "Generate freely. No filtering. Quantity over quality." |
| **HYPOTHESES** | divergent | expand | hypotheses[], testable_predictions | "What could explain this? How would we test each?" |
| **ALTERNATIVES** | divergent | expand | alternatives[], dismissed_why | "What else could work? Why might we reject the obvious?" |
| **INVERSION** | divergent | expand | inverted_goal, insights | "What if we wanted the opposite? What does that reveal?" |
| **PRIOR_ART** | divergent | expand | examples[], patterns, gaps | "Who's solved this before? What can we steal?" |
| **EVIDENCE_AUDIT** | sequential | refine | claims[], evidence[], gaps[], verdict | "What's claimed? What's the evidence? What's missing?" |
| **COMPLEXITY_INVENTORY** | sequential | refine | components[], dependencies[], hotspots | "What are all the pieces? What depends on what?" |
| **STEEL_MAN_OPPOSITE** | sequential | refine | strongest_counter, why_they_believe, what_flips_me | "What's the best argument against?" |
| **GAP_ANALYSIS** | sequential | refine | current_state, desired_state, gaps[], bridge_actions | "Where are we? Where do we want to be?" |
| **CONTRADICTION** | sequential | refine | claim_a, claim_b, resolution, revised_model | "These two things seem incompatible. How do we reconcile?" |
| **META_AUDIT** | sequential | refine | process_used, blind_spots, what_id_do_differently | "How did I think about this? What did I miss?" |
| **PREMORTEM** | adversarial | refine | future_state, failure, cause, prevent | "It's 6 months later. This failed. What happened?" |
| **FAILURE_MODES** | adversarial | refine | failure_modes[], likelihood, impact, mitigations | "How could this break? What's the blast radius?" |
| **BRANCH_EXPLORE** | branching | expand | fork_point, paths[], converge_when | "What decision splits the future? Explore each path." |
| **ANTIREZ_TEST** | checkpoint | commit | can_delete, two_use_cases, simplest_solution, verdict | "Can I delete instead? 2 real use cases?" |
| **VERDICT** | checkpoint | commit | verify, conclusion, flips_if | "Does this follow from evidence? What's the call?" |
| **PICK** | checkpoint | commit | options_considered, selection, rationale, flips_if | "Choose one. Commit." |
| **NEXT_ACTION** | checkpoint | commit | action, owner, deadline, blockers | "What's the single next thing to do?" |

**WHY dict registry:**
- Fast lookup, no I/O
- Easy to extend
- Tactic implies defaults (stance, relation) - Claude only overrides when needed

### Session State

```python
sessions: dict[str, Session] = {}

@dataclass
class Session:
    thoughts: list[Thought]
    branches: dict[str, list[int]]  # branch_name -> thought_ids

@dataclass
class Thought:
    id: int
    stance: str
    content: str
    relation: str | None
    targets: list[int]
    tactic: str | None
```

**WHY in-memory:**
- MCP servers are long-lived
- Thinking sessions are ephemeral
- No persistence complexity

## High-Level Phases

1. **Scaffold** - pyproject.toml, src/reasoning_mcp/server.py, basic FastMCP setup
2. **Core tool** - `think` tool with stance/content, session state
3. **Relations** - Add relation parameter, thought targeting
4. **Tactics** - Full 19-tactic registry with guidance injection
5. **Distribution** - README, installation instructions, `pip install` or local path
6. **TypeScript port** (optional) - If `npx` distribution becomes priority (~4hrs)

## Next Step

Run: `/critique reasoning-mcp`
