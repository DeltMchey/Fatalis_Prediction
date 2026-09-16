---
title: Development Roadmap
tags:
  - roadmap
  - phases
  - development
created: 2026-08-04
updated: 2026-09-16
---

# Development Roadmap — BlackDragon v1.2

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
| P5.3 | 双进程 Overlay | 2026-08-04 | overlay.py 独立进程 + launch.py 双进程启动 |
| P5.3-auto | 自动启动 | 2026-08-04 | auto_start_overlay + auto_record 配置（ADR-P5.3） |
| — | v1.0.0 首发发行 | 2026-08-04 | 双进程冻结 EXE 发行包（556 tests） |
| P5.4 | 训练管线整合 | 2026-08-05 | `--pipeline` 一键 clean→train（ADR-P5.4，v1.1.0，581 tests） |
| P6/P6.1 | AutoML 模型迁移 | 2026-09-16 | FLAML Run B XGBoost 采纳为生产模型；G1–G8 门槛评审 + G5a 用户裁决；production_backend 一键训练后端；数据合并语义 + 两代备份链 + factory model；selftest 构建门禁（ADR-P6.1，v1.2.0，766 tests） |

## 2. 未来阶段 / Follow-ups

原 P6 候选任务多数已被 P6.1 覆盖或取消：

- [x] 模型版本管理 → 已落地 sidecar meta.json + 两代备份链 + factory_model（v1.2.0）
- [x] 特征消融实验 → Run A（6 列）vs Run B（12 列）对照完成
- [x] CI/CD（测试部分）→ GitHub Actions 已有；release workflow 未做
- [ ] ~~增量学习（LightGBM `init_model`）~~ → 取消：XGBoost 全量重训几秒完成，动机消失
- [ ] ~~数据 schema versioning~~ → 降级：以 `source_session` 列为界处理远古格式，告警并留在备份链

ADR-P6.1 遗留 follow-ups（本轮不动）：

- [ ] sha256 工具统一：`scripts/{adopt_model,benchmark_model,train_automl}.py` 三处副本改为 import `src/core/backup_chain.py`
- [ ] selftest helper 去重：`overlay.py _selftest()` 与 `launch.py` 内联逻辑提取共享模块
- [ ] 引入单一 `__version__` 常量（当前版本号散落在 README/包名/CHANGELOG 文本）
- [ ] sidecar 进 spec datas：`fatalis_ai_model.pkl.meta.json` 目前为组装步骤手工补入
- [ ] push / GitHub Release v1.2.0（待用户裁决）+ 用户进游戏长线实测（对照 top3_filtered 65.37%）

## 3. 关键里程碑指标

| 阶段 | Tests | 架构状态 |
|------|:---:|---------|
| P3 | 182 | 单体 ai_engine.py |
| P4 | 385 | 5 模块提取 + main.py |
| P5.3-auto | 541 | 双进程 + 自动启动 |
| v1.1.0 | 581 | + 一键训练管线 |
| v1.2.0 | **766** | + XGBoost Pipeline 生产模型 + 数据安全层 + selftest 门禁 |

## 4. 参考

- 历史路线图：`docs/legacy/development-v0/Refactoring_Roadmap.md`（P3 时期）
- 详细阶段事件：[[memory_bank/changelog|Changelog]]
- 版本记录：[[Development/Release_History|Release History]]
- 模型迁移决策：[[docs/architecture/ADR-P6.1-automl-model-migration|ADR-P6.1]]
