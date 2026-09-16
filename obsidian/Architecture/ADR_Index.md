---
title: ADR Index
tags:
  - architecture
  - ADR
  - decisions
created: 2026-08-04
updated: 2026-09-16
---

# Architecture Decision Records — Index

> 架构决策记录索引。全文见 `docs/architecture/ADR-*.md`。
> **维护规则**：每新增一条 ADR，在此文件追加一行。

## ADR 列表

| ID | Title | Date | Status | Summary |
|----|-------|------|--------|---------|
| ADR-P5.2 | Overlay Architecture Decision | 2026-08-03 | Decided | 双进程架构决策：DPG 2.x / GLFW main-thread 限制迫使 Overlay 独立为子进程。三种进程内方案（多视口 / daemon 线程 / 命令队列）均失败 |
| ADR-P5.3 | Auto-Start and Recording Default | 2026-08-04 | Decided | launch.py 默认自动启动 Overlay 子进程 + `auto_record=True` 默认录制；Overlay 连接游戏采用重试循环 |
| ADR-P5.4 | Training Pipeline Integration | 2026-08-05 | Decided (revised) | 采用 `--pipeline` flag 将 data_cleaner → train_lgbm 整合为 2 步骤自动化流水线；`data_upgrade` 移除（数据格式已固定）；保留 `--train` 向后兼容；TrainingPanel UI 无变化。（v1.2.0 起训练后端切换为 production_backend，见 ADR-P6.1 Decision 4） |
| ADR-P6.1 | AutoML Model Migration | 2026-09-16 | Accepted (implemented in v1.2.0) | FLAML AutoML 选型、Run B (XGBoost 12 列) 采纳为生产模型、G5a 内存超标用户裁决、`production_backend` 一键训练后端（`--train` 保留 legacy LightGBM）、数据合并语义 + 两代备份链 + 出厂模型、PyInstaller 冻结三课（pickle 动态引用 / xgboost 运行时 / selftest 门禁） |

## 决策主题索引

### Overlay 架构演进（P5.2 → P5.3）

| 决策点 | ADR-P5.2 | ADR-P5.3 |
|--------|----------|----------|
| 覆盖层运行方式 | 独立子进程（`overlay.py`） | 不变 |
| Dashboard 启动行为 | 无条件 spawn overlay | `if config.auto_start_overlay: start_overlay()`（默认 True） |
| 录制默认状态 | 硬编码 `is_recording=True` | `config.auto_record`（默认 True） |
| 游戏连接时序 | 立即连接，失败退出 | 重试循环（≤60 次 × 2s） |

### 训练流水线（P5.4 → P6.1）

| 决策点 | ADR-P5.4 | ADR-P6.1 |
|--------|----------|----------|
| 训练入口 | `--pipeline` flag（clean → train_lgbm） | 不变（`--pipeline`），但训练后端换为 `src/model/production_backend.py`（Run B XGBoost 配置） |
| 训练算法 | LightGBM 300 树 | XGBoost 190 树（FLAML Run B 采纳配置） |
| legacy 路径 | `--train` flag 保留不动 | 不变（`train_lgbm.py` 仍为 LightGBM） |
| 数据语义 | 全量重建数据集 | **合并语义**：保留 source_session 不在场的历史会话 |
| 数据安全 | 无备份 | 两代备份链（`.bak`/`.bak2`，same-sha 跳过）+ 不可变 `factory_model.pkl` + 训练守门告警 + 训练日志 |

### 模型迁移（P6.1 要点）

| 决策点 | 结论 |
|--------|------|
| AutoML 引擎 | FLAML 2.6.0（仅实验 CLI `scripts/train_automl.py` 用；生产推理零 flaml 依赖） |
| 生产模型 | `Pipeline[FeatureBuilder → LabelDecodedEstimator(XGBClassifier)]`，7.46MB，top3_filtered 58.81% → 65.37% |
| G5a 内存超标 | 加载 RSS +122MB > 100MB 门槛，用户 Tier 2 裁决接受（一次性增量，稳态/漂移 PASS） |
| FLAML 线程教训 | `n_jobs=-1` 必须在 FLAML 注入点覆盖（`automl.fit(n_jobs=1)`），OMP 环境变量无效 |

## 关联文档

- [[docs/architecture/ADR-P5.2-overlay-process|ADR-P5.2 全文]]
- [[docs/architecture/ADR-P5.3-auto-start|ADR-P5.3 全文]]
- [[docs/architecture/ADR-P5.4-training-pipeline-integration|ADR-P5.4 全文]]
- [[docs/architecture/ADR-P6.1-automl-model-migration|ADR-P6.1 全文]]
- 调研笔记（历史参考）：`docs/research/architecture-control-center.md`, `architecture-p5.1-bootstrap.md`, `ui-product-analysis.md`
