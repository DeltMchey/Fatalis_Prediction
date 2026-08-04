# PyInstaller Packaging Research Report — BlackDragon P5.3

- **Date**: 2026-08-04
- **Researcher**: Researcher (read-only analysis)
- **Scope**: P5.3 dual-process architecture packaging feasibility
- **Status**: Research — no code modified

---

## 1. Executive Summary

BlackDragon 的 P5.3 双进程架构可以被打包为单个 exe，但有以下关键挑战：

| Challenge | Severity | Resolution Path |
|-----------|:---:|------|
| 双进程启动 (`subprocess.Popen` + `sys.executable`) | 🔴 Critical | Single exe + `--overlay` runtime flag |
| DependencyChecker in exe | 🔴 Critical | Skip bootstrap in frozen mode |
| DearPyGui GLFW DLL bundling | 🟡 Medium | Hidden imports + collect DLLs |
| LightGBM native library | 🟡 Medium | `--collect-binaries lightgbm` |
| Resource bundling (model, config) | 🟡 Medium | `--add-data` in .spec |
| 字体文件（系统字体，不打包） | 🟢 Low | Runtime fallback, Windows guaranteed |

**结论**: 可行，推荐 **single-exe + `--overlay` runtime flag** 方案。预估需要 ~800 行 PyInstaller `.spec` 文件 + controller.py 约 10 行修改。

---

## 2. Dual-Process Challenge (CRITICAL)

### 2.1 Current Behavior

```python
# src/app/controller.py:224
self._overlay_proc = subprocess.Popen(
    [sys.executable, self._config.overlay_script],  # overlay_script = "overlay.py"
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
)
```

**在开发环境中**:
- `sys.executable` = `C:/.../python.exe`
- `overlay.py` 作为独立脚本存在于文件系统
- `subprocess.Popen` 成功启动 Python 解释器运行 `overlay.py`

**在 PyInstaller exe 中**:
- `sys.executable` = `C:/.../BlackDragon.exe`（打包后的 exe）
- `overlay.py` **不存在于文件系统** — 它被编译打包进了 exe 内部
- `subprocess.Popen(["BlackDragon.exe", "overlay.py"])` → ❌ 失败（找不到 overlay.py）

### 2.2 Solution: Single-EXE + Runtime Mode Flag

**方案**: 将 `launch.py` 和 `overlay.py` 打包到 **同一个 exe** 中，通过命令行参数区分角色。

```python
# 启动行为
BlackDragon.exe              # Dashboard 进程（默认）
BlackDragon.exe --overlay    # Overlay 进程
```

**实现**: 在 exe 的入口点检测 `sys.argv`:

```python
# main entry point (pyinstaller entry)
import sys

def main():
    if "--overlay" in sys.argv:
        # Overlay process mode
        from overlay import main as overlay_main
        overlay_main()
    else:
        # Dashboard process mode (default)
        from launch import main as launch_main
        launch_main()
```

**controller.py 适配**:

```python
def start_overlay(self) -> bool:
    if self.is_overlay_running:
        return False
    try:
        self._overlay_proc = subprocess.Popen(
            [sys.executable, "--overlay"],  # ← 改为 flag-based
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        ...
```

> **注意**: `sys.executable` 在 PyInstaller 环境中正确指向 exe 自身。`[sys.executable, "--overlay"]` = `["BlackDragon.exe", "--overlay"]`。第二个进程会重新执行同一个 exe，通过 `--overlay` 进入 Overlay 分支。

### 2.3 Alternative: Two Separate EXEs

| 方案 | Pros | Cons | Verdict |
|------|------|------|:---:|
| **Single EXE + flag** | 只发布一个文件；自动去重（shared Python runtime） | 运行时两进程都解压到 temp dir；exe 体积大（~200MB） | ✅ Recommended |
| **Two EXEs** | 独立文件；可以只运行 overlay | 两个 exe 各含完整 Python runtime（~400MB total）；build 复杂度 ×2 | ❌ Not recommended |

### 2.4 Resource Sharing Between Processes

PyInstaller `--onefile` 模式下，每个进程启动时将 Python + dependencies 解压到临时目录。两个进程会各自解压到 **不同的** 临时目录 — 无共享冲突。

---

## 3. Component Compatibility Analysis

### 3.1 DearPyGui 2.3

| Aspect | Status | Notes |
|--------|:---:|------|
| GLFW DLL | ⚠️ Needs attention | `dearpygui` bundles `glfw3.dll` internally。PyInstaller 通常能检测到，但 --onefile 下 DLL 加载路径可能异常 |
| Hidden imports | ⚠️ | DPG 使用 `importlib` 动态加载后端 — 需 `--hidden-import dearpygui._dearpygui` |
| Windows-only | ✅ | 项目本身 Windows-only — 无跨平台顾虑 |

**Risk**: Medium. Community reports mixed success with DPG 2.x + PyInstaller. 建议 .spec 添加:

```python
a = Analysis(
    ...
    binaries=[('path/to/glfw3.dll', '.')],  # 如果有
    hiddenimports=['dearpygui._dearpygui'],
)
```

### 3.2 pymem 1.14.0

| Aspect | Status | Notes |
|--------|:---:|------|
| ctypes usage | ✅ | Pure `ctypes` — PyInstaller 原生支持 |
| Windows API | ✅ | `kernel32.dll`, `user32.dll` — 系统 DLL，不需要打包 |
| Hidden imports | ✅ | 无动态导入 — `import pymem` 足够 |

**Risk**: Low. pymem 使用标准 ctypes 调用 Windows API — PyInstaller 开箱即用。

### 3.3 LightGBM 4.6.0

| Aspect | Status | Notes |
|--------|:---:|------|
| Native library | 🔴 Critical | `lib_lightgbm.dll` — PyInstaller 默认不检测 |
| Custom hook | ⚠️ Needed | `--collect-binaries lightgbm` 或自定义 hook 文件 |
| OpenMP dependency | ⚠️ | Windows 需要 `vcomp140.dll` / `libomp140.x86_64.dll` |

**Solution**:

```python
# PyInstaller .spec
a = Analysis(
    ...
    binaries=[
        ('path/to/lib_lightgbm.dll', './lightgbm'),
    ],
    hiddenimports=['lightgbm', 'lightgbm.basic', 'lightgbm.callback', 'lightgbm.sklearn'],
)
```

**Alternative**: `--collect-all lightgbm` — 粗暴但有效，但会增加包体积（收集不需要的 dll/lib 等）。

**Risk**: High without proper hook. LightGBM 是 BlackDragon 的核心依赖 — exe 无法推理则完全不可用。

### 3.4 numpy 2.4.4 + scikit-learn 1.8.0

| Component | Status | Notes |
|-----------|:---:|------|
| numpy | ✅ | PyInstaller 有官方 hook (`pyinstaller/hooks/hook-numpy.py`) |
| scikit-learn | ✅ | 大部分通过官方 hook 覆盖；`sklearn.utils._typedefs` 等可能需要 `--hidden-import` |
| pandas 3.0.2 | ✅ | 官方 hook 覆盖 |

**Risk**: Low. 这些是成熟的科学计算栈，PyInstaller 社区支持完善。

```python
hiddenimports=[
    'sklearn.utils._typedefs',
    'sklearn.utils._vector_sentinel',
    'sklearn.neighbors._typedefs',
    'pandas._libs.tslibs',
]
```

### 3.5 matplotlib 3.10.9

| Aspect | Status | Notes |
|--------|:---:|------|
| Backend detection | ⚠️ | `MPLBACKEND=Agg` 避免 TkAgg |
| Bundle size | ⚠️ | matplotlib 是 BlackDragon 最大的依赖之一 |

**Note**: matplotlib 仅用于 `train_lgbm.py` 的特征重要性图生成 — 不是运行时必需的。可以考虑从主 exe 中排除，或使用 `--exclude-module matplotlib.backends` 减体积。

---

## 4. Resource Bundling

### 4.1 Required Resources

| Resource | Path | Status | Action |
|----------|------|:---:|------|
| AI Model | `models/fatalis_ai_model.pkl` (17.6 MB) | Must bundle | `--add-data "models/*.pkl;models/"` |
| Config | `blackdragon_config.json` | Generated at runtime | Defaults — no bundling needed |
| CJK Font | `C:/Windows/Fonts/msyh.ttc` | System font | NOT bundled — Windows always has it |
| Offsets | `src/config/offsets.py` | Hardcoded in Python | Already in exe — no action |
| Actions | `src/config/actions.py` | Hardcoded in Python | Already in exe — no action |

### 4.2 PyInstaller Add-Data

```python
a = Analysis(
    ...
    datas=[
        ('models/fatalis_ai_model.pkl', 'models'),     # 18 MB
        ('models/feature_importance.png', 'models'),     # 50 KB (optional)
    ],
)
```

### 4.3 Runtime Path Resolution

在 PyInstaller 打包环境中，`__file__` 不可靠。应使用 `sys._MEIPASS`:

```python
import sys, os

def get_resource_path(relative_path):
    """获取打包后的资源路径（兼容开发环境和 exe 环境）"""
    if getattr(sys, 'frozen', False):
        # PyInstaller 环境
        base = sys._MEIPASS
    else:
        # 开发环境
        base = os.path.abspath(".")
    return os.path.join(base, relative_path)

# 使用：
model_path = get_resource_path("models/fatalis_ai_model.pkl")
```

**影响文件**:
- `launch.py` line 38: `AppConfig.load()` — config 路径
- `overlay.py` line 61: `ActionPredictor("models/fatalis_ai_model.pkl")` — 需适配
- `src/app/controller.py` line 99: `ActionPredictor(self._config.model_path)` — 同上

> Note: `AppConfig.load()` 默认读取 `"blackdragon_config.json"`，该文件初始不存在，load() 返回默认值。exe 中亦然 — 用户首次运行后自动生成。无需特殊处理。

---

## 5. DependencyChecker in EXE

### 5.1 Current Behavior

```python
# src/bootstrap/checker.py
class DependencyChecker:
    @classmethod
    def ensure(cls, ...) -> bool:
        # 1. check_python_version()     — exe ships Python, always passes
        # 2. get_missing("requirements.txt") — requirements.txt NOT in exe → returns []
        # 3. install(packages)           — pip install in exe → WILL FAIL
```

### 5.2 Adaptations Required

| Method | In Dev | In EXE | Action |
|--------|:---:|:---:|------|
| `check_python_version()` | ✅ works | ✅ works (but pointless) | Skip |
| `get_missing("requirements.txt")` | ✅ reads file | ❌ file not found → returns `[]` | Graceful fallback already handled |
| `install(packages)` | ✅ pip install | ❌ pip not available | MUST skip |
| `ensure()` | ✅ full check | ⚠️ partial | Gate on `getattr(sys, 'frozen', False)` |

**Recommended fix**: Add early-return in `ensure()`:

```python
@classmethod
def ensure(cls, ...) -> bool:
    # In frozen (PyInstaller) environment, skip dependency check entirely
    if getattr(sys, 'frozen', False):
        print("BlackDragon (packaged) — dependency check skipped")
        return True
    # ... original logic for dev environment
```

This affects `launch.py` line 34: `if not DependencyChecker.ensure(): return`.

---

## 6. PyInstaller .spec File Design

### 6.1 Recommended Structure

```python
# BlackDragon.spec

block_cipher = None

# ---- Bundled resources ----
added_files = [
    ('models/fatalis_ai_model.pkl', 'models'),
    ('models/feature_importance.png', 'models'),
]

# ---- Entry point ----
# Custom runtime entry that checks --overlay flag
entry_script = 'pyinstaller_entry.py'

a = Analysis(
    [entry_script],
    pathex=[],
    binaries=[],
    datas=added_files,
    hiddenimports=[
        # DearPyGui
        'dearpygui._dearpygui',
        # LightGBM
        'lightgbm', 'lightgbm.basic', 'lightgbm.callback', 'lightgbm.sklearn',
        # scikit-learn edge cases
        'sklearn.utils._typedefs', 'sklearn.utils._vector_sentinel',
        # Pandas
        'pandas._libs.tslibs',
        # Project modules (ensure all P4/P5 packages collected)
        'src.core.state_tracker', 'src.core.memory_reader',
        'src.model.predictor', 'src.data.recorder',
        'src.ui.overlay', 'src.ui.fonts',
        'src.app.config', 'src.app.controller', 'src.app.game_service',
        'src.dashboard.main_window', 'src.dashboard.status_bar',
        'src.dashboard.log_view', 'src.dashboard.training_panel',
        'src.bootstrap.checker',
        'src.config.actions', 'src.config.offsets',
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        # Reduce size — exclude unused backends
        'matplotlib.backends.backend_tkagg',
        'matplotlib.backends.backend_qt5agg',
        'matplotlib.backends.backend_gtk3agg',
    ],
)

pyz = PYZ(a.pure, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    name='BlackDragon',
    icon='icon.ico',       # optional: custom icon
    console=False,         # hide console for release
    onefile=True,          # single exe
    target_architecture='x86_64',
)
```

### 6.2 Custom Entry Point (`pyinstaller_entry.py`)

```python
"""PyInstaller entry point — dual-process bootstrap.

Normal usage:  BlackDragon.exe           → Dashboard
Overlay usage: BlackDragon.exe --overlay → Overlay process
"""

import sys

# Ensure we flush stdout so subprocess output is visible
sys.stdout = open(sys.stdout.fileno(), mode='w', buffering=1)


def main():
    if "--overlay" in sys.argv:
        # Overlay process mode — independent DPG context
        from overlay import main as overlay_main
        sys.argv.remove("--overlay")
        overlay_main()
    else:
        # Dashboard process mode (default)
        from launch import main as launch_main
        launch_main()


if __name__ == "__main__":
    main()
```

### 6.3 controller.py Adaptation

```python
# src/app/controller.py — start_overlay method
def start_overlay(self) -> bool:
    if self.is_overlay_running:
        return False
    try:
        self._overlay_proc = subprocess.Popen(
            [sys.executable, "--overlay"],  # ← runtime flag, not script path
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        logger.error("启动覆盖层子进程失败", exc_info=True)
        self._overlay_proc = None
        return False
    return True
```

---

## 7. Estimated EXE Size

| Component | Est. Size |
|-----------|:---:|
| Python 3.12 runtime | ~30 MB |
| DearPyGui 2.3 + GLFW | ~15 MB |
| LightGBM + lib_lightgbm.dll | ~10 MB |
| numpy + scikit-learn + pandas | ~80 MB |
| matplotlib | ~30 MB |
| joblib | ~2 MB |
| pymem | ~1 MB |
| Application code (src/) | ~2 MB |
| AI model (fatalis_ai_model.pkl) | ~18 MB |
| **TOTAL (estimated)** | **~190 MB** |

> 注：`matplotlib` 占 ~30 MB 且仅用于训练（非运行时）。可考虑从 runtime exe 中排除，或通过 `--exclude-module` 缩减到 ~160 MB。

---

## 8. Known Issues & Mitigations

| # | Issue | Severity | Mitigation |
|---|-------|:---:|------|
| 1 | `subprocess.Popen` 启动 overlay 在 --onefile 下可能触发杀毒软件（同一 exe 双实例） | 🟡 Medium | 数字签名 + 文档说明 |
| 2 | DPG GLFW 在 --onefile 下需要解压到临时目录 — 首次启动慢 | 🟡 Medium | Recommended: `--onedir` for dev testing，`--onefile` for release |
| 3 | `lightgbm` 的 `lib_lightgbm.dll` 可能被其他 LightGBM 安装干扰 | 🟢 Low | Bundle to exe internal path → no system PATH conflict |
| 4 | `C:/Windows/Fonts/msyh.ttc` 在某些精简 Windows 版本可能缺失 | 🟢 Low | Fallback to DPG default font (already handled) |
| 5 | PyInstaller `--console` vs `--windowed` — DPG 需要 console 吗？ | 🟢 Low | `console=False` — DPG 创建自己的窗口，不依赖 console |
| 6 | Two processes each decompress ~190 MB to temp | 🟡 Medium | ~380 MB temp usage. Acceptable on modern machines |

---

## 9. Build Commands

```bash
# Install PyInstaller
pip install pyinstaller

# Build single exe
pyinstaller BlackDragon.spec

# Output:
# dist/BlackDragon.exe   (~190 MB, --onefile)

# Test
dist/BlackDragon.exe              # Dashboard
dist/BlackDragon.exe --overlay    # Overlay
```

---

## 10. Recommendations

### 10.1 For v1.0 Release

| Recommendation | Priority | Effort |
|----------------|:---:|:---:|
| Single EXE + `--overlay` flag | 🔴 Must | Medium (~200 lines) |
| `DependencyChecker` exe gate | 🔴 Must | Low (3 lines) |
| LightGBM DLL bundling | 🔴 Must | Low (~5 lines in .spec) |
| Model resource bundling | 🟡 Should | Low (~3 lines in .spec) |
| `controller.start_overlay` flag adaptation | 🔴 Must | Low (1 line change) |
| Custom icon | 🟢 Nice | Optional |

### 10.2 Post-Release

| Task | Notes |
|------|-------|
| GitHub Actions auto-build workflow (`.github/workflows/build.yml`) | PyInstaller build on `windows-latest` runner |
| Release artifact upload (`BlackDragon.exe` to GitHub Release) | GitHub Actions `upload-artifact` |
| Code signing (EV certificate) | For anti-virus trust |

### 10.3 Not Recommended for v1.0

- Matplotlib exclusion from runtime exe (complex hook needed — deferred)
- Two-EXE split (doubles build complexity and size — deferred)
- MSI installer (single exe sufficient for target audience)
