# Legacy Documents — BlackDragon

> 本目录包含 BlackDragon v1.0 知识库重构（2026-08-04）**之前**的历史文档。
> 这些文档已不再反映当前系统架构，但保留为历史记录（**不删除**，`git mv` 迁移）。

## 归档说明

| 内容 | 来源 | 归档原因 |
|------|------|----------|
| `architecture-v0/` | 旧 `obsidian/Architecture/` 目录 | P3 时期 God Class 架构描述，已被新版 `Architecture/`（双进程）取代 |
| `development-v0/` | 旧 `obsidian/Development/` 目录 | P1-P3 路线图/日志草案，已被新版 `Development/` 取代 |
| `Project_map.md` | 旧 `obsidian/docs/` | 最后更新 2026-06-07，540 行描述已废弃的单文件结构 |
| `Refactoring_roadmap.md` | 旧 `obsidian/docs/` | P3 制定的完整路线图，任务已全部执行完毕 |
| `Tech_debt.md` | 旧 `obsidian/docs/` | P2/P3 技术债清单，多数条目（#1/#2/#3/#4）已在 P2-P5 解决 |
| `MEMORY_BANK_SPEC.md` | 旧 `obsidian/docs/` | P1 一次性 Memory Bank 初始化规范，已执行完毕 |
| `P2_CLOSURE_REPORT.md` | 旧 `obsidian/docs/` | P2 结项报告（历史存档） |
| `P3_HANDOFF.md` | 旧 `obsidian/docs/` | P3 交接文档（历史存档） |
| `offsets_guide.md` | 旧 `obsidian/docs/` | 偏移量修改指南——内容仍有效，将迁移到 `Game_Reverse/` |
| `PROJECT_ANALYSIS.md` | 旧 `obsidian/docs/` | 早期项目分析（历史存档） |

## 迁移状态

> 本 README 在 v1.0 知识库 Step 1（新建文件）阶段创建。
> Step 2（移动旧文件）由 architect 确认后执行 `git mv`——**移动而非删除**。

```
状态标记：
⬜ 待移动    → 仍位于原位置
✅ 已移动    → 已位于本目录
📌 就地保留  → 内容仍有效，保持原位置（如 offsets_guide.md 迁移到 Game_Reverse/）
```

## 权威文档对照

| 历史文档 | 当前权威替代 |
|----------|-------------|
| `architecture-v0/System_Architecture.md` | `Architecture/System_Architecture.md` |
| `architecture-v0/AI_Pipeline.md` | `AI_Model/Training_Pipeline.md` + `AI_Model/Inference_System.md` |
| `architecture-v0/Data_Flow.md` | `Architecture/Data_Flow.md` |
| `architecture-v0/Memory_Architecture.md` | `Game_Reverse/Memory_Architecture.md` |
| `development-v0/Refactoring_Roadmap.md` | `Development/Development_Roadmap.md` |
| `Tech_debt.md` | `Development/Development_Roadmap.md`（P6 候选任务）+ 代码现状 |
| `Refactoring_roadmap.md` | `memory_bank/progress.md` + `memory_bank/changelog.md` |
