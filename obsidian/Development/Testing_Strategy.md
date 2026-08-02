---
title: Testing Strategy
tags:
  - testing
  - pytest
  - coverage
  - CI
created: 2026-07-26
updated: 2026-07-26
---

# Testing Strategy

## 概述

BlackDragon 的测试体系在 P3 阶段建立，目标是在 P4 大规模重构前为纯逻辑建立安全网。

## 测试金字塔

```
        ┌──────┐
        │ E2E  │  ← P5 补充（全链路游戏内测试）
       ┌┤      ├┐
       ││ 集成 ││  ← P3.4 建设中（数据管线集成测试）
       │├──────┤│
       ││ 单元 ││  ← P3.1-P3.3 已完成（纯函数 + Config）
       └┴──────┴┘
```

## 当前测试指标

| 指标 | 值 |
|------|-----|
| **测试总数** | 147（7 个文件） |
| **通过率** | 100% |
| **整体覆盖率** | 29% |
| **Config 模块覆盖率** | 100%（3/3 模块） |
| **ai_engine.py 覆盖率** | 43% |
| **CI 平台** | GitHub Actions（Ubuntu + Windows, Python 3.11/3.12） |

## 测试文件清单

| # | 文件 | 测试数 | 阶段 | 测试目标 |
|---|------|--------|------|----------|
| 1 | `test_infrastructure.py` | 17 | P3.1 | Fixtures, pytest config, CI 自检 |
| 2 | `test_actions.py` | 20 | P3.2 | ACTION_DB 完整性, 映射正确性, 集合互斥 |
| 3 | `test_offsets.py` | 14 | P3.2 | GameOffsets 字段类型, 值, 不可变性 |
| 4 | `test_logging.py` | 11 | P3.2 | setup_logging 返回, FileHandler, 编码 |
| 5 | `test_math_logic.py` | 27 | P3.3A | distance, angle 计算, top-k 选择 |
| 6 | `test_phase_filter.py` | 32 | P3.3B | Phase/posture 过滤, renormalize |
| 7 | `test_nova.py` | 26 | P3.3C | Nova 阈值 FSM（初始化/检测/重置） |

## 测试设计原则

### 1. 只测纯逻辑

不依赖游戏进程的纯函数优先测试：
- `calc_distance_2d()` — 数学计算
- `filter_probs_by_phase()` — 数组操作
- `evaluate_nova()` — 状态机

### 2. 使用 fixtures 隔离

```python
# conftest.py 提供共享 fixtures
@pytest.fixture
def sample_df():
    """5 行模拟战斗数据"""
    return pd.DataFrame({...})

@pytest.fixture
def temp_data_dir(tmp_path):
    """临时数据目录，避免污染真实 data/"""
    d = tmp_path / "data"
    d.mkdir(parents=True, exist_ok=True)
    return str(d)
```

### 3. 自定义 Markers

```ini
# pytest.ini
markers =
    slow: tests that take a long time (skipped by default)
    integration: tests that require filesystem or external data
    smoke: minimal import and structure validation
```

运行快速测试:
```bash
pytest -m "not slow" -v
```

## 待建设部分 (P3.4)

### 目标文件

| 文件 | 语句数 | 当前覆盖 | 测试方法 |
|------|--------|----------|----------|
| `data_cleaner.py` | 56 | 0% | 构造合成 CSV，验证输出列/值 |
| `data_upgrade.py` | 38 | 0% | 创建旧格式 CSV，验证升级后输出 |
| `train_lgbm.py` | 52 | 0% | 构造极小合成数据集，验证模型训练 |

### 测试要点

**data_cleaner.py**:
- 动作映射正确应用（38→37）
- 姿态状态机正确追踪
- 派生对提取正确（prev_action→next_action）
- 小动作/演出排除
- 边界 case: 空文件、全脏数据、单行数据

**data_upgrade.py**:
- Phase 回填正确（HP%→1/2/3）
- Enrage 回溯正确（怒吼+180s）
- 已升级文件跳过不重复处理
- 列序正确（timestamp, hp_percent, phase, ...）

**train_lgbm.py**:
- 罕见招式过滤（<3 次）
- 类别特征正确编码
- 模型训练成功（产物 .pkl 存在）
- early_stopping 生效

## 覆盖率目标

| 模块 | P3.4 前 | P3.4 目标 | P3.5 目标 |
|------|---------|-----------|-----------|
| `src/config/actions.py` | 100% | 100% | 100% |
| `src/config/offsets.py` | 100% | 100% | 100% |
| `src/logging_config.py` | 100% | 100% | 100% |
| `ai_engine.py` | 43% | 43% | 43% |
| `data_cleaner.py` | 0% | ≥ 70% | ≥ 70% |
| `data_upgrade.py` | 0% | ≥ 70% | ≥ 70% |
| `train_lgbm.py` | 0% | ≥ 50% | ≥ 50% |
| **整体** | **29%** | **≥ 58%** | **≥ 60%** |

## 运行测试

```bash
# 全部测试
python -m pytest tests/ -v

# 带覆盖率
python -m pytest tests/ --cov --cov-report=term

# 快速测试（跳过 slow）
python -m pytest tests/ -m "not slow" -q

# 指定文件
python -m pytest tests/test_actions.py -v
```

## CI 配置

详见 [[Development/CI_CD|CI/CD]]。

每次 push 自动触发:
- Ubuntu + Windows
- Python 3.11 + 3.12
- `pytest --cov` → 覆盖率报告
