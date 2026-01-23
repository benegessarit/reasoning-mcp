# Critique Report: reasoning-mcp Specs

**Date:** 2026-01-29
**Round:** 1
**Verdict:** REVISE REQUIRED

---

## Executive Summary

4 auditors analyzed the specs. Found 1 P0 blocker and 5 P1 improvements. The linear dependency chain (Task 1→2→3→4) is correct. All 19 tactics remain in scope per user's explicit request.

---

## P0 Blocker (Must Fix)

### Missing `branch` field for BRANCH_EXPLORE tactic

**Evidence:** Plan line 137 defines branching support, Task 3 line 48 lists BRANCH_EXPLORE tactic, but no spec adds the required field to the Thought dataclass.

**Impact:** Worker implementing Task 3 will discover mid-implementation that the data structure doesn't support branching.

**Fix for `task-1-scaffold-core-spec.md`:**

```python
# In models.py, update Thought:
@dataclass
class Thought:
    id: int
    stance: str
    content: str
    branch: str | None = None  # NEW - For BRANCH_EXPLORE tactic
```

---

## P1 Improvements (Recommended)

### 1. Delete Session class wrapper

**File:** `task-1-scaffold-core-spec.md` lines 38-41

**Current:**
```python
@dataclass
class Session:
    id: str
    thoughts: list[Thought]

sessions: dict[str, Session] = {}
```

**Fix:**
```python
# Delete Session class entirely
sessions: dict[str, list[Thought]] = {}
```

**Rationale:** Session is a wrapper around a list with zero logic. Dict key is already the session ID.

---

### 2. Delete next_needed parameter

**Files:** `task-1-scaffold-core-spec.md` line 50, `task-2-relations-spec.md` line 38

**Issue:** Config option with no use case for False value.

**Fix:** Remove from:
- Parameter signature
- Return dict

Add back when you have ONE real case where it's False.

---

### 3. Delete wrapper functions

**File:** `task-3-tactics-spec.md` lines 37-41

**Current:**
```python
def get_tactic(name: str) -> dict | None:
    return TACTICS.get(name.upper())

def list_tactics() -> list[str]:
    return list(TACTICS.keys())
```

**Fix:** Delete both. Call `TACTICS.get(name.upper())` and `list(TACTICS)` directly.

---

### 4. Use final entry point pattern in Task 1

**Files:** `task-1-scaffold-core-spec.md` lines 52-56, `task-4-verify-spec.md` lines 70-77

**Issue:** Task 1 creates `__main__.py` with inline `mcp.run()`, Task 4 rewrites it with `main()` wrapper.

**Fix:** Use Task 4's pattern in Task 1 from the start:
```python
def main():
    from reasoning_mcp.server import mcp
    mcp.run()

if __name__ == "__main__":
    main()
```

---

### 5. pytest "passes" → "exits 0"

**Files:** All spec files

**Issue:** Inconsistent exit code specification.

**Fix:** Change all instances of `pytest ... passes` to `pytest ... exits 0`:
- `task-1-scaffold-core-spec.md` line 65
- `task-2-relations-spec.md` line 60
- `task-3-tactics-spec.md` line 76
- `task-4-verify-spec.md` line 84

---

## Rejected Recommendations

### "Start with 3 tactics, not 19"

**Source:** simplicity-auditor

**Rejected because:** User explicitly requested all 19 tactics:
> "add all of the named phases... all specific tactics must be in, everything from compose thinking"

This is intentional scope, not YAGNI.

---

## Dependency Analysis

**Verdict:** CLEAN ✓

Linear chain Task 1 → Task 2 → Task 3 → Task 4 is correct and necessary:
- `server.py` and `models.py` are modified by Tasks 1, 2, and 3 sequentially
- Parallel execution would cause merge conflicts
- No optimization possible without restructuring

---

## Action Items

| Priority | Item | Spec File | Line |
|----------|------|-----------|------|
| P0 | Add `branch: str \| None` to Thought | task-1-scaffold-core-spec.md | 31-36 |
| P1 | Delete Session class | task-1-scaffold-core-spec.md | 38-41, 46 |
| P1 | Delete next_needed | task-1, task-2 | Multiple |
| P1 | Delete wrapper functions | task-3-tactics-spec.md | 37-41 |
| P1 | Use main() pattern in Task 1 | task-1-scaffold-core-spec.md | 52-56 |
| P1 | pytest "exits 0" consistency | All specs | Multiple |

---

## Auditor Reports

- `/Users/davidbeyer/projects/reasoning-mcp/plans/specs/reviewer-2-decomposition.json`
- Acceptance criteria, simplicity, and dependency audits available in session transcript
