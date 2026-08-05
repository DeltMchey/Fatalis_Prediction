# Training Pipeline Integration Analysis — BlackDragon v1.1

- **Date**: 2026-08-04
- **Revised**: 2026-08-05 — 移除 `data_upgrade.py` 依赖（数据格式已固定）
- **Analyst**: Architect / Researcher
- **Scope**: Dashboard "Training" button → automated data_cleaner + train_lgbm pipeline
- **Status**: Analysis — no code modified

---

## 1. Current Architecture

### 1.1 Module Inventory

| File | Function | Input | Output | Frozen Bundled? |
|------|----------|-------|--------|:---:|
| `data_cleaner.py` | `clean_combat_data()` | `data/fatalis_combat_data_*.csv` (raw recordings) | `data/ML_Ready_Dataset.csv` | ❌ Not in any spec |
| `data_upgrade.py` | `upgrade_old_csv_files()` | `data/fatalis_combat_data_*.csv` (old format) | `data/fatalis_combat_data_*.csv` (in-place upgrade) | ❌ Not in any spec |
| `train_lgbm.py` | `train_fatalis_ai()` | `data/ML_Ready_Dataset.csv` | `models/fatalis_ai_model.pkl` + `models/feature_importance.png` | ✅ Via `launch.py --train` import |

> **Revised note (2026-08-05)**: `data_upgrade.py` 保留为独立工具，但**不纳入 --pipeline 自动化流程**。用户数据格式已固定为 v2（含 `phase`/`is_enraged` 列），无需运行时升级。

### 1.2 Current Call Chain

```
User clicks "开始训练"
    ↓
TrainingPanel._on_start()
    ↓
controller.start_training()
    ↓ frozen: sys.frozen=True → cmd=[BlackDragon.exe, --train], cwd=<exe_dir>
    ↓ dev:    sys.frozen=False → cmd=[python.exe, train_lgbm.py]
    ↓
subprocess.Popen → stdout=PIPE
    ↓
_read_training_output() → queue → get_training_output() → TrainingPanel.refresh()
```

### 1.3 Data Flow (Manual — User Must Run Separately)

```
[Manual step 1] python data_cleaner.py    ← user runs manually
    ↓
data/ML_Ready_Dataset.csv                 ← output must exist before step 2
[Manual step 2] python train_lgbm.py      ← user runs manually OR clicks "开始训练"
    ↓
models/fatalis_ai_model.pkl
```

**Gap**: "开始训练" button skips `data_cleaner.py`. User must run it manually, then click the button.

---

## 2. Feasibility Analysis

### 2.1 Option A: Inline Pipeline in Controller（推荐）

> **Revised (2026-08-05)**: 原三步骤（upgrade → clean → train）简化为两步骤（clean → train）。
> `data_upgrade` 已从 pipeline 移除——数据格式已固定为 v2，不存在旧格式 CSV 需要运行时升级的场景。

```python
# controller.start_training() (modified)
def start_training(self):
    cmd = [sys.executable, "--pipeline"]  # new flag: clean + train
    self._training_proc = subprocess.Popen(cmd, ...)
```

Then in `launch.py`:
```python
if "--pipeline" in sys.argv:
    from data_cleaner import clean_combat_data
    from train_lgbm import train_fatalis_ai
    clean_combat_data()
    train_fatalis_ai()
    return
```

| Pro | Con |
|-----|-----|
| Minimal changes (1 new flag) | Two scripts run in 1 process; failure in one aborts all |
| Reuses existing PIPE output capture | Cannot cancel midway (kill subprocess kills everything) |
| Dev mode `python launch.py --pipeline` works | User sees combined output, cannot distinguish steps |
| No in-place data modification (upgrade step removed) | |
| Only 1 new hidden import (`data_cleaner`) | |

### 2.2 Option B: TrainingService (New Abstraction)

```
src/app/training_service.py   ← NEW: TrainingService class

Dashboard → Controller → TrainingService
                              ├── DataCleaner (import data_cleaner.clean_combat_data)
                              └── ModelTrainer (import train_lgbm.train_fatalis_ai)
```

| Pro | Con |
|-----|-----|
| Clean architecture — each step independent | Largest change: new module + refactored controller |
| Granular progress: "Step 1/2: Cleaning..." → "Step 2/2: Training..." | Both modules must be bundled in frozen exe |
| Testable — TrainingService can be unit-tested | TrainingPanel would need multi-line progress streaming |
| Cancellable — stop between steps | Over-engineering for 2-function pipeline |

### 2.3 Option C: Script-Based Subprocess Pipeline

```
controller.start_training()
    ↓
step 1: subprocess.Popen([exe, "--clean"], cwd=exe_dir)
    ↓ (waits for completion)
step 2: subprocess.Popen([exe, "--train"], cwd=exe_dir)
```

| Pro | Con |
|-----|-----|
| Maximum reuse — each script is already subprocess-capable | Requires `--clean` flag (1 new flag) |
| Each step can fail independently | TrainingPanel needs multi-phase output handling |
| Same output capture mechanism (PIPE + queue) | Subprocess overhead (2 launches instead of 1) |
| Minimal source changes (add flags to launch.py) | `data_cleaner.py` NOT in frozen exe → need hidden import + spec update |

---

## 3. Frozen Mode Analysis

### 3.1 Current State

| Flag | Implemented | Bundled in EXE | Status |
|------|:---:|:---:|:---:|
| `--train` | ✅ | ✅ (via `launch.py` import → PyInstaller AST analysis) | Works |
| `--pipeline` | ❌ | ❌ (needs `data_cleaner`) | Not implemented |

### 3.2 What Needs to Be Bundled

To implement `--pipeline` in frozen mode, the following must be added to `build/BlackDragon.spec`:

```python
hiddenimports=[
    # ── NEW: data pipeline module ──
    'data_cleaner',   # clean_combat_data()
]
```

> **Removed from original design**: `data_upgrade` 不再纳入 hiddenimports——`--pipeline` 不调用 upgrade。

**PyInstaller detection risk**: `data_cleaner` imports `pandas` + `glob` — these are already in the exe (via predictor.py). `data_cleaner` itself must be explicitly added because it's only imported dynamically inside `--pipeline` block (not statically visible to AST analysis).

**Est. size increase**: 0 MB (pandas already bundled; script is <3 KB).

### 3.3 Entry Point Design

```
launch.py main():

if "--pipeline" in sys.argv:         # clean + train (2 steps)
    from data_cleaner import clean_combat_data
    from train_lgbm import train_fatalis_ai
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    clean_combat_data()
    train_fatalis_ai()
    return

if "--train" in sys.argv:            # existing — unchanged
    from train_lgbm import train_fatalis_ai
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    train_fatalis_ai()
    return
```

This gives users flexibility: `BlackDragon.exe --pipeline` (full: clean + train), `--train` (training only).

---

## 4. Data Safety Analysis

### 4.1 File Overwrite Risk

| Action | Overwrites | Risk |
|--------|:---:|:---:|
| `clean_combat_data()` | Overwrites `data/ML_Ready_Dataset.csv` | 🟡 Medium — training input changes |
| `train_fatalis_ai()` | Overwrites `models/fatalis_ai_model.pkl` | 🟡 Medium — runtime model changes |

> **Revised**: `data_upgrade.py` 风险移除——不再作为 pipeline 步骤运行。用户如需升级旧数据，手动运行该脚本（独立工具模式）。

### 4.2 Safety Recommendations

| Recommendation | Implementation |
|----------------|----------------|
| **Backup ML_Ready_Dataset.csv before clean** | `data_cleaner.py` should rename old to `ML_Ready_Dataset.csv.bak` if it exists |
| **Backup model before training** | `train_lgbm.py` should rename old to `models/fatalis_ai_model.pkl.bak` |
| **Graceful failure on no data** | Already handled: `clean_combat_data()` prints warning and returns (no crash); `train_fatalis_ai()` prints error and returns |

### 4.3 Failure Rollback

| Failure Point | Rollback Strategy |
|---------------|-------------------|
| `clean_combat_data` fails | Old `ML_Ready_Dataset.csv.bak` exists → restore |
| `train_fatalis_ai` fails | Old `models/fatalis_ai_model.pkl.bak` exists → restore; Dashboard/Overlay continue using old model |

**Recommendation**: Implement backup-before-write in both scripts (each ~3 lines). Not blocking for v1.1 but should precede production release.

---

## 5. UI Design Analysis

### 5.1 Current TrainingPanel

```
┌─────────────────────────────┐
│  [开始训练]  [取消训练]       │
│  训练状态: 空闲               │
│  (训练输出...)                │
└─────────────────────────────┘
```

### 5.2 Proposed Pipeline State Machine

> **Revised**: 三状态简化为两状态（移除 UPGRADING）。

```
┌───────────┐     ┌───────────┐     ┌───────────┐
│  IDLE     │ ──→ │ CLEANING  │ ──→ │ TRAINING  │ ──→ IDLE
│           │     │           │     │           │
│ status:   │     │ status:   │     │ status:   │
│ 空闲      │     │ 数据清洗中 │     │ 训练中... │
└───────────┘     └───────────┘     └───────────┘
                       │                  │
                       ▼                  ▼
                   [取消]             [取消]
                   → IDLE             → IDLE
```

### 5.3 TrainingPanel Changes Required

| Element | Current | Proposed |
|---------|---------|----------|
| Status line | `训练状态: 空闲/进行中` | `训练状态: 空闲/进行中`（含义不变） |
| Output buffer | Single scroll | Same — PIPE captures all subprocess output |
| Cancel button | Terminates training subprocess | Same — terminates entire pipeline subprocess |
| Progress indicator | None | Optional: DPG progress bar（推迟至 v1.2） |

**Minimal change for MVP**: keep existing UI, add `--pipeline` flag to controller. The PIPE capture already handles all output — user sees "🔍 正在扫描..." → "✅ 数据提纯完成..." → "🚀 正在训练..." in the existing output text widget without any UI code changes.

---

## 6. Test Impact Assessment

### 6.1 New Test File: `tests/test_training_pipeline.py`

```python
# 6 tests total
TestTrainingPipeline:
    test_pipeline_flag_invokes_clean_and_train   # --pipeline calls clean + train (no upgrade)
    test_cleaner_no_csv_graceful                 # no raw CSVs → clean prints warning
    test_cleaner_writes_output                   # CSVs present → ML_Ready_Dataset.csv created
    test_frozen_pipeline_uses_correct_cmd        # frozen=True → [exe, "--pipeline"]
    test_pipeline_output_streamed                # stdout captured via PIPE
    test_cancel_terminates_pipeline              # cancel kills subprocess
```

### 6.2 Modified Test Files

| File | Changes | Tests Affected |
|------|---------|:---:|
| `test_app_controller.py` | `test_start_training_frozen_uses_train_flag` → rename to `test_start_training_frozen_uses_pipeline_flag` | 1 modified, +1 new |
| `test_launch.py` | `TestTrainMode` → add `test_main_handles_pipeline_flag` | +1 new |
| `test_dashboard.py` | `TestTrainingPanel` → no structural changes | 0 modified |

### 6.3 Expected Test Count

```
Baseline: 551 tests
Pipeline: +6 new tests (test_training_pipeline.py)
          +2 new/modified tests (controller + launch)
          = ~559 tests total
```

**No breakage expected** — existing tests mock subprocess.Popen; new flags added incrementally.

---

## 7. ADR Recommendation

**Updated**: ADR-P5.4 revised to reflect 2-step pipeline (clean → train) instead of original 3-step design.

| Field | Value |
|-------|-------|
| Title | Automated Training Pipeline Integration |
| Decision | Option A (--pipeline flag) for v1.1 MVP — **2-step**: clean + train |
| Context | User must manually run data_cleaner.py before training. Integration removes manual step. `data_upgrade` no longer needed (data format fixed). |
| Rationale | Minimal code change (1 new flag, 1 new hidden import), maximum reuse, same proven subprocess model as existing --train |
| Rejected alternatives | Option B (TrainingService — over-engineered for 2-function pipeline), Option C (separate subprocesses — unnecessary overhead) |
| Consequences | launch.py grows ~10 lines; spec gains 1 hidden import; no UI changes needed (PIPE capture handles output) |

---

## 8. Final Recommendation

### ✅ Recommend: Option A (Inline Pipeline via --pipeline flag — 2-step)

### Rationale

| Criterion | Score | Notes |
|-----------|:---:|------|
| Implementation effort | 🟢 Low | ~15 lines total (launch.py + controller + spec) |
| Frozen EXE compatibility | 🟢 Verified pattern | Same `--flag` model as `--train` and `--overlay` |
| Test impact | 🟢 Low | ~8 new tests, 0 breaking changes |
| UI impact | 🟢 None | Existing PIPE capture displays all output |
| Data safety | 🟢 Improved | No in-place CSV modification (upgrade step removed); only 2 backup targets |
| Architecture consistency | 🟢 High | Follows existing `--overlay`/`--train` flag pattern |

### Recommended for v1.1

**Not recommended for v1.0** — v1.0 release is feature-complete and stable. Pipeline integration is a UX enhancement, not critical path. Recommend targeting v1.1.

### Implementation Plan (v1.1 — Simplified)

| Step | Files | Effort |
|------|-------|:---:|
| 1. Add `--pipeline` flag to `launch.py` (clean → train) | `launch.py` | ~8 lines |
| 2. Add `data_cleaner` to `build/BlackDragon.spec` hiddenimports | `build/BlackDragon.spec` | +1 line |
| 3. Update `controller.start_training()` to use `--pipeline` (frozen) or `[python, launch.py, --pipeline]` (dev) | `src/app/controller.py` | ~6 lines |
| 4. Add backup-before-write to `data_cleaner.py`, `train_lgbm.py` | `data_cleaner.py`, `train_lgbm.py` | ~6 lines |
| 5. Add tests | `tests/test_training_pipeline.py` new + 2 existing | ~80 lines |
| 6. Rebuild EXE + run RC tests | `scripts/build_exe.ps1` | No change needed |
| **Total** | **7 files** | **~100 lines** |

### Risk Assessment

| Risk | Severity | Mitigation |
|------|:---:|------|
| ~~`data_upgrade` modifies raw CSVs in-place~~ | ~~🔴 High~~ | **风险移除** —— upgrade 不再作为 pipeline 步骤 |
| `clean_combat_data` overwrites existing ML_Ready_Dataset.csv | 🟡 Medium | Backup .bak |
| Pipeline failure mid-way leaves partial state | 🟡 Medium | Backup + rollback |
| Frozen EXE size increase | 🟢 None | pandas already bundled |
