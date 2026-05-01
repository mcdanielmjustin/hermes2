# HERMES Development Journal

## Session 2026-05-01: Phase 2-3 Complete ✅

### Accomplished

**Phase 2: Core Pipeline** - 15 files created
- Pass A (distractors), Pass B (stem w/ redaction), Pass C (flashcards)
- 8+1 gates including RedactionViolationGate
- Orchestrator, CLI, tests

**Phase 3: Audit + Integration** - 3 files updated/added
- `src/hermes/pipeline/gates.py` - Fixed `EPONYM_WHITELIST` typo, 140+ names
- `src/hermes/pipeline/audit.py` - 4-class verdict + Bloom's shape
- `src/hermes/pipeline/orchestrator.py` - Options assembly, audit wiring
- `scripts/test_generation.py` - End-to-end test with rich output

### Repository Status

**20 files total:**

| Category | Files |
|----------|-------|
| Planning | `HERMES_PIPELINE.md`, `README.md`, `PHASE_JOURNAL.md`, `pyproject.toml` |
| Core | `constants.py`, `taxonomy.py`, `cli.py` |
| Pipeline | `pass_a.py`, `pass_b.py`, `pass_c.py`, `gates.py`, `orchestrator.py`, `audit.py` |
| Tests | `tests/test_gates.py` |
| Scripts | `scripts/test_generation.py` |

### Key Features Implemented

1. **Distractor-First Architecture** - Pass A generates distractors + extracts contradictable_facts, Pass B composes stem with REDACTION
2. **20 Stem Patterns** - All patterns defined, tier-keyed
3. **8+1 Validation Gates** - Structure, RedactionViolation (NEW), ContentQuality, OptionLengthBalance, Consistency, DistractorMix (soft), Attribution (140-name whitelist), AnchorGrounding, Uniqueness
4. **Audit Pass** - 4-class verdict (ship/minor_fix/major_rework/scrap) + Bloom's shape
5. **Options Assembly** - Correct answer position cycling (20-position balanced cycle)
6. **CLI** - `hermes generate --anchor-uid X --tier N`

### Next: Test Run

```bash
export ANTHROPIC_API_KEY=sk-...
python scripts/test_generation.py --tier 2 --variant 1
```

This will:
1. Generate 1 question (Tier 2, variant 1)
2. Run through Pass A → B → C → gates → audit
3. Display stem, options table, gate results, verdict
4. Save to `data/test_runs/UID-T2-V1.json`

### Validation Targets

| Criterion | Target | Goliath | Godzilla |
|-----------|--------|---------|----------|
| english_gap | 0.0% | 6-9% | 0.0% |
| Editorial | <20% | 42% | 45% |
| Tier fit | ≥80% | ~40% | TBD |
| Cost | ~$0.30 | ~$0.30 | $0.245 |

### Remaining Work

- [ ] Phase 6: Smart Retry (conditional retry logic)
- [ ] Anchor brief loading from disk
- [ ] Batch generation script (cohort mode)
- [ ] Export to CSV/JSON bundles
- [ ] Run validation cohort (32 questions)
- [ ] Compare metrics to goliath baseline
