# Critique: reasoning-mcp Optimizer Plan v5 — Round 1

**Target:** `plans/reasoning-mcp-plan-v5.md` (implementation plan)
**Auditors:** epic-risk-auditor, plan-skeptic, blast-radius-analyzer
**Date:** 2026-01-29

---

## Verdict: FIX_AND_SHIP

1 P0 blocker (trivial fix), 5 P1 issues (plan-level fixes, no architectural redesign).

---

## P0 — Blockers

### 1. Missing `finish` tool (plan says 6, server has 7)

**Evidence:** `server.py` has 7 `@mcp.tool()` decorators:
- `begin_session` (line 74)
- `submit_meta_analysis` (line 93)
- `declare_scaffold` (line 121)
- `think` (line 170)
- `finish` (line 333) ← **MISSING FROM PLAN**
- `get_session_state` (line 358)
- `get_tactic_info` (line 378)

**Impact:** Runner's `TOOL_DEFINITIONS` will have 6 tools. Claude will try to call `finish()` to complete a workflow. Runner returns "unknown tool" error. Every trajectory is incomplete.

**Fix:** Add `finish` as the 7th tool in `TOOL_DEFINITIONS` and `TOOL_HANDLERS`. Update all "6 tools" references to "7 tools" throughout the plan.

---

## P1 — Significant

### 1. Async gap — handlers are `async def`, plan doesn't address it

**Evidence:** All 7 handlers are `async def`. Plan's runner pseudocode shows synchronous calls to `messages.create()` but must `await` handler functions.

**Fix:** Plan must specify: use `AsyncAnthropic` client + `async def run_mcp_session()` with `await handler(...)` calls, or use `asyncio.run()` wrapper. Recommend async throughout since handlers are already async.

### 2. Cross-repo reference — `scripts/optimize_compose_thinking.py`

**Evidence:** File exists at `/Users/davidbeyer/claude-code/scripts/optimize_compose_thinking.py`, NOT in reasoning-mcp. Plan references it 3 times as if it's local.

**Fix:** Either copy the file into reasoning-mcp, or update references to absolute path. The "reuse `_parse_judge_response()`" claim in Phase 3 needs the actual code available.

### 3. Session memory leak during optimization

**Evidence:** `sessions: dict[str, Session] = {}` at `server.py:39`. Each `begin_session()` adds an entry. Over 500 evaluations, 500 Session objects accumulate with full thought histories.

**Fix:** Add `del sessions[session_id]` after trajectory capture in runner. Or clear sessions dict between evaluations.

### 4. Crash-safe mutation — no try/finally on dict mutation

**Evidence:** `TACTICS`, `STYLE_PROMPTS`, `STAGE_PROMPTS` are plain mutable dicts. `apply_components()` mutates them in-place. If runner crashes before `reset_components()`, dicts stay corrupted for the rest of the process.

**Fix:** Use context manager pattern:
```python
@contextmanager
def patched_components(components):
    originals = deepcopy_originals()
    apply_components(components)
    try:
        yield
    finally:
        restore_originals(originals)
```

### 5. Style prompt granularity mismatch

**Evidence:** `TACTICS[x]["guidance"]` values are single sentences (~50-60 chars). `STYLE_PROMPTS[x]` values are multi-paragraph XML templates (~20-30 lines each, `prompts.py:90-206`). The reflection prompt and judge need different strategies for each.

**Fix:** Plan should acknowledge this. Options: (a) optimize only guidance strings in v1 (19 components), defer style/stage to v2; or (b) design reflection prompts that handle both granularities explicitly.

---

## P2 — Nice-to-have

1. **Runner system prompt is an "open question"** — should be a Phase 2 deliverable. Claude needs a prompt telling it the correct tool-call sequence (begin_session → submit_meta → declare_scaffold → think* → finish). Bad system prompt = garbage trajectories regardless of component quality.

2. **Two-stage gating threshold undefined** — "minibatch first, full only on improvements" but what counts as "improvement"? Average score > parent's? Any instance > Pareto best? Specify.

3. **No cost cap or early-stop** — $50-120 estimate, no budget enforcement. Add `--max-cost` flag or eval counter that halts when budget exceeded.

4. **Concurrent safety** — add a warning to CLI output: "Do not run while MCP server is active." No lock file needed for a dev tool, but explicit warning prevents confusion.

5. **Merge deferral** — `merge.py` (Phase 5) implements ancestry graphs, desirable predictors, diamond-graph traversal. This is sophisticated machinery for v1. Consider deferring to v2 — mutation-only GEPA still works. Cuts scope to 6 files.

---

## Necessity Note

The epic-risk-auditor flagged "no evidence of need" — no user testing, no baseline metrics, no identified quality issues. This is valid from an antirez perspective but is a **judgment call**: the user has iterated through 5 plan versions intentionally. This is research/exploration of optimization techniques, not premature optimization of a broken system. Noted but not blocking.

---

## Next Steps

1. **Fix P0:** Add `finish` tool (trivial — update TOOL_DEFINITIONS, TOOL_HANDLERS, all "6 tools" references)
2. **Fix P1s:** Address async, cross-repo ref, session cleanup, crash safety, granularity in plan update
3. **Consider P2s:** Especially runner system prompt (P2.1) and merge deferral (P2.5)
4. **Re-run:** `/critique` Round 2 after fixes to verify P0 resolved
