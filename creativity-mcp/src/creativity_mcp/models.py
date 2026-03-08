"""Data models for the Creativity MCP."""
from dataclasses import dataclass, field


@dataclass
class Branch:
    """A creative branch/idea in the exploration."""

    id: str
    content: str
    is_weird: bool = False
    depth: int = 1
    parent_id: str | None = None
    constraints_applied: list[str] = field(default_factory=list)
    lane: str | None = None
    archived: bool = False

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "content": self.content,
            "is_weird": self.is_weird,
            "depth": self.depth,
            "parent_id": self.parent_id,
            "constraints_applied": self.constraints_applied,
            "lane": self.lane,
            "archived": self.archived,
        }


@dataclass
class Constraint:
    """A creative constraint injected to force new directions."""

    id: str
    text: str
    branches_before: int = 0

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "text": self.text,
            "branches_before": self.branches_before,
        }


@dataclass
class PruneRecord:
    """Record of a pruned branch with reason."""

    branch_id: str
    fatal_flaw: str
    rejected: bool = False
    rejection_reason: str | None = None


@dataclass
class Session:
    """Tracks session state through the creativity workflow."""

    id: str
    challenge: str
    domain: str | None = None
    branches: list[Branch] = field(default_factory=list)
    constraints: list[Constraint] = field(default_factory=list)
    pruned: list[PruneRecord] = field(default_factory=list)
    harvested: bool = False
    used_concept_domains: list[str] = field(default_factory=list)  # Track distant concepts used

    @property
    def branch_count(self) -> int:
        return len(self.active_branches)

    @property
    def total_branch_count(self) -> int:
        return len(self.branches)

    @property
    def weird_branch_exists(self) -> bool:
        return any(b.is_weird for b in self.active_branches)

    @property
    def min_branch_depth(self) -> int:
        active = self.active_branches
        if not active:
            return 0
        return min(b.depth for b in active)

    @property
    def constraint_count(self) -> int:
        return len(self.constraints)

    @property
    def active_branches(self) -> list[Branch]:
        return [b for b in self.branches if not b.archived]

    def can_harvest(self) -> bool:
        """Check if session meets harvest requirements (archived branches excluded)."""
        active = self.active_branches
        return (
            len(active) >= 5
            and any(b.is_weird for b in active)
            and min((b.depth for b in active), default=0) >= 2
            and self.constraint_count >= 1
        )

    def get_branch(self, branch_id: str) -> Branch | None:
        return next((b for b in self.branches if b.id == branch_id), None)
