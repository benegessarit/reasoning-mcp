# Plan: Reasoning MCP Optimizer — Implementation (v5)

## Original Goal

> "Build a trajectory-based optimizer that captures think() calls"

## Relationship to v4.1

v4.1 (`reasoning-mcp-plan-v4.md`) is the **algorithm specification** — data models, pseudocode, GEPA equivalence proofs. This plan is the **implementation plan** — how to build working Python from that spec.

## Discovery Summary

| Source | Finding |
|--------|---------|
| `src/reasoning_mcp/server.py:40-267` | 6 MCP tools: begin_session, submit_meta_analysis, declare_scaffold, think, get_session_state, get_tactic_info |
| `src/reasoning_mcp/tactics.py:1-116` | 19 tactics with guidance strings (optimization targets) |
| `src/reasoning_mcp/prompts.py:5-228` | 3 stage prompts + 4 style prompts + TACTIC_STYLES mapping (optimization targets) |
| `src/reasoning_mcp/models.py:1-12` | `Thought` dataclass (session state) |
| `src/reasoning_mcp/analyzers.py:1-111` | Content analyzers for phase validation (not optimized) |
| `src/reasoning_mcp/__main__.py:1-7` | Entry point: `mcp.run()` |
| `anthropic` SDK 0.76.0 | `messages.create()` + `ToolUseBlock` + `ToolParam` — no Agent SDK exists |
| `scripts/optimize_compose_thinking.py:1-410` | Existing DSPy GEPA optimizer (pattern reference, can't reuse — DSPy can't drive MCP) |
| `pyproject.toml:1-20` | Dependencies: `mcp>=1.0.0`, `pydantic>=2.0.0`. No `anthropic` yet. |
| Preflight check | Zero optimizer code exists. No `examples.json`. No Agent SDK. |

## Requirements

**Problem:** DSPy can't run MCP tool-call sessions. Reasoning-MCP's 26 prompt components (19 tactic guidance + 4 style + 3 stage) need optimization via GEPA's algorithm, which requires capturing full tool-call trajectories and using reflective mutation with textual feedback.

**Success Criteria:**
- [ ] `run_mcp_session(question, components)` returns `Trajectory` with all tool calls captured
- [ ] `judge_trajectory(traj)` returns `(score: float, feedback: str)`
- [ ] `propose_mutation(parent, comp, state, examples)` returns `tuple | None`
- [ ] `update_pareto_front(state, candidate)` tracks per-instance-best correctly
- [ ] `try_merge(state)` finds common ancestors and merges component-by-component
- [ ] Full loop runs 3+ generations, checkpoints, resumes without data loss
- [ ] `python -m reasoning_mcp.optimizer --examples examples.json --max-evals 50` works end-to-end

**Scope:**

| IN | OUT |
|----|-----|
| All 26 components (19 guidance + 4 style + 3 stage) | Model hyperparameters |
| Full GEPA: population, Pareto, merge, two-stage, feedback | Value network / GRPO |
| `anthropic.messages.create()` tool loop (no Agent SDK) | DSPy integration |
| JSONL trajectory + JSON checkpoint | Persistent database |
| Claude Sonnet for judge + reflection | Multi-model judge (GPT) |
| 15-20 curated example questions | Transcript extraction |

## Risk Analysis

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Tool loop diverges (Claude calls wrong tools, hangs) | MEDIUM | Max-turns=15, 120s timeout per session, strict tool name validation |
| Judge Goodharts on XML structure | HIGH | Judge prompt scores content quality + non-obviousness, not just tag presence |
| Reflection produces garbage mutations | MEDIUM | Strict `>` acceptance; worst case = wasted budget, no regression |
| Cost blowout ($50-120 per run) | MEDIUM | Start with 5-example dry run, two-stage gating cuts 80% of full evals |
| Module-level mutation has side effects | LOW | Reset modules to original values before each session; single-threaded |

## Architecture

### Design Decisions

**1. Runner: `anthropic.messages.create()` + in-process tool loop**

Claude Agent SDK doesn't exist as a pip package. We use the raw anthropic SDK:
- Define 6 MCP tools as `ToolParam` dicts
- Call `messages.create()` with system prompt + question
- When Claude returns `ToolUseBlock`: call MCP handler in-process, return `tool_result`
- Loop until Claude stops calling tools (sends text) or max_turns hit
- Capture every `ToolUseBlock` → `ToolCall` object

**Why not subprocess + JSON-RPC:** Unnecessary IPC complexity. MCP handlers are pure Python functions — call them directly.

**Why not DSPy:** DSPy has no MCP/tool-call awareness. Can't capture trajectories.

**2. Judge: Claude Sonnet, same API key**

Score + textual feedback. One dependency, one key. Self-bias is a monitor-and-fix risk.

**3. File structure: Flat module, 8 files**

```
src/reasoning_mcp/optimizer/
├── __init__.py       # Exports optimize(), Candidate, OptimizerState
├── state.py          # Candidate, OptimizerState, Pareto front, eval cache, sampling
├── runner.py         # anthropic tool loop, trajectory capture
├── judge.py          # Score + feedback, JUDGE_PROMPT
├── reflect.py        # propose_mutation(), reflective dataset, REFLECTION_PROMPT
├── merge.py          # try_merge(), ancestry graph, desirable predictors
├── loop.py           # Main optimization loop + CLI entry point
├── checkpoint.py     # JSON save/load of OptimizerState
└── examples.json     # 15-20 curated questions
```

Sampling (`sample_minibatch`) and selection (`select_parent`) are inlined into `state.py` — too small for separate files.

**4. Injection: Module-level dict mutation**

Before each `run_mcp_session()`, mutate `tactics.TACTICS` and `prompts.STAGE_PROMPTS`/`STYLE_PROMPTS` dicts in-place. Reset after. Single-threaded, safe.

```python
# In runner.py — before each session
import reasoning_mcp.tactics as tactics_mod
import reasoning_mcp.prompts as prompts_mod

def apply_components(components: dict[str, str]) -> None:
    for name, value in components.items():
        if name.startswith("TACTICS."):
            tactic = name.split(".")[1]
            tactics_mod.TACTICS[tactic]["guidance"] = value
        elif name.startswith("STYLE_PROMPTS."):
            style = name.split(".")[1]
            prompts_mod.STYLE_PROMPTS[style] = value
        elif name.startswith("STAGE_PROMPTS."):
            stage = name.split(".")[1]
            prompts_mod.STAGE_PROMPTS[stage] = value
```

Source: v4.1 plan lines 769-788.

**5. Tool definitions for anthropic SDK**

The 6 MCP tools need to be expressed as `ToolParam` dicts for `messages.create()`. These mirror `server.py:40-267` exactly:

```python
TOOLS = [
    {
        "name": "begin_session",
        "description": "Start a new reasoning session. Returns the meta_analysis prompt.",
        "input_schema": {
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "Optional session ID"}
            }
        }
    },
    # ... 5 more matching server.py signatures
]
```

The runner calls the actual MCP handler functions (`begin_session()`, `think()`, etc.) in-process when Claude requests a tool — NOT over stdio/network.

## High-Level Phases

### Phase 1: State + Data Model (`state.py`)

New file: `src/reasoning_mcp/optimizer/state.py`

**Builds:**
- `ToolCall` dataclass (tool, inputs, result)
- `Trajectory` dataclass (question, tool_calls, score, feedback)
- `Candidate` dataclass (id, parent_ids, components, per_instance_scores, round_robin_index)
- `EvalCacheEntry` dataclass (score, feedback)
- `OptimizerState` dataclass (candidates, pareto_front_by_instance, eval_cache, rng, merge state)
- `update_pareto_front()` — per-instance-best tracking (NOT classic dominance)
- `get_front_candidate_ids()` — union of all per-instance bests
- `select_parent()` — uniform random from front
- `sample_minibatch()` — epoch-shuffled with seeded RNG
- `candidate_hash()` — SHA-256 for eval cache

**Source:** v4.1 plan lines 112-238, 373-398.

**Tests:** Pareto front updates correctly, sampling covers all examples per epoch, cache keys are deterministic.

### Phase 2: Runner (`runner.py`)

New file: `src/reasoning_mcp/optimizer/runner.py`

**Builds:**
- `TOOL_DEFINITIONS` — 6 tools as `ToolParam` dicts matching `server.py`
- `TOOL_HANDLERS` — map tool name → async handler function (imported from server.py)
- `apply_components()` / `reset_components()` — module-level dict mutation
- `run_mcp_session(question, components)` → `Trajectory`
  - Apply components → create anthropic client → messages.create() loop → capture ToolUseBlocks → reset components

**Depends on:** `state.py` (ToolCall, Trajectory)

**External dep:** `anthropic` SDK (add to pyproject.toml)

**Tests:** Mock `anthropic.Client().messages.create()` to return scripted ToolUseBlocks. Verify trajectory capture, component injection, reset.

### Phase 3: Judge (`judge.py`)

New file: `src/reasoning_mcp/optimizer/judge.py`

**Builds:**
- `JUDGE_PROMPT` — scoring criteria for reasoning trajectories
- `judge_trajectory(traj)` → `(float, str)` — calls Claude Sonnet, parses score + feedback
- `_parse_judge_response()` — extract score float + feedback text

**Pattern:** Reuse `_parse_judge_response()` from `scripts/optimize_compose_thinking.py:132-141`.

**Tests:** Mock LLM call. Verify score parsing, feedback extraction, edge cases (malformed response → 0.5 default).

### Phase 4: Reflective Mutation (`reflect.py`)

New file: `src/reasoning_mcp/optimizer/reflect.py`

**Builds:**
- `REFLECTION_PROMPT` — GEPA's exact template (v4.1 plan lines 506-521)
- `build_reflective_dataset(trajectories)` → `list[dict]`
- `_summarize_trajectory(traj)` → readable text of think() calls
- `call_reflection_llm(component_name, current_value, dataset)` → `str | None`
- `propose_mutation(parent, component_name, state, examples)` → `tuple | None`
  - Self-contained: sample → eval parent → reflect → eval mutation → return

**Depends on:** `state.py`, `runner.py`, `judge.py`

**Tests:** Mock runner + judge + LLM. Verify: dataset structure, prompt formatting, code block extraction, None on parse failure, None on identical mutation.

### Phase 5: Merge (`merge.py`)

New file: `src/reasoning_mcp/optimizer/merge.py`

**Builds:**
- `should_try_merge(state)` → `bool` (event-driven trigger)
- `get_ancestors(candidate, state)` → `set[int]` (parent graph traversal)
- `_has_desirable_predictors(ancestor, a, b)` → `bool`
- `try_merge(state, max_attempts=10)` → `Candidate | None`

**Depends on:** `state.py`

**Tests:** Ancestry traversal with diamond graph, merge with divergent predictors, retry exhaustion, no-common-ancestor case.

### Phase 6: Checkpoint (`checkpoint.py`)

New file: `src/reasoning_mcp/optimizer/checkpoint.py`

**Builds:**
- `save_checkpoint(state, path)` — serialize OptimizerState to JSON
- `load_checkpoint(path)` → `OptimizerState | None`
- Handle: set serialization, RNG state, dataclass → dict → dataclass roundtrip

**Tests:** Roundtrip: save → load → compare all fields. Corrupt file → None.

### Phase 7: Loop + CLI (`loop.py`)

New file: `src/reasoning_mcp/optimizer/loop.py`

**Builds:**
- `eval_with_cache()` — check cache, run if miss
- `full_eval()` — eval all examples
- `optimize(examples, max_evals)` → `OptimizerState` — the main GEPA loop
- `load_components()` — read current values from tactics.py + prompts.py
- CLI: `python -m reasoning_mcp.optimizer --examples examples.json --max-evals 500`
- `__main__.py` for the optimizer subpackage

**Depends on:** Everything.

**Tests:** Mock all IO. Verify: loop executes N generations, checkpoint called, merge triggered after successful mutation, accepted mutations added to archive.

### Phase 8: Examples + Integration Test

New file: `src/reasoning_mcp/optimizer/examples.json`

**Builds:**
- 15-20 curated questions spanning: technical decisions, debugging, design trade-offs, architecture, code review
- One integration test: run 2 generations with 3 examples (mocked LLM), verify end-to-end flow

## Dependency Graph

```
Phase 1 (state) ──────────────────────────────────┐
Phase 2 (runner) ──── depends on Phase 1           │
Phase 3 (judge) ──── standalone                    │
Phase 4 (reflect) ── depends on Phases 1, 2, 3    ├── Phase 7 (loop) depends on ALL
Phase 5 (merge) ──── depends on Phase 1            │
Phase 6 (checkpoint) depends on Phase 1            │
Phase 8 (examples) ─ standalone ───────────────────┘
```

Parallelizable: Phases 1+3+5+8 can be built independently. Phase 2 needs 1. Phase 4 needs 1+2+3. Phase 7 needs everything.

## Open Questions

1. **`anthropic` not in pyproject.toml** — needs adding as dependency. Which version minimum?
2. **ANTHROPIC_API_KEY** — needed for runner + judge + reflection. Env var, same as other scripts.
3. **Max turns per session** — v4.1 doesn't specify. Suggest 15 (begin_session + submit_meta + declare_scaffold + up to 12 think() calls).
4. **System prompt for runner** — Claude needs instructions to use the reasoning-MCP tools. This is itself a prompt we could optimize later, but start with a fixed one.

## Next Step

Run: `/critique reasoning-mcp-optimizer`
