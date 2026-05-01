"""HERMES Orchestrator - Main pipeline coordinator.

Coordinates the full pipeline:
Phase 0: Anchor Resolve
Phase 1: Pass A (Distractor Design)
Phase 2: Pass B (Stem Composition)
Phase 3: Pass C (Flashcard Seeds)
Phase 4: Validation (8+1 gates)
Phase 5: Audit
Phase 6: Smart Retry
Phase 7: Assembly
"""

from dataclasses import dataclass
from typing import Optional
import random

from ..constants import Tier, DISTRACTOR_MIX, CORRECT_POSITIONS
from .pass_a import generate_distractors, PassAOutput, Distractor, CorrectAnswer
from .pass_b import compose_stem, PassBOutput
from .pass_c import generate_flashcard_seeds, PassCOutput
from .gates import (
    GateResult,
    StructureGate,
    RedactionViolationGate,
    ContentQualityGate,
    OptionLengthBalanceGate,
    ConsistencyGate,
    create_gate_pipeline,
)
from .audit import audit_question, AuditVerdict


@dataclass
class QuestionOutput:
    """Final assembled question output."""
    question_id: str
    stem: str
    stem_pattern: str
    tier: Tier
    correct_letter: str
    options: list[dict]
    flashcard_seeds: list[dict]
    metadata: dict
    gate_results: dict[str, GateResult]
    audit_verdict: Optional[str] = None


@dataclass
class AnchorBrief:
    """Anchor brief structure."""
    uid: str
    core_claims: list[str]
    concepts: list[dict]
    misconceptions: list[dict]
    question_angles: list[dict]


class HermesOrchestrator:
    """Main pipeline orchestrator."""

    def __init__(self, client, anchor_briefs_dir: str = "data/anchor_briefs"):
        self.client = client
        self.anchor_briefs_dir = anchor_briefs_dir
        self._brief_cache: dict[str, AnchorBrief] = {}

    async def load_anchor_brief(self, anchor_uid: str) -> Optional[AnchorBrief]:
        """Load anchor brief from disk (or None if not exists)."""
        if anchor_uid in self._brief_cache:
            return self._brief_cache[anchor_uid]
        # TODO: Implement file loading from {dir}/{DOMAIN}/{uid}.json
        return None

    def get_distractor_mix(self, tier: Tier) -> list[int]:
        """Get expected distractor levels for a tier."""
        mix = DISTRACTOR_MIX[tier]
        levels = []
        for level, count in enumerate(mix, start=1):
            levels.extend([level] * count)
        return levels

    def assemble_options(
        self,
        correct: CorrectAnswer,
        distractors: list[Distractor],
        position_index: int,
    ) -> tuple[list[dict], str]:
        """Assemble 4 options with correct answer at specified position."""
        correct_letter = CORRECT_POSITIONS[position_index % len(CORRECT_POSITIONS)]

        # Map distractors to letters (skip correct letter)
        all_letters = ["A", "B", "C", "D"]
        distractor_letters = [l for l in all_letters if l != correct_letter]

        options = []
        for i, d in enumerate(distractors):
            options.append({
                "letter": distractor_letters[i],
                "text": d.text,
                "is_correct": False,
                "distractor_level": int(d.distractor_level),
                "concept_id": d.concept_id,
                "misconception_id": d.misconception_id,
                "misconception_type": d.misconception_type,
                "confused_with": d.confused_with,
                "explanation": d.explanation,
            })

        # Add correct answer
        options.append({
            "letter": correct_letter,
            "text": correct.text,
            "is_correct": True,
            "concept_id": correct.concept_id,
            "explanation": correct.explanation,
        })

        # Sort by letter
        options.sort(key=lambda o: o["letter"])

        return options, correct_letter

    async def generate_question(
        self,
        anchor_uid: str,
        tier: Tier,
        variant: int,
        stem_pattern: str,
        verbatim_anchor: str,
        testable_fact: str,
        core_claim: str,
        tested_concept_id: str,
        tested_concept_label: str,
        tested_concept_description: str,
        misconception_slots: list[dict],
        character_name: Optional[str] = None,
        run_audit: bool = True,
    ) -> QuestionOutput:
        """Generate a single question through the full pipeline."""

        gate_results = {}

        # Phase 1: Pass A - Distractor Design
        pass_a_output = await generate_distractors(
            client=self.client,
            anchor_uid=anchor_uid,
            verbatim_anchor=verbatim_anchor,
            testable_fact=testable_fact,
            core_claim=core_claim,
            tested_concept_id=tested_concept_id,
            tested_concept_label=tested_concept_label,
            tested_concept_description=tested_concept_description,
            tier=tier,
            variant=variant,
            misconception_slots=misconception_slots,
        )

        # Phase 2: Pass B - Stem Composition
        pass_b_output = await compose_stem(
            client=self.client,
            pass_a_output=pass_a_output,
            stem_pattern=stem_pattern,
            character_name=character_name,
        )

        # Phase 3: Pass C - Flashcard Seeds
        pass_c_output = await generate_flashcard_seeds(
            client=self.client,
            stem=pass_b_output.stem,
            pass_a_output=pass_a_output,
        )

        # Phase 4: Validation Gates
        expected_levels = self.get_distractor_mix(tier)
        gates = create_gate_pipeline(expected_levels)

        # Assemble options
        position_index = (variant - 1) % 20
        options, correct_letter = self.assemble_options(
            pass_a_output.correct_answer,
            pass_a_output.distractors,
            position_index,
        )

        # Run gates
        gate_results["StructureGate"] = gates["StructureGate"].validate(
            pass_b_output.stem, options, correct_letter
        )

        gate_results["RedactionViolationGate"] = gates["RedactionViolationGate"].validate(
            pass_b_output.stem,
            pass_a_output.contradictable_facts,
        )

        gate_results["ContentQualityGate"] = gates["ContentQualityGate"].validate(
            pass_b_output.stem, options
        )

        gate_results["OptionLengthBalanceGate"] = gates["OptionLengthBalanceGate"].validate(
            options, correct_letter
        )

        gate_results["ConsistencyGate"] = gates["ConsistencyGate"].validate(
            [{"distractor_level": int(d.distractor_level), "misconception_type": d.misconception_type}
             for d in pass_a_output.distractors]
        )

        # Check if any hard gate failed
        hard_fails = [r for r in gate_results.values() if not r.passed and r.severity == "error"]

        # Phase 5: Audit (optional)
        audit_verdict = None
        if run_audit:
            distractor_texts = [d.text for d in pass_a_output.distractors]
            audit_result = await audit_question(
                client=self.client,
                stem=pass_b_output.stem,
                correct_letter=correct_letter,
                correct_text=pass_a_output.correct_answer.text,
                distractor_texts=distractor_texts,
                tier=tier,
                stem_pattern=stem_pattern,
                tested_concept_id=pass_a_output.tested_concept_id,
                gate_results=gate_results,
            )
            audit_verdict = audit_result.verdict

        # Determine final verdict
        if hard_fails:
            final_verdict = "major_rework"
        elif audit_verdict == "scrap":
            final_verdict = "scrap"
        elif audit_verdict == "major_rework":
            final_verdict = "major_rework"
        elif audit_verdict == "minor_fix":
            final_verdict = "minor_fix"
        else:
            final_verdict = "ship"

        # Phase 7: Assembly
        output = QuestionOutput(
            question_id=f"{anchor_uid}-T{tier}-V{variant}",
            stem=pass_b_output.stem,
            stem_pattern=stem_pattern,
            tier=tier,
            correct_letter=correct_letter,
            options=options,
            flashcard_seeds=[
                {"type": s.seed_type, "front": s.front, "back": s.back}
                for s in pass_c_output.seeds
            ],
            metadata={
                "anchor_uid": anchor_uid,
                "tested_concept_id": pass_a_output.tested_concept_id,
                "tested_concept_label": pass_a_output.tested_concept_label,
                "knowledge_tested": pass_a_output.knowledge_tested,
            },
            gate_results=gate_results,
            audit_verdict=final_verdict,
        )

        return output

