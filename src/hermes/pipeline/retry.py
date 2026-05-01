"""Smart Retry - Phase 6 of HERMES pipeline.

Targeted retry for fixable issues. Max 1 retry, then escalate to human review.
"""

from dataclasses import dataclass
import json

from ..constants import Tier
from ..taxonomy import get_tier_verbs


@dataclass
class RetryOutcome:
    """Result of retry attempt."""
    success: bool
    stem: str
    gate_results: dict
    retry_reason: str


# Feedback templates per gate failure
GATE_GUIDANCE = {
    "StructureGate": """
RETRY INSTRUCTION: Fix structural issues.
- Ensure exactly 4 options with letters A, B, C, D
- Stem must be 1-8 sentences, non-empty
- All options must have text (5+ chars)
""",
    "RedactionViolationGate": """
RETRY INSTRUCTION: The stem prints or negates a contradictable fact.

CONTRADICTABLE_FACTS (cannot appear in stem):
{contradictable_facts}

REVISE the stem to remove any reference to these facts. The stem must make sense
WITHOUT revealing information that would expose distractors.

Remember: Negation counts as printing!
- If fact = "uses rehearsal", stem cannot say "does NOT use rehearsal"
""",
    "ContentQualityGate": """
RETRY INSTRUCTION: Fix content quality issues.
- Remove forbidden phrases: "all of the above", "none of the above", "a and b"
- Stem must be 1-8 sentences
- Options must be 5-45 words each
- Use interrogative or indicative mood (not imperative)
- Avoid compound double-asks (single cognitive operation per question)
""",
    "OptionLengthBalanceGate": """
RETRY INSTRUCTION: Fix option length imbalance.
- All 4 options should be within 1.7x of each other in character count
- Correct answer must NOT be >20% longer than ALL distractors
- Parallel structure: parens/semicolons/em-dashes must not cluster on correct answer
""",
    "ConsistencyGate": """
RETRY INSTRUCTION: Fix distractor consistency issues.
- Distractor levels must match tier plan: {expected_levels}
- Misconception types must be from: similar_property, partial_understanding,
  overgeneralization, similar_name, opposite_direction, similar_store
""",
}


RETRY_SYSTEM_PROMPT = """You are fixing a flawed EPPP exam question.

ORIGINAL ATTEMPT FAILED validation. Your task: revise to fix the specific issues.

{gate_guidance}

ORIGINAL STEM:
{original_stem}

ORIGINAL OPTIONS:
{original_options}

IMPORTANT: Preserve the core concept being tested: {tested_concept_id}
Do NOT change the fundamental knowledge being assessed.

OUTPUT JSON: {{"stem": "...", "options": [{{"letter": "A", "text": "..."}}, ...]}}
"""


async def retry_question(
    client,
    stem: str,
    options: list[dict],
    tier: Tier,
    tested_concept_id: str,
    gate_results: dict,
    contradictable_facts: list[str] = None,
):
    """Retry a question that failed validation (Phase 6).

    Only call this for questions with fixable issues (not scrap verdict).
    Max 1 retry - if this fails, escalate to human review.
    """
    # Determine which gates failed
    failures = {name: result for name, result in gate_results.items() if not result.passed}

    if not failures:
        return None  # Nothing to retry

    # Build gate guidance
    guidance_parts = []
    for gate_name, result in failures.items():
        if gate_name in GATE_GUIDANCE:
            guidance = GATE_GUIDANCE[gate_name]
            # Fill in gate-specific details
            if gate_name == "RedactionViolationGate" and contradictable_facts:
                guidance = guidance.format(
                    contradictable_facts="\n".join(f"- {f}" for f in contradictable_facts)
                )
            elif gate_name == "ConsistencyGate":
                guidance = guidance.format(
                    expected_levels="L1+L2+L3" if tier <= 2 else "L2+L3+L4" if tier == 3 else "L3+L4+L4"
                )
            guidance_parts.append(f"\n## {gate_name} FAILED\n{guidance}")
            guidance_parts.append(f"Error: {result.message}")

    gate_guidance = "\n".join(guidance_parts)

    # Build options text
    options_text = "\n".join(
        f"{opt['letter']}. {opt['text']} {'[CORRECT]' if opt.get('is_correct') else ''}"
        for opt in options
    )

    # Build system prompt
    system_prompt = RETRY_SYSTEM_PROMPT.format(
        gate_guidance=gate_guidance,
        original_stem=stem,
        original_options=options_text,
        tested_concept_id=tested_concept_id,
    )

    # Call LLM
    response = await client.messages.create(
        model="claude-opus-4-7-20250514",
        max_tokens=1500,
        system=system_prompt,
        messages=[{"role": "user", "content": "Revise this question to fix the validation failures."}],
        temperature=0.7,
    )

    result = json.loads(response.content[0].text)

    return RetryOutcome(
        success=True,
        stem=result.get("stem", stem),
        gate_results={name: "pending_revalidation" for name in failures.keys()},
        retry_reason=gate_guidance[:500] + "...",
    )


RETRY_DECISION_RULES = """
Retry Decision Rules:

RETRY (1 attempt allowed):
- StructureGate FAIL (fixable formatting issues)
- ContentQualityGate FAIL (forbidden phrases, length issues)
- OptionLengthBalanceGate FAIL (can trim/expand options)
- ConsistencyGate FAIL (can adjust distractor metadata)

DO NOT RETRY (escalate to human review):
- RedactionViolationGate FAIL (structural flaw - distractor design issue)
- Gate FAIL after already retrying once
- Audit verdict = "scrap"
- Multiple gate failures (>2)

RATIONALE:
- Redaction violations indicate Pass A distractor design was flawed
- Cannot fix in Pass B retry - need to regenerate distractors from scratch
- Multiple failures suggest fundamental issues, not surface problems
"""


def should_retry(gate_results: dict, audit_verdict: str, retry_count: int) -> tuple[bool, str]:
    """Determine if a question should be retried.

    Returns: (should_retry: bool, reason: str)
    """
    if retry_count >= 1:
        return False, "Already retried once - escalate to human review"

    failures = {name: r for name, r in gate_results.items() if not r.passed}
    hard_fails = [r for r in failures.values() if r.severity == "error"]

    if audit_verdict == "scrap":
        return False, "Audit verdict is 'scrap' - unfixable"

    if len(failures) > 2:
        return False, f"Too many failures ({len(failures)}) - fundamental issues"

    # Check for redaction violation (cannot retry - need distractor redesign)
    if "RedactionViolationGate" in failures:
        return False, "Redaction violation - requires Pass A redesign, not stem retry"

    if hard_fails:
        return True, f"Fixable failures: {list(failures.keys())}"

    return False, "No hard failures - no retry needed"

