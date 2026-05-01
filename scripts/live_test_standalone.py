#!/usr/bin/env python3
"""Standalone live test - no package install needed.

Usage:
    export OPENROUTER_API_KEY="sk-or-..."
    python scripts/live_test_standalone.py
"""

import asyncio
import os
import json
import sys
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from enum import IntEnum

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Minimal imports - will import hermes modules inline where needed

console_output = []

def print_rich(text=""):
    """Mimic rich print."""
    print(text)
    console_output.append(str(text))


# BPSY Anchor: Hippocampal memory consolidation
BPSY_ANCHOR = {
    "uid": "D7-MEM-042",
    "domain_code": "BPSY",
    "verbatim_anchor": "The hippocampus is critical for memory consolidation—short-term memories transformed into long-term memories via LTP.",
    "testable_fact": "Hippocampus mediates memory consolidation via LTP over days to weeks.",
    "core_claim": "Hippocampal-dependent memory consolidation requires LTP and unfolds over extended time.",
    "tested_concept_id": "hippocampal-consolidation",
    "tested_concept_label": "Hippocampal Memory Consolidation",
    "tested_concept_description": "Process where hippocampus stabilizes short-term memories into long-term storage via LTP.",
}

STEM_PATTERNS = {
    1: ["direct_definition"],
    2: ["comparison"],
    3: ["clinical_vignette"],
    4: ["best_answer"],
}


async def generate_with_api(client, tier: int, pattern: str, anchor: dict, slots: list) -> dict:
    """Generate one question via API."""
    
    # Import here to avoid issues
    import httpx
    
    api_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
    
    # Build prompt
    tier_names = {1: "REMEMBER", 2: "UNDERSTAND", 3: "APPLY", 4: "EVALUATE"}
    
    system_prompt = f"""You are an expert EPPP exam writer. Generate a Tier {tier} ({tier_names[tier]}) question.

STEM PATTERN: {pattern}
- Tier 1 (direct_definition): Ask student to select correct definition. 1-2 sentences.
- Tier 2 (comparison): Identify key distinction between two concepts. 1-3 sentences.
- Tier 3 (clinical_vignette): Named clinician/client case. 3-5 sentences, include character name.
- Tier 4 (best_answer): All options contain truth; evaluate MOST correct. 3-5 sentences.

ANCHOR: {anchor['core_claim']}
CONCEPT: {anchor['tested_concept_label']} ({anchor['tested_concept_id']})

DISTRACTOR SLOTS: {json.dumps(slots)}
- L1: Cross-subdomain (different topic)
- L2: Same subdomain, different concept  
- L3: Same concept family
- L4: Partially correct

OUTPUT EXACTLY THIS JSON:
{{
  "stem": "...",
  "character_name": null or string,
  "correct_answer": {{"letter": "B", "text": "...", "concept_id": "...", "explanation": "..."}},
  "distractors": [
    {{"letter": "A", "text": "...", "level": 1, "misconception_type": "...", "explanation": "..."}},
    ...
  ],
  "contradictable_facts": ["fact1", "fact2"]
}}"""

    user_prompt = f"""Anchor: {anchor['verbatim_anchor'][:150]}
Testable: {anchor['testable_fact']}
Tier: {tier}, Pattern: {pattern}

Generate the question JSON now."""

    try:
        async with httpx.AsyncClient(timeout=60.0) as http:
            resp = await http.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "anthropic/claude-3-5-sonnet",
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "max_tokens": 2000,
                    "temperature": 0.7,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            
            # Extract JSON
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            
            result = json.loads(content.strip())
            return result
    except Exception as e:
        return {"error": str(e), "stem": "Generation failed", "correct_answer": {"letter": "A", "text": "Error"}, "distractors": []}


async def run_test():
    """Run the 4-tier test."""
    print_rich("=" * 60)
    print_rich("HERMES LIVE TEST: 1 BPSY Anchor × 4 Bloom's Tiers")
    print_rich("=" * 60)
    print_rich()
    print_rich(f"Anchor: {BPSY_ANCHOR['uid']}")
    print_rich(f"Concept: {BPSY_ANCHOR['tested_concept_label']}")
    print_rich()
    
    api_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print_rich("ERROR: No API key found. Set OPENROUTER_API_KEY or ANTHROPIC_API_KEY")
        return
    
    print_rich(f"API Key: {api_key[:15]}...")
    print_rich()
    
    slots_by_tier = {
        1: [{"level": 1, "type": "similar_store"}, {"level": 2, "type": "similar_property"}, {"level": 3, "type": "similar_name"}],
        2: [{"level": 1, "type": "similar_store"}, {"level": 2, "type": "similar_property"}, {"level": 3, "type": "opposite_direction"}],
        3: [{"level": 2, "type": "similar_name"}, {"level": 3, "type": "partial_understanding"}, {"level": 4, "type": "overgeneralization"}],
        4: [{"level": 3, "type": "partial_understanding"}, {"level": 4, "type": "similar_property"}, {"level": 4, "type": "similar_name"}],
    }
    
    results = []
    
    for tier in [1, 2, 3, 4]:
        pattern = STEM_PATTERNS[tier][0]
        slots = slots_by_tier[tier]
        
        print_rich("-" * 60)
        print_rich(f"TIER {tier} - Pattern: {pattern}")
        print_rich("-" * 60)
        
        result = await generate_with_api(None, tier, pattern, BPSY_ANCHOR, slots)
        
        if "error" in result:
            print_rich(f"ERROR: {result['error']}")
            results.append({"tier": tier, "error": result["error"]})
            continue
        
        # Display
        print_rich()
        print_rich(f"STEM:\n  {result.get('stem', 'N/A')}")
        print_rich()
        print_rich(f"Correct ({result.get('correct_answer', {}).get('letter', '?')}): {result.get('correct_answer', {}).get('text', 'N/A')[:80]}...")
        print_rich()
        print_rich("Distractors:")
        for i, d in enumerate(result.get('distractors', [])):
            print_rich(f"  {d.get('letter', chr(65+i))}. {d.get('text', 'N/A')[:60]}... (L{d.get('level', '?')})")
        print_rich()
        
        # Simple gate checks
        print_rich("Quick Checks:")
        stem = result.get('stem', '')
        facts = result.get('contradictable_facts', [])
        
        # Redaction check
        redact_pass = True
        for fact in facts:
            if fact.lower() in stem.lower():
                print_rich(f"  ✗ Redaction VIOLATION: '{fact}' found in stem")
                redact_pass = False
        if redact_pass:
            print_rich(f"  ✓ Redaction: Passed (no contradictable facts in stem)")
        
        # Length check
        opts = [result.get('correct_answer', {}).get('text', '')] + [d.get('text', '') for d in result.get('distractors', [])]
        lengths = [len(o) for o in opts if o]
        if lengths:
            ratio = max(lengths) / max(1, min(lengths))
            if ratio > 1.7:
                print_rich(f"  ✗ Length balance: {ratio:.2f}x (too high)")
            else:
                print_rich(f"  ✓ Length balance: {ratio:.2f}x")
        
        print_rich()
        results.append({"tier": tier, "result": result})
    
    # Summary
    print_rich("=" * 60)
    print_rich("SUMMARY")
    print_rich("=" * 60)
    successful = sum(1 for r in results if "result" in r)
    print_rich(f"Generated: {successful}/4 questions")
    print_rich()
    
    # Save
    output_dir = Path("data/live_tests")
    output_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = output_dir / f"bpsy_4tier_{ts}.json"
    
    with open(out_path, "w") as f:
        json.dump({"anchor": BPSY_ANCHOR, "results": results}, f, indent=2)
    
    print_rich(f"Saved: {out_path}")


if __name__ == "__main__":
    asyncio.run(run_test())
