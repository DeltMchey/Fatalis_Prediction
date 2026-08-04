---
title: Development Roadmap
tags:
  - roadmap
  - phases
  - development
created: 2026-08-04
updated: 2026-08-04
---

# Development Roadmap — BlackDragon v1.0

> 阶段路线图概览（替代旧 Development/Refactoring_Roadmap.md）。详细阶段事件见 [[memory_bank/changelog|Changelog]]。

## 1. 已完成阶段

| Phase | 名称 | 完成时间 | 关键成果 |
|-------|------|---------|---------|
| P1 | 项目标准化 | 2026-06-22 | README, .gitignore, requirements.txt, 目录结构（tag: v0.1.0） |
| P2 | P0 关键修复 | 2026-06-25 | 统一日志、actions.py/offsets.py 单源、姿态 FSM、裸 except 清理（tag: v0.2.0） |
| P3 | 测试体系 | 2026-08-02 | 182 tests, 60% coverage, GitHub Actions CI（tag: v0.3.0） |
| P4 | 架构重构 | 2026-08-03 | 5 模块提取（StateTracker/MemoryReader/Predictor/Recorder/OverlayUI）+ main.py 组装 |
| P5 | 控制中心（Dashboard + Bootstrap） | 2026-08-03 | AppConfig/AppController/GameService/Dashboard UI/Bootstrap（v0.5.0） |
| P5.1 | Bootstrap + Game-less | 2026-08-03 | DependencyChecker、GameService、无游戏可启动 |
| P5.2 | Overlay 集成（实验——失败） | 2026-08-03 | 三种方案失败 → 确定双进程架构（ADR-P5.2）——**不投入使用** |
| P5.3 | 双进程 Overlay | 2026-08-04 | overlay.py 独立进程 + launch.py 双进程启动（541 tests, 94%） |
| P5.3-auto | 自动启动 | 2026-08-04 | auto_start_overlay + auto_record 配置（ADR-P5.3） |

## 2. 未来阶段

| Phase | 名称 | 状态 | 目标 |
|-------|------|------|------|
| P6 | 模型工程化 | Planned | Model versioning, incremental learning (`init_model`), CSV schema version, GitHub Release v1.0.0 |

### P6 候选任务

- [ ] 模型版本管理：文件名加时间戳 + metadata.json
- [ ] 增量学习：LightGBM `init_model`
- [ ] 数据 schema versioning：CSV 引入 `schema_version` 列
- [ ] 特征消融实验
- [ ] CI/CD：lint + test + release workflows
- [ ] 完整文档（安装、使用、模型训练、内存 RE 指南）
- [ ] GitHub Release v1.0.0

## 3. 关键里程碑指标

| 阶段 | Tests | Coverage | 架构状态 |
|------|:---:|:---:|---------|
| P3 | 182 | 60% | 单体 ai_engine.py |
| P4 | 385 | 72% | 5 模块提取 + main.py |
| P5.3 | 532 | 93% | 双进程 |
| P5.3-auto | 541 | 94% | 双进程 + 自动启动 |

## 4. 参考

- 历史路线图：`docs/legacy/development-v0/Refactoring_Roadmap.md`（P3 时期）
- 详细阶段事件：[[memory_bank/changelog|Changelog]]
- 版本记录：[[Development/Release_History|Release History]]
