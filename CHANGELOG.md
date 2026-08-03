# Changelog

All notable changes to the BlackDragon project.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [v0.5.0-integration] — 2026-08-03

### Added (P4.6 — Integration)

- `main.py` — application composition root wiring 5 P4 modules
  - `python main.py` is the new recommended entry point
  - `python ai_engine.py` retained as legacy fallback (zero modifications)
- `tests/test_main_integration.py` — 20 tests validating wiring (shared instances,
  lifecycle order, graceful pymem failure, structural constraints)
- Project cleanup: `enrage.py` + P2/P3 closure reports moved to `archive/`

### Metrics

| Metric | v0.3.0 | v0.5.0 |
|--------|--------|--------|
| Total tests | 182 | **385** |
| Pass rate | 100% | **100%** |
| Overall coverage | 60% | **72%** |
| P4 modules coverage | — | **100%** (5/5 modules) |

---

## [v0.4.0-architecture-refactor] — 2026-08-02/03

### Added (P4 — Architecture Refactor)

- **P4.1**: `src/core/state_tracker.py` — CombatStateTracker (50 tests, 100%)
- **P4.2**: `src/core/memory_reader.py` — MemoryReader (27 tests, 100%)
- **P4.3**: `src/model/predictor.py` — ActionPredictor (31 tests, 99%)
- **P4.4**: `src/data/recorder.py` — CombatRecorder (34 tests, 100%)
- **P4.5**: `src/ui/overlay.py` — OverlayUI (41 tests, 100%)
- God Class (`ai_engine.py`): zero modifications, dual-track maintained throughout

### Design

- Sequential extraction from `ai_engine.py` God Class into 5 single-responsibility modules
- Shared instances injected by reference (MemoryReader/StateTracker shared between
  Recorder and OverlayUI; Predictor UI-only)
- Thread model unchanged: main thread = DPG overlay, daemon thread = CSV recorder
- `ai_engine.py` retained as legacy reference + P3 test-compat entry

---

## [v0.3.0-test-safety-net] — 2026-08-02

### Added (P3 — Test Safety Net)

- **P3.1: Testing Infrastructure**
  - `pytest.ini` — pytest config (testpaths, pythonpath, markers: slow/integration/smoke)
  - `.coveragerc` — coverage config (branch=True, omit .venv/tests/archive)
  - `.github/workflows/test.yml` — CI workflow (Ubuntu + Windows, Python 3.11/3.12)
  - `tests/conftest.py` — 6 shared fixtures (sample_df, pipeline_workdir, etc.)
  - `tests/test_infrastructure.py` — 17 self-verification tests

- **P3.2: Config Module Tests (100% coverage)**
  - `tests/test_actions.py` — 20 tests (ACTION_DB, ACTION_MAPPING, phase/posture sets)
  - `tests/test_offsets.py` — 14 tests (GameOffsets dataclass, immutability)
  - `tests/test_logging.py` — 11 tests (setup_logging, FileHandler, log output)

- **P3.3: Core Logic Tests (8 pure functions extracted into ai_engine.py)**
  - `tests/test_math_logic.py` — 27 tests (calc_distance_2d, calc_relative_angle, select_top_k)
  - `tests/test_phase_filter.py` — 32 tests (filter_probs_by_phase, filter_probs_by_posture, renormalize_probs)
  - `tests/test_nova.py` — 26 tests (evaluate_nova threshold FSM)

- **P3.4: Integration Tests**
  - `tests/test_data_cleaner.py` — 19 tests (ETL: action mapping, posture FSM, filtering, corrupted CSV)
  - `tests/test_data_upgrade.py` — 11 tests (phase backfill, enrage window, column order, mixed files)
  - `tests/test_train_lgbm.py` — 5 smoke tests (mini dataset training, model/file output, rare class filter, error logging)

### Changed (P2 — Critical Fixes)

- Unified all constants into `src/config/actions.py` + `src/config/offsets.py` (single source of truth)
- Replaced all bare `except:` with structured logging via `src/logging_config.py`
- Centralized posture FSM transition sets
- Fixed remaining bare except in `train_lgbm.py` and `enrage.py`

### Metrics

| Metric | P3 Start | P3.3 | P3.4 (Final) |
|--------|----------|------|--------------|
| Total tests | 0 | 147 | **182** |
| Pass rate | — | 100% | **100%** |
| Overall coverage | ~8% | 29% | **60%** |
| ai_engine.py | 0% | 43% | 43% |
| config modules | 0% | 100% | 100% |
| data pipeline (3 modules) | 0% | 0% | **100%** |

---

## [v0.2.0-p0-fixes] — 2026-06-25

### Added

- `src/config/actions.py` — unified action database (127 entries, 54 mappings, phase/posture sets)
- `src/config/offsets.py` — centralized memory offsets (GameOffsets frozen dataclass, 20 fields)
- `src/logging_config.py` — unified logging (FileHandler → blackdragon.log, WARNING level)

### Changed

- `ai_engine.py` — imports from `src.config.*`, all `except: pass` → `except Exception: logger.warning`
- `data_cleaner.py` — imports from `src.config.actions`, unified ACTION_MAPPING
- `train_lgbm.py` — bare except → logger.error
- `enrage.py` — bare except → structured handling

### Fixed

- Duplicated ACTION_MAPPING across 3 files → single source of truth
- Scattered memory offsets across 3 files → single GameOffsets dataclass
- Silent error swallowing → all exceptions logged

---

## [v0.1.0-project-init] — 2026-06-22

### Added

- `.gitignore` — excludes `.venv/`, `__pycache__/`, `data/*.csv`, `models/*.pkl`, `models/*.png`, `.idea/`
- `requirements.txt` — pinned dependency versions (dearpygui, lightgbm, pymem, etc.)
- `README.md` — project overview, install guide, usage, directory structure
- `CHANGELOG.md` — this file
- `data/` directory — all combat recording CSVs moved here
- `models/` directory — trained model (`.pkl`) and feature importance plot (`.png`) moved here
- `archive/` directory — deprecated `mod.py` moved here
- `tests/` directory — `manual_checklist.md` for manual verification
- `archive/README.md` — explains archive purpose

### Changed

- Updated file paths in `ai_engine.py` (CSV output → `data/`, model load → `models/`)
- Updated file paths in `data_cleaner.py` (CSV glob + output → `data/`)
- Updated file paths in `train_lgbm.py` (dataset → `data/`, model + plot → `models/`)
- Updated file paths in `data_upgrade.py` (CSV glob → `data/`)
- Moved `出招表.txt` and `招式表2.0.txt` to `docs/`

### Verified

- `python data_cleaner.py` processes all 17 CSV files → 2447 valid samples
- `python train_lgbm.py` trains successfully (Top-3 accuracy: 56.17%)
- All imports resolve correctly
- All file paths point to correct new locations

---

## Prior Versions

No version history exists before v0.1.0. The project was previously an unversioned monolithic script.
