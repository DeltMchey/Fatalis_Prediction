---
title: Module Design
tags:
  - architecture
  - modules
  - src
  - design
created: 2026-08-04
updated: 2026-09-16
---

# Module Design — BlackDragon v1.2

> 本文档描述 `src/` 下所有模块的职责、关键 API 与测试映射。基于当前源码（v1.2.0，含 ADR-P6.1 新增模块）。

## 1. src/ 目录树

```
src/
├── __init__.py
├── logging_config.py          # 统一日志（setup_logging + QueueHandler）
│
├── core/                      # P4 — 纯逻辑核心
│   ├── state_tracker.py       #   CombatStateTracker（战斗状态 FSM）
│   ├── memory_reader.py       #   MemoryReader（pymem 内存读取）
│   └── backup_chain.py        #   promote_with_backup（v1.2.0：原子提升 + 两代备份链 + same-sha 跳过）
│
├── model/                     # P4 — AI 模型
│   ├── predictor.py           #   ActionPredictor（加载 + 推理；对外契约未变）
│   ├── dataset.py             #   v1.2.0：load_ml_dataset + 分层切分（实验/生产共享）
│   ├── features.py            #   v1.2.0：FeatureBuilder（6 输入 → 12 列派生，fit/transform 防泄漏）
│   ├── label_decode.py        #   v1.2.0：LabelDecodedEstimator（XGBClassifier 包装，classes_ 即原始招式 ID）
│   ├── production_backend.py  #   v1.2.0：--pipeline 训练后端（Run B 配置确定性重训 + 守门 + 日志）
│   └── mlp_learner.py         #   v1.2.0：AutoML 实验 MLP learner（pickle 导出契约，随应用分发）
│
├── data/                      # P4 — 数据采集
│   └── recorder.py            #   CombatRecorder（CSV 录制 daemon）
│
├── ui/                        # P4.5 + P5.1 — UI
│   ├── overlay.py             #   OverlayUI（透明覆盖层，独立进程；含 --selftest 自检）
│   └── fonts.py               #   setup_cjk_font（共享中文字体）
│
├── app/                       # P5 — 应用协调
│   ├── config.py              #   AppConfig（JSON 持久化）+ resolve_runtime_path（v1.2.0：frozen 路径解析）
│   ├── controller.py          #   AppController（生命周期协调；训练输出 tee 到日志）
│   └── game_service.py        #   GameService（后台游戏检测）
│
├── dashboard/                 # P5 — 控制中心 UI
│   ├── main_window.py         #   Dashboard（主窗口 + Tabs）
│   ├── status_bar.py          #   StatusBar（状态指示灯）
│   ├── log_view.py            #   LogView（实时日志）
│   └── training_panel.py      #   TrainingPanel（训练控制）
│
├── bootstrap/                 # P5.1 — 启动检查
│   └── checker.py             #   DependencyChecker（环境检查）
│
└── config/                    # P2 — 唯一数据源
    ├── actions.py             #   ACTION_DB / ACTION_MAPPING / 分类集合
    └── offsets.py             #   GameOffsets（内存偏移量）
```

**`scripts/`（v1.2.0 新增，工具与打包）**：

```
scripts/
├── train_automl.py            # FLAML AutoML 实验 CLI（--n-jobs 注入点；仅实验，flaml 不进生产依赖）
├── export_model.py            # AutoML 候选零 flaml 导出（提取路径）
├── adopt_model.py             # 候选 → 生产显式采纳（门槛校验 → .bak 轮换 → 拷贝 → 加载复核 → sidecar）
├── benchmark_model.py         # 四指标 benchmark（top1 / top3_raw / top3_filtered / macro_top3）
└── build_exe.ps1              # 双 EXE 构建（7 步；第 2 步全量 pytest + 第 7 步双 EXE --selftest 硬门禁）
```

## 2. 模块职责卡片

### 2.1 `src/core/state_tracker.py` — CombatStateTracker

**职责**：纯战斗状态管理。从原始内存数据计算派生状态（phase / enrage / posture / nova），替代原 `shared_state` dict。

**关键 API**：

| 方法 | 签名 | 说明 |
|------|------|------|
| `calc_distance_2d` | `(p_coords, m_coords) -> float` | XZ 平面距离 |
| `calc_relative_angle` | `(p_coords, m_coords, m_quat) -> float` | 相对角度 [-180,180] |
| `map_action` | `(raw_action: int) -> int` | 动画帧 ID → Base ID |
| `update_phase` | `(hp_percent) -> None` | HP% → P1/P2/P3 |
| `update_enrage` | `(enrage_timer, enrage_max) -> None` | 发怒状态 |
| `update_posture` | `(action) -> int \| None` | 姿态 FSM 切换 |
| `update_nova` | `(hp_percent, action) -> bool` | Nova 阈值预警 |
| `reset_for_zone_change` | `() -> None` | 离开虚黑城时重置 |

**零依赖**：仅 `math` + `src.config.actions`。

### 2.2 `src/core/memory_reader.py` — MemoryReader

**职责**：所有 pymem 进程内存读取的唯一入口。无业务逻辑，返回原始数据。

**关键 API**：

| 方法 | 签名 | 说明 |
|------|------|------|
| `follow_pointer_chain` | `(address, offsets) -> int` | 多级指针解引用 |
| `check_zone` | `() -> int \| None` | 区域 ID（无 417 判断） |
| `find_monster` | `() -> int \| None` | 遍历 10 槽位找黑龙 |
| `read_player_coords` | `() -> list[float] \| None` | 玩家坐标 |
| `read_monster_coords` | `(monster_ptr) -> list[float] \| None` | 怪物坐标 |
| `read_monster_quat` | `(monster_ptr) -> list[float] \| None` | 怪物四元数 |
| `read_monster_hp` | `(monster_ptr) -> float \| None` | HP 百分比 |
| `read_monster_action` | `(monster_ptr) -> int \| None` | 动作 ID |
| `read_enrage_state` | `(monster_ptr) -> tuple[float, float]` | 发怒计时器/上限 |

**依赖**：`pymem` + `src.config.offsets`。

### 2.3 `src/model/predictor.py` — ActionPredictor

**职责**：模型加载 + 推理管线。加载失败 → `_model = None` → `predict()` 返回 `[]`。

**关键 API**：

| 方法 | 签名 | 说明 |
|------|------|------|
| `predict` | `(distance, relative_angle, posture, previous_action, phase, is_enraged) -> list[tuple[int, float]]` | 6 特征推理 |
| `filter_probs_by_phase` | static | 阶段过滤 |
| `filter_probs_by_posture` | static | 姿态过滤 |
| `renormalize_probs` | static | 重归一化 |
| `select_top_k` | static | Top-3 提取（threshold=0.03） |

**属性**：`is_loaded: bool`。v1.2.0：加载失败记 `logger.error`（含 traceback），Overlay 显示橙色"⚠ AI 模型未加载"提示；模型为 XGBoost Pipeline 时 `predict_proba` 由 Pipeline 内 FeatureBuilder 自动扩展 12 列，对外 6 特征签名不变。

### 2.4 `src/data/recorder.py` — CombatRecorder

**职责**：daemon 线程 CSV 录制。0.1s 帧间隔，zone=417 门控。

**关键 API**：`start()` / `stop()` / `run()`（线程 target）

**CSV 列**：`timestamp, hp_percent, phase, is_enraged, distance, relative_angle, posture, action_id`

### 2.5 `src/ui/overlay.py` — OverlayUI

**职责**：透明覆盖层界面（P4.5 standalone 设计）。运行在**独立进程**主线程。

**关键 API**：

| 方法 | 说明 |
|------|------|
| `__init__(memory_reader, state_tracker, predictor, action_buffer, action_lock)` | 只存注入依赖 |
| `run()` | DPG event loop（阻塞，唯一入口） |
| `_compute_frame()` | 纯逻辑，0 DPG 调用 |
| `_apply_display(display)` | DPG 更新层 |

**Win32 透明**：`WS_EX_LAYERED \| WS_EX_TRANSPARENT`，420×350 右上角。

### 2.6 `src/ui/fonts.py` — setup_cjk_font

**职责**：共享中文字体加载（Dashboard 与 Overlay 均调用）。`msyh.ttc` 优先，跨平台回退。找不到字体 → warning 不阻塞。

### 2.7 `src/app/config.py` — AppConfig

**职责**：JSON 配置持久化。缺失/损坏 → 默认值降级。

**字段**（P5.3 auto-start 后）：

| 字段 | 默认值 | 说明 |
|------|--------|------|
| `model_path` | `models/fatalis_ai_model.pkl` | AI 模型 |
| `data_dir` | `data` | CSV 输出 |
| `auto_record` | `True` | 默认录制（ADR-P5.3） |
| `auto_start_overlay` | `True` | 默认自动启动 Overlay（ADR-P5.3） |
| `overlay_opacity` | `1.0` | 覆盖层透明度 |
| `overlay_script` | `overlay.py` | 覆盖层脚本 |
| `prediction_interval` | `0.5` | 预测节流 |
| `training_script` | `train_lgbm.py` | 训练脚本 |
| `dataset_path` | `data/ML_Ready_Dataset.csv` | 训练集 |

### 2.8 `src/app/controller.py` — AppController

**职责**：应用生命周期协调器。Dashboard 通过它间接控制底层模块。

**关键 API**：

| 方法 | 说明 |
|------|------|
| `attach_game(pm, base) -> bool` | 游戏附着 → 创建 P4 模块 + 启动 Recorder |
| `detach_game()` | 游戏分离 → 停止 Recorder |
| `start_overlay() -> bool` | 启动 `overlay.py` 子进程（P5.3） |
| `stop_overlay() -> bool` | 终止 Overlay 子进程 |
| `toggle_recording() -> bool` | 切换录制 |
| `set_recording(enabled)` | 设置录制 |
| `start_training() / cancel_training()` | 训练子进程管理 |
| `get_training_output()` | 训练输出轮询 |
| `shutdown()` | 优雅退出（Recorder → Overlay → Training） |

**属性**：`is_game_attached`, `is_game_connected`, `is_recording`, `is_model_loaded`, `is_overlay_running`, `is_training`, `data_dir`。

### 2.9 `src/app/game_service.py` — GameService

**职责**：后台游戏检测 daemon 线程。2s 轮询 `MonsterHunterWorld.exe`，游戏出现 → `attach_game`，连续 3 次失败 → `detach_game`。

### 2.10 `src/dashboard/` — Dashboard UI 组件

| 类 | 文件 | 职责 |
|----|------|------|
| `Dashboard` | main_window.py | 主窗口（控制台/训练/日志 Tabs + 状态栏），DPG event loop |
| `StatusBar` | status_bar.py | 游戏/模型/录制/覆盖层 指示灯 |
| `LogView` | log_view.py | 消费全局日志队列实时显示 |
| `TrainingPanel` | training_panel.py | 训练子进程控制 + 输出显示 |

### 2.11 `src/bootstrap/checker.py` — DependencyChecker

**职责**：启动环境检查（Python ≥3.11 + requirements 比对 + 可选 pip 安装）。零第三方依赖（bootstrap 在 pip install 前运行）。

### 2.12 `src/config/` — 唯一数据源

| 文件 | 内容 |
|------|------|
| `actions.py` | `ACTION_DB`（144 招式名）、`ACTION_MAPPING`（54 合并映射）、`P1_ONLY_IDS`/`P2_PLUS_IDS`/`P3_ONLY_IDS`、`POSTURE_STAND/PRONE/FLY`、`NOVA_THRESHOLDS`、`DOWN_IDS`/`SCRIPTED_IDS`/`MINOR_AND_PASSIVE` |
| `offsets.py` | `GameOffsets` frozen dataclass（23 字段）+ `OFFSETS` 单例 |

### 2.13 v1.2.0 新增模块（ADR-P6.1 AutoML 迁移）

| 模块 | 职责 |
|------|------|
| `src/model/dataset.py` | `load_ml_dataset`（数据集加载，实验/生产共享）+ 分层切分（random_state=42） |
| `src/model/features.py` | `FeatureBuilder`：sklearn transformer，6 输入 → 12 列派生（fit 仅 train_80 防泄漏）；随应用分发（pickle 契约 + hiddenimports） |
| `src/model/label_decode.py` | `LabelDecodedEstimator`：包装 XGBClassifier，`classes_`/`predict_proba` 直接输出原始招式 ID |
| `src/model/production_backend.py` | `--pipeline` 训练后端：Run B 配置确定性重训（auto_augment/shuffle 镜像）→ Pipeline 组装 → .tmp 原子提升；数据摘要行 + 破坏性守门告警 + sidecar |
| `src/model/mlp_learner.py` | AutoML 实验 MLP learner（BalancedMLPClassifier + FLAML wrapper）；属导出契约，随应用分发 |
| `src/core/backup_chain.py` | `promote_with_backup(tmp, target, generations=2)`：原子提升 + `.bak`/`.bak2` 链 + same-sha 跳过；模型与数据集两侧共用；正式 `sha256_file` 实现所在地 |
| `scripts/train_automl.py` | FLAML AutoML 实验 CLI（`--n-jobs` 线程注入点；flaml 仅实验依赖） |
| `scripts/export_model.py` | 候选模型零 flaml 导出（提取路径，重训复现 + 独立导出物） |
| `scripts/adopt_model.py` | 候选 → 生产显式采纳（门槛校验 → .bak 轮换 → 拷贝 → ActionPredictor 加载复核 → sidecar） |
| `scripts/benchmark_model.py` | 四指标 benchmark：top1 / top3_raw / top3_filtered / macro_top3（+辅助口径、时延、RSS） |
| `scripts/build_exe.ps1` | 构建 7 步：pytest 全量门禁 → 双 EXE → surface（数据集/19 CSV/模型/factory_model 缺失即失败）→ 双 EXE `--selftest` 硬门禁 |

## 3. 模块依赖图（DAG）

```mermaid
graph LR
    CFG[src/config] --> CORE[src/core]
    CORE --> MODEL[src/model]
    CORE --> DATA[src/data]
    CORE --> UI[src/ui]
    CFG --> UI
    APP[src/app] --> CORE
    APP --> MODEL
    APP --> DATA
    APP --> CFG
    DASH[src/dashboard] --> APP
    DASH --> UI
    BOOT[src/bootstrap] -.->|启动时检查| CFG
    SCRIPTS[scripts/] --> MODEL
    SCRIPTS --> CORE
```

> v1.2.0 约束：`src/model/production_backend.py` 正式代码零 `experiments/` 运行时依赖；`scripts/train_automl.py`（flaml）只在实验侧，生产推理零 flaml 引用。

## 4. 模块 → 测试映射

| 模块 | 测试文件 | 覆盖点 |
|------|----------|------|
| `src/config/actions.py` | test_actions.py | ACTION_DB, ACTION_MAPPING, phase/posture sets |
| `src/config/offsets.py` | test_offsets.py | GameOffsets dataclass, 字段值, 不可变性 |
| — (P3 纯逻辑) | test_math_logic.py | calc_distance_2d / calc_relative_angle / select_top_k |
| — (P3 过滤器) | test_phase_filter.py | filter_probs_by_phase/posture, renormalize |
| — (P3 Nova FSM) | test_nova.py | evaluate_nova |
| — (P3 基础设施) | test_infrastructure.py | fixtures, config, discovery, CI |
| `src/logging_config.py` | test_logging.py | setup_logging, FileHandler |
| `src/ui/fonts.py` | test_fonts.py | setup_cjk_font |
| `src/core/state_tracker.py` | test_state_tracker.py | CombatStateTracker 全方法 |
| `src/core/memory_reader.py` | test_memory_reader.py | MemoryReader 指针链/读取 |
| `src/core/backup_chain.py` | test_backup_chain.py | 原子提升/两代链/same-sha 跳过（v1.2.0） |
| `src/model/predictor.py` | test_predictor.py | ActionPredictor 加载/预测/过滤 |
| `src/model/dataset.py` | test_dataset_split.py | load_ml_dataset/分层切分（v1.2.0） |
| `src/model/features.py` | test_features.py | FeatureBuilder 12 列派生/防泄漏（v1.2.0） |
| `src/model/production_backend.py` | test_production_backend.py | Run B 重训链/守门/sidecar（v1.2.0） |
| `src/data/recorder.py` | test_recorder.py | CombatRecorder 门控/录制/生命周期 |
| `src/ui/overlay.py` | test_overlay.py | OverlayUI 状态/显示/DPG 生命周期 |
| `src/app/config.py` | test_app_config.py | AppConfig 默认值/持久化 |
| `src/app/controller.py` | test_app_controller.py | AppController 生命周期/子进程 |
| `src/app/game_service.py` | test_game_service.py | GameService 检测/附着/分离 |
| `src/bootstrap/checker.py` | test_bootstrap_checker.py | DependencyChecker 检查/安装 |
| `src/dashboard/` | test_dashboard.py | Dashboard UI 组件/回调 |
| — (数据清洗) | test_data_cleaner.py | ETL + 合并语义 |
| — (数据升级) | test_data_upgrade.py | 旧 CSV 回填 |
| — (训练脚本 legacy) | test_train_lgbm.py | LightGBM legacy 路径 |
| — (AutoML 工具链, v1.2.0) | test_train_automl.py / test_automl_metric.py / test_model_export.py / test_adopt_model.py / test_benchmark_model.py | FLAML CLI/指标/导出/采纳/benchmark |
| 根入口 | test_launch.py / test_overlay_entry.py / test_main_integration.py | launch --pipeline/--train 路由、overlay 自检、main 组装 |

**总计：766 passed（v1.2.0 构建门禁基线，36 个测试文件）。**
