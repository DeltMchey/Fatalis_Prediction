# BlackDragon (黑龙) — 项目说明书

---

## ⚠️ 免责声明

**BlackDragon 是一个作弊类型的游戏外挂程序。**

1. **仅供研究与学习**：本项目仅供技术研究、机器学习应用、逆向工程教育用途，严禁用于任何违反游戏服务条款的行为。

2. **开发者免责**：本项目作者及贡献者**不对使用者的任何行为承担法律责任**。使用者自行承担所有风险，包括但不限于账号封禁、数据丢失、法律纠纷。

3. **不鼓励作弊**：作者不鼓励在任何在线/多人游戏环境中使用本工具。请在离线/单人模式下使用，并尊重其他玩家的游戏体验。

4. **无担保**：本软件按"原样"提供，不提供任何形式的明示或暗示担保，包括但不限于适销性、特定用途适用性的担保。

**使用本软件即表示您已阅读、理解并同意承担全部责任。如果您不同意以上条款，请勿使用本软件。**

---

## 1. 项目概述

BlackDragon（黑龙）是一个基于**内存读取 + 机器学习**的《怪物猎人世界》（Monster Hunter World）AI 辅助狩猎工具，专为终局 Boss **黑龙（Fatalis）** 设计。

### 核心能力

| 功能 | 描述 |
|------|------|
| **实时预测** | XGBoost 多分类模型（46 个招式类别，v1.2.0 起经 AutoML 迁移自 LightGBM），每 0.5 秒推理一次，显示 Top-3 预测 |
| **透明覆盖层** | DearPyGui 悬浮窗口（420×350），位于屏幕右上角，可穿透鼠标点击 |
| **游戏规则过滤** | 根据战斗阶段/怪物姿态硬过滤不可能招式，保证预测物理可行 |
| **飞天火预警** | 基于 HP 血线阈值的终极技能预警（红色警告） |
| **战斗录制** | 实时 CSV 数据记录（~10 行/秒），累积数据用于模型训练 |
| **控制中心** | Dashboard 图形界面，管理覆盖层、录制、训练和实时日志 |
| **一键训练** | 一键清洗 + 重训（几秒完成，自动合并历史会话 + 备份链保护） |

### 技术指标

| 指标 | 数值 |
|------|------|
| 模型类型 | XGBoost 多分类器（sklearn Pipeline 封装，190 树） |
| 特征维度 | 6 维输入（Pipeline 内扩展 12 列：距离、角度、姿态、上一招、阶段、发怒 + 6 派生） |
| 招式类别 | 46 个 |
| 推理频率 | 0.5 秒/次，p95 4.31ms（单线程） |
| Top-3 命中率 | 66.19%（raw）/ **65.37%**（实战硬过滤口径，留出集） |
| 测试覆盖 | 766 个测试通过 |
| 模型大小 | 7.46 MB（joblib 序列化；旧 LightGBM 为 19.05 MB） |

---

## 2. 模块总览

BlackDragon 采用**双进程架构**（ADR-P5.2）：Dashboard 控制中心与 Overlay 透明覆盖层是两个独立的 Python 进程。

### 2.1 源码目录树（`src/`）

```
src/
├── config/                     # 唯一数据源（P2）
│   ├── actions.py              #   动作数据库（144 招式名/54 合并映射/阶段分类/姿态集合/Nova 阈值）
│   └── offsets.py              #   内存偏移量（23 个 GameOffsets 字段，frozen dataclass）
│
├── core/                       # 纯逻辑核心（P4）
│   ├── state_tracker.py        #   CombatStateTracker — 战斗状态状态机
│   └── memory_reader.py        #   MemoryReader — pymem 内存读取唯一入口
│
├── model/                      # AI 模型（P4）
│   └── predictor.py            #   ActionPredictor — 模型加载 + 推理管线
│
├── data/                       # 数据采集（P4）
│   └── recorder.py             #   CombatRecorder — CSV 录制 daemon 线程
│
├── ui/                         # 界面（P4.5 + P5.1）
│   ├── overlay.py              #   OverlayUI — 透明覆盖层（独立进程运行）
│   └── fonts.py                #   setup_cjk_font — 共享中文字体加载
│
├── app/                        # 应用协调（P5）
│   ├── config.py               #   AppConfig — JSON 配置持久化
│   ├── controller.py           #   AppController — 应用生命周期协调器
│   └── game_service.py         #   GameService — 后台游戏检测 daemon
│
├── dashboard/                  # 控制中心 UI（P5）
│   ├── main_window.py          #   Dashboard — 主窗口 + Tabs
│   ├── status_bar.py           #   StatusBar — 状态指示灯
│   ├── log_view.py             #   LogView — 实时日志显示
│   └── training_panel.py       #   TrainingPanel — 训练控制面板
│
├── bootstrap/                  # 启动检查（P5.1）
│   └── checker.py              #   DependencyChecker — 环境检查 + 依赖安装
│
└── logging_config.py           # 统一日志（setup_logging + QueueHandler）
```

### 2.2 各模块功能详情

#### 2.2.1 `src/config/` — 唯一数据源

| 文件 | 功能 |
|------|------|
| `actions.py` | **动作数据库**：`ACTION_DB`（144 个招式 ID → 中文名如 "龙车"、"连咬"）、`ACTION_MAPPING`（54 条动画帧合并映射，如 38,39,40→37）、`P1_ONLY_IDS` / `P2_PLUS_IDS` / `P3_ONLY_IDS`（阶段专属招式）、`POSTURE_STAND/PRONE/FLY`（姿态触发集合）、`NOVA_THRESHOLDS`（飞天火血线阈值 [0.78, 0.50, 0.41, 0.26, 0.06]）、`DOWN_IDS` / `SCRIPTED_IDS` / `MINOR_AND_PASSIVE`（训练排除集合） |
| `offsets.py` | **内存偏移量**：`GameOffsets` frozen dataclass（23 个字段），包含三大基址（玩家 0x050139A0 / 怪物 0x051238C8 / 区域 0x0500ECA0）、怪物属性偏移（HP/坐标/四元数/动作ID）、发怒结构体（0x1BE30）、玩家坐标链、区域判定（417=虚黑城） |

#### 2.2.2 `src/core/state_tracker.py` — CombatStateTracker

**职责**：纯战斗状态管理。从原始内存数据计算派生状态，替代原 God Class 中的 `shared_state` dict。

| 方法 | 功能 |
|------|------|
| `calc_distance_2d(p_coords, m_coords)` | 计算玩家与怪物 XZ 平面欧几里得距离 |
| `calc_relative_angle(p_coords, m_coords, m_quat)` | 计算怪物朝向到玩家的相对角度 [-180°, 180°] |
| `map_action(raw_action)` | 动画帧 ID → 起手式 Base ID（通过 ACTION_MAPPING） |
| `update_phase(hp_percent)` | HP% → 战斗阶段（>78%=P1, 50-78%=P2, <50%=P3） |
| `update_enrage(timer, max)` | 发怒状态判定（0 < timer < max → 发怒中） |
| `update_posture(action)` | 姿态状态机（0=趴下/1=站立/2=飞行/3=倒地/4=演出） |
| `update_nova(hp_percent, action)` | 飞天火血线预警状态机（跨阈值触发 → 特定动作清除） |
| `reset_for_zone_change()` | 离开虚黑城时彻底重置所有状态 |

**设计约束**：零依赖（仅 `math` + `src.config.actions`），纯逻辑可测试。

#### 2.2.3 `src/core/memory_reader.py` — MemoryReader

**职责**：所有 pymem 进程内存读取的**唯一入口**。返回原始数据，不做语义解释。

| 方法 | 功能 |
|------|------|
| `follow_pointer_chain(address, offsets)` | 多级指针链解引用 |
| `check_zone()` | 读取当前区域 ID |
| `find_monster()` | 遍历 10 个怪物槽位，HP > 500 判定为黑龙 |
| `read_player_coords()` | 读取玩家 XYZ 坐标（3 级指针链） |
| `read_monster_coords(ptr)` | 读取怪物 XYZ 坐标 |
| `read_monster_quat(ptr)` | 读取怪物旋转四元数 [x,y,z,w] |
| `read_monster_hp(ptr)` | 读取怪物 HP 百分比（两级指针：HP Base → Current/Max） |
| `read_monster_action(ptr)` | 读取怪物当前动作 ID（int32） |
| `read_enrage_state(ptr)` | 读取引擎内部发怒秒表 (timer, max) |

#### 2.2.4 `src/model/predictor.py` — ActionPredictor

**职责**：XGBoost Pipeline 模型加载 + **两层预测推理管线**（对外 6 特征契约自 v1.0 未变；Pipeline 内 FeatureBuilder 自动扩展 12 列）。

**推理管线**（每 0.5s 一次）：
```text
6 特征构造 → Pipeline predict_proba（FeatureBuilder 12 列 → XGBoost）
    → Phase Filter（阶段过滤） → Posture Filter（姿态过滤）
    → Renormalize（重归一化） → Top-3 + 3% 概率阈值
```

| 方法 | 功能 |
|------|------|
| `predict(distance, angle, posture, prev_action, phase, enrage)` | 完整推理管线入口 |
| `filter_probs_by_phase(probs, classes, phase)` | 根据阶段将不可能招式概率置零 |
| `filter_probs_by_posture(probs, classes, posture)` | 根据姿态将不可能招式概率置零 |
| `renormalize_probs(probs)` | 概率数组重新归一化（总和=1） |
| `select_top_k(probs, classes, k=3, threshold=0.03)` | 提取 Top-3 预测 |

**核心创新——两层预测**：纯 ML 可能输出物理不可能的预测（如 P1 阶段预测 P3 专属招式）。硬过滤层保证预测的合法性。

#### 2.2.5 `src/data/recorder.py` — CombatRecorder

**职责**：daemon 线程 CSV 战斗数据录制。

| 属性 | 值 |
|------|-----|
| 帧间隔 | 0.1s |
| 触发条件 | `is_recording=True` 且 `zone==417`（虚黑城） |
| CSV 列 | `timestamp, hp_percent, phase, is_enraged, distance, relative_angle, posture, action_id` |
| 文件命名 | `fatalis_combat_data_YYYYMMDD_HHMMSS.csv` |
| 容错 | 单帧异常 → logger.warning → continue（不终止录制） |

#### 2.2.6 `src/ui/overlay.py` — OverlayUI

**职责**：透明覆盖层界面（DPG），运行在**独立进程**主线程。

| 特性 | 描述 |
|------|------|
| 窗口尺寸 | 420×350 |
| 位置 | 屏幕右上角 |
| 透明穿透 | WS_EX_LAYERED \| WS_EX_TRANSPARENT（Win32 API） |
| 显示内容 | 当前动作名、阶段/发怒状态、距离/角度/HP%、飞天火预警（红色）、AI Top-3 预测（绿色） |
| 用户控制 | checkbox 录制开关 |

**分层设计**：`_compute_frame()`（纯逻辑，0 个 DPG 调用）+ `_apply_display()`（DPG 更新层）分离。

#### 2.2.7 `src/app/config.py` — AppConfig

**职责**：JSON 应用配置持久化（dataclass）。缺失/损坏时降级到默认值。

| 字段 | 默认值 | 说明 |
|------|--------|------|
| `model_path` | `models/fatalis_ai_model.pkl` | AI 模型路径 |
| `data_dir` | `data` | CSV 录制输出目录 |
| `auto_record` | `True` | 默认开启录制 |
| `auto_start_overlay` | `True` | 默认自动启动覆盖层子进程 |
| `prediction_interval` | `0.5` | AI 预测节流（秒） |

#### 2.2.8 `src/app/controller.py` — AppController

**职责**：应用生命周期协调器。Dashboard 通过它与底层模块交互。

| 方法 | 功能 |
|------|------|
| `attach_game(pm, base)` | 游戏连接后初始化全部 P4 模块 + 启动 Recorder |
| `detach_game()` | 游戏退出后清理 P4 模块 |
| `start_overlay()` / `stop_overlay()` | 启动/终止 Overlay 子进程 |
| `toggle_recording()` / `set_recording(enabled)` | 录制开关控制 |
| `start_training()` / `cancel_training()` | 训练子进程管理 |
| `shutdown()` | 优雅退出（Recorder → Overlay → Training） |

#### 2.2.9 `src/app/game_service.py` — GameService

**职责**：后台游戏检测 daemon 线程。每 2 秒轮询 `MonsterHunterWorld.exe`：
- 游戏出现 → `attach_game()`（初始化 P4 模块）
- 连续 3 次健康检查失败 → `detach_game()`（清理模块）

#### 2.2.10 `src/dashboard/` — Dashboard UI 组件

| 组件 | 文件 | 功能 |
|------|------|------|
| `Dashboard` | main_window.py | 主窗口（控制台/训练/日志三个 Tab），DPG event loop |
| `StatusBar` | status_bar.py | 游戏连接/模型加载/录制/覆盖层 四色状态指示灯 |
| `LogView` | log_view.py | 消费全局日志队列，实时滚动显示 |
| `TrainingPanel` | training_panel.py | 训练子进程控制按钮 + 实时输出 + 状态指示 |

#### 2.2.11 `src/bootstrap/checker.py` — DependencyChecker

**职责**：启动环境检查。Python ≥ 3.11 版本检测 + requirements.txt 依赖比对 + 可选自动 pip 安装。零第三方依赖（在 pip install 之前运行）。

#### 2.2.12 离线脚本与训练后端（独立于进程外）

| 脚本 | 功能 |
|------|------|
| `data_cleaner.py` | ETL 数据清洗：合并原始 CSV（**合并语义**：保留历史会话）→ 过滤 → 动作合并 → 姿态追踪 → 派生对提取 → `ML_Ready_Dataset.csv` |
| `src/model/production_backend.py` | 一键训练后端（v1.2.0，`--pipeline`）：Run B 配置确定性重训 XGBoost Pipeline（几秒完成）+ 数据摘要行 + 破坏性守门告警 + 两代备份链 + 训练日志 |
| `train_lgbm.py` | LightGBM 训练（**legacy**，`--train` 入口保留向后兼容） |
| `data_upgrade.py` | 旧数据升级：为缺少 `phase`/`is_enraged` 列的历史 CSV 回填数据 |
| `scripts/` | AutoML 工具链（train_automl / export_model / adopt_model / benchmark_model）与构建脚本 |

---

## 3. 系统工作流

### 3.1 启动流程

```text
用户: python launch.py
  │
  ├── 1. DependencyChecker.ensure()     ← 检查 Python ≥ 3.11 + 依赖完整性
  ├── 2. AppConfig.load()               ← 加载 blackdragon_config.json
  ├── 3. AppController(config)          ← 轻量构造（无游戏也不崩溃）
  ├── 4. controller.start_overlay()     ← [可选] 自动启动 Overlay 子进程（config.auto_start_overlay）
  ├── 5. GameService(controller).start()← 后台游戏检测 daemon 启动
  └── 6. Dashboard(controller).run()    ← DPG event loop（阻塞）
```

### 3.2 游戏附着流程（自动）

```text
GameService daemon 每 2s 轮询:
  ├── 游戏未连接 → _try_attach()
  │     └→ pymem.Pymem("MonsterHunterWorld.exe") 成功
  │         └→ controller.attach_game(pm, base):
  │               ├─ MemoryReader(pm, base)         ← 内存读取器
  │               ├─ CombatStateTracker(auto_record)← 战斗状态机
  │               ├─ ActionPredictor(model_path)     ← AI 模型加载
  │               ├─ deque + Lock                    ← 线程通信通道
  │               └─ CombatRecorder(...).start()     ← 录制 daemon 启动
  │
  └── 游戏已连接 → _monitor()
        └→ 连续 3 次健康检查失败 → detach_game()
```

### 3.3 运行时数据流

```text
                    MonsterHunterWorld.exe
                            │
                    ┌───────┴───────┐
                    │  pymem 内存读取 │
                    └───────┬───────┘
                            │
              ┌─────────────┼─────────────┐
              ▼             ▼             ▼
        MemoryReader   StateTracker   Recorder (daemon)
        (原始数据)      (派生状态)      ├── CSV 写入
              │             │           └── action_buffer
              └──────┬──────┘                 │
                     ▼                        ▼
              ActionPredictor            OverlayUI._buffer
              (6 特征 → Top-3)                │
                     │                        │
                     ▼                        ▼
              OverlayUI._compute_frame()
                     │
                     ▼
              OverlayUI._apply_display()
              (DPG set_value 刷新)
```

### 3.4 离线训练管线

```text
data/*.csv (19 个出厂文件 + 用户录制)
        │
        ▼  data_cleaner.py
        │  (动作合并/姿态追踪/派生提取/过滤/合并语义)
data/ML_Ready_Dataset.csv
        │
        ▼  src/model/production_backend.py
        │  (XGBoost Run B 重训, 190 树, 几秒完成; legacy: train_lgbm.py)
models/fatalis_ai_model.pkl + feature_importance.png
  (+ .bak/.bak2 备份链 + factory_model.pkl 出厂副本 + sidecar + train log)
```

### 3.5 双进程架构

BlackDragon 使用两个独立 Python 进程（ADR-P5.2）：

| 进程 | 入口 | 职责 |
|------|------|------|
| **Dashboard 进程** | `python launch.py` | 控制中心 UI + GameService 后台检测 + AppController 生命周期协调 |
| **Overlay 进程** | `python overlay.py` | 透明覆盖层 UI + 独立的 MemoryReader/StateTracker/Predictor/Recorder |

**为什么双进程**：DPG 2.x 使用 GLFW 作为窗口后端，GLFW 要求所有窗口创建在主线程执行。单进程无法同时运行 Dashboard 和 Overlay 两个 DPG 窗口 — 进程级隔离是最简方案。

---

## 4. 使用指南

### 4.1 环境要求

| 要求 | 说明 |
|------|------|
| 操作系统 | **Windows**（Win32 API 依赖） |
| 游戏 | Monster Hunter World 正在运行（`MonsterHunterWorld.exe`） |
| Python | 3.11 或 3.12 |
| 中文字体 | `msyh.ttc`（微软雅黑，Windows 自带） |

### 4.2 安装与配置

```bash
# 1. 克隆项目
git clone <repo-url>
cd BlackDragon

# 2. 创建虚拟环境
python -m venv .venv
.venv\Scripts\activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. 训练模型（首次使用，内置数据；也可直接用随包模型）
python launch.py --pipeline # 一键: 数据清洗（合并语义）→ XGBoost 重训 → 备份链
```

### 4.3 启动系统

```bash
# 推荐方式：双进程（Dashboard + Overlay 自动启动）
python launch.py

# 仅覆盖层（手动模式）
python overlay.py
```

### 4.4 使用步骤

1. **启动游戏**：进入《怪物猎人世界》，接取黑龙（Fatalis）任务
2. **启动 BlackDragon**：运行 `python launch.py`
3. **Dashboard 出现**：控制中心窗口显示，状态栏显示连接状态
4. **等待自动附着**：GameService 检测到游戏后自动初始化，状态指示灯变绿
5. **进入虚黑城**：进入任务后（zone=417），覆盖层自动激活
6. **查看预测**：透明悬浮窗显示当前状态 + Top-3 下一招预测
7. **录制数据**：默认自动录制，可在覆盖层/控制中心切换
8. **退出**：关闭 Dashboard 窗口 → 自动终止 Overlay 子进程并清理

### 4.5 覆盖层显示内容

```
[动作]: 龙车 | P1 [未怒]
[状态]: 距:350 | 角:-15° | 血:82.5%

预测下一招:
连咬: 45.3%
单火球: 22.1%
后撤: 12.8%
```

**颜色含义**：
- 白色文字：战斗状态信息
- 绿色文字：AI Top-3 预测
- 红色文字：飞天火预警

### 4.6 Dashboard 控制中心

| Tab | 功能 |
|-----|------|
| **控制台** | 覆盖层启停按钮、录制开关、CSV 文件列表 |
| **训练** | 一键启动/取消模型训练（XGBoost 一键管线）、实时训练输出 |
| **日志** | 实时滚动日志（所有模块的 logger 输出） |
| **状态栏** | 游戏/模型/录制/覆盖层 四色指示灯 |

### 4.7 重新训练模型

当累积更多战斗数据后，可以重新训练模型以提升预测精度：

```bash
# 方式一：命令行（推荐，一键 = 清洗 → 重训）
python launch.py --pipeline
#   训练前打印数据摘要行（本次 vs 上代 会话/行/类），破坏性变化打 ⚠ 告警
#   你的新录像自动与随包数据集合并，不会静默替换

# 方式二：Dashboard → 训练 Tab → 点击"开始训练"（同一链路）

# 方式三：legacy LightGBM 路径（向后兼容）
python train_lgbm.py
```

---

## 5. 使用注意事项

### 5.1 游戏启动顺序

- **先启动游戏，后启动 BlackDragon**：Overlay 进程有 2 分钟重试窗口（60 次 × 2s），游戏启动后可自动连接
- 如果游戏意外崩溃，Dashboard 会自动清理模块（detach_game），等待游戏重新启动后自动重新附着
- 关闭游戏前应先关闭 BlackDragon（避免内存读取异常）

### 5.2 必须在虚黑城内

- 系统通过内存读取区域 ID（zone=417）判定是否在虚黑城
- **离开虚黑城后覆盖层自动休眠**（显示"未在虚黑城，雷达已休眠..."），所有状态重置
- 重新进入虚黑城后自动恢复工作
- 这意味着探索地图、回营地、接其他任务时覆盖层不会干扰

### 5.3 内存偏移量版本依赖

- **内存偏移量与游戏版本强绑定**：游戏更新后三大基址（PLAYER_BASE/MONSTER_BASE/ZONE_BASE）可能变化
- 如果游戏更新导致读取失败，需要用 Cheat Engine 等工具重新定位基址，更新 `src/config/offsets.py` 中的值
- 20 个内部偏移量在小更新中通常不变
- 详细操作指南见：[[Game_Reverse/Offset_System|Offset System]]

### 5.4 中文字体依赖

- 覆盖层使用 `msyh.ttc`（微软雅黑）渲染中文招式名
- Windows 系统自带此字体，通常不需要额外配置
- 如果覆盖层中文显示异常：检查 `C:/Windows/Fonts/msyh.ttc` 是否存在；确认 `src/ui/fonts.py` 字体路径正确

### 5.5 双进程架构注意事项

- 两个进程**独立运行**：Dashboard 和 Overlay 各自有独立的 DPG context
- 配置在启动时各自加载一次：运行时修改 `blackdragon_config.json` 不会同步到已运行的进程（需要重启）
- 录制数据各自写独立 CSV：Dashboard 和 Overlay 各自有一个 CombatRecorder，生成不同的 CSV 文件
- 关闭 Dashboard 会自动终止 Overlay 子进程

### 5.6 模型训练注意事项

- 训练脚本运行在**子进程**中：不会阻塞 Dashboard 界面
- 训练使用 `data/ML_Ready_Dataset.csv` 作为输入（一键链路自动先清洗合并）
- 训练产物通过**两代备份链**提升（`.bak` / `.bak2`），内容不变时跳过轮换
- 随包分发不可变出厂副本 `models/factory_model.pkl`，可一步回滚到发行模型
- 更多数据 = 更好模型：建议录制更多黑龙战斗后一键重训（数据自动合并）

### 5.7 运行中的安全事项

- 覆盖层窗口设置了**鼠标穿透**（WS_EX_TRANSPARENT）：点击覆盖层区域不会影响游戏操作
- 覆盖层始终置顶（always_on_top），但不会拦截键盘/鼠标输入
- 如果覆盖层位置遮挡了重要游戏 UI，可以拖拽调整窗口位置（取决于 DPG 设置）

### 5.8 冻结版（EXE 分发）

如果有 PyInstaller 打包的 EXE 版本：
- `BlackDragon.exe` → Dashboard（等同于 `python launch.py`）
- `BlackDragonOverlay.exe` → 覆盖层（等同于 `python overlay.py`）
- 双击 `BlackDragon.exe` 即可启动，自动检测游戏并弹出覆盖层
- 训练功能在冻结版中通过同一 EXE 的 `--pipeline` 模式运行（Dashboard 训练按钮触发）
- **自检**：任一 EXE 运行 `--selftest` 可验证"路径解析 → 模型加载 → 一次推理"（exit 0 = 健康）；该自检也是构建门禁

### 5.9 已知限制

| 限制 | 说明 |
|------|------|
| 单一怪物 | 仅支持黑龙（Fatalis），硬编码 zone=417，HP>500 判定 |
| 无多人追踪 | 不追踪其他玩家的位置和状态 |
| 无武器区分 | 不根据玩家武器类型调整预测 |
| 单模型 | 仅一个 XGBoost 生产模型（+legacy LightGBM 路径），未使用集成 |
| 启动内存 | 模型加载带来约 122MB 一次性 RSS 增量（xgboost 固有，用户裁决接受；稳态在预算内） |

---

## 6. 核心创新点

### 6.1 硬件级发怒检测

传统辅助用"软计时器"推测发怒状态（检测怒吼动作 → 推算 180 秒窗口）。BlackDragon 直接读取游戏引擎内部的**发怒秒表**（Monster + 0x1BE30 + 0x24），实现帧级精度、绝对准确的发怒判定。

### 6.2 两层预测架构

```
ML 概率 → Phase Filter（阶段过滤）
        → Posture Filter（姿态过滤）
        → Renormalize（重归一化）
        → Top-3 输出
```

纯 ML 模型可能输出物理上不可能在当前阶段/姿态执行的招式。硬过滤层利用游戏规则保证预测合法性——这是 BlackDragon 区别于纯 ML 方案的关键设计。

### 6.3 动作合并映射（ACTION_MAPPING）

游戏引擎在动画每一帧暴露不同 action_id（如龙车帧1=38, 帧2=39, 帧3=40）。直接使用会导致模型学到大量"假转移"。54 条合并映射将所有动画帧合并为起手式 Base ID，确保模型学习的都是真实的招式切换。

---

## 7. 技术栈

| 类别 | 技术 | 说明 |
|------|------|------|
| 语言 | Python 3.11/3.12 | |
| 内存读取 | pymem | Windows 进程内存（ReadProcessMemory） |
| GUI 框架 | DearPyGui 2.x | 透明覆盖层 + 控制中心双窗口 |
| 窗口穿透 | Win32 API (ctypes) | WS_EX_LAYERED \| WS_EX_TRANSPARENT |
| ML 框架（生产） | XGBoost 3.4.1 | 多分类梯度提升树（sklearn Pipeline 封装，v1.2.0 起） |
| ML 框架（legacy） | LightGBM 4.6.0 | `--train` 旧训练路径保留 |
| AutoML（仅实验） | FLAML 2.6.0 | `scripts/train_automl.py`（生产推理零 flaml 依赖） |
| 数据处理 | pandas, numpy | CSV 读写 + 特征构造 |
| 模型序列化 | joblib | .pkl 格式 |
| 测试框架 | pytest + coverage | 766 tests passed（v1.2.0） |
| CI | GitHub Actions | Ubuntu + Windows, Python 3.11/3.12 |

---

## 8. 相关文档

- 完整知识库索引：[[Index]]
- 系统架构：[[Architecture/System_Architecture|System Architecture]]
- 模块设计：[[Architecture/Module_Design|Module Design]]
- 进程与线程模型：[[Architecture/Process_Architecture|Process Architecture]]
- 数据全链路：[[Architecture/Data_Flow|Data Flow]]
- 战斗状态系统：[[Game_Reverse/Combat_State|Combat State]]
- 内存架构：[[Game_Reverse/Memory_Architecture|Memory Architecture]]
- 训练管线：[[AI_Model/Training_Pipeline|Training Pipeline]]
- 开发路线图：[[Development/Development_Roadmap|Development Roadmap]]
- 架构决策记录：[[Architecture/ADR_Index|ADR Index]]
- 项目 README：`../README.md`
