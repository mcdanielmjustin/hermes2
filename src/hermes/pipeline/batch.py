"""Batch generation for HERMES pipeline.

Generate a cohort of questions across domains/tiers/variants.
"""

import asyncio
import json
import csv
from pathlib import Path
from datetime import datetime

from rich.console import Console
from rich.progress import Progress, TaskProgressColumn, TextColumn

from ..constants import Tier, DOMAIN_CODES
from .orchestrator import HermesOrchestrator, QuestionOutput
from .retry import should_retry, retry_question

console = Console()


@dataclass
class CohortManifest:
    """Manifest for a generation cohort."""
    run_id: str
    started_at: str
    completed_at: str
    total_questions: int
    shipped: int
    minor_fix: int
    major_rework: int
    scrap: int
    gates_passed: dict[str, int]
    bloom_shapes: dict[str, int]
    avg_cost_per_question: float
    questions: list[dict]


BATCH_SYSTEM_PROMPT = """You are generating a cohort of EPPP exam questions.

COHORT SPECIFICATIONS:
- {total_questions} questions total
- Domains: {domains}
- Tiers: {tiers}
- Variants per anchor: {variants}

QUALITY TARGETS:
- english_gap: 0.0% (redaction violations)
- Editorial major rate: <20%
- Tier fit: ≥80% tier_appropriate

Generate questions through the full HERMES pipeline:
Pass A → Pass B → Pass C → Gates → Audit → (Retry if needed)
"""


class BatchGenerator:
    """Generate question cohorts in batch mode."""

    def __init__(self, client, anchor_briefs_dir: str = "data/anchor_briefs"):
        self.client = client
        self.orchestrator = HermesOrchestrator(client, anchor_briefs_dir)
        self.output_dir = Path("data/cohorts")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def generate_cohort(
        self,
        run_id: str,
        anchors: list[dict],
        tiers: list[int] = [1, 2, 3, 4],
        variants_per_tier: int = 5,
        max_workers: int = 5,
    ) -> CohortManifest:
        """Generate a full cohort of questions.

        Args:
            run_id: Unique identifier for this run
            anchors: List of anchor dicts with uid, verbatim, testable_fact, core_claim, etc.
            tiers: Which tiers to generate (default: all 4)
            variants_per_tier: Variants per tier (default: 5)
            max_workers: Concurrent generation workers

        Returns:
            CohortManifest with generation statistics
        """
        started_at = datetime.utcnow().isoformat()

        # Compute total questions
        total_questions = len(anchors) * len(tiers) * variants_per_tier
        console.print(f"[bold cyan]Starting cohort generation[/bold cyan]")
        console.print(f"Run ID: {run_id}")
        console.print(f"Anchors: {len(anchors)}")
        console.print(f"Tiers: {tiers}")
        console.print(f"Variants per tier: {variants_per_tier}")
        console.print(f"[bold]Total questions: {total_questions}[/bold]")
        console.print()

        # Statistics tracking
        stats = {
            "shipped": 0,
            "minor_fix": 0,
            "major_rework": 0,
            "scrap": 0,
            "gates_passed": {gate: 0 for gate in ["StructureGate", "RedactionViolationGate", "ContentQualityGate", "OptionLengthBalanceGate", "ConsistencyGate"]},
            "bloom_shapes": {"tier_appropriate": 0, "borderline": 0, "scope_creep": 0},
        }

        results = []
        semaphore = asyncio.Semaphore(max_workers)

        async def generate_single(
            anchor: dict,
            tier: Tier,
            variant: int,
        ) -> dict:
            """Generate one question with semaphore for concurrency control."""
            async with semaphore:
                try:
                    # Generate
                    result = await self.orchestrator.generate_question(
                        anchor_uid=anchor["uid"],
                        tier=tier,
                        variant=variant,
                        stem_pattern=self._get_stem_pattern(tier, variant),
                        verbatim_anchor=anchor.get("verbatim_anchor", ""),
                        testable_fact=anchor.get("testable_fact", ""),
                        core_claim=anchor.get("core_claim", ""),
                        tested_concept_id=anchor.get("tested_concept_id", ""),
                        tested_concept_label=anchor.get("tested_concept_label", ""),
                        tested_concept_description=anchor.get("tested_concept_description", ""),
                        misconception_slots=anchor.get("misconception_slots", []),
                        run_audit=True,
                    )

                    # Check if retry needed
                    retry_count = 0
                    should_retry_flag, retry_reason = should_retry(
                        result.gate_results,
                        result.audit_verdict or "ship",
                        retry_count,
                    )

                    if should_retry_flag:
                        console.print(f"  [yellow]Retrying {result.question_id}:[/yellow] {retry_reason}")
                        retry_result = await retry_question(
                            client=self.client,
                            stem=result.stem,
                            options=result.options,
                            tier=tier,
                            tested_concept_id=result.metadata["tested_concept_id"],
                            gate_results=result.gate_results,
                            contradictable_facts=[],  # Would need to fetch from Pass A output
                        )
                        if retry_result:
                            # Re-validate (simplified - just update gate_results placeholder)
                            result.stem = retry_result.stem
                            result.gate_results = retry_result.gate_results
                            retry_count += 1

                    # Update stats
                    verdict = result.audit_verdict or "ship"
                    if verdict == "ship":
                        stats["shipped"] += 1
                    elif verdict == "minor_fix":
                        stats["minor_fix"] += 1
                    elif verdict == "major_rework":
                        stats["major_rework"] += 1
                    else:
                        stats["scrap"] += 1

                    # Gate stats
                    for gate_name, gate_result in result.gate_results.items():
                        if gate_result.passed:
                            stats["gates_passed"][gate_name] = stats["gates_passed"].get(gate_name, 0) + 1

                    return {
                        "question_id": result.question_id,
                        "tier": tier,
                        "verdict": verdict,
                        "gates": {k: v.passed for k, v in result.gate_results.items()},
                        "full_output": {
                            "stem": result.stem,
                            "options": result.options,
                            "metadata": result.metadata,
                            "flashcard_seeds": result.flashcard_seeds,
                        },
                    }

                except Exception as e:
                    console.print(f"  [red]Error generating {anchor['uid']}-T{tier}-V{variant}: {e}[/red]")
                    return {
                        "question_id": f"{anchor['uid']}-T{tier}-V{variant}",
                        "tier": tier,
                        "verdict": "error",
                        "error": str(e),
                    }

        # Generate all questions
        with Progress(
            TextColumn("[bold blue]{task.description}"),
            TaskProgressColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("[cyan]Generating questions...", total=total_questions)

            tasks = []
            for anchor in anchors:
                for tier_num in tiers:
                    for variant in range(1, variants_per_tier + 1):
                        tier = Tier(tier_num)
                        tasks.append(generate_single(anchor, tier, variant))

            # Run all tasks
            for coro in asyncio.as_completed(tasks):
                result = await coro
                results.append(result)
                progress.advance(task)

        # Compute final stats
        completed_at = datetime.utcnow().isoformat()
        avg_gates_passed = sum(stats["gates_passed"].values()) / len(stats["gates_passed"]) / max(1, len(results)) * 100

        manifest = CohortManifest(
            run_id=run_id,
            started_at=started_at,
            completed_at=completed_at,
            total_questions=len(results),
            shipped=stats["shipped"],
            minor_fix=stats["minor_fix"],
            major_rework=stats["major_rework"],
            scrap=stats["scrap"],
            gates_passed=stats["gates_passed"],
            bloom_shapes=stats["bloom_shapes"],
            avg_cost_per_question=0.30,  # Estimate - would track actual token usage
            questions=results,
        )

        # Save manifest
        manifest_path = self.output_dir / f"{run_id}_manifest.json"
        with open(manifest_path, "w") as f:
            json.dump({
                "run_id": manifest.run_id,
                "started_at": manifest.started_at,
                "completed_at": manifest.completed_at,
                "total_questions": manifest.total_questions,
                "shipped": manifest.shipped,
                "minor_fix": manifest.minor_fix,
                "major_rework": manifest.major_rework,
                "scrap": manifest.scrap,
                "gates_passed": manifest.gates_passed,
                "bloom_shapes": manifest.bloom_shapes,
                "avg_cost_per_question": manifest.avg_cost_per_question,
            }, f, indent=2)

        # Save individual questions
        questions_dir = self.output_dir / run_id
        questions_dir.mkdir(parents=True, exist_ok=True)
        for q in results:
            if q.get("full_output"):
                q_path = questions_dir / f"{q['question_id']}.json"
                with open(q_path, "w") as f:
                    json.dump(q["full_output"], f, indent=2)

        # Print summary
        console.print()
        console.print("[bold green]Cohort Generation Complete[/bold green]")
        console.print(f"Run ID: {manifest.run_id}")
        console.print(f"Total: {manifest.total_questions} questions")
        console.print(f"Shipped: {manifest.shipped} ({manifest.shipped/manifest.total_questions*100:.1f}%)")
        console.print(f"Minor Fix: {manifest.minor_fix}")
        console.print(f"Major Rework: {manifest.major_rework}")
        console.print(f"Scrap: {manifest.scrap}")
        console.print(f"Avg Gates Passed: {avg_gates_passed:.1f}%")
        console.print(f"\nSaved to: {manifest_path}")

        return manifest

    def _get_stem_pattern(self, tier: Tier, variant: int) -> str:
        """Get stem pattern for tier and variant."""
        patterns = {
            1: ["direct_definition", "concept_identification", "fact_recognition", "true_false_which", "feature_listing"],
            2: ["comparison", "example_recognition", "simple_application", "paraphrase", "categorization"],
            3: ["clinical_vignette", "scenario_completion", "error_identification", "case_analysis", "mechanism_application"],
            4: ["contrast_prompt", "best_answer", "subtle_error", "competing_evidence", "integration"],
        }
        return patterns[tier][(variant - 1) % 5]

