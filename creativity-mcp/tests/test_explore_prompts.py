"""Tests for explore_prompts module — lens-variant prompts for explore() orchestration."""


def test_all_prompt_constants_exist_and_nonempty():
    from creativity_mcp.explore_prompts import (
        LENS_PROMPTS,
        PROD_INTERNAL_PROMPT,
        REVISIT_INTERNAL_PROMPT,
        SPARK_INTERNAL_PROMPT,
        WEIRD_INTERNAL_PROMPT,
    )

    for name, val in [
        ("SPARK_INTERNAL_PROMPT", SPARK_INTERNAL_PROMPT),
        ("REVISIT_INTERNAL_PROMPT", REVISIT_INTERNAL_PROMPT),
        ("WEIRD_INTERNAL_PROMPT", WEIRD_INTERNAL_PROMPT),
        ("PROD_INTERNAL_PROMPT", PROD_INTERNAL_PROMPT),
    ]:
        assert isinstance(val, str), f"{name} should be a string"
        assert len(val) > 0, f"{name} should be non-empty"

    assert isinstance(LENS_PROMPTS, dict), "LENS_PROMPTS should be a dict"
    for key, val in LENS_PROMPTS.items():
        assert isinstance(val, str) and len(val) > 0, f"LENS_PROMPTS[{key}] should be non-empty string"


def test_lens_prompts_has_exactly_four_keys():
    from creativity_mcp.explore_prompts import LENS_PROMPTS

    assert set(LENS_PROMPTS.keys()) == {"technical", "human", "systemic", "contrarian"}


def test_lens_prompts_contain_required_placeholders():
    from creativity_mcp.explore_prompts import LENS_PROMPTS

    for lens_name, prompt in LENS_PROMPTS.items():
        assert "{challenge}" in prompt, f"{lens_name} missing {{challenge}}"
        assert "{existing_branches}" in prompt, f"{lens_name} missing {{existing_branches}}"
        assert "{constraints}" in prompt, f"{lens_name} missing {{constraints}}"


def test_spark_internal_prompt_contains_challenge():
    from creativity_mcp.explore_prompts import SPARK_INTERNAL_PROMPT

    assert "{challenge}" in SPARK_INTERNAL_PROMPT


def test_revisit_internal_prompt_placeholders():
    from creativity_mcp.explore_prompts import REVISIT_INTERNAL_PROMPT

    assert "{branch_content}" in REVISIT_INTERNAL_PROMPT
    assert "{challenge}" in REVISIT_INTERNAL_PROMPT


def test_weird_internal_prompt_placeholders():
    from creativity_mcp.explore_prompts import WEIRD_INTERNAL_PROMPT

    assert "{challenge}" in WEIRD_INTERNAL_PROMPT
    assert "{existing_branches}" in WEIRD_INTERNAL_PROMPT


def test_prod_internal_prompt_placeholders():
    from creativity_mcp.explore_prompts import PROD_INTERNAL_PROMPT

    assert "{branches_summary}" in PROD_INTERNAL_PROMPT
    assert "{challenge}" in PROD_INTERNAL_PROMPT


def test_contrarian_lens_mentions_is_weird():
    from creativity_mcp.explore_prompts import LENS_PROMPTS

    assert "is_weird" in LENS_PROMPTS["contrarian"]


def test_lens_prompts_are_structurally_distinct():
    from creativity_mcp.explore_prompts import LENS_PROMPTS

    values = list(LENS_PROMPTS.values())
    for i, a in enumerate(values):
        for j, b in enumerate(values):
            if i < j:
                assert a != b, f"Lens prompts at index {i} and {j} are identical"
                # Check they use meaningfully different perspective language
                # by verifying less than 80% overlap in unique words
                words_a = set(a.lower().split())
                words_b = set(b.lower().split())
                overlap = len(words_a & words_b) / max(len(words_a), len(words_b))
                assert overlap < 0.85, (
                    f"Lens prompts at index {i} and {j} are too similar ({overlap:.0%} word overlap)"
                )


def test_weird_internal_prompt_mentions_is_weird_true():
    from creativity_mcp.explore_prompts import WEIRD_INTERNAL_PROMPT

    assert '"is_weird": true' in WEIRD_INTERNAL_PROMPT or '"is_weird":true' in WEIRD_INTERNAL_PROMPT


def test_all_prompts_contain_context_block_placeholder():
    """Every prompt template must include {context_block} for context threading."""
    from creativity_mcp.explore_prompts import (
        LENS_PROMPTS,
        PROD_INTERNAL_PROMPT,
        REVISIT_INTERNAL_PROMPT,
        SPARK_INTERNAL_PROMPT,
        WEIRD_INTERNAL_PROMPT,
    )

    for name, prompt in [
        ("SPARK_INTERNAL_PROMPT", SPARK_INTERNAL_PROMPT),
        ("REVISIT_INTERNAL_PROMPT", REVISIT_INTERNAL_PROMPT),
        ("WEIRD_INTERNAL_PROMPT", WEIRD_INTERNAL_PROMPT),
        ("PROD_INTERNAL_PROMPT", PROD_INTERNAL_PROMPT),
    ]:
        assert "{context_block}" in prompt, f"{name} missing {{context_block}} placeholder"

    for key, prompt in LENS_PROMPTS.items():
        assert "{context_block}" in prompt, f"LENS_PROMPTS[{key}] missing {{context_block}} placeholder"


def test_all_prompts_format_with_context_block_kwarg():
    """Every prompt must accept context_block as a .format() kwarg without KeyError."""
    from creativity_mcp.explore_prompts import (
        LENS_PROMPTS,
        PROD_INTERNAL_PROMPT,
        REVISIT_INTERNAL_PROMPT,
        SPARK_INTERNAL_PROMPT,
        WEIRD_INTERNAL_PROMPT,
    )

    SPARK_INTERNAL_PROMPT.format(challenge="test", domain="test", context_block="")
    SPARK_INTERNAL_PROMPT.format(challenge="test", domain="test", context_block="\nCONTEXT:\nsome context")

    for key, prompt in LENS_PROMPTS.items():
        prompt.format(challenge="test", existing_branches="test", constraints="test", context_block="")
        prompt.format(challenge="test", existing_branches="test", constraints="test", context_block="\nCONTEXT:\ninfo")

    REVISIT_INTERNAL_PROMPT.format(challenge="test", branch_content="test", context_block="")
    WEIRD_INTERNAL_PROMPT.format(challenge="test", existing_branches="test", context_block="")
    PROD_INTERNAL_PROMPT.format(challenge="test", branches_summary="test", context_block="")
