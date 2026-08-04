# 🔥 BlackDragon 项目全面分析报告

> 生成日期：2026-06-07

---

## 1. 项目结构图

```
D:\BlackDragon/
│
├── ═══ 核心引擎 ═══
│   ├── ai_engine.py          ★ 主程序：实时内存读取 + AI 预测 + 悬浮窗 + 数据录制
│   └── mod.py                旧版简易悬浮窗（无 AI 预测，已废弃）
│
├── ═══ 数据处理管线 ═══
│   ├── data_cleaner.py       原始 CSV → ML_Ready_Dataset.csv（动作合并 + 姿态状态机 + 派生提取）
│   └── data_upgrade.py       旧版 CSV 补全工具（回填 phase / is_enraged 列）
│
├── ═══ 模型训练 ═══
│   └── train_lgbm.py         LightGBM 多分类训练 → fatalis_ai_model.pkl + feature_importance.png
│
├── ═══ 逆向工程 ═══
│   └── enrage.py             内存扫描器：发现发怒结构体偏移
│
├── ═══ 数据资产 ═══
│   ├── ML_Ready_Dataset.csv        清洗后的训练数据集（~88KB, 数千条派生样本）
│   ├── fatalis_ai_model.pkl        训练好的 LightGBM 模型（~18MB）
│   ├── feature_importance.png      特征重要性柱状图
│   └── fatalis_combat_data_*.csv  17 个原始录制文件（总计 ~11MB）
│
├── ═══ 参考文档 ═══
│   ├── 出招表.txt            动作 ID ↔ 名称映射表（v1）
│   └── 招式表2.0.txt          动作 ID ↔ 名称映射表（v2，更详细的分类注释）
│
└── ═══ 环境 ═══
    ├── .venv/                Python 虚拟环境
    └── .idea/                PyCharm 项目配置
```

### 各文件职责一句话总结

| 文件 | 性质 | 核心职责 |
|------|------|----------|
| `ai_engine.py` (328行) | 主程序 | 游戏内存实时读取 → 状态解析 → AI 预测 → 透明悬浮窗渲染 |
| `data_cleaner.py` (130行) | ETL | 原始录制 CSV → 动作合并映射 → 姿态状态机 → 提取动作派生对 |
| `data_upgrade.py` (76行) | 数据兼容 | 给旧 CSV 回填 phase/enrage 列，使历史数据可用于训练 |
| `train_lgbm.py` (82行) | 训练 | 加载 ML_Ready_Dataset → LightGBM 训练 → 导出模型 |
| `enrage.py` (82行) | 逆向工具 | 扫描怪物内存结构体，辅助发现发怒计时器偏移量 |
| `mod.py` (248行) | 旧版程序 | 简化版悬浮窗，无 AI 预测，无数据录制 |

---

## 2. 数据流图

```
┌─────────────────────────────────────────────────────────────────────┐
│                     MonsterHunterWorld.exe                          │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐                │
│  │ Player Base  │ │ Monster Base │ │ Zone Base    │                │
│  │ 0x050139A0   │ │ 0x051238C8   │ │ 0x0500ECA0   │                │
│  └──────┬───────┘ └──────┬───────┘ └──────┬───────┘                │
└─────────┼────────────────┼────────────────┼─────────────────────────┘
          │                │                │
          ▼                ▼                ▼
┌──────────────────────────────────────────────────────────────────┐
│  pymem 内存读取层                                                  │
│  ├─ 玩家坐标 (float×3)                                            │
│  ├─ 怪物坐标 (float×3 at +0x160)                                  │
│  ├─ 怪物四元数旋转 (+0x170)                                       │
│  ├─ HP 当前/最大 (+0x7670→+0x60/+0x64)                            │
│  ├─ 当前动作 ID (int32 at +0x6278)                                │
│  ├─ 发怒计时器 (+0x1BE30→+0x24/+0x28)                             │
│  └─ 区域 ID (zone check: 417=虚黑城)                              │
└──────────────────────┬───────────────────────────────────────────┘
                       │
         ┌─────────────┼─────────────┐
         ▼             ▼             ▼
    ┌─────────┐  ┌──────────┐  ┌──────────────┐
    │ 实时计算 │  │ CSV 录制 │  │ 状态机解析    │
    │         │  │          │  │              │
    │ 距离    │  │ 每秒~10  │  │ Phase (1/2/3)│
    │ 相对角度│  │ 行写入   │  │ Enrage (0/1) │
    │ HP%    │  │          │  │ Posture (0-4) │
    └────┬────┘  └────┬─────┘  └──────┬───────┘
         │            │               │
         ▼            ▼               ▼
    ┌─────────┐  ┌──────────────────────────────────────┐
    │悬浮窗渲染│  │         fatalis_combat_data_*.csv     │
    │(dearpy) │  │  timestamp|hp|phase|enrage|dist|     │
    │         │  │  angle|posture|action_id              │
    │ 当前招式│  └────────────────┬─────────────────────┘
    │ HP/距离 │                   │
    │ 发怒状态│                   ▼
    │ AI 预测 │  ┌──────────────────────────────────────┐
    └─────────┘  │  data_cleaner.py (ETL 管线)          │
                 │  ├─ 动作映射合并 (ACTION_MAPPING)     │
                 │  ├─ 姿态状态机推算                     │
                 │  ├─ 过滤小动作/演出/倒地              │
                 │  └─ 提取派生对 (prev→next)           │
                 └────────────────┬─────────────────────┘
                                  │
                                  ▼
                 ┌──────────────────────────────────────┐
                 │       ML_Ready_Dataset.csv            │
                 │  distance|angle|posture|prev_action|  │
                 │  phase|enrage|next_action             │
                 └────────────────┬─────────────────────┘
                                  │
                                  ▼
                 ┌──────────────────────────────────────┐
                 │  train_lgbm.py (模型训练)             │
                 │  ├─ LightGBM 多分类                   │
                 │  ├─ 6维特征 → 招式类别                │
                 │  ├─ 训练/测试 8:2 分割                │
                 │  └─ 特征重要性分析                    │
                 └──────┬──────────────┬────────────────┘
                        │              │
                        ▼              ▼
           ┌──────────────────┐  ┌──────────────────┐
           │fatalis_ai_model  │  │feature_importance│
           │     .pkl (18MB)  │  │     .png         │
           └────────┬─────────┘  └──────────────────┘
                    │
                    │  joblib.load()
                    ▼
           ┌──────────────────────────────────────────┐
           │  ai_engine.py 推理环路 (每 0.5s 一次)      │
           │  ├─ 收集当前 6 维特征                      │
           │  ├─ model.predict_proba()                  │
           │  ├─ 阶段/姿态物理过滤 (概率归零)            │
           │  ├─ 概率重归一化                           │
           │  └─ 输出 Top-3 预测招式                    │
           └──────────────────────────────────────────┘
```

---

## 3. 模块依赖图

```
                    ┌──────────────────┐
                    │  外部系统依赖     │
                    │                  │
                    │  MonsterHunter   │
                    │  World.exe       │──── 游戏进程 (内存源)
                    │  (进程内存空间)   │
                    └────────┬─────────┘
                             │ pymem
                             │
        ┌────────────────────┼────────────────────────┐
        │                    │                        │
        ▼                    ▼                        ▼
┌──────────────┐   ┌──────────────┐          ┌──────────────┐
│  ai_engine   │   │   mod.py     │          │  enrage.py   │
│  (主程序)     │   │  (旧版覆盖层) │          │  (内存扫描器) │
│              │   │              │          │              │
│ pymem        │   │ pymem        │          │ pymem        │
│ dearpygui    │   │ dearpygui    │          │              │
│ pandas       │   │ threading    │          │              │
│ numpy        │   │ ctypes       │          │              │
│ joblib       │   │              │          │              │
│ threading    │   │              │          │              │
│ csv          │   │              │          │              │
│ ctypes       │   │              │          │              │
└──────┬───────┘   └──────────────┘          └──────────────┘
       │
       │ 读取训练产物
       │
       ▼
┌──────────────┐
│ fatalis_ai   │
│ _model.pkl   │◄──── joblib.dump() ──── train_lgbm.py
│ (18MB)       │                       │
└──────────────┘                       │ lightgbm
                                       │ scikit-learn
                                       │ pandas, numpy
                                       │ matplotlib
                                       │ joblib
                                               ▲
                                               │ 读取
                                               │
                                    ┌──────────────────┐
                                    │ ML_Ready_Dataset │
                                    │ .csv             │
                                    └────────┬─────────┘
                                             ▲
                                             │ 产出
                                             │
                                    ┌──────────────────┐
                                    │ data_cleaner.py  │
                                    │ pandas, glob     │
                                    └────────┬─────────┘
                                             ▲
                                             │ 读取
                                             │
                                    ┌──────────────────┐
                                    │ fatalis_combat   │
                                    │ _data_*.csv (×17)│
                                    └────────┬─────────┘
                                             ▲
                                             │ 写入
                                             │
                                    ┌──────────────────┐
                                    │  ai_engine.py    │
                                    │  (录制线程)       │
                                    └──────────────────┘

═══════════════════════════════════════════════════════════════
模块间无代码级 import 依赖，完全通过文件系统耦合：
  *.csv  →  data_cleaner.py  →  ML_Ready_Dataset.csv
  ML_Ready_Dataset.csv  →  train_lgbm.py  →  fatalis_ai_model.pkl
  fatalis_ai_model.pkl  →  ai_engine.py (joblib.load)
```

### 关键技术依赖

| 库 | 用途 | 使用模块 |
|---|---|---|
| `pymem` | 读取游戏进程内存 | ai_engine, mod, enrage |
| `dearpygui` | GPU 加速透明悬浮窗 | ai_engine, mod |
| `lightgbm` | 梯度提升树多分类 | train_lgbm |
| `scikit-learn` | 数据分割、指标计算 | train_lgbm |
| `pandas` | 数据框操作 | ai_engine, data_cleaner, data_upgrade, train_lgbm |
| `numpy` | 数值计算 | ai_engine, train_lgbm |
| `matplotlib` | 特征重要性可视化 | train_lgbm |
| `joblib` | 模型持久化 | ai_engine, train_lgbm |
| `ctypes` | Win32 API 调用（窗口透明/置顶） | ai_engine, mod |
| `threading` | 后台数据采样线程 | ai_engine, mod |

---

## 4. 模型训练流程

```
┌──────────────────────────────────────────────────────────────┐
│                    训练流程全景                               │
└──────────────────────────────────────────────────────────────┘

[1] 数据采集阶段 (ai_engine.py)
    │
    ├─ 玩家进入虚黑城 (zone==417) → 自动开始录制
    ├─ 每 0.1s 采样一帧，写入 CSV
    ├─ 列：timestamp, hp_percent, phase, is_enraged, distance,
    │       relative_angle, posture, action_id
    └─ 17 个录制文件，覆盖多次狩猎

[2] 数据清洗阶段 (data_cleaner.py)
    │
    ├─ 加载所有 fatalis_combat_data_*.csv
    ├─ 过滤：distance > 5000m 的脏数据
    ├─ 过滤：action_id == 1 的未知动作
    │
    ├─ ★ 动作合并映射 (ACTION_MAPPING)
    │   将同一招式的动画后段帧映射到起手帧 Base ID
    │   例：龙车 38/39/40 → 37，连咬 54/55/56/57 → 53
    │   效果：消除同一招式内部帧间的"假派生"
    │
    ├─ ★ 姿态状态机 (Posture FSM)
    │   posture ∈ {0=趴下, 1=站立, 2=飞行, 3=倒地, 4=演出}
    │   追踪跨动作的姿态变化
    │
    ├─ ★ 派生对提取
    │   仅在主合并动作切换时记录：
    │   {distance, angle, posture, previous_action, phase, enrage} → next_action
    │
    └─ 输出：ML_Ready_Dataset.csv

[3] 模型训练阶段 (train_lgbm.py)
    │
    ├─ 加载 ML_Ready_Dataset.csv
    ├─ 过滤：出现次数 < 3 的罕见招式
    │
    ├─ 特征工程（6 维）
    │   ┌─────────────────┬──────────┬──────────────────┐
    │   │ 特征             │ 类型      │ 物理含义          │
    │   ├─────────────────┼──────────┼──────────────────┤
    │   │ distance         │ float    │ 玩家-怪物水平距离  │
    │   │ relative_angle   │ float    │ 玩家相对怪物朝向角  │
    │   │ posture          │ category │ 怪物姿态(0-4)     │
    │   │ previous_action  │ category │ 上一招 Base ID    │
    │   │ phase            │ category │ 战斗阶段(1-3)     │
    │   │ is_enraged       │ category │ 是否发怒(0/1)     │
    │   └─────────────────┴──────────┴──────────────────┘
    │
    ├─ 模型架构
    │   算法：LightGBM (Gradient Boosting Decision Tree)
    │   类型：多分类 (multiclass)
    │   超参数：
    │     num_leaves=63, max_depth=7
    │     learning_rate=0.03, n_estimators=300
    │     subsample=0.8, colsample_bytree=0.8
    │     class_weight='balanced'
    │     early_stopping=15 rounds
    │
    ├─ 评估
    │   训练/测试 = 8:2 (random_state=42)
    │   绝对准确率 (Accuracy)
    │   Top-3 命中率 (核心实战指标)
    │
    └─ 输出：fatalis_ai_model.pkl (joblib 序列化)
```

---

## 5. 推理流程 (实时预测)

```
┌──────────────────────────────────────────────────────────────┐
│         ai_engine.py 推理环路 (每 0.5s 执行一次)              │
└──────────────────────────────────────────────────────────────┘

[Step 1] 区域检查
    │ zone_addr == 0 或 zone != 417 → 休眠，清空所有状态
    └─ 通过 → 继续

[Step 2] 内存读取
    ├─ find_monster() → 遍历 10 个怪物槽位，按 HP>500 匹配
    ├─ 读取玩家/怪物坐标 → 计算 distance, relative_angle
    ├─ 读取 HP → 计算 hp_percent → 推导 phase
    ├─ 读取 action_id → 通过 ACTION_MAPPING 转换为 Base ID
    └─ 读取发怒结构体 (+0x1BE30) → 秒表区间判断 enrage

[Step 3] 状态更新
    ├─ 飞天火(Nova)血线预警：hp <= 78/50/41/26/6% 触发
    ├─ 姿态状态机：根据招式切换更新 posture
    └─ 发怒状态：物理硬件级读取 (不再依赖软计时器)

[Step 4] AI 预测 (如果模型已加载 && 动作有效)
    │
    ├─ 构造输入向量
    │   {distance, relative_angle, posture, previous_action, phase, is_enraged}
    │
    ├─ model.predict_proba(input) → 所有招式的概率分布
    │
    ├─ ★ 物理约束过滤 (关键创新)
    │   ├─ P1_ONLY_IDS:  phase>1 时概率归零  (如 P1 龙车)
    │   ├─ P2_PLUS_IDS: phase<2 时概率归零  (如 P2 孕吐)
    │   ├─ P3_ONLY_IDS: phase<3 时概率归零  (如 360°扫火)
    │   ├─ Posture==1 (站立) 时趴下招式概率归零
    │   └─ Posture==0 (趴下) 时站立招式概率归零
    │
    ├─ 概率重归一化 (除以过滤后的 sum)
    │
    └─ 输出 Top-3 预测 (概率 > 3% 才显示)

[Step 5] 悬浮窗渲染 (dearpygui 透明 overlay)
    ├─ 动作名称 + 阶段 + 发怒状态
    ├─ 距离 + 角度 + 血量百分比
    ├─ Nova 预警 (红色闪烁)
    └─ AI 预测 Top-3 (绿色)
```

### 推理的核心创新点

1. **模型预测 + 物理规则双层过滤**：LightGBM 给出概率分布后，用硬性游戏规则（阶段/姿态）将不可能招式概率归零再重归一化，确保预测 100% 符合游戏机制。

2. **物理级发怒检测**：不再使用软计时器推测（旧方案：检测到怒吼动作 → +180s），而是直接从引擎结构体 `+0x1BE30` 读取秒表值，精确到帧。

3. **动作合并映射**：将同一招式的多帧动画 ID 统一映射到起手 Base ID，避免模型学到"假派生"噪声。

---

## 6. 核心技术债

### 🔴 严重 (影响稳定性/正确性)

| # | 问题 | 位置 | 影响 |
|---|------|------|------|
| 1 | **魔法数字硬编码** | `ai_engine.py` 内存偏移 | 游戏每次更新，所有偏移量 (`0x698`, `0x7670`, `0x6278`, `0x1BE30` 等) 可能失效，无配置文件管理 |
| 2 | **ACCTION_MAPPING 三处重复定义** | `ai_engine.py:48-60`, `data_cleaner.py:15-45`, `mod.py` 隐含 | 修改一处必须在三处同步，目前已出现细微不一致（如 `data_cleaner.py` 多了 `57:53`，`119:129` 和 `80:79` 等） |
| 3 | **静默异常吞噬** | `ai_engine.py:146-147` `except: pass` | 录制线程任何异常都被静默丢弃，数据丢失无感知 |
| 4 | **静默异常吞噬** | `ai_engine.py:309-310` `except: pass` | UI 刷新异常被静默，问题难以排查 |
| 5 | **模型文件硬编码** | `ai_engine.py:156` `"fatalis_ai_model.pkl"` | 无法切换模型版本，缺少模型版本管理 |

### 🟡 中等 (影响可维护性/扩展性)

| # | 问题 | 位置 | 影响 |
|---|------|------|------|
| 6 | **God Class** | `ai_engine.py` `Ultimate_Radar_UI` | 328 行单文件包含：内存读取、状态机、CSV 录制、AI 推理、UI 渲染，违反单一职责 |
| 7 | **全局可变状态** | `ai_engine.py:72-78` `shared_state`, `action_buffer` | 多线程共享无保护（虽然有 lock 但只有 action_buffer 用了），竞态条件隐患 |
| 8 | **CSV 文件无压缩** | 17 个原始 CSV 累计 ~11MB | 长期录制存储膨胀 |
| 9 | **无增量学习** | `train_lgbm.py` | 每次训练从零开始，无法利用之前的模型做增量更新 |
| 10 | **无数据版本标识** | 所有 CSV 无 schema version | `data_upgrade.py` 靠试探列名判断新旧，脆弱 |
| 11 | **特征工程硬编码** | `ai_engine.py:269-272` | 特征集与训练时耦合，若训练新增特征需同步改推理 |
| 12 | **单一模型策略** | `train_lgbm.py` | 只用 LightGBM 一种算法，无模型对比/集成 |

### 🟢 轻微 (代码质量问题)

| # | 问题 | 位置 | 说明 |
|---|------|------|------|
| 13 | 中文/Emoji 混合注释 | 全项目 | 中英混用降低可读性（对非中文开发者） |
| 14 | `mod.py` 与 `ai_engine.py` 冗余 | mod.py | `mod.py` 是 `ai_engine.py` 的前身，功能已完全被覆盖但仍保留 |
| 15 | 缺少测试 | 全项目 | 零单元测试，依赖手工进游戏测试 |
| 16 | 无配置文件 | 全项目 | 所有配置（偏移量、阈值、路径）硬编码在源码中 |
| 17 | `enrage.py` offset 硬编码 | `enrage.py:41` | 扫描范围固定 0x0-0x28，若结构体扩展则遗漏 |

---

## 7. 重构建议

### 优先级 P0：可配置化与解耦

```
建议结构（增量重构，不破坏现有功能）:

src/
├── config/
│   ├── offsets.py           # 所有内存偏移量集中管理
│   ├── actions.py            # ACTION_DB + ACTION_MAPPING (唯一数据源)
│   ├── thresholds.py         # Nova 阈值、Phase 阈值等
│   └── features.py           # 特征列定义
│
├── core/
│   ├── memory_reader.py      # 封装 pymem，提供高层 API
│   ├── state_tracker.py      # 状态机：phase/posture/enrage
│   └── action_resolver.py    # 动作映射 + 名称解析
│
├── data/
│   ├── recorder.py           # CSV 录制（从 ai_engine 拆出）
│   ├── cleaner.py            # 从 data_cleaner.py 迁移
│   └── upgrade.py            # 从 data_upgrade.py 迁移
│
├── model/
│   ├── trainer.py            # 从 train_lgbm.py 迁移
│   ├── predictor.py          # 推理 + 物理过滤
│   └── versioning.py         # 模型版本管理
│
├── ui/
│   └── overlay.py            # dearpygui UI 层 (从 ai_engine 拆出)
│
├── tools/
│   └── enrage_scanner.py     # 从 enrage.py 迁移
│
└── main.py                   # 入口
```

### 优先级 P1：修复技术债

| 编号 | 建议 | 具体做法 |
|------|------|----------|
| #1 | 魔法数字外提 | 创建 `offsets.py`，所有内存偏移集中定义，支持配置文件覆盖 |
| #2 | ACTION_MAPPING 统一 | 创建 `actions.py` 作为唯一数据源，各模块 import 使用 |
| #3 | 异常日志化 | 用 `logging` 替代 `except: pass`，至少记录到文件 |
| #6 | 拆解 God Class | 将 `Ultimate_Radar_UI` 拆为 `MemoryReader`, `StateTracker`, `Predictor`, `OverlayUI` 四个类 |
| #7 | 线程安全 | 用 `threading.RLock()` 保护所有 `shared_state` 读写，或用 `queue.Queue` 替代 `deque` |

### 优先级 P2：模型改进

| 建议 | 说明 |
|------|------|
| **模型版本管理** | 模型文件名包含训练日期和指标，如 `fatalis_v5_20260607_acc72.pkl` |
| **集成学习** | 对比 XGBoost / CatBoost / RandomForest，或 LightGBM + 规则融合 |
| **增量训练** | 利用 LightGBM 的 `init_model` 参数，支持在新数据上继续训练 |
| **超参数搜索** | 加入 Optuna 或 GridSearch 自动调参 |
| **在线评估** | 录制推理日志，离线分析预测准确率，形成反馈闭环 |

### 优先级 P3：工程质量

| 建议 | 说明 |
|------|------|
| **单元测试** | 核心逻辑（状态机、动作映射）写测试，不需要游戏环境 |
| **类型标注** | 逐步加入 type hints，降低维护成本 |
| **配置热加载** | 偏移量/阈值支持 yaml/json 配置，不需重新打包 |
| **清理 mod.py** | 确认废弃后删除，避免混淆 |
| **文档化数据格式** | CSV 列定义、动作 ID 含义写成独立文档 |

---

## 8. 总结

BlackDragon 是一个为 **Monster Hunter World 的终局 Boss 黑龙（Fatalis）** 定制的 **AI 辅助狩猎工具**。其技术栈覆盖了完整的 ML 管线：

```
游戏内存逆向 → 实时数据采集 → ETL 清洗 → LightGBM 训练 → 实时推理 → 透明悬浮窗
```

项目的核心优势在于：
- **物理级精度**：直接读取引擎内存而非屏幕图像识别
- **双层预测**：ML 概率 + 硬性游戏规则过滤，确保预测合法
- **完整的反馈闭环**：录制→训练→推理→再录制

主要短板在于所有代码集中在少数几个文件中，耦合度高，缺乏配置管理和测试，但代码逻辑本身清晰，核心算法（动作合并、姿态状态机、物理过滤）设计巧妙且符合游戏机制。
