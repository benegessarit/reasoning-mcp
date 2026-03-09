"""Prompts for the Generative Agent Ensemble MCP.

Each prompt guides Claude through a specific step of the ensemble reasoning workflow.
The MCP enforces structure; Claude provides the thinking.
"""

ENSEMBLE_PROMPT = """Analyze this question and generate {min_agents}+ ideal personas to reason through it.

QUESTION: {question}

Generate personas TAILORED to THIS question. Don't use generic roles — pick perspectives that illuminate THIS problem's specific tensions.

For each persona, provide:
- name: Short memorable name (e.g., "Performance Engineer", "Security Hawk", "User Advocate")
- role: Their professional identity or stance
- purpose: What perspective they bring to THIS question
- perspective: Their natural bias/focus — what they care about most

{chaos_instruction}

{orchestrator_instruction}

Respond with JSON:
{{
  "agents": [
    {{"name": "...", "role": "...", "purpose": "...", "perspective": "...", "is_chaos": false, "is_orchestrator": false}},
    ...
  ],
  "suggested_order": ["Name1", "Name2", ...]
}}

The suggested_order should sequence perspectives for productive dialogue — usually start with the most enthusiastic/optimistic, let others challenge, chaos agent stress-tests, orchestrator assesses progress and pushes for depth."""

CHAOS_INSTRUCTION = """IMPORTANT: One persona MUST be a chaos/perturbation agent (is_chaos: true).
This agent expands the aperture and hunts incompleteness. Their questions:
- "What if...?" — Explore alternative scenarios we haven't considered
- "What else are we missing?" — Surface blind spots in the discussion
- "What other angles exist?" — Find perspectives no one has taken
- "Is our reasoning incomplete?" — Identify gaps in the logical chain
- "What haven't we questioned?" — Challenge silent assumptions

The chaos agent INSERTS RANDOMLY — not on a fixed schedule. They interject whenever the discussion gets too comfortable or linear. Examples:
- "Aperture Expander" — What possibilities aren't we seeing?
- "Gap Hunter" — What's missing from this analysis?
- "Angle Finder" — Who else has a stake we forgot?
- "Incompleteness Detector" — Where did we stop thinking too soon?

Name the chaos agent appropriately for THIS question's domain."""

INVOKE_PROMPT = """You ARE {agent_name}. Stay COMPLETELY in character for this entire response.

YOUR IDENTITY:
- Role: {agent_role}
- Purpose: {agent_purpose}
- Perspective: {agent_perspective}

QUESTION: {question}

{prior_context}

{additional_context}

**CONSTRAINT: 150 WORDS MAXIMUM.** Be dense, direct, high-signal. Every word must earn its place.

Respond AS {agent_name}. Be specific, opinionated, true to your perspective.
- Bring your unique viewpoint — that's why you exist in this ensemble
- Challenge prior speakers where your perspective differs
- Raise specific questions or concerns from your vantage point

End with JSON:
{{
  "response": "Your full response in character...",
  "raises": ["Specific questions or concerns you raise"],
  "suggests_next": "Agent name who should speak next, OR 'synthesize' if perspectives complete"
}}"""

PRIOR_CONTEXT_TEMPLATE = """PRIOR DISCUSSION:
{invocations}

Build on, challenge, or extend what's been said. Your perspective matters because it differs."""

PERTURB_PROMPT = """You are a chaos engineer testing reasoning robustness.

TARGET TO PERTURB: {target}
PERTURBATION MODE: {mode}

Modes:
- negate: Assume the opposite is true
- remove: Assume this doesn't exist/apply
- extreme: Assume this is 10x more/less than expected
- opposite: Flip the framing entirely

CURRENT REASONING CONTEXT:
{context}

Apply the perturbation and assess honestly: does the reasoning survive?

Respond with JSON:
{{
  "perturbation": "What you changed and how",
  "impact": "survives" | "breaks" | "weakens",
  "explanation": "Why the reasoning survives/breaks/weakens under this perturbation"
}}

Be rigorous. If the perturbation reveals a real weakness, say so."""

SYNTHESIZE_PROMPT = """Synthesize the multi-perspective discussion into a clear conclusion.

ORIGINAL QUESTION: {question}

DISCUSSION:
{invocations}

{perturbations}

Your task: Integrate all perspectives into a coherent conclusion.
- Don't paper over disagreements — acknowledge them
- Track what assumptions the conclusion depends on
- Note where confident vs. uncertain

Respond with JSON:
{{
  "conclusion": "Your synthesized conclusion — clear, actionable, grounded in the discussion",
  "confidence": 0.0-1.0,
  "dissent": "What agents disagreed on that remains unresolved (or null if resolved)",
  "key_tensions": ["Tensions between perspectives that shaped the conclusion"],
  "assumptions": ["Assumptions this conclusion rests on — if wrong, conclusion changes"]
}}"""

PERTURBATIONS_CONTEXT = """
PERTURBATIONS APPLIED:
{perturbations}

Factor perturbation results into your synthesis — what survived? What broke?"""

# =============================================================================
# ORCHESTRATOR - The demanding thesis advisor who won't let you off easy
# =============================================================================

ORCHESTRATOR_INSTRUCTION = """IMPORTANT: One persona MUST be the Orchestrator (is_orchestrator: true).
The Orchestrator is a meta-observer who:
- Assesses whether the discussion is actually making progress or just circling
- Identifies perspectives NOT YET heard that would illuminate the question
- Detects premature consensus and comfortable agreement that papers over real tensions
- Demands that raised questions actually get answered, not ignored
- Decides when to go deeper vs. when to pivot vs. when synthesis is genuinely ready

Name them something fitting: "Discussion Director", "Devil's Editor", "Socratic Prod", etc."""

ORCHESTRATOR_INVOKE_PROMPT = """You are the ORCHESTRATOR — the demanding thesis advisor who won't let this discussion settle for mediocrity.

YOUR JOB: Meta-observe this discussion and PUSH for genuine insight.

QUESTION BEING EXPLORED: {question}

DISCUSSION SO FAR:
{prior_context}

AGENTS AVAILABLE: {available_agents}
AGENTS WHO HAVE SPOKEN: {agents_spoken}
UNANSWERED QUESTIONS RAISED: {unanswered_questions}

---

ASSESS THE DISCUSSION STATE:

1. **PROGRESS CHECK**: Is this discussion actually advancing toward insight, or are people talking past each other / repeating themselves / staying surface-level?

2. **COVERAGE AUDIT**: What perspectives are MISSING? Who hasn't spoken that should? What viewpoint would challenge the emerging consensus?

3. **TENSION DETECTOR**: Are there real disagreements being papered over with vague language? ("It depends" is usually a cop-out. "We need to balance X and Y" often means we haven't actually decided.)

4. **QUESTION GRAVEYARD**: What questions were raised but never answered? These are often the most important ones — they got uncomfortable so everyone moved on.

5. **DEPTH CHECK**: Are we exploring the REAL question or a comfortable proxy? Often discussions settle on an easier version of the hard question.

6. **PREMATURE SYNTHESIS ALARM**: If someone suggests "ready to synthesize" — are we ACTUALLY ready? Or are we just tired of thinking?

7. **CHAOS INJECTION**: The chaos agent should NOT follow a fixed order. RANDOMLY inject them when:
   - Discussion feels too linear or comfortable
   - Everyone is agreeing too easily
   - A perspective hasn't been questioned in 2+ turns
   - You sense the group is missing something obvious
   Chaos keeps the discussion honest. Use them unpredictably.

---

YOUR RESPONSE MUST:

Be SPECIFIC. Don't say "we should explore more perspectives" — say WHICH perspective and WHY it would add value.

Be DEMANDING. Your job is to make this discussion uncomfortable when it's being lazy. Comfortable consensus is usually wrong.

Be DIRECTIVE. Tell the ensemble exactly what to do next: which agent, what question to address, what tension to resolve.

---

Respond with JSON:
{{
  "assessment": {{
    "progress": "advancing | circling | stuck | premature",
    "coverage_gaps": ["Perspective X not heard because...", "Viewpoint Y would challenge..."],
    "unresolved_tensions": ["Agent A said X but Agent B said Y — no one resolved this"],
    "buried_questions": ["This question was raised but ignored: ..."],
    "depth_concern": "Are we on the real question or a proxy?"
  }},
  "verdict": "continue | go_deeper | pivot | challenge | ready_to_synthesize",
  "directive": {{
    "action": "What exactly should happen next",
    "agent": "Which agent should speak (or null if synthesize)",
    "focus": "The specific question or tension they must address",
    "push": "The uncomfortable thing someone needs to say"
  }},
  "orchestrator_note": "Your honest assessment of this discussion's quality so far"
}}

---

PUSH HARD. A good discussion should feel uncomfortable at points. If everyone agrees easily, someone isn't thinking hard enough."""

# =============================================================================
# DEPTH PROBE - Metacognitive check before committing to an approach
# =============================================================================

DEPTH_PROBE_PROMPT = """STOP. Before you think, interrogate your thinking.

QUESTION: {question}

You're about to reason through this. First, audit the reasoning process itself.

---

**AM I FRAMING THIS RIGHT?**
Is the question I'm about to answer the REAL question? Or am I solving a proxy, a symptom, a comfortable reframing? What's the actual problem underneath?

**WHAT KIND OF THINKING DOES THIS REQUIRE?**
Systems thinking or linear? Creative or analytical? Precise or directional? Fast or slow? Am I about to use the wrong cognitive tool for this job?

**WHERE WILL MY REASONING BE SHALLOW?**
What parts will I skate over? Where will I be satisfied with surface-level when depth is needed? Name the sections I'll be tempted to hand-wave.

**WHAT DIMENSIONS AM I NOT SEEING?**
Technical, political, temporal, emotional, second-order effects, stakeholder perspectives, failure modes—which lenses am I not even picking up?

**WHERE WOULD A MASTER REASONER INTERVENE?**
If someone who thinks for a living watched my process, where would they stop me? Not disagree with my conclusion—critique my METHOD.

---

Respond with JSON:
{{
  "reframing": "The real question underneath, or 'framing is correct' if it is",
  "thinking_required": "The type of reasoning this actually needs",
  "shallow_spots": "Where my analysis will be thin if I don't force depth",
  "missing_dimensions": "Lenses I'm not applying",
  "process_critique": "Where a master reasoner would intervene in my method"
}}

This isn't about the answer. It's about whether your reasoning process is up to the task."""

# JSON response schema shared by all depth probe modes
_DEPTH_PROBE_JSON_SCHEMA = """Respond with JSON:
{{
  "reframing": "The real question underneath, or 'framing is correct' if it is",
  "thinking_required": "The type of reasoning this actually needs",
  "shallow_spots": "Where my analysis will be thin if I don't force depth",
  "missing_dimensions": "Lenses I'm not applying",
  "process_critique": "Where a master reasoner would intervene in my method"
}}"""

DEPTH_PROBE_PROMPTS = {
    # Pre-resolve double braces so all modes work uniformly with .replace()
    "vanilla": DEPTH_PROBE_PROMPT.replace("{{", "{").replace("}}", "}"),

    "failure": """STOP. Before you think, hunt for plausible wrong answers.

QUESTION: {{question}}

You're about to reason through this. First, map the failure landscape.

---

**WHAT ARE THE MOST PLAUSIBLE WRONG ANSWERS?**
List the answers that FEEL right but aren't. What makes each seductive — what true thing does it build on before going wrong?

**WHERE DOES EACH WRONG PATH DIVERGE FROM TRUTH?**
For each plausible wrong answer: identify the exact moment the reasoning goes off track. What assumption slips in unnoticed?

**WHICH WRONG ANSWER AM I MOST LIKELY TO GIVE?**
Be honest. Which failure mode matches your default reasoning pattern? Why will you be drawn to it?

**WHAT WOULD MAKE THE WRONG ANSWER CORRECT?**
Under what conditions would each plausible wrong answer actually be right? This reveals hidden assumptions about the problem.

**WHERE WOULD A MASTER REASONER INTERVENE?**
If someone who thinks for a living watched my process, where would they stop me? Not disagree with my conclusion—critique my METHOD.

---

{json_schema}

This isn't about the answer. It's about mapping failure modes before they happen.""".format(json_schema=_DEPTH_PROBE_JSON_SCHEMA),

    "assumption": """STOP. Before you think, excavate the hidden premises.

QUESTION: {{question}}

You're about to reason through this. First, audit what the question silently assumes.

---

**WHAT UNSTATED ASSUMPTIONS DOES THIS QUESTION BAKE IN?**
List every premise the question takes for granted. Include framings, scope limitations, and implied values. The question itself constrains the answer space — how?

**WHICH ASSUMPTIONS ARE MOST LIKELY WRONG?**
Rank by fragility. Which assumed premises would change the answer most dramatically if false?

**WHAT WOULD CHANGE IF EACH ASSUMPTION WERE FALSE?**
For each key assumption: what different question would you be answering? What different answer would be correct?

**WHAT QUESTION SHOULD HAVE BEEN ASKED INSTEAD?**
If you could rewrite the question without its hidden assumptions, what would it become? Is the rewritten question more honest?

**WHERE WOULD A MASTER REASONER INTERVENE?**
If someone who thinks for a living watched my process, where would they stop me? Not disagree with my conclusion—critique my METHOD.

---

{json_schema}

This isn't about the answer. It's about whether the question deserves the answer you're about to give it.""".format(json_schema=_DEPTH_PROBE_JSON_SCHEMA),

    "stakeholder": """STOP. Before you think, find the people who'd disagree.

QUESTION: {{question}}

You're about to reason through this. First, populate the room with missing perspectives.

---

**WHO WOULD DISAGREE WITH THE OBVIOUS ANSWER AND WHY WOULD THEY BE RIGHT?**
Name specific stakeholders, roles, or perspectives that would challenge the consensus view. What do they see that the majority misses?

**WHAT PERSPECTIVE AM I NOT SEEING?**
Which viewpoint is structurally invisible from your position? Who has skin in the game that you're ignoring? Whose costs are you externalizing?

**WHAT WOULD EACH DISSENTER PRIORITIZE?**
For each missing perspective: what's their #1 concern? How does it reshape the problem?

**WHERE IS THE OBVIOUS ANSWER ACTUALLY SOMEONE ELSE'S PROBLEM?**
The "right" answer often just shifts costs. Who bears the cost of the obvious solution? Would they agree it's obvious?

**WHERE WOULD A MASTER REASONER INTERVENE?**
If someone who thinks for a living watched my process, where would they stop me? Not disagree with my conclusion—critique my METHOD.

---

{json_schema}

This isn't about the answer. It's about whether your reasoning includes the people who'll live with the consequences.""".format(json_schema=_DEPTH_PROBE_JSON_SCHEMA),

    "meta": """STOP. A previous probe already examined this question. Now examine what that probe missed.

QUESTION: {{question}}

PREVIOUS PROBE FINDINGS:
{{prior}}

The previous probe gave you a frame. Now break that frame.

---

**WHAT DID THAT FRAMING MISS?**
Every frame is a window — it shows something and hides something. What's hidden by the previous probe's perspective?

**WHAT'S INVISIBLE FROM THAT FRAME?**
Not just "missing" — structurally invisible. What can't you see from the vantage point the previous probe established?

**WHERE DID THE PREVIOUS PROBE GO SHALLOW?**
Which of its findings feel complete but aren't? Where did it satisfy itself too easily?

**WHAT WOULD A SECOND OPINION LOOK LIKE?**
If you asked a completely different kind of thinker to probe this question, what would they focus on that the first probe didn't?

**WHERE WOULD A MASTER REASONER INTERVENE?**
If someone who thinks for a living watched the COMBINED probing process, where would they stop you? What's the meta-failure in your meta-cognition?

---

{json_schema}

This isn't about the answer. It's about whether your second look is genuinely independent or just confirming the first.""".format(json_schema=_DEPTH_PROBE_JSON_SCHEMA),
}
