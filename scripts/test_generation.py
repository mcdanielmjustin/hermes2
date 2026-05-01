#!/usr/bin/env python3
"""Quick test script for end-to-end question generation."""

import asyncio
import os
import json
from pathlib import Path

import anthropic
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from hermes.constants import Tier
from hermes.pipeline.orchestrator import HermesOrchestrator

console = Console()


# Mock anchor data for testing
MOCK_ANCHOR = {
    "uid": "D7-WMEM-001",
    "verbatim_anchor": "Working memory has limited capacity (~7±2 items per Miller, 1956).",
    "testable_fact": "Working memory capacity is approximately 7 ± 2 chunks of information.",
    "core_claim": "Working memory has limited capacity, typically 7 ± 2 chunks.",
    "tested_concept_id": "working-memory-capacity",
    "tested_concept_label": "Working Memory Capacity",
    "tested_concept_description": "The limited amount of information working memory can hold simultaneously (Miller, 1956: 7±2 items).",
    "misconception_slots": [
        {"level": 1, "misconception_id": "wm-vs-sensory-capacity", "type": "similar_store"},
        {"level": 2, "misconception_id": "wm-vs-ltm-capacity", "type": "similar_property"},
        {"level": 3, "misconception_id": "wm-capacity-exact-number", "type": "partial_understanding"},
    ],
}

STEM_PATTERNS = {
    1: ["direct_definition", "concept_identification", "fact_recognition", "true_false_which", "feature_listing"],
    2: ["comparison", "example_recognition", "simple_application", "paraphrase", "categorization"],
    3: ["clinical_vignette", "scenario_completion", "error_identification", "case_analysis", "mechanism_application"],
    4: ["contrast_prompt", "best_answer", "subtle_error", "competing_evidence", "integration"],
}


async def test_generation(tier: int = 2, variant: int = 1):
    """Test end-to-end generation."""
    console.print(Panel.fit("[bold cyan]HERMES Test Generation[/bold cyan]"))

    # Get API key
    api_key = os.getenv("ANTHROPIC_API_KEY") or os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        console.print("[red]Error:[/red] Set ANTHROPIC_API_KEY or OPENROUTER_API_KEY")
        return

    client = anthropic.AsyncClient(api_key=api_key)
    orchestrator = HermesOrchestrator(client)

    tier_val = Tier(tier)
    pattern = STEM_PATTERNS[tier][(variant - 1) % 5]

    console.print(f"[cyan]Config:[/cyan] Tier {tier}, Variant {variant}, Pattern: {pattern}")
    console.print()

    # Generate
    with console.status("[bold green]Generating question...") as status:
        result = await orchestrator.generate_question(
            anchor_uid=MOCK_ANCHOR["uid"],
            tier=tier_val,
            variant=variant,
            stem_pattern=pattern,
            verbatim_anchor=MOCK_ANCHOR["verbatim_anchor"],
            testable_fact=MOCK_ANCHOR["testable_fact"],
            core_claim=MOCK_ANCHOR["core_claim"],
            tested_concept_id=MOCK_ANCHOR["tested_concept_id"],
            tested_concept_label=MOCK_ANCHOR["tested_concept_label"],
            tested_concept_description=MOCK_ANCHOR["tested_concept_description"],
            misconception_slots=MOCK_ANCHOR["misconception_slots"],
        )

    # Display results
    console.print()
    console.print(Panel(result.stem, title="[bold]Stem[/bold]"))

    # Options table
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Letter")
    table.add_column("Correct")
    table.add_column("Text")
    table.add_column("Type/Level")

    for opt in result.options:
        is_correct = "✓" if opt["is_correct"] else ""
        type_info = ""
        if opt["is_correct"]:
            type_info = f"Concept: {opt.get('concept_id', 'N/A')}"
        else:
            type_info = f"L{opt.get('distractor_level', '?')} / {opt.get('misconception_type', 'N/A')}"
        table.add_row(opt["letter"], is_correct, opt["text"][:60] + "..." if len(opt["text"]) > 60 else opt["text"], type_info)

    console.print()
    console.print(table)

    # Gate results
    console.print()
    console.print("[bold]Gate Results:[/bold]")
    for gate_name, gate_result in result.gate_results.items():
        status_icon = "✓" if gate_result.passed else "✗"
        status_color = "green" if gate_result.passed else "red"
        console.print(f"  [{status_color}]{status_icon} {gate_name}:[/bold] {gate_result.message}")

    # Audit verdict
    console.print()
    verdict_color = {
        "ship": "green",
        "minor_fix": "yellow",
        "major_rework": "orange3",
        "scrap": "red",
    }.get(result.audit_verdict, "white")
    console.print(f"[bold {verdict_color}]Audit Verdict: {result.audit_verdict}[/bold {verdict_color}]")

    # Save output
    output = {
        "question_id": result.question_id,
        "stem": result.stem,
        "tier": str(result.tier),
        "stem_pattern": result.stem_pattern,
        "correct_letter": result.correct_letter,
        "options": result.options,
        "flashcard_seeds": result.flashcard_seeds,
        "gate_results": {k: {"passed": v.passed, "message": v.message, "severity": v.severity} for k, v in result.gate_results.items()},
        "audit_verdict": result.audit_verdict,
    }

    output_dir = Path("data/test_runs")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{result.question_id}.json"
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)

    console.print()
    console.print(f"[green]Saved:[/green] {output_path}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--tier", type=int, default=2, choices=[1, 2, 3, 4])
    parser.add_argument("--variant", type=int, default=1, choices=[1, 2, 3, 4, 5])
    args = parser.parse_args()
    asyncio.run(test_generation(args.tier, args.variant))

