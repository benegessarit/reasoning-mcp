# Task 1: Reasoning MCP Server

## Summary

Create FastMCP server with `think` tool supporting stance/relation/tactic parameters and 19 cognitive tactics.

## Project Structure

```
reasoning-mcp/
├── pyproject.toml
├── README.md
├── src/
│   └── reasoning_mcp/
│       ├── __init__.py
│       ├── server.py      # FastMCP server + think tool
│       ├── models.py      # Thought dataclass
│       ├── tactics.py     # 19 tactics dict
│       └── __main__.py    # Entry point
└── tests/
    ├── test_server.py     # Session, thought storage
    ├── test_relations.py  # Relation validation
    ├── test_tactics.py    # Tactic lookup
    └── test_integration.py # Full workflow
```

## Implementation

### models.py

```python
from dataclasses import dataclass, field

@dataclass
class Thought:
    id: int
    stance: str  # expand, refine, commit
    content: str
    branch: str | None = None
    relation: str | None = None
    targets: list[int] = field(default_factory=list)
    tactic: str | None = None
```

### server.py

```python
from mcp.server.fastmcp import FastMCP
from typing import Literal
import uuid

mcp = FastMCP("reasoning_mcp")
sessions: dict[str, list[Thought]] = {}

@mcp.tool()
async def think(
    stance: Literal["expand", "refine", "commit"],
    content: str,
    relation: Literal["builds", "revises", "forks", "attacks", "synthesizes", "concludes"] | None = None,
    targets: list[int] | None = None,
    tactic: str | None = None,
    session_id: str | None = None,
) -> dict:
    # Auto-generate session_id if not provided
    # Validate: relation requires non-empty targets
    # Validate: targets must exist in session
    # Validate: tactic must be in TACTICS (return list if invalid)
    # Store thought, return response with guidance if tactic specified
```

### tactics.py

```python
TACTICS: dict[str, dict] = {
    "META_ANALYSIS": {
        "style": "special",
        "default_stance": "expand",
        "outputs": ["surface_ask", "real_need", "unstated_context", "failure_modes", "optimal_response"],
        "guidance": "What did they literally ask? What do they actually need?",
    },
    "WILD_OPTIONS": {
        "style": "divergent",
        "default_stance": "expand",
        "outputs": ["options", "weird_one"],
        "guidance": "Generate freely. No filtering. Quantity over quality.",
    },
    # All 19: META_ANALYSIS, WILD_OPTIONS, HYPOTHESES, ALTERNATIVES, INVERSION, PRIOR_ART,
    # EVIDENCE_AUDIT, COMPLEXITY_INVENTORY, STEEL_MAN_OPPOSITE, GAP_ANALYSIS, CONTRADICTION,
    # META_AUDIT, PREMORTEM, FAILURE_MODES, BRANCH_EXPLORE, ANTIREZ_TEST, VERDICT, PICK, NEXT_ACTION
}
# Use TACTICS.get(name.upper()) and list(TACTICS) directly - no wrapper functions
```

### __main__.py

```python
def main():
    from reasoning_mcp.server import mcp
    mcp.run()

if __name__ == "__main__":
    main()
```

### pyproject.toml

```toml
[project]
name = "reasoning-mcp"
version = "0.1.0"
description = "MCP server for structured reasoning with tactics"
readme = "README.md"
requires-python = ">=3.10"
dependencies = ["mcp>=1.0.0", "pydantic>=2.0.0"]

[project.scripts]
reasoning-mcp = "reasoning_mcp.__main__:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

## Acceptance Criteria

- [ ] `pip install -e .` exits 0
- [ ] `pytest tests/ -v` exits 0 (≥8 tests covering: session creation, thought storage, relations, tactics)
- [ ] `python -c "from reasoning_mcp.tactics import TACTICS; assert len(TACTICS) == 19"` exits 0
- [ ] `timeout 2 python -m reasoning_mcp || [ $? -eq 124 ]` exits 0
- [ ] `test -f README.md && grep -q "## Installation" README.md && grep -q "## Tactics" README.md` exits 0

## Reviews

- `code-quality`

## Testing

- test_server.py: session creation, thought append, stance validation (3 tests)
- test_relations.py: valid relation, invalid target, relation without targets (3 tests)
- test_tactics.py: 19 tactics exist, invalid tactic returns list, guidance included (3 tests)
- test_integration.py: multi-step workflow with relations and tactics (1-2 tests)
