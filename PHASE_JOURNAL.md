# HERMES Development Journal

## Session 2026-05-01: Initial Analysis ✅

**Goal:** Read goliath + godzilla, create planning document.

**Accomplished:**
- ✅ Loaded educational-question-authoring skill
- ✅ Read goliath: CONTINUATION.md, ENRICHMENT_SPEC.md (80KB), STEM_PATTERN_SPEC.md (62KB), MEASUREMENT_INSTRUMENT_PLAN.md, pipeline/, scripts/
- ✅ Read godzilla: README.md, SESSION_JOURNAL.md, src/godzilla/pipeline/, prompts/
- ✅ Created HERMES_PIPELINE.md
- ✅ Committed to hermes2 repo

**Key Discoveries:**
1. Distractor-first eliminates english_gap (0.0% on 93 distractors)
2. Editorial ~45% is baseline LLM tendency, not pipeline bug
3. Tier 4 never generated in goliath production (user decision)
4. Eponym whitelist needs word-boundary regex (\band\b not and)
5. 20 stem patterns are tier-keyed with detailed specs

---

## Session 2026-05-01 (Continued): Phase 2 Core Pipeline ✅

**Goal:** Implement Pass A/B/C + gates + orchestrator

**Accomplished:**
- ✅ `src/hermes/constants.py` - Tier, DistractorLevel, MisconceptionType, DISTRACTOR_MIX, BLOOMS_VERBS
- ✅ `src/hermes/taxonomy.py` - Tier enforcement rules, Bloom's verbs
- ✅ `src/hermes/pipeline/pass_a.py` - Distractor design + contradictable_facts extraction
- ✅ `src/hermes/pipeline/pass_b.py` - Stem composition with redaction enforcement
- ✅ `src/hermes/pipeline/pass_c.py` - Flashcard seed generation (concept/comparison/nuance)
- ✅ `src/hermes/pipeline/gates.py` - 8+1 gates (Structure, RedactionViolation, ContentQuality, OptionLengthBalance, Consistency, DistractorMix, Attribution, AnchorGrounding, Uniqueness)
- ✅ `src/hermes/pipeline/orchestrator.py` - Main pipeline coordinator

**Key Implementations:**

### Pass A (Distractor Design)
- Generates 3 distractors + 1 correct answer
- Extracts `contradictable_facts` for redaction
- Uses claude-opus-4.7 with temperature=1.0 (extended thinking)

### Pass B (Stem with Redaction)
- "NEGATION COUNTS AS PRINTING" rule enforced
- Cannot print contradictable_facts OR their logical negations
- Stem pattern enforcement (20 patterns, tier-keyed)

### Gates Implemented
- `StructureGate` - JSON schema, 4 options, A-D
- `RedactionViolationGate` - Direct match + simple negation detection
- `ContentQualityGate` - No "all/none", lengths
- `OptionLengthBalanceGate` - Ratio < 1.7x, correct not >20% longer
- `ConsistencyGate` - Misconception types, levels match plan
- `DistractorMixGate` - Soft enforcement
- `AttributionGate` - 140-name eponym whitelist (abbreviated)
- `AnchorGroundingGate` - Concept from brief
- `UniquenessGate` - No duplicate stems

**Next Session:**
1. Add missing imports (json, Optional) to pass_b.py
2. Create CLI entry point (`src/hermes/cli.py`)
3. Create test script for single-anchor generation
4. Test end-to-end with one anchor
5. Fix any issues discovered

---

## Open Issues / TODO

1. `pass_b.py` missing imports: `json`, `Optional`, `get_tier_verbs`
2. `gates.py` typo: `EPYONYM_WHITELIST` should be `EPONYM_WHITELIST`
3. Full eponym whitelist needs 140 names (currently ~50)
4. Full stem pattern descriptions (currently 4 of 20)
5. Orchestrator placeholder: correct letter assignment, options assembly
6. Need anchor brief loading implementation
7. Need audit pass (Phase 5) - 4-class verdict
8. Need smart retry (Phase 6) - conditional retry logic

