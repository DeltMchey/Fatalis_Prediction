# PyInstaller Build Guide — BlackDragon v1.0

- **Date**: 2026-08-04
- **Status**: Implementation

---

## 1. Overview

BlackDragon 使用 PyInstaller 将 Python 源码打包为 Windows 可执行文件。双进程架构生成 **两个 exe**：

| EXE | Entry | Process | Spawned By |
|-----|-------|---------|-----------|
| `BlackDragon.exe` | `launch.py` | Dashboard 控制中心 | 用户双击 |
| `BlackDragonOverlay.exe` | `overlay.py` | 透明覆盖层 | `BlackDragon.exe`（自动） |

## 2. Development Environment (source run)

开发环境不需要打包，直接运行源码：

```bash
# 双进程（推荐）
python launch.py

# 仅 Overlay
python overlay.py
```

`launch.py` → `controller.start_overlay()` 通过 `getattr(sys, "frozen", False)` 检测：

```python
# src/app/controller.py
if getattr(sys, "frozen", False):
    cmd = [exe_dir / "BlackDragonOverlay.exe"]   # 冻结模式
else:
    cmd = [sys.executable, "overlay.py"]         # 开发模式
```

## 3. Build Commands

### 3.1 Prerequisites

```bash
pip install pyinstaller
```

### 3.2 One-Click Build

```powershell
.\scripts\build_exe.ps1 -Clean
```

脚本自动执行：
1. 验证 PyInstaller 已安装
2. 运行 pytest（541 tests）——失败则中止
3. 清理旧构建产物
4. `pyinstaller build/BlackDragon.spec` → `dist/BlackDragon/`
5. `pyinstaller build/BlackDragonOverlay.spec` → `dist/BlackDragonOverlay/`

### 3.3 Manual Build

```bash
# Dashboard
pyinstaller build/BlackDragon.spec --noconfirm

# Overlay
pyinstaller build/BlackDragonOverlay.spec --noconfirm
```

## 4. Resource Directories

### 4.1 Bundled Resources (--datas)

| Resource | Path | Bundle Target |
|----------|------|--------------|
| AI model | `models/fatalis_ai_model.pkl` (17.6 MB) | `models/` in exe package |

两个 exe 各自打包模型（`--onedir` 模式下输出到 exe 同目录的 `models/`）。

### 4.2 External Directories (user-visible)

发布包建议结构：

```
BlackDragon-v1.0/
├── BlackDragon.exe
├── BlackDragonOverlay.exe
├── models/
│   └── fatalis_ai_model.pkl     ← 用户可替换
├── config/
│   └── blackdragon_config.json  ← 首次运行自动生成
└── data/                        ← 录制输出（自动创建）
```

### 4.3 System Resources (not bundled)

| Resource | Location | Note |
|----------|----------|------|
| CJK Font | `C:/Windows/Fonts/msyh.ttc` | Windows 系统字体，无需打包 |
| Offsets | 编译进 exe（`src/config/offsets.py`） | 无需单独文件 |
| Actions | 编译进 exe（`src/config/actions.py`） | 无需单独文件 |

## 5. Spec Files

### 5.1 `build/BlackDragon.spec` — Dashboard

- **Entry**: `launch.py`
- **Includes**: `src/app/`, `src/dashboard/`, `src/bootstrap/`, `src/core/`, `src/model/`, `src/data/`, `src/ui/fonts.py`
- **Hidden imports**: `dearpygui._dearpygui`, `lightgbm.*`, `sklearn.*`, `pandas._libs.tslibs`
- **Excludes**: matplotlib Tk/Qt backends
- **`upx=False`**: DPG/GLFW DLL 在 UPX 压缩下可能损坏

### 5.2 `build/BlackDragonOverlay.spec` — Overlay

- **Entry**: `overlay.py`
- **Includes**: `src/core/`, `src/model/`, `src/data/`, `src/ui/`, `src/app/config.py`
- **Excludes**: `src/dashboard/`, `src/bootstrap/`, `src/app/controller.py`, `src/app/game_service.py`（体积优化）

## 6. Frozen Mode Behavior

| Behavior | Dev (`python launch.py`) | Frozen (`BlackDragon.exe`) |
|----------|:---:|:---:|
| Overlay spawn | `python overlay.py` | `<exe_dir>/BlackDragonOverlay.exe` |
| DependencyChecker | 完整检查（pip） | 跳过（依赖已打包） |
| Overlay 脚本路径 | `overlay.py` | `BlackDragonOverlay.exe` |

**实现位置**:
- `src/app/controller.py:start_overlay()` — 检测 `sys.frozen`，选择 spawn 命令
- `launch.py:main()` — `getattr(sys, "frozen", False)` 门控 DependencyChecker

## 7. Release Workflow

```
1. 确保 541 tests pass
2. .\scripts\build_exe.ps1 -Clean
3. 收集 dist/BlackDragon/ 和 dist/BlackDragonOverlay/
4. 合并到发布目录（同目录放置两个 exe + models/ + config/）
5. 验证：双击 BlackDragon.exe → Dashboard + Overlay 出现
6. 打包 zip / 分发
```

## 8. Troubleshooting

| Issue | Cause | Fix |
|-------|-------|-----|
| `ModuleNotFoundError: lightgbm` at runtime | `lib_lightgbm.dll` 未收集 | spec 中已含 `lightgbm.*` hidden imports；若仍失败用 `--collect-binaries lightgbm` |
| DPG 窗口不出现 | GLFW DLL 缺失或 UPX 损坏 | 确认 `upx=False`；重新 `-Clean` 构建 |
| Overlay 未自动启动 | 两个 exe 不在同目录 | 确认 `BlackDragonOverlay.exe` 与 `BlackDragon.exe` 在同一目录 |
| 首次启动慢 | --onedir 解压 | 正常现象；现代 SSD 上 <5s |

## 9. Constraints

- P4 core（`src/core/`, `src/model/`, `src/data/`）零修改
- `launch.py` / `overlay.py` 开发模式不受影响（`python launch.py` 仍可用）
- 构建产物（`build/`, `dist/`）应加入 `.gitignore`
