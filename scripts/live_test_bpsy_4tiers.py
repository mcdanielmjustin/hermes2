#!/usr/bin/env python3
"""Live test: 1 BPSY anchor × 4 Bloom's tiers = 4 questions."""

import asyncio
import os
import json
from pathlib import Path
from datetime import datetime

import anthropic
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.markdown import Markdown

from hermes.constants import Tier
from hermes.pipeline.orchestrator import HermesOrchestrator
from hermes.export import export_to_csv

console = Console()

# Real BPSY anchor: Hippocampal role in memory consolidation
BPSY_ANCHOR = {
    "uid": "D7-MEM-042-hippocampal-consolidation",
    "domain_code": "BPSY",
    "verbatim_anchor": "The hippocampus is critical for memory consolidation—the process by which short-term memories are transformed into long-term memories. This process involves synaptic plasticity (long-term potentiation) and systems-level consolidation over days to weeks.",
    "testable_fact": "The hippocampus mediates memory consolidation via long-term potentiation (LTP), with systems consolidation occurring over days to weeks.",
    "core_claim": "Hippocampal-dependent memory consolidation requires LTP and unfolds over extended time periods through systems consolidation.",
    "tested_concept_id": "hippocampal-memory-consolidation",
    "tested_concept_label": "Hippocampal Memory Consolidation",
    "tested_concept_description": "The hippocampus-dependent process where short-term memories are stabilized into long-term storage through LTP and systems-level reorganization.",
    "misconception_slots_by_tier": {
        1: [
            {"level": 1, "misconception_id": "hippocampus-vs-cerebellum", "type": "similar_store"},
            {"level": 2, "misconception_id": "hippocampus-vs-amygdala", "type": "similar_property"},
            {"level": 3, "misconception_id": "consolidation-vs-encoding", "type": "similar_name"},
        ],
        2: [
            {"level": 1, "misconception_id": "hippocampus-vs-cortex", "type": "similar_store"},
            {"level": 2, "misconception_id": "synaptic-vs-systems-consolidation", "type": "similar_property"},
            {"level": 3, "misconception_id": "ltp-vs-ltd", "type": "opposite_direction"},
        ],
        3: [
            {"level": 2, "misconception_id": "anterograde-vs-retrograde", "type": "similar_name"},
            {"level": 3, "misconception_id": "consolidation-timecourse", "type": "partial_understanding"},
            {"level": 4, "misconception_id": "hippocampus-permanent-storage", "type": "overgeneralization"},
        ],
        4: [
            {"level": 3, "misconception_id": "standard-consolidation-model", "type": "partial_understanding"},
            {"level": 4, "misconception_id": "multiple-trace-theory", "type": "similar_property"},
            {"level": 4, "misconception_id": "memory-reconsolidation", "type": "similar_name"},
        ],
    },
}

STEM_PATTERNS = {
    1: ["direct_definition", "concept_identification", "fact_recognition", "true_false_which", "feature_listing"],
    2: ["comparison", "example_recognition", "simple_application", "paraphrase", "categorization"],
    3: ["clinical_vignette", "scenario_completion", "error_identification", "case_analysis", "mechanism_application"],
    4: ["contrast_prompt", "best_answer", "subtle_error", "competing_evidence", "integration"],
}


async def generate_4_tiers():
    """Generate 4 questions (T1-T4) for one BPSY anchor."""
    console.print(Panel.fit("[bold cyan]HERMES Live Test: BPSY Anchor × 4 Tiers[/bold cyan]"))
    console.print()
    console.print(f"[bold]Anchor:[/bold] {BPSY_ANCHOR['uid']}")
    console.print(f"[bold]Domain:[/bold] {BPSY_ANCHOR['domain_code']}")
    console.print(f"[bold]Concept:[/bold] {BPSY_ANCHOR['tested_concept_label']}")
    console.print()

    # Get API key
    api_key = os.getenv("ANTHROPIC_API_KEY") or os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        console.print("[red]Error:[/red] Set ANTHROPIC_API_KEY or OPENROUTER_API_KEY")
        console.print("Example: export ANTHROPIC_API_KEY=sk-ant-...")
        return

    client = anthropic.AsyncClient(api_key=api_key)
    orchestrator = HermesOrchestrator(client)

    results = []
    stats = {"shipped": 0, "minor_fix": 0, "major_rework": 0, "scrap": 0, "gates_passed": 0, "gates_total": 0}

    for tier_num in [1, 2, 3, 4]:
        tier = Tier(tier_num)
        variant = 1
        pattern = STEM_PATTERNS[tier_num][0]  # Use first pattern for each tier
        misconception_slots = BPSY_ANCHOR["misconception_slots_by_tier"][tier_num]

        console.print(Panel(f"[bold]Generating Tier {tier_num} ({tier.name})[/bold]\nPattern: {pattern}", style="cyan"))
        console.print()

        try:
            with console.status(f"[bold green]Tier {tier_num}: Pass A → B → C → Gates → Audit...") as status:
                result = await orchestrator.generate_question(
                    anchor_uid=BPSY_ANCHOR["uid"],
                    tier=tier,
                    variant=variant,
                    stem_pattern=pattern,
                    verbatim_anchor=BPSY_ANCHOR["verbatim_anchor"][:200],
                    testable_fact=BPSY_ANCHOR["testable_fact"],
                    core_claim=BPSY_ANCHOR["core_claim"],
                    tested_concept_id=BPSY_ANCHOR["tested_concept_id"],
                    tested_concept_label=BPSY_ANCHOR["tested_concept_label"],
                    tested_concept_description=BPSY_ANCHOR["tested_concept_description"],
                    misconception_slots=misconception_slots,
                    run_audit=True,
                )

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

            passed_gates = sum(1 for r in result.gate_results.values() if r.passed)
            stats["gates_passed"] += passed_gates
            stats["gates_total"] += len(result.gate_results)

            # Display stem
            console.print()
            console.print(Panel(result.stem, title=f"[bold]Tier {tier_num} Stem[/bold]", border_style="green"))

            # Options table
            table = Table(show_header=True, header_style="bold magenta", show_lines=True)
            table.add_column("Letter", style="bold")
            table.add_column("Correct")
            table.add_column("Text", width=60)
            table.add_column("Type/Level", width=25)

            for opt in result.options:
                is_correct = "✓" if opt["is_correct"] else ""
                type_info = ""
                if opt["is_correct"]:
                    type_info = f"[green]Concept:[/green] {opt.get('concept_id', 'N/A')[:30]}"
                else:
                    level = opt.get('distractor_level', '?')
                    ms_type = opt.get('misconception_type', 'N/A')
                    type_info = f"[yellow]L{level}[/yellow] / {ms_type}"
                text-preview = opt["text"][:57] + "..." if len(opt["text"]) > 60 else opt["text"]
                table.add_row(opt["letter"], is_correct, text-preview, type_info)

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
                "ship": "bold green",
                "minor_fix": "bold yellow",
                "major_rework": "bold orange3",
                "scrap": "bold red",
            }.get(verdict, "white")
            console.print(f"[{verdict_color}]Audit Verdict: {verdict}[/{verdict_color}]")
            console.print()
            console.print("-" * 80)
            console.print()

            # Store result
            results.append({
                "question_id": result.question_id,
                "stem": result.stem,
                "tier": tier_num,
                "stem_pattern": result.stem_pattern,
                "correct_letter": result.correct_letter,
                "options": result.options,
                "metadata": result.metadata,
                "flashcard_seeds": result.flashcard_seeds,
                "gate_results": {k: {"passed": v.passed, "message": v.message} for k, v in result.gate_results.items()},
                "audit_verdict": verdict,
            })

        except Exception as e:
            console.print(f"[red]Error generating Tier {tier_num}: {e}[/red]")
            import traceback
            console.print(traceback.format_exc())

    # Summary
    console.print()
    console.print(Panel.fit(
        f"[bold green]Live Test Complete![/bold green]\n\n"
        f"[bold]Anchor:[/bold] {BPSY_ANCHOR['uid']}\n"
        f"[bold]Questions Generated:[/bold] {len(results)}/4\n"
        f"[bold]Shipped:[/bold] {stats['shipped']}\n"
        f"[bold]Minor Fix:[/bold] {stats['minor_fix']}\n"
        f"[bold]Major Rework:[/bold] {stats['major_rework']}\n"
        f"[bold]Scrap:[/bold] {stats['scrap']}\n"
        f"[bold]Gates Passed:[/bold] {stats['gates_passed']}/{stats['gates_total']} ({stats['gates_passed']/max(1,stats['gates_total'])*100:.0f}%)"
    ))

    # Save results
    output_dir = Path("data/live_tests")
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = output_dir / f"bpsy_4tier_{timestamp}.json"
    
    with open(output_path, "w") as f:
        json.dump({
            "anchor": BPSY_ANCHOR,
            "generated_at": timestamp,
            "stats": stats,
            "questions": results,
        }, f, indent=2)

    console.print(f"\n[green]Saved:[/green] {output_path}")

    # Export to CSV
    csv_path = export_to_csv(results, str(output_dir / f"bpsy_4tier_{timestamp}.csv"))
    console.print(f"[green]CSV Export:[/green] {csv_path}")

    return results


if __name__ == "__main__":
    console.print("[bold yellow]HERMES Live Test[/bold yellow]\n")
    console.print("This script generates 4 questions (Tier 1-4) for 1 BPSY anchor.")
    console.print("Requires: ANTHROPIC_API_KEY or OPENROUTER_API_KEY\n")
    asyncio.run(generate_4_tiers())
