"""HERMES CLI entry point."""

import argparse
import asyncio
import os
import json
from pathlib import Path

import anthropic
from rich.console import Console
from rich.json import JSON

from .constants import Tier
from .pipeline.orchestrator import HermesOrchestrator

console = Console()


def parse_args():
    parser = argparse.ArgumentParser(description="HERMES Question Generator")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # generate command
    gen = subparsers.add_parser("generate", help="Generate one question")
    gen.add_argument("--anchor-uid", required=True, help="Anchor UID")
    gen.add_argument("--tier", type=int, choices=[1, 2, 3, 4], required=True)
    gen.add_argument("--variant", type=int, choices=[1, 2, 3, 4, 5], default=1)
    gen.add_argument("--output", type=str, help="Output directory")

    return parser.parse_args()


async def generate_single(args):
    """Generate a single question."""
    # Initialize client
    api_key = os.getenv("ANTHROPIC_API_KEY") or os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        console.print("[red]Error:[/red] Set ANTHROPIC_API_KEY or OPENROUTER_API_KEY")
        return

    client = anthropic.AsyncClient(api_key=api_key)

    # Initialize orchestrator
    orchestrator = HermesOrchestrator(client, anchor_briefs_dir="data/anchor_briefs")

    # Mock anchor data for testing (TODO: load from brief or CSV)
    anchor_data = {
        "verbatim_anchor": "Working memory has limited capacity (~7±2 items).",
        "testable_fact": "Working memory capacity is approximately 7 ± 2 items.",
        "core_claim": "Working memory has limited capacity, typically 7 ± 2 chunks of information.",
        "tested_concept_id": "working-memory-capacity",
        "tested_concept_label": "Working Memory Capacity",
        "tested_concept_description": "The limited amount of information working memory can hold simultaneously.",
        "misconception_slots": [
            {"level": 1, "misconception_id": "wm-vs-sensory-capacity", "type": "similar_store"},
            {"level": 2, "misconception_id": "wm-vs-ltm-capacity", "type": "similar_property"},
            {"level": 3, "misconception_id": "wm-capacity-exact-number", "type": "partial_understanding"},
        ],
    }

    stem_patterns = {
        1: ["direct_definition", "concept_identification", "fact_recognition", "true_false_which", "feature_listing"],
        2: ["comparison", "example_recognition", "simple_application", "paraphrase", "categorization"],
        3: ["clinical_vignette", "scenario_completion", "error_identification", "case_analysis", "mechanism_application"],
        4: ["contrast_prompt", "best_answer", "subtle_error", "competing_evidence", "integration"],
    }
    pattern = stem_patterns[args.tier][(args.variant - 1) % 5]

    console.print(f"[cyan]Generating:[/cyan] Tier {args.tier}, Variant {args.variant}, Pattern: {pattern}")

    # Generate
    result = await orchestrator.generate_question(
        anchor_uid=args.anchor_uid,
        tier=Tier(args.tier),
        variant=args.variant,
        stem_pattern=pattern,
        verbatim_anchor=anchor_data["verbatim_anchor"],
        testable_fact=anchor_data["testable_fact"],
        core_claim=anchor_data["core_claim"],
        tested_concept_id=anchor_data["tested_concept_id"],
        tested_concept_label=anchor_data["tested_concept_label"],
        tested_concept_description=anchor_data["tested_concept_description"],
        misconception_slots=anchor_data["misconception_slots"],
    )

    # Output
    output = {
        "question_id": result.question_id,
        "stem": result.stem,
        "tier": result.tier,
        "stem_pattern": result.stem_pattern,
        "gate_results": {k: {"passed": v.passed, "message": v.message} for k, v in result.gate_results.items()},
        "audit_verdict": result.audit_verdict,
    }

    if args.output:
        out_path = Path(args.output) / f"{result.question_id}.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w") as f:
            json.dump(output, f, indent=2)
        console.print(f"[green]Saved:[/green] {out_path}")
    else:
        console.print(JSON(output))


def main():
    args = parse_args()
    if args.command == "generate":
        asyncio.run(generate_single(args))


if __name__ == "__main__":
    main()

