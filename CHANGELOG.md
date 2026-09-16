# Changelog

All notable changes to the BlackDragon project.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [v1.2.0] — 2026-09-16

### Added (AutoML model migration — FLAML Run B)

- **New AI model**: production model replaced by an XGBoost pipeline found via
  FLAML AutoML (Run B: 12 derived features, 190 trees). Same game interface,
  better predictions:
  | Metric (holdout, 488 rows / 46 classes) | v1.1.0 (LightGBM) | v1.2.0 (XGBoost) |
  |---|---|---|
  | Top-1 accuracy | 27.05% | **32.58%** (+5.53pp) |
  | Top-3 (raw) | 60.25% | **66.19%** (+5.94pp) |
  | **Top-3 (hard-filtered, in-game metric)** | **58.81%** | **65.37%** (+6.56pp) |
  | Model file size | 19.05 MB | **7.46 MB** |
  - Inference stays single-threaded (~2% CPU, p95 4.31ms); startup memory
    rises once by ~122 MB at model load (accepted user decision, steady-state
    within budget).
- **One-click training now uses the Run B winning config**: Dashboard
  "Start Training" retrains XGBoost on your merged recordings in a few
  seconds (previously LightGBM). `--train` keeps the legacy LightGBM path.
- **Training data merge + backup protection** (v1.2 data safety):
  - Your new recordings are merged with the shipped dataset — recording one
    fight no longer silently replaces the shipped 19-session dataset.
  - Two-generation backup chains (`.bak` / `.bak2`) for both dataset and
    model; retraining with unchanged data no longer consumes the backup.
  - Immutable factory model `models/factory_model.pkl` shipped for
    one-step rollback to the release model; raw combat CSVs shipped so the
    dataset can be rebuilt from scratch.
  - Training prints a data summary line (sessions/rows/classes vs the
    previous model) and prominent warnings on suspicious data shrinkage;
    every run is logged to `models/train_YYYYMMDD_HHMMSS.log` (last 10 kept).
- **`--selftest` diagnostic mode**: `BlackDragon.exe --selftest` /
  `BlackDragonOverlay.exe --selftest` exercise path resolution → model load
  → one prediction inside the real EXE and exit 0/1. Wired into the build
  as a hard gate.

### Fixed

- **Overlay could show a blank AI area in frozen packages** (model-load
  failures were silently swallowed, and relative paths broke when launched
  from a different working directory). Frozen path resolution is now
  exe-relative; load failures are logged with a full traceback and the
  overlay shows an orange "⚠ AI 模型未加载" hint instead of blank space.
- PyInstaller: Overlay EXE missing `sklearn.pipeline` (dynamic pickle
  reference) and xgboost runtime (`xgboost.dll` + `VERSION`) now bundled.

### Notes

- Release package: `Fatalis-Prediction-v1.2.0-windows.zip` (see
  `obsidian/docs/Release_v1.2.0_Package_Report.md` for contents + SHA256).
- Architecture decision record: `obsidian/docs/architecture/ADR-P6.1-automl-model-migration.md`.
- Tests: 581 → **766** passed.

---

## [v1.1.0] — 2026-08-05

### Added (P5.4 — Training Pipeline + Frozen EXE)

- One-click training pipeline: `launch.py --pipeline` / Dashboard button runs
  `data_cleaner` → `train_lgbm` automatically; unknown-action and
  small-dataset defenses (`stratify` fallback, NaN/non-numeric label warnings).
- PyInstaller frozen distribution: `BlackDragon.exe` (Dashboard) +
  `BlackDragonOverlay.exe` (Overlay) in one folder, model/dataset surfaced
  next to the EXEs. Auto-start overlay + auto-record defaults (ADR-P5.3).
- Release package `Fatalis-Prediction-v1.1.0-windows.zip`; docs: LICENSE,
  CONTRIBUTING, SECURITY, package report. Tests: 551 → 581.

---

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
