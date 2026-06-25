# Active Context — BlackDragon

## Current Phase

**P3 — Testing and Validation Framework (测试体系)**

## Current Goal

Establish a test safety net: extract testable functions, build a pytest suite with ≥60% coverage, and set up GitHub Actions CI.

## What We Are Doing Now

Preparing the repository for automated testing:
- Identify all testable modules, functions, and code paths
- Classify modules by testability tier (unit, integration, manual)
- Propose a testing strategy and execution order
- Create test infrastructure (pytest, CI config)
- Write unit tests for core logic (action mapping, posture FSM, phase filter, Nova logic)

## Hard Constraints (Do Not Violate)

1. **No architecture refactoring** — God Class stays intact; module extraction is P4 work
2. **No module decomposition** — do not split ai_engine.py into submodules
3. **No behavior changes** — all existing logic must produce identical outputs
4. **No model changes** — training and inference pipelines untouched
5. **No gameplay changes** — action mappings, posture rules, phase thresholds remain unchanged
6. **Project must remain runnable** — `python ai_engine.py` must still function after every change

## What Is Allowed Right Now

- Extracting pure functions from ai_engine.py into testable helpers
- Creating test files (tests/) with pytest
- Creating CI configuration (.github/workflows/)
- Creating test fixtures and mock data
- Documenting test strategy and coverage targets
- Adding type hints where they aid testability

## What Is Explicitly Out of Scope

These are planned for future phases and must NOT be done now:
- Architecture refactoring (P4)
- God Class splitting (P4)
- Module redesign (P4)
- Model versioning (P5)
- Incremental learning (P5)
- GitHub Release (P5)

## Success Criteria for P3

- [ ] All core logic functions extracted and testable (no game memory dependency)
- [ ] Unit tests for: action mapping, posture FSM, phase detection, Nova logic, enrage detection
- [ ] Integration tests for: data_cleaner.py ETL pipeline, train_lgbm.py model training
- [ ] Test coverage ≥60% overall, ≥90% on core logic
- [ ] GitHub Actions CI runs pytest on every push
- [ ] All tests pass on clean checkout
- [ ] Git tag: `v0.3.0-test-safety-net`

## P2 Closure Summary

P2 completed 2026-06-25. All 6 tasks done (3 roadmap + 3 audit extensions):
- P2.1–P2.3: Committed (`ea143d5`, `43bfcff`, `cb4d218`)
- P2.4–P2.6: Working tree (awaiting commit)
- Zero bare `except:` in active code
- All constants centralized in `src/config/`
- Closure report: `docs/P2_CLOSURE_REPORT.md`

## Current Blockers

None. Phase P3 is ready to begin.

## Recent Decisions

- P2 closure audit completed 2026-06-25 — repository ready for P3
- P2.4–P2.6 included in P2 scope (posture FSM unification, residual bare except fixes)
- P3 readiness confirmed: logging infrastructure, centralized config, and cleaned error handling all in place

## Next Immediate Actions

1. Perform P3 readiness assessment (module classification, test strategy)
2. Create test directory and pytest configuration
3. Extract first testable function (ACTION_MAPPING validation)
4. Set up GitHub Actions CI workflow
