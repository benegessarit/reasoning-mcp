# Plan: Reasoning MCP Optimizer (v3)

## Original Goal

> "Build a trajectory-based optimizer that captures think() calls"

## Discovery Summary

| Source | Finding |
|--------|---------|
| `src/reasoning_mcp/server.py:40-224` | 6 tools: begin_session, submit_meta_analysis, declare_scaffold, think, get_session_state, get_tactic_info |
| `src/reasoning_mcp/tactics.py:1-116` | 19 tactics with guidance strings |
| `src/reasoning_mcp/prompts.py:5-82` | 3 stage prompts + 4 style prompts (7,098 chars total) |
| `scripts/optimize_compose_thinking.py:118-180` | JUDGE_PROMPT_TEMPLATE (reusable pattern) |
| GEPA paper (Agrawal et al., Jul 2025) | Round-robin `component_selector` — one module per generation |
| mmGRPO paper (Ziems et al., Aug 2025) | Best composition: MIPROv2 → GRPO (+11% vs baseline) |

## Requirements

**Problem:** Existing GEPA optimizer uses DSPy's `prompt → LLM → response → judge` loop. Reasoning-MCP needs:
```
prompts → MCP_server → Claude_calls_tools_N_times → trajectory → judge
```
DSPy can't run MCPs or capture tool calls.

**Success Criteria:**
- [ ] Captures full trajectory (all tool calls with parameters) during MCP session
- [ ] Judge scores trajectory quality (depth, revisions, branch exploration)
- [ ] Round-robin selects ONE component per generation, evaluates whole trajectory
- [ ] Reflection mutates selected component based on failing trajectories
- [ ] Multi-generation loop improves average trajectory score
- [ ] Checkpoints enable resume after interruption

**Scope:**

| IN | OUT |
|----|-----|
| All 26 components (19 guidance + 4 style + 3 stage) | Optimize model hyperparameters |
| Round-robin component selection (GEPA-style) | Joint multi-component mutation |
| Claude Agent SDK for MCP execution | DSPy integration |
| JSONL trajectory logging | Persistent database |
| GEPA-style reflection | Full GRPO with critic/value network |
| Single MCP server | Multi-server orchestration |

## Risk Analysis

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Claude Agent SDK can't load local stdio MCP | MEDIUM | Test with `mcp_servers` config first; fallback to subprocess + JSON-RPC |
| Judge Goodharts on length | HIGH | Score depth markers (revisions, branches, tactic variety), not word count |
| Reflection produces bad mutations | MEDIUM | Keep best-so-far per component; only adopt improvements |
| 26 components = slow convergence | MEDIUM | Round-robin means 26 generations = 1 full pass; start with 3-5 passes (78-130 gens) |
| Large prompts hard to mutate well | LOW | Reflection sees full prompt + failing trajectories; can make targeted edits |

## Architecture

### Optimization Targets (26 components)

```python
# Layer 1: Tactic guidance (19 strings, ~50-60 chars each)
# In tactics.py — returned in think() response as guidance for next phase
TACTICS["META_ANALYSIS"]["guidance"]     # "What did they literally ask? What do they actually need?"
TACTICS["WILD_OPTIONS"]["guidance"]      # "Generate freely. No filtering. Quantity over quality."
# ... 17 more

# Layer 2: Style prompts (4 strings, ~400-600 chars each)
# In prompts.py — returned by declare_scaffold() and think() as style_prompt
STYLE_PROMPTS["divergent"]    # XML template for divergent phase execution
STYLE_PROMPTS["sequential"]   # XML template with thought chains
STYLE_PROMPTS["adversarial"]  # XML template with premortem structure
STYLE_PROMPTS["checkpoint"]   # XML template with verify/conclude

# Layer 3: Stage prompts (3 strings, ~300-900 chars each)
# In prompts.py — returned by begin_session(), submit_meta_analysis(), declare_scaffold()
STAGE_PROMPTS["meta_analysis"]     # Instructions for analyzing the prompt
STAGE_PROMPTS["select_scaffold"]   # Instructions for picking scaffold type
STAGE_PROMPTS["declare_scaffold"]  # Instructions for declaring workflow
```

### Round-Robin Strategy

```
Generation 1:  optimize TACTICS["META_ANALYSIS"]["guidance"]     → eval whole trajectory
Generation 2:  optimize TACTICS["WILD_OPTIONS"]["guidance"]      → eval whole trajectory
...
Generation 19: optimize TACTICS["NEXT_ACTION"]["guidance"]       → eval whole trajectory
Generation 20: optimize STYLE_PROMPTS["divergent"]               → eval whole trajectory
Generation 21: optimize STYLE_PROMPTS["sequential"]              → eval whole trajectory
Generation 22: optimize STYLE_PROMPTS["adversarial"]             → eval whole trajectory
Generation 23: optimize STYLE_PROMPTS["checkpoint"]              → eval whole trajectory
Generation 24: optimize STAGE_PROMPTS["meta_analysis"]           → eval whole trajectory
Generation 25: optimize STAGE_PROMPTS["select_scaffold"]         → eval whole trajectory
Generation 26: optimize STAGE_PROMPTS["declare_scaffold"]        → eval whole trajectory
Generation 27: optimize TACTICS["META_ANALYSIS"]["guidance"]     → (cycle repeats)
```

Each generation:
1. **Select** one component (round-robin)
2. **Generate** trajectories using current prompts
3. **Judge** each trajectory (whole-system score)
4. **Reflect** on failures → propose mutation to selected component only
5. **Accept** if avg score improves; reject otherwise

### Data Model

```python
@dataclass
class ToolCall:
    tool: str              # "think", "begin_session", etc.
    inputs: dict           # All parameters passed
    result: dict           # Parsed JSON result

@dataclass
class Trajectory:
    question: str
    tool_calls: list[ToolCall]
    final_phases: list[str]
    tactics_used: list[str]
    score: float | None = None

@dataclass
class Component:
    name: str              # "TACTICS.META_ANALYSIS.guidance" or "STYLE_PROMPTS.divergent"
    layer: str             # "guidance" | "style" | "stage"
    current_value: str     # Current prompt text
    best_value: str        # Best-performing version
    best_score: float      # Score when best_value was set
```

### Flow

```
┌─────────────────────────────────────────────────────────────────┐
│ 0. SETUP                                                         │
├─────────────────────────────────────────────────────────────────┤
│ components = load_all_26_components()                            │
│ examples = load_examples("prompts.json")                         │
│ component_order = round_robin(components)                        │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 1. SELECT (round-robin)                                          │
├─────────────────────────────────────────────────────────────────┤
│ target = component_order[generation % len(components)]           │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 2. GENERATE                                                      │
├─────────────────────────────────────────────────────────────────┤
│ for question in examples:                                        │
│   traj = run_mcp_session(question, current_prompts)             │
│   traj.score = judge_trajectory(traj)                            │
│   trajectories.append(traj)                                      │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 3. REFLECT                                                       │
├─────────────────────────────────────────────────────────────────┤
│ failures = [t for t in trajectories if t.score < threshold]      │
│ new_value = reflect_on_component(target, failures)               │
│ if avg(scores) > target.best_score:                              │
│     target.best_value = new_value                                │
│     target.best_score = avg(scores)                              │
│ checkpoint(components, generation)                               │
└─────────────────────────────────────────────────────────────────┘
                              ↓
             Repeat for N generations (78-130 = 3-5 full passes)
```

### Key Functions

```python
# reasoning_mcp/optimizer/components.py
def load_components() -> list[Component]:
    """Load all 26 optimizable components from tactics.py and prompts.py."""

def apply_components(components: list[Component]) -> None:
    """Write current component values back to the MCP server's runtime state."""

# reasoning_mcp/optimizer/runner.py
async def run_mcp_session(question: str, prompts: dict) -> Trajectory:
    """Run MCP session via Claude Agent SDK, capture all tool calls."""

# reasoning_mcp/optimizer/judge.py
async def judge_trajectory(trajectory: Trajectory) -> float:
    """Score trajectory 0.0-1.0 based on depth, revisions, branches, tactic variety."""

# reasoning_mcp/optimizer/reflect.py
async def reflect_on_component(
    component: Component,
    failures: list[Trajectory],
) -> str:
    """Analyze failures, propose mutation to ONE component's prompt text."""

# reasoning_mcp/optimizer/loop.py
async def optimize(
    examples: list[str],
    generations: int = 78,
    examples_per_gen: int = 3,
) -> list[Component]:
    """Main round-robin optimization loop. Returns best components."""

# reasoning_mcp/optimizer/checkpoint.py
def save_checkpoint(components: list[Component], gen: int, path: Path) -> None:
def load_checkpoint(path: Path) -> tuple[list[Component], int] | None:
```

### Injection Mechanism

The MCP server reads from `TACTICS` dict and `STAGE_PROMPTS`/`STYLE_PROMPTS` dicts at runtime. Two options:

**Option A: Module-level mutation** (simplest)
```python
# Before each trajectory run, mutate the imported modules directly
import reasoning_mcp.tactics as tactics_mod
import reasoning_mcp.prompts as prompts_mod
tactics_mod.TACTICS["META_ANALYSIS"]["guidance"] = component.current_value
```

**Option B: Server restart with env/args** (isolated but slower)
```python
# Write components to temp file, restart MCP server with --overrides flag
```

→ **Choose Option A.** The MCP server runs in-process via Agent SDK. Module mutation is safe and fast.

## Implementation Phases

1. **Components** — Load/apply 26 components, checkpoint serialization
2. **Runner** — Claude Agent SDK integration, trajectory capture
3. **Judge** — Trajectory scorer (depth markers, tactic variety, revision quality)
4. **Reflect** — Per-component mutation proposer with failure analysis
5. **Loop** — Round-robin orchestrator with checkpointing
6. **CLI** — `python -m reasoning_mcp.optimizer --examples prompts.json --generations 78`

## Open Question

**Claude Agent SDK availability:** Need to verify the exact import path and MCP server loading API. If SDK can't load stdio MCP servers directly, fallback is subprocess + JSON-RPC stdin/stdout protocol (more code but guaranteed to work).

## Next Step

Build Phase 1: `reasoning_mcp/optimizer/components.py`
