# Legacy Documents — BlackDragon

> 本目录包含 BlackDragon v1.0 知识库重构（2026-08-04）**之前**的历史文档。
> 所有文档已通过 `git mv` **迁移归档**——**不删除，不再维护**。保留仅用于历史追溯。

---

## 不再维护声明

> [!warning] 不再维护
> 本目录下所有文档 **已停止维护**。它们描述的是 BlackDragon 早期架构（P1–P3 单体 `ai_engine.py` 时代），
> **不再反映当前系统**（P5.3 双进程架构 + `src/` 模块化）。
> 请勿将本目录内容作为开发参考——当前权威文档见各活跃目录（`Architecture/`, `AI_Model/`, `Game_Reverse/`, `Development/`）。
> 本目录仅用于：历史追溯、审计留档、技术债演变记录。

---

## 迁移记录

### Architecture → `architecture-v0/`

| 原路径 | 新路径 | 归档原因 |
|--------|--------|----------|
| `obsidian/Architecture/System_Architecture.md` | `docs/legacy/architecture-v0/System_Architecture.md` | P3 时期 God Class 单体架构描述，已被新版双进程架构取代 |
| `obsidian/Architecture/Data_Flow.md` | `docs/legacy/architecture-v0/Data_Flow.md` | P3 时期数据流描述，已被新版 `Architecture/Data_Flow.md` 取代 |
| `obsidian/Architecture/AI_Pipeline.md` | `docs/legacy/architecture-v0/AI_Pipeline.md` | 旧 AI 管线，已被 `AI_Model/Training_Pipeline.md` + `Inference_System.md` 取代 |
| `obsidian/Architecture/Memory_Architecture.md` | `docs/legacy/architecture-v0/Memory_Architecture.md` | 旧内存架构，已被 `Game_Reverse/Memory_Architecture.md` 取代 |

> 注：`System_Architecture.md` 与 `Data_Flow.md` 在 v1.0 中被重写——此处归档的为 **P3-era 旧版本**（从 git 历史 `65ac9e4` 恢复）；新版本保留在 `Architecture/` 活跃目录。

### Development → `development-v0/`

| 原路径 | 新路径 | 归档原因 |
|--------|--------|----------|
| `obsidian/Development/Refactoring_Roadmap.md` | `docs/legacy/development-v0/Refactoring_Roadmap.md` | P3 时期 5 阶段路线图，任务已全部执行，被 `Development_Roadmap.md` 取代 |
| `obsidian/Development/Development_Log.md` | `docs/legacy/development-v0/Development_Log.md` | 早期开发日志（104 行），无活跃替代，保留历史 |
| `obsidian/Development/CI_CD.md` | `docs/legacy/development-v0/CI_CD.md` | 早期 CI 配置说明（125 行），保留历史 |

### docs/ 独立文档 → `legacy/`

| 原路径 | 新路径 | 归档原因 |
|--------|--------|----------|
| `obsidian/docs/Project_map.md` | `docs/legacy/Project_map.md` | 2026-06-07 冻结，540 行描述已废弃的单文件结构 |
| `obsidian/docs/Refactoring_roadmap.md` | `docs/legacy/Refactoring_roadmap.md` | P3 制定的完整路线图，任务已全部执行完毕 |
| `obsidian/docs/Tech_debt.md` | `docs/legacy/Tech_debt.md` | P2/P3 技术债清单，多数条目（#1/#2/#3/#4）已在 P2–P5 解决 |
| `obsidian/docs/MEMORY_BANK_SPEC.md` | `docs/legacy/MEMORY_BANK_SPEC.md` | P1 一次性 Memory Bank 初始化规范，已执行完毕 |
| `obsidian/docs/P2_CLOSURE_REPORT.md` | `docs/legacy/P2_CLOSURE_REPORT.md` | P2 结项报告（历史存档） |
| `obsidian/docs/P3_HANDOFF.md` | `docs/legacy/P3_HANDOFF.md` | P3 交接文档（历史存档） |
| `obsidian/docs/offsets_guide.md` | `docs/legacy/offsets_guide.md` | 偏移量修改指南——内容仍有效，但已被 `Game_Reverse/Offset_System.md` 覆盖 |
| `obsidian/docs/PROJECT_ANALYSIS.md` | `docs/legacy/PROJECT_ANALYSIS.md` | 早期项目分析（历史存档） |

---

## 权威文档对照

| 历史文档 | 当前权威替代 |
|----------|-------------|
| `architecture-v0/System_Architecture.md` | `Architecture/System_Architecture.md` |
| `architecture-v0/AI_Pipeline.md` | `AI_Model/Training_Pipeline.md` + `AI_Model/Inference_System.md` |
| `architecture-v0/Data_Flow.md` | `Architecture/Data_Flow.md` |
| `architecture-v0/Memory_Architecture.md` | `Game_Reverse/Memory_Architecture.md` |
| `development-v0/Refactoring_Roadmap.md` | `Development/Development_Roadmap.md` |
| `development-v0/CI_CD.md` | `.github/workflows/test.yml`（CI workflow 源码） |
| `Tech_debt.md` | `Development/Development_Roadmap.md`（P6 候选任务）+ 代码现状 |
| `Refactoring_roadmap.md` | `memory_bank/progress.md` + `memory_bank/changelog.md` |
| `offsets_guide.md` | `Game_Reverse/Offset_System.md` + `src/config/offsets.py` |

---

## 保留在 docs/ 的非归档文件

以下文件 **不属于 legacy**，保留在活跃位置：

| 文件 | 说明 |
|------|------|
| `docs/architecture/ADR-P5.2-overlay-process.md`, `ADR-P5.3-auto-start.md` | 架构决策记录（活跃） |
| `docs/research/*` | P5 架构调研笔记（历史参考，活跃） |
| `docs/Knowledge_Base_Audit.md` 等 | 知识库审计/设计/审查报告（活跃） |
| `docs/出招表.txt`, `docs/招式表2.0.txt` | 动作 ID 参考表（被 `Game_Reverse/` 引用，保留） |
