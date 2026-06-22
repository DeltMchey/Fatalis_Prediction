# Active Context — BlackDragon

## Current Phase

**P1 — Project Standardization (项目规范化)**

## Current Goal

Establish a standard project structure to support future refactoring, without modifying any core logic.

## What We Are Doing Now

Preparing the repository for GitHub publication through non-invasive improvements:
- Directory reorganization (data/, models/, docs/, archive/)
- Documentation (README.md, CHANGELOG.md)
- Configuration files (.gitignore, requirements.txt)
- Memory Bank initialization
- Path updates in existing scripts (no logic changes)

## Hard Constraints (Do Not Violate)

1. **No core Python logic changes** — do not modify game memory reading, state machine, AI inference, or model training logic
2. **No game mechanics changes** — action mappings, posture rules, phase thresholds remain untouched
3. **No model behavior changes** — training pipeline and inference pipeline must produce identical results
4. **No feature engineering changes** — the 6 features and their derivation remain unchanged
5. **No architecture refactoring** — God Class stays intact; module extraction is P4 work
6. **Project must remain runnable** — `python ai_engine.py` must still function after every change

## What Is Allowed Right Now

- Creating new directories and moving files
- Creating new documentation files
- Updating file paths in import statements and I/O calls
- Creating configuration files (.gitignore, requirements.txt)
- Initializing git repository
- Creating Memory Bank files

## What Is Explicitly Out of Scope

These are planned for future phases and must NOT be done now:
- Architecture refactoring (P4)
- God Class splitting (P4)
- Module redesign (P4)
- Test suite creation (P3)
- Logging system (P2)
- ACTION_MAPPING unification (P2)
- Offset centralization (P2)
- Model versioning (P5)
- Incremental learning (P5)

## Success Criteria for P1

- [ ] `README.md` exists with install steps, usage guide, project structure
- [ ] `.gitignore` properly excludes generated files
- [ ] `requirements.txt` enables reproducible environment
- [ ] Directory structure: data/, models/, docs/, archive/, tests/ created
- [ ] `git init` completed; `git status` shows only source code and docs
- [ ] `python data_cleaner.py && python train_lgbm.py` runs successfully
- [ ] `python ai_engine.py` starts (imports succeed, shows "未找到游戏进程" without game)
- [ ] Memory Bank initialized (6 files in memory-bank/)
- [ ] Git tag: `v0.1.0-project-init`

## Key Files to Modify (P1 Only)

| File | Change | Risk |
|------|--------|------|
| `ai_engine.py` L103, L156 | Path updates for data/ and models/ | Minimal |
| `data_cleaner.py` L8, L125 | Path updates for data/ | Minimal |
| `data_upgrade.py` L8 | Path update for data/ | Minimal |
| `train_lgbm.py` L14, L64, L78 | Path updates for data/ and models/ | Minimal |

## Current Blockers

None. Phase P1 is ready to execute.

## Recent Decisions

- Memory Bank spec received 2026-06-07 — initiating memory-bank/ creation
- Current phase declared as P1 per `docs/MEMORY_BANK_SPEC.md`
- All 5 analysis documents (PROJECT_ANALYSIS.md, Project_map.md, Tech_debt.md, Refactoring_roadmap.md, MEMORY_BANK_SPEC.md) reviewed and found consistent — no conflicts

## Next Immediate Actions

1. Create `README.md`
2. Create `.gitignore`
3. Create `requirements.txt`
4. Reorganize directories (data/, models/, docs/, archive/)
5. Update paths in Python scripts
6. Initialize git repository
7. Verify project still runs
