# BlackDragon 控制 UI 产品调研

> **目标**: 为 BlackDragon 设计一个类似 HunterPie 的桌面控制面板（Launcher/Dashboard），
> 使非技术用户也能方便使用。调研覆盖现有架构能力、UI 框架选型、新增模块设计和风险分析。

---

## 1. 当前架构分析

### 1.1 现有模块拓扑

```
main.py (composition root, 85 lines)
│
├── ① pymem.Pymem("MonsterHunterWorld.exe")        游戏进程连接
├── ② MemoryReader(pm, base)                       共享 — stateless 内存读取
├── ③ CombatStateTracker()                         共享 — 战斗状态容器
├── ④ ActionPredictor("models/...")                 UI 专用 — AI 推理
├── ⑤ deque(100) + threading.Lock()                 通信通道
├── ⑥ CombatRecorder(mr, st, buf, lock).start()     daemon — CSV 录制
└── ⑦ OverlayUI(mr, st, pred, buf, lock).run()      阻塞 — DPG 透明覆盖层
```

### 1.2 关键线程模型

| 线程 | 运行内容 | 阻塞？ | 生命周期 |
|------|---------|:--:|------|
| Main | `OverlayUI.run()` — DPG event loop | **阻塞** | 进程存活期间 |
| Daemon | `CombatRecorder` — 0.1s 帧循环 | 否 | `start()` → `stop()` 或进程退出 |

**关键约束**: `OverlayUI.run()` 在 main 线程上阻塞运行 DPG event loop。当前 `main()` 在启动 Recorder 后立即进入 `overlay.run()`——在此之前不存在用户交互窗口。

### 1.3 现有数据能力

| 数据                  | 模块                           |    精度    |     实时？      |
| ------------------- | ---------------------------- | :------: | :----------: |
| Monster HP%         | MemoryReader → StateTracker  |   硬件级    |     ✅ 每帧     |
| Monster Phase       | StateTracker.update_phase    | P1/P2/P3 |      ✅       |
| Monster Posture     | StateTracker.update_posture  |  0/1/2   |      ✅       |
| Monster Enrage      | MemoryReader + StateTracker  |   帧精确    |      ✅       |
| Monster Action ID   | MemoryReader → action_buffer |  原始帧 ID  |      ✅       |
| AI Prediction Top-3 | ActionPredictor              | 0.5s 节流  |      ✅       |
| Nova Warning        | StateTracker.update_nova     |   阈值触发   |      ✅       |
| Player Coords       | MemoryReader                 | float×3  |      ✅       |
| Distance/Angle      | StateTracker static          |   派生值    |      ✅       |
| CSV Recording       | CombatRecorder               |  0.1s/行  | ✅ toggleable |

### 1.4 现有模块的可用控制接口

| 模块 | 可控方法 | 说明 |
|------|---------|------|
| CombatRecorder | `start()` / `stop()` | 线程启停 |
| CombatRecorder | `is_running` (property) | 查询状态 |
| CombatStateTracker | `is_recording` (bool) | 暂停/恢复写 CSV |
| CombatStateTracker | `reset_for_zone_change()` | 重置战斗状态 |
| ActionPredictor | `is_loaded` (property) | 模型状态查询 |
| ActionPredictor | `predict(6 features)` | 推理接口 |
| OverlayUI | `run()` | 阻塞启动 |

---

## 2. 需要新增的模块

### 2.1 架构建议

```
main.py (重写)
│
├── ═══ 共享层（不变）═════
├── MemoryReader
├── CombatStateTracker
├── action_buffer + lock
│
├── ═══ 业务层（不变）═════
├── ActionPredictor
├── CombatRecorder
├── OverlayUI (游戏内透明覆盖层)
│
└── ═══ 新增 — 控制面板 ═══
    └── ControlPanel                              ← NEW
        ├── 模型训练 Tab
        ├── 数据控制 Tab
        ├── 实时日志 Tab
        ├── 设置 Tab
        └── 游戏连接状态栏
```

### 2.2 新模块: `src/ui/control_panel.py`

```
ControlPanel
├── 职责
│   ├── 作为应用主窗口（正常窗口，非透明覆盖层）
│   ├── 管理 OverlayUI 的生命周期（启动/关闭）
│   ├── 提供模型训练的 GUI 界面
│   ├── 显示实时日志流
│   └── 管理全局设置
│
├── 依赖注入
│   ├── state_tracker: CombatStateTracker   # 控制 is_recording
│   ├── recorder: CombatRecorder            # 控制 start/stop
│   ├── predictor: ActionPredictor          # 查询模型状态
│   ├── memory_reader: MemoryReader?        # 检测游戏连接（可选）
│   └── config: dict                        # 用户设置
│
├── 新增依赖（内部）
│   ├── train_lgbm 模块调用（子进程或线程）
│   ├── 日志缓冲区（QueueHandler）
│   └── 设置持久化（JSON 文件）
│
└── DPG 结构
    ├── dpg.create_viewport("BlackDragon", ...)  # 主窗口
    ├── Tab Bar: [控制台 | 训练 | 数据 | 日志 | 设置]
    └── Status Bar: 游戏连接 / 模型 / 录制 状态
```

### 2.3 新模块: `src/config/settings.py`

```python
# 用户配置持久化（JSON）
class AppSettings:
    model_path: str = "models/fatalis_ai_model.pkl"
    data_path: str = "data/ML_Ready_Dataset.csv"
    auto_start_overlay: bool = False
    auto_start_recording: bool = False
    overlay_opacity: float = 1.0
    prediction_interval: float = 0.5
```

### 2.4 新模块: `src/logging_config.py` 扩展

当前 `setup_logging()` 写入 `blackdragon.log` 文件。需要添加 **QueueHandler** 将日志同时路由到 GUI 的日志面板：

```
日志流:
  FileHandler(blackdragon.log) ←─┐
                                   ├── Logger("BlackDragon")
  QueueHandler(queue) ←──────────┘
      │
      └── ControlPanel 轮询 queue → DPG text widget
```

### 2.5 修改: `main.py`

`main()` 不再直接调用 `overlay.run()`。改为：

```
main()
├── 启动 ControlPanel (DPG 主窗口，在主线程运行 event loop)
│   ├── 用户点击 "Start Overlay" → 启动 OverlayUI
│   ├── 用户点击 "Start Recording" → is_recording = True
│   └── 用户关闭窗口 → 优雅退出
└── (OverlayUI 运行在同一个 DPG context 的 secondary viewport)
```

---

## 3. UI 框架选择建议

### 3.1 现有选择: DearPyGUI（已集成，推荐）

| 维度 | 评估 |
|------|------|
| **熟悉度** | ✅ 项目已深度使用 DPG（OverlayUI 289 行） |
| **零新增依赖** | ✅ 已在 requirements.txt 中 |
| **多窗口支持** | ✅ DPG 2.x 支持 primary + secondary viewports |
| **Tab 控件** | ✅ `dpg.add_tab_bar()` / `dpg.add_tab()` |
| **表格** | ✅ `dpg.add_table()` |
| **实时文本** | ✅ `dpg.add_text()` / `dpg.set_value()` |
| **进度条** | ✅ `dpg.add_progress_bar()` |
| **输入/按钮** | ✅ `dpg.add_input_text()` / `dpg.add_button()` |
| **主题** | ✅ `dpg.add_theme()` |
| **文件对话框** | ✅ `dpg.add_file_dialog()` |
| **线程安全** | ⚠️ DPG 调用必须在主线程（已有经验） |
| **打包分发** | ⚠️ 需额外工具（PyInstaller） |

**结论: 保持 DearPyGUI**，理由充分：
- 零学习曲线（团队已掌握）
- 零新增依赖（ship 给用户时更轻量）
- 可在同一进程中同时运行 ControlPanel（主窗口）和 Overlay（透明覆盖层）

### 3.2 备选方案（不推荐）

| 方案 | 优点 | 缺点 |
|------|------|------|
| **PyQt/PySide** | 成熟、文档丰富、打包成熟 | 新增 50MB+ 依赖、学习曲线；与 DPG 共存需要两个 event loop（复杂） |
| **Tkinter** | 标准库、零依赖 | 外观过时、不支持透明窗口、Tab 控件不原生 |
| **Electron + Python backend** | 现代化 UI | 极度复杂、臃肿、不适合游戏 overlay 场景 |
| **Web UI (Flask + browser)** | 跨平台、响应式 | 需要浏览器、不适合游戏内 overlay、延迟高 |

### 3.3 DPG 双窗口架构

```
同一进程，同一 DPG context，两个 viewports:

Primary Viewport (主窗口 — ControlPanel)
├── title: "BlackDragon Control Panel"
├── width: 800, height: 600
├── decorated: True (正常窗口)
└── Tab Bar → [训练|数据|日志|设置]

Secondary Viewport (覆盖层 — OverlayUI)
├── title: "overlay"
├── width: 420, height: 350
├── decorated: False
├── always_on_top: True
├── clear_color: [0,0,0,0]
└── Win32 透明窗口 (ctypes.windll)

生命周期:
  ControlPanel 创建 primary viewport
  → 用户点击 "Start" → OverlayUI 创建 secondary viewport
  → 用户关闭 secondary → OverlayUI 隐藏（不退出进程）
  → 用户关闭 primary → 优雅退出所有
```

**关键优势**: 共享同一个 DPG event loop → 无多线程 DPG 调用冲突；ControlPanel 可以原子地控制 Overlay 的 viewport 生命周期。

---

## 4. 与现有模块的接口关系

### 4.1 ControlPanel → CombatRecorder

| 操作 | 调用 | 说明 |
|------|------|------|
| 启动录制 | `state_tracker.is_recording = True` | 已有接口，零改动 |
| 暂停录制 | `state_tracker.is_recording = False` | Recorder 内部检查该标志 |
| 停止线程 | `recorder.stop()` | 线程退出 |
| 查询状态 | `state_tracker.is_recording` / `recorder.is_running` | UI 更新状态灯 |
| 查看 CSV 文件 | `glob("data/fatalis_combat_data_*.csv")` | 显示文件列表 + 大小 |

### 4.2 ControlPanel → ActionPredictor

| 操作 | 调用 | 说明 |
|------|------|------|
| 查询模型状态 | `predictor.is_loaded` | 显示 ✅/❌ |
| 模型路径 | 由 `AppSettings.model_path` 提供 | 用户可在 Setting Tab 修改 |

### 4.3 ControlPanel → OverlayUI

这是最大的接口变更：

| 当前 | 需要修改为 |
|------|-----------|
| `OverlayUI.run()` 阻塞 main 线程 | `OverlayUI` 不调用 `run()`——改为 `create_viewport()` + 由 ControlPanel 的 event loop 驱动 |
| `__init__` 调用 `_setup_dpg()` | 拆分为 `__init__`(注入) + `create_viewport()`(创建 secondary viewport) |
| DPG context 由 OverlayUI 独有 | 两个模块共享 DPG context（by design — DPG 是进程级单例） |

**OverlayUI 接口变更（建议）**:

```python
class OverlayUI:
    def __init__(self, mr, st, pred, buf, lock):  # 同现在
        ...  # 只存依赖，不创建 DPG

    def create_viewport(self) -> None:
        """创建 secondary viewport + widgets, 但不启动 event loop"""
        # 原来 _setup_dpg() 的内容

    def hide_viewport(self) -> None:
        """隐藏覆盖层（不销毁）"""
        ...

    def show_viewport(self) -> None:
        """重新显示覆盖层"""
        ...

    # update_logic() / _compute_frame() / _apply_display() 不变
```

### 4.4 ControlPanel → train_lgbm

当前 `train_lgbm.py` 是一个独立脚本（88 行），使用 `print()` 输出进度。GUI 集成方案：

| 方案 | 复杂度 | 推荐？ |
|------|:--:|:--:|
| **子进程运行** `python train_lgbm.py` | 中 | ✅ 推荐——隔离训练进程、不阻塞 DPG event loop、stdout 可捕获为日志流 |
| 线程内直接调用 `train_fatalis_ai()` | 低 | ⚠️ LightGBM 训练使用 `n_jobs=-1`（全部 CPU 核）——但线程可工作；需要 monkeypatch `print` 捕获输出 |
| 重写为可注入 logger 的函数 | 中 | ❌ 额外重构工作量——train_lgbm 已有测试，不宜大改 |

**建议**: 子进程方案——`subprocess.Popen(["python", "train_lgbm.py"])`，实时读取 stdout 并转发到 GUI 日志面板。LightGBM 训练可能耗时 5-30 秒（取决于数据集大小），子进程中运行不冻结 UI。

### 4.5 ControlPanel → 日志系统

扩展 `logging_config.py`，添加 `QueueHandler`:

```python
import logging.handlers
_log_queue = queue.Queue()
queue_handler = logging.handlers.QueueHandler(_log_queue)
logging.getLogger("BlackDragon").addHandler(queue_handler)
```

ControlPanel 的日志 Tab 每 0.5s 轮询 `_log_queue`，将新记录追加到 `dpg.add_text()` 或滚动文本框。

### 4.6 完整依赖注入图

```
ControlPanel(
    state_tracker,        # → Tab: 录制状态、重置
    recorder,             # → Tab: 启动/停止录制
    predictor,            # → Tab: 模型状态显示
    memory_reader?,       # → 状态栏: 游戏连接检测
    settings: AppSettings, # → Tab: 设置读写
    log_queue: Queue,     # → Tab: 实时日志
)
```

---

## 5. 潜在风险

### Risk Table

| ID | 风险 | 概率 | 影响 | 级别 | 缓解 |
|----|------|:--:|:--:|:--:|------|
| **R1** | DPG 双 viewport 共享 context 冲突 | M | H | **High** | DPG 2.x 原生支持多 viewport。在原型阶段创建最小双窗口测试验证。若不可行，回退方案：ControlPanel 用标准 DPG window（非 viewport），Overlay 保持独立 viewport |
| **R2** | `OverlayUI.run()` 阻塞→改为非阻塞架构 | M | H | **High** | 当前 `run()` 内 `while dpg.is_dearpygui_running()` 独占 event loop。重构为 `create_viewport()` + 由 ControlPanel event loop 驱动。核心逻辑（`_compute_frame` / `_apply_display`）不变 |
| **R3** | 训练线程与 DPG UI 线程通信 | M | M | **Medium** | 子进程方案：读 stdout 不涉及跨线程 DPG 调用。若改为线程方案：训练进度通过 `queue.Queue` 传递到主线程后再更新 DPG |
| **R4** | 日志 QueueHandler 内存增长 | L | M | **Medium** | 日志面板设置上限（如最近 1000 行），超出后丢弃旧记录 |
| **R5** | 用户同时运行旧 `python ai_engine.py` + 新 `python main.py` | L | L | **Low** | 文档说明。两个进程各自独立连接游戏 → 双份内存读取 + 双份 CSV。但无数据破坏风险 |
| **R6** | DPG 性能——ControlPanel + Overlay 双窗口导致帧率下降 | L | M | **Medium** | DPG 是 immediate mode，渲染开销低。Overlay 每帧约 200 字符文本 + 颜色配置；ControlPanel 主要在用户交互时更新。基准测试验证 |
| **R7** | 设置文件（settings.json）格式兼容性 | L | L | **Low** | 使用版本号 + try/except 降级到默认值 |
| **R8** | OverlayUI 重构导致 P4.5 测试回归 | M | H | **High** | 重构仅拆分 `_setup_dpg()` 和 `run()`；`_compute_frame` / `_apply_display` / `update_logic` 逻辑零改动。先写测试再重构 |

---

## 6. MVP 建议

### v0.6.0 — Control Panel MVP

**优先级 P0（第一版）**:

| 功能 | Tab | 复杂度 | 理由 |
|------|:--:|:--:|------|
| 游戏连接状态指示 | Status Bar | 低 | `pymem.Pymem` 是否成功→🟢/🔴 |
| 模型加载状态 | Status Bar | 低 | `predictor.is_loaded`→🟢/🔴 |
| 录制开关 + 状态 | 控制台 Tab | 低 | `state_tracker.is_recording` toggle |
| CSV 文件列表 | 控制台 Tab | 低 | `glob("data/*.csv")` 显示文件名+大小 |
| 实时日志面板 | 日志 Tab | 中 | QueueHandler + DPG text |
| Overlay 启动/关闭 | 控制台 Tab | 高 | 重构 OverlayUI 为非阻塞 |
| 设置持久化 | 设置 Tab | 低 | JSON 读写 |

**优先级 P1（第二版）**:

| 功能 | Tab | 复杂度 |
|------|:--:|:--:|
| 模型训练启动 + 进度 | 训练 Tab | 中 — subprocess + stdout |
| 训练日志实时显示 | 训练 Tab | 中 |
| 模型元数据显示（训练日期、样本数） | 训练 Tab | 低 |
| 主题/字体设置 | 设置 Tab | 低 |
| Overlay 透明度设置 | 设置 Tab | 低 |

**优先级 P2（后续）**:

| 功能 | 说明 |
|------|------|
| 训练数据集预览 | 表格显示 ML_Ready_Dataset.csv |
| 模型版本管理 | 多模型文件选择/对比 |
| 自动更新检测 | GitHub Release polling |
| DPS/战斗统计 | 需要新增内存偏移（玩家伤害结构体） |

---

## 7. 实施路径建议

| 阶段 | 步骤 | 预估 |
|:--:|------|:--:|
| **P5.1** | DPG 双 viewport 原型验证（最小测试——两个 viewport 共存） | 0.5d |
| **P5.2** | 日志 QueueHandler 扩展 `logging_config.py` | 0.5d |
| **P5.3** | `AppSettings` 模块 + JSON 持久化 | 0.5d |
| **P5.4** | OverlayUI 重构（拆 `run()` → `create_viewport()`）| 1d |
| **P5.5** | ControlPanel 基础框架（window + tab bar + status bar） | 1d |
| **P5.6** | 控制台 Tab（录制开关、CSV 列表、Overlay 启停） | 1d |
| **P5.7** | 日志 Tab（QueueHandler → DPG text 实时显示）| 0.5d |
| **P5.8** | 重写 `main.py`（ControlPanel 作为主入口）| 0.5d |
| **P5.9** | 测试 + 回调验证 | 1d |
| **P5.10** | 训练 Tab（P1）| 1-2d |

---

## 8. 总结

### 建议

1. **保持 DearPyGUI**——已集成、零新依赖、团队掌握、支持双窗口。
2. **ControlPanel 作为主窗口**——DPG primary viewport 承载控制面板，DPG secondary viewport 承载游戏内 Overlay。
3. **OverlayUI 重构**——`run()` 拆分，使 ControlPanel 可通过按钮控制 Overlay 的创建/隐藏/销毁。
4. **训练用子进程**——隔离稳定性风险，不阻塞 UI。
5. **日志用 QueueHandler**——最小侵入性扩展现有 `logging_config.py`。

### 关键决策待确认

| # | 决策 | 选项 |
|---|------|------|
| D1 | DPG 双 viewport 验证（原型） | 通过 / 回退到双 DPG window（同 viewport） |
| D2 | OverlayUI 重构范围 | 仅拆 `run()` / 同时改 `_setup_dpg()` |
| D3 | 模型训练方案 | 子进程 / 线程 / 保持独立 CLI（不集成到 GUI） |
| D4 | 设置持久化格式 | JSON / TOML / INI |
