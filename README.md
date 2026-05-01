# HERMES2

**Bloom's-faithful question generation for EPPP exam prep**

HERMES synthesizes [godzilla](https://github.com/mcdanielmjustin/godzilla)'s distractor-first architecture (0% english_gap) with [goliath](https://github.com/mcdanielmjustin/goliath)'s 8-gate validation maturity.

## Status

🚧 **Phase 2: Core Pipeline Implementation**

See [`HERMES_PIPELINE.md`](./HERMES_PIPELINE.md) for full architecture.

## Quick Start (When Implemented)

```bash
pip install -e .
hermes generate --anchor-uid D7-BPSY-021 --tier 2
hermes generate-cohort --domain BPSY --count 32
hermes audit --run-id latest
```

## Architecture

| Phase | Component | Function |
|-------|-----------|----------|
| 0 | Anchor Resolve | Load brief OR chapter vocab |
| 1 | Pass A | Distractors + contradictable_facts |
| 2 | Pass B | Stem with REDACTION |
| 3 | Pass C | Flashcard seeds |
| 4 | Validation | 8+1 gates |
| 5 | Audit | 4-class verdict |
| 6 | Retry | Max 1 retry |
| 7 | Assembly | Export |

## Key Innovations

1. **Distractor-First** — Eliminates english_gap
2. **Redaction** — Stem cannot expose distractors
3. **20 Stem Patterns** — 5 per Bloom's tier
4. **8+1 Gates** — Structural + redaction validation
5. **Measurement Targets** — Generation input, not post-hoc

## Comparison

| Feature | Goliath | Godzilla | HERMES |
|---------|---------|----------|--------|
| Distractor-first | ❌ | ✅ | ✅ |
| Gates | 8 | 6 | 8+1 |
| english_gap | 6-9% | 0.0% | 0.0% target |
| Editorial | 42% | 45% | <20% target |

## License

MIT

