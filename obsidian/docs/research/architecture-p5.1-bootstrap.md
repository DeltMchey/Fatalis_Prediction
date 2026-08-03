# P5.1 — Bootstrap + Game-less Startup Architecture

> **目标**: (A) 启动时自动检查运行环境、(B) 无游戏进程时 Dashboard 正常运行、
> 同时处理 Reviewer 提出的 2 个 Should Fix。

---

## 1. Reviewer Should Fix 处理

### SF-1: Dashboard 不应绕过 AppController 直调 overlay

**位置**: `src/dashboard/main_window.py` L103-110

**当前**:
```python
def _refresh_overlay(self):
    overlay = getattr(self._controller, "_overlay", None)  # ← 访问私有属性
    if overlay is not None and self._controller.is_overlay_visible:
        overlay.update_logic()                               # ← 直接操作 OverlayUI
```

**修改**: 在 `AppController` 中新增 `refresh_overlay()` 方法：

```python
# src/app/controller.py
def refresh_overlay(self) -> None:
    """驱动覆盖层 update_logic()（Dashboard 每帧调用）。"""
    if self._overlay is not None and self._overlay_visible:
        try:
            self._overlay.update_logic()
        except Exception:
            logger.debug("Overlay 刷新异常", exc_info=True)  # NH-2: 不再静默吞掉
```

Dashboard 改为:
```python
def _refresh_overlay(self) -> None:
    self._controller.refresh_overlay()
```

### SF-2: `_apply_win32_overlay` 调用时机偏移

**位置**: `src/ui/overlay.py` L115-126

**当前**:
```python
def create_viewport(self):
    self._create_widgets()
    dpg.create_viewport(...)
    self._apply_win32_overlay()   # ← 在 setup_dearpygui 之前调用

def _setup_dpg(self):
    dpg.create_context()
    self.create_viewport()         # _apply_win32_overlay 在此执行
    dpg.setup_dearpygui()
    dpg.show_viewport()
    # 原始代码: _apply_win32_overlay 在此
```

**修改**: 恢复原始顺序——`_apply_win32_overlay` 在 `setup_dearpygui + show_viewport` **之后**：

```python
def create_viewport(self):
    """仅创建 viewport + widgets（不含 Win32 透明设置）。"""
    self._create_widgets()
    dpg.create_viewport(...)

def finalize_viewport(self):
    """在 show_viewport 之后应用 Win32 透明设置。"""
    self._apply_win32_overlay()

def _setup_dpg(self):
    """Standalone 模式（向后兼容）——原始顺序不变。"""
    dpg.create_context()
    self.create_viewport()
    dpg.setup_dearpygui()
    dpg.show_viewport()
    self._apply_win32_overlay()      # ← 恢复至最后
```

AppController 调用:
```python
def start_overlay(self):
    ...
    self._overlay.create_viewport()
    self._overlay.show_viewport()
    self._overlay.finalize_viewport()   # SF-2 NEW
    self._overlay_visible = True
```

---

## 2. 需求 A — Bootstrap 环境检查

### 2.1 架构

```
launch.py
├── Step 0: bootstrap  ← NEW
│   DependencyChecker.check()
│   ├─ Python ≥ 3.11?      (yes/no → 退出)
│   ├─ requirements.txt 全部满足?  (yes → 继续)
│   └─ 缺失 → 提示 → pip install → 重试 → 继续或退出
│
├── Step 1: GameService  ← 需求 B
├── Step 2: AppController
└── Step 3: Dashboard.run()
```

### 2.2 新增模块: `src/bootstrap/checker.py`

```python
# 职责: 环境检查 + 依赖安装
# 约束: 零第三方依赖（仅 Python stdlib）—— bootstrap 在 pip install 之前运行
#       不导入 dearpygui / pymem / P4 模块

class DependencyChecker:
    @staticmethod
    def check_python_version(min_version=(3, 11)) -> bool
    @staticmethod
    def get_missing(requirements_path="requirements.txt") -> list[str]
        # 解析 requirements.txt → importlib.metadata 比对已安装版本
    @staticmethod
    def install(packages: list[str]) -> bool
        # subprocess: [sys.executable, "-m", "pip", "install", *packages]
    @classmethod
    def ensure(cls, requirements_path="requirements.txt") -> bool
        # 一站式: check→ask→install→retry
        # 返回 True 表示环境就绪，False 表示用户放弃
```

### 2.3 UI 交互

Bootstrap 在 Dashboard **之前**运行（控制台模式），不污染 UI 层：

```
$ python launch.py

BlackDragon 环境检查...
  Python 3.12.6 ✅ (需要 ≥ 3.11)
  依赖检查: dearpygui ✅  joblib ✅  lightgbm ✅  ...  Pymem ❌
  缺失: Pymem==1.14.0

自动安装缺失依赖? [Y/n]: Y
Installing Pymem==1.14.0... ✅

环境就绪。正在启动 BlackDragon...
```

### 2.4 与 launch.py 集成

```python
# launch.py
from src.bootstrap.checker import DependencyChecker

def main():
    if not DependencyChecker.ensure():
        return  # 用户放弃安装
    # ... 继续原有流程
```

---

## 3. 需求 B — 无游戏进程启动 Dashboard

### 3.1 核心思想

将 P4 模块的初始化从"阻塞前置条件"改为"后台检测 → 动态附着"：

```
BEFORE (当前 launch.py):
  pymem 连接 → 失败 = 退出
  → 初始化 P4 模块 (MemoryReader/StateTracker/Predictor/Recorder)
  → AppController(所有模块)
  → Dashboard.run()

AFTER (新 launch.py):
  bootstrap → Dashboard(最小依赖) → GameService(后台检测)
  → 检测到游戏 → attach_game(P4 模块) → Dashboard 启用按钮
  → 游戏退出 → detach_game → Dashboard 禁用按钮
```

### 3.2 新增模块: `src/app/game_service.py`

```python
class GameService:
    """后台游戏检测线程。

    职责:
      - 循环检测 MonsterHunterWorld.exe 是否存在
      - 游戏出现 → 通知 AppController 初始化 P4 模块
      - 游戏消失 → 通知 AppController 清理 P4 模块
    """

    _POLL_INTERVAL: float = 2.0          # 未连接时轮询间隔
    _MONITOR_INTERVAL: float = 2.0       # 已连接时健康检查间隔

    def __init__(self, controller):
        self._controller = controller
        self._running = False
        self._thread = None

    def start(self) -> None:
        """启动检测线程（daemon）。"""
        ...

    def stop(self) -> None:
        """停止检测线程。"""
        ...

    def _run(self) -> None:
        """检测主循环:
          while running:
            if not controller.is_game_attached:
                尝试 pymem.Pymem("MonsterHunterWorld.exe")
                → 成功: controller.attach_game(pm, base)
                → 失败: sleep(2)
            else:
                健康检查: check_zone() or process alive
                → 失败(连续N次): controller.detach_game()
                sleep(2)
        """
```

### 3.3 AppController 生命周期变化

```python
class AppController:
    # ── 构造 — 轻量化 ──
    def __init__(self, config: AppConfig):
        # 仅 config 必选——P4 模块延迟附着
        self._config = config
        self._state = None       # CombatStateTracker — None 直到 attach_game
        self._recorder = None    # CombatRecorder
        self._predictor = None   # ActionPredictor
        self._reader = None      # MemoryReader
        self._overlay = None     # OverlayUI
        self._buffer = None      # deque
        self._lock = None        # Lock

        self._overlay_visible = False
        self._game_attached = False

    # ── 游戏附着/分离 ──
    def attach_game(self, pm, base) -> bool:
        """GameService 检测到游戏时调用。
        创建全部 P4 模块 → 启动 Recorder → 创建 Overlay(未显示)。
        失败回滚（部分创建的模块清理干净）。
        """

    def detach_game(self) -> None:
        """游戏退出时调用。
        stop recorder → hide overlay → 清理所有 P4 引用。
        """

    @property
    def is_game_attached(self) -> bool:
        """P4 模块是否已初始化（游戏已连接）。"""
        return self._game_attached

    @property
    def is_game_connected(self) -> bool:
        """游戏进程是否仍存活（已附着 + 内存可读）。"""
        if not self._game_attached:
            return False
        try:
            return self._reader.check_zone() is not None
        except Exception:
            return False

    # ── SF-1: Overlay 刷新 ──
    def refresh_overlay(self) -> None:
        """Dashboard 每帧调用。仅当 overlay 可见时执行 update_logic()。"""

    # ── 以下方法与 P5 当前一致 ──
    def toggle_recording / set_recording / start_overlay / stop_overlay
    def start_training / cancel_training / get_training_output / shutdown
```

### 3.4 Dashboard 适配

| 变化 | 说明 |
|------|------|
| 按钮启用/禁用 | `_on_frame()` 根据 `controller.is_game_attached` 动态启用/禁用 "启动覆盖层" 按钮和录制 checkbox |
| StatusBar | 新增状态 "游戏: 🟡 检测中"（GameService 运行但未附着） |
| `_refresh_overlay` | 改为 `self._controller.refresh_overlay()`（SF-1） |

### 3.5 launch.py 重写

```python
# launch.py — P5.1
def main():
    # 0. Bootstrap
    if not DependencyChecker.ensure():
        return

    # 1. 轻量 Controller（无 P4 模块）
    config = AppConfig.load()
    controller = AppController(config)

    # 2. Dashboard（无游戏连接）
    dashboard = Dashboard(controller)

    # 3. 后台游戏检测
    game_service = GameService(controller)
    game_service.start()

    # 4. DPG event loop（阻塞）
    dashboard.run()     # finally → controller.shutdown() + game_service.stop()
```

---

## 4. 整体架构

```
┌─────────────────────────────────────────────────────────┐
│ launch.py                                              │
│                                                        │
│  bootstrap.ensure()                                     │
│    └─ 失败 → exit                                      │
│                                                        │
│  controller = AppController(config)    ← 仅 config     │
│  dashboard  = Dashboard(controller)                     │
│  game_svc   = GameService(controller).start()           │
│  dashboard.run()                      ← 阻塞 (DPG)     │
│                                                        │
│ ═════════════ GameService (daemon) ══════════════════  │
│                                                        │
│  while running:                                        │
│    if not attached:                                    │
│      try pymem → attach_game(pm, base):                │
│        ├─ MemoryReader(pm, base)                       │
│        ├─ CombatStateTracker()                         │
│        ├─ ActionPredictor("models/...")                │
│        ├─ deque(100) + Lock()                          │
│        ├─ CombatRecorder(...).start()                  │
│        └─ OverlayUI(...)                               │
│      except: sleep(2)                                  │
│    else:                                               │
│      健康检查 → 失败 → detach_game():                   │
│        ├─ recorder.stop()                              │
│        ├─ overlay.hide_viewport()                      │
│        └─ 清理所有 P4 引用                              │
│      sleep(2)                                          │
│                                                        │
│ ═════════════ Dashboard main thread ═════════════════  │
│                                                        │
│  while dpg.is_running:                                 │
│    controller.refresh_overlay()   ← SF-1               │
│    status.Update(...)                                   │
│    log_view.refresh()                                   │
│    training_panel.refresh()                             │
│    _refresh_csv_list()                                  │
│    _refresh_button_states()     ← 需求 B               │
│    dpg.render_dearpygui_frame()                         │
│                                                        │
│ finally:                                               │
│    controller.shutdown()                               │
│    game_service.stop()                                │
│    dpg.destroy_context()                               │
└─────────────────────────────────────────────────────────┘
```

---

## 5. 新增 / 修改模块

### 新增

| 文件 | 职责 |
|------|------|
| `src/bootstrap/__init__.py` | bootstrap 包 |
| `src/bootstrap/checker.py` | DependencyChecker: Python 版本 + pip 依赖检查/安装 |
| `src/app/game_service.py` | GameService: 后台游戏检测线程 |

### 修改

| 文件 | 变更 |
|------|------|
| `src/app/controller.py` | 构造轻量化（仅 config）；新增 `attach_game/detach_game/refresh_overlay/is_game_attached` |
| `src/ui/overlay.py` | SF-2: `create_viewport` 移除 `_apply_win32_overlay`；新增 `finalize_viewport`；`_setup_dpg` 恢复原始顺序 |
| `src/dashboard/main_window.py` | SF-1: `_refresh_overlay` 改为 `controller.refresh_overlay()`；需求 B: 按钮启用/禁用逻辑 |
| `src/dashboard/status_bar.py` | NH-1: 移除 `paused` 参数；新增 "检测中" 状态 |
| `launch.py` | 完全重写：bootstrap + 轻量 controller + GameService + Dashboard |

---

## 6. API 设计

### DependencyChecker

```python
class DependencyChecker:
    @staticmethod
    def check_python_version(min_version=(3, 11)) -> bool
    @staticmethod
    def get_missing(requirements_path="requirements.txt") -> list[str]
    @staticmethod
    def install(packages: list[str]) -> bool
    @classmethod
    def ensure(cls, requirements_path="requirements.txt",
               auto_install: bool = False) -> bool
        # auto_install=True 跳过提示直接安装（CI 模式）
```

### GameService

```python
class GameService:
    def __init__(self, controller: AppController):
    def start(self) -> None       # 启动 daemon 线程
    def stop(self) -> None        # 停止检测
    @property
    def is_running(self) -> bool
```

### AppController（新增/修改接口）

```python
class AppController:
    # 构造: controller = AppController(config)          ← 仅 config
    def __init__(self, config: AppConfig):

    # 游戏生命周期
    def attach_game(self, pm, base) -> bool              ← NEW
    def detach_game(self) -> None                        ← NEW
    @property is_game_attached(self) -> bool             ← NEW

    # Overlay 刷新（SF-1）
    def refresh_overlay(self) -> None                    ← NEW

    # 现有接口不变
    toggle_recording / set_recording / start_overlay / stop_overlay
    start_training / cancel_training / get_training_output / shutdown
    is_recording / is_model_loaded / is_overlay_visible / is_training
```

### OverlayUI（新增接口 — SF-2）

```python
class OverlayUI:
    def create_viewport(self)    # 移除 _apply_win32_overlay 调用
    def finalize_viewport(self)  # NEW: 公开 Win32 透明设置
    def show_viewport(self)      # 不变
    def hide_viewport(self)      # 不变
    def run(self)                # 向后兼容不变
```

---

## 7. 生命周期流程图

### 正常启动（游戏存在）

```
launch.py main()
│
├─ [0] bootstrap.ensure() → ✅
│
├─ [1] controller = AppController(config)
├─ [2] dashboard = Dashboard(controller)
├─ [3] game_service = GameService(controller).start()
│
├─ [4] dashboard.run()  ← 阻塞
│      │
│      └─ _on_frame() 每帧:
│         ├─ controller.refresh_overlay()
│         ├─ status.update(game=🟡 检测中, ...)
│         └─ 按钮: disabled
│
│  GameService (后台):
│  ├─ try pymem.Pymem("MonsterHunterWorld.exe") → ✅
│  ├─ controller.attach_game(pm, base)
│  │   ├─ MemoryReader / StateTracker / Predictor / Recorder / OverlayUI
│  │   └─ recorder.start()
│  └─ Dashboard 按钮: enabled, status: 🟢
│
│  用户点击 "启动覆盖层":
│  ├─ controller.start_overlay()
│  │   ├─ overlay.create_viewport()
│  │   ├─ overlay.show_viewport()
│  │   └─ overlay.finalize_viewport()  (SF-2)
│  └─ _on_frame: overlay.update_logic()
│
│  用户关闭 Dashboard:
│  └─ finally: controller.shutdown() + game_service.stop() + dpg.destroy_context()
```

### 无游戏启动 → 延迟连接

```
launch.py main()
│
├─ [0] bootstrap.ensure() → ✅
├─ [1-3] controller + dashboard + game_service
├─ [4] dashboard.run()
│
│  GameService:
│  ├─ try pymem → ❌ (进程不存在)
│  ├─ sleep(2)
│  ├─ try pymem → ❌
│  ├─ ... (每 2 秒重试)
│
│  用户启动 MonsterHunterWorld.exe ...
│
│  GameService:
│  ├─ try pymem → ✅
│  └─ controller.attach_game()
│      └─ Dashboard 按钮: enabled, status: 🟢
```

### 游戏退出 → 重新等待

```
  游戏运行中（attached）
│
│  GameService 健康检查:
│  ├─ check_zone() → None (进程已退出)
│  └─ controller.detach_game()
│      ├─ recorder.stop()
│      ├─ overlay.hide_viewport()
│      └─ 清理 P4 引用
│
│  Dashboard 按钮: disabled, status: 🔴
│
│  GameService 重新进入检测循环...
```

---

## 8. 风险分析

| ID | 风险 | 级别 | 缓解 |
|----|------|:--:|------|
| R1 | `attach_game()` 部分失败（MemoryReader 创建成功但 Predictor 失败）→ P4 模块状态不一致 | **High** | `attach_game()` 用 try/finally 回滚：若创建失败，清理已创建的模块再 return False |
| R2 | GameService 在后台线程调用 `attach_game()`，创建 Recorder + start() → daemon 线程从后台线程启动 | **Medium** | Recorder.start() 本身就是用 daemon 线程——从哪个线程调用 start() 不影响。但需验证 `recorder.start()` 和 `overlay.create_viewport()` 不在主调线程中调用 DPG（`finalize_viewport` 会调 `dpg.set_viewport_pos` —— **这必须在主线程！**） |
| R3 | `finalize_viewport()` 含 DPG 调用，在 GameService 线程中执行会崩溃 | **High** | **关键设计决定**: `attach_game()` 只负责创建 OverlayUI 实例（构造仅存依赖），不调用 create_viewport。`start_overlay()` 仍由用户在 Dashboard 按钮中触发（主线程）→ 安全。 |
| R4 | `bootstrap.install()` 使用 subprocess pip install，权限不足 | **Low** | try/except + 提示用户手动安装；`--user` 标志 |
| R5 | `DependencyChecker.get_missing()` 解析 requirements.txt 格式兼容性 | **Low** | 支持 `pkg==version` / `pkg>=version` / 注释行 / 空行 |
| R6 | Dashboard 按钮禁用/启用状态闪烁（GameService 在 attached/detached 间快速切换） | **Low** | 使用连续失败阈值（如连续 3 次 check_zone()=None 才 detach） |
| R7 | `detach_game()` 中 recorder.stop() 异步（线程退出需 ~1s），Dashboard 在此期间调用已销毁的 overlay | **Low** | `detach_game()` 设置 `_overlay = None` 并 `hide_viewport()` 先关闭 UI，recorder.stop() 异步运行 |

### R2/R3 详细分析

GameService._run() 线程中：
```
attach_game() {
    create P4 modules (no DPG calls) ← ✅ 纯 Python/PyMem
    overlay = OverlayUI(...)          ← ✅ 仅存依赖，无 DPG
    recorder.start()                  ← ✅ 从任何线程调用均可
}
```

用户点击 "启动覆盖层" (主线程) → start_overlay():
```
overlay.create_viewport() ← DPG: create viewport + widgets
overlay.show_viewport()   ← DPG
overlay.finalize_viewport() ← DPG: set_viewport_pos + ctypes
```
所有 DPG 调用在**主线程**执行。—— 安全 ✅

---

## 9. 线程模型（更新）

| 线程 | 内容 | 创建时机 |
|------|------|------|
| **Main** | Dashboard DPG event loop | launch.py 启动时 |
| **Daemon 1** | GameService 检测循环 (2s) | launch.py → game_service.start() |
| **Daemon 2** | CombatRecorder CSV 录制 (0.1s) | GameService → attach_game → recorder.start() |
| **Daemon 3** | TrainingReader stdout 消费 | AppController → start_training() |

---

## 10. 实施步骤

| 步骤 | 内容 | 文件 |
|:--:|------|------|
| 1 | SF-2: 修改 OverlayUI — 移除 `_apply_win32_overlay` from `create_viewport`，新增 `finalize_viewport`，恢复 `_setup_dpg` 原始顺序 | `src/ui/overlay.py` |
| 2 | SF-1: AppController 新增 `refresh_overlay()` | `src/app/controller.py` |
| 3 | SF-1: Dashboard `_refresh_overlay` 改为 `controller.refresh_overlay()` | `src/dashboard/main_window.py` |
| 4 | NH-1: StatusBar 移除 `paused` 参数 | `src/dashboard/status_bar.py` |
| 5 | 创建 `DependencyChecker` | `src/bootstrap/checker.py` |
| 6 | 重构 AppController — 构造轻量化 + `attach_game/detach_game/is_game_attached` | `src/app/controller.py` |
| 7 | 创建 `GameService` | `src/app/game_service.py` |
| 8 | Dashboard 适配 — 按钮启用/禁用逻辑 + StatusBar "检测中" | `src/dashboard/main_window.py` |
| 9 | 重写 `launch.py` — bootstrap + 轻量 controller + GameService + Dashboard | `launch.py` |
| 10 | 测试 — `test_bootstrap_checker.py` / `test_game_service.py` / 扩展现有测试 | `tests/` |
| 11 | 全量回归 — `pytest -q` 确认 445+ tests 通过 | — |
| 12 | Review + commit | — |

---

## 11. 涉及文件清单

| 操作 | 文件 | 变更量 |
|:--:|------|:--:|
| 新增 | `src/bootstrap/__init__.py` | ~2 行 |
| 新增 | `src/bootstrap/checker.py` | ~100 行 |
| 新增 | `src/app/game_service.py` | ~80 行 |
| 修改 | `src/app/controller.py` | 构造重构 + attach/detach + refresh_overlay |
| 修改 | `src/ui/overlay.py` | SF-2: 拆分 _apply_win32_overlay；新增 finalize_viewport |
| 修改 | `src/dashboard/main_window.py` | SF-1: refresh_overlay；需求 B: 按钮状态；NH-1 |
| 修改 | `src/dashboard/status_bar.py` | NH-1: paused 参数移除 |
| 修改 | `launch.py` | 完全重写 |
