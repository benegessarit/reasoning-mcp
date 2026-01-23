# Plan: Reasoning MCP Optimizer (v4.1)

## Changes from v4

v4 had the right mechanisms but wrong implementations for 3 of them (Pareto front, merge, reflection dataset) and left 2 underspecified (merge scheduling, ancestry tracking). Found via adversarial audit re-reading GEPA source code (`gepa-ai/gepa`).

| v4 Flaw | v4.1 Fix |
|---------|----------|
| Pareto front used classic multi-objective dominance | Per-instance-best tracking (matching `state.py`) |
| `parent_id: int \| None` — can't track merge ancestry | `parent_ids: list[int]` + ancestry graph traversal |
| Merge iterated Pareto combinations, oversimplified logic | Random sampling from ALL candidates, ancestor filtering, retry (up to 10), predictor-level scoring |
| Merge scheduled "every N generations" | Event-driven: `merges_due` counter incremented on successful mutation |
| Reflective dataset was raw trajectories | Structured `build_reflective_dataset()` with GEPA's prompt template |
| No eval cache | SHA-256(sorted candidate dict) × example_id cache |
| Coverage-weighted sampling unverifiable | Uniform random from front (honest about what we can verify) |
| `reflect_and_mutate()` always returns string | Returns `str | None` — main loop handles None |
| No deterministic RNG | Seeded `random.Random(seed)` threaded through all stochastic ops |

## Changes from v3

v3 was a naive hill climber. v4+ adds the 5 critical GEPA mechanisms verified against source code.

| Mechanism | v3 | v4.1 |
|-----------|----|----|
| Population | Single best candidate | Unbounded archive of accepted candidates |
| Selection | Global best | Per-instance-best Pareto front, uniform random sampling |
| Combination | None | Merge/crossover via common-ancestor detection with ancestry graph |
| Eval budget | Full eval every time | Two-stage: minibatch → full only on strict improvements |
| Feedback | Score only (float) | Score + textual feedback fed to reflector via structured dataset |

---

## Original Goal

> "Build a trajectory-based optimizer that captures think() calls"

## Discovery Summary

| Source | Finding |
|--------|---------|
| `src/reasoning_mcp/server.py:40-224` | 6 tools: begin_session, submit_meta_analysis, declare_scaffold, think, get_session_state, get_tactic_info |
| `src/reasoning_mcp/tactics.py:1-116` | 19 tactics with guidance strings |
| `src/reasoning_mcp/prompts.py:5-82` | 3 stage prompts + 4 style prompts (7,098 chars total) |
| `gepa-ai/gepa core/engine.py` | Main loop: merge attempt → reflective mutation → two-stage eval → Pareto update |
| `gepa-ai/gepa core/state.py` | Candidate archive, per-instance scores, 3 Pareto frontier types, eval cache |
| `gepa-ai/gepa proposer/merge.py` | Common-ancestor algorithmic crossover (no LLM) |
| `gepa-ai/gepa proposer/reflective_mutation/` | Trace capture → failure dataset → LLM reflection → proposal |

## Requirements

**Problem:** DSPy can't run MCPs or capture tool calls. We need:
```
components → MCP_server → Claude_calls_tools_N_times → trajectory → judge(score+feedback)
```

**Success Criteria:**
- [ ] Captures full trajectory (all tool calls with parameters) during MCP session
- [ ] Judge returns `(score: float, feedback: str)` — not just a number
- [ ] Maintains unbounded candidate archive with per-instance scores
- [ ] Pareto front tracks candidates that are best on at least one example (per-instance-best)
- [ ] Round-robin selects ONE component per generation per candidate
- [ ] Reflective mutation receives textual feedback + structured dataset
- [ ] Two-stage eval: minibatch first, full eval only on strict improvements
- [ ] Merge/crossover combines candidates sharing a common ancestor
- [ ] Epoch-shuffled minibatch sampling (every example seen once per epoch)
- [ ] Checkpoints enable resume after interruption

**Scope:**

| IN | OUT |
|----|-----|
| All 26 components (19 guidance + 4 style + 3 stage) | Model hyperparameters |
| Full GEPA algorithm (population, Pareto, merge, two-stage, feedback) | Value network / GRPO |
| Claude Agent SDK for MCP execution | DSPy integration |
| JSONL trajectory + checkpoint logging | Persistent database |
| Single MCP server | Multi-server orchestration |

## Risk Analysis

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Claude Agent SDK can't load local stdio MCP | MEDIUM | Test with `mcp_servers` config first; fallback to subprocess + JSON-RPC |
| Judge Goodharts on length | HIGH | Textual feedback focuses on depth markers; separate score dimensions |
| Pareto front grows unbounded | LOW | GEPA doesn't bound either; archive is cheap (just prompt strings + scores) |
| Merge finds no common ancestors | MEDIUM | Merge is opportunistic — falls back to reflective mutation (matches GEPA) |
| 26 components × minibatch = many API calls | HIGH | Two-stage gating cuts full evals by ~80% (GEPA empirical) |
| Reflection produces bad mutations | MEDIUM | Accept only strict improvements vs parent on same minibatch |

## Architecture

### Optimization Targets (26 components)

```python
# Layer 1: Tactic guidance (19 strings, ~50-60 chars each)
TACTICS["META_ANALYSIS"]["guidance"]     # "What did they literally ask? What do they actually need?"
TACTICS["WILD_OPTIONS"]["guidance"]      # "Generate freely. No filtering. Quantity over quality."
# ... 17 more

# Layer 2: Style prompts (4 strings, ~400-600 chars each)
STYLE_PROMPTS["divergent"]    # XML template for divergent phase execution
STYLE_PROMPTS["sequential"]   # XML template with thought chains
STYLE_PROMPTS["adversarial"]  # XML template with premortem structure
STYLE_PROMPTS["checkpoint"]   # XML template with verify/conclude

# Layer 3: Stage prompts (3 strings, ~300-900 chars each)
STAGE_PROMPTS["meta_analysis"]     # Instructions for analyzing the prompt
STAGE_PROMPTS["select_scaffold"]   # Instructions for picking scaffold type
STAGE_PROMPTS["declare_scaffold"]  # Instructions for declaring workflow
```

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
    feedback: str | None = None    # NEW: textual feedback from judge

@dataclass
class Candidate:
    """A complete set of 26 component values — one 'program' in GEPA terms."""
    id: int
    parent_ids: list[int]                    # [single_parent] or [parent_a, parent_b] for merges
    components: dict[str, str]               # name → current prompt text
    per_instance_scores: dict[str, float]    # example_id → score
    round_robin_index: int = 0               # Per-candidate rotation counter

    @property
    def avg_score(self) -> float:
        if not self.per_instance_scores:
            return 0.0
        return sum(self.per_instance_scores.values()) / len(self.per_instance_scores)

@dataclass
class EvalCacheEntry:
    """Cached evaluation result for a (candidate_hash, example_id) pair."""
    score: float
    feedback: str

@dataclass
class OptimizerState:
    """Full optimizer state — serializable for checkpointing."""
    candidates: list[Candidate]              # Unbounded archive
    # Per-instance-best front: example_id → set of candidate IDs that scored highest
    pareto_front_by_instance: dict[str, set[int]] = field(default_factory=dict)
    # Best score seen per instance (for fast comparison)
    pareto_best_scores: dict[str, float] = field(default_factory=dict)
    next_candidate_id: int = 1
    generation: int = 0
    # Eval cache: (sha256_hash, example_id) → EvalCacheEntry
    eval_cache: dict[tuple[str, str], EvalCacheEntry] = field(default_factory=dict)
    # Epoch-shuffled sampling state
    epoch_order: list[str] = field(default_factory=list)
    epoch_offset: int = 0
    # Merge scheduling (GEPA event-driven pattern)
    merges_due: int = 0
    total_merges_tested: int = 0
    max_merge_invocations: int = 5
    last_iter_found_new_program: bool = False
    # Merge attempt tracking (prevent re-merging same ancestors)
    attempted_merge_ancestors: set[int] = field(default_factory=set)
    # Deterministic RNG seed
    rng: random.Random = field(default_factory=lambda: random.Random(42))
```

### Pareto Front (Per-Instance-Best — NOT Classic Dominance)

**CRITICAL**: GEPA does NOT use classic multi-objective Pareto dominance. It tracks **per-instance bests**: for each validation example, which program(s) scored highest. The "front" is the union of all programs that are best on at least one example.

This is simpler and more generous than classic dominance — any program that excels on even ONE example makes the front, preserving diversity.

```python
def update_pareto_front(state: OptimizerState, candidate: Candidate) -> list[int]:
    """Update per-instance-best front after a candidate gets full validation scores.

    Source: gepa/core/state.py — pareto_front_valset + program_at_pareto_front_valset

    Returns: list of displaced candidate IDs (were on front, no longer are).
    """
    displaced = []
    for ex_id, score in candidate.per_instance_scores.items():
        prev_best = state.pareto_best_scores.get(ex_id, float("-inf"))
        if score > prev_best:
            # New best for this instance — replace front entry
            old_front_ids = state.pareto_front_by_instance.get(ex_id, set())
            state.pareto_front_by_instance[ex_id] = {candidate.id}
            state.pareto_best_scores[ex_id] = score
            # Check if displaced candidates are still on front for other instances
            for old_id in old_front_ids:
                if old_id != candidate.id and not _is_on_front(old_id, state):
                    displaced.append(old_id)
        elif score == prev_best:
            # Tied — add to existing front for this instance
            state.pareto_front_by_instance.setdefault(ex_id, set()).add(candidate.id)

    return displaced

def get_front_candidate_ids(state: OptimizerState) -> set[int]:
    """Union of all programs that are best on at least one instance."""
    ids = set()
    for front_set in state.pareto_front_by_instance.values():
        ids.update(front_set)
    return ids

def _is_on_front(candidate_id: int, state: OptimizerState) -> bool:
    """Check if candidate is still best on any instance."""
    return any(candidate_id in s for s in state.pareto_front_by_instance.values())
```

### Candidate Selection

GEPA's `ParetoCandidateSelector` samples from the Pareto front via `select_program_candidate_from_pareto_front()`. The exact weighting mechanism is internal to a utility function whose source we couldn't retrieve. We use **uniform random from the front** as a safe default — the per-instance-best front already provides diversity (each member excels on different examples).

```python
def select_parent(state: OptimizerState) -> Candidate:
    """Uniform random sample from per-instance-best Pareto front.

    Source: gepa/strategies/candidate_selector.py — ParetoCandidateSelector
    Note: GEPA delegates to select_program_candidate_from_pareto_front()
    whose internals we couldn't verify. Uniform random is safe default
    because per-instance-best front inherently provides diversity.
    """
    front_ids = get_front_candidate_ids(state)
    front_candidates = [c for c in state.candidates if c.id in front_ids]
    if not front_candidates:
        # Fallback: best average score (matches GEPA's CurrentBestCandidateSelector)
        return max(state.candidates, key=lambda c: c.avg_score)
    return state.rng.choice(front_candidates)
```

### Two-Stage Evaluation

GEPA evaluates mutations cheaply first, then invests in full validation only on improvements.

```
Stage 1: Evaluate parent + mutation on SAME minibatch (3 examples)
         → Accept mutation ONLY if sum(mutation_scores) > sum(parent_scores)
         → Reject otherwise (no full eval — saves ~80% API budget)

Stage 2: IF accepted, run full validation on ALL examples
         → Update per_instance_scores
         → Recompute Pareto front
```

### Merge/Crossover

No LLM involved. Algorithmic combination of two candidates with a common ancestor. **Event-driven scheduling**: triggered by successful mutations, not periodic.

```python
def should_try_merge(state: OptimizerState) -> bool:
    """GEPA merge trigger conditions (engine.py).
    Merge is event-driven, NOT periodic."""
    return (
        state.merges_due > 0
        and state.last_iter_found_new_program
        and state.total_merges_tested < state.max_merge_invocations
    )

def try_merge(state: OptimizerState, max_attempts: int = 10) -> Candidate | None:
    """Find two candidates with common ancestor, merge them.

    Source: gepa/proposer/merge.py
    Key differences from v4:
    - Samples random PAIRS from ALL candidates (not just Pareto front combinations)
    - Filters ancestors: no prior merge attempts + desirable predictors
    - For divergent predictors: picks from descendant with higher AGGREGATED score
    - Retries up to max_attempts (GEPA default: 10)
    """
    if len(state.candidates) < 2:
        return None

    for _attempt in range(max_attempts):
        # Random sample two candidates (GEPA samples from all, not just front)
        a, b = state.rng.sample(state.candidates, 2)

        # Find common ancestors via parent graph traversal
        a_ancestors = get_ancestors(a, state)
        b_ancestors = get_ancestors(b, state)
        common = a_ancestors & b_ancestors

        if not common:
            continue

        # Filter ancestors (GEPA merge.py):
        # (a) No prior merge attempts on this ancestor
        # (b) Ancestor score <= both descendants
        # (c) Has "desirable predictors" — ancestor matches one child but children differ
        valid_ancestor = None
        for anc_id in common:
            if anc_id in state.attempted_merge_ancestors:
                continue
            anc = _get_candidate(anc_id, state)
            if anc.avg_score > a.avg_score or anc.avg_score > b.avg_score:
                continue
            if _has_desirable_predictors(anc, a, b):
                valid_ancestor = anc
                break

        if valid_ancestor is None:
            continue

        state.attempted_merge_ancestors.add(valid_ancestor.id)

        # Merge predictors (GEPA merge.py — 3 cases)
        merged = {}
        for name in a.components:
            a_changed = a.components[name] != valid_ancestor.components[name]
            b_changed = b.components[name] != valid_ancestor.components[name]

            if a_changed and not b_changed:
                merged[name] = a.components[name]
            elif b_changed and not a_changed:
                merged[name] = b.components[name]
            elif a_changed and b_changed and a.components[name] != b.components[name]:
                # Both diverged from ancestor differently —
                # GEPA: pick from descendant with higher AGGREGATED score
                merged[name] = a.components[name] if a.avg_score >= b.avg_score else b.components[name]
            else:
                # Neither changed, or both changed identically —
                # GEPA: deterministically picks first child's version
                merged[name] = a.components[name]

        new = Candidate(
            id=state.next_candidate_id,
            parent_ids=[a.id, b.id],
            components=merged,
            per_instance_scores={},
        )
        state.next_candidate_id += 1
        state.merges_due -= 1
        state.total_merges_tested += 1
        return new

    return None  # All attempts failed

def get_ancestors(candidate: Candidate, state: OptimizerState) -> set[int]:
    """Traverse parent graph to find all ancestors."""
    visited = set()
    stack = list(candidate.parent_ids)
    while stack:
        pid = stack.pop()
        if pid in visited:
            continue
        visited.add(pid)
        parent = _get_candidate(pid, state)
        if parent:
            stack.extend(parent.parent_ids)
    return visited

def _has_desirable_predictors(ancestor: Candidate, a: Candidate, b: Candidate) -> bool:
    """Check if ancestor has predictors where it matches one child but children differ."""
    for name in ancestor.components:
        a_matches = a.components[name] == ancestor.components[name]
        b_matches = b.components[name] == ancestor.components[name]
        children_differ = a.components[name] != b.components[name]
        if (a_matches != b_matches) and children_differ:
            return True
    return False
```

**Merge acceptance** (in main loop): `merged_sum >= max(parent_a_sum, parent_b_sum)` — note `>=` not `>` (allows equal, unlike mutation which requires strict `>`). We compare full validation sums. GEPA has an additional optimization (strategic validation subset spanning performance buckets) that we skip for simplicity — full eval on all examples is correct, just slightly more expensive.

### Epoch-Shuffled Minibatch Sampling

Every example is seen once per epoch before reshuffling. Prevents oversampling.

```python
def sample_minibatch(state: OptimizerState, examples: list[str], batch_size: int = 3) -> list[str]:
    """Epoch-shuffled: each example seen once before reshuffle.

    Source: gepa/strategies/batch_sampler.py — EpochShuffledBatchSampler
    Uses state.rng for deterministic reproducibility.
    Pads with least-frequent examples when len(examples) % batch_size != 0.
    """
    if not state.epoch_order or state.epoch_offset >= len(state.epoch_order):
        state.epoch_order = list(examples)
        state.rng.shuffle(state.epoch_order)
        # Pad to multiple of batch_size with least-seen examples
        remainder = len(state.epoch_order) % batch_size
        if remainder != 0:
            # GEPA pads with least-frequent IDs
            pad_count = batch_size - remainder
            state.epoch_order.extend(state.epoch_order[:pad_count])
        state.epoch_offset = 0
    batch = state.epoch_order[state.epoch_offset:state.epoch_offset + batch_size]
    state.epoch_offset += batch_size
    return batch
```

### Reflective Mutation (with structured feedback dataset)

GEPA's reflector is a self-contained unit (`propose()`) that:
1. Evaluates the parent on a minibatch (with trace capture)
2. Transforms traces into a structured reflective dataset
3. Sends current instruction + dataset to an LLM
4. Extracts the proposed new instruction from code blocks
5. Evaluates the proposal on the SAME minibatch
6. Returns `CandidateProposal | None` — None if proposal fails to parse or is identical

**Source:** `gepa/proposer/reflective_mutation/reflective_mutation.py`

```python
async def propose_mutation(
    parent: Candidate,
    component_name: str,
    state: OptimizerState,
    examples: list[str],
    batch_size: int = 3,
) -> tuple[Candidate, list[Trajectory], list[Trajectory]] | None:
    """Self-contained reflective mutation proposer (matches GEPA's propose()).

    Returns: (mutation_candidate, parent_trajs, mutation_trajs) or None.
    The caller (main loop) handles acceptance — this just proposes.
    """
    # 1. Sample minibatch
    batch = sample_minibatch(state, examples, batch_size)

    # 2. Evaluate parent on minibatch with trace capture
    parent_trajs = []
    for q in batch:
        traj = await run_mcp_session(q, parent.components)
        traj.score, traj.feedback = await judge_trajectory(traj)
        parent_trajs.append(traj)

    # 3. Build reflective dataset (GEPA's make_reflective_dataset)
    dataset = build_reflective_dataset(parent_trajs)

    # 4. LLM proposes new instruction
    new_value = await call_reflection_llm(
        component_name=component_name,
        current_value=parent.components[component_name],
        reflective_dataset=dataset,
    )

    if new_value is None or new_value == parent.components[component_name]:
        return None  # Failed to parse or identical — matches GEPA

    # 5. Build mutation candidate
    mutation = Candidate(
        id=state.next_candidate_id,
        parent_ids=[parent.id],
        components={**parent.components, component_name: new_value},
        per_instance_scores={},
    )
    state.next_candidate_id += 1

    # 6. Evaluate mutation on SAME minibatch
    mut_trajs = []
    for q in batch:
        traj = await run_mcp_session(q, mutation.components)
        traj.score, traj.feedback = await judge_trajectory(traj)
        mut_trajs.append(traj)

    return mutation, parent_trajs, mut_trajs


def build_reflective_dataset(trajectories: list[Trajectory]) -> list[dict]:
    """Transform trajectories into structured records for reflection.

    Source: gepa/core/adapter.py — make_reflective_dataset()
    Each record contains: input (question), output (trajectory summary),
    score, and textual feedback.
    """
    records = []
    for traj in trajectories:
        records.append({
            "input": traj.question,
            "output": _summarize_trajectory(traj),
            "score": traj.score,
            "feedback": traj.feedback or "",
        })
    return records


def _summarize_trajectory(traj: Trajectory) -> str:
    """Convert trajectory tool calls into readable text for reflection prompt.

    GEPA's adapter transforms raw execution traces into text that the reflector
    can reason about. For MCP trajectories, we serialize the think() calls —
    the content Claude produced at each phase.
    """
    parts = []
    for tc in traj.tool_calls:
        if tc.tool == "think":
            phase = tc.inputs.get("phase_name", "?")
            tactic = tc.inputs.get("tactic", "none")
            content = tc.inputs.get("content", "")[:500]  # Truncate for prompt budget
            parts.append(f"[{phase}|{tactic}] {content}")
        elif tc.tool == "submit_meta_analysis":
            parts.append(f"[meta_analysis] {tc.inputs.get('meta_analysis', '')[:300]}")
    return "\n".join(parts)


# GEPA's reflection prompt template
# Source: gepa/strategies/instruction_proposal.py
REFLECTION_PROMPT = """I provided an assistant with the following instructions:

---
{current_instruction}
---

Here are examples of task inputs, the assistant's responses, and feedback on those responses:

{dataset_entries}

Write a new instruction that incorporates the feedback to improve the assistant's responses.
The new instruction should be specific and actionable.

```
[new instruction here]
```"""


async def call_reflection_llm(
    component_name: str,
    current_value: str,
    reflective_dataset: list[dict],
) -> str | None:
    """Send reflection prompt to LLM, extract new instruction from code block.

    Source: gepa/strategies/instruction_proposal.py
    Returns None if no code block found in response.
    """
    entries = []
    for record in reflective_dataset:
        entries.append(
            f"Input: {record['input']}\n"
            f"Output: {record['output']}\n"
            f"Score: {record['score']}\n"
            f"Feedback: {record['feedback']}"
        )

    prompt = REFLECTION_PROMPT.format(
        current_instruction=current_value,
        dataset_entries="\n---\n".join(entries),
    )

    response = await call_llm(prompt)  # Claude Sonnet for reflection quality

    # Extract from code block (GEPA pattern)
    import re
    match = re.search(r"```\n?(.*?)```", response, re.DOTALL)
    if match:
        return match.group(1).strip()
    return None  # Failed to parse — propose() returns None
```

### Judge (score + feedback)

```python
async def judge_trajectory(trajectory: Trajectory) -> tuple[float, str]:
    """Score trajectory 0.0-1.0 AND return textual feedback.

    Returns:
        (score, feedback) — feedback explains WHY the score is what it is.
    """
    # Score dimensions (not just average):
    # - Depth: revision count, thought chain length
    # - Breadth: tactic variety, branch exploration
    # - Quality: non-obvious insights, specific vs generic
    # - Structure: proper XML tags, phase execution

    # Textual feedback examples:
    # "Score 0.4: Meta-analysis was shallow — real_need just rephrased surface_ask.
    #  Divergent phase produced only 3 options, all obvious. No revision tags used."
    # "Score 0.8: Good depth. 4 revisions that actually changed reasoning.
    #  Weak on adversarial — failure scenario was generic 'it might not work'."
    ...
```

### Eval Cache

Prevents redundant evaluations. A candidate's components dict hashed with SHA-256 × example_id = cache key.

```python
import hashlib, json

def candidate_hash(candidate: Candidate) -> str:
    """Deterministic hash of candidate's component values.
    Source: gepa/core/state.py — uses sorted dict for stability."""
    serialized = json.dumps(candidate.components, sort_keys=True)
    return hashlib.sha256(serialized.encode()).hexdigest()

async def eval_with_cache(
    candidate: Candidate,
    example_id: str,
    state: OptimizerState,
) -> tuple[float, str]:
    """Check cache before evaluating. Returns (score, feedback)."""
    key = (candidate_hash(candidate), example_id)
    if key in state.eval_cache:
        entry = state.eval_cache[key]
        return entry.score, entry.feedback

    traj = await run_mcp_session(example_id, candidate.components)
    score, feedback = await judge_trajectory(traj)
    state.eval_cache[key] = EvalCacheEntry(score=score, feedback=feedback)
    return score, feedback


async def full_eval(
    candidate: Candidate,
    examples: list[str],
    state: OptimizerState,
) -> None:
    """Run eval_with_cache on all examples, populate candidate.per_instance_scores."""
    for ex_id in examples:
        score, feedback = await eval_with_cache(candidate, ex_id, state)
        candidate.per_instance_scores[ex_id] = score


def _get_candidate(candidate_id: int, state: OptimizerState) -> Candidate | None:
    """Lookup candidate by ID in the archive."""
    for c in state.candidates:
        if c.id == candidate_id:
            return c
    return None
```

### Main Loop

**Source: `gepa/core/engine.py`** — The loop structure matches GEPA exactly: save state → increment → try merge (event-driven) → if no merge, reflective mutation → accept/reject → full eval on accept → Pareto update.

```
┌─────────────────────────────────────────────────────────────────┐
│ 0. SETUP                                                         │
├─────────────────────────────────────────────────────────────────┤
│ state = load_checkpoint() or OptimizerState()                    │
│ if fresh: seed with original component values as Candidate #0    │
│   full_eval(candidate_0) → update Pareto front                   │
│ examples = load_examples("prompts.json")                         │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 1. SAVE + INCREMENT                                              │
├─────────────────────────────────────────────────────────────────┤
│ save_checkpoint(state)                                           │
│ state.generation += 1                                            │
│ state.last_iter_found_new_program = False                        │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 2. TRY MERGE (event-driven, NOT periodic)                        │
├─────────────────────────────────────────────────────────────────┤
│ if should_try_merge(state):           # merges_due > 0 AND      │
│   merged = try_merge(state)           # last_iter found new AND  │
│   if merged:                          # budget remaining         │
│     full_eval(merged, examples)                                  │
│     parent_a, parent_b = get parents from merged.parent_ids      │
│     merged_sum = sum(merged.per_instance_scores.values())        │
│     threshold = max(sum(a.scores), sum(b.scores))                │
│     if merged_sum >= threshold:       # >= not > (GEPA merge.py) │
│       state.candidates.append(merged)                            │
│       update_pareto_front(state, merged)                         │
│       state.last_iter_found_new_program = True                   │
│     continue  # Skip mutation this iteration (GEPA engine.py)    │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 3. SELECT PARENT (uniform random from Pareto front)              │
├─────────────────────────────────────────────────────────────────┤
│ parent = select_parent(state)                                    │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 4. SELECT COMPONENT (round-robin per candidate)                  │
├─────────────────────────────────────────────────────────────────┤
│ comp_name = component_order[parent.round_robin_index % 26]       │
│ parent.round_robin_index += 1                                    │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 5. PROPOSE MUTATION (self-contained reflective proposer)         │
├─────────────────────────────────────────────────────────────────┤
│ result = propose_mutation(parent, comp_name, state, examples)    │
│ if result is None:                                               │
│   continue  # Reflection failed to produce valid proposal        │
│ mutation, parent_trajs, mut_trajs = result                       │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 6. ACCEPT/REJECT (strict improvement on minibatch)               │
├─────────────────────────────────────────────────────────────────┤
│ parent_sum = sum(t.score for t in parent_trajs)                  │
│ mut_sum = sum(t.score for t in mut_trajs)                        │
│ if mut_sum > parent_sum:                 # Strict > (not >=)     │
│   state.candidates.append(mutation)                              │
│   state.last_iter_found_new_program = True                       │
│   # Schedule merge opportunity (GEPA event-driven pattern)       │
│   if state.total_merges_tested < state.max_merge_invocations:    │
│     state.merges_due += 1                                        │
│   # Stage 2: full validation                                     │
│   full_eval(mutation, examples)                                  │
│   update_pareto_front(state, mutation)                            │
│ else:                                                            │
│   discard mutation  # No full eval — budget saved                │
└─────────────────────────────────────────────────────────────────┘
                              ↓
             Repeat until eval budget exhausted
```

**Key GEPA-matching behaviors:**
- Merge skips mutation that iteration (`continue` after merge attempt)
- `propose_mutation()` is self-contained (samples, evals parent, reflects, evals mutation)
- `propose_mutation()` returns `None` on failure — loop continues gracefully
- Merge acceptance uses `>=` (allows equal), mutation uses `>` (strict improvement)
- `merges_due` incremented only on successful mutation AND if merge budget remains
- `last_iter_found_new_program` gates merge attempts (no merge after failed iterations)

### Key Functions

```python
# reasoning_mcp/optimizer/state.py
@dataclass class Candidate: ...          # id, parent_ids, components, per_instance_scores
@dataclass class EvalCacheEntry: ...     # score, feedback
@dataclass class OptimizerState: ...     # candidates, pareto_front_by_instance, eval_cache, rng, ...
def update_pareto_front(state, candidate) -> list[int]: ...  # Returns displaced IDs
def get_front_candidate_ids(state) -> set[int]: ...
def candidate_hash(candidate) -> str: ...                    # SHA-256 for eval cache

# reasoning_mcp/optimizer/selection.py
def select_parent(state) -> Candidate: ...                   # Uniform random from front

# reasoning_mcp/optimizer/sampling.py
def sample_minibatch(state, examples, batch_size=3) -> list[str]: ...  # Epoch-shuffled

# reasoning_mcp/optimizer/merge.py
def should_try_merge(state) -> bool: ...                     # Event-driven trigger
def try_merge(state, max_attempts=10) -> Candidate | None: ...
def get_ancestors(candidate, state) -> set[int]: ...         # Parent graph traversal

# reasoning_mcp/optimizer/runner.py
async def run_mcp_session(question, components) -> Trajectory: ...

# reasoning_mcp/optimizer/judge.py
async def judge_trajectory(trajectory) -> tuple[float, str]: ...  # (score, feedback)

# reasoning_mcp/optimizer/reflect.py
async def propose_mutation(parent, component_name, state, examples) -> tuple | None: ...
def build_reflective_dataset(trajectories) -> list[dict]: ...
async def call_reflection_llm(component_name, current_value, dataset) -> str | None: ...

# reasoning_mcp/optimizer/eval.py
async def eval_with_cache(candidate, example_id, state) -> tuple[float, str]: ...
async def full_eval(candidate, examples, state) -> None: ...  # Populates per_instance_scores

# reasoning_mcp/optimizer/components.py
def load_components() -> dict[str, str]: ...
def apply_components(components: dict[str, str]) -> None: ...

# reasoning_mcp/optimizer/checkpoint.py
def save_checkpoint(state, path) -> None: ...
def load_checkpoint(path) -> OptimizerState | None: ...

# reasoning_mcp/optimizer/loop.py
async def optimize(examples, max_evals=500) -> OptimizerState: ...
```

### Injection Mechanism

Same as v3 — module-level mutation. The MCP server runs in-process via Agent SDK.

```python
import reasoning_mcp.tactics as tactics_mod
import reasoning_mcp.prompts as prompts_mod

def apply_components(components: dict[str, str]) -> None:
    for name, value in components.items():
        if name.startswith("TACTICS."):
            tactic_name = name.split(".")[1]
            tactics_mod.TACTICS[tactic_name]["guidance"] = value
        elif name.startswith("STYLE_PROMPTS."):
            style_name = name.split(".")[1]
            prompts_mod.STYLE_PROMPTS[style_name] = value
        elif name.startswith("STAGE_PROMPTS."):
            stage_name = name.split(".")[1]
            prompts_mod.STAGE_PROMPTS[stage_name] = value
```

## Implementation Phases

1. **State + Data Model** — `Candidate`, `OptimizerState`, per-instance-best Pareto front, eval cache
2. **Selection + Sampling** — Uniform random from front, epoch-shuffled minibatch with seeded RNG
3. **Runner** — Claude Agent SDK integration, trajectory capture with `ToolCall` objects
4. **Judge** — Returns `(score, feedback_text)`, multi-dimensional scoring
5. **Reflective Mutation** — Self-contained proposer: minibatch eval → `build_reflective_dataset()` → GEPA prompt template → LLM → extract from code blocks → eval mutation → return `tuple | None`
6. **Merge** — Ancestry graph traversal, random pair sampling, desirable predictor filter, event-driven scheduling
7. **Eval** — Cache with SHA-256 hashing, `full_eval()` populating per-instance scores
8. **Main Loop** — Event-driven merge → self-contained propose → accept/reject → Pareto update → checkpoint
9. **CLI** — `python -m reasoning_mcp.optimizer --examples prompts.json --max-evals 500`

## GEPA Equivalence Checklist

| GEPA Component | Source File | v4.1 Section | Status |
|----------------|-------------|------------|--------|
| Candidate population | `core/state.py` | `OptimizerState.candidates` | EQUIVALENT — unbounded archive |
| Per-instance scores | `core/state.py` | `Candidate.per_instance_scores` | EQUIVALENT |
| Pareto front | `core/state.py` | `update_pareto_front()` | EQUIVALENT — per-instance-best, NOT classic dominance |
| Parent selection | `strategies/candidate_selector.py` | `select_parent()` | APPROXIMATED — uniform random from front (GEPA's `select_program_candidate_from_pareto_front()` internals unverifiable) |
| Round-robin component | `strategies/component_selector.py` | Per-candidate `round_robin_index` | EQUIVALENT |
| Epoch-shuffled batches | `strategies/batch_sampler.py` | `sample_minibatch()` | EQUIVALENT — seeded RNG, padding |
| Two-stage eval gating | `core/engine.py` | Steps 5-6 in main loop | EQUIVALENT — minibatch then full eval |
| Strict-improvement accept | `core/engine.py` | `mut_sum > parent_sum` | EQUIVALENT — strict `>` for mutation |
| Merge acceptance | `proposer/merge.py` | `merged_sum >= threshold` | EQUIVALENT — `>=` for merge (not strict) |
| Textual feedback | `core/adapter.py` | `judge_trajectory() → (score, feedback)` | EQUIVALENT — judge returns both |
| Reflective dataset | `core/adapter.py` | `build_reflective_dataset()` | EQUIVALENT — structured records (input, output, score, feedback) |
| Reflection prompt | `strategies/instruction_proposal.py` | `REFLECTION_PROMPT` template | EQUIVALENT — GEPA's exact template structure |
| Self-contained proposer | `proposer/reflective_mutation/` | `propose_mutation()` | EQUIVALENT — evals parent, reflects, evals mutation, returns `None` on failure |
| Common-ancestor merge | `proposer/merge.py` | `try_merge()` | EQUIVALENT — random pairs, ancestry graph, desirable predictors, retry |
| Event-driven merge scheduling | `core/engine.py` | `should_try_merge()` + `merges_due` | EQUIVALENT — incremented on successful mutation |
| Ancestry tracking | `proposer/merge.py` | `get_ancestors()` + `parent_ids: list[int]` | EQUIVALENT — full graph traversal |
| Eval caching | `core/state.py` | `eval_with_cache()` + SHA-256 hash | EQUIVALENT |
| Deterministic RNG | throughout | `state.rng` (seeded `random.Random`) | EQUIVALENT |
| Checkpointing | `core/state.py` | `save_checkpoint()` / `load_checkpoint()` | EQUIVALENT |

## Budget Estimation

GEPA uses eval-count budget, not generation-count. `propose_mutation()` is self-contained — it runs both parent and mutation evals internally.

Per generation:
- **Rejected mutation**: 3 MCP runs (parent) + 3 judges (parent) + 1 reflection LLM + 3 MCP runs (mutation) + 3 judges (mutation) = **13 API calls**
- **Accepted mutation**: 13 + N full validation (MCP + judge each) = **13 + 2N calls**
- **Failed proposal** (reflection returns None): 3 MCP + 3 judge + 1 reflection = **7 API calls**
- **Merge attempt**: 2N full validation calls (eval both parents if not cached + merged)

With 15 examples and ~30% acceptance rate:
- 100 generations ≈ 70 × 13 (rejected) + 30 × (13 + 30) (accepted) = 2,200 API calls
- MCP runner calls ≈ $0.01-0.02 (Haiku)
- Judge/reflection calls ≈ $0.03-0.05 (Sonnet)
- Estimated cost: **$50-120 per optimization run**

## Open Questions

1. **Claude Agent SDK**: Need to verify exact import path and MCP loading API. Fallback: subprocess + JSON-RPC.
2. **Judge model**: Use Sonnet for judging/reflection (quality matters) vs Haiku for trajectory generation (volume matters)?
3. ~~**Merge frequency**~~: RESOLVED — event-driven via `merges_due` counter, capped by `max_merge_invocations`. Matches GEPA exactly.

## Next Step

Build Phase 1: `reasoning_mcp/optimizer/state.py` — Candidate, OptimizerState, Pareto front logic.
