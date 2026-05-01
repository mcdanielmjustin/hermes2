"""Audit pass for HERMES pipeline.

4-class verdict + Bloom's shape verdict.
"""

from dataclasses import dataclass
from typing import Optional
import json

from ..constants import Tier


@dataclass
class AuditVerdict:
    """Output from audit pass."""
    verdict: str  # "ship", "minor_fix", "major_rework", "scrap"
    bloom_shape: str  # "tier_appropriate", "borderline", "scope_creep"
    issues: list[str]
    reasoning: str
    factual_check: Optional[str] = None  # "pass", "fail", or "unchecked"
    ambiguity_check: Optional[str] = None  # "pass", "fail", or "unchecked"


AUDIT_SYSTEM_PROMPT = """You are an expert EPPP question auditor.

YOUR TASK: Evaluate a generated question and assign:
1. VERDICT: ship | minor_fix | major_rework | scrap
2. BLOOM'S SHAPE: tier_appropriate | borderline | scope_creep
3. ISSUES: List of specific problems
4. REASONING: Brief explanation

VERDICT CRITERIA:
- ship: No issues, ready for deployment
- minor_fix: Editorial tweaks only (typos, grammar, parallel structure)
- major_rework: Structural issues (redaction violation, tier mismatch, factual error, ambiguity)
- scrap: Unfixable (hallucinated facts, incoherent stem, >2 gate failures)

BLOOM'S SHAPE:
- tier_appropriate: Cognitive demand matches labeled tier
- borderline: Could go either way
- scope_creep: Asks for higher cognitive demand than tier label

TIER EXPECTATIONS:
- T1 (Remember): Direct recall, no scenario, 1-2 sentences
- T2 (Understand): Comprehension, brief scenario OK, 1-3 sentences
- T3 (Apply): Full scenario with named character, 2-5 sentences
- T4 (Evaluate): Complex scenario, competing evidence, 3-7 sentences

OUTPUT JSON: {{"verdict": "...", "bloom_shape": "...", "issues": [], "reasoning": "..."}}
"""

AUDIT_USER_PROMPT = """
## Question
Stem: {stem}

## Options
Correct ({correct_letter}): {correct_text}
Distractors:
{distractor_texts}

## Metadata
Tier: {tier}
Stem Pattern: {stem_pattern}
Tested Concept: {tested_concept_id}

## Gate Results
{gate_results}

Evaluate this question. Assign verdict, Bloom's shape, and list any issues.
"""


async def audit_question(
    client,
    stem: str,
    correct_letter: str,
    correct_text: str,
    distractor_texts: list[str],
    tier: Tier,
    stem_pattern: str,
    tested_concept_id: str,
    gate_results: dict,
) -> AuditVerdict:
    """Audit a single question (Phase 5)."""

    gate_summary = "\n".join(
        f"- {name}: {'PASS' if r.passed else 'FAIL'} - {r.message}"
        for name, r in gate_results.items()
    )

    user_prompt = AUDIT_USER_PROMPT.format(
        stem=stem,
        correct_letter=correct_letter,
        correct_text=correct_text,
        distractor_texts="\n".join(f"- {d}" for d in distractor_texts),
        tier=tier,
        stem_pattern=stem_pattern,
        tested_concept_id=tested_concept_id,
        gate_results=gate_summary,
    )

    response = await client.messages.create(
        model="claude-sonnet-4-20250514",  # Cheaper, good for classification
        max_tokens=500,
        system=AUDIT_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
        temperature=0.3,  # Low temp for consistent classification
    )

    result = json.loads(response.content[0].text)

    return AuditVerdict(
        verdict=result["verdict"],
        bloom_shape=result["bloom_shape"],
        issues=result.get("issues", []),
        reasoning=result.get("reasoning", ""),
    )


SAMPLE_AUDIT_PROMPT = """Check for factual errors in this question.

STEM: {stem}
CORRECT: {correct_text}
EXPLANATIONS: {explanations}

Flag any factual inaccuracies, misattributions, or outdated information.
Respond with: {{"factual_check": "pass" or "fail", "errors": [...]}}
"""


AMBIGUITY_AUDIT_PROMPT = """Check for ambiguity in this question.

STEM: {stem}
ALL OPTIONS: {all_options}

Try to argue for each option. Are multiple options defensible?
Respond with: {{"ambiguity_check": "pass" or "fail", "ambiguous_options": [...]}}
"""


async def audit_factual(client, stem: str, correct_text: str, explanations: list[str]) -> dict:
    """Sample-based factual correctness audit."""
    prompt = SAMPLE_AUDIT_PROMPT.format(
        stem=stem,
        correct_text=correct_text,
        explanations="\n".join(explanations),
    )
    response = await client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=300,
        system="You are a factual auditor. Be strict.",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
    )
    return json.loads(response.content[0].text)


async def audit_ambiguity(client, stem: str, all_options: list[str]) -> dict:
    """Sample-based ambiguity audit."""
    prompt = AMBIGUITY_AUDIT_PROMPT.format(
        stem=stem,
        all_options="\n".join(f"{i+1}. {o}" for i, o in enumerate(all_options)),
    )
    response = await client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=300,
        system="You are an ambiguity auditor. Try to argue for each option.",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
    )
    return json.loads(response.content[0].text)

