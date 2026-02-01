# Archived Scripts - Pre-Integration

These scripts use the OLD architecture (pre-Phases 1-6) and are incompatible with the new MemoryHierarchy system.

## Deprecated Scripts

### train_foundation.py
- **Issue**: Used Gen() directly, raw VoxelCloud without MemoryHierarchy
- **Incompatible with**: Phases 1-6 architecture (MemoryHierarchy, TemporalBuffer, etc.)

### demo_foundation.py
- **Issue**: Old architecture patterns, direct VoxelCloud usage
- **Incompatible with**: ConversationPipeline, StreamingSynthesizer

### test_foundation.py
- **Issue**: Pre-Phase 1 testing approach
- **Incompatible with**: New test suite structure (tests/test_phase*.py)

## Replacement

Use `genesis.js` commands instead:

### Training
```bash
genesis.js train --data /usr/lib/alembic/data/datasets/curated/foundation/ --output ./models/genesis_foundation.pkl
```

### Interactive Chat
```bash
genesis.js chat --model ./models/genesis_foundation.pkl --stream
```

### Testing
```bash
genesis.js test [--gpu] [--benchmark]
```

### Evaluation
```bash
genesis.js eval --model ./models/genesis_foundation.pkl --test-cases tests/test_cases.json
```

## Architecture Migration Notes

The old scripts directly instantiated:
- `Origin.Gen()` → Now wrapped in `MemoryHierarchy`
- `VoxelCloud` → Now managed by `CoreMemory`
- Raw synthesis → Now through `ConversationPipeline`

See `docs/INTEGRATION_PLAN.md` for detailed migration guide.

**Date Archived**: 2025-11-30
**Reason**: Incompatible with MemoryHierarchy (Phases 1-6) architecture
**Integration Status**: Complete through Phase 6, awaiting Phase 7 cleanup