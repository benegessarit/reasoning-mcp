# Plan: Reasoning MCP Optimizer

## Original Goal

> "Build a trajectory-based optimizer that captures think() calls"

## Discovery Summary

| Source | Finding |
|--------|---------|
| `src/reasoning_mcp/server.py:40-224` | 6 tools: begin_session, submit_meta_analysis, declare_scaffold, think, get_session_state, get_tactic_info |
| `src/reasoning_mcp/tactics.py:1-116` | 19 tactics with guidance strings (optimizable target) |
| `src/reasoning_mcp/prompts.py:5-82` | Stage prompts: meta_analysis, select_scaffold, declare_scaffold |
| `scripts/optimize_compose_thinking.py:118-180` | JUDGE_PROMPT_TEMPLATE (reusable) |
| Prior conversation | Claude Agent SDK can load MCP servers and capture ToolUseBlock objects |

## Requirements

**Problem:** Existing GEPA optimizer (`scripts/optimize_compose_thinking.py`) uses DSPy's `prompt → LLM → response → judge` loop. But reasoning-mcp needs:
```
guidance → MCP_server → Claude_calls_tools_N_times → trajectory → judge
```
DSPy can't run MCPs or capture tool calls.

**Success Criteria:**
- [ ] Captures full trajectory (all tool calls with parameters) during MCP session
- [ ] Judge scores trajectory quality (depth, revisions, branch exploration)
- [ ] Reflection mutates guidance strings based on failing trajectories
- [ ] Multi-generation loop improves average trajectory score
- [ ] Checkpoints enable resume after interruption

**Scope:**

| IN | OUT |
|----|-----|
| Optimize tactic guidance strings (19 targets) | Optimize stage prompts |
| Claude Agent SDK for MCP execution | DSPy integration |
| JSONL trajectory logging | Persistent database |
| GEPA-style reflection (no value network) | Full GRPO with critic |
| Single MCP server | Multi-server orchestration |

## Risk Analysis

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Claude Agent SDK can't load local MCP | MEDIUM | Test with `mcp_servers` config first; fallback to subprocess |
| Trajectory capture incomplete | LOW | SDK streams ToolUseBlock; we capture all |
| Judge Goodharts on length | HIGH | Score depth markers (revisions, branches), not word count |
| Reflection produces bad mutations | MEDIUM | Keep best-so-far; only adopt improvements |

## Architecture

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
    final_phases: list[str]   # Which phases were executed
    tactics_used: list[str]   # Which tactics appeared in think() calls
```

### Optimization Target

```python
# In tactics.py, each tactic has a guidance string:
TACTICS = {
    "META_ANALYSIS": {
        "guidance": "What did they literally ask? What do they actually need?",  # <-- OPTIMIZE THIS
        ...
    },
    ...
}
```

The optimizer mutates these 19 guidance strings to improve trajectory quality.

### Flow

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. GENERATE                                                      │
├─────────────────────────────────────────────────────────────────┤
│ for question in examples:                                        │
│   trajectory = run_mcp_session(question, current_guidance)       │
│   score = judge_trajectory(trajectory)                           │
│   trajectories.append((trajectory, score))                       │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 2. REFLECT (GEPA-style)                                          │
├─────────────────────────────────────────────────────────────────┤
│ failures = [t for t in trajectories if t.score < threshold]      │
│ new_guidance = reflect_and_mutate(current_guidance, failures)    │
│ if avg(scores) > best_score:                                     │
│     best_guidance = current_guidance                             │
│     best_score = avg(scores)                                     │
└─────────────────────────────────────────────────────────────────┘
                              ↓
             Repeat for N generations
```

### Key Functions

```python
# reasoning_mcp/optimizer/runner.py
async def run_mcp_session(question: str, guidance: dict[str, str]) -> Trajectory:
    """Run MCP session via Claude Agent SDK, capture all tool calls."""

# reasoning_mcp/optimizer/judge.py
def judge_trajectory(trajectory: Trajectory) -> float:
    """Score trajectory 0.0-1.0 based on depth, revisions, branches."""

# reasoning_mcp/optimizer/reflect.py
def reflect_and_mutate(guidance: dict, failures: list[Trajectory]) -> dict:
    """Analyze failures, propose mutations to guidance strings."""

# reasoning_mcp/optimizer/loop.py
async def optimize(examples: list, generations: int = 10) -> dict:
    """Main optimization loop. Returns best guidance dict."""
```

## High-Level Phases

1. **Runner** — Claude Agent SDK integration to run MCP and capture trajectories
2. **Judge** — Trajectory scorer (depth markers, not word count)
3. **Reflect** — GEPA-style mutation proposer
4. **Loop** — Multi-generation orchestrator with checkpointing
5. **CLI** — `python -m reasoning_mcp.optimizer --examples prompts.json`

## Next Step

Run: `/critique reasoning-mcp`
