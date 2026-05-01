# HERMES Development Journal

## Session 2026-05-01: Phases 2-4 Complete ✅

### Accomplished

#### Phase 2: Core Pipeline (15 files)
Pass A/B/C, 8+1 gates, orchestrator, CLI, tests

#### Phase 3: Audit + Integration (3 files)
- `audit.py` - 4-class verdict + Bloom's shape
- Fixed gates.py typo, expanded whitelist to 140 names
- `test_generation.py` - End-to-end test script

#### Phase 4: Smart Retry + Batch + Export (4 files NEW)
- `src/hermes/pipeline/retry.py` - Phase 6: Gate-specific retry guidance
- `src/hermes/pipeline/batch.py` - Cohort generation with concurrency
- `src/hermes/export/csv_export.py` - 62-column Supabase-compatible CSV
- `src/hermes/export/__init__.py`

**Total: 24 files across 10 commits**

---

### Complete Pipeline Status

| Phase | Component | Status |
|-------|-----------|--------|
| 0 | Anchor Resolve | 🔄 Partial (mock data) |
| 1 | Pass A (Distractors) | ✅ Complete |
| 2 | Pass B (Stem + Redaction) | ✅ Complete |
| 3 | Pass C (Flashcards) | ✅ Complete |
| 4 | Validation (8+1 gates) | ✅ Complete |
| 5 | Audit (4-class verdict) | ✅ Complete |
| 6 | Smart Retry | ✅ Complete |
| 7 | Assembly + Export | ✅ Complete |

---

### Key Features

**1. Distractor-First Architecture**
- Pass A → extract contradictable_facts → Pass B with REDACTION
- RedactionViolationGate enforces "NEGATION COUNTS AS PRINTING"
- Target: 0.0% english_gap (godzilla validated this)

**2. 8+1 Validation Gates**
- StructureGate, ContentQualityGate, ConsistencyGate
- AnchorGroundingGate, AttributionGate (140-name whitelist)
- OptionLengthBalanceGate, DistractorMixGate (soft)
- UniquenessGate, **RedactionViolationGate** (NEW)

**3. Smart Retry (Phase 6)**
- Gate-specific guidance templates
- Decision rules: retry vs escalate
- Max 1 retry, then human review

**4. Batch Generation**
- Concurrent workers (configurable)
- Progress tracking with rich
- Manifest with statistics

**5. Export Pipeline**
- 62-column CSV (Supabase-compatible)
- Per-domain JSON bundles
- Flashcard seeds included

---

### Usage

**Single Question:**
```bash
python scripts/test_generation.py --tier 2 --variant 1
```

**Batch Cohort (when anchors loaded):**
```python
from hermes.pipeline.batch import BatchGenerator

generator = BatchGenerator(client)
manifest = await generator.generate_cohort(
    run_id="v1_test",
    anchors=anchor_list,
    tiers=[1, 2, 3, 4],
    variants_per_tier=5,
    max_workers=5,
)
```

**Export:**
```python
from hermes.export import export_to_csv, export_to_json_bundle

export_to_csv(questions, "data/export/enrichment.csv")
export_to_json_bundle(questions, "data/export/bundles/", by_domain=True)
```

---

### Next: Validation Run

1. **Test single generation** - Validate pipeline works
2. **Load real anchors** - From goliath csvs/anchor_points.csv
3. **Generate 32-question cohort** - Prove english_gap = 0.0%
4. **Compare to goliath** - Run goliath auditors on hermes output
5. **Iterate on discoveries**

---

### Metrics to Track

| Metric | Target | Goliath | Godzilla | HERMES |
|--------|--------|---------|----------|--------|
| english_gap | 0.0% | 6-9% | 0.0% | TBD |
| Editorial major | <20% | 42% | 45% | TBD |
| Tier fit | ≥80% | ~40% | TBD | TBD |
| Cost/question | ~$0.30 | ~$0.30 | $0.245 | ~$0.30 |
| First-pass rate | >85% | ~78% | 75% | TBD |

---

### Files Created This Session

| File | Purpose |
|------|---------|
| `retry.py` | Gate-specific retry guidance |
| `batch.py` | Cohort generation |
| `csv_export.py` | Supabase-compatible CSV export |
| `export/__init__.py` | Export module init |

---

**Ready for first live test run!**
