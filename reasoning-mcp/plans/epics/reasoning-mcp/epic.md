# Epic: Reasoning MCP

## Tasks

### Task 1: Reasoning MCP Server
**Description:** Create FastMCP server with `think` tool supporting stance/relation/tactic parameters and 19 cognitive tactics
**Required reviews:** code-quality
**Depends on:** (none)

#### Acceptance Criteria
- [ ] `pip install -e .` exits 0
- [ ] `pytest tests/ -v` exits 0 (≥8 tests covering: session creation, thought storage, relations, tactics)
- [ ] `python -c "from reasoning_mcp.tactics import TACTICS; assert len(TACTICS) == 19"` exits 0
- [ ] `timeout 2 python -m reasoning_mcp || [ $? -eq 124 ]` exits 0
- [ ] `test -f README.md && grep -q "## Installation" README.md && grep -q "## Tactics" README.md` exits 0
