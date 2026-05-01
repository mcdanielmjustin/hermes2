# HERMES Pipeline — Bloom's 1-4 Question Generation

**Version:** 1.0.0  
**Created:** 2026-05-01  
**Status:** Planning → Phase 2 Implementation  
**Source Analysis:** goliath v2.1 + godzilla v1.0 (mcdanielmjustin)

---

## Executive Summary

HERMES synthesizes godzilla's **distractor-first architecture** (0% english_gap) with goliath's **8-gate validation maturity** (anchor briefs, measurement targets, audit passes).

**Core Thesis:** Distractor-first generation eliminates english_gap. But structural correctness alone isn't enough — questions must also be factually accurate, unambiguous, tier-appropriate, and diagnostically meaningful.

---

## Discovery Summary

### From GOLIATH

**Strengths:**
- 8-Gate Validation (Structure, ContentQuality, Consistency, AnchorGrounding, Attribution, OptionLengthBalance, DistractorMix, Uniqueness)
- Anchor Brief System ($0.50/anchor: core_claims, 5-8 concepts, 8-12 misconceptions, tier-keyed question_angles)
- 20 Stem Patterns (5 per tier with detailed specs)
- Audit Passes (factual_correctness ~10% error, ambiguity ~16%, tier_fit 60% scope_creep)

**Weaknesses:**
- English Gap: 6-9% (distractors rejectable by reading stem)
- Single-pass generation (stem+distractors together)
- Editorial: 42% major issues

### From GODZILLA

**Strengths:**
- Distractor-First: Pass A (distractors + contradictable_facts) → Pass B (stem with redaction) → **0.0% english_gap** on 93 distractors
- 6-Pass Pipeline (clean separation)
- Redaction: "NEGATION COUNTS AS PRINTING"
- Cost: $0.245 cached

**Weaknesses:**
- Editorial: 45% (same baseline)
- 6 gates vs goliath's 8
- Length gate over-rejection at 1.7×

---

## HERMES Architecture

### Pipeline Overview

```
Phase 0: Anchor Resolve → Load brief OR chapter vocab
Phase 1: Pass A (~$0.15) → 3 distractors + correct + contradictable_facts
Phase 2: Pass B (~$0.10 cached) → Stem with REDACTION
Phase 3: Pass C (~$0.02) → Flashcard seeds
Phase 4: Validation ($0) → 8+1 gates
Phase 5: Audit (~$0.03) → 4-class verdict + Bloom's shape
Phase 6: Smart Retry (~$0.15) → Max 1 retry
Phase 7: Assembly ($0) → Export JSON + CSV
```

### Comparison

| Feature | Goliath | Godzilla | HERMES |
|---------|---------|----------|--------|
| Distractor-first | ❌ | ✅ | ✅ |
| Gates | 8 | 6 | 8+1 |
| Anchor briefs | ✅ | ✅ | ✅ |
| Stem patterns | 20 | 20 | 20 + enforcement |
| Measurement target | Post-hoc | ❌ | Input |
| English gap | 6-9% | 0.0% | 0.0% |
| Editorial | 42% | 45% | <20% target |

---

## Specifications

### Distractor Mix

| Tier | Bloom's | Mix |
|------|---------|-----|
| T1 | Remember | 1×L1, 1×L2, 1×L3 |
| T2 | Understand | 1×L1, 1×L2, 1×L3 |
| T3 | Apply | 1×L2, 1×L3, 1×L4 |
| T4 | Evaluate | 1×L3, 2×L4 |

### Redaction Enforcement

```python
class PassAOutput:
    distractors: list[Distractor]
    correct_answer: CorrectOption
    contradictable_facts: list[str]  # Stem cannot print these OR negations

# Pass B Rule: "NEGATION COUNTS AS PRINTING"
# If fact = 'varies actions', stem cannot say 'does not vary actions'
```

### Gates (8+1)

1. StructureGate — JSON schema, 4 options, A-D
2. ContentQualityGate — No "all/none", lengths
3. ConsistencyGate — Misconception types, levels
4. AnchorGroundingGate — Concept from brief
5. AttributionGate — 140-name eponym whitelist
6. OptionLengthBalanceGate — Ratio < 1.7×
7. DistractorMixGate — Soft enforcement
8. UniquenessGate — No duplicates
9. **RedactionViolationGate** — NEW

---

## Milestones

| # | Milestone | Status |
|---|-----------|--------|
| M1 | Repo scaffold | ✅ Done |
| M2 | Core pipeline (Pass A/B/C) | ⏳ Next |
| M3 | 8+1 gates | ⏳ |
| M4 | 20 stem patterns | ⏳ |
| M5 | Anchor brief integration | ⏳ |
| M6 | Audit pass | ⏳ |
| M7 | Validation cohort (32q) | ⏳ |
| M8 | Ship decision | ⏳ |

---

## Validation Criteria (Ship)

| Priority | Criterion | Target | Goliath | HERMES |
|----------|-----------|---------|---------|--------|
| 1 | english_gap | <2% | 6-9% | **0.0%** |
| 2 | Coherence (manual 10) | Pass | Pass | Pass |
| 3 | Editorial major | <20% | 42% | <20% |
| 4 | Tier preservation | ≥80% | ~40% | ≥80% |
| 5 | Cost | ≤$0.30 | ~$0.30 | ~$0.30 |
| 6 | Factual error | <5% | ~10% | <5% |
| 7 | Ambiguity | <10% | ~16% | <10% |

**Ship Rule:** P1 MUST hit. P3 tolerated at baseline if structural clean.

---

## Next: Phase 2 Implementation

1. Implement Pass A (distractor design + contradictable_facts)
2. Implement Pass B (stem with redaction)
3. Implement Pass C (flashcard seeds)
4. Wire StructureGate + RedactionViolationGate
5. Test single anchor end-to-end
