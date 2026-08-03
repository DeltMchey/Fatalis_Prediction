# BlackDragon 用户控制中心 — 架构设计

> **目标**: 新增 Dashboard UI 层，使用户无需命令行即可管理 BlackDragon。
> **约束**: 不修改现有 P4 模块内部代码; 不破坏 385 测试; `python main.py` 仍可运行。

---

## 1. 新 UI 职责边界

### 1.1 Dashboard（`src/dashboard/`— 纯 UI 层）

| 可以做的事 | 不可以做的事 |
|-----------|-------------|
| ✅ 创建 DPG primary viewport 并运行 event loop | ❌ 不调用 `pm.read_*`（内存读取） |
| ✅ 显示各 Tab 的 widgets（按钮/表格/文本） | ❌ 不调用 `predictor.predict()`（AI 推理——仅显示结果） |
| ✅ 通过 AppController 间接控制模块 | ❌ 不自己创建 `MemoryReader` / `StateTracker` 实例 |
| ✅ 读 `AppConfig` 展示设置值 | ❌ 不直接操作文件系统（训练输出除外） |
| ✅ 显示 `blackdragon.log` 的实时流 | ❌ 不重新实现日志系统 |

### 1.2 AppController（`src/app/`— 协调层）

| 职责 | 不做什么 |
|------|---------|
| ✅ 持有 `recorder` / `predictor` / `state_tracker` 引用（注入） | ❌ 不持有 `MemoryReader` 引用（Dashboard 不需要读内存） |
| ✅ 暴露管理 API: `start_overlay()` / `stop_overlay()` / `toggle_recording()` / `start_training()` | ❌ 不管理底层线程——Recorder 自己管理 daemon 线程 |
| ✅ 管理 OverlayUI 的 viewport 生命周期 | ❌ 不处理 DPG widgets（那是 Dashboard 的职责） |
| ✅ 管理训练子进程 | ❌ 不自己加载/运行模型（那是 train_lgbm.py 的职责） |
| ✅ 将日志事件转发到 Dashboard | ❌ 不自己写日志文件 |

### 1.3 AppConfig（`src/app/config.py`— 设置层）

| 职责 |
|------|
| ✅ 定义所有可配置项（model_path、overlay_opacity、auto_start 等） |
| ✅ JSON 持久化（`save()` / `load()`） |
| ✅ 默认值（文件不存在时降级） |
| ✅ 供 Dashboard 读写 |

---

## 2. 进程 / 线程模型

### 2.1 线程拓扑

```
┌────────────────────────────────────────────────────┐
│ MAIN THREAD                                        │
│                                                    │
│  launch.py main()                                  │
│    │                                               │
│    ├─ pymem.Pymem(...)      连接游戏               │
│    ├─ MemoryReader(pm, base) 共享                  │
│    ├─ StateTracker()          共享                 │
│    ├─ Predictor(...)          UI 专用              │
│    ├─ deque + Lock            通信通道              │
│    │                                               │
│    ├─ AppController(...)      协调层               │
│    │                                               │
│    ├─ Dashboard(...)          DPG 主窗口           │
│    │   │                                           │
│    │   ├─ [控制台 Tab]  录制开关、Overlay 启停     │
│    │   ├─ [训练 Tab]    模型训练                   │
│    │   ├─ [数据 Tab]    CSV 文件浏览               │
│    │   ├─ [日志 Tab]    实时日志流                 │
│    │   └─ [设置 Tab]    参数配置                   │
│    │                                               │
│    └─ Dashboard.run()        DPG event loop (阻塞) │
│        │                                           │
│        ├─ on "Start Overlay":                       │
│        │   controller.start_overlay()               │
│        │   → OverlayUI.create_viewport()            │
│        │   → secondary viewport (透明覆盖层)        │
│        │                                           │
│        ├─ render callback:                          │
│        │   if overlay.is_active:                    │
│        │       overlay.update_logic()               │
│        │   dpg.render_dearpygui_frame()             │
│        │                                           │
│        └─ on window close:                          │
│            controller.shutdown()                    │
│            → recorder.stop()                        │
│            → dpg.destroy_context()                  │
│                                                    │
│  ═════════════════════════════════════════════════  │
│  DAEMON THREAD                                      │
│                                                    │
│  ┌─ CombatRecorder (0.1s loop)                     │
│  │   ├─ MemoryReader reads memory                  │
│  │   ├─ StateTracker reads (phase/posture/enrage)  │
│  │   ├─ action_buffer.append() (with lock)         │
│  │   └─ CSV write (with open/close per frame)      │
│  │                                                 │
│  └─ 生命周期: recorder.start() → recorder.stop()   │
│      (或进程退出时自动回收)                         │
└────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────┐
│ SUBPROCESS (训练时)                                 │
│                                                    │
│  python train_lgbm.py                              │
│    │                                               │
│    ├─ stdout → AppController → Dashboard 日志面板  │
│    └─ 退出码 → 训练成功/失败状态                    │
└────────────────────────────────────────────────────┘
```

### 2.2 生命周期状态机

```
    ┌──────────┐
    │  START   │  launch.py 启动
    └────┬─────┘
         ▼
    ┌──────────┐
    │  IDLE    │  Dashboard 显示，等待用户操作
    │          │  游戏: 未连接 🔴
    │          │  录制: 停止 ⬛
    │          │  覆盖层: 关闭 ⬛
    └────┬─────┘
         │ 用户点击 "Connect Game"
         ▼
    ┌──────────┐
    │CONNECTED │  pymem.Pymem("MonsterHunterWorld.exe") 成功
    │          │  游戏: 已连接 🟢
    │          │  录制: 停止 ⬛
    └────┬─────┘
         │ 用户点击 "Start Overlay"
         ▼
    ┌──────────┐
    │RUNNING   │  Recorder started + Overlay visible
    │          │  游戏: 已连接 🟢
    │          │  录制: 进行中 🟢 / 暂停 🟡 (is_recording)
    │          │  覆盖层: 打开 🟢
    └────┬─────┘
         │ 用户点击 "Start Training"
         ▼
    ┌──────────┐
    │TRAINING  │  子进程 train_lgbm.py 运行中
    │          │  录制: 可继续 (与训练并发)
    │          │  覆盖层: 可继续 (与训练并发)
    └────┬─────┘
         │ 用户关闭 Dashboard 窗口
         ▼
    ┌──────────┐
    │SHUTDOWN  │  recorder.stop()
    │          │  overlay.hide_viewport()
    │          │  dpg.destroy_context()
    │          │  进程退出
    └──────────┘
```

### 2.3 OverlayUI 的重构范围

```
当前 OverlayUI:

__init__(self, mr, st, pred, buf, lock)   ← 不变: 只存依赖
_setup_dpg()                              ← 拆分: create_context + setup → 移出
                                            create_viewport + widgets → 保留
_run_event_loop()                         ← 移出: Dashboard 主循环替代
_apply_win32_overlay()                    ← 不变
_destroy()                                ← 移出: Dashboard 负责 destroy_context
update_logic()                            ← 不变
_compute_frame()                          ← 不变
_compute_ai_display()                     ← 不变
_apply_display()                          ← 不变

─────────────────────────────────────────

重构后 OverlayUI:

__init__(...)                             ← 完全不变
create_viewport()                         ← NEW: 创建 secondary viewport +
                                            widgets + Win32 透明设置
                                            (包含原 _setup_dpg 的 viewport+
                                            window+widgets+Win32 部分,
                                            排除 create_context/setup/show_viewport)

update_logic()                            ← 完全不变
_compute_frame()                          ← 完全不变
_compute_ai_display()                     ← 完全不变
_apply_display()                          ← 完全不变
_apply_win32_overlay()                    ← 完全不变

hide_viewport()                           ← NEW: dpg.hide_viewport("overlay")
show_viewport()                           ← NEW: dpg.show_viewport("overlay")

run()                                     ← KEPT for backward compat:
                                            创建独立 DPG context →
                                            create_viewport() →
                                            event loop →
                                            destroy.
                                            (main.py 仍用这个，不动)
```

**P4.5 测试影响**: 零。`_compute_frame` / `_apply_display` / `update_logic` 完全不变。新增 `create_viewport()` / `show_viewport()` / `hide_viewport()` 是纯新方法，不影响现有测试路径。`run()` 保留原行为。

---

## 3. main.py 策略

**决策: 不修改 `main.py`。**

| 入口 | 文件 | 启动内容 | 用途 |
|------|------|---------|------|
| `python main.py` | main.py (不变) | P4 composition root → OverlayUI.run() | P4 backward compat + test compat |
| `python launch.py` | launch.py (新增) | P5 composition root → Dashboard.run() | 新推荐入口 |

`launch.py` 与 `main.py` 共享同一套 wiring 逻辑（MemoryReader + StateTracker + Predictor + Recorder），区别在于 wiring 的终点不同：

```
main.py wiring:     ... → OverlayUI → overlay.run()
launch.py wiring:   ... → AppController → Dashboard → dashboard.run()
```

`launch.py` 不需要 `import OverlayUI`——OverlayUI 由 AppController 在 Dashboard 请求时动态创建。

---

## 4. 数据流

```
                    ┌─────────────┐
                    │  launch.py  │  composition root
                    └──────┬──────┘
                           │ 创建并注入引用
        ┌──────────────────┼──────────────────┐
        ▼                  ▼                  ▼
┌───────────────┐  ┌──────────────┐  ┌────────────────┐
│MemoryReader   │  │StateTracker  │  │Predictor       │
│(shared, R/O)  │  │(shared, R/W) │  │(UI-only, R/O)  │
└───────┬───────┘  └──────┬───────┘  └───────┬────────┘
        │                 │                   │
        │    ┌────────────┘                   │
        │    │                                │
        ▼    ▼                                │
┌──────────────────┐                          │
│CombatRecorder    │                          │
│(daemon, R/O)     │                          │
│   reads st.phase │                          │
│   reads st.enrage│                          │
│   reads st.posture                         │
│   writes buf     │                          │
└────────┬─────────┘                          │
         │                                    │
         │  action_buffer + lock              │
         │                                    │
         ▼                                    ▼
┌──────────────────────────────────────────────────┐
│              AppController                       │
│                                                  │
│  manages:                                        │
│   - recorder.start() / stop()                    │
│   - state_tracker.is_recording (toggle)          │
│   - overlay create_viewport / hide / show        │
│   - training subprocess                          │
│                                                  │
│  exposes to Dashboard:                           │
│   - status properties (is_recording, etc.)       │
│   - commands (start_overlay, toggle_rec, train)  │
│   - log event stream                             │
└──────────────────────┬───────────────────────────┘
                       │
                       │  commands + status
                       ▼
┌──────────────────────────────────────────────────┐
│                 Dashboard                        │
│                                                  │
│  DPG primary viewport                            │
│  ┌─────────┬────────┬────────┬────────┬────────┐ │
│  │ 控制台  │  训练  │  数据  │  日志  │  设置  │ │
│  │         │        │        │        │        │ │
│  │ Start   │Train   │CSV    │实时    │model   │ │
│  │ Overlay │Button  │list   │日志    │path    │ │
│  │ Toggle  │Progress│file   │auto-   │opacity │ │
│  │ Record  │Log     │size   │scroll  │auto    │ │
│  └─────────┴────────┴────────┴────────┴────────┘ │
│  ┌──────────────────────────────────────────────┐ │
│  │ Status Bar: 🟢 Game | 🟢 Model | 🟢 Record  │ │
│  └──────────────────────────────────────────────┘ │
└──────────────────────┬───────────────────────────┘
                       │
                       │  用户点击 "Start Overlay"
                       ▼
┌──────────────────────────────────────────────────┐
│              OverlayUI                           │
│  (DPG secondary viewport — 透明覆盖层)           │
│                                                  │
│  Dashboard render callback 每帧调用:             │
│    overlay.update_logic()                        │
│    dpg.render_dearpygui_frame()  ← 渲染所有      │
│                                     viewports    │
└──────────────────────────────────────────────────┘
```

### 数据流方向总结

| 数据项 | 生产者 | 消费者 | 通道 |
|--------|--------|--------|------|
| 游戏内存数据 | MemoryReader | Recorder + OverlayUI | 直接读（stateless） |
| 战斗状态 | OverlayUI (write) | Recorder (read) | StateTracker 共享实例 |
| action_id | Recorder | OverlayUI | action_buffer + lock |
| 录制状态 | Dashboard → StateTracker | Recorder | `state_tracker.is_recording` |
| 日志事件 | Logger → QueueHandler | Dashboard 日志 Tab | `queue.Queue` |
| 训练输出 | train_lgbm subprocess stdout | Dashboard 训练 Tab | `subprocess.PIPE` |
| 用户设置 | Dashboard → AppConfig | launch.py (下次启动) | JSON 文件 |

---

## 5. 文件结构

```
BlackDragon/
│
├── launch.py                       ← NEW: P5 推荐入口（Dashboard composition root）
├── main.py                         ← 不变: P4 入口（OverlayUI composition root）
├── ai_engine.py                    ← 不变: legacy God Class
│
├── src/
│   ├── app/                         ← NEW: 应用层
│   │   ├── __init__.py
│   │   ├── config.py                ← AppConfig + logging QueueHandler
│   │   └── controller.py            ← AppController: 生命周期管理
│   │
│   ├── dashboard/                   ← NEW: UI 层
│   │   ├── __init__.py
│   │   ├── main_window.py           ← Dashboard: DPG 主窗口 (Tab + StatusBar)
│   │   ├── log_view.py              ← LogView: 实时日志面板
│   │   ├── training_panel.py        ← TrainingPanel: 模型训练 UI
│   │   └── status_bar.py            ← StatusBar: 状态指示灯
│   │
│   ├── core/                        ← 不变
│   │   ├── state_tracker.py
│   │   └── memory_reader.py
│   ├── model/                       ← 不变
│   │   └── predictor.py
│   ├── data/                        ← 不变
│   │   └── recorder.py
│   ├── ui/                          ← 重构 OverlayUI
│   │   └── overlay.py               ← 新增: create_viewport()/hide/show; run() 保留
│   ├── config/                      ← 不变
│   │   ├── actions.py
│   │   └── offsets.py
│   └── logging_config.py            ← 扩展: 添加 QueueHandler
│
├── tests/
│   ├── test_app_controller.py       ← NEW: ~15 tests
│   ├── test_app_config.py           ← NEW: ~8 tests
│   ├── test_dashboard.py            ← NEW: ~20 tests (mock DPG)
│   ├── test_overlay.py              ← 扩展: +5 tests for new methods
│   └── ... (all existing tests unchanged)
│
├── models/                          ← 不变
├── data/                            ← 不变
├── archive/                         ← 不变
├── obsidian/                        ← 不变 (memory bank)
├── requirements.txt                 ← 不变 (DPG 已存在)
├── pytest.ini                       ← 不变
└── .gitignore                       ← 不变
```

---

## 6. API 设计

### 6.1 AppController

```python
class AppController:
    """协调 Recorder / OverlayUI / Trainer 生命周期。

    与 Dashboard 的关系:
      Dashboard 持有 AppController 引用 → call commands + poll status.
      Dashboard NEVER 直接操作 Recorder / OverlayUI.
    """

    # ── 构造（注入现有模块）──
    def __init__(
        self,
        state_tracker: CombatStateTracker,
        recorder: CombatRecorder,
        predictor: ActionPredictor,
        memory_reader: MemoryReader,          # 仅用于 game_connected 检测
        config: AppConfig,
    ): ...

    # ── 状态查询（Dashboard 轮询）──
    @property
    def is_game_connected(self) -> bool: ...       # check_zone() is not None
    @property
    def is_recording(self) -> bool: ...            # state_tracker.is_recording
    @property
    def is_overlay_visible(self) -> bool: ...      # overlay viewport visible
    @property
    def is_model_loaded(self) -> bool: ...         # predictor.is_loaded
    @property
    def is_training(self) -> bool: ...             # training subprocess alive

    # ── 命令（Dashboard 按钮绑定）──
    def toggle_recording(self) -> None: ...        # flip state_tracker.is_recording
    def start_overlay(self) -> None: ...           # OverlayUI.create_viewport() + show
    def stop_overlay(self) -> None: ...            # OverlayUI.hide_viewport()
    def start_training(self) -> None: ...          # subprocess.Popen(["python","train_lgbm.py"])
    def cancel_training(self) -> None: ...         # subprocess.kill()
    def shutdown(self) -> None: ...                # recorder.stop() + cleanup

    # ── 训练输出流（Dashboard 日志 Tab 消费）──
    def get_training_output(self) -> str | None: ...  # 从 subprocess.stdout 读一行
    def get_log_messages(self) -> list[str]: ...       # 从 log_queue 取所有待显示消息
```

### 6.2 AppConfig

```python
@dataclass
class AppConfig:
    # ── 模型 ──
    model_path: str = "models/fatalis_ai_model.pkl"

    # ── 录制 ──
    data_dir: str = "data"

    # ── Overlay ──
    auto_start_overlay: bool = False
    overlay_opacity: float = 1.0           # (future use)

    # ── 预测 ──
    prediction_interval: float = 0.5

    # ── 持久化 ──
    @classmethod
    def load(cls, path: str = "blackdragon_config.json") -> "AppConfig": ...

    def save(self, path: str = "blackdragon_config.json") -> None: ...

    def reset_to_defaults(self) -> None: ...
```

### 6.3 Dashboard

```python
class Dashboard:
    """DPG 主窗口——用户控制中心。

    构造函数只创建 DPG context 和 primary viewport。
    Tab 内容按需创建（通过 controller 查询/命令）。
    """

    def __init__(self, controller: AppController): ...
    def run(self) -> None: ...
        # 创建 primary viewport
        # dpg.setup_dearpygui()
        # while dpg.is_dearpygui_running():
        #     self._on_frame()
        #     dpg.render_dearpygui_frame()
        # finally: controller.shutdown()
```

### 6.4 OverlayUI（重构后新增方法）

```python
class OverlayUI:
    # 现有方法保持不变:
    #   __init__, _on_recording_toggle, update_logic,
    #   _compute_frame, _compute_ai_display, _apply_display, run()

    # ── 新增: 外部驱动的 viewport 管理 ──

    def create_viewport(self) -> None:
        """创建 secondary viewport + widgets + Win32 透明设置。

        由 AppController 在 Dashboard 请求 Start Overlay 时调用。
        DPG context 必须已在外部创建（Dashboard.run() 负责）。
        调用后 OverlayUI 开始接收 update_logic() 调用（由 Dashboard
        的 render callback 驱动）。
        """

    def hide_viewport(self) -> None:
        """隐藏覆盖层（不销毁 viewport）。"""

    def show_viewport(self) -> None:
        """重新显示覆盖层。"""

    def destroy_viewport(self) -> None:
        """销毁 secondary viewport。"""
```

### 6.5 launch.py

```python
# launch.py — P5 推荐入口
def main():
    # 步骤 1-5: 与 main.py 完全相同的 wiring
    pm = pymem.Pymem("MonsterHunterWorld.exe")
    base = ...
    memory_reader = MemoryReader(pm, base)
    state_tracker = CombatStateTracker(is_recording=True)
    predictor = ActionPredictor("models/fatalis_ai_model.pkl")
    action_buffer = deque(100)
    action_lock = Lock()
    recorder = CombatRecorder(mr, st, buf, lock)
    recorder.start()

    # 步骤 6: P5 新增——创建应用层
    config = AppConfig.load()
    controller = AppController(state_tracker, recorder, predictor, memory_reader, config)

    # 步骤 7: 启动 Dashboard（阻塞——DPG event loop on main thread）
    dashboard = Dashboard(controller)
    dashboard.run()

if __name__ == "__main__":
    main()
```

---

## 7. 测试策略

### 7.1 新增测试文件

| 文件 | 测试数 | 覆盖 |
|------|:--:|------|
| `tests/test_app_config.py` | ~8 | JSON 序列化/反序列化、默认值降级、写入权限错误 |
| `tests/test_app_controller.py` | ~15 | 状态查询、录制开关、训练启动/取消、shutdown 调用 |
| `tests/test_dashboard.py` | ~20 | mock DPG + mock controller: Tab 创建、按钮绑定、状态刷新、日志轮询 |

### 7.2 扩展测试文件

| 文件 | 新增 | 覆盖 |
|------|:--:|------|
| `tests/test_overlay.py` | +5 | `create_viewport()` mock DPG、`hide_viewport()`/`show_viewport()`、`run()` 后向兼容 |

### 7.3 测试约束

- Dashboard 测试: **不启动真实 DPG 窗口**——mock `dpg` 模块（与现有 `test_overlay.py` 一致）
- AppController 测试: mock Recorder / StateTracker / Predictor（与现有 `test_main_integration.py` 一致）
- AppConfig 测试: 真实 JSON I/O（使用 `tmp_path`）

### 7.4 回归保护

运行 `python -m pytest -q` → 原有 385 tests 必须全部通过（重构不破坏现有测试）。

---

## 8. 实施步骤

| 步骤 | 内容 | 文件 | 验证 |
|:--:|------|------|------|
| **P5.1** | `AppConfig` 模块 | `src/app/config.py` + `src/app/__init__.py` | `pytest tests/test_app_config.py` |
| **P5.2** | logging QueueHandler 扩展 | `src/logging_config.py` | 验证日志文件 + queue 双输出 |
| **P5.3** | `AppController` 模块 | `src/app/controller.py` | `pytest tests/test_app_controller.py` |
| **P5.4** | OverlayUI 重构: add `create_viewport()` / `hide` / `show`; keep `run()` | `src/ui/overlay.py` | `pytest tests/test_overlay.py` → 41+5 tests |
| **P5.5** | DPG 双 viewport 原型验证 | 临时脚本 | 验证 primary + secondary viewports 共存 |
| **P5.6** | Dashboard: StatusBar + LogView | `src/dashboard/` + `__init__` | `pytest tests/test_dashboard.py` |
| **P5.7** | Dashboard: TrainingPanel | `src/dashboard/training_panel.py` | 同上 |
| **P5.8** | Dashboard: 控制台 Tab (overlay start/stop, recording toggle) | `src/dashboard/main_window.py` | 同上 |
| **P5.9** | `launch.py` composition root | `launch.py` | `pytest` full suite → ~430 tests |
| **P5.10** | 全量回归 + 文档更新 | — | 385 original + ~45 new = ~430 tests all green |
| **P5.11** | Review + Commit + Tag v0.6.0 | — | — |

---

## 9. 风险与缓解

| ID | 风险 | 缓解 |
|----|------|------|
| R1 | OverlayUI 重构破坏 P4.5 测试 | `run()` 保留为向后兼容; `create_viewport()` 是纯新方法; 先写扩展测试再重构 |
| R2 | DPG 双 viewport 共存不可行 | P5.5 原型验证—若失败回退: Overlay 仍为独立 DPG window（不是 viewport），Dashboard 通过子进程启动 |
| R3 | 训练子进程 stdout 编码问题 | `subprocess.Popen(..., encoding='utf-8', errors='replace')` |
| R4 | Dashboard DPG event loop 性能 | DPG immediate mode 渲染开销极低。Overlay 每帧 ~2 次 DPG 调用。基准测试: 目标 ≥60fps with both windows |
| R5 | `launch.py` 与 `main.py` 共享 wiring 代码重复 | 考虑提取 `_build_modules(pm, base)` 工厂函数——但避免过早抽象。两个文件各自 ~85 行，差异仅在最后 5 行 |
