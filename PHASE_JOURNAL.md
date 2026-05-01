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

**Open Questions:**
1. Prioritize editorial improvements early or accept baseline?
2. Start T4 with small test batch (10 questions)?
3. Confirm: OpenRouter (Qwen) or Anthropic direct?

---

## Session 2026-05-01 (Continued): Phase 2 Start ⏳

**Goal:** Implement core pipeline (Pass A/B/C)

**Plan:**
1. Create src/hermes/ directory structure
2. Implement constants.py (tier codes, distractor levels, misconception types)
3. Implement taxonomy.py (Bloom's verbs per tier)
4. Implement pipeline/pass_a.py (distractor design)
5. Implement pipeline/pass_b.py (stem with redaction)
6. Implement pipeline/pass_c.py (flashcard seeds)
7. Implement pipeline/gates.py (StructureGate, RedactionViolation_gate)
8. Test single anchor end-to-end

**Next:** Create core modules

