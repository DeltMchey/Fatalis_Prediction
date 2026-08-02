# Progress — BlackDragon

> Status source: `Refactoring_roadmap.md`

## Phase Overview

| Phase | Name | Status | Est. Days | Key Deliverables | Tag |
|-------|------|--------|-----------|------------------|-----|
| **P1** | 项目优化 (Project Standardization) | **Complete** | 2 | README, .gitignore, requirements.txt, directory structure | v0.1.0 |
| **P2** | P0 修复 (Critical Fixes) | **Complete** | 3 | Logging, unified actions.py, centralized offsets.py, posture FSM, bare except sweep | v0.2.0 |
| P3 | 测试体系 (Test Safety Net) | **Complete** | 3 | 182 tests (60% coverage), GitHub Actions CI | v0.3.0 |
| P4 | 架构重构 (Architecture Refactor) | **Active** | 5 | src/core/, src/data/, src/model/, src/ui/, main.py | v0.4.0 |
| P5 | 模型工程化 (Model Engineering) | Planned | 4 | Model versioning, incremental learning, docs, GitHub Release | v1.0.0 |

## P1 — Project Standardization (Active)

**Goal**: Establish project infrastructure without modifying any core logic.

### Tasks
- [ ] Create `README.md` — project intro, install guide, usage, directory structure
- [ ] Create `.gitignore` — exclude .venv/, __pycache__/, *.csv, *.pkl, .idea/
- [ ] Create `requirements.txt` — pin all dependencies
- [ ] Create `CHANGELOG.md` — version history
- [ ] Create `archive/` directory — move mod.py there
- [ ] Create `data/` directory — move CSVs there
- [ ] Create `models/` directory — move .pkl and .png there
- [ ] Create `docs/` directory — move reference docs there
- [ ] Update file paths in all Python scripts to reflect new directory structure
- [ ] Create `tests/manual_checklist.md` — manual verification checklist
- [ ] Verify `python data_cleaner.py && python train_lgbm.py` still works
- [ ] Verify `python ai_engine.py` starts (game not required for import check)

### Constraints
- No changes to core Python logic
- No changes to game mechanics logic
- No changes to model behavior
- No changes to feature engineering
- No architecture refactoring

## P2 — Critical Fixes (Complete ✅)

See `Tech_debt.md` items #1, #2, #3. Extended with audit findings P2.4–P2.6.

- [x] Replace all `except: pass` with structured logging (#3) → `ea143d5`
- [x] Unify ACTION_MAPPING into single source of truth (#2) → `43bfcff`
- [x] Centralize memory offsets into config (#1) → `cb4d218`
- [x] Unify posture FSM transition sets (P2.4) → uncommitted
- [x] Fix `train_lgbm.py` bare except (P2.5) → uncommitted
- [x] Fix `enrage.py` bare except (P2.6) → uncommitted

**Closure report**: `docs/P2_CLOSURE_REPORT.md`

## P3 — Test Safety Net (Complete ✅)

**Completion date**: 2026-08-02

- [x] P3.1: Testing Infrastructure — pytest.ini, .coveragerc, CI workflow, conftest.py, 17 infrastructure tests
- [x] P3.2: Config Module Tests — test_actions (20), test_offsets (14), test_logging (11) → config 100%
- [x] P3.3: Core Logic Tests — 8 pure functions extracted, test_math_logic (27), test_phase_filter (32), test_nova (26)
- [x] P3.4: Integration Tests — test_data_upgrade (11), test_data_cleaner (19), test_train_lgbm (5)
- [x] P3.5: CI Finalization — README badges, changelog, closure report
- [x] Coverage: 60% overall, ai_engine.py 43%, config modules 100%, data pipeline modules 100%
- [x] All 182 tests pass, CI compatible with Windows + Linux, Python 3.11/3.12

**Closure report**: `P3_CLOSURE_REPORT.md`

## P4 — Architecture Refactor (Active 🔵)

**P4 Step 1 complete (2026-08-02). Step 2 planned.**

Sequential extraction from `ai_engine.py`:
- [x] **P4.1: StateTracker** → `src/core/state_tracker.py` — CombatStateTracker class, 50 tests, 100% coverage
- [ ] **P4.2: MemoryReader** → `src/core/memory_reader.py`
- [ ] **P4.3: ActionPredictor** → `src/model/predictor.py`
- [ ] **P4.4: CombatRecorder** → `src/data/recorder.py`
- [ ] **P4.5: OverlayUI** → `src/ui/overlay.py`
- [ ] **P4.6: Main assembly** → `main.py`

## P5 — Model Engineering (Planned)

- [ ] Model version management with metadata
- [ ] Incremental training via LightGBM `init_model`
- [ ] Data schema versioning for CSVs
- [ ] Complete documentation (installation, usage, model training, memory RE guide)
- [ ] CI/CD: lint + test + release workflows
- [ ] GitHub Release v1.0.0

---

## Current State Summary

- **Phase**: P4 (Architecture Refactor) — active; P4 Step 1 complete, Step 2 planned
- **Project runs**: Yes — `python ai_engine.py` works with the game
- **Tests**: **232** (12 test files, 100% pass rate)
- **Coverage**: **64%** overall; 100% config + data pipeline + state_tracker; 43% ai_engine (UI/thread code)
- **CI/CD**: GitHub Actions (pytest + coverage on Windows/Ubuntu, Python 3.11/3.12)
- **Version control**: P1+P2+P3 committed (v0.1.0, v0.2.0, v0.3.0 tags); P4 Step 1 pending commit
- **Documentation**: User-facing: README.md, CHANGELOG.md. Analysis: P3_EXECUTION_PLAN.md, TEST_COVERAGE_MAP.md, P3_3_REVIEW.md, P3_3_TEST_RESULTS.md, P3_CLOSURE_REPORT.md. Memory Bank: 6 files (obsidian/memory_bank/)
