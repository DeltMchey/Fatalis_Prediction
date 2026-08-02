# P3.3 — Core Logic Testability Review

> **Date**: 2026-06-30
> **Phase**: P3.3 — Test safety net preparation
> **File analyzed**: `ai_engine.py` (299 lines)

---

## 1. Executive Summary

| Logic Area | Classification | Effort | Key Risk |
|------------|---------------|--------|----------|
| Phase Detection | **A** — Immediate | Trivial | None |
| Posture FSM | **A** — Immediate | Trivial | None |
| Action Mapping | **A** — Immediate | Done (P3.2) | None |
| Nova Threshold Logic | **C** — Extract first | Low | shared_state coupling |
| Distance Calculations | **A** — Immediate | Trivial | Duplicated code |
| Angle Calculations | **A** — Immediate | Trivial | Duplicated code |
| Probability Filtering | **B** — Mock needed | Medium | Hardcoded magic sets |
| Top-K Selection | **A** — Immediate | Trivial | None |

**Overall**: 6 of 8 areas can be tested immediately (A). 1 needs mocking (B). 1 requires extraction (C).

---

## 2. Per-Area Analysis

### 2.1 Phase Detection

| Property | Detail |
|----------|--------|
| **Location** | `ai_engine.py:194` — inline inside `Ultimate_Radar_UI.update_logic()` |
| **Current code** | `shared_state['phase'] = 1 if hp_percent > 0.78 else (2 if hp_percent > 0.50 else 3)` |
| **Dependencies** | `hp_percent: float` (from memory read) |
| **Side effects** | Writes to `shared_state['phase']` (global dict) |
| **Pure logic** | `f(hp_percent) → phase` — a 3-bucket threshold classifier |
| **Duplicated elsewhere** | No |
| **Testability w/o refactoring** | ✅ **A** — Trivially extractable. Feed `[0.80, 0.60, 0.40, 0.10]` → expect `[1, 2, 3, 3]` |
| **Testability w/ mocking** | ✅ Not needed |
| **Extraction required** | No — one-liner that can be extracted as `determine_phase(hp_percent: float) -> int` |

**Test cases needed**: 5 (above/below each threshold, edge cases at 0.78, 0.50)

---

### 2.2 Posture FSM

| Property | Detail |
|----------|--------|
| **Location** | `ai_engine.py:222-228` — inline inside `Ultimate_Radar_UI.update_logic()` |
| **Current code** | Branch logic checking `action in POSTURE_STAND/PRONE/FLY` then setting `shared_state['posture']` |
| **Dependencies** | `action: int`, `last_action: int`, `POSTURE_STAND/PRONE/FLY: set[int]` (from config) |
| **Side effects** | Writes to `shared_state['posture']` (global dict). Gate: only on action change. |
| **Pure logic** | `f(action, last_action, prev_posture) → new_posture` |
| **Duplicated elsewhere** | Similar logic in `data_cleaner.py` (posture FSM during ETL) |
| **Testability w/o refactoring** | ✅ **A** — Input: (action_id, is_new_action), Output: posture int or None (no change) |
| **Testability w/ mocking** | ✅ Not needed |
| **Extraction required** | No — A pure function `transition_posture(action, prev_posture) -> int` |

**Test cases needed**: ~12 (trigger each posture set; verify no-change when same action; verify -1 is ignored; verify unknown actions don't change posture)

---

### 2.3 Action Mapping

| Property | Detail |
|----------|--------|
| **Location** | `ai_engine.py:190` — `ACTION_MAPPING.get(raw_action, raw_action)` |
| **Dependencies** | `ACTION_MAPPING: dict[int, int]` (from config), `raw_action: int` (from memory) |
| **Side effects** | None |
| **Pure logic** | `f(raw_action) → base_action` — dict lookup with identity fallback |
| **Duplicated elsewhere** | `data_cleaner.py` also uses ACTION_MAPPING for ETL |
| **Testability w/o refactoring** | ✅ **A** — Already covered by P3.2 (`test_actions.py` validates ACTION_MAPPING integrity) |
| **Testability w/ mocking** | ✅ Not needed |
| **Extraction required** | No — Already centralized in `src/config/actions.py` |

**Test cases needed**: 0 (covered by P3.2). Optional integration test: raw → mapped behavior.

---

### 2.4 Nova Threshold Logic

| Property | Detail |
|----------|--------|
| **Location** | `ai_engine.py:211-219` — inline inside `Ultimate_Radar_UI.update_logic()` |
| **Current code** | Two-phase: (1) initialization pass marking already-crossed thresholds, (2) continuous check for newly-crossed thresholds |
| **Dependencies** | `hp_percent: float`, `NOVA_THRESHOLDS: list[float]`, `shared_state['triggered_novas']`, `shared_state['hp_initialized']`, `shared_state['nova_warning']`, `action: int` (for reset) |
| **Side effects** | Mutates `shared_state['triggered_novas']` (set), `shared_state['nova_warning']` (bool), `shared_state['hp_initialized']` (bool). Nova warning reset on actions 197/167/179. |
| **Pure logic** | `f(current_hp, prev_triggered_set) → (new_triggered_set, should_warn: bool)` |
| **Duplicated elsewhere** | No |
| **Testability w/o refactoring** | ❌ **C** — Three shared_state fields mutated in one code block. Impossible to unit-test without running the full UI loop. |
| **Testability w/ mocking** | ⚠️ Partial — Could mock `shared_state` dict but still need to simulate state transitions across frames |
| **Extraction required** | ✅ Yes — Extract to `check_nova(hp_percent: float, triggered: set, initialized: bool, thresholds: list, reset_actions: set, current_action: int) → (triggered, warning, initialized)` |

**Test cases needed**: ~10 (initialization: hp=1.0, 0.8, 0.5; crossing: single pass through each threshold; reset on action 197/167/179; idempotency of re-crossing; boundary at each threshold value)

---

### 2.5 Distance Calculations

| Property | Detail |
|----------|--------|
| **Location** | `ai_engine.py:183` (update_logic) and `ai_engine.py:102` (data_logger_thread) — **duplicated** |
| **Current code** | `math.sqrt((p[0]-m[0])**2 + (p[2]-m[2])**2)` |
| **Dependencies** | `p_coords: list[float]`, `m_coords: list[float]` (from memory reads) |
| **Side effects** | None |
| **Pure logic** | `f(player_xyz, monster_xyz) → distance_2d` — Euclidean distance on XZ plane (ignoring Y) |
| **Duplicated elsewhere** | ✅ Yes — identical logic at lines 102 and 183 |
| **Testability w/o refactoring** | ✅ **A** — Pure math. `calc_distance((0,0,0), (3,4,0))` → 5.0 |
| **Testability w/ mocking** | ✅ Not needed |
| **Extraction required** | ✅ Recommended — deduplicate into a single function `calc_distance_2d(player_coords, monster_coords) -> float` |

**Test cases needed**: 4 (origin-to-origin = 0; same point; Pythagorean 3-4-5; Y coordinate ignored)

---

### 2.6 Angle Calculations

| Property | Detail |
|----------|--------|
| **Location** | `ai_engine.py:184-187` (update_logic) and `ai_engine.py:103-106` (data_logger_thread) — **duplicated** |
| **Current code** | 3-step: `monster_yaw` from quaternion → `target_yaw` from position delta → `rel_angle` normalized to [-180, 180] |
| **Dependencies** | `p_coords`, `m_coords`, `m_quat: list[float]` (from memory reads) |
| **Side effects** | None |
| **Pure logic** | `f(player_xyz, monster_xyz, monster_quat) → relative_angle_degrees` |
| **Duplicated elsewhere** | ✅ Yes — identical logic at lines 103-106 and 184-187 |
| **Testability w/o refactoring** | ✅ **A** — Pure math. `calc_relative_angle(...)` |
| **Testability w/ mocking** | ✅ Not needed |
| **Extraction required** | ✅ Recommended — deduplicate into `calc_relative_angle(player_coords, monster_coords, monster_quat) -> float` |

**Test cases needed**: ~6 (player directly ahead = 0°; player behind = ±180°; player to left; player to right; facing-north edge cases; quaternion identity)

---

### 2.7 Probability Filtering

| Property | Detail |
|----------|--------|
| **Location** | `ai_engine.py:251-266` — inline inside `Ultimate_Radar_UI.update_logic()` |
| **Current code** | Loop over `classes`: zero out probs based on phase filters (P1_ONLY/P2_PLUS/P3_ONLY) and posture filters (hardcoded magic sets), then renormalize |
| **Dependencies** | `probs: np.ndarray`, `classes: np.ndarray`, `shared_state['phase']`, `shared_state['posture']`, config sets + **hardcoded inline sets** (lines 256-263) |
| **Side effects** | Mutates `probs` array in-place |
| **Pure logic** | `f(prob_array, class_array, phase, posture) → filtered_normalized_probs` |
| **Duplicated elsewhere** | No |
| **Testability w/o refactoring** | ⚠️ **B** — Requires constructing numpy arrays and mocking shared_state. The hardcoded posture filter sets on lines 256-263 are magic numbers that should be constants. |
| **Testability w/ mocking** | ✅ **B** — Pass synthetic `probs`, `classes`, `phase`, `posture`. Verify P1-only IDs are zeroed in P2; standing-posture IDs are zeroed; renormalization preserves sum=1. |
| **Extraction required** | Recommended for cleanliness but not strictly necessary. The hardcoded inline sets (lines 256-263) should be moved to `src/config/actions.py` as `POSTURE_STAND_EXCLUDE` and `POSTURE_PRONE_EXCLUDE`. |

**Test cases needed**: ~8 (phase filter in P1/P2/P3; prune-only posture filter; prone-only posture filter; renormalization preserves total; all-zero → no division by zero; threshold filter; mixed filters; no-op when all valid)

---

### 2.8 Top-K Selection

| Property | Detail |
|----------|--------|
| **Location** | `ai_engine.py:270-274` — inline inside `Ultimate_Radar_UI.update_logic()` |
| **Current code** | `np.argsort(probs)[-3:][::-1]` — top 3 indices, filter by `probs[idx] > 0.03`, format string with `ACTION_DB` |
| **Dependencies** | `probs: np.ndarray`, `classes: np.ndarray`, `ACTION_DB: dict`, `threshold: 0.03` (hardcoded) |
| **Side effects** | None (only formats display string) |
| **Pure logic** | `f(probs, classes, k, threshold) → list[(class_id, prob)]` |
| **Duplicated elsewhere** | No |
| **Testability w/o refactoring** | ✅ **A** — Feed numpy arrays, verify correct indices selected and threshold applied |
| **Testability w/ mocking** | ✅ Not needed |
| **Extraction required** | No |

**Test cases needed**: 4 (k=3 with all above threshold; some below threshold; empty probs; tie-breaking)

---

## 3. Critical Findings

### F1: Code Duplication — Distance & Angle (lines 102-106 and 183-187)

The exact same distance and angle computation appears twice in `ai_engine.py`:
- `data_logger_thread()` (lines 102-106)
- `Ultimate_Radar_UI.update_logic()` (lines 183-187)

**Impact**: Must test the same logic twice; drift risk if one copy is modified.
**Recommendation**: Extract `calc_distance_2d()` and `calc_relative_angle()` — P3.3 should extract these as part of the test effort.

### F2: Hardcoded Magic Sets in Probability Filter (lines 256-263)

The posture filtering in `update_logic()` has two large hardcoded sets that are NOT in `src/config/actions.py`:

```python
# Standing filter (line 256-258) — 15 IDs
{129, 119, 98, 99, 68, 69, 70, 71, 72, 149, 150, 151, 152, 153, 93}

# Prone filter (lines 259-263) — 35 IDs
{138, 49, 50, 51, 52, 73, 107, 108, 136, 88, 91, 92, 94, 95, 96, 97,
 100, 101, 137, 154, 155, 156, 37, 38, 39, 40, 131, 132, 133, 140, 141,
 142, 135, 134, 81, 82, 83}
```

**Impact**: These are configuration data treated as inline code. Testing the filter requires extracting these sets from the method body.
**Recommendation**: Move to `src/config/actions.py` as `PROB_FILTER_STAND_EXCLUDE` and `PROB_FILTER_PRONE_EXCLUDE`. But this modifies production code — defer to P3.3 implementation or P4.

### F3: Nova Logic — Stateful Across Frames (lines 211-219)

The Nova warning system spans multiple frames:
1. First frame: seed `triggered_novas` with already-crossed thresholds, set `hp_initialized`
2. Subsequent frames: check for newly crossed thresholds
3. Reset: `nova_warning = False` on actions 197/167/179

**Impact**: This is the only logic area that genuinely requires extraction before testing.
**Recommendation**: Extract as `evaluate_nova(hp_pct, triggered, initialized, thresholds, action, reset_actions) → (new_triggered, warning, new_initialized)`.

---

## 4. Recommended Execution Order

Based on classification and dependencies:

```
Phase 1 (Immediate — A-class, no extraction):
  ├── 1a. Distance calculations      (4 tests)  ← also fixes F1 duplication
  ├── 1b. Angle calculations         (6 tests)  ← also fixes F1 duplication
  ├── 1c. Phase detection            (5 tests)
  ├── 1d. Top-K selection            (4 tests)
  └── 1e. Posture FSM               (12 tests)

Phase 2 (Mock-dependent — B-class):
  └── 2a. Probability filtering       (8 tests)  ← needs F2 addressed

Phase 3 (Extraction-required — C-class):
  └── 3a. Nova threshold logic       (10 tests)  ← needs F3 addressed
```

**Total estimated tests**: 49

---

## 5. What Must Be Extracted

For P3.3 (test-only phase), the following helper functions should be extracted from `ai_engine.py` to enable testing:

| Function | Location | Signature |
|----------|----------|-----------|
| `determine_phase` | Line 194 | `(hp_percent: float) -> int` |
| `transition_posture` | Lines 222-228 | `(action: int, prev_posture: int, is_new: bool, stand_set, prone_set, fly_set) -> int` |
| `calc_distance_2d` | Line 183/102 | `(p_coords: list, m_coords: list) -> float` |
| `calc_relative_angle` | Lines 184-187/103-106 | `(p_coords, m_coords, m_quat: list) -> float` |
| `filter_probs_by_phase` | Lines 253-255 | `(probs, classes, phase, p1_set, p2_set, p3_set) -> np.ndarray` |
| `filter_probs_by_posture` | Lines 256-263 | `(probs, classes, posture, stand_exclude, prone_exclude) -> np.ndarray` |
| `renormalize_probs` | Lines 265-266 | `(probs: np.ndarray) -> np.ndarray` |
| `select_top_k` | Lines 270-274 | `(probs, classes, k, threshold) -> list[tuple]` |
| `evaluate_nova` | Lines 211-219 | `(hp_pct, triggered, initialized, thresholds, action, reset_actions) -> tuple` |

**Constraint reminder** (from `activeContext.md`):
- Extraction is ALLOWED ("Extracting pure functions from ai_engine.py into testable helpers")
- Architecture refactoring is NOT allowed
- Module decomposition is NOT allowed
- All extracted functions must live within `ai_engine.py` or a test helper — no new modules

---

## 6. Coverage Projection

If all 49 tests are implemented and all extracted functions tested:

| Module | Current Coverage | Projected | Delta |
|--------|-----------------|-----------|-------|
| `src/config/actions.py` | 100% | 100% | — |
| `src/config/offsets.py` | 100% | 100% | — |
| `src/logging_config.py` | 100% | 100% | — |
| `ai_engine.py` | 0% | ~35% | +35% |
| **Overall** | 8% | **~25%** | +17% |

> Note: Full ≥60% overall target requires P3.4 (integration tests for data_cleaner, data_upgrade, train_lgbm) and P3.5 (CI finalization).
