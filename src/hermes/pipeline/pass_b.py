"""Pass B: Stem Composition with Redaction Enforcement.

CRITICAL RULE:
- Stem CANNOT print contradictable_facts OR their logical negations
- "NEGATION COUNTS AS PRINTING"
"""

from dataclasses import dataclass
from typing import Optional
import json

from ..constants import Tier
from ..taxonomy import get_tier_verbs
from .pass_a import PassAOutput


@dataclass
class PassBOutput:
    stem: str
    character_name: Optional[str]
    stem_pattern: str
    redaction_compliant: bool
    redaction_compliance_reason: str


PASS_B_SYSTEM_PROMPT = """You are an expert EPPP exam question writer.

YOUR TASK: Compose a stem for Tier {tier} using pattern: {stem_pattern}.

CRITICAL REDACTION: These facts are FORBIDDEN in the stem:

{contradictable_facts_bullet}

VIOLATIONS:
- Direct: "uses exposure" when fact = "uses exposure"
- Negation: "does NOT use exposure" (negation = violation)
- Quantifier hedge: "some exposure" when fact = "all exposure"

STEM PATTERN: {stem_pattern_description}
BLOOM'S VERBS: {blooms_verbs}
LENGTH: {stem_length}

OUTPUT JSON: {{"stem": "...", "character_name": "..." or null, "stem_pattern": "...", "redaction_compliant": true, "reason": "..."}}
"""

PASS_B_USER_PROMPT = """
## Pass A Output
Correct: {correct_text} ({tested_concept_id})
Distractors:
{distractor_texts}

## Contradictable Facts (REDACTED)
{contradictable_facts_json}

## Requirements
Pattern: {stem_pattern}
Tier: {tier}, Verbs: {blooms_verbs}
Length: {stem_length}
Character: {character_name}
"""

STEM_PATTERNS = {
    "direct_definition": "Ask student to select correct definition. Stem: 1 sentence naming concept.",
    "concept_identification": "Describe concept without naming; student identifies term. Stem: 1-2 sentences.",
    "clinical_vignette": "Named clinician/client case with setting. Stem: 3-5 sentences. Character required.",
    "best_answer": "All options contain truth; evaluate MOST correct. Stem: 3-5 sentences with context.",
    "comparison": "Identify key distinction between two concepts. Stem: names both concepts.",
    "example_recognition": "Name concept; student picks illustrating scenario. Stem: names concept.",
    "simple_application": "Brief scenario; student identifies concept. Stem: 1-3 sentences.",
    "paraphrase": "Select accurate restatement of concept. Stem: names concept/principle.",
    "categorization": "Classify item within taxonomy. Stem: presents item or category.",
    "scenario_completion": "Professional scenario; predict next step. Stem: 2-4 sentences.",
    "error_identification": "Find substantive error in claims. Stem: presents context + claims.",
    "case_analysis": "Identify underlying mechanism (WHY, not WHAT). Stem: 3-5 sentences. Character required.",
    "mechanism_application": "Apply named principle to novel situation; predict outcome. Stem: names principle.",
    "contrast_prompt": "Case where two concepts apply; which fits better? Stem: presents case. Character recommended.",
    "subtle_error": "Detect nuanced flaw in expert reasoning. Stem: 4-7 sentences with quoted reasoning. Character required.",
    "competing_evidence": "Weigh two defensible positions; context is tiebreaker. Stem: 4-6 sentences.",
    "integration": "Synthesize 2+ concept areas. Stem: 4-7 sentences, multi-concept. Character required.",
    "fact_recognition": "Identify correct factual statement grounded in authority. Stem: names authority.",
    "true_false_which": "Which statement about X is correct/incorrect? Stem: names concept.",
    "feature_listing": "Which is NOT a characteristic of X? Stem: names concept, uses EXCEPT/NOT.",
}

TIER_LENGTHS = {
    1: "1-2 sentences, ~20-50 words",
    2: "1-3 sentences, ~40-70 words",
    3: "2-5 sentences, ~80-130 words",
    4: "3-7 sentences, ~100-150 words",
}


def get_pattern_desc(pattern: str) -> str:
    return STEM_PATTERNS.get(pattern, f"Generate {pattern} stem for tier.")


async def compose_stem(
    client,
    pass_a_output: PassAOutput,
    stem_pattern: str,
    character_name: Optional[str] = None,
) -> PassBOutput:
    tier = pass_a_output.tier
    facts_bullet = "\n".join(f"- {f}" for f in pass_a_output.contradictable_facts)
    distractor_texts = "\n".join(f"{d.letter}. {d.text}" for d in pass_a_output.distractors)

    system = PASS_B_SYSTEM_PROMPT.format(
        tier=tier,
        stem_pattern=stem_pattern,
        contradictable_facts_bullet=facts_bullet,
        stem_pattern_description=get_pattern_desc(stem_pattern),
        blooms_verbs=", ".join(get_tier_verbs(tier)),
        stem_length=TIER_LENGTHS[tier],
    )

    user = PASS_B_USER_PROMPT.format(
        correct_text=pass_a_output.correct_answer.text,
        tested_concept_id=pass_a_output.tested_concept_id,
        distractor_texts=distractor_texts,
        contradictable_facts_json=json.dumps(pass_a_output.contradictable_facts),
        stem_pattern=stem_pattern,
        tier=tier,
        blooms_verbs=", ".join(get_tier_verbs(tier)),
        stem_length=TIER_LENGTHS[tier],
        character_name=character_name or "N/A",
    )

    response = await client.messages.create(
        model="claude-opus-4-7-20250514",
        max_tokens=1000,
        system=system,
        messages=[{"role": "user", "content": user}],
        temperature=0.7,
    )

    result = json.loads(response.content[0].text)
    return PassBOutput(
        stem=result["stem"],
        character_name=result.get("character_name"),
        stem_pattern=stem_pattern,
        redaction_compliant=result["redaction_compliant"],
        redaction_compliance_reason=result.get("reason", ""),
    )

