---
title: Release History
tags:
  - release
  - versions
  - history
created: 2026-08-04
updated: 2026-09-16
---

# Release History — BlackDragon v1.2

> 版本历史与关键指标演进。基于 `memory_bank/changelog.md`、根 `CHANGELOG.md` 与 git tags。

## 1. 版本表

| Version | Tag | Date | Tests | Coverage | 关键变更 |
|---------|-----|------|:---:|:---:|----------|
| v0.1.0 | `v0.1.0-project-init` | 2026-06-22 | — | — | 项目标准化：README, .gitignore, requirements.txt, 目录结构 |
| v0.2.0 | `v0.2.0-p0-fixes` | 2026-06-25 | — | — | 关键修复：统一日志、actions/offsets 单源、姿态 FSM、裸 except 清理 |
| v0.3.0 | `v0.3.0-test-safety-net` | 2026-08-02 | 182 | 60% | 测试体系：pytest 基础设施、Config/Core 纯逻辑测试、CI workflow |
| v0.4.0 | `v0.4.0-architecture-refactor` | 2026-08-03 | 385 | 72% | 架构重构：5 模块提取 + main.py 组装 |
| v0.5.0 | `v0.5.0-dashboard` | 2026-08-04 | 532 | 93% | 双进程架构：Dashboard + Overlay 独立进程 |
| P5.3-auto | — | 2026-08-04 | 541 | 94% | auto-start：自动启动 Overlay + 默认录制 |
| v1.0.0 | `v1.0.0` | 2026-08-04 | 556 | — | 首个正式发行（Fatalis_Prediction）：双进程冻结 EXE 发行包 `BlackDragon-v1.0.0-windows.zip`（118.66MB）+ release 文档 + UTF-8 hotfix |
| v1.1.0 | `v1.1.0` | 2026-08-05 | 581 | — | P5.4 训练管线整合（ADR-P5.4）：`--pipeline` 一键 clean→train、小数据集防御、冻结发行包 125.7MB |
| v1.2.0 | `v1.2.0` | 2026-09-16 | **766** | 86% | AutoML 模型迁移（ADR-P6.1）：FLAML Run B XGBoost 采纳为生产模型（top3_filtered 58.81%→65.37%，19.05MB→7.46MB）、一键训练切 Run B 后端、数据合并语义 + 两代备份链 + factory model、`--selftest` 构建门禁、冻结可观测性修复；发行包 `Fatalis-Prediction-v1.2.0-windows.zip` 159.1MB |

## 2. 测试数量演进

```
182  ── P3 (60%)
  │
385  ── P4 (72%)   +203  (5 模块提取测试)
  │
510  ── P5.2 实验   (P5 Dashboard 基线)
  │
532  ── P5.3        +22   (双进程架构测试)
  │
541  ── P5.3-auto   +9    (auto-start/auto-record 测试)
  │
556  ── v1.0.0      +15   (发行收尾)
  │
581  ── v1.1.0      +25   (P5.4 管线与防御)
  │
766  ── v1.2.0      +185  (AutoML 迁移：backup_chain / features / production_backend / 采纳与导出工具链 / 守门)
```

## 3. 关键架构里程碑

| 版本 | 架构 | 入口 |
|------|------|------|
| ≤ v0.3.0 | 单体 `ai_engine.py` God Class | `python ai_engine.py` |
| v0.4.0 | 5 模块提取 + `main.py` composition root | `python main.py` |
| v0.5.0+ | 双进程（Dashboard + Overlay） | `python launch.py` |
| v1.1.0+ | + 一键训练管线（`--pipeline`） | `python launch.py --pipeline` |
| v1.2.0 | + 生产模型换 XGBoost Pipeline（`--train` 留 LightGBM legacy） | `python launch.py --pipeline` / `--selftest` |

## 4. 维护规则

- **coder** 在每次 tag/v 版本发布时追加一行
- 数据来源：`memory_bank/changelog.md` 最新条目 + `git tag` 列表 + 根 `CHANGELOG.md`

## 5. 参考

- 完整阶段事件：[[memory_bank/changelog|Changelog]]
- 阶段路线图：[[Development/Development_Roadmap|Development Roadmap]]
- 根目录 `CHANGELOG.md`（项目根，版本发布记录）
- 发行包报告：[[docs/Release_v1.1.0_Package_Report|v1.1.0]]、[[docs/Release_v1.2.0_Package_Report|v1.2.0]]
