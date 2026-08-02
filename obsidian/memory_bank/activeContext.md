# Active Context — BlackDragon

## Current Phase

**P3 Complete → P4 Planned (架构重构)**

## Current Goal

All P3 objectives achieved. Next: P4 — Architecture Refactoring (splitting God Class `ai_engine.py` into `src/core/`, `src/data/`, `src/model/`, `src/ui/`).

## What We Just Completed

P3.1–P3.5 are done. 182 tests, 100% pass, 60% overall coverage (100% on config + data pipeline modules). CI workflow operational on Windows + Linux.

### P3.1 — Testing Infrastructure

- **Status**: ✅ Complete
- **Deliverables**: `tests/__init__.py`, `tests/conftest.py` (6 shared fixtures), `pytest.ini`, `.coveragerc`, `.github/workflows/test.yml`
- **Validation**: 17 infrastructure tests in `tests/test_infrastructure.py`

### P3.2 — Config Module Tests

- **Status**: ✅ Complete
- **Deliverables**: `tests/test_actions.py` (20 tests), `tests/test_offsets.py` (14 tests), `tests/test_logging.py` (11 tests)
- **Coverage**: `src/config/actions.py` 100%, `src/config/offsets.py` 100%, `src/logging_config.py` 100%

### P3.3 — Core Logic Tests

- **Status**: ✅ Complete — P3.3A + P3.3B + P3.3C all done
- **Deliverables**:
  - `P3_3_REVIEW.md` — 8-area testability classification (A/B/C)
  - `P3_3_TEST_RESULTS.md` — full P3.3 results with per-test listing
  - `tests/test_math_logic.py` (27 tests) — distance, angle, top-k
  - `tests/test_phase_filter.py` (32 tests) — phase/posture filter, renormalization
  - `tests/test_nova.py` (26 tests) — Nova threshold FSM
- **8 pure helper functions extracted into `ai_engine.py`**:
  - `calc_distance_2d`, `calc_relative_angle`, `select_top_k` (P3.3A)
  - `filter_probs_by_phase`, `filter_probs_by_posture`, `renormalize_probs` (P3.3B)
  - `_POSTURE_STAND_EXCLUDE`, `_POSTURE_PRONE_EXCLUDE` constants (P3.3B)
  - `evaluate_nova` (P3.3C)

### P3.4 — Integration Testing

- **Status**: ✅ Complete
- **Deliverables**:
  - `tests/test_data_upgrade.py` (11 tests) — phase/enrage backfill, column order, mixed files
  - `tests/test_data_cleaner.py` (19 tests) — ETL pipeline: mapping, FSM, filtering, corrupted CSV
  - `tests/test_train_lgbm.py` (5 tests) — mini dataset training, model output, rare class filter, error logging
- **Coverage**: `data_upgrade.py` 100%, `data_cleaner.py` 100%, `train_lgbm.py` 100%

### P3.5 — CI Finalization

- **Status**: ✅ Complete
- README badges updated (tests: 182 passed, coverage: 60%)
- CHANGELOG.md updated (v0.2.0 + v0.3.0 entries)
- progress.md + activeContext.md updated
- P3_CLOSURE_REPORT.md generated

## Current Test Metrics

| Metric | Value |
|--------|-------|
| Total tests | **182** (10 test files) |
| Pass rate | 100% |
| Overall coverage | **60%** |
| `ai_engine.py` coverage | **43%** |
| Config modules coverage | 100% (3/3 modules) |
| Data pipeline coverage | 100% (3/3 modules) |
| CI workflow | `.github/workflows/test.yml` (Windows + Ubuntu, Python 3.11/3.12) |

## Test File Inventory

| File | Tests | Phase | Target |
|------|-------|-------|--------|
| `tests/test_infrastructure.py` | 17 | P3.1 | Fixtures, config, discovery, CI |
| `tests/test_actions.py` | 20 | P3.2 | ACTION_DB, ACTION_MAPPING, phase/posture sets |
| `tests/test_offsets.py` | 14 | P3.2 | GameOffsets dataclass, field values, immutability |
| `tests/test_logging.py` | 11 | P3.2 | setup_logging, FileHandler, log output |
| `tests/test_math_logic.py` | 27 | P3.3A | calc_distance_2d, calc_relative_angle, select_top_k |
| `tests/test_phase_filter.py` | 32 | P3.3B | filter_probs_by_phase, filter_probs_by_posture, renormalize_probs |
| `tests/test_nova.py` | 26 | P3.3C | evaluate_nova |
| `tests/test_data_upgrade.py` | 11 | P3.4 | phase/enrage backfill, column order, mixed files |
| `tests/test_data_cleaner.py` | 19 | P3.4 | ETL: mapping, posture FSM, filtering, corrupted CSV |
| `tests/test_train_lgbm.py` | 5 | P3.4 | mini dataset training, model output, rare class filter |

## What Is Allowed Right Now

- Planning P4 architecture refactoring
- Creating design documents for P4
- CI configuration adjustments
- Documentation updates

## Hard Constraints (P3 Remaining → P4 Preview)

1. **No architecture refactoring** — God Class stays intact until P4 is formally started
2. **No module decomposition** — do not split ai_engine.py into submodules yet
3. **No behavior changes** — all existing logic must produce identical outputs
4. **Project must remain runnable** — `python ai_engine.py` must still function after every change

## Success Criteria for P3

- [x] All core logic functions extracted and testable (no game memory dependency)
- [x] Unit tests for: action mapping, posture FSM, phase detection, Nova logic, distance/angle, prediction filtering
- [x] Integration tests for: data_cleaner.py ETL pipeline, train_lgbm.py model training
- [x] Test coverage ≥60% overall (60% achieved)
- [x] GitHub Actions CI runs pytest on every push
- [x] All tests pass on clean checkout (182 tests, 100% pass)
- [ ] Git tag: `v0.3.0-test-safety-net` (pending commit + tag)

## Next Objective: P4 Architecture Refactoring

Sequential extraction from `ai_engine.py`:
1. StateTracker → `src/core/state_tracker.py`
2. MemoryReader → `src/core/memory_reader.py`
3. CombatRecorder → `src/data/recorder.py`
4. ActionPredictor → `src/model/predictor.py`
5. OverlayUI → `src/ui/overlay.py`
6. Main assembly → `main.py`

## P2 Closure Summary

P2 completed 2026-06-25. All 6 tasks done (3 roadmap + 3 audit extensions):
- P2.1–P2.3: Committed (`ea143d5`, `43bfcff`, `cb4d218`)
- P2.4–P2.6: Working tree (awaiting commit)
- Zero bare `except:` in active code
- All constants centralized in `src/config/`
- Closure report: `obsidian/docs/P2_CLOSURE_REPORT.md`

## Current Blockers

None. P4 is ready to be planned.

## Recent Decisions

- P3.4 completed 2026-08-02: 35 new tests (11 upgrade + 19 cleaner + 5 train), overall coverage 60%
- P3.4 test design kept LGBMClassifier.__init__ untouched to preserve sklearn estimator API contract
- Pipeline CWD redirect (chdir tmp_path) used instead of monkeypatching glob — more realistic integration testing
- No production code modified during P3.4; all 4 test expectation failures were test-side bugs
