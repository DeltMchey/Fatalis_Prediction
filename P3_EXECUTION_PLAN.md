# P3 执行计划 — 测试与验证框架

> **日期**: 2026-06-25
> **阶段**: P3 — 测试安全网 (Test Safety Net)
> **目标**: 通过 ≥60% 总体覆盖率、核心逻辑 ≥90% 覆盖率的 pytest 套件，以及 GitHub Actions CI
> **来源**: `memory-bank/progress.md`、`memory-bank/activeContext.md`

---

## 1. 阶段概述

| 子阶段 | 名称 | 预估工作量 | 关键交付物 |
|----------|------|-----------|-------------|
| P3.1 | 测试基础设施搭建 | 0.5 天 | pytest 配置、测试目录结构、CI 工作流 |
| P3.2 | 配置模块测试（Tier 1） | 0.5 天 | `test_actions.py`、`test_offsets.py`、`test_logging.py` |
| P3.3 | 核心逻辑提取与测试（Tier 1） | 1 天 | `test_core_logic.py`（阶段、姿态、Nova、发怒、过滤逻辑） |
| P3.4 | 集成测试（Tier 2） | 1 天 | `test_data_cleaner.py`、`test_data_upgrade.py`、`test_train_lgbm.py` |
| P3.5 | CI 最终确定与覆盖验证 | 0.5 天 | CI 通过、覆盖报告、Git 标签 `v0.3.0` |
| **总计** | | **3.5 天** | |

---

## 2. 前置条件

| 前置条件 | 状态 |
|------------|--------|
| P2 结项（记录在 `docs/P2_CLOSURE_REPORT.md` 中） | ✅ |
| 常量集中化在 `src/config/` 中 | ✅ |
| 活跃代码中零裸 except | ✅ |
| 日志基础设施（`src/logging_config.py`） | ✅ |
| Python 虚拟环境（`.venv/`） | ✅ |
| `requirements.txt` | ✅ |

---

## 3. 详细执行计划

### P3.1 — 测试基础设施搭建（0.5 天）

**目标**: 搭建测试框架和 CI，不编写任何断言。

**任务**:
1. 创建 `tests/` 目录，包含 `tests/__init__.py`
2. 创建 `tests/conftest.py`，包含共享 fixtures（临时目录、示例 CSV、示例数据帧）
3. 在项目根目录创建 `pytest.ini` / `pyproject.toml` [tool.pytest.ini_options]：
   - `testpaths = ["tests"]`
   - `pythonpath = ["."]`
   - `addopts = "-v --tb=short --strict-markers"`
4. 创建 `.github/workflows/test.yml`：
   - 触发器：push、pull_request
   - Python 3.x、pip install、pytest --cov
5. 运行 `pytest --co` 验证框架能够发现测试
6. 配置 `coverage`（省略：`.venv/*`、`tests/*`、`archive/*`）

**交付物**:
- `tests/__init__.py`
- `tests/conftest.py`
- `pytest.ini` 或 `pyproject.toml` [pytest]
- `.github/workflows/test.yml`
- `pytest --co` 首次运行通过（零测试，零失败）

**风险**: 🟢 低 — 标准基础设施，无逻辑变更

---

### P3.2 — 配置模块测试（Tier 1，0.5 天）

**目标**: 对纯数据配置模块实现 100% 测试覆盖率。

**任务**:

| 测试文件 | 测试内容 |
|-----------|-----------|
| `tests/test_offsets.py` | `GameOffsets` 数据类不可变（frozen=True）；所有字段类型正确；所有字段值非空/非零；单例 `OFFSETS` 是其类的实例 |
| `tests/test_actions.py` | `ACTION_DB` 包含 127 个条目；`ACTION_MAPPING` 包含 54 个条目；每个 `ACTION_MAPPING` 键映射到 `ACTION_DB` 中存在的值；`P1_ONLY_IDS`、`P2_PLUS_IDS`、`P3_ONLY_IDS` 互不相交；`POSTURE_STAND`、`POSTURE_PRONE`、`POSTURE_FLY` 互不相交；`NOVA_THRESHOLDS` 降序排列；`SCRIPTED_IDS` 是 157..197 的连续范围；`DOWN_IDS` 与 `MINOR_AND_PASSIVE` 部分重叠（按设计文档） |
| `tests/test_logging.py` | `setup_logging()` 返回 Logger 实例；日志级别为 WARNING；FileHandler 编码为 utf-8 |

**交付物**:
- `tests/test_actions.py`（~15 个测试）
- `tests/test_offsets.py`（~8 个测试）
- `tests/test_logging.py`（~5 个测试）
- `src/config/` 覆盖率达到 ~100%

**风险**: 🟢 低 — 仅测试纯数据

---

### P3.3 — 核心逻辑提取与测试（Tier 1，1 天）

**目标**: 从 `ai_engine.py` 中提取纯函数以进行隔离测试。这是 P3 中最关键的部分。

**提取的函数**（添加至现有 `ai_engine.py` 作为模块级函数，而非创建新模块）:

| 函数 | 签名 | 测试内容 |
|----------|-----------|----------|
| `compute_phase(hp_percent: float) -> int` | `>0.78→1, >0.50→2, else→3` | 边界情况：0.78、0.50、0.0、1.0、每个阈值 ±ε |
| `check_nova_thresholds(hp_percent, triggered, thresholds) -> tuple[bool, set]` | 返回 `(is_new_nova, updated_triggered)` | 每个阈值的上升/下降交叉；重复触发被抑制 |
| `check_nova_reset(action: int) -> bool` | `action in {197, 167, 179}` | 恢复动作返回 True；其他返回 False |
| `detect_enrage(timer: float, max_val: float) -> int` | `0 < timer < max → 1 else 0` | 边界情况：0、等于 max、负数、大值 |
| `apply_posture_fsm(action: int, last_action: int) -> int | None` | 如果动作匹配 `POSTURE_*` 集合则返回新的姿态；否则返回 None | 所有 34 个姿态触发动作；未知动作 → None；相同动作不变 |
| `apply_action_mapping(raw_id: int) -> int` | `ACTION_MAPPING.get(raw, raw)` | 映射键、非映射键、负 ID |
| `compute_distance(px, pz, mx, mz) -> float` | 欧几里得距离（2D） | 零距离、已知向量、负坐标 |
| `compute_relative_angle(px, pz, mx, mz, qw, qx, qy, qz) -> float` | Yaw + 目标角 → 相对角 [-180, 180] | 正前方、后方、左侧、右侧 |
| `apply_phase_filter(probs, classes, phase) -> np.ndarray` | 根据 `P*_ONLY_IDS` 将概率置零 | 阶段 1/2/3 各自可用的动作；交叉检查无遗漏 |
| `apply_posture_filter(probs, classes, posture) -> np.ndarray` | 根据站立/趴下规则将概率置零 | 站立 vs 趴下的动作；交叉检查 |
| `renormalize_probs(probs) -> np.ndarray` | 除以总和，处理零总和 | 正常情况、全零情况、单元素 |
| `select_top_k(probs, classes, k=3, min_prob=0.03) -> list[tuple]` | argsort，按最小概率过滤 | <3 个候选、全部低于阈值、空数组 |

**交付物**:
- `tests/test_core_logic.py`（~50 个测试）
- 将纯函数提取到 `ai_engine.py` 的模块级别
- `update_logic()` 重构为使用提取的函数

**风险**: 🟡 低-中 — 提取后的函数必须产生与当前内联逻辑相同的输出。通过对比重构前后完整数据管道的输出来验证。

---

### P3.4 — 集成测试（Tier 2，1 天）

**目标**: 使用真实文件和 mini-CSV fixtures 测试数据管道组件。

**任务**:

| 测试文件 | 测试内容 |
|-----------|-----------|
| `tests/test_data_upgrade.py` | 向示例旧格式 CSV 中补充 `phase` 和 `is_enraged` 列；跳过已升级的文件；列顺序与预期匹配；升级后字段值正确 |
| `tests/test_data_cleaner.py` | 3 行 CSV → 预期转换对；动作映射应用正确；姿态 FSM 跨行推进；有效范围内排除 SCRIPTED 动作；空文件优雅处理；输出 CSV 具有预期的列和行数 |
| `tests/test_train_lgbm.py`（冒烟） | 使用 mini 数据集训练（10 行，3 类）；模型文件已创建；特征重要性图已保存；Top-3 准确率在合理范围内；类别权重应用正确 |

**交付物**:
- `tests/test_data_upgrade.py`（~10 个测试）
- `tests/test_data_cleaner.py`（~12 个测试）
- `tests/test_train_lgbm.py`（~5 个冒烟测试）
- `tests/conftest.py` 中的 Fixture 数据（示例 CSV 字符串、mini 数据帧）
- `data_cleaner.py` + `data_upgrade.py` + `train_lgbm.py` 的覆盖率

**风险**: 🟡 中等 — 集成测试创建真实的文件 I/O；需要仔细设计 fixtures。

---

### P3.5 — CI 最终确定与覆盖验证（0.5 天）

**目标**: 确保所有测试在 CI 中通过，覆盖目标达成。

**任务**:
1. 在 CI 工作流中使用 `pytest --cov=src --cov=ai_engine --cov=data_cleaner --cov=data_upgrade --cov=train_lgbm --cov-report=term --cov-report=xml` 运行测试
2. 如果覆盖率 < 60%，添加针对性的测试
3. 使用 Git 标签 `v0.3.0-test-safety-net` 进行版本标记
4. 更新 `README.md` 添加测试状态徽章
5. 使用覆盖报告更新 `memory-bank/progress.md`

**交付物**:
- 合并 PR 上 CI 通过
- 总体覆盖报告 ≥ 60%
- 核心逻辑覆盖报告 ≥ 90%
- Git 标签：`v0.3.0-test-safety-net`

**风险**: 🟢 低 — 验证阶段

---

## 4. 时间线与依赖关系

```
P3.1 基础设施搭建 ─────────────────────────────────────────────
                    │
                    ├── P3.2 配置测试 ────────────────────────
                    │                   │
                    │                   ├── P3.4 集成测试 ────
                    │                   │                   │
                    ├── P3.3 核心逻辑 ──┤                   │
                    │                                       │
                    └─────────────────── P3.5 CI 最终确定 ──┘

第 1 天: P3.1 + P3.2（并行机会：配置测试不依赖基础设施之外的其他条件）
第 2 天: P3.3（最关键路径 — 大部分测试价值来自核心逻辑）
第 3 天: P3.4（依赖 P3.2 的 fixtures，可以与 P3.3 最终确定并行）
第 4 天: P3.5 最终确定 + 缓冲
```

---

## 5. 预计覆盖贡献

| 子阶段 | 目标文件 | 预计覆盖率贡献 |
|----------|-----------|----------------------------|
| P3.2 | `src/config/actions.py`、`src/config/offsets.py`、`src/logging_config.py` | +15%（每个文件 ~100%） |
| P3.3 | `ai_engine.py`（提取的核心函数） | +25%（~50 个核心逻辑测试） |
| P3.4 | `data_cleaner.py`、`data_upgrade.py`、`train_lgbm.py` | +20%（集成测试） |
| **预计总计** | | **~60% 总体** |

---

## 6. 排除项（不在 P3 范围内）

| 项目 | 排除原因 |
|------|---------------|
| 从 `ai_engine.py` 提取完整类（StateTracker 等） | P4 架构重构 |
| `Ultimate_Radar_UI` 的 UI 测试 | 需要 dearpygui/Win32 — 手动验证 |
| `data_logger_thread()` 测试 | 需要实时游戏进程 — 手动验证 |
| `enrage.py` 测试 | 诊断工具，仅手动验证 |
| `archive/mod.py` | 已弃用，已归档 |
| 模型性能/准确性基准测试 | P5 模型工程化 |
| 跨版本偏移量验证 | 超出范围 |

---

*P3 执行计划。未修改任何代码。*
