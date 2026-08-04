# Knowledge Base v1.0 — Architecture Design

- **Date**: 2026-08-04
- **Author**: Architect
- **Source**: `docs/Knowledge_Base_Audit.md` (researcher audit)
- **Status**: Proposed

---

## 1. Design Principles

| # | Principle | Rationale |
|---|-----------|-----------|
| P1 | **不删除已有文档** | 旧文档保留为历史记录（移入 `docs/legacy/`）；新建文档使用新路径 |
| P2 | **Memory Bank 独立维护** | `memory_bank/` 结构不变——它服务于 AI Agent 会话上下文，由 architect（activeContext/progress）和 coder（changelog）分工维护 |
| P3 | **ADR 保留在 docs/architecture/** | 架构决策记录是 Git 历史的一部分，不随知识库结构变化而迁移 |
| P4 | **"事实文档"vs"历史文档"明确分离** | 当前架构文档（`Architecture/`）与历史调研笔记（`docs/research/`）、旧项目文档（`docs/legacy/`）分目录存放 |
| P5 | **文档合并减少碎片** | 审计发现的重复内容（Memory_Reading ↔ Memory_Architecture, Action_System + Enrage_System, AI_Pipeline + Training_Process）通过新建合并文档解决 |
| P6 | **Index.md 作为纯导航中枢** | 不自维护状态数据——状态来自 `memory_bank/activeContext.md`；Index 只负责路由 |

---

## 2. Target Directory Structure

```
obsidian/
│
├── Index.md                              # ★ 新建：知识库总入口
│
├── Architecture/                         # ★ 重写：当前系统架构
│   ├── System_Architecture.md            #    NEW：系统拓扑 + 组件交互
│   ├── Module_Design.md                  #    NEW：模块职责矩阵 + 关键 API
│   ├── Process_Architecture.md           #    NEW：双进程/线程模型 + 生命周期
│   ├── Data_Flow.md                      #    NEW：数据全链路（采集→清洗→训练→推理）
│   └── ADR_Index.md                      #    NEW：全部 ADR 索引 + 单行摘要
│
├── Development/                          # ★ 重写：开发者文档
│   ├── Development_Roadmap.md            #    NEW：已完成阶段概览 + 未来方向
│   ├── Release_History.md                #    NEW：版本历史 + 关键指标演进
│   └── Testing_Strategy.md               #    REWRITE：当前测试体系
│
├── AI_Model/                             # 保留 + 新增
│   ├── Feature_Engineering.md            #    KEEP：特征设计（6 维）
│   ├── Training_Pipeline.md              #    NEW：完整训练管线（合并 AI_Pipeline + Training_Process）
│   ├── Inference_System.md               #    NEW：推理系统（合并 LightGBM_Model + Model_Evaluation）
│   ├── LightGBM_Model.md                 #    KEEP：模型规格原始文档
│   ├── Model_Evaluation.md               #    KEEP：评估指标原始文档
│   └── Training_Process.md               #    KEEP：超参数原始文档
│
├── Game_Reverse/                         # 保留 + 新增
│   ├── Memory_Architecture.md            #    NEW：内存架构（合并 Memory_Reading + Architecture/Memory_Architecture）
│   ├── Offset_System.md                  #    KEEP：偏移系统
│   ├── Combat_State.md                   #    NEW：战斗状态（合并 Action_System + Enrage_System）
│   ├── Action_System.md                  #    KEEP：动作系统原始文档
│   ├── Memory_Reading.md                 #    KEEP：内存读取方法学
│   └── Enrage_System.md                  #    KEEP：发怒系统原始文档
│
├── docs/                                 # 重组
│   ├── architecture/                     #    KEEP：ADR 决策记录
│   │   ├── ADR-P5.2-overlay-process.md
│   │   └── ADR-P5.3-auto-start.md
│   │
│   ├── research/                         #    KEEP：P5 架构调研（历史参考）
│   │   ├── architecture-control-center.md
│   │   ├── architecture-p5.1-bootstrap.md
│   │   └── ui-product-analysis.md
│   │
│   ├── legacy/                           #    NEW：历史文档归档
│   │   ├── README.md                     #    归档说明（为何归档、归档来源）
│   │   ├── architecture-v0/              #    旧 Architecture/ 目录
│   │   │   ├── System_Architecture.md    #      P3 时期 God Class 架构
│   │   │   ├── AI_Pipeline.md            #      旧 AI 管线描述
│   │   │   ├── Data_Flow.md              #      旧数据流描述
│   │   │   └── Memory_Architecture.md    #      旧内存架构描述
│   │   ├── development-v0/               #    旧 Development/ 目录
│   │   │   ├── Refactoring_Roadmap.md
│   │   │   ├── Development_Log.md
│   │   │   └── CI_CD.md
│   │   ├── Project_map.md                #     2026-06-07 冻结
│   │   ├── Refactoring_roadmap.md        #     旧版路线图
│   │   ├── Tech_debt.md                  #     P2/P3 技术债清单
│   │   ├── MEMORY_BANK_SPEC.md           #     P1 初始化规范
│   │   ├── P2_CLOSURE_REPORT.md          #     P2 结项报告
│   │   ├── P3_HANDOFF.md                 #     P3 交接文档
│   │   ├── offsets_guide.md              #     偏移量修改指南
│   │   └── PROJECT_ANALYSIS.md           #     早期项目分析
│   │
│   └── Knowledge_Base_Audit.md           #    KEEP：审计报告（本次）
│
├── assets/                               # KEEP（空目录，Obsidian assets）
├── experiments/                          # KEEP（空目录）
│
└── memory_bank/                          # KEEP：AI Agent 上下文
    ├── activeContext.md                  #    需更新到 P5.3 auto-start
    ├── changelog.md                      #    ✅ 最新（coder 自动维护）
    ├── progress.md                       #    需更新到 P5.3 auto-start
    ├── projectbrief.md                   #    需更新
    ├── productContext.md                 #    需更新
    ├── systemPatterns.md                 #    需更新
    └── techContext.md                    #    需更新
```

---

## 3. 每个文件的详细设计

### 3.1 `Index.md` — 知识库总入口

**设计原则**：不自维护状态数据（P1）。状态数据从 `memory_bank/activeContext.md` 引用。

**内容骨架**：

```markdown
# BlackDragon 知识库

## 我是谁
→ 链接到 memory_bank/projectbrief.md（项目身份）

## 当前状态
→ 链接到 memory_bank/activeContext.md（phase / test count / coverage）
→ 链接到 memory_bank/progress.md（阶段任务清单）

## 快速导航

### 架构
→ Architecture/System_Architecture.md — 系统拓扑
→ Architecture/Module_Design.md — 模块职责
→ Architecture/Process_Architecture.md — 进程/线程模型
→ Architecture/Data_Flow.md — 数据流
→ Architecture/ADR_Index.md — 架构决策记录索引

### AI 模型
→ AI_Model/Training_Pipeline.md — 训练管线
→ AI_Model/Feature_Engineering.md — 特征设计
→ AI_Model/Inference_System.md — 推理系统

### 游戏逆向
→ Game_Reverse/Memory_Architecture.md — 内存结构
→ Game_Reverse/Offset_System.md — 偏移量
→ Game_Reverse/Combat_State.md — 战斗状态系统

### 开发
→ Development/Development_Roadmap.md — 路线图
→ Development/Release_History.md — 版本历史
→ Development/Testing_Strategy.md — 测试策略

## 入口点
| 命令         | 用途                         |
|-------------|-----------------------------|
| launch.py   | 双进程（推荐）                |
| overlay.py  | 仅 Overlay                   |
| main.py     | P4 overlay (legacy)          |
| ai_engine.py | God Class (legacy)          |

## 技术栈
→ 链接到 memory_bank/techContext.md
```

### 3.2 `Architecture/System_Architecture.md` — 系统拓扑

**来源**：替换过时的 `Architecture/System_Architecture.md`（P3 God Class 描述）。

**应覆盖**：
- 进程结构图（Dashboard Process + Overlay Process → 两个独立 Python 进程）
- DashBoard 进程内部：`launch.py` → `AppController` → `GameService` + `Dashboard.run()`
- Overlay 进程内部：`overlay.py` → `MemoryReader` + `StateTracker` + `Predictor` + `Recorder` + `OverlayUI.run()`
- 组件交互图（Mermaid）：两进程各自的模块拓扑
- 外部依赖：`MonsterHunterWorld.exe`（pymem 连接）、`blackdragon_config.json`（共享配置）、`data/` 和 `models/` 目录
- 离线管线（独立脚本：`data_cleaner.py`, `train_lgbm.py`——非进程内运行）
- 与 legacy 的关系（`ai_engine.py` 保留作为 P3 测试兼容入口）

**页数目标**：~100-150 行，含 2 个 Mermaid 图

### 3.3 `Architecture/Module_Design.md` — 模块职责矩阵

**应覆盖**：
- `src/` 目录树全览
- 每个包的职责卡片（1 段落 + API 列表）：
  - `src/core/` — `CombatStateTracker`, `MemoryReader`
  - `src/model/` — `ActionPredictor`
  - `src/data/` — `CombatRecorder`
  - `src/ui/` — `OverlayUI`, `setup_cjk_font`
  - `src/app/` — `AppController`, `AppConfig`, `GameService`
  - `src/dashboard/` — `Dashboard`, `StatusBar`, `LogView`, `TrainingPanel`
  - `src/bootstrap/` — `DependencyChecker`
  - `src/config/` — `actions.py`, `offsets.py`（唯一数据源）
- 模块依赖图（Mermaid DAG）
- 每个模块的测试文件映射（模块 → test file → test count → coverage%）

**页数目标**：~150-200 行，含 1 个 DAG 图 + 1 个职责表

### 3.4 `Architecture/Process_Architecture.md` — 进程/线程模型

**应覆盖**：
- 双进程动机（DPG 2.x / GLFW main-thread 限制，来自 ADR-P5.2）
- 两个进程的启动时序图（launch.py 如何 spawn overlay.py，谁先谁后）
- Dashboard 进程线程模型：
  - Main thread: DPG event loop（`Dashboard.run()`）
  - GameService daemon：2s 轮询游戏进程 → `attach_game` / `detach_game`
  - Recorder daemon：0.1s 录制帧（仅在游戏附着后存在）
  - Training subprocess（可选）
- Overlay 进程线程模型：
  - Main thread: DPG event loop（`OverlayUI.run()`）
  - Recorder daemon：0.1s 录制帧
- 进程生命周期状态机：
  - 启动 → Bootstrap → 加载 Config → [auto_start_overlay?] spawn Overlay → Dashboard 就绪
  - 游戏附着 → attach_game → create P4 modules → start Recorder
  - 游戏分离 → detach_game → stop Recorder
  - Dashboard 退出 → shutdown → terminate Overlay subprocess → terminate Training
- 状态同步策略（两个进程间，来自 ADR-P5.2）：
  - Recording state: 独立 per-process
  - CSV files: 各自写入 `data/`（独立 CombatRecorder 实例）
  - Model: 各自加载 `models/fatalis_ai_model.pkl`
  - Config: 各自独立加载 `blackdragon_config.json`

**页数目标**：~120-150 行，含 2 个 Mermaid 时序图

### 3.5 `Architecture/Data_Flow.md` — 数据流

**来源**：合并旧 `Architecture/Data_Flow.md` + 旧 `Architecture/AI_Pipeline.md` 的管线部分。

**应覆盖**：
- 数据流全景图（从游戏内存到悬浮窗预测）
- 在线路径：Game RAM → pymem → MemoryReader → StateTracker → Predictor → OverlayUI
  - 数据格式转换：raw bytes → Python float/int → derived state → feature vector → probability array → display text
- 录制路径：Game RAM → pymem → MemoryReader → StateTracker → CombatRecorder → CSV
  - CSV 列格式（8 列）
  - 文件命名规则（`fatalis_combat_data_YYYYMMDD_HHMMSS.csv`）
- 训练路径：CSV ×17 → data_cleaner.py → ML_Ready_Dataset.csv → train_lgbm.py → fatalis_ai_model.pkl
  - 数据变换关键节点（动作合并、姿态追踪、派生提取、物理过滤）
- Config 数据流：`blackdragon_config.json` ←→ `AppConfig.load()` / `AppConfig.save()`
  - 跨进程 config 共享模式

**页数目标**：~100-130 行，含 1 个全链路 Mermaid 图

### 3.6 `Architecture/ADR_Index.md` — ADR 索引

```markdown
# Architecture Decision Records

| ID | Title | Date | Status | Summary |
|----|-------|------|--------|---------|
| ADR-P5.2 | Overlay Architecture Decision | 2026-08-03 | Decided | 双进程架构决策：DPG/GLFW main-thread 限制迫使 Overlay 独立为子进程 |
| ADR-P5.3 | Auto-Start and Recording Default | 2026-08-04 | Proposed | launch.py 默认启动 Overlay + auto_record 默认 True |

→ 全文见 `docs/architecture/ADR-*.md`
```

**维护规则**：每新增一条 ADR，在此文件追加一行。

### 3.7 `Development/Development_Roadmap.md` — 路线图

**来源**：替换 `Development/Refactoring_Roadmap.md`。

```markdown
# Development Roadmap

## Completed Phases

| Phase | Name | Completion | Key Outcome |
|-------|------|-----------|-------------|
| P1 | 项目标准化 | 2026-06-22 | README, .gitignore, 目录结构 |
| P2 | P0 关键修复 | 2026-06-25 | Logging, 统一 actions/offsets, posture FSM |
| P3 | 测试体系 | 2026-08-02 | 182 tests, 60% coverage, CI |
| P4 | 架构重构 | 2026-08-03 | 5 模块提取（StateTracker/MemoryReader/Predictor/Recorder/OverlayUI）|
| P5 | Dashboard + Overlay | 2026-08-04 | 双进程架构, 541 tests, 94% coverage |
| P5.3 auto-start | 自动启动 | 2026-08-04 | auto_start_overlay + auto_record 配置 |

## Future

| Phase | Name | Status | Target |
|-------|------|--------|--------|
| P6 | 模型工程化 | Planned | Model versioning, incremental learning, GitHub Release v1.0.0 |
```

### 3.8 `Development/Release_History.md` — 版本历史

```markdown
# Release History

| Version | Tag | Date | Tests | Coverage | Key Change |
|---------|-----|------|:---:|:---:|-------------|
| v0.1.0 | project-init | 2026-06-22 | — | — | Project standardization |
| v0.2.0 | p0-fixes | 2026-06-25 | — | — | Critical fixes |
| v0.3.0 | test-safety-net | 2026-08-02 | 182 | 60% | Test infrastructure |
| v0.4.0 | architecture-refactor | 2026-08-03 | 385 | 72% | Module extraction |
| v0.5.0 | dashboard | 2026-08-04 | 532 | 93% | Dual-process overlay |
| v1.0.0 | (planned) | TBD | — | — | Model engineering + Release |
```

### 3.9 `Development/Testing_Strategy.md` — 重写

**当前内容**：P3 版本（147 tests）。

**新内容**：
- 测试金字塔更新到 541 tests
- 每个测试文件的用途表（16+ test files → target module mapping）
- Coverage 报告（94% overall, 100% on P4 core）
- Cross-platform strategy（Linux CI stubs for pymem/dpg）
- Mock 策略：MemoryReader、ActionPredictor 在 tests 中完全 mock；CombatStateTracker 使用真实实例（纯逻辑）
- `MPLBACKEND=Agg` 要求（Tcl/Tk 环境问题）

### 3.10 `AI_Model/Training_Pipeline.md` — 新建合并

**来源**：合并 `Architecture/AI_Pipeline.md`（在线/离线管线）+ `AI_Model/Training_Process.md`（超参数/命令）。

**内容**：
- 管线图（原始 CSV → data_cleaner → ML_Ready → train_lgbm → .pkl）
- 数据采集（CombatRecorder daemon 录制）
- 数据清洗关键步骤
- 训练超参数表
- 评估指标
- 训练命令 + 产物

**保留原文件**：`AI_Model/Training_Process.md` 不变（作为详细参考）；新建的 `Training_Pipeline.md` 是概览文档。

### 3.11 `AI_Model/Inference_System.md` — 新建合并

**来源**：合并 `AI_Model/LightGBM_Model.md`（模型规格/推理流程）+ `AI_Model/Model_Evaluation.md`（评估指标）。

**内容**：
- LightGBM 规格（6 特征 → ~40-60 类）
- 推理流程图（→ predict_proba → filter → renormalize → Top-3）
- 两层预测架构（ML + 物理规则）
- 实现：`ActionPredictor.predict()` API
- 推理性能指标（< 5ms）
- Evaluation metrics（Accuracy, Top-3 hit rate）

**保留原文件**：`LightGBM_Model.md`、`Model_Evaluation.md` 不变。

### 3.12 `Game_Reverse/Memory_Architecture.md` — 新建合并

**来源**：合并 `Game_Reverse/Memory_Reading.md`（方法学）+ `Architecture/Memory_Architecture.md`（偏移量布局）。

**内容**：
- pymem vs 替代方案的选择理由
- 三大基址 + 指针遍历流程图
- 怪物实例链（10 槽位）、玩家链（3 级）、区域检测
- 每个关键偏移量的含义 + 当前值（引用 `src/config/offsets.py`）
- `MemoryReader` 实现的 9 个 public method 对照表
- 版本依赖性警告

**保留原文件**：`Memory_Reading.md`、`Architecture/Memory_Architecture.md`（后者移入 legacy）。

### 3.13 `Game_Reverse/Combat_State.md` — 新建合并

**来源**：合并 `Game_Reverse/Action_System.md`（动作映射 + 姿态）+ `Game_Reverse/Enrage_System.md`（发怒检测 + Nova）。

**内容**：
- 战斗状态全景：动作（ACTION_DB / ACTION_MAPPING）、姿态（5 态 FSM）、阶段（HP% → P1/P2/P3）、发怒（硬件级读取）、Nova（阈值 FSM）
- 两层预测中的物理规则层（Phase Filter + Posture Filter）
- `CombatStateTracker` 的 8 个 public method 对照表
- 特殊招式分类（DOWN_IDS, SCRIPTED_IDS, MINOR_AND_PASSIVE）

**保留原文件**：`Action_System.md`、`Enrage_System.md` 不变。

### 3.14 `docs/legacy/README.md` — 归档说明

```markdown
# Legacy Documents

本目录包含 BlackDragon v1.0 知识库重构（2026-08-04）前的历史文档。
这些文档已不再反映当前系统架构，但保留为历史记录。

│ 子目录│ 来源│ 归档原因│
│------│------│----------│
│ architecture-v0/ | obsidian/Architecture/ | P3 时期 God Class 架构描述，已由新版 Architecture/ 取代 |
│ development-v0/  | obsidian/Development/   | P1-P3 路线图草案，已由新版 Development/ 取代 |
│ Project_map.md   | obsidian/docs/          | 最后更新 2026-06-07，540 行描述已废弃的单文件结构 |
│ Refactoring_roadmap.md | obsidian/docs/   | P3 制定，内容已分散到 progress.md 等 |
│ MEMORY_BANK_SPEC.md | obsidian/docs/       | P1 一次性初始化规范 |
│ ...              |                        | |
```

---

## 4. Migration Plan

### Step 1: 新建文件（零风险——不修改已有文件）

| 顺序 | 文件 | 依赖 |
|:---:|------|------|
| 1 | `Architecture/ADR_Index.md` | `docs/architecture/ADR-*` |
| 2 | `Architecture/System_Architecture.md` | 源码结构 |
| 3 | `Architecture/Module_Design.md` | 源码结构 |
| 4 | `Architecture/Process_Architecture.md` | `System_Architecture.md` + ADR-P5.2 |
| 5 | `Architecture/Data_Flow.md` | 源码 + `AI_Model/Training_Pipeline.md` |
| 6 | `AI_Model/Training_Pipeline.md` | `AI_Model/Training_Process.md` |
| 7 | `AI_Model/Inference_System.md` | `AI_Model/LightGBM_Model.md` |
| 8 | `Game_Reverse/Memory_Architecture.md` | `Game_Reverse/Memory_Reading.md` |
| 9 | `Game_Reverse/Combat_State.md` | `Game_Reverse/Action_System.md` |
| 10 | `Development/Development_Roadmap.md` | `changelog.md` + `progress.md` |
| 11 | `Development/Release_History.md` | `changelog.md` |
| 12 | `Development/Testing_Strategy.md` | `tests/` 目录 + coverage 报告 |
| 13 | `docs/legacy/README.md` | 旧文档清单 |
| 14 | `Index.md` | 所有新建文件 |

### Step 2: 移动旧文件（需 architect 确认后执行——移动而非删除）

| 操作 | 目标路径 | 说明 |
|------|----------|------|
| MOVE | `docs/legacy/architecture-v0/System_Architecture.md` | 从 `Architecture/` 移动（保留 4 个文件） |
| MOVE | `docs/legacy/architecture-v0/AI_Pipeline.md` | 同上 |
| MOVE | `docs/legacy/architecture-v0/Data_Flow.md` | 同上 |
| MOVE | `docs/legacy/architecture-v0/Memory_Architecture.md` | 同上 |
| MOVE | `docs/legacy/development-v0/Refactoring_Roadmap.md` | 从 `Development/` 移动 |
| MOVE | `docs/legacy/development-v0/Development_Log.md` | 同上 |
| MOVE | `docs/legacy/development-v0/CI_CD.md` | 同上 |
| MOVE | `docs/legacy/Project_map.md` | 从 `docs/` 移动 |
| MOVE | `docs/legacy/Refactoring_roadmap.md` | 同上 |
| MOVE | `docs/legacy/Tech_debt.md` | 同上 |
| MOVE | `docs/legacy/MEMORY_BANK_SPEC.md` | 同上 |
| MOVE | `docs/legacy/P2_CLOSURE_REPORT.md` | 同上 |
| MOVE | `docs/legacy/P3_HANDOFF.md` | 同上 |
| MOVE | `docs/legacy/offsets_guide.md` | 同上 |
| MOVE | `docs/legacy/PROJECT_ANALYSIS.md` | 同上 |
| REWRITE | `Index.md` | 原地重写（旧版本已过时） |
| NONE | `memory_bank/*` | 不移动——在当前位置手工更新 |

### Step 3: 更新 Memory Bank（需 architect 执行）

| 文件 | 变更 |
|------|------|
| `activeContext.md` | 更新到 P5.3 auto-start 完成状态 |
| `progress.md` | 更新 P5 任务勾选 + 当前指标 |
| `projectbrief.md` | 反映模块化项目结构 |
| `productContext.md` | 添加 Dashboard 控制中心场景 |
| `systemPatterns.md` | 添加双进程模型 + 配置系统 |
| `techContext.md` | 更新 File Inventory + 技术栈 |

---

## 5. 文档依赖图

新文件之间的信息引用路径（单向，无环）：

```
Index.md
 ├── memory_bank/activeContext.md          ← 当前状态
 ├── Architecture/System_Architecture.md    ← 架构全景
 │    ├── Architecture/Module_Design.md     ← 模块职责
 │    ├── Architecture/Process_Architecture.md ← 进程/线程
 │    └── Architecture/Data_Flow.md         ← 数据流
 ├── AI_Model/Training_Pipeline.md          ← 训练管线
 │    ├── AI_Model/Feature_Engineering.md   ← 特征
 │    └── AI_Model/Inference_System.md      ← 推理
 ├── Game_Reverse/Memory_Architecture.md    ← 内存结构
 ├── Game_Reverse/Combat_State.md           ← 战斗状态
 ├── Development/Development_Roadmap.md     ← 路线图
 └── Architecture/ADR_Index.md              ← ADR 索引

docs/architecture/ADR-*.md                  ← 不依赖新结构（独立权威）
docs/research/*                             ← 不依赖新结构（历史参考）
docs/legacy/*                               ← 不依赖新结构（时间胶囊）
memory_bank/*                               ← 不依赖新结构（自包含）
```

---

## 6. 与旧结构的对比

| 维度 | 旧 (v0) | 新 (v1.0) |
|------|---------|-----------|
| 总文件数 | 39 | ~55（+16 新建，旧文件保留在 legacy/） |
| 架构描述 | God Class 时代（`ai_engine.py` 328 行） | 模块化 + 双进程（20+ 个模块） |
| 入口 | 内嵌状态数据（Index.md 自行维护阶段/测试数） | 链接型中枢（Index → activeContext.md 获取状态） |
| 文档新鲜度 | ~60% 过时 | 14 个新建文件均反映当前源码 |
| 模块文档 | 无 | `Module_Design.md`（每模块 1 卡片） |
| 进程模型 | Thread 1 + Thread 0 图 | 双进程 + 多线程 + 子进程（Training）全景 |
| ADR 可发现性 | ADR 散落在 `docs/architecture/` | `ADR_Index.md` 带单行摘要的索引表 |
| 重复内容 | Memory_Reading ↔ Memory_Architecture； AI_Pipeline ↔ Data_Flow | 合并文档消除碎片 |
| 历史归档 | 无规则——旧文档与当前文档混放 | `docs/legacy/README.md` 清晰解释归档原因 |

---

## 7. 维护策略

| 文件或目录 | 维护者 | 触发条件 |
|-----------|--------|---------|
| `memory_bank/changelog.md` | **coder** | 每次任务结束自动追加 |
| `memory_bank/activeContext.md` | **architect** | 阶段完成或架构变更时更新 |
| `memory_bank/progress.md` | **architect** | 阶段完成时更新 phase 状态 |
| `memory_bank/projectbrief.md` 等 | **architect** | 项目身份/目标实质变化时（低频） |
| `Architecture/ADR_Index.md` | **architect** | 每新增一条 ADR 时追加一行 |
| `Architecture/System_Architecture.md` | **architect** | 架构大变更时更新（如跨 phases） |
| `Architecture/Module_Design.md` | **architect** | 新增/移除模块时更新 |
| `Development/Release_History.md` | **coder** | 每次 tag/v 版本发布时追加版本行 |
| `docs/legacy/` | **nobody** | "写一次，永不修改"的时间胶囊——仅在从活跃区移动额外文件时补充 |
| `Index.md` | **architect** | 仅当导航结构变化时更新 |

---

## 8. Approval Checklist

- [ ] architect 确认 `Architecture/` 5 个新文件的设计范围
- [ ] architect 确认 `AI_Model/` 和 `Game_Reverse/` 的合并策略（保留原文件 + 新建合并文档，不删除原文件）
- [ ] architect 确认 `docs/legacy/` 归档清单（旧文档全部保留，不删除）
- [ ] architect 确认 Memory Bank 更新计划（Step 3）
- [ ] architect 分配新文件编写任务（Step 1 可由 coder 执行：新文件基于源码生成；Step 2 和 Step 3 需 architect 审核后执行）
