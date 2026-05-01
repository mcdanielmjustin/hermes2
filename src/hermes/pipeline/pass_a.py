"""Pass A: Distractor Design + Correct Answer + Contradictable Facts.

This is the FIRST LLM pass in the distractor-first pipeline.

Input:
- Anchor brief (or chapter vocab fallback)
- Tier (1-4)
- Distractor mix plan (e.g., T1: 1×L1, 1×L2, 1×L3)
- Pre-assigned misconception slots

Output:
- 3 distractors with: text, level, misconception_id, misconception_type, concept_id
- 1 correct answer with: text, concept_id, explanation
- contradictable_facts: list of facts the stem CANNOT print (or negate)
"""

from dataclasses import dataclass, field
from typing import Optional
import json

from ..constants import Tier, DistractorLevel, MisconceptionType, DISTRACTOR_MIX
from ..taxonomy import get_tier_verbs


@dataclass
class Distractor:
    """A wrong answer option with diagnostic metadata."""
    letter: str  # A, B, C, or D (assigned later by assembler)
    text: str
    distractor_level: DistractorLevel
    concept_id: str
    misconception_id: str
    misconception_type: str
    confused_with: str  # concept_id of correct answer
    explanation: str  # 200-300 words: what student likely confused + correction


@dataclass
class CorrectAnswer:
    """The correct answer option."""
    letter: str  # Assigned later
    text: str
    concept_id: str
    explanation: str  # 200-300 words: clinical facts, mechanisms, thresholds


@dataclass
class PassAOutput:
    """Output from Pass A: distractor design."""
    distractors: list[Distractor]
    correct_answer: CorrectAnswer
    contradictable_facts: list[str]  # Facts stem cannot print OR negate
    tested_concept_id: str
    tested_concept_label: str
    knowledge_tested: str  # Prose: what the question tests
    anchor_uid: str
    tier: Tier
    variant: int


# Prompt template for Pass A
PASS_A_SYSTEM_PROMPT = """You are an expert EPPP exam question writer specializing in diagnostic distractor design.

YOUR TASK: Generate 3 distractors + 1 correct answer for a Bloom's Tier {tier} question.

INPUT:
- Anchor: {anchor_uid}
- Core Claim: {core_claim}
- Tested Concept: {tested_concept_id} ({tested_concept_label})
- Distractor Mix: {distractor_mix}
- Misconception Slots: {misconception_slots}

CRITICAL RULES:

1. DISTRACTOR-FIRST DESIGN: You are generating distractors BEFORE the stem exists.
   Each distractor must be a plausible wrong answer that a student with a SPECIFIC
   misconception would select.

2. CONTRADICTABLE FACTS: For each distractor and the correct answer, extract facts
   that the stem CANNOT print (or the distractor would be rejectable). Examples:
   - If distractor says "uses exposure hierarchies", contradictable_fact = "uses exposure hierarchies"
   - If correct says "thought records", contradictable_fact = "thought records"
   The stem will be written in Pass B with REDACTION constraints.

3. MISCONCEPTION ALIGNMENT: Each distractor must match its assigned misconception_type:
   - similar_property: Shares surface features with correct concept
   - partial_understanding: Almost right, missing one crucial qualifier
   - overgeneralization: Correct principle applied beyond its scope
   - similar_name: Terminologically confusable
   - opposite_direction: Reversed causal direction
   - similar_store: Same mental shelf (chapter/category)

4. DISTRACTOR LEVELS: Match the assigned level:
   - L1: Cross-subdomain (different topic entirely)
   - L2: Same subdomain, different concept
   - L3: Same concept family, closely related
   - L4: Partially correct (would be right in some context)

5. EXPLANATIONS: 200-300 words each.
   - Distractor: "You may have chosen this because [misconception pattern]. The key distinction: [correction]."
   - Correct: Detailed clinical facts, mechanisms, thresholds.

6. NO STEM: Do NOT write the stem. Only distractors + correct + contradictable_facts.

OUTPUT FORMAT (valid JSON):
{
  "distractors": [
    {
      "letter": "A",
      "text": "...",
      "distractor_level": 2,
      "concept_id": "...",
      "misconception_id": "conceptA-vs-conceptB",
      "misconception_type": "similar_property",
      "confused_with": "correct_concept_id",
      "explanation": "..."
    },
    ...
  ],
  "correct_answer": {
    "letter": "B",
    "text": "...",
    "concept_id": "...",
    "explanation": "..."
  },
  "contradictable_facts": [
    "fact from distractor A",
    "fact from distractor C",
    "fact from correct answer"
  ],
  "tested_concept_id": "...",
  "tested_concept_label": "...",
  "knowledge_tested": "..."
}
"""


PASS_A_USER_PROMPT = """
## Anchor
UID: {anchor_uid}
Verbatim: {verbatim_anchor}
Testable Fact: {testable_fact}

## Core Claim (MUST ADDRESS)
{core_claim}

## Tested Concept
ID: {tested_concept_id}
Label: {tested_concept_label}
Description: {tested_concept_description}

## Distractor Mix (Tier {tier})
{distractor_mix_description}

## Pre-Assigned Misconception Slots
{misconception_slots_json}

## Bloom's Verbs for Tier {tier}
{blooms_verbs}

Generate 3 distractors + 1 correct answer. Extract contradictable_facts for redaction in Pass B.
"""


async def generate_distractors(
    client,
    anchor_uid: str,
    verbatim_anchor: str,
    testable_fact: str,
    core_claim: str,
    tested_concept_id: str,
    tested_concept_label: str,
    tested_concept_description: str,
    tier: Tier,
    variant: int,
    misconception_slots: list[dict],
) -> PassAOutput:
    """Generate distractors + correct answer + contradictable_facts (Pass A)."""
    
    # Build distractor mix description
    mix = DISTRACTOR_MIX[tier]
    mix_desc = f"L1: {mix[0]}, L2: {mix[1]}, L3: {mix[2]}, L4: {mix[3]}"
    
    # Build user prompt
    user_prompt = PASS_A_USER_PROMPT.format(
        anchor_uid=anchor_uid,
        verbatim_anchor=verbatim_anchor[:200],  # Truncate
        testable_fact=testable_fact[:200],
        core_claim=core_claim,
        tested_concept_id=tested_concept_id,
        tested_concept_label=tested_concept_label,
        tested_concept_description=tested_concept_description,
        tier=tier,
        distractor_mix_description=mix_desc,
        misconception_slots_json=json.dumps(misconception_slots, indent=2),
        blooms_verbs=", ".join(get_tier_verbs(tier)),
    )
    
    # Build system prompt
    system_prompt = PASS_A_SYSTEM_PROMPT.format(
        tier=tier,
        anchor_uid=anchor_uid,
        core_claim=core_claim,
        tested_concept_id=tested_concept_id,
        tested_concept_label=tested_concept_label,
        distractor_mix=mix_desc,
        misconception_slots=json.dumps(misconception_slots),
    )
    
    # Call LLM (claude-opus-4.7 via OpenRouter or Anthropic)
    response = await client.messages.create(
        model="claude-opus-4-7-20250514",
        max_tokens=2000,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
        temperature=1.0,  # Required for extended thinking
    )
    
    # Parse response
    content = response.content[0].text
    result = json.loads(content)
    
    # Build output
    distractors = [
        Distractor(
            letter=d["letter"],
            text=d["text"],
            distractor_level=DistractorLevel(d["distractor_level"]),
            concept_id=d["concept_id"],
            misconception_id=d["misconception_id"],
            misconception_type=d["misconception_type"],
            confused_with=d["confused_with"],
            explanation=d["explanation"],
        )
        for d in result["distractors"]
    ]
    
    correct = CorrectAnswer(
        letter=result["correct_answer"]["letter"],
        text=result["correct_answer"]["text"],
        concept_id=result["correct_answer"]["concept_id"],
        explanation=result["correct_answer"]["explanation"],
    )
    
    return PassAOutput(
        distractors=distractors,
        correct_answer=correct,
        contradictable_facts=result["contradictable_facts"],
        tested_concept_id=result["tested_concept_id"],
        tested_concept_label=result["tested_concept_label"],
        knowledge_tested=result["knowledge_tested"],
        anchor_uid=anchor_uid,
        tier=tier,
        variant=variant,
    )

