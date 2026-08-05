---
title: ADR Index
tags:
  - architecture
  - ADR
  - decisions
created: 2026-08-04
updated: 2026-08-05
---

# Architecture Decision Records — Index

> 架构决策记录索引。全文见 `docs/architecture/ADR-*.md`。
> **维护规则**：每新增一条 ADR，在此文件追加一行。

## ADR 列表

| ID | Title | Date | Status | Summary |
|----|-------|------|--------|---------|
| ADR-P5.2 | Overlay Architecture Decision | 2026-08-03 | Decided | 双进程架构决策：DPG 2.x / GLFW main-thread 限制迫使 Overlay 独立为子进程。三种进程内方案（多视口 / daemon 线程 / 命令队列）均失败 |
| ADR-P5.3 | Auto-Start and Recording Default | 2026-08-04 | Decided | launch.py 默认自动启动 Overlay 子进程 + `auto_record=True` 默认录制；Overlay 连接游戏采用重试循环 |
| ADR-P5.4 | Training Pipeline Integration | 2026-08-05 | Decided (revised) | 采用 `--pipeline` flag 将 data_cleaner → train_lgbm 整合为 2 步骤自动化流水线；`data_upgrade` 移除（数据格式已固定）；保留 `--train` 向后兼容；TrainingPanel UI 无变化 |

## 决策主题索引

### Overlay 架构演进（P5.2 → P5.3）

| 决策点 | ADR-P5.2 | ADR-P5.3 |
|--------|----------|----------|
| 覆盖层运行方式 | 独立子进程（`overlay.py`） | 不变 |
| Dashboard 启动行为 | 无条件 spawn overlay | `if config.auto_start_overlay: start_overlay()`（默认 True） |
| 录制默认状态 | 硬编码 `is_recording=True` | `config.auto_record`（默认 True） |
| 游戏连接时序 | 立即连接，失败退出 | 重试循环（≤60 次 × 2s） |

### 训练流水线（P5.4）

| 决策点 | ADR-P5.4 |
|--------|----------|
| 训练入口 | `--pipeline` flag（clean → train，2 步骤） |
| 子进程模型 | 单一子进程，内联两个步骤 |
| 移除模块 | `data_upgrade` 不纳入 pipeline（保留为独立工具） |
| UI 变更 | 无（PIPE 捕获机制不变） |
| 向后兼容 | `--train` flag 保留不动 |

## 关联文档

- [[docs/architecture/ADR-P5.2-overlay-process|ADR-P5.2 全文]]
- [[docs/architecture/ADR-P5.3-auto-start|ADR-P5.3 全文]]
- [[docs/architecture/ADR-P5.4-training-pipeline-integration|ADR-P5.4 全文]]
- 调研笔记（历史参考）：`docs/research/architecture-control-center.md`, `architecture-p5.1-bootstrap.md`, `ui-product-analysis.md`
