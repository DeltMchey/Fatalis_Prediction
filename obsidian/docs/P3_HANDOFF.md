# P3 Handoff — Test Safety Net (测试体系)

> **Date**: 2026-06-30
> **Status**: P3.1–P3.3 Complete → **P3.4 Ready**
> **Purpose**: Allow any new Claude Code session to resume P3 work immediately.

---

## 1. Repository Status

```
Branch:     master
Last commit: 621a40a "P2.4-P2.6: Complete remaining P2 tasks + closure audit"
Working tree: Clean — all P3 work is uncommitted (?? and M files)
Python:     3.12.6 (venv at .venv/)
Tests:      147 passed, 0 failed
Coverage:   29% overall
```

### Changed Files

| Status | File | Phase |
|--------|------|-------|
| M | `ai_engine.py` | P3.3 — 8 new pure functions + call-site replacements |
| M | `memory-bank/activeContext.md` | P3.4 phase declaration |
| ?? | `tests/` (10 files) | P3.1–P3.3 test suite |
| ?? | `pytest.ini` | P3.1 pytest config |
| ?? | `.coveragerc` | P3.1 coverage config |
| ?? | `.github/workflows/test.yml` | P3.1 CI workflow |
| ?? | `P3_3_REVIEW.md` | P3.3 testability analysis |
| ?? | `P3_3_TEST_RESULTS.md` | P3.3 full test results |
| ?? | `P3_EXECUTION_PLAN.md` | P3 master plan |
| ?? | `TEST_COVERAGE_MAP.md` | Coverage target map |
| ?? | `TEST_PRIORITY_LIST.md` | Test priority ordering |
| ?? | `.coverage` | Coverage data (ephemeral) |

---

## 2. Completed Phases (P3.1–P3.3)

### P3.1 — Testing Infrastructure ✅

**Files created:**
- `tests/__init__.py` — test package marker
- `tests/conftest.py` — 4 shared fixtures: `sample_df`, `sample_csv_path`, `mock_offsets`, `temp_data_dir`
- `pytest.ini` — `testpaths=tests`, `pythonpath=.`, `--strict-markers`, 3 custom markers (`slow`, `integration`, `smoke`)
- `.coveragerc` — excludes `.venv/`, `tests/`, `archive/`
- `.github/workflows/test.yml` — Windows + Ubuntu, Python 3.11/3.12, `pytest --cov`
- `tests/test_infrastructure.py` — 17 self-verification tests

### P3.2 — Config Module Tests ✅

**Coverage:** 3/3 config modules at 100%

| Test file | Tests | Target | Coverage |
|-----------|-------|--------|----------|
| `tests/test_actions.py` | 20 | `src/config/actions.py` | 100% |
| `tests/test_offsets.py` | 14 | `src/config/offsets.py` | 100% |
| `tests/test_logging.py` | 11 | `src/logging_config.py` | 100% |

### P3.3 — Core Logic Tests ✅

**8 pure functions extracted into `ai_engine.py`** (no new modules, no behavior change):

| Function | Location in ai_engine.py | Purpose |
|----------|--------------------------|---------|
| `calc_distance_2d` | ~line 55 | XZ-plane Euclidean distance |
| `calc_relative_angle` | ~line 68 | Relative angle monster→player |
| `select_top_k` | ~line 97 | Top-k from probability array |
| `filter_probs_by_phase` | ~line 120 | Zero probs invalid for current phase |
| `filter_probs_by_posture` | ~line 150 | Zero probs invalid for current posture |
| `renormalize_probs` | ~line 175 | Renormalize to sum=1 |
| `_POSTURE_STAND_EXCLUDE` | ~line 42 | 15 IDs (stand exclude set) |
| `_POSTURE_PRONE_EXCLUDE` | ~line 47 | 37 IDs (prone exclude set) |
| `evaluate_nova` | ~line 195 | Nova threshold FSM (HP→warning) |

**85 tests across 3 files, 100% pass rate.**

---

## 3. Current Coverage

```
Name                     Stmts   Miss   Cover
--------------------------------------------------------------------
ai_engine.py               248    153    43%
src/config/actions.py       12      0   100%
src/config/offsets.py       27      0   100%
src/logging_config.py        4      0   100%
data_cleaner.py             56     56     0%   ← P3.4 target
data_upgrade.py             38     38     0%   ← P3.4 target
train_lgbm.py               52     52     0%   ← P3.4 target
enrage.py                   58     58     0%   (diagnostic tool)
--------------------------------------------------------------------
TOTAL                      495    357    29%
```

**Coverage gap to 60%**: 153 more statements must be covered. The three P3.4 files have 146 statements total — covering them would reach ~58%.

---

## 4. Test File Inventory (7 files, 147 tests)

| # | File | Tests | Phase | Target |
|---|------|-------|-------|--------|
| 1 | `tests/test_infrastructure.py` | 17 | P3.1 | pytest/CI/fixture verification |
| 2 | `tests/test_actions.py` | 20 | P3.2 | Action DB integrity |
| 3 | `tests/test_offsets.py` | 14 | P3.2 | Memory offset config |
| 4 | `tests/test_logging.py` | 11 | P3.2 | Logging setup |
| 5 | `tests/test_math_logic.py` | 27 | P3.3A | Distance, angle, top-k |
| 6 | `tests/test_phase_filter.py` | 32 | P3.3B | Phase/posture filter, renormalization |
| 7 | `tests/test_nova.py` | 26 | P3.3C | Nova threshold FSM |

---

## 5. Outstanding Work — P3.4 Integration Testing

### Target Files

| File | Statements | What It Does | Test Approach |
|------|-----------|-------------|---------------|
| `data_cleaner.py` | 56 | Raw CSV → ML-ready transition pairs | Create synthetic CSVs, verify output columns/values |
| `data_upgrade.py` | 38 | Backfill phase/enrage in old CSVs | Create old-format CSV, verify upgraded output |
| `train_lgbm.py` | 52 | Train LightGBM classifier | Create tiny synthetic dataset, verify model trains |

### Then P3.5 — CI Finalization

- Final coverage verification (≥60% target)
- GitHub Actions complete workflow validation
- Git tag `v0.3.0`

---

## 6. Exact Starting Point for P3.4

```bash
# 1. Activate environment
source .venv/Scripts/activate

# 2. Run existing tests (should all pass)
python -m pytest tests/ -q

# 3. Read the target source files
#    data_cleaner.py  — ETL: raw CSV → ML_Ready_Dataset.csv
#    data_upgrade.py  — backfill phase/enrage columns in old CSVs
#    train_lgbm.py    — LightGBM training script

# 4. Create test files
#    tests/test_data_cleaner.py
#    tests/test_data_upgrade.py
#    tests/test_train_lgbm.py

# 5. Run with coverage
python -m pytest tests/ --cov -q
```

### Key Imports Available in Tests

```python
# From conftest.py (shared fixtures):
#   sample_df       — 5-row DataFrame with combat columns
#   sample_csv_path — sample_df written to temp CSV
#   mock_offsets    — deep copy of OFFSETS
#   temp_data_dir   — temp data/ directory

# From ai_engine.py (pure functions):
#   calc_distance_2d, calc_relative_angle, select_top_k
#   filter_probs_by_phase, filter_probs_by_posture, renormalize_probs
#   evaluate_nova

# From src/config/:
#   OFFSETS, ACTION_DB, ACTION_MAPPING, P1_ONLY_IDS, ...
```

---

## 7. Risks to Avoid

| # | Risk | Mitigation |
|---|------|-----------|
| 1 | **Architecture refactoring** — do NOT split modules, reorganize imports, or create new `src/*/` subpackages | P4 work only. Keep all changes within `tests/` and `ai_engine.py` (for extraction) |
| 2 | **Behavior changes** — data_cleaner/train_lgbm must produce identical output | Use `pytest-regressions` or exact-match assertions on known-good output |
| 3 | **Large file dependencies** — train_lgbm needs `.pkl` model and real CSV data to run | Create synthetic minimal datasets in tests; avoid loading real `models/fatalis_ai_model.pkl` (18 MB) |
| 4 | **Platform-specific deps** — Pymem and dearpygui fail on Linux | The three P3.4 target files DO NOT import pymem/dearpygui — they are pure data processing. Safe to test on any platform. |
| 5 | **test isolation** — data_cleaner writes to `data/ML_Ready_Dataset.csv` by default | Use `tmp_path` fixture to redirect output to temp directories |
| 6 | **70-column CSV assumption** — data_upgrade has hardcoded column expectations | Verify column count before processing; test with both old-format and already-upgraded files |

---

## 8. Quick Reference — Project Structure

```
D:\BlackDragon\
├── ai_engine.py              ← Main program (299→~350 lines after extractions)
├── data_cleaner.py           ← P3.4 target: CSV ETL
├── data_upgrade.py           ← P3.4 target: CSV backfill
├── train_lgbm.py             ← P3.4 target: model training
├── enrage.py                 ← Diagnostic tool (skip testing)
├── src/
│   ├── config/
│   │   ├── actions.py        ← 100% covered
│   │   └── offsets.py        ← 100% covered
│   └── logging_config.py     ← 100% covered
├── tests/                    ← 7 test files, 147 tests
├── data/                     ← CSV files (gitignored)
├── models/                   ← .pkl models (gitignored)
├── docs/                     ← Documentation
│   └── P3_HANDOFF.md         ← THIS FILE
├── memory-bank/              ← 6 files (systemPatterns, techContext, etc.)
├── pytest.ini                ← Pytest configuration
├── .coveragerc               ← Coverage configuration
└── .github/workflows/test.yml ← CI workflow
```

---

## 9. Commit Recommendations

When ready to commit P3 work, split into logical commits:

```
P3.1: Set up testing infrastructure (pytest, coverage, CI)
P3.2: Add config module tests (actions, offsets, logging)
P3.3A: Extract distance/angle/top-k + tests
P3.3B: Extract phase/posture filter/renormalization + tests
P3.3C: Extract Nova threshold logic + tests
P3.4: Add integration tests for data pipeline
P3.5: CI finalization + v0.3.0 tag
```
