# Frozen Model Lifecycle Audit — BlackDragon v1.0

- **Date**: 2026-08-04
- **Auditor**: Frozen Model Lifecycle Audit
- **Scope**: Training → Save → Load → Predict (complete lifecycle)

---

## 1. Model Lifecycle Map

```
┌─────────────────────────────────────────────────────────────────┐
│ TRAINING (frozen mode)                                          │
│                                                                 │
│ Dashboard: "开始训练" button                                    │
│   → controller.start_training()                                 │
│     → subprocess.Popen([exe, "--train"], cwd=<exe_dir>)         │
│       → launch.py main() → "--train" flag                       │
│         → train_lgbm.train_fatalis_ai()                         │
│           → os.makedirs("models", exist_ok=True)                │
│           → joblib.dump(model, "models/fatalis_ai_model.pkl")   │
│                                                                 │
│ WRITES TO: <exe_dir>/models/fatalis_ai_model.pkl                │
│           ✅ (cwd = exe_dir, verified)                           │
└─────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│ INFERENCE (frozen mode)                                         │
│                                                                 │
│ OVERLAY PROCESS: BlackDragonOverlay.exe                         │
│   overlay.py:88 → ActionPredictor("models/fatalis_ai_model.pkl")│
│                                                                 │
│ DASHBOARD PROCESS: BlackDragon.exe                              │
│   controller.attach_game():102                                  │
│     → ActionPredictor(self._config.model_path)                  │
│     → model_path = "models/fatalis_ai_model.pkl"                │
│                                                                 │
│ READS FROM (BOTH): <exe_dir>/models/fatalis_ai_model.pkl        │
│                   ❌ GAP: bundled model at _internal/models/    │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. Path Analysis

### 2.1 Training Path (WRITE)

| Layer | Code | Resolved Path (frozen) |
|-------|------|----------------------|
| `controller.start_training()` | `subprocess.Popen(..., cwd=<exe_dir>)` | Sets CWD for training subprocess |
| `launch.py:45` | `train_lgbm.train_fatalis_ai()` | Runs in training subprocess |
| `train_lgbm.py:72` | `os.makedirs("models", exist_ok=True)` | ✅ Creates `<exe_dir>/models/` |
| `train_lgbm.py:73` | `joblib.dump(model, "models/fatalis_ai_model.pkl")` | ✅ Writes to `<exe_dir>/models/fatalis_ai_model.pkl` |
| `train_lgbm.py:87` | `plt.savefig("models/feature_importance.png")` | ✅ Writes to `<exe_dir>/models/feature_importance.png` |

**Training path: CORRECT** ✅ — verified by runtime test (model saved, accuracy output correct)

### 2.2 Inference Path (READ)

#### Overlay Process

| Layer | Code | Resolved Path |
|-------|------|---------------|
| `overlay.py:88` | `ActionPredictor("models/fatalis_ai_model.pkl")` | CWD-relative |
| `predictor.py:66` | `joblib.load(model_path)` | CWD-relative |

#### Dashboard Process

| Layer | Code | Resolved Path |
|-------|------|---------------|
| `controller.py:102` | `ActionPredictor(self._config.model_path)` | `model_path = "models/fatalis_ai_model.pkl"` |
| `predictor.py:66` | `joblib.load(model_path)` | CWD-relative |

#### Resolved Path (Frozen)

| Component | CWD | Resolved Model Path | Model Exists? |
|-----------|-----|---------------------|:---:|
| Overlay | `<exe_dir>` (inherited from Dashboard) | `<exe_dir>/models/fatalis_ai_model.pkl` | ❌ First run |
| Dashboard | `<exe_dir>` (set at launch) | `<exe_dir>/models/fatalis_ai_model.pkl` | ❌ First run |

### 2.3 Bundled Model Location

| Location | Source | Size |
|----------|--------|------|
| `dist/BlackDragon/_internal/models/fatalis_ai_model.pkl` | PyInstaller `COLLECT` from `datas` in spec | 17.6 MB |
| `dist/BlackDragon/models/` | — | **EMPTY on first run** |

**PyInstaller 6.x COLLECT puts `datas` at `_internal/<relative-path>`, not at `<exe_dir>/<relative-path>`.** The bundled model is only accessible via `_internal/models/`, which is NOT on the CWD-relative search path.

### 2.4 Post-Training Path (CLOSES THE GAP)

After user runs training once:

| Location | Source |
|----------|--------|
| `dist/BlackDragon/models/fatalis_ai_model.pkl` | Created by `train_lgbm.py` (os.makedirs + joblib.dump) |

After this, both Overlay and Dashboard can find the model at CWD-relative `models/fatalis_ai_model.pkl`. ✅

---

## 3. Gap Analysis

### 3.1 First-Run Gap (🔴 CRITICAL)

| State | Model at `<exe_dir>/models/` | Model at `_internal/models/` | Predictor Status |
|-------|:---:|:---:|------|
| After download (first run) | ❌ Empty | ✅ Bundled (17.6 MB) | `is_loaded = False` → No AI predictions |
| After training | ✅ Written by training | ✅ Bundled (unchanged) | `is_loaded = True` → AI predictions active |
| After retraining | ✅ Overwritten by training | ✅ Bundled (unchanged) | `is_loaded = True` → AI predictions active |

**Impact on first run**: Overlay window appears but shows only game state (phase/enrage/distance). AI Top-3 prediction section is absent. Dashboard shows "模型: 🔴 未加载".

### 3.2 Predictor Graceful Degradation

`ActionPredictor.__init__` handles model load failure gracefully:
```python
try:
    self._model = joblib.load(model_path)
except Exception:
    self._model = None
```

When model is not found:
- `predictor.is_loaded` = `False`
- `predictor.predict(...)` returns `[]` (empty list)
- OverlayUI skips AI display (`ai_text = None`)
- Dashboard status bar shows "🔴 未加载"

**No crash, no error** — just no predictions on first run. ✅ (graceful)

---

## 4. Root Cause

Same root cause as the `data/ML_Ready_Dataset.csv` issue (already fixed for data):

- PyInstaller 6.x `COLLECT` places `datas` in `_internal/<path>`, not `<exe_dir>/<path>`
- Application code uses CWD-relative paths (`"models/fatalis_ai_model.pkl"`)
- `src/model/predictor.py` is **P4 frozen** — cannot be modified for frozen-aware path resolution

---

## 5. Proposed Fix

### Surface bundled model to `<exe_dir>/models/` (same pattern as data/ML_Ready_Dataset.csv)

Add post-build step to `scripts/build_exe.ps1`:

```
$ModelSrc = Join-Path $ProjectRoot "dist/BlackDragon/_internal/models/fatalis_ai_model.pkl"
$ModelDst = Join-Path $ProjectRoot "dist/BlackDragon/models/fatalis_ai_model.pkl"
New-Item -ItemType Directory -Force -Path (Split-Path $ModelDst) | Out-Null
Copy-Item $ModelSrc $ModelDst -Force
```

**Files to modify**: `scripts/build_exe.ps1` only (+5 lines)

**Files NOT modified**:
- `src/model/predictor.py` (P4 frozen ✅)
- `src/core/`, `src/data/` (P4 frozen ✅)
- `overlay.py`, `launch.py`, `controller.py` (no changes needed)
- `build/BlackDragon.spec` (model is already in datas)

**After fix**:

```
dist/BlackDragon/
├── BlackDragon.exe
├── BlackDragonOverlay.exe
├── models/                          ← NEW: surfaced from _internal/
│   └── fatalis_ai_model.pkl          ← bundled model (17.6 MB)
│       (after training: overwritten by user's trained model)
├── data/
│   └── ML_Ready_Dataset.csv          ← surfaced (existing)
└── _internal/
    ├── models/
    │   └── fatalis_ai_model.pkl      ← PyInstaller bundled (unchanged)
    └── data/
        └── ML_Ready_Dataset.csv      ← PyInstaller bundled (unchanged)
```

### Verification after fix

| Scenario | Model Source | Predictions |
|----------|-------------|:---:|
| First run (no training) | Surfaced bundled model | ✅ AI predictions present |
| After training | User-trained model (overwrites bundled) | ✅ AI predictions with fresh data |
| After retraining | User-trained model (overwrites again) | ✅ AI predictions with latest data |

---

## 6. Complete Lifecycle (After Fix)

```
Download & Extract
    ↓
    ├── <exe_dir>/models/fatalis_ai_model.pkl  ← surfaced from _internal/
    │
    ↓
First Launch
    ├── Dashboard: ActionPredictor("models/fatalis_ai_model.pkl")
    │     → joblib.load → ✅ MODEL FOUND → is_loaded = True
    ├── Overlay: ActionPredictor("models/fatalis_ai_model.pkl")
    │     → joblib.load → ✅ MODEL FOUND → AI predictions show
    │
    ↓
Record Hunts (CombatRecorder → data/fatalis_combat_data_*.csv)
    ↓
Train Model (Dashboard "开始训练")
    ├── controller.start_training() → cwd=<exe_dir>
    ├── launch.py --train → train_fatalis_ai()
    ├── os.makedirs("models", exist_ok=True) → ✅
    ├── joblib.dump(model, "models/fatalis_ai_model.pkl")
    │     → WRITES TO <exe_dir>/models/ → overwrites bundled model
    │
    ↓
Restart (or automatic model hot-reload — future)
    ├── Dashboard/Overlay load NEW model
    │     → joblib.load("models/fatalis_ai_model.pkl")
    │     → ✅ USER-TRAINED MODEL → predictions with fresh data
    │
    ↓
CLOSED LOOP ✅
```

---

## 7. Files Referenced in Audit

| File | Role | Frozen-Path Aware? |
|------|------|:---:|
| `train_lgbm.py:72-73` | Write model | ✅ CWD = exe_dir (set by controller.start_training) |
| `overlay.py:88` | Load model (Overlay) | ❌ CWD-relative, no frozen awareness |
| `controller.py:102` | Load model (Dashboard) | ❌ CWD-relative, no frozen awareness |
| `src/model/predictor.py:66` | `joblib.load()` | ❌ CWD-relative, P4 frozen (cannot modify) |
| `src/app/config.py:33` | `model_path: str = "models/fatalis_ai_model.pkl"` | ❌ Static string |
| `build/BlackDragon.spec:21` | `datas`: bundle model | ✅ Bundled to `_internal/models/` |
| `scripts/build_exe.ps1` | Post-build surface | ⚠️ Surfaces data/ but NOT models/ |

## 8. Proposed Fix Summary

| File | Change | Lines |
|------|--------|:---:|
| `scripts/build_exe.ps1` | Add model surfacing step (same pattern as data/ML_Ready_Dataset.csv) | +5 |

**No source code changes.** P4 core untouched. Build-only fix.
