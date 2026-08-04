# Frozen Runtime Bug Fix — Review Report

- **Date**: 2026-08-04
- **Reviewer**: Reviewer
- **Scope**: 4 files (controller.py, launch.py, test_app_controller.py, test_launch.py)

---

## 1. Summary

| Check | Result |
|-------|:---:|
| Bug 1 (CSV path) fixed | ✅ |
| Bug 2 (Training subprocess) fixed | ✅ |
| 548 tests passed | ✅ |
| Dev mode unaffected | ✅ |
| P4 core untouched | ✅ |
| Dashboard API boundary clean | ✅ |

**No Must Fix items found. 1 Should Fix identified. Ready to rebuild.**

---

## 2. Bug 1: data_dir Design — ✅ CORRECT

### 2.1 Frozen Resolution

```python
@property
def data_dir(self) -> Path:
    path = self._config.data_dir           # "data" or user-configured
    if getattr(sys, "frozen", False) and not os.path.isabs(path):
        return Path(sys.executable).parent / path   # exe-relative
    return Path(path)                      # dev: config/resolved
```

| Scenario | Behavior | Correct? |
|----------|----------|:---:|
| Dev: `python launch.py` | `Path("data")` → CWD-relative | ✅ Same as before |
| Frozen: `BlackDragon.exe` | `Path(<exe_dir>)/"data"` | ✅ Exe-relative, not CWD |
| Custom config: `data_dir = "my_data"` (dev) | `Path("my_data")` | ✅ Config respected |
| Custom config: `data_dir = "D:/absolute/path"` (frozen) | `Path("D:/absolute/path")` | ✅ Absolute path not rewritten |
| Custom config: `data_dir = "my_data"` (frozen) | `Path(<exe_dir>)/"my_data"` | ✅ Config respected, exe-relative |

### 2.2 Recorder Initialization

```python
# attach_game line 108-109:
recorder = CombatRecorder(reader, state, buffer, lock,
                          data_dir=str(self.data_dir))
```

`self.data_dir` returns a `Path` → `str()` → string → `CombatRecorder(data_dir="<resolved>")`. Recorder creates directory at resolved path. Dashboard reads CSV from same path. **Consistent** ✅

### 2.3 AppConfig Integrity

`AppConfig.data_dir` field unchanged (`data_dir: str = "data"`). Controller property wraps it with frozen resolution. Config `load()`/`save()` unaffected. **No AppConfig API change** ✅

---

## 3. Bug 2: Training Frozen Mode — ✅ CORRECT

### 3.1 Subprocess Spawn

| Mode | Command | Behavior |
|------|---------|----------|
| Dev | `[python.exe, "train_lgbm.py"]` | ✅ Runs training in Python process |
| Frozen | `[BlackDragon.exe, "--train"]` | ✅ Same exe, training mode — no Dashboard restart |

### 3.2 --train Flow Verification

```python
# launch.py main() — line 44-49
if "--train" in sys.argv:
    sys.argv.remove("--train")              # Clean argv
    from train_lgbm import train_fatalis_ai # Import training function
    train_fatalis_ai()                      # Run training
    return                                  # Exit (no Dashboard)
```

| Risk | Mitigation |
|------|-----------|
| Would enter Dashboard? | ❌ No — `return` exits before Dashboard code (line 51+) |
| Would trigger DependencyChecker? | ❌ No — `return` before bootstrap check (line 52) |
| Would start overlay? | ❌ No — `return` before `controller.start_overlay()` (line 63) |
| Would exit cleanly? | ✅ Yes — `train_fatalis_ai()` runs to completion then returns |

### 3.3 Output Capture

`controller.start_training()` uses `subprocess.PIPE` for stdout → `_read_training_output` thread reads output → Training tab displays it. This mechanism **unchanged** between dev and frozen modes.

```
BlackDragon.exe --train
    ↓ print() → PIPE → controller._read_training_output → TrainingPanel refresh
```

**Correct** ✅

---

## 4. API Boundary — ✅ CLEAN

### 4.1 Dashboard → Controller

Dashboard only accesses **public** properties:

| Dashboard Code | Controller Property |
|----------------|---------------------|
| `self._controller.data_dir` | `data_dir` (public property) |
| `self._controller.start_overlay()` | `start_overlay()` (public method) |
| `self._controller.is_recording` | `is_recording` (public property) |

**Zero access** to `_config`, `_state`, `_recorder` or any private field. ✅

### 4.2 Dashboard → Config

Dashboard **never** directly imports or accesses `AppConfig`. All config access goes through controller. **Clean architecture** ✅

---

## 5. Findings

### 🔴 Must Fix — NONE

### 🟡 Should Fix — 1

| # | Issue | Location | Impact |
|---|-------|----------|--------|
| SF-1 | `start_training()` frozen spawn doesn't set `cwd` | `controller.py:291` | Training subprocess inherits parent CWD. If user launched exe from an unexpected directory, `train_fatalis_ai()` may fail to find `data/ML_Ready_Dataset.csv` or `models/` |

**Fix**: Add `cwd=os.path.dirname(sys.executable)` to the frozen `subprocess.Popen` call:

```python
# controller.py line 291:
self._training_proc = subprocess.Popen(
    cmd,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True, encoding="utf-8", errors="replace",
    cwd=os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else None,
)
```

This ensures the training subprocess runs with the exe's directory as CWD — matching where `data/` and `models/` are expected to be.

### 🟢 Nice to Have — 1

| # | Suggestion |
|---|------------|
| NTH-1 | `train_lgbm.train_fatalis_ai()` uses relative paths (`"data/ML_Ready_Dataset.csv"`, `"models/fatalis_ai_model.pkl"`). These depend on CWD. Consider making them frozen-aware via `Path(sys.executable).parent` in a future iteration |

---

## 6. Build Readiness

### ✅ READY TO REBUILD

| Condition | Status |
|-----------|:---:|
| Bug 1 fix correct | ✅ |
| Bug 2 fix correct | ✅ |
| 548 tests pass | ✅ |
| Dev mode preserved | ✅ |
| P4 core untouched | ✅ |
| Dashboard API boundary clean | ✅ |

### Rebuild Command

```bash
.\scripts\build_exe.ps1 -Clean
```

### Post-Rebuild Manual Checks

- [ ] `dist/BlackDragon/BlackDragon.exe` starts Dashboard
- [ ] Dashboard CSV list shows `data/` contents (not "(无法读取)")
- [ ] Click "开始训练" → Training tab shows output, **no new Dashboard window**
- [ ] `dist/BlackDragon/BlackDragon.exe --train` runs training directly (no Dashboard)
- [ ] `dist/BlackDragon/data/` directory auto-created on first recording
