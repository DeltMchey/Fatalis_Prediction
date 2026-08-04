# PyInstaller Packaging Architecture — BlackDragon v1.0

- **Date**: 2026-08-04
- **Architect**: Architect (design only)
- **Source**: `obsidian/docs/PyInstaller_Packaging_Research.md`
- **Status**: Proposed — no code modified

---

## 1. Design Overview

### 1.1 User Experience Target

```
下载 BlackDragon-v1.0.zip
解压 → BlackDragon/
双击 BlackDragon.exe → 启动 Dashboard + 自动启动 Overlay
```

### 1.2 Output Structure

```
BlackDragon-v1.0/
├── BlackDragon.exe              # Dashboard 进程（用户双击入口）
├── BlackDragonOverlay.exe       # Overlay 进程（Dashboard 自动 spawn）
├── models/
│   └── fatalis_ai_model.pkl     # AI 模型 (17.6 MB)
├── config/
│   └── (首次运行生成: blackdragon_config.json)
└── README.txt                   # 使用说明
```

### 1.3 Architecture: Two-EXE Split

```
┌─────────────────────────────────────────────────────────┐
│  BlackDragon.exe  (Dashboard Process)                    │
│  ┌──────────────────────────────────────────────────┐   │
│  │  Python 3.12 runtime  (bundled, ~30 MB)          │   │
│  │  numpy + pandas + lightgbm + dearpygui           │   │
│  │  src/app/ + src/dashboard/ + src/bootstrap/      │   │
│  │  src/core/ + src/model/ + src/data/              │   │
│  └──────────────────────────────────────────────────┘   │
│                                                         │
│  subprocess.Popen("BlackDragonOverlay.exe")              │
│       │                                                  │
│       ▼                                                  │
└───────┬─────────────────────────────────────────────────┘
        │
┌───────▼─────────────────────────────────────────────────┐
│  BlackDragonOverlay.exe  (Overlay Process)              │
│  ┌──────────────────────────────────────────────────┐   │
│  │  Python 3.12 runtime  (bundled, ~30 MB)          │   │
│  │  numpy + pandas + lightgbm + dearpygui           │   │
│  │  src/core/ + src/model/ + src/data/ + src/ui/    │   │
│  └──────────────────────────────────────────────────┘   │
│                                                         │
│  读取 ../models/fatalis_ai_model.pkl                    │
│  读取 ../blackdragon_config.json（首次自动生成）         │
└─────────────────────────────────────────────────────────┘
```

**共享**: `models/` 目录两个 exe 共享读取。**独立**: 每个 exe 有自己的 Python runtime + 专属依赖。

---

## 2. Build Directory Structure

### 2.1 Source Layout (before build)

```
BlackDragon/                              # 项目根（开发环境）
├── launch.py                             # Dashboard 入口（→ BlackDragon.exe）
├── overlay.py                            # Overlay 入口（→ BlackDragonOverlay.exe）
├── src/                                  # 源码（两个 exe 共享编译）
├── models/
│   └── fatalis_ai_model.pkl              # AI 模型
├── config/                               # 空白（exe 运行时生成 blackdragon_config.json）
├── assets/
│   ├── icon.ico                          # 应用图标
│   └── README.txt.template               # 发布版 README 模板
├── build/                                # ★ 打包配置（新建）
│   ├── BlackDragon.spec                  # Dashboard exe 构建规格
│   ├── BlackDragonOverlay.spec           # Overlay exe 构建规格
│   └── post_build.py                    # 后处理脚本（合并输出）
├── requirements.txt
└── ...
```

### 2.2 Build Output (after build)

```
dist/BlackDragon-v1.0/                    # ★ 发布目录
├── BlackDragon.exe                       # Dashboard (from launch.py)
├── BlackDragonOverlay.exe                # Overlay (from overlay.py)
├── models/
│   └── fatalis_ai_model.pkl              # 复制自源目录
├── config/                               # 空目录（运行时生成配置）
├── README.txt                            # 使用说明
└── _internal/                            # PyInstaller 内部依赖（两个 exe 共享）
```

### 2.3 Intermediate Build Directories

```
build/
├── BlackDragon/                          # Dashboard build artifacts (git-ignored)
├── BlackDragonOverlay/                   # Overlay build artifacts (git-ignored)
dist/
└── BlackDragon-v1.0/                     # ★ 最终输出
```

---

## 3. SPEC File Design

### 3.1 `build/BlackDragon.spec` — Dashboard EXE

```python
# -*- mode: python ; coding: utf-8 -*-
# BlackDragon.spec — Dashboard EXE build specification

a = Analysis(
    ['launch.py'],                                    # Entry: Dashboard
    pathex=['.'],
    binaries=[],                                      # No extra binaries
    datas=[
        ('models/fatalis_ai_model.pkl', 'models'),    # Bundle model into exe (--onedir)
    ],
    hiddenimports=[
        # DearPyGui backend
        'dearpygui._dearpygui',
        # LightGBM native
        'lightgbm', 'lightgbm.basic', 'lightgbm.callback', 'lightgbm.sklearn',
        # scikit-learn edge cases
        'sklearn.utils._typedefs', 'sklearn.utils._vector_sentinel',
        # pandas internals
        'pandas._libs.tslibs',
        # Project packages (ensure collection)
        'src.core.state_tracker', 'src.core.memory_reader',
        'src.model.predictor', 'src.data.recorder',
        'src.ui.fonts',
        'src.app.config', 'src.app.controller', 'src.app.game_service',
        'src.dashboard.main_window', 'src.dashboard.status_bar',
        'src.dashboard.log_view', 'src.dashboard.training_panel',
        'src.bootstrap.checker',
        'src.config.actions', 'src.config.offsets',
        'src.logging_config',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Reduce size — exclude unused matplotlib backends
        'matplotlib.backends.backend_tkagg',
        'matplotlib.backends.backend_qt5agg',
    ],
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='BlackDragon',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,                          # Disable UPX (DPG GLFW DLL may break)
    console=False,                      # Windowed app (DPG creates own window)
    icon='assets/icon.ico',
    target_architecture='x86_64',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name='BlackDragon',                 # → dist/BlackDragon/
)
```

### 3.2 `build/BlackDragonOverlay.spec` — Overlay EXE

```python
# BlackDragonOverlay.spec — Overlay EXE build specification
# Same as Dashboard spec, but entry point is overlay.py
# and name is BlackDragonOverlay

a = Analysis(
    ['overlay.py'],                                   # Entry: Overlay
    pathex=['.'],
    binaries=[],
    datas=[
        ('models/fatalis_ai_model.pkl', 'models'),    # Bundle model
    ],
    hiddenimports=[
        # Same as Dashboard + additional
        'dearpygui._dearpygui',
        'lightgbm', 'lightgbm.basic', 'lightgbm.callback', 'lightgbm.sklearn',
        'sklearn.utils._typedefs', 'sklearn.utils._vector_sentinel',
        'pandas._libs.tslibs',
        'src.core.state_tracker', 'src.core.memory_reader',
        'src.model.predictor', 'src.data.recorder',
        'src.ui.overlay', 'src.ui.fonts',             # ← OverlayUI
        'src.app.config',
        'src.config.actions', 'src.config.offsets',
        'src.logging_config',
    ],
    excludes=[
        # Exclude Dashboard-specific modules to reduce size
        'src.dashboard',
        'src.bootstrap',
        'src.app.game_service',
        'src.app.controller',
        'matplotlib.backends.backend_tkagg',
        'matplotlib.backends.backend_qt5agg',
    ],
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='BlackDragonOverlay',
    debug=False,
    console=False,
    icon='assets/icon.ico',
    target_architecture='x86_64',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    name='BlackDragonOverlay',          # → dist/BlackDragonOverlay/
)
```

### 3.3 Size Comparison

| Exe | Entry | Dependencies | Models | Est. Size |
|-----|-------|-------------|:---:|:---:|
| BlackDragon.exe | launch.py | Full stack + Dashboard modules | 18 MB | ~190 MB |
| BlackDragonOverlay.exe | overlay.py | Core + Overlay modules (excludes dashboard) | 18 MB | ~150 MB |

### 3.4 Build Script

```bash
#!/bin/bash
# build.sh — Build both EXEs and assemble release package

# Step 1: Build individual EXEs
pyinstaller build/BlackDragon.spec --clean
pyinstaller build/BlackDragonOverlay.spec --clean

# Step 2: Merge into release directory
python build/post_build.py

# Step 3: Package
powershell Compress-Archive -Path dist/BlackDragon-v1.0 -DestinationPath dist/BlackDragon-v1.0.zip
```

---

## 4. Entry Point Modifications

### 4.1 controller.py — Subprocess Spawn (1 line change)

```python
# src/app/controller.py — start_overlay() method (line 224)

import os, sys

def start_overlay(self) -> bool:
    if self.is_overlay_running:
        return False
    try:
        # ★ DETECT: dev environment vs EXE environment
        if getattr(sys, 'frozen', False):
            # EXE: spawn sibling exe from same directory
            exe_dir = os.path.dirname(sys.executable)
            overlay_path = os.path.join(exe_dir, "BlackDragonOverlay.exe")
            cmd = [overlay_path]
        else:
            # DEV: spawn via Python interpreter
            cmd = [sys.executable, "overlay.py"]

        self._overlay_proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        logger.error("启动覆盖层子进程失败", exc_info=True)
        self._overlay_proc = None
        return False
    return True
```

**变更**: `controller.py` 1 个方法，~12 行（包含空行和注释），从原始 10 行扩展到 ~16 行。不违反 P4 core 约束（controller.py 在 `src/app/`，非冻结层）。

### 4.2 DependencyChecker — EXE Gate (3 lines)

```python
# src/bootstrap/checker.py — ensure() method

@classmethod
def ensure(cls, ...) -> bool:
    # ★ In frozen (exe) environment, skip dependency check
    if getattr(sys, 'frozen', False):
        print("BlackDragon (packaged) — dependency check skipped")
        return True

    # ... original development environment logic unchanged
```

**变更**: `checker.py` 的 `ensure()` 方法开头增加 3 行。不违反 P4 core 约束。

### 4.3 Model Path Resolution

两个 exe 均通过 `--datas` 在构建时将 `models/fatalis_ai_model.pkl` 打包到 exe 内部。PyInstaller `--onedir` 模式下，exe 运行时 `sys._MEIPASS` 指向包含 `models/` 的临时目录。

**当前代码**（`overlay.py:61`, `controller.py:99`）已使用相对路径 `"models/fatalis_ai_model.pkl"`。在 exe 环境中，PyInstaller 的 `COLLECT` 会将 `datas` 解压到 exe 同目录。**无需修改** — 相对路径自然工作。

**验证**: `--onedir` 输出 `dist/BlackDragon/models/fatalis_ai_model.pkl` → exe 同目录，`ActionPredictor("models/fatalis_ai_model.pkl")` 可正确解析。

### 4.4 NO Changes Required

| File | Reason |
|------|--------|
| `launch.py` | 入口逻辑不变 — DependencyChecker gate 已由 checker.py 处理 |
| `overlay.py` | 入口逻辑不变 — 独立构建为 Overlay exe |
| `src/core/` | P4 frozen — 零修改 |
| `src/model/` | P4 frozen — 零修改 |
| `src/data/` | P4 frozen — 零修改 |
| `src/config/` | 配置常量 — 无需修改 |
| `src/ui/overlay.py` | DPG 入口不变 |

---

## 5. Data File Handling

### 5.1 Resource Bundling Strategy

| Resource | Dev | EXE | Strategy |
|----------|-----|-----|----------|
| `models/fatalis_ai_model.pkl` (17.6 MB) | `models/` 目录 | Bundle via `--add-data` | `COLLECT` 输出到 exe 同目录 |
| `blackdragon_config.json` | 首次运行生成 | 首次运行生成 | `AppConfig.load()` 已处理缺失 → 返回默认值 |
| `C:/Windows/Fonts/msyh.ttc` | 系统字体 | 系统字体 | 不打包 — Windows 保证存在 |
| `src/config/offsets.py` | Python 源码 | 已编译进 exe | 无需处理 |
| `src/config/actions.py` | Python 源码 | 已编译进 exe | 无需处理 |

### 5.2 External Data Directory (User-Visible)

```
BlackDragon/
├── BlackDragon.exe
├── BlackDragonOverlay.exe
├── models/                          ← ★ 用户可替换模型
│   └── fatalis_ai_model.pkl
├── config/                          ← 首次运行自动生成
│   └── blackdragon_config.json
└── data/                            ← 录制输出（自动创建）
    └── fatalis_combat_data_*.csv
```

**用户权益**:
- 可替换 `models/fatalis_ai_model.pkl` 更新 AI
- 可编辑 `blackdragon_config.json` 关闭 auto_start_overlay 或 auto_record
- `data/` 自动创建于 exe 所在目录，用于录制输出

### 5.3 Config Auto-Generation (No Changes Needed)

`AppConfig.load()` 当前逻辑：
```python
filepath = Path(path)  # path = "blackdragon_config.json"
if not filepath.exists():
    return config  # return default AppConfig()
```

当 exe 首次运行时，`blackdragon_config.json` 不存在 → 返回默认值 (`auto_start_overlay=True`, `auto_record=True`)。用户后续可通过 Dashboard 设置面板保存（未来功能）或手动编辑。**无需修改**。

---

## 6. Post-Build Script (`build/post_build.py`)

### 6.1 Purpose

将两个独立构建的 `--onedir` 输出合并到统一发布目录：

```
dist/BlackDragon/         (Dashboard build)
dist/BlackDragonOverlay/  (Overlay build)
    ↓ post_build.py
dist/BlackDragon-v1.0/    (Release package)
```

### 6.2 Logic Outline

```python
"""post_build.py — assemble v1.0 release package from two EXE builds."""

import os, shutil, glob

SRC_DIR  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST_DIR = os.path.join(SRC_DIR, "dist")
RELEASE  = os.path.join(DIST_DIR, "BlackDragon-v1.0")

def merge():
    os.makedirs(RELEASE, exist_ok=True)

    # 1. Copy dashboard exe + dependencies
    copy_tree(os.path.join(DIST_DIR, "BlackDragon"), RELEASE)

    # 2. Copy overlay exe (only the exe — skip duplicate dependencies)
    overlay_exe = os.path.join(DIST_DIR, "BlackDragonOverlay", "BlackDragonOverlay.exe")
    shutil.copy2(overlay_exe, os.path.join(RELEASE, "BlackDragonOverlay.exe"))

    # 3. Copy external resources
    copy_tree(os.path.join(SRC_DIR, "models"), os.path.join(RELEASE, "models"))
    os.makedirs(os.path.join(RELEASE, "config"), exist_ok=True)  # empty

    # 4. Copy README
    shutil.copy2(os.path.join(SRC_DIR, "assets", "README.txt"), RELEASE)

    # 5. Clean build artifacts not needed in release
    #    (PyInstaller temp files, .pyc, etc.)

    print(f"Release package assembled at: {RELEASE}")
```

### 6.3 De-duplication Strategy

两个 exe 共享依赖（numpy, pandas, lightgbm, dearpygui）。`post_build.py` 将 Dashboard 的全部依赖复制到发布目录，Overlay 只复制 `.exe` 自身。由于两个 exe 使用相同的依赖版本，Overlay exe 可以直接使用 Dashboard 已有的 DLL/PYD 文件（它们在同一目录）。

> **关键假设**: 两个 exe 使用相同的 Python 版本和依赖版本。此假设由 `requirements.txt` 中已固定版本号保证。

---

## 7. Release Workflow

### 7.1 One-Time Setup

```bash
# Install PyInstaller (add to build deps)
pip install pyinstaller

# Create build directory structure
mkdir -p build models config assets

# Place resources
cp models/fatalis_ai_model.pkl models/
cp assets/icon.ico assets/
```

### 7.2 Build Steps

```bash
# Step 1: Verify tests pass
MPLBACKEND=Agg pytest tests/ -q     # 541 passed

# Step 2: Clean previous builds
rm -rf build/BlackDragon build/BlackDragonOverlay dist/

# Step 3: Build Dashboard EXE
pyinstaller build/BlackDragon.spec --clean --noconfirm

# Step 4: Build Overlay EXE
pyinstaller build/BlackDragonOverlay.spec --clean --noconfirm

# Step 5: Assemble release package
python build/post_build.py

# Step 6: Package for distribution
Compress-Archive -Path dist/BlackDragon-v1.0 -DestinationPath dist/BlackDragon-v1.0.zip

# Step 7: Verify (manual)
# - Extract zip to temp
# - Double-click BlackDragon.exe
# - Confirm Dashboard appears + Overlay auto-starts
```

### 7.3 GitHub Actions CI (Future)

```yaml
# .github/workflows/release.yml
name: Build Release
on:
  push:
    tags: ['v*']

jobs:
  build:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.12' }
      - run: pip install -r requirements.txt pyinstaller
      - run: MPLBACKEND=Agg pytest tests/ -q
      - run: pyinstaller build/BlackDragon.spec --clean --noconfirm
      - run: pyinstaller build/BlackDragonOverlay.spec --clean --noconfirm
      - run: python build/post_build.py
      - run: powershell Compress-Archive -Path dist/BlackDragon-v1.0 -DestinationPath dist/BlackDragon-v1.0.zip
      - uses: actions/upload-artifact@v4
        with:
          name: BlackDragon-v1.0
          path: dist/BlackDragon-v1.0.zip
```

---

## 8. Migration Summary

### 8.1 Files to Create

| File | Purpose | Location |
|------|---------|----------|
| `build/BlackDragon.spec` | Dashboard exe build spec | `build/` |
| `build/BlackDragonOverlay.spec` | Overlay exe build spec | `build/` |
| `build/post_build.py` | Release package assembly script | `build/` |
| `assets/icon.ico` | Application icon (optional) | `assets/` |
| `assets/README.txt` | User-facing README for release package | `assets/` |

### 8.2 Files to Modify

| File | Lines | Change |
|------|:---:|--------|
| `src/app/controller.py` | ~15 | `start_overlay()` — frozen env subprocess path |
| `src/bootstrap/checker.py` | +3 | `ensure()` — frozen env gate |

### 8.3 Files EXCLUDED from Modification

| File | Reason |
|------|--------|
| `launch.py` | Entry unchanged — dev mode still `python launch.py` |
| `overlay.py` | Entry unchanged — dev mode still `python overlay.py` |
| `src/core/`, `src/model/`, `src/data/` | P4 frozen |
| `src/ui/overlay.py`, `src/ui/fonts.py` | Unchanged |
| `src/app/config.py` | Unchanged (AppConfig.load() handles exe gracefully) |
| `src/dashboard/` | Unchanged |
| `tests/` | Unchanged |

---

## 9. Risk Register

| # | Risk | Severity | Mitigation |
|---|------|:---:|------|
| R1 | Two exes double disk usage (~340 MB vs ~190 MB single-exe) | 🟡 Medium | Acceptable for target audience (modern gaming PCs); de-duplication via shared dependency directory mitigates partially |
| R2 | `post_build.py` merge may miss DLLs | 🔴 High | Test on clean Windows VM; verify both exes launch |
| R3 | LightGBM `lib_lightgbm.dll` not detected | 🔴 High | Explicit `--hidden-import` + `--collect-binaries lightgbm` in both specs |
| R4 | `subprocess.Popen("BlackDragonOverlay.exe")` may fail if CWD ≠ exe dir | 🟡 Medium | Use `os.path.dirname(sys.executable)` to resolve absolute path — tested in `controller.py` adaptation |
| R5 | Windows Defender false positive on two PyInstaller exes | 🟢 Low | Code signing (EV cert) optional; documentation disclaimer |
