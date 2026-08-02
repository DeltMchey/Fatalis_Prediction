# Changelog — BlackDragon Memory Bank

> 记录每个阶段的完成事件，与根目录 `CHANGELOG.md`（版本发布记录）互补。

---

## 2026-08-02 — P4 Step 1 Complete

### Phase
P4 Architecture Refactoring (架构重构)

### Completed
- **P4.1: StateTracker Extraction**
  - Created `src/core/__init__.py`
  - Created `src/core/state_tracker.py` — `CombatStateTracker` class (156 lines)
  - Created `tests/test_state_tracker.py` — 50 tests, 100% pass
  - `state_tracker.py` achieves **100% branch coverage**
  - `ai_engine.py` left untouched — backward compat maintained

### Design Decisions
- StateTracker encapsulates all shared_state dict semantics (7 state fields + 8 methods)
- Zero external dependencies: only `math` + `src.config.actions`
- `shared_state['action_id']` confirmed dead code — dropped
- `action_buffer` + `lock` deferred to P4 Step 4 (Recorder thread coordination)
- Not yet wired into ai_engine.py — standalone module for now

### Review
- P4 Step 1 Review: **APPROVED** (0 blocking, 3 non-blocking recommendations)

### Metrics
- Total tests: 182 → **232** (+50)
- Overall coverage: 60% → **64%**

---

## 2026-08-02 — P3 Complete

### Phase
P3 Test Safety Net (测试体系)

### Completed
- P3.1–P3.5: 182 tests, 60% coverage, GitHub Actions CI
- Tag: `v0.3.0-test-safety-net`

---

## 2026-06-25 — P2 Complete

### Phase
P2 Critical Fixes (P0 修复)

### Completed
- Logging, unified constants, posture FSM, bare except sweep
- Tag: `v0.2.0-p0-fixes`

---

## 2026-06-22 — P1 Complete

### Phase
P1 Project Standardization (项目优化)

### Completed
- README, .gitignore, requirements.txt, directory structure
- Tag: `v0.1.0-project-init`
