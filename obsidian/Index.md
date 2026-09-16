---
title: BlackDragon AI Knowledge Hub
tags:
  - AI
  - XGBoost
  - GameAI
  - ReverseEngineering
  - MonsterHunter
  - Project
created: 2026-06-22
updated: 2026-09-16
---

# BlackDragon 知识库

> 本页是知识库**导航中枢**。当前阶段、测试数、覆盖率等**状态数据**由 Memory Bank 维护，本页只负责路由（不自行维护状态）。

## 我是谁

BlackDragon（黑龙）是一个基于内存读取 + 机器学习的《怪物猎人世界》AI 辅助狩猎工具，专为终局 Boss **黑龙（Fatalis）** 设计。通过实时读取游戏进程内存、解析战斗状态、使用 XGBoost 模型（v1.2.0 起，AutoML 迁移自 LightGBM，ADR-P6.1）预测 Boss 下一招，并以透明悬浮窗展示。

- 项目身份：[[memory_bank/projectbrief|Project Brief]]
- 产品背景：[[memory_bank/productContext|Product Context]]

## 当前状态

> 状态数据以下方 Memory Bank 文件为准（每次任务结束由 coder/architect 更新）。

- 当前阶段 / 目标：[[memory_bank/activeContext|Active Context]]
- 阶段任务清单：[[memory_bank/progress|Progress]]
- 阶段完成事件：[[memory_bank/changelog|Changelog]]

## 快速导航

### 架构

- [[Architecture/System_Architecture|System Architecture]] — 系统拓扑与组件交互
- [[Architecture/Module_Design|Module Design]] — 模块职责矩阵与关键 API
- [[Architecture/Process_Architecture|Process Architecture]] — 双进程 / 线程模型与生命周期
- [[Architecture/Data_Flow|Data Flow]] — 数据全链路（采集 → 清洗 → 训练 → 推理）
- [[Architecture/ADR_Index|ADR Index]] — 架构决策记录索引

### AI 模型

- [[AI_Model/LightGBM_Model|Production Model]] — 生产模型规格（XGBoost Pipeline；含 LightGBM legacy 小节）
- [[AI_Model/Training_Pipeline|Training Pipeline]] — 完整训练管线
- [[AI_Model/Feature_Engineering|Feature Engineering]] — 特征设计（6 用户指定 + 6 派生 = 12 列）
- [[AI_Model/Inference_System|Inference System]] — 推理系统与两层预测架构

### 游戏逆向

- [[Game_Reverse/Memory_Architecture|Memory Architecture]] — 内存结构与读取
- [[Game_Reverse/Offset_System|Offset System]] — 偏移量系统
- [[Game_Reverse/Combat_State|Combat State]] — 战斗状态系统（动作/姿态/阶段/发怒/Nova）

### 开发

- [[Development/Development_Roadmap|Development Roadmap]] — 阶段路线图
- [[Development/Release_History|Release History]] — 版本历史与指标演进
- [[Development/Testing_Strategy|Testing Strategy]] — 测试体系

## 入口点

| 命令 | 用途 | 备注 |
|------|------|------|
| `python launch.py` | Dashboard + Overlay 双进程（推荐） | P5.3 自动启动 Overlay |
| `python launch.py --pipeline` | 一键训练（清洗 → XGBoost Run B 重训） | v1.2.0 推荐训练入口 |
| `python launch.py --train` | LightGBM 训练 | legacy（向后兼容） |
| `--selftest`（双 EXE） | 路径解析 + 模型加载 + 推理自检 | v1.2.0 构建门禁 |
| `python overlay.py` | 仅覆盖层进程 | 独立 DPG 进程 |
| `python main.py` | P4 独立 overlay | legacy（P4.6 composition root） |
| `python ai_engine.py` | God Class | legacy（P3 测试兼容入口） |

## 技术栈

详见 [[memory_bank/techContext|Tech Context]]：

| 类别 | 技术 | 版本 |
|------|------|------|
| 语言 | Python | 3.11+ |
| 内存读取 | pymem | Windows-only |
| GUI/覆盖层 | dearpygui | 2.3 |
| ML 框架（生产） | XGBoost | 3.4.1（v1.2.0 起） |
| ML 框架（legacy 训练） | LightGBM | 4.6.0（`--train` 路径保留） |
| AutoML（仅实验） | FLAML | 2.6.0（scripts/train_automl.py） |
| 数据处理 | pandas, numpy | — |
| 平台 | Windows | 专用 |

## 历史参考

- 架构调研笔记：[[docs/research/architecture-control-center|Control Center 调研]] 等（P5 设计期）
- 历史审计：[[docs/Knowledge_Base_Audit|Knowledge Base Audit]]
- 知识库 v1.0 设计：[[docs/Knowledge_Base_v1_Architecture|KB v1.0 Architecture]]
