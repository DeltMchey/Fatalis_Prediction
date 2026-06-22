# Progress — BlackDragon

> Status source: `Refactoring_roadmap.md`

## Phase Overview

| Phase | Name | Status | Est. Days | Key Deliverables | Tag |
|-------|------|--------|-----------|------------------|-----|
| **P1** | 项目优化 (Project Standardization) | **Active** | 2 | README, .gitignore, requirements.txt, directory structure | v0.1.0 |
| P2 | P0 修复 (Critical Fixes) | Planned | 3 | Logging, unified actions.py, centralized offsets.py | v0.2.0 |
| P3 | 测试体系 (Test Safety Net) | Planned | 3 | Test suite (≥60% coverage), GitHub Actions CI | v0.3.0 |
| P4 | 架构重构 (Architecture Refactor) | Planned | 5 | src/core/, src/data/, src/model/, src/ui/, main.py | v0.4.0 |
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

## P2 — Critical Fixes (Planned)

See `Tech_debt.md` items #1, #2, #3.

- [ ] Replace all `except: pass` with structured logging (#3)
- [ ] Unify ACTION_MAPPING into single source of truth (#2)
- [ ] Centralize memory offsets into config (#1)

## P3 — Test Safety Net (Planned)

- [ ] Extract testable functions from core logic
- [ ] Write unit tests for: action mapping, posture FSM, phase filter, Nova logic
- [ ] Set up GitHub Actions CI with pytest
- [ ] Target: ≥60% overall coverage, ≥90% on core logic

## P4 — Architecture Refactor (Planned)

Sequential extraction from `ai_engine.py`:
1. StateTracker → `src/core/state_tracker.py`
2. MemoryReader → `src/core/memory_reader.py`
3. CombatRecorder → `src/data/recorder.py`
4. ActionPredictor → `src/model/predictor.py`
5. OverlayUI → `src/ui/overlay.py`
6. Main assembly → `main.py`

## P5 — Model Engineering (Planned)

- [ ] Model version management with metadata
- [ ] Incremental training via LightGBM `init_model`
- [ ] Data schema versioning for CSVs
- [ ] Complete documentation (installation, usage, model training, memory RE guide)
- [ ] CI/CD: lint + test + release workflows
- [ ] GitHub Release v1.0.0

---

## Current State Summary

- **Phase**: P1 (Project Standardization)
- **Project runs**: Yes — `python ai_engine.py` works with the game
- **Tests**: None
- **CI/CD**: None
- **Version control**: Not yet initialized (`git init` pending)
- **Documentation**: Analysis docs exist (Project_map.md, Tech_debt.md, Refactoring_roadmap.md, PROJECT_ANALYSIS.md); no user-facing docs
