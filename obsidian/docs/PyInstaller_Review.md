# PyInstaller Packaging Review — BlackDragon v1.0

- **Date**: 2026-08-04
- **Reviewer**: Reviewer
- **Scope**: build/BlackDragon.spec, build/BlackDragonOverlay.spec, scripts/build_exe.ps1, controller.py frozen logic

---

## 1. MUST FIX

### MF-1: `SPECPATH.parent.parent` → `SPECPATH.parent` (both specs)

| File | Line | Current | Correct |
|------|:---:|---------|---------|
| `build/BlackDragon.spec` | 16 | `Path(SPECPATH).parent.parent` | `Path(SPECPATH).parent` |
| `build/BlackDragonOverlay.spec` | 19 | `Path(SPECPATH).parent.parent` | `Path(SPECPATH).parent` |

**Root cause**: `SPECPATH` in PyInstaller = directory containing the spec file (not the file itself). Spec file at `build/BlackDragon.spec` → `SPECPATH` = `D:/.../BlackDragon/build`. `.parent` = project root ✅; `.parent.parent` = `D:/.../` ❌ (wrong parent).

**Impact**: Both specs compute `PROJECT_ROOT` as the wrong directory → `launch.py`/`overlay.py` not found → `Analysis()` fails with `FileNotFoundError`.

**Verification**:
```
SPECPATH                   = D:/.../BlackDragon/build
.parent (project root)     = D:/.../BlackDragon    ← CORRECT
.parent.parent             = D:/.../                ← WRONG
```

### MF-2: Missing `pymem` + `pymem.process` from Dashboard spec hidden imports

| File | Missing |
|------|---------|
| `build/BlackDragon.spec:40-49` | `pymem`, `pymem.process` |

**Root cause**: `src/app/game_service.py._try_attach()` imports pymem **dynamically** (inside the method body, not at module level). PyInstaller's AST analysis cannot see lazy imports. In contrast, `overlay.py` imports pymem at module level → PyInstaller detects it, so Overlay spec doesn't need it.

**Impact**: Dashboard exe crashes when GameService first detects `MonsterHunterWorld.exe` → `ModuleNotFoundError: No module named 'pymem'`.

**Fix**: Add to Dashboard spec `hiddenimports`:
```python
'pymem', 'pymem.process',
```

Note: `pymem.process` imports `pymem.ressources` internally — the PyInstaller import chain resolves this automatically.

---

## 2. SHOULD FIX

### SF-1: Two EXEs built into separate directories — no merge step

| Issue | Detail |
|-------|--------|
| Current | `dist/BlackDragon/BlackDragon.exe` + `dist/BlackDragonOverlay/BlackDragonOverlay.exe` — **separate dirs** |
| Expected | Both EXEs in **same directory** (so `os.path.dirname(sys.executable) + "/BlackDragonOverlay.exe"` resolves correctly) |

**Impact**: In frozen mode, `controller.start_overlay()` computes the overlay path relative to `sys.executable`'s directory. Dashboard exe looks for `dist/BlackDragon/BlackDragonOverlay.exe` but it's at `dist/BlackDragonOverlay/BlackDragonOverlay.exe` → **spawn fails silently**.

**Fix options**:

| Option | Complexity |
|--------|:---:|
| A: Add `post_build.py` merge script (copy BlackDragonOverlay.exe into BlackDragon/ dir) | Low |
| B: Change `COLLECT(name='BlackDragon')` in both specs to output to same directory | Medium (PyInstaller may conflict) |
| C: Document as manual step for release packaging | Zero (acceptable for v1.0) |

**Recommendation**: Option C for v1.0 + SF-1 documented in build guide.

### SF-2: `build_exe.ps1` uses global `pyinstaller` command

| Line | Issue |
|:---:|-------|
| 31 | `pyinstaller --version` — uses global PATH, may conflict if multiple Python envs |
| 69, 79 | `pyinstaller build/...` — same issue |

**Impact**: If global `pyinstaller` uses a different Python version than venv, spec file may load wrong packages. Low risk on typical dev machine but can cause cryptic errors.

**Fix**: Use `python -m PyInstaller` or `$env:VENV/Scripts/pyinstaller.exe` to ensure venv's PyInstaller is used.

### SF-3: Overlay spec excludes `src/app/controller` but controller is not used

| Spec | Exclude | Verdict |
|------|---------|:---:|
| Overlay | `src.app.controller` | ✅ Safe — overlay.py never imports controller |

This is correct and intentional — overlaying process doesn't need controller. No fix needed; included for completeness.

---

## 3. NICE TO HAVE

### NTH-1: Remove `matplotlib` from runtime specs

| Spec | matplotli b 是否运行时必需 |
|------|:---:|
| Dashboard | No — only TrainingPanel uses it via subprocess `train_lgbm.py` |
| Overlay | No — never uses it |

matplotlib (~30MB) 仅在训练脚本中使用。从两个运行时 spec 中排除 matplotlib → 可节省 ~30MB per exe。需在 `excludes` 中加入完整模块名（`'matplotlib'` 需要 hook 验证）。

### NTH-2: Add `joblib` to hidden imports for safety

Both specs rely on `joblib.load` (in `predictor.py`). PyInstaller detects this from module-level import in predictor, but adding `'joblib'` to hidden imports provides compile-time safety against hook changes.

### NTH-3: Add PyInstaller build to CI

`.github/workflows/build.yml` 可在 `windows-latest` runner 上执行 PyInstaller 构建 + 上传 artifact。对 v1.0 release 有用但非阻塞。

---

## 4. PASSED CHECKS

### 4.1 SPEC 入口点

| Spec | Entry | PyInstaller 可找到？ |
|------|-------|:---:|
| Dashboard | `launch.py` | ⚠️ 修复 MF-1 后 → ✅ |
| Overlay | `overlay.py` | ⚠️ 修复 MF-1 后 → ✅ |

### 4.2 Hidden imports — Dashboard (post MF-2 fix)

| 类别 | 模块 | 来源 | 版本 |
|------|------|------|:---:|
| DearPyGui | `dearpygui._dearpygui` | Dashboard.run() / StatusBar / LogView 等 | ✅ |
| LightGBM | `lightgbm*` (4) | ActionPredictor.predict() | ✅ |
| sklearn | `sklearn.utils._typedefs` / `_vector_sentinel` | predictor / state_tracker | ✅ |
| pandas | `pandas._libs.tslibs` | predictor | ✅ |
| pymem | `pymem`, `pymem.process` | game_service._try_attach() (lazy) | ⚠️ MF-2 |
| src/* (12 modules) | 全包覆盖 | Dashboard + controller | ✅ |
| matplotlib backends | `tkagg, qt5agg, gtk3agg` | 排除 → 体积优化 | ✅ |

### 4.3 Hidden imports — Overlay

| 类别 | 模块 | 覆盖 |
|------|------|:---:|
| DearPyGui | `dearpygui._dearpygui` | ✅ |
| LightGBM | `lightgbm*` (4) | ✅ |
| sklearn | `_typedefs`, `_vector_sentinel` | ✅ |
| pymem | (module-level import → auto-detected by PyInstaller) | ✅ |
| src/* (8 modules) | core + model + data + ui + config | ✅ |
| Excluded Dashboard | `src.dashboard`, `src.bootstrap`, `src.app.controller`, `src.app.game_service` | ✅ (saves ~20MB) |

### 4.4 Frozen Mode Logic (controller.py)

```python
if getattr(sys, "frozen", False):
    exe_dir = os.path.dirname(os.path.abspath(sys.executable))
    cmd = [os.path.join(exe_dir, "BlackDragonOverlay.exe")]
else:
    cmd = [sys.executable, self._config.overlay_script]
```

| Check | Result |
|-------|:---:|
| Dev mode (`sys.frozen = False`) → `[python.exe, overlay.py]` | ✅ Verified |
| Frozen mode (`sys.frozen = True`) → `[exe_dir/BlackDragonOverlay.exe]` | ✅ Verified |
| `os.path.abspath` handles Windows paths | ✅ |
| `subprocess.Popen(cmd, ...)` compatible with both modes | ✅ |
| Test compatibility (tests run in dev mode) | ✅ 541 passed |

### 4.5 launch.py Frozen Gate

```python
if not getattr(sys, "frozen", False):
    if not DependencyChecker.ensure():
        return
```

| Check | Result |
|-------|:---:|
| Dev mode → DependencyChecker runs normally | ✅ |
| Frozen mode → skip DependencyChecker | ✅ |
| `getattr(sys, "frozen", False)` safe (frozen attr doesn't exist in dev) | ✅ |
| Test compatibility (TestAutoStartBehavior patches DependencyChecker) | ✅ |

### 4.6 build_exe.ps1

| Check | Result |
|-------|:---:|
| PyInstaller version check | ✅ |
| pytest verification before build | ✅ |
| Clean step removes old build/dist | ✅ |
| Error handling (`$LASTEXITCODE`) | ✅ |
| Build both specs sequentially | ✅ |
| `Set-Location $ProjectRoot` from script location | ✅ |
| Summary output with exe paths | ✅ |

### 4.7 Constraints

| Constraint | Status |
|-----------|:---:|
| P4 core untouched | ✅ `src/core/`, `src/model/`, `src/data/` zero diff |
| `python launch.py` dev mode still works | ✅ |
| 541 tests passed | ✅ |
| `git mv` for moves | N/A (no source moves in this task) |

---

## 5. BUILD READINESS ASSESSMENT

### 🔴 NOT READY — 2 Must Fix items block first build

After MF-1 and MF-2 fixes:

| Item | Status | Notes |
|------|:---:|------|
| Spec file correctness | 🟡 | After MF-1 fix → ✅ |
| Hidden imports | 🟡 | After MF-2 fix → ✅ |
| Two EXEs built | ✅ | Both specs produce output |
| Dashboard → Overlay spawn | 🟡 | Need same-dir merge (SF-1) for actual runtime test |
| Real-machine frozen test | ⚠️ | Not yet executed — need PyInstaller build on Windows |
| CI integration | ❌ | Not implemented |

### Verdict

修复 MF-1 + MF-2 后，spec 文件逻辑上正确。但**未在真实 PyInstaller 环境中执行构建验证**——`SPECPATH` 行为、LightGBM DLL 收集、DPG GLFW 绑定均待实机确认。**建议在修复后执行 `.\scripts\build_exe.ps1 -Clean` 并验证两个 exe 可启动**。

### Recommended Fix Order

1. Fix MF-1 (SPECPATH.parent.parent → .parent)
2. Fix MF-2 (add pymem to Dashboard hiddenimports)
3. Fix SF-2 (use venv's pyinstaller in build script)
4. Execute: `pip install pyinstaller ; .\scripts\build_exe.ps1 -Clean`
5. Verify: `dist/BlackDragon/BlackDragon.exe` starts Dashboard
6. Verify: `dist/BlackDragonOverlay/BlackDragonOverlay.exe` starts Overlay
7. Manually test: copy BlackDragonOverlay.exe next to BlackDragon.exe, launch → overlay auto-spawns
