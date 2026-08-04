# Frozen Runtime Bug Report — BlackDragon v1.0

- **Date**: 2026-08-04
- **Auditor**: Frozen Runtime Audit
- **Build**: `dist/BlackDragon/BlackDragon.exe` (PyInstaller --onedir, 20.35 MB)
- **Test Environment**: Windows 11, no venv, no Python PATH

---

## Bug 1: CSV File List Cannot Be Read in Frozen Mode

### 1.1 Root Cause

**路径解析链** (all use relative `"data"` → dependent on CWD):

```
src/app/config.py:36         data_dir: str = "data"              ← 硬编码相对路径
src/app/controller.py:196    return self._config.data_dir         → "data"
src/dashboard/main_window.py:141  Path(self._controller.data_dir) → Path("data")
src/data/recorder.py:60      data_dir: str = "data"              ← 硬编码相对路径
src/data/recorder.py:198     os.makedirs(self._data_dir, ...)    → mkdir("data")
```

**问题**: `Path("data")` 和 `os.path.join("data", ...)` 都解析为**相对于 CWD** 的路径。

| 环境 | CWD | `data/` 解析为 | Status |
|------|-----|---------------|:---:|
| `python launch.py` | 项目根 (`D:/.../BlackDragon`) | `D:/.../BlackDragon/data/` | ✅ Dev mode works |
| `BlackDragon.exe` (双击) | exe 所在目录 (`dist/BlackDragon/`) | `dist/BlackDragon/data/` | ⚠️ May work if CWD = exe dir |
| `BlackDragon.exe` (快捷方式 with Start in = Desktop) | Desktop | `Desktop/data/` | ❌ `data/` not found |
| `BlackDragon.exe` (cmd from other dir) | other dir | `<other>/data/` | ❌ `data/` not found |

**根因**: 冻结模式下，exe 的 CWD 依赖**用户如何启动它**——双击在 exe 所在目录；快捷方式可能指向不同目录；终端启动可能在任意目录。相对路径 `"data"` 不保证总是解析到 exe 同目录。

### 1.2 Impact

- Dashboard 中 "CSV 文件" 列表显示 "(无法读取)"
- `CombatRecorder` 可能将 CSV 写入错误的位置（取决于 CWD）——录制可能成功但文件不可见
- 两进程（Dashboard + Overlay）各自的 CWD 可能不同，导致一个能看到 CSV 而另一个不能

### 1.3 Fix: Resolve data_dir Relative to Exe Directory

在冻结模式下，所有文件系统路径应**相对于 exe 所在目录**，而非 CWD。

**修改文件**:

| File | Change |
|------|--------|
| `src/app/controller.py:194-196` | `data_dir` property: in frozen mode, resolve relative to `os.path.dirname(sys.executable)` |
| `src/app/config.py:36` | Add `get_data_dir()` helper OR leave as-is (default string) + resolve at use-site |

**推荐方案**: 在 `controller.data_dir` property 中处理（统一入口），不修改 `AppConfig`（保持 config 值为纯默认字符串，由 controller 解析）：

```python
# src/app/controller.py

import sys

@property
def data_dir(self) -> str:
    """录制 CSV 输出目录（Dashboard 显示文件列表用）。
    
    冻结模式下，data/ 解析为 <exe_dir>/data/ 而非 CWD。
    """
    path = self._config.data_dir  # "data"
    if getattr(sys, "frozen", False) and not os.path.isabs(path):
        path = os.path.join(os.path.dirname(sys.executable), path)
    return path
```

**注意**: `CombatRecorder` 的 `data_dir` 参数由 `controller.attach_game()` 传入（目前传的也是 `self._config.data_dir`）。需同步更新 `attach_game` 中的 `CombatRecorder(..., data_dir=self.data_dir)` 以使用解析后的路径——确保记录器和 Dashboard 读取相同的目录。

### 1.4 Dev Mode Impact

| Check | Result |
|-------|:---:|
| `python launch.py` — CWD = project root | `getattr(sys, "frozen", False)` = False → `path = "data"` → same as before ✅ |
| Existing tests | Unchanged (tests mock `data_dir` via MagicMock controller) ✅ |
| `AppConfig` default value | Unchanged (`data_dir: str = "data"`) ✅ |

**Dev mode unchanged** ✅

---

## Bug 2: Clicking "Model Training" Opens a New Dashboard Window

### 2.1 Root Cause

**控制链**:

```
controller.start_training()                         (line 261)
  → subprocess.Popen(                              (line 269)
      [sys.executable, self._config.training_script],  # training_script = "train_lgbm.py"
      ...
    )
```

| Environment | `sys.executable` | `training_script` | Result |
|-------------|-----------------|-------------------|--------|
| Dev mode | `python.exe` | `"train_lgbm.py"` | `python.exe train_lgbm.py` ✅ Runs training |
| Frozen mode | `BlackDragon.exe` | `"train_lgbm.py"` | `BlackDragon.exe train_lgbm.py` ❌ |

**为什么打开新 Dashboard**: `BlackDragon.exe` 的入口 (`launch.py main()`) 不处理 `train_lgbm.py` 参数。exe 启动后，`sys.argv` 中包含 `train_lgbm.py`，但 `main()` 无条件执行 Dashboard 启动流程——相当于启动第二个 `BlackDragon.exe` 实例。

**这是 `start_overlay()` 已修复但 `start_training()` 未修复的对称 Bug**:

| Method | Dev Mode Spawn | Frozen Fixed? |
|--------|---------------|:---:|
| `start_overlay()` | `[python, overlay.py]` | ✅ Fixed: `[BlackDragonOverlay.exe]` |
| `start_training()` | `[python, train_lgbm.py]` | ❌ NOT Fixed: `[BlackDragon.exe, train_lgbm.py]` |

### 2.2 Impact

- 点击 Dashboard 中"开始训练"→ 新的 `BlackDragon.exe` 弹窗（第二个 Dashboard）
- 训练实际上**未执行**（`train_lgbm.py` 作为参数被 exe 忽略）
- 第二个 Dashboard 可能 crash（两个 DPG instance 冲突）
- Dashboard 状态栏显示"训练进行中"（因为 `_training_proc.poll()` = None），但实际并未训练

### 2.3 Fix: --train Flag Mode

**方案**: 与 overlay 同样的 flag-based 模式——`BlackDragon.exe --train` 进入训练模式。

**步骤 1: `launch.py` 入口添加 `--train` 检测**

```python
# launch.py main()

def main():
    # --train flag: run training in frozen mode (spawned by controller)
    if "--train" in sys.argv:
        from train_lgbm import train_fatalis_ai
        sys.argv.remove("--train")
        train_fatalis_ai()
        return

    # ... existing Dashboard launch logic ...
```

**步骤 2: `controller.start_training()` 冻结模式分支**

```python
# src/app/controller.py — start_training()

def start_training(self) -> bool:
    if self.is_training:
        return False
    try:
        if getattr(sys, "frozen", False):
            # 冻结模式：spawn 同 exe 的 --train 模式
            cmd = [sys.executable, "--train"]
        else:
            # 开发模式：python train_lgbm.py
            cmd = [sys.executable, self._config.training_script]
        self._training_proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace",
        )
    except Exception:
        logger.error("启动训练失败", exc_info=True)
        return False
    # ... queue + thread setup unchanged ...
```

**关键验证**: `train_fatalis_ai()` 函数已在 `train_lgbm.py:15` 定义，可直接 import 调用。训练脚本输出仍然通过 `print()` 到 stdout → PIPE → `_read_training_output` 线程捕获。**输出捕获机制不变** ✅

### 2.4 Dev Mode Impact

| Check | Result |
|-------|:---:|
| `python launch.py` — `getattr(sys, "frozen", False)` = False → `[python, train_lgbm.py]` → same as before ✅ |
| `train_lgbm.py` standalone (`python train_lgbm.py`) | Unchanged ✅ |
| Test `test_start_training()` — monkeypatches `subprocess.Popen` → dev mode path → unchanged ✅ |
| `--train` flag NOT triggered in dev mode (frozen=False → cmd = [python, script]) | ✅ |

**Dev mode unchanged** ✅

### 2.5 Alternative Considered: Disable Training in Frozen Mode

**方案**: 冻结模式下禁用训练按钮，显示"训练仅在开发模式可用"。

**拒绝理由**:
- 用户数据采集后需要重新训练模型——这是核心工作流的一部分
- 训练脚本 (`train_lgbm.py` 88 lines) 是纯 Python，可内联运行
- `--train` flag 方案最接近 overlay 的已验证模式，复用相同架构

---

## 3. Fix Summary

| Bug | Files to Modify | Dev Impact | Test Impact |
|-----|----------------|:---:|:---:|
| Bug 1 (CSV path) | `src/app/controller.py:194-196` (`data_dir` property) | None | None (property returns string, tests mock) |
| Bug 2 (Training) | `launch.py:main()` (+ `--train` flag), `src/app/controller.py:261-276` (`start_training`) | None | None (frozen=False → dev path unchanged) |

### Modified Files

| File | Lines Changed | Change Description |
|------|:---:|------|
| `src/app/controller.py` | ~10 | `data_dir` property frozen-aware path resolve; `start_training()` frozen branch |
| `launch.py` | ~5 | `--train` flag detection |

### NOT Modified

| File | Reason |
|------|--------|
| `src/app/config.py` | Default `"data"` value unchanged — resolution happens at use-site |
| `src/data/recorder.py` | Accepts `data_dir` string; resolution happens at caller (`attach_game` passes `controller.data_dir` which is now frozen-aware) |
| `src/core/`, `src/model/`, `src/data/` | P4 frozen — zero diff |
| `tests/` | All existing tests pass (mocked controller) |

---

## 4. Test Plan

### 4.1 Existing Tests

```bash
MPLBACKEND=Agg pytest tests/ -q  # 541 passed — unchanged
```

Existing tests mock `AppController.data_dir` and `subprocess.Popen` — frozen path not exercised. Expected: **541 passed** ✅

### 4.2 New Tests (Recommended)

| Test | What It Verifies |
|------|-----------------|
| `test_data_dir_frozen_resolves_to_exe_dir` | Patch `sys.frozen=True`, `sys.executable=v:/path/exe.exe` → `controller.data_dir` returns `v:/path/data` |
| `test_data_dir_dev_uses_config_value` | Frozen=False → returns `self._config.data_dir` (raw "data") |
| `test_start_training_frozen_uses_flag` | Patch `sys.frozen=True`, verify `subprocess.Popen` called with `[sys.executable, "--train"]` |
| `test_main_handles_train_flag` | Patch `train_lgbm.train_fatalis_ai`, call `main()` with `sys.argv=['exe','--train']` → `train_fatalis_ai` called |

### 4.3 Manual Runtime Test

After fix + rebuild:

```bash
.\scripts\build_exe.ps1 -Clean
dist/BlackDragon/BlackDragon.exe
```

Manual checks:
- [ ] Dashboard CSV list shows files (or "(无 CSV 文件)" not "(无法读取)")
- [ ] Click "开始训练" → no new Dashboard window
- [ ] Training output appears in Training tab
- [ ] `dist/BlackDragon/data/` populated by recorder
