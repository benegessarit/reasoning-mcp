"""Lens-variant prompts for explore() orchestration.

Internal prompts used by the explore tool to run multi-lens creative exploration.
Each returns structured JSON for programmatic consumption.
"""

SPARK_INTERNAL_PROMPT = """Restate this challenge as an open exploration space.

CHALLENGE: {challenge}
{domain}

Return JSON:
{{
  "challenge": "Your open-ended restatement",
  "is_open": true
}}

Make it generative — invite many directions, not convergence."""

LENS_PROMPTS: dict[str, str] = {
    "technical": """Generate creative branches from an ENGINEERING perspective.

CHALLENGE: {challenge}

EXISTING BRANCHES:
{existing_branches}

CONSTRAINTS:
{constraints}

Think about mechanisms, systems, architectures, implementations, materials, processes, and technical tradeoffs. What engineering approaches has no one considered?

Each branch must be meaningfully different from existing ones.

Return JSON array:
[
  {{"content": "A technically-grounded direction...", "is_weird": false}},
  ...
]""",

    "human": """Generate creative branches from a HUMAN perspective.

CHALLENGE: {challenge}

EXISTING BRANCHES:
{existing_branches}

CONSTRAINTS:
{constraints}

Think about emotions, relationships, social dynamics, lived experiences, cultural context, and what people actually feel and need. What human truths has no one surfaced?

Each branch must be meaningfully different from existing ones.

Return JSON array:
[
  {{"content": "A human-centered direction...", "is_weird": false}},
  ...
]""",

    "systemic": """Generate creative branches from a SYSTEMIC perspective.

CHALLENGE: {challenge}

EXISTING BRANCHES:
{existing_branches}

CONSTRAINTS:
{constraints}

Think about feedback loops, emergent behavior, second-order effects, network dynamics, equilibria, and how parts interact to produce wholes. What systemic patterns has no one identified?

Each branch must be meaningfully different from existing ones.

Return JSON array:
[
  {{"content": "A systems-level direction...", "is_weird": false}},
  ...
]""",

    "contrarian": """Generate creative branches that INVERT ASSUMPTIONS.

CHALLENGE: {challenge}

EXISTING BRANCHES:
{existing_branches}

CONSTRAINTS:
{constraints}

Break rules. Question premises. Flip the problem. What if the opposite were true? What if the constraint everyone accepts is wrong?

IMPORTANT: At least ONE branch MUST have "is_weird": true and should break an unstated assumption or make the reader uncomfortable. Push past what feels safe.

Each branch must be meaningfully different from existing ones.

Return JSON array:
[
  {{"content": "A conventional-but-contrarian direction...", "is_weird": false}},
  {{"content": "A genuinely uncomfortable direction...", "is_weird": true}},
  ...
]""",
}

REVISIT_INTERNAL_PROMPT = """Go deeper on this specific branch.

CHALLENGE: {challenge}

BRANCH TO REVISIT:
{branch_content}

Generate 1-2 sub-branches that deepen this idea. What sub-directions exist? What would this look like taken further?

Return JSON:
{{
  "sub_branches": [
    {{"content": "A deeper exploration of this direction...", "is_weird": false}},
    ...
  ]
}}

Don't rephrase. Go deeper."""

WEIRD_INTERNAL_PROMPT = """Generate ONE genuinely weird branch.

CHALLENGE: {challenge}

EXISTING BRANCHES:
{existing_branches}

This is a fallback — the contrarian lens didn't produce anything weird enough. Push harder.

Weird means: breaks an unstated assumption, combines things that don't go together, makes you uncomfortable to suggest.

Return JSON:
{{
  "content": "Your genuinely surprising direction...",
  "is_weird": true,
  "why_weird": "What assumption this breaks or why it's surprising"
}}

"is_weird": true is mandatory. Push harder than you're comfortable with."""

PROD_INTERNAL_PROMPT = """Assess this exploration's quality.

CHALLENGE: {challenge}

BRANCHES:
{branches_summary}

Are these actually different directions or variations on the same idea? Has the space been genuinely explored or just skimmed?

Return JSON:
{{
  "verdict": "push_harder" or "acceptable",
  "directive": "What specifically should happen next"
}}

"acceptable" requires genuine exhaustion of the space, not fatigue."""

HARVEST_SUMMARY_PROMPT = """Collect and summarize the viable branches from this exploration.

CHALLENGE: {challenge}

BRANCHES:
{branches}

Group related branches. Present ALL viable directions without picking a winner or combining them. The caller decides what to do with these.

Return a grouped summary of the exploration results."""
