"""Pass C: Flashcard Seed Generation.

Generates 3 flashcard seeds per question:
- concept: Core factual concept (L1 errors trigger this)
- comparison: X vs Y distinction (L2 errors trigger this)
- nuance: Edge cases, boundary conditions (L3/L4 errors trigger this)

Zero API cost extraction from Pass A output.
"""

from dataclasses import dataclass
from .pass_a import PassAOutput


@dataclass
class FlashcardSeed:
    """A flashcard seed for adaptive remediation."""
    seed_type: str  # "concept", "comparison", "nuance"
    front: str  # 57-121 chars typical
    back: str   # 178-436 chars typical
    triggered_by_level: list[int]  # Which distractor levels trigger this seed


@dataclass
class PassCOutput:
    """Output from Pass C: flashcard seeds."""
    seeds: list[FlashcardSeed]


# Prompt template for Pass C
PASS_C_SYSTEM_PROMPT = """You are an expert instructional designer creating adaptive flashcard seeds.

YOUR TASK: Generate 3 flashcard seeds from a completed question:
1. CONCEPT seed (core factual concept) - triggered by L1 errors
2. COMPARISON seed (X vs Y distinction) - triggered by L2 errors
3. NUANCE seed (edge cases, boundary conditions) - triggered by L3/L4 errors

INPUT:
- Question stem and correct answer
- 3 distractors with their misconception types and confused_with concepts

RULES:

1. CONCEPT SEED:
   - Front: Direct question about the tested concept
   - Back: Concise definition + exam-relevant implication (~30-35 words)
   - Two-part format: definition + implication

2. COMPARISON SEED:
   - Front: Must contain "vs" or "distinguish" or "differ"
   - Back: Key discriminating feature between confused concepts
   - Focus on what makes them different, not just definitions

3. NUANCE SEED:
   - Front: Edge case or boundary condition question
   - Back: At least 2 sentences explaining when rule applies vs breaks down
   - Tests deep understanding, not rote recall

4. LENGTH GUIDELINES:
   - Front: 57-121 characters typical
   - Back: 178-436 characters typical
   - Concise but complete

OUTPUT FORMAT (valid JSON):
{
  "seeds": [
    {
      "seed_type": "concept",
      "front": "...",
      "back": "...",
      "triggered_by_level": [1]
    },
    {
      "seed_type": "comparison",
      "front": "...",
      "back": "...",
      "triggered_by_level": [2]
    },
    {
      "seed_type": "nuance",
      "front": "...",
      "back": "...",
      "triggered_by_level": [3, 4]
    }
  ]
}
"""


PASS_C_USER_PROMPT = """
## Question
Stem: {stem}

## Correct Answer
Concept: {tested_concept_id} ({tested_concept_label})
Text: {correct_text}
Explanation: {correct_explanation}

## Distractors
{distractors_json}

Generate 3 flashcard seeds: concept, comparison, nuance.
"""


async def generate_flashcard_seeds(
    client,
    stem: str,
    pass_a_output: PassAOutput,
) -> PassCOutput:
    """Generate 3 flashcard seeds from completed question (Pass C)."""
    
    # Build distractors JSON
    distractors_json = "\n".join(
        f"- {d.letter}. {d.text}\n"
        f"  Level: {d.distractor_level}, Type: {d.misconception_type}, "
        f"Confused with: {d.confused_with}"
        for d in pass_a_output.distractors
    )
    
    # Build user prompt
    user_prompt = PASS_C_USER_PROMPT.format(
        stem=stem,
        tested_concept_id=pass_a_output.tested_concept_id,
        tested_concept_label=pass_a_output.tested_concept_label,
        correct_text=pass_a_output.correct_answer.text,
        correct_explanation=pass_a_output.correct_answer.explanation[:300],
        distractors_json=distractors_json,
    )
    
    # Call LLM (sonnet-4.6, cheaper than opus)
    response = await client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=800,
        system=PASS_C_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
        temperature=0.7,
    )
    
    # Parse response
    import json
    content = response.content[0].text
    result = json.loads(content)
    
    # Build output
    seeds = [
        FlashcardSeed(
            seed_type=s["seed_type"],
            front=s["front"],
            back=s["back"],
            triggered_by_level=s["triggered_by_level"],
        )
        for s in result["seeds"]
    ]
    
    return PassCOutput(seeds=seeds)

