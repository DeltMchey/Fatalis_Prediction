# Knowledge Base Audit — BlackDragon Obsidian Vault

- **Date**: 2026-08-04
- **Author**: Researcher
- **Scope**: `obsidian/` 全部 39 个 Markdown 文件
- **Method**: 逐文件逐目录审计 vs. 当前项目源码状态（P5.3 auto-start, 541 tests, 94% coverage）

---

## 1. Summary

| 维度 | 评价 |
|------|------|
| 文档总量 | 39 个 `.md` 文件，分布在 8 个目录 |
| 整体健康度 | ⚠️ **严重过时** — 约 60% 的文档停滞在 2026-07-26（P3.4 或更早） |
| 最新可用 | changelog.md（✅ 最新）、ADR-P5.2/ADR-P5.3（✅）、research/ 调研笔记（✅ 历史参考） |
| 核心问题 | `activeContext.md`、`progress.md`、`Index.md`、`Architecture/` 全部未更新，反映的是 P3–P4 早期状态 |

**结论**：知识库并未随项目演进而维护。Memory Bank 的 `changelog` 是唯一保持更新的文件（通过 coder 在每次任务结束时自动写入），但 `activeContext` 和 `progress` 停滞超过一个月 VET。`Architecture/` 和 `Index.md` 仍描述单文件 `ai_engine.py` God Class 时代，与当前 `src/` 模块化结构脱节。

---

## 2. 按目录深度审计

### 2.1 `Index.md` — 知识库入口

| 状态 | ⛔ 严重过时 |
|------|------------|

**过时内容**：
- "当前阶段: P3.4 — Integration Testing（147 tests, 29% coverage）" → 实际：P5.3 auto-start, 541 tests, 94%
- Phase 表格：P3 🔄 进行中 / P4-P5 📋 计划中 → 实际：P4 完成、P5 完成
- 路线图进度仍为 5 阶段占位
- Entry points 一节不存在（缺少 `launch.py` / `overlay.py` / `main.py` / `ai_engine.py` 入口说明）
- 无 `src/` 目录结构、P4/P5 架构的索引链接

**建议**：应重写为当前状态，或删繁就简改为"动态入口"（链接到 `activeContext.md` 而非自行维护状态）。

### 2.2 `memory_bank/` — Memory Bank

| 文件 | 状态 | 说明 |
|------|------|------|
| `changelog.md` | ✅ **最新** | 完整记录 P1→P5.3 auto-start 全部阶段完成事件 |
| `activeContext.md` | ⛔ P5.2 冻结 | 标题 "P5.2 Overlay Integration Deferred"；Next Steps 仍在描述"Revert P5.2 experimental code" |
| `progress.md` | ⛔ P5.2 冻结 | P5 显示 "Overlay Integration deferred"；测试数 510、覆盖率 72% |
| `projectbrief.md` | ⚠️ P1 原样 | 仍描述 `ai_engine.py` 为"monolithic script (328 lines)"——实际项目已 16+ 个文件 |
| `productContext.md` | ⚠️ P1 原样 | 用户故事、约束描述仍围绕单体脚本；未提及 Dashboard 控制中心 |
| `systemPatterns.md` | ⚠️ P1 原样 | 线程模型仍为 "Thread 1 data_logger / Thread 0 ui"；无双进程模型、无 Config 系统说明 |
| `techContext.md` | ⚠️ P1 原样 | File Inventory 仍列出 `ai_engine.py` 328 行 + 6 files——实际 d 目录已到 20+ 模块 |

**核心问题**：Memory Bank 的设计假设是 `activeContext` 和 `progress` 在每个阶段结束时被维护者更新。但实际发生了"只有 changelog 被自动追加（coder 权限），其余文件停滞"的 drift。`projectbrief`/`productContext`/`systemPatterns`/`techContext` 四文件在 P1 初始化后从未更新，反映项目原始状态。

### 2.3 `Architecture/` — 架构文档

| 文件 | 状态 | 说明 |
|------|------|------|
| `System_Architecture.md` | ⛔ P3 冻结 | 描述 God Class `ai_engine.py` 为系统中心；无 P4 模块拆分、无 P5 Dashboard、无双进程 |
| `AI_Pipeline.md` | ⚠️ 部分有效 | 管线逻辑仍正确（数据采集→清洗→训练→推理），但引用 `data_logger_thread()` 等旧函数名 |
| `Data_Flow.md` | ⚠️ 部分有效 | CSV 格式、数据变换节点仍正确，但无 `CombatRecorder` / `AppConfig` / `auto_record` 等新概念 |
| `Memory_Architecture.md` | ⚠️ 部分有效 | 偏移量、指针链仍正确；引用 `ai_engine.py` 的旧读取函数而非 `MemoryReader` |

**缺失的架构文档**：
- P4 模块化重构概览（5 模块的职责和关系）
- P5 Dashboard 架构（Controller / GameService / Config / UI Tabs）
- P5.3 双进程架构总览（进程隔离、DPG/GLFW 限制、状态同步策略）
- `src/` 目录结构与模块职责矩阵
- 线程/进程模型全景图（主线程 DPG → Thread 模型 → Process 模型 演进）

### 2.4 `AI_Model/` — 模型文档

| 文件 | 状态 | 说明 |
|------|------|------|
| `Feature_Engineering.md` | ✅ 有效 | 6 特征定义、物理语义、特征重要性均正确 |
| `LightGBM_Model.md` | ⚠️ 引用旧 API | 推理示例中 `shared_state['posture']` 等已无此全局变量；其余正确 |
| `Training_Process.md` | ✅ 有效 | 超参数、训练流程、数据集规模均正确 |
| `Model_Evaluation.md` | ✅ 有效 | 评估指标、Baseline 数据有效 |

**注**：AI 模型文档总体上是最可靠的——因为 P4 重构明确不改变模型行为。仅代码示例中的实现引用（`shared_state`、`ai_engine.py` 中函数名）已过时。

### 2.5 `Game_Reverse/` — 游戏逆向

| 文件 | 状态 | 说明 |
|------|------|------|
| `Action_System.md` | ✅ 有效 | ACTION_DB / ACTION_MAPPING / Phase 分类 / Posture 规则均正确——这些是由 `src/config/actions.py` 定义的**源数据**，文档是对它的注解 |
| `Offset_System.md` | ✅ 有效 | 23 个偏移字段值均正确——`src/config/offsets.py` 的 `GameOffsets` dataclass 是权威来源 |
| `Memory_Reading.md` | ⚠️ 引用旧 API | 内存流程描述正确（zone gating、monster 遍历、enrage 读取）；但代码引用 `ai_engine.py` 的 `get_ptr()` / `find_monster()` 而非 `MemoryReader` |
| `Enrage_System.md` | ✅ 有效 | 硬件级检测原理、`enrage.py` 工具说明、逆向过程均正确 |

### 2.6 `Development/` — 开发记录

| 文件 | 状态 | 说明 |
|------|------|------|
| `Refactoring_Roadmap.md` | ⛔ P3 冻结 | P3 标记 🔄、P4-P5 📋；测试数 147、覆盖率 29% |
| `Testing_Strategy.md` | ⛔ P3 冻结 | 测试金字塔仅 P3.1-P3.4 级别，测试数过时 |
| `Development_Log.md` | 未读 | — |
| `CI_CD.md` | 未读 | — |

### 2.7 `docs/` — 项目文档

| 文件 | 状态 | 说明 |
|------|------|------|
| `architecture/ADR-P5.2-overlay-process.md` | ✅ 有效 | P5.3 双进程决策记录 |
| `architecture/ADR-P5.3-auto-start.md` | ✅ 有效 | P5.3 自动启动决策记录 |
| `research/architecture-control-center.md` | ✅ 历史参考 | P5 Dashboard 设计调研（572 行） |
| `research/architecture-p5.1-bootstrap.md` | ✅ 历史参考 | P5.1 Bootstrap 设计调研（606 行） |
| `research/ui-product-analysis.md` | ✅ 历史参考 | UI 框架选型调研（400 行） |
| `MEMORY_BANK_SPEC.md` | ⛔ P1 冻结 | 指导初始化 Memory Bank 的 spec；所有阶段限制标注为 P1 范围 |
| `Project_map.md` | ⛔ 2026-06-07 冻结 | 540 行详细文档仍描述单文件项目结构 |
| `Tech_debt.md` | ⚠️ 可能过期 | P2/P3 时的 14 项技术债清单——许多已解决（#1 offsets, #2 actions, #3 exceptions, #4 God Class），但文档状态未知 |
| `Refactoring_roadmap.md` | ⛔ P3 冻结 | 与 `Development/Refactoring_Roadmap.md` **重复**；旧版本更详细 |
| `P2_CLOSURE_REPORT.md` | ✅ 历史存档 | P2 结项 |
| `P3_HANDOFF.md` | ✅ 历史存档 | P3 交接 |
| `offsets_guide.md` | ⚠️ 未评估 | — |

---

## 3. 重复内容

| 模式 | 位置 | 重复度 |
|------|------|--------|
| "pymem 读取流程 + 指针链" | `Game_Reverse/Memory_Reading.md` vs. `Architecture/Memory_Architecture.md` | 🔴 高（两篇文章描述同一套偏移量和 API） |
| "AI 管线（采集→清洗→训练→推理）" | `Architecture/AI_Pipeline.md` vs. `Architecture/Data_Flow.md` vs. `Architecture/System_Architecture.md` | 🟡 中（三篇文章不同粒度） |
| "重构路线图" | `Development/Refactoring_Roadmap.md` vs. `docs/Refactoring_roadmap.md` | 🔴 高（summary vs. detailed，内容重叠） |

---

## 4. 应归档内容

以下文档已不再反映当前项目状态，应移至 `archive/` 而非继续维护：

| 文件 | 理由 | 替代 |
|------|------|------|
| `docs/Refactoring_roadmap.md` | 完成品（P1–P5 已全部执行） | `progress.md` 已完成概览 |
| `docs/Project_map.md` | 2026-06-07 冻结，540 行描述已淘汰架构 | `src/` 结构已在 changelog 中记录 |
| `docs/P2_CLOSURE_REPORT.md` | 历史结项报告 | 已移至 `archive/legacy_reports/`（外部的） |
| `docs/P3_HANDOFF.md` | 历史交接文档 | — |
| `Development/Refactoring_Roadmap.md` | 描述已完成的工作 | `progress.md` |
| `docs/MEMORY_BANK_SPEC.md` | P1 一次性 spec，已执行完毕 | Memory Bank 文件自身 |

**注**：`docs/research/` 下的三篇调研笔记（`architecture-control-center.md`, `architecture-p5.1-bootstrap.md`, `ui-product-analysis.md`）属于**历史参考**——它们记录了当时的架构探索过程。这些文档已完成使命，应标记为 ARCHIVED 并移至 `archive/architecture-research/`。与之对应的 ADR（`ADR-P5.2`，`ADR-P5.3`）是**当前权威决策记录**，同等保留。

---

## 5. 应保留（Keep）

| 文件 | 理由 | 需要更新？ |
|------|------|:---:|
| `changelog.md` | 唯一的完整阶段历史记录 | 否，由 coder 自动维护 |
| `AI_Model/Feature_Engineering.md` | 特征定义未变 | 轻微（删去过时的 `shared_state` 引用） |
| `AI_Model/LightGBM_Model.md` | 模型规格未变 | 轻微（同上） |
| `AI_Model/Training_Process.md` | 训练流程未变 | 否 |
| `AI_Model/Model_Evaluation.md` | 评估逻辑未变 | 否 |
| `Game_Reverse/Action_System.md` | 动作数据库是单源真相 | 否（`src/config/actions.py` 已是最新） |
| `Game_Reverse/Offset_System.md` | 偏移量是单源真相 | 否（`src/config/offsets.py` 是最新） |
| `Game_Reverse/Enrage_System.md` | 逆向发现过程记录 | 否 |
| `Game_Reverse/Memory_Reading.md` | 内存读取方法学 | 轻微（API 引用更新为 MemoryReader） |
| `docs/architecture/ADR-P5.2-overlay-process.md` | 架构决策记录 | 否 |
| `docs/architecture/ADR-P5.3-auto-start.md` | 架构决策记录 | 否（但需补充 implementation deviation 备注） |

---

## 6. 缺失的重要文档

以下主题在当前代码库中已有完整的源码/测试，但知识库中无对应文档：

### 6.1 架构系统级

| 缺失文档 | 重要性 | 说明 |
|----------|:---:|------|
| **System Architecture v2**（当前状态） | 🔴 高 | 覆盖 P4 模块拆分 + P5 Dashboard + P5.3 双进程。替代过时的 `Architecture/` 下的单文件文档 |
| **模块职责矩阵** | 🔴 高 | `src/core/`, `src/model/`, `src/data/`, `src/ui/`, `src/app/`, `src/dashboard/` 各模块的单行职责描述 + 关键 API + 测试覆盖 |
| **进程/线程模型** | 🟡 中 | 双进程架构的完整图形：Dashboard 进程（main thread DPG + GameService daemon + Recorder daemon）、Overlay 进程（main thread DPG + Recorder daemon）|
| **AppConfig 系统** | 🟡 中 | JSON 持久化设计、字段表、默认值、跨进程共享（两个进程独立加载同一个 `blackdragon_config.json`） |
| **Entry Point 选择指南** | 🟡 中 | `launch.py` vs. `overlay.py` vs. `main.py` vs. `ai_engine.py` 的场景推荐 |
| **P5.2 失败实验记录** | 🟢 低 | P5.2 三种失败方案的详细文档（目前仅在 ADR-P5.2 中简要描述） |

### 6.2 开发者文档

| 缺失文档 | 重要性 | 说明 |
|----------|:---:|------|
| **模块依赖图** | 🟡 中 | `src/` 下各包之间的 import 关系图 |
| **Testing 指南** | 🟡 中 | 更新 `Testing_Strategy.md` 到 541 tests 状态；新增每个测试文件的用途说明 |
| **真机调试指南** | 🟢 低 | 如何在没有 mock 的真实 Windows 环境下调试（MPLBACKEND、pymem 连接、DPG 窗口位置） |

---

## 7. 建议的知识库重构方案

### 7.1 立即行动（高优先级）

1. **更新 `activeContext.md` 和 `progress.md`** — 反映 P5.3 auto-start 完成状态（541 tests, 94% coverage, 双进程架构）
2. **重写 `Index.md`** — 反映当前阶段、入口点、最新指标；转向"链接型入口"而非"自维护状态型"
3. **更新 `projectbrief.md` / `productContext.md` / `techContext.md` / `systemPatterns.md`** — 至少要更新技术上下文和系统模式
4. **更新 `Architecture/System_Architecture.md`** — 反映 2026-08-04 的 src/ 模块化 + 双进程实际架构

### 7.2 中期行动（中优先级）

5. **合并重复内容** — `Memory_Reading.md` 与 `Memory_Architecture.md` 应合并或分工明确（一个讲逆向方法、一个讲当前架构）
6. **新建 `Architecture/Module_Overview.md`** — 替代过时的 `System_Architecture.md` 中的单体架构描述
7. **新建 `Development/Process_Thread_Model.md`** — 双进程模型图
8. **新建 `Development/Entry_Points.md`** — 四种 `python xxx.py` 入口的场景说明
9. **归档旧文档** — 移动 `docs/Refactoring_roadmap.md`, `docs/Project_map.md`, `docs/research/*` 到 `archive/`

### 7.3 长期行动（低优先级）

10. **建立文档更新触发** — 重大 PR 合入时自动提示归档/新建文档的 checklist
11. **分离"事实文档"和"历史文档"** — 当前目录结构混淆了两者：
    - 事实：`AI_Model/`、`Game_Reverse/`、`memory_bank/`、`docs/architecture/ADR-*`
    - 历史/调研：`Architecture/`（过时）、`docs/research/`（调研笔记）
12. **重新评估 Memory Bank 规范** — `activeContext` / `progress` 需要定期手工更新（coder 有 `changelog.md` 写入权但无架构文件写入权）。建议 architect 在阶段结束时主动触发 MB 更新，或降低 MB 维护策略（如：`Index.md` 直接链接到 `changelog.md` 最新条目）。

---

## Appendix A: File Status Matrix

| 文件 | 过时 | 有效 | 建议动作 |
|------|:---:|:---:|------|
| `Index.md` | ⛔ | | 重写 |
| `memory_bank/activeContext.md` | ⛔ | | 更新到 P5.3 auto-start |
| `memory_bank/progress.md` | ⛔ | | 更新到 P5.3 auto-start |
| `memory_bank/projectbrief.md` | ⚠️ | | 更新 |
| `memory_bank/productContext.md` | ⚠️ | | 更新 |
| `memory_bank/systemPatterns.md` | ⚠️ | | 更新 |
| `memory_bank/techContext.md` | ⚠️ | | 更新 |
| `memory_bank/changelog.md` | | ✅ | 保持 |
| `AI_Model/Feature_Engineering.md` | | ✅ | 保持 |
| `AI_Model/LightGBM_Model.md` | ⚠️ | | 轻微更新 |
| `AI_Model/Training_Process.md` | | ✅ | 保持 |
| `AI_Model/Model_Evaluation.md` | | ✅ | 保持 |
| `Game_Reverse/Action_System.md` | | ✅ | 保持 |
| `Game_Reverse/Offset_System.md` | | ✅ | 保持 |
| `Game_Reverse/Memory_Reading.md` | ⚠️ | | 轻微更新 |
| `Game_Reverse/Enrage_System.md` | | ✅ | 保持 |
| `Architecture/System_Architecture.md` | ⛔ | | 重写 |
| `Architecture/AI_Pipeline.md` | ⚠️ | | 更新 API 引用 |
| `Architecture/Data_Flow.md` | ⚠️ | | 更新 API 引用 |
| `Architecture/Memory_Architecture.md` | ⚠️ | | 更新 API 引用 |
| `Development/Refactoring_Roadmap.md` | ⛔ | | 归档 |
| `Development/Testing_Strategy.md` | ⛔ | | 重写或归档 |
| `docs/Project_map.md` | ⛔ | | 归档 |
| `docs/Tech_debt.md` | ⚠️ | | 评估更新 |
| `docs/Refactoring_roadmap.md` | ⛔ | | 归档 |
| `docs/architecture/ADR-P5.2-overlay-process.md` | | ✅ | 保持 |
| `docs/architecture/ADR-P5.3-auto-start.md` | | ✅ | 保持（需补充 implementation deviation） |
| `docs/research/*` (3 files) | | ✅ | 归档到 `archive/architecture-research/` |
| `docs/MEMORY_BANK_SPEC.md` | ⛔ | | 归档 |
| `docs/P2_CLOSURE_REPORT.md` / `P3_HANDOFF.md` | | ✅ | 移动到已有的 `archive/legacy_reports/` |
