"""Export pipeline - CSV/JSON bundles for deployment."""

import csv
import json
from pathlib import Path
from datetime import datetime

from rich.console import Console

console = Console()


def export_to_csv(questions: list[dict], output_path: str) -> str:
    """Export questions to flat CSV (Supabase-compatible format).

    62-column schema matching goliath's enrichment_all_questions.csv.
    """
    # Flattened schema (subset - full schema has 62 columns)
    fieldnames = [
        "question_id", "stem_pattern", "difficulty_tier", "blooms_primary", "blooms_secondary",
        "question_stem", "option_a", "option_b", "option_c", "option_d", "correct_answer",
        "explanation_a", "explanation_b", "explanation_c", "explanation_d",
        "tested_concept_id", "tested_concept_label", "knowledge_tested",
        "anchor_uid", "domain_code", "chapter_num",
        "distractor_1_letter", "distractor_1_level", "distractor_1_misconception_type",
        "distractor_2_letter", "distractor_2_level", "distractor_2_misconception_type",
        "distractor_3_letter", "distractor_3_level", "distractor_3_misconception_type",
        "flashcard_concept_front", "flashcard_concept_back",
        "flashcard_comparison_front", "flashcard_comparison_back",
        "flashcard_nuance_front", "flashcard_nuance_back",
        "generation_batch", "generated_by",
    ]

    rows = []
    for q in questions:
        # Extract options
        options = q.get("options", [])
        options_by_letter = {opt["letter"]: opt for opt in options}

        row = {
            "question_id": q.get("question_id", ""),
            "stem_pattern": q.get("stem_pattern", ""),
            "difficulty_tier": q.get("tier", "").value if hasattr(q.get("tier"), "value") else q.get("tier"),
            "blooms_primary": _tier_to_blooms(q.get("tier")),
            "blooms_secondary": _tier_to_blooms_secondary(q.get("tier")),
            "question_stem": q.get("stem", ""),
            "option_a": options_by_letter.get("A", {}).get("text", ""),
            "option_b": options_by_letter.get("B", {}).get("text", ""),
            "option_c": options_by_letter.get("C", {}).get("text", ""),
            "option_d": options_by_letter.get("D", {}).get("text", ""),
            "correct_answer": q.get("correct_letter", ""),
            "explanation_a": options_by_letter.get("A", {}).get("explanation", ""),
            "explanation_b": options_by_letter.get("B", {}).get("explanation", ""),
            "explanation_c": options_by_letter.get("C", {}).get("explanation", ""),
            "explanation_d": options_by_letter.get("D", {}).get("explanation", ""),
            "tested_concept_id": q.get("metadata", {}).get("tested_concept_id", ""),
            "tested_concept_label": q.get("metadata", {}).get("tested_concept_label", ""),
            "knowledge_tested": q.get("metadata", {}).get("knowledge_tested", ""),
            "anchor_uid": q.get("metadata", {}).get("anchor_uid", ""),
            "distractor_1_letter": _get_distractor_letter(options, 0),
            "distractor_1_level": _get_distractor_level(options, 0),
            "distractor_1_misconception_type": _get_distractor_misconception(options, 0),
            "distractor_2_letter": _get_distractor_letter(options, 1),
            "distractor_2_level": _get_distractor_level(options, 1),
            "distractor_2_misconception_type": _get_distractor_misconception(options, 1),
            "distractor_3_letter": _get_distractor_letter(options, 2),
            "distractor_3_level": _get_distractor_level(options, 2),
            "distractor_3_misconception_type": _get_distractor_misconception(options, 2),
            "generation_batch": datetime.utcnow().isoformat(),
            "generated_by": "hermes2-v0.1.0",
        }

        # Flashcard seeds
        seeds = q.get("flashcard_seeds", [])
        for seed in seeds:
            if seed["type"] == "concept":
                row["flashcard_concept_front"] = seed["front"]
                row["flashcard_concept_back"] = seed["back"]
            elif seed["type"] == "comparison":
                row["flashcard_comparison_front"] = seed["front"]
                row["flashcard_comparison_back"] = seed["back"]
            elif seed["type"] == "nuance":
                row["flashcard_nuance_front"] = seed["front"]
                row["flashcard_nuance_back"] = seed["back"]

        rows.append(row)

    # Write CSV
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    with open(output, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    console.print(f"[green]Exported {len(rows)} questions to {output}[/green]")
    return str(output)


def _tier_to_blooms(tier):
    """Map tier to primary Bloom's level."""
    mapping = {1: "remember", 2: "understand", 3: "apply", 4: "evaluate"}
    if hasattr(tier, "value"):
        tier = tier.value
    return mapping.get(tier, "apply")


def _tier_to_blooms_secondary(tier):
    """Map tier to secondary Bloom's level."""
    mapping = {1: "understand", 2: "apply", 3: "analyze", 4: "analyze"}
    if hasattr(tier, "value"):
        tier = tier.value
    return mapping.get(tier, "analyze")


def _get_distractor_letter(options: list, index: int) -> str:
    """Get letter of distractor at index (non-correct options only)."""
    non_correct = [opt for opt in options if not opt.get("is_correct")]
    if index < len(non_correct):
        return non_correct[index].get("letter", "")
    return ""


def _get_distractor_level(options: list, index: int) -> int:
    """Get level of distractor at index."""
    non_correct = [opt for opt in options if not opt.get("is_correct")]
    if index < len(non_correct):
        return non_correct[index].get("distractor_level", 0)
    return 0


def _get_distractor_misconception(options: list, index: int) -> str:
    """Get misconception type of distractor at index."""
    non_correct = [opt for opt in options if not opt.get("is_correct")]
    if index < len(non_correct):
        return non_correct[index].get("misconception_type", "")
    return ""


def export_to_json_bundle(questions: list[dict], output_dir: str, by_domain: bool = True) -> str:
    """Export questions to JSON bundles (per-domain or single file)."""

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    if by_domain:
        # Group by domain
        by_domain_dict = {}
        for q in questions:
            domain = q.get("metadata", {}).get("domain_code", "UNKNOWN")
            if domain not in by_domain_dict:
                by_domain_dict[domain] = []
            by_domain_dict[domain].append(q)

        # Write per-domain files
        for domain, domain_questions in by_domain_dict.items():
            domain_path = output / f"{domain.lower()}_quiz.json"
            with open(domain_path, "w") as f:
                json.dump(domain_questions, f, indent=2)
            console.print(f"[green]{domain}: {len(domain_questions)} questions → {domain_path}[/green]")
    else:
        # Single file
        bundle_path = output / "all_questions.json"
        with open(bundle_path, "w") as f:
            json.dump(questions, f, indent=2)
        console.print(f"[green]{len(questions)} questions → {bundle_path}[/green]")

    return str(output)

