---
title: Development Log
tags:
  - timeline
  - changelog
  - history
created: 2026-07-26
updated: 2026-07-26
---

# Development Log

## 项目发展时间线

### 起源 — 单体脚本阶段

项目最初是一个单体 Python 脚本，核心功能已经实现：
- 内存读取与覆盖层显示
- 战斗数据 CSV 录制
- LightGBM 模型训练与推理
- 两层预测架构（ML + 物理规则过滤）
- 姿态状态机和 Nova 预警

> [!note] 项目命名
> "BlackDragon"（黑龙）取自目标 Boss **Fatalis（黑龙）**——MHW 公认的最难 Boss。

---

### 2026-06-22 — v0.1.0: 项目标准化 (P1)

**提交**: `94d0bc5`

从无版本管理的单体脚本变为结构化项目。

**新增**:
- `README.md` — 项目介绍与使用指南
- `.gitignore` — 排除虚拟环境和生成文件
- `requirements.txt` — 锁定依赖版本
- `CHANGELOG.md` — 版本记录
- 目录重组: `data/`, `models/`, `archive/`, `tests/`, `docs/`
- 文件路径统一更新（CSV→data/, 模型→models/）

**验证**:
- `python data_cleaner.py` → 2447 个有效样本
- `python train_lgbm.py` → Top-3 准确率 56.17%
- `python ai_engine.py` → 可正常启动

---

### 2026-06-22 — v0.2.0: 关键修复 (P2)

#### P2.1 — 异常日志化 (Tech_debt #3)
**提交**: `ea143d5`

- 创建 `src/logging_config.py` 统一日志配置
- 替换所有 `except: pass` 为 `except Exception: logger.*()`
- 活跃代码中裸 `except:` 降至 0

#### P2.2 — ACTION_MAPPING 统一 (Tech_debt #2)
**提交**: `43bfcff`

- 创建 `src/config/actions.py` 为唯一数据源
- 合并 `ai_engine.py` 和 `data_cleaner.py` 中的映射（取并集）
- 消除两处重复定义的不一致

#### P2.3 — 偏移量配置化 (Tech_debt #1)
**提交**: `cb4d218`

- 创建 `src/config/offsets.py` (23 个字段, `frozen=True` dataclass)
- 所有硬编码十六进制偏移量替换为 `OFFSETS.*`
- 新增 `docs/offsets_guide.md` 更新指南

#### P2.4-P2.6 — 审计扩展修复
**提交**: `621a40a`

- P2.4: 统一姿态 FSM 转移集（`POSTURE_STAND`, `POSTURE_PRONE`, `POSTURE_FLY`）
- P2.5: 修复 `train_lgbm.py` 裸 except
- P2.6: 修复 `enrage.py` 裸 except（3 处）
- P2 结项报告: `docs/P2_CLOSURE_REPORT.md`

---

### 2026-06-30 — P3.1-P3.3: 测试体系建设 (P3 前 3 个子阶段)

#### P3.1 — Testing Infrastructure

**新增**:
- `tests/__init__.py`, `tests/conftest.py`（4 个 fixtures）
- `pytest.ini`（3 个 markers: slow, integration, smoke）
- `.coveragerc`（排除 .venv/, tests/, archive/）
- `.github/workflows/test.yml`（CI: Ubuntu+Windows, Python 3.11/3.12）
- `tests/test_infrastructure.py`（17 个验证测试）

#### P3.2 — Config Module Tests

**新增**:
- `tests/test_actions.py`（20 个测试）→ 100% 覆盖 `src/config/actions.py`
- `tests/test_offsets.py`（14 个测试）→ 100% 覆盖 `src/config/offsets.py`
- `tests/test_logging.py`（11 个测试）→ 100% 覆盖 `src/logging_config.py`

#### P3.3 — Core Logic Tests

**从 `ai_engine.py` 提取 8 个纯函数**:
- `calc_distance_2d`, `calc_relative_angle`, `select_top_k`（P3.3A）
- `filter_probs_by_phase`, `filter_probs_by_posture`, `renormalize_probs`, 2 个排除集合常量（P3.3B）
- `evaluate_nova`（P3.3C）

**新增**:
- `tests/test_math_logic.py`（27 个测试）
- `tests/test_phase_filter.py`（32 个测试）
- `tests/test_nova.py`（26 个测试）

**结果**: 85 个新测试，100% 通过率。ai_engine.py 覆盖率提升至 43%。

---

### 当前 — P3.4: 集成测试进行中

**目标**: 为数据管线编写集成测试，推动覆盖率 ≥ 60%

**待测试文件**:
- `data_cleaner.py`（56 行，0% 覆盖）
- `data_upgrade.py`（38 行，0% 覆盖）
- `train_lgbm.py`（52 行，0% 覆盖）

**测试指标**:

| 指标 | 当前值 |
|------|--------|
| 测试总数 | 147（7 个文件） |
| 通过率 | 100% |
| 整体覆盖率 | 29% |
| Config 模块覆盖率 | 100%（3/3 模块） |
| ai_engine.py 覆盖率 | 43% |

**阻塞项**: 无

---

## 路线图概览

```
P1 ──► P2 ──► P3 ──► P4 ──► P5
✅      ✅      🔄     📋      📋
```

| Phase | 名称 | 状态 | 工期 | 关键产物 | Tag |
|-------|------|------|------|----------|-----|
| P1 | 项目标准化 | ✅ | 2 天 | README, .gitignore, requirements.txt, 目录结构 | v0.1.0 |
| P2 | P0 关键修复 | ✅ | 3 天 | logging_config, actions.py, offsets.py | v0.2.0 |
| P3 | 测试体系 | 🔄 | 3 天 | 测试套件 ≥60% 覆盖, CI 运作 | v0.3.0 |
| P4 | 架构重构 | 📋 | 5 天 | src/core/, src/data/, src/model/, src/ui/, main.py | v0.4.0 |
| P5 | 模型工程化 | 📋 | 4 天 | 模型版本管理, 增量学习, 完整文档, GitHub Release | v1.0.0 |

## Git 提交历史

| Hash | 日期 | 描述 |
|------|------|------|
| `621a40a` | 2026-06-25 | P2.4-P2.6: Complete remaining P2 tasks + closure audit |
| `cb4d218` | 2026-06-22 | P2.3: Centralize memory offsets into src/config/offsets.py |
| `f7c9481` | 2026-06-22 | Update prompt.md: advance to P2 phase |
| `43bfcff` | 2026-06-22 | P2.2: Unify ACTION_MAPPING into single source of truth |
| `ea143d5` | 2026-06-22 | P2.1: Replace bare except:pass with structured logging |
| `94d0bc5` | 2026-06-22 | v0.1.0-project-init: Repository standardization |
