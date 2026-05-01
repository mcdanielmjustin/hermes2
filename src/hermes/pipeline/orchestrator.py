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
import asyncio

from ..constants import Tier, DISTRACTOR_MIX
from .pass_a import generate_distractors, PassAOutput
from .pass_b import compose_stem, PassBOutput
from .pass_c import generate_flashcard_seeds, PassCOutput
from .gates import (
    GateResult,
    StructureGate,
    RedactionViolationGate,
    ContentQualityGate,
    OptionLengthBalanceGate,
    create_gate_pipeline,
)


@dataclass
class QuestionOutput:
    """Final assembled question output."""
    question_id: str
    stem: str
    stem_pattern: str
    tier: Tier
    correct_letter: str
    options: list[dict]  # All 4 options with full metadata
    flashcard_seeds: list[dict]
    metadata: dict
    gate_results: dict[str, GateResult]
    audit_verdict: Optional[str] = None  # "ship", "minor_fix", "major_rework", "scrap"


@dataclass
class AnchorBrief:
    """Anchor brief structure (from goliath anchor_briefs)."""
    uid: str
    core_claims: list[str]
    concepts: list[dict]  # {concept_id, label, description}
    misconceptions: list[dict]  # {misconception_id, label, type, concepts_involved}
    question_angles: list[dict]  # {type, description} - tier-keyed


class HermesOrchestrator:
    """Main pipeline orchestrator for HERMES question generation."""

    def __init__(self, client, anchor_briefs_dir: str):
        self.client = client
        self.anchor_briefs_dir = anchor_briefs_dir
        self._brief_cache: dict[str, AnchorBrief] = {}

    async def load_anchor_brief(self, anchor_uid: str) -> Optional[AnchorBrief]:
        """Load anchor brief from disk (or return None if not exists)."""
        if anchor_uid in self._brief_cache:
            return self._brief_cache[anchor_uid]

        # TODO: Implement file loading
        # Brief path: {anchor_briefs_dir}/{DOMAIN}/{uid}.json
        # Fallback: return None (use chapter vocab)

        return None

    def get_distractor_mix(self, tier: Tier) -> list[int]:
        """Get expected distractor levels for a tier."""
        mix = DISTRACTOR_MIX[tier]
        levels = []
        for level, count in enumerate(mix, start=1):
            levels.extend([level] * count)
        return levels

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
    ) -> QuestionOutput:
        """Generate a single question through the full pipeline."""

        gate_results: dict[str, GateResult] = {}

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

        # Build options list for gates
        options = [
            {"letter": "A", "text": "", "is_correct": False},  # Placeholder
        ]
        # TODO: Assemble full options from pass_a_output + assigned positions

        # Run gates
        gate_results["StructureGate"] = gates["StructureGate"].validate(
            pass_b_output.stem, options, "B"  # Placeholder correct letter
        )

        gate_results["RedactionViolationGate"] = gates["RedactionViolationGate"].validate(
            pass_b_output.stem,
            pass_a_output.contradictable_facts,
        )

        gate_results["ContentQualityGate"] = gates["ContentQualityGate"].validate(
            pass_b_output.stem, options
        )

        gate_results["OptionLengthBalanceGate"] = gates["OptionLengthBalanceGate"].validate(
            options, "B"
        )

        # Check if any gate failed
        all_passed = all(r.passed for r in gate_results.values())

        # Phase 5: Audit (simplified - full audit in separate pass)
        audit_verdict = "ship" if all_passed else "major_rework"

        # Phase 7: Assembly
        output = QuestionOutput(
            question_id=f"{anchor_uid}-T{tier}-V{variant}",
            stem=pass_b_output.stem,
            stem_pattern=stem_pattern,
            tier=tier,
            correct_letter="B",  # Placeholder
            options=options,
            flashcard_seeds=[
                {"type": s.seed_type, "front": s.front, "back": s.back}
                for s in pass_c_output.seeds
            ],
            metadata={
                "anchor_uid": anchor_uid,
                "tested_concept_id": pass_a_output.tested_concept_id,
                "tested_concept_label": pass_a_output.tested_concept_label,
            },
            gate_results=gate_results,
            audit_verdict=audit_verdict,
        )

        return output

