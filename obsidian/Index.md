---
title: BlackDragon AI Knowledge Hub
tags:
  - AI
  - LightGBM
  - GameAI
  - ReverseEngineering
  - MonsterHunter
  - Project
created: 2026-06-22
updated: 2026-07-26
---

# BlackDragon AI 项目

## 项目简介

BlackDragon（黑龙）是一个基于内存读取 + 机器学习的《怪物猎人世界》AI 辅助狩猎工具，专为终局 Boss **黑龙（Fatalis）** 设计。通过实时读取游戏进程内存、解析战斗状态、使用 LightGBM 模型预测 Boss 下一招，并以透明悬浮窗展示。

> [!important] 当前阶段
> **P3.4 — Integration Testing（集成测试）**。已有 147 个测试、29% 覆盖率，目标 ≥60%。

## 核心能力

- **实时内存读取**：通过 pymem 直接读取 `MonsterHunterWorld.exe` 进程内存，无需屏幕截图
- **AI 行为预测**：LightGBM 多分类模型，预测黑龙下一招，Top-3 显示
- **物理规则过滤**：两层预测架构（ML 概率 → 阶段/姿态硬过滤 → 重归一化 → Top-3）
- **战斗数据录制**：自动录制战斗数据到 CSV，每 0.1s 一行
- **Nova 飞天火预警**：血量阈值检测，提前警告终极技能
- **硬件级发怒检测**：直接读取游戏引擎内部发怒秒表，帧精度判定
- **自动化测试**：pytest 测试套件 + GitHub Actions CI

## 系统架构

- [[Architecture/System_Architecture]] — 整体系统拓扑与组件交互
- [[Architecture/AI_Pipeline]] — 完整机器学习管线
- [[Architecture/Data_Flow]] — 数据采集→清洗→训练→推理全链路
- [[Architecture/Memory_Architecture]] — pymem 读取流程与 offset 系统

## AI 模型

- [[AI_Model/LightGBM_Model]] — 模型架构、输入输出、推理流程
- [[AI_Model/Feature_Engineering]] — 6 维特征设计与姿态阶段分析
- [[AI_Model/Training_Process]] — 训练超参数、数据规模、评估过程
- [[AI_Model/Model_Evaluation]] — 准确率、Top-3 命中率、特征重要性

## 游戏逆向

- [[Game_Reverse/Memory_Reading]] — 游戏内存逆向分析方法
- [[Game_Reverse/Offset_System]] — 23 个内存偏移量字段详解
- [[Game_Reverse/Action_System]] — 动作数据库与招式映射
- [[Game_Reverse/Enrage_System]] — 硬件级发怒检测机制

## 开发状态

从 [[../memory_bank/activeContext|activeContext]] 获取当前状态：

- **当前阶段**：P3.4 — Integration Testing
- **测试总数**：147（7 个测试文件，100% 通过率）
- **覆盖率**：整体 29%，Config 模块 100%，ai_engine.py 43%
- **下一目标**：data_cleaner.py / data_upgrade.py / train_lgbm.py 集成测试
- **阻塞项**：无

### 路线图进度

| Phase | 名称 | 状态 | Tag |
|-------|------|------|-----|
| P1 | 项目标准化 | ✅ 完成 | v0.1.0 |
| P2 | P0 关键修复 | ✅ 完成 | v0.2.0 |
| P3 | 测试体系 | 🔄 进行中 | v0.3.0 |
| P4 | 架构重构 | 📋 计划中 | v0.4.0 |
| P5 | 模型工程化 | 📋 计划中 | v1.0.0 |

## 快速导航

### 核心文档
- [[../memory_bank/projectbrief|Project Brief]] — 项目身份与核心目标
- [[../memory_bank/productContext|Product Context]] — 为什么做、给谁做、怎么用
- [[../memory_bank/systemPatterns|System Patterns]] — 架构模式与设计决策
- [[../memory_bank/techContext|Tech Context]] — 技术栈与环境约束

### 开发文档
- [[Development/Development_Log]] — 项目时间线与发展历程
- [[Development/Refactoring_Roadmap]] — 5 阶段重构路线图
- [[Development/Testing_Strategy]] — 测试体系与策略
- [[Development/CI_CD]] — GitHub Actions CI 配置

### 参考文档
- [[../docs/Project_map|Project Map]] — 项目架构地图（540 行详细文档）
- [[../docs/Tech_debt|Tech Debt]] — 技术债清单（14 项）
- [[../docs/Refactoring_roadmap|Refactoring Roadmap]] — 完整重构路线图
- [[../docs/offsets_guide|Offsets Guide]] — 游戏更新后修改偏移量指南
- [[../docs/P2_CLOSURE_REPORT|P2 Closure Report]] — P2 结项报告
- [[../docs/P3_HANDOFF|P3 Handoff]] — P3 交接文档

## 技术栈

| 类别 | 技术 | 版本 |
|------|------|------|
| 语言 | Python | 3.12.6 |
| 内存读取 | Pymem | 1.14.0 |
| GUI/覆盖层 | dearpygui | 2.3 |
| ML 框架 | LightGBM | 4.6.0 |
| 数据处理 | pandas, numpy | 3.0.2, 2.4.4 |
| ML 工具 | scikit-learn | 1.8.0 |
| 可视化 | matplotlib | 3.10.9 |
| 模型持久化 | joblib | 1.5.3 |
| 测试 | pytest | — |
| CI/CD | GitHub Actions | — |
| 平台 | Windows Only | — |
