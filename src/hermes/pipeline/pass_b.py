"""Pass B: Stem Composition with Redaction Enforcement.

This is the SECOND LLM pass in the distractor-first pipeline.

Input:
- Pass A output (distractors, correct answer, contradictable_facts)
- Tier
- Stem pattern (one of 20 patterns, tier-keyed)
- Character assignment (name for vignette-style patterns)

Output:
- Stem (1-8 sentences, pattern-appropriate)
- Character name (if applicable)
- Redaction compliance self-check

CRITICAL RULE:
- Stem CANNOT print contradictable_facts OR their logical negations
- "NEGATION COUNTS AS PRINTING"
- If fact = "varies actions", stem cannot say "does not vary actions"
"""

from dataclasses import dataclass
from ..constants import Tier
from .pass_a import PassAOutput


@dataclass
class PassBOutput:
    """Output from Pass B: stem composition."""
    stem: str
    character_name: Optional[str]  # None for non-vignette patterns
    stem_pattern: str
    redaction_compliant: bool
    redaction_compliance_reason: str


# Prompt template for Pass B
PASS_B_SYSTEM_PROMPT = """You are an expert EPPP exam question writer specializing in stem composition.

YOUR TASK: Compose a question stem for Bloom's Tier {tier} using the {stem_pattern} pattern.

CRITICAL: REDACTION ENFORCEMENT
The following facts are REDACTED. You CANNOT print them or their logical negations in the stem:

CONTRADICTABLE_FACTS:
{contradictable_facts bullet list}

VIOLATION EXAMPLES:
- If fact = "uses exposure hierarchies", stem cannot say "uses exposure hierarchies" (direct print)
- If fact = "uses exposure hierarchies", stem cannot say "does NOT use exposure hierarchies" (negation = violation)
- If fact = "thought records", stem cannot say "thinks and records" (paraphrase may still violate)
- If fact = "all forgetting", stem cannot say "some forgetting" (quantifier hedge = violation)

Your stem must make sense WITHOUT these facts. The student must select the correct answer
based on their KNOWLEDGE, not based on stem-distractor contradictions.

STEM PATTERN: {stem_pattern}
{stem_pattern_description}

BLOOM'S VERBS FOR TIER {tier}: {blooms_verbs}
Use at least one of these verbs (or cognate form) in the stem.

STEM LENGTH:
- Tier 1: 1-2 sentences, ~20-50 words
- Tier 2: 1-3 sentences, ~40-70 words
- Tier 3: 2-5 sentences, ~80-130 words
- Tier 4: 3-7 sentences, ~100-150 words

CHARACTER INJECTION:
- Required for: clinical_vignette, case_analysis, subtle_error, competing_evidence, integration
- Optional for: scenario_completion, error_identification, contrast_prompt, best_answer, mechanism_application
- None for: direct_definition, concept_identification, fact_recognition, true_false_which, feature_listing, comparison, paraphrase, categorization

OUTPUT FORMAT (valid JSON):
{
  "stem": "...",
  "character_name": "Dr. Elena Rodriguez" or null,
  "stem_pattern": "...",
  "redaction_compliant": true,
  "redaction_compliance_reason": "I verified the stem does not print or negate any contradictable facts."
}
"""


PASS_B_USER_PROMPT = """
## Pass A Output (Distractors + Correct Answer)

### Correct Answer
Concept: {tested_concept_id} ({tested_concept_label})
Text: {correct_text}

### Distractors
{distractor_texts}

### Contradictable Facts (REDACTED FROM STEM)
{contradictable_facts_json}

## Stem Pattern
Pattern: {stem_pattern}
Description: {stem_pattern_description}

## Tier Requirements
Tier: {tier}
Bloom's Verbs: {blooms_verbs}
Stem Length: {stem_length_guidance}

## Character (if required for pattern)
Assigned Name: {character_name}

Compose a stem that:
1. Uses the {stem_pattern} pattern
2. Uses at least one Bloom's verb: {blooms_verbs}
3. Does NOT print or negate any contradictable facts
4. Matches tier length guidelines
5. Includes character name if pattern requires it
"""


# Stem pattern descriptions (subset - full 20 patterns in production)
STEM_PATTERN_DESCRIPTIONS = {
    "direct_definition": "Present a concept and ask the student to select its correct definition. Stem: 1 sentence naming the concept.",
    "concept_identification": "Present a description and ask the student to identify the correct term. Stem: 1-2 sentences describing without naming.",
    "clinical_vignette": "Clinical vignette with named professional/client, specific setting, presenting concern. Stem: 3-5 sentences.",
    "best_answer": "All options contain truth; evaluate which is MOST correct in this specific context. Stem: 3-5 sentences with context.",
    # ... (add all 20 patterns in production)
}


# Tier length guidance
TIER_LENGTH_GUIDANCE = {
    Tier.REMEMBER: "1-2 sentences, ~20-50 words",
    Tier.UNDERSTAND: "1-3 sentences, ~40-70 words",
    Tier.APPLY: "2-5 sentences, ~80-130 words",
    Tier.EVALUATE: "3-7 sentences, ~100-150 words",
}


def get_stem_pattern_description(pattern: str) -> str:
    return STEM_PATTERN_DESCRIPTIONS.get(pattern, "Generate a stem appropriate for the tier.")


async def compose_stem(
    client,
    pass_a_output: PassAOutput,
    stem_pattern: str,
    character_name: Optional[str] = None,
) -> PassBOutput:
    """Compose stem with redaction enforcement (Pass B)."""
    
    tier = pass_a_output.tier
    
    # Build contradictable facts bullet list
    facts_bullet = "\n".join(f"- {fact}" for fact in pass_a_output.contradictable_facts)
    
    # Build distractor texts
    distractor_texts = "\n".join(
        f"{d.letter}. {d.text}"
        for d in pass_a_output.distractors
    )
    
    # Build system prompt
    system_prompt = PASS_B_SYSTEM_PROMPT.format(
        tier=tier,
        stem_pattern=stem_pattern,
        stem_pattern_description=get_stem_pattern_description(stem_pattern),
        contradictable_facts_bullet=facts_bullet,
        blooms_verbs=", ".join(get_tier_verbs(tier)),
    )
    
    # Build user prompt
    user_prompt = PASS_B_USER_PROMPT.format(
        tested_concept_id=pass_a_output.tested_concept_id,
        tested_concept_label=pass_a_output.tested_concept_label,
        correct_text=pass_a_output.correct_answer.text,
        distractor_texts=distractor_texts,
        contradictable_facts_json=json.dumps(pass_a_output.contradictable_facts),
        stem_pattern=stem_pattern,
        stem_pattern_description=get_stem_pattern_description(stem_pattern),
        tier=tier,
        blooms_verbs=", ".join(get_tier_verbs(tier)),
        stem_length_guidance=TIER_LENGTH_GUIDANCE[tier],
        character_name=character_name or "N/A",
    )
    
    # Call LLM
    response = await client.messages.create(
        model="claude-opus-4-7-20250514",
        max_tokens=1000,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
        temperature=0.7,
    )
    
    # Parse response
    content = response.content[0].text
    result = json.loads(content)
    
    return PassBOutput(
        stem=result["stem"],
        character_name=result.get("character_name"),
        stem_pattern=stem_pattern,
        redaction_compliant=result["redaction_compliant"],
        redaction_compliance_reason=result["redaction_compliance_reason"],
    )

