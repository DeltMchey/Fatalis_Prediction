# Training Pipeline Integration Analysis — BlackDragon v1.1

- **Date**: 2026-08-04
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

### 2.1 Option A: Inline Pipeline in Controller

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
    from data_upgrade import upgrade_old_csv_files
    from train_lgbm import train_fatalis_ai
    upgrade_old_csv_files()
    clean_combat_data()
    train_fatalis_ai()
    return
```

| Pro | Con |
|-----|-----|
| Minimal changes (1 new flag) | Monolithic — all 3 scripts run in 1 process; failure in one aborts all |
| Reuses existing PIPE output capture | No tool-specific progress — user sees 70 lines of combined output |
| Dev mode `python launch.py --pipeline` works | Cannot cancel midway (kill subprocess kills everything) |

### 2.2 Option B: TrainingService (New Abstraction)

```
src/app/training_service.py   ← NEW: TrainingService class

Dashboard → Controller → TrainingService
                              ├── DataCleaner (import data_cleaner.clean_combat_data)
                              ├── DataUpgrader (import data_upgrade.upgrade_old_csv_files)
                              └── ModelTrainer (import train_lgbm.train_fatalis_ai)
```

| Pro | Con |
|-----|-----|
| Clean architecture — each step independent | Largest change: new module + refactored controller |
| Granular progress: "Step 1/3: Upgrading CSVs..." → "Step 2/3: Cleaning..." → "Step 3/3: Training..." | Requires all 3 modules bundled in frozen exe (hidden import additions) |
| Testable — TrainingService can be unit-tested | TrainingPanel would need multi-line output streaming for pipeline progress |
| Cancellable — stop between steps | Data safety: if clean succeeds but train fails, clean output is already overwritten |

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
| Maximum reuse — each script is already a subprocess | Requires `--clean` + `--upgrade` flags (2 new flags) |
| Each step can fail independently | TrainingPanel needs to handle multi-phase output (clean output → then train output) |
| Same output capture mechanism (PIPE + queue) | Subprocess overhead (3 launches instead of 1) |
| Minimal source changes (add flags to launch.py) | `data_cleaner.py` and `data_upgrade.py` NOT in frozen exe → need hidden import + spec updates |

---

## 3. Frozen Mode Analysis

### 3.1 Current State

| Flag | Implemented | Bundled in EXE | Status |
|------|:---:|:---:|:---:|
| `--train` | ✅ | ✅ (via `launch.py` import → PyInstaller AST analysis) | Works |
| `--clean` | ❌ | ❌ (not imported, not in hiddenimports) | Not implemented |
| `--upgrade` | ❌ | ❌ (same) | Not implemented |
| `--pipeline` | ❌ | ❌ (needs all 3) | Not implemented |

### 3.2 What Needs to Be Bundled

To implement `--clean` / `--pipeline` in frozen mode, the following must be added to `build/BlackDragon.spec`:

```python
hiddenimports=[
    # ── NEW: data pipeline modules ──
    'data_cleaner',   # clean_combat_data()
    'data_upgrade',   # upgrade_old_csv_files()
    'train_lgbm',     # train_fatalis_ai() (already detected by PyInstaller via launch import)
]
```

**PyInstaller detection risk**: `data_cleaner` imports `pandas` + `glob` — these are already in the exe (via predictor.py). `data_cleaner` itself must be explicitly added because it's only imported dynamically inside `--clean` block (not statically visible to AST analysis).

**Est. size increase**: 0 MB (pandas already bundled; scripts are <3 KB each).

### 3.3 Best Entry Point Design

```
launch.py main():

if "--pipeline" in sys.argv:         # all-in-one: upgrade + clean + train
    from data_upgrade import upgrade_old_csv_files
    from data_cleaner import clean_combat_data
    from train_lgbm import train_fatalis_ai
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    upgrade_old_csv_files()
    clean_combat_data()
    train_fatalis_ai()
    return

if "--clean" in sys.argv:            # individual step
    from data_upgrade import upgrade_old_csv_files
    from data_cleaner import clean_combat_data
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    upgrade_old_csv_files()
    clean_combat_data()
    return

if "--train" in sys.argv:            # existing — unchanged
    from train_lgbm import train_fatalis_ai
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    train_fatalis_ai()
    return
```

This gives users flexibility: `BlackDragon.exe --pipeline` (full), `--clean` (data only), `--train` (training only).

---

## 4. Data Safety Analysis

### 4.1 File Overwrite Risk

| Action | Overwrites | Risk |
|--------|:---:|:---:|
| `upgrade_old_csv_files()` | Modifies raw CSVs **in-place** | 🔴 High — transforms original data |
| `clean_combat_data()` | Overwrites `data/ML_Ready_Dataset.csv` | 🟡 Medium — training input changes |
| `train_fatalis_ai()` | Overwrites `models/fatalis_ai_model.pkl` | 🟡 Medium — runtime model changes |

### 4.2 Safety Recommendations

| Recommendation | Implementation |
|----------------|----------------|
| **Backup raw CSVs before upgrade** | `data_upgrade.py` should save original as `data/backup_<date>/` before in-place modification |
| **Backup ML_Ready_Dataset.csv before clean** | `data_cleaner.py` should rename old to `ML_Ready_Dataset.csv.bak` if it exists |
| **Backup model before training** | `train_lgbm.py` should rename old to `models/fatalis_ai_model.pkl.bak` |
| **Graceful failure on no data** | Already handled: `clean_combat_data()` prints warning and returns (no crash); `train_fatalis_ai()` prints error and returns |

### 4.3 Failure Rollback

| Failure Point | Rollback Strategy |
|---------------|-------------------|
| `upgrade_old_csv_files` fails | Raw CSVs already backed up → restore from backup |
| `clean_combat_data` fails | Old `ML_Ready_Dataset.csv.bak` exists → restore |
| `train_fatalis_ai` fails | Old `models/fatalis_ai_model.pkl.bak` exists → restore; Dashboard/Overlay continue using old model |

**Recommendation**: Implement backup-before-write in all three scripts (each ~3 lines). Not blocking for v1.1 but should precede production release.

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

```
┌───────────┐     ┌───────────┐     ┌───────────┐     ┌───────────┐
│  IDLE     │ ──→ │ UPGRADING │ ──→ │ CLEANING  │ ──→ │ TRAINING  │ ──→ IDLE
│           │     │           │     │           │     │           │
│ status:   │     │ status:   │     │ status:   │     │ status:   │
│ 空闲      │     │ 数据升级中 │     │ 数据清洗中 │     │ 训练中... │
└───────────┘     └───────────┘     └───────────┘     └───────────┘
                       │                  │                 │
                       ▼                  ▼                 ▼
                   [取消]             [取消]            [取消]
                   → IDLE             → IDLE            → IDLE
```

### 5.3 TrainingPanel Changes Required

| Element | Current | Proposed |
|---------|---------|----------|
| Status line | `训练状态: 空闲/进行中` | `训练状态: [步骤 X/3] 数据清洗中...` |
| Output buffer | Single scroll | Same — PIPE captures all subprocess output |
| Cancel button | Terminates training subprocess | **New**: terminates current pipeline step only |
| Progress indicator | None | Optional: DPG progress bar widget |

**Minimal change for MVP**: keep existing UI, add `--pipeline` flag to controller. The PIPE capture already handles all output — user sees "🔍 正在扫描..." → "🔄 正在处理..." → "🚀 正在训练..." in the existing output text widget without any UI code changes.

---

## 6. Test Impact Assessment

### 6.1 New Test File: `tests/test_training_pipeline.py`

```python
# 6-8 tests total
TestTrainingPipeline:
    test_pipeline_flag_invokes_all_steps     # --pipeline calls upgrade+clean+train
    test_clean_flag_runs_cleaner             # --clean calls upgrade+clean
    test_cleaner_no_csv_graceful             # no raw CSVs → clean prints warning
    test_cleaner_writes_output               # CSVs present → ML_Ready_Dataset.csv created
    test_upgrade_modifies_old_format         # old CSV → upgraded in-place
    test_frozen_pipeline_uses_correct_cmd    # frozen=True → [exe, "--pipeline"]
    test_pipeline_output_streamed            # stdout captured via PIPE
```

### 6.2 Modified Test Files

| File | Changes | Tests Affected |
|------|---------|:---:|
| `test_app_controller.py` | `test_start_training_frozen_uses_train_flag` → rename? Add pipeline version? | 1 modified, +1 new |
| `test_launch.py` | `TestTrainMode` → add `test_main_handles_pipeline_flag`, `test_main_handles_clean_flag` | +2 new |
| `test_dashboard.py` | `TestTrainingPanel` → no structural changes (TrainingPanel calls controller.start_training unchanged) | 0 modified |

### 6.3 Expected Test Count

```
Baseline: 551 tests
Pipeline: +7 new tests (test_training_pipeline.py)
          +3 new tests (controller + launch)
          = ~561 tests total
```

**No breakage expected** — existing tests mock subprocess.Popen; new flags added incrementally.

---

## 7. ADR Recommendation

**Yes — new ADR recommended**: `ADR-P5.4-training-pipeline-integration.md`

| Field | Value |
|-------|-------|
| Title | Automated Training Pipeline Integration |
| Decision | Option A (--pipeline flag) for v1.1 MVP |
| Context | User must manually run data_cleaner.py before training. Integration removes manual step |
| Rationale | Minimal code change (1 new flag, 3 new hidden imports), maximum reuse, same proven subprocess model as existing --train |
| Rejected alternatives | Option B (TrainingService — over-engineered for 3-function pipeline), Option C (separate subprocesses — unnecessary overhead) |
| Consequences | launch.py grows 10 lines; spec gains 2 hidden imports; no UI changes needed (PIPE capture handles output) |

---

## 8. Final Recommendation

### ✅ Recommend: Option A (Inline Pipeline via --pipeline flag)

### Rationale

| Criterion | Score | Notes |
|-----------|:---:|------|
| Implementation effort | 🟢 Low | ~20 lines total (launch.py + controller + spec) |
| Frozen EXE compatibility | 🟢 Verified pattern | Same `--flag` model as `--train` and `--overlay` |
| Test impact | 🟢 Low | ~10 new tests, 0 breaking changes |
| UI impact | 🟢 None | Existing PIPE capture displays all output |
| Data safety | 🟡 Medium | Add backup-before-write (3 × ~3 lines) |
| Architecture consistency | 🟢 High | Follows existing `--overlay`/`--train` flag pattern |

### Recommended for v1.1

**Not recommended for v1.0** — v1.0 release is feature-complete and stable. Pipeline integration is a UX enhancement, not critical path. Recommend targeting v1.1.

### Implementation Plan (v1.1)

| Step | Files | Effort |
|------|-------|:---:|
| 1. Add `--clean`, `--pipeline` flags to `launch.py` | `launch.py` | ~10 lines |
| 2. Add `data_cleaner`, `data_upgrade` to `build/BlackDragon.spec` hiddenimports | `build/BlackDragon.spec` | +2 lines |
| 3. Update `controller.start_training()` to use `--pipeline` (frozen) or `[python, data_cleaner.py] && [python, train_lgbm.py]` (dev) | `src/app/controller.py` | ~8 lines |
| 4. Add backup-before-write to all 3 scripts | `data_cleaner.py`, `data_upgrade.py`, `train_lgbm.py` | ~9 lines |
| 5. Add tests | `tests/test_training_pipeline.py` new + 3 existing | ~100 lines |
| 6. Rebuild EXE + run RC tests | `scripts/build_exe.ps1` | No change needed |
| **Total** | **6 files** | **~130 lines** |

### Risk Assessment

| Risk | Severity | Mitigation |
|------|:---:|------|
| `data_upgrade` modifies raw CSVs in-place | 🔴 High | Add backup-before-write |
| `clean_combat_data` overwrites existing ML_Ready_Dataset.csv | 🟡 Medium | Backup .bak |
| Pipeline failure mid-way leaves partial state | 🟡 Medium | Backup + rollback |
| Frozen EXE size increase | 🟢 None | pandas already bundled |
