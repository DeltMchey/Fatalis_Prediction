# P2 执行计划 — 高优先级技术债务修复

> **生成时间**: 2026-06-25  
> **数据来源**: `memory-bank/progress.md`（路线图）, `memory-bank/activeContext.md`, `memory-bank/systemPatterns.md`, `memory-bank/techContext.md`  
> **注意**: `PROJECT_ANALYSIS.md`、`Tech_debt.md`、`Refactoring_roadmap.md` 在磁盘上不存在。路线图信息从 `memory-bank/progress.md` 提取。

---

## 1. 来源文档状态

| 文档 | 状态 | 说明 |
|------|------|------|
| `memory-bank/progress.md` | ✅ 存在 | P2 任务定义来源（Tech_debt #1, #2, #3） |
| `memory-bank/activeContext.md` | ✅ 存在 | 仍显示 P1 为活跃阶段（已过时） |
| `memory-bank/systemPatterns.md` | ✅ 存在 | 系统架构参考 |
| `memory-bank/techContext.md` | ✅ 存在 | 技术栈与偏移量文档 |
| `PROJECT_ANALYSIS.md` | ❌ 缺失 | 被 prompt.md 引用但未创建 |
| `Tech_debt.md` | ❌ 缺失 | 被 prompt.md 引用但未创建 |
| `Refactoring_roadmap.md` | ❌ 缺失 | 被 prompt.md 引用但未创建 |

---

## 2. 路线图 P2 任务（来源: `progress.md`）

> 路线图定义 P2 = "P0 修复 (Critical Fixes)"，3 个任务，对应 Tech_debt 项目 #1, #2, #3。
> **截止 commit `cb4d218`，三个任务均已提交。**

---

### P2.1 — ✅ 已完成：将 `except: pass` 替换为结构化日志（Tech_debt #3）

| 维度 | 详情 |
|------|------|
| **目标** | 消除所有静默异常吞噬（`except: pass` / 裸 `except:`），替换为带 traceback 上下文的统一结构化日志 |
| **受影响文件** | `src/logging_config.py`（新增）、`ai_engine.py`（8 处 `except` 块全部重写） |
| **风险等级** | 🟢 低 — 仅改变错误处理路径；不改变正常执行流程 |
| **预估工作量** | ~30 分钟（已完成） |
| **验证策略** | 1. `grep -r "except:\s*pass" *.py` 在活跃代码中零命中 <br> 2. 所有 `except Exception:` 块通过 `logger.warning()` / `logger.error()` + `traceback.format_exc()` 输出 <br> 3. `python ai_engine.py` 导入成功，无崩溃 |

**Commit**: `ea143d5`

---

### P2.2 — ✅ 已完成：将 ACTION_MAPPING 统一为单一真实来源（Tech_debt #2）

| 维度 | 详情 |
|------|------|
| **目标** | 消除 `ai_engine.py` 和 `data_cleaner.py` 之间重复的 ACTION_MAPPING（原 54 项），创建 `src/config/actions.py` 作为统一数据源 |
| **受影响文件** | `src/config/actions.py`（新增，125 行）、`ai_engine.py:21-26`（导入替换内联定义）、`data_cleaner.py:14-16`（导入替换内联定义） |
| **风险等级** | 🟢 低 — 纯常量提取；两个原始源取并集 |
| **预估工作量** | ~45 分钟（已完成） |
| **验证策略** | 1. `ACTION_DB` 包含 127 个条目（两个原始源的并集）<br>2. `ACTION_MAPPING` 包含 54 项映射（原始源一致）<br>3. 两个消费者均从 `src.config.actions` 导入<br>4. `python data_cleaner.py && python train_lgbm.py` 产生相同输出 |

**Commit**: `43bfcff`

---

### P2.3 — ✅ 已完成：将内存偏移量集中到配置中（Tech_debt #1）

| 维度 | 详情 |
|------|------|
| **目标** | 将所有硬编码游戏内存偏移量集中到 `src/config/offsets.py`（`GameOffsets` 数据类），使游戏版本更新只需单点修改 |
| **受影响文件** | `src/config/offsets.py`（新增，63 行）、`ai_engine.py`（所有偏移量引用迁移至 `OFFSETS.*`）、`enrage.py`（同理）、`docs/offsets_guide.md`（新增偏移量参考文档） |
| **风险等级** | 🟢 低 — 值完全不变地迁移；冻结数据类防止运行时篡改 |
| **预估工作量** | ~45 分钟（已完成） |
| **验证策略** | 1. `grep -r "0x050139A0\|0x051238C8\|0x0500ECA0" *.py` 在活跃代码中零命中（偏移量仅在 `offsets.py` 中定义）<br>2. `OFFSETS` 实例冻结（`frozen=True`），防止运行时篡改<br>3. `python ai_engine.py` 启动并正确读取内存 |

**Commit**: `cb4d218`

---

## 3. 审计发现的残余 P2 范围工作项

> 以下项目在审计三个已完成的路线图任务时发现。每一项都属于 P2.1 或 P2.2 已确立的范围，但被原始的三项定义遗漏。

---

### 🔴 优先级 1：P2.4 — 将姿态 FSM 转移集统一到 `src/config/actions.py`

| 维度 | 详情 |
|------|------|
| **目标** | 消除 `ai_engine.py` 和 `data_cleaner.py` 之间重复的姿态状态机转移集（3 个集合 × 2 份副本 = 6 个内联集合字面量）。与 P2.2 修复的 ACTION_MAPPING 重复属于同一缺陷类别。 |
| **受影响文件** | `src/config/actions.py`（新增 3 个常量）、`ai_engine.py:222-228`（替换内联集合）、`data_cleaner.py:49-55`（替换内联集合） |
| **风险等级** | 🟢 低 — 纯常量提取；标识符完全相同，逐位验证 |
| **预估工作量** | 30 分钟 |
| **验证策略** | 1. 在 `src/config/actions.py` 中定义 `POSTURE_STAND`、`POSTURE_PRONE`、`POSTURE_FLY` 集合 <br>2. 两个消费者均导入集合 <br>3. `diff <(python data_cleaner.py 2>&1)` 前后输出行数一致 <br>4. `python -c "from src.config.actions import POSTURE_STAND, POSTURE_PRONE, POSTURE_FLY; print(len(POSTURE_STAND), len(POSTURE_PRONE), len(POSTURE_FLY))"` 确认集合非空 |
| **硬约束检查** | ✅ 无架构重构 ✅ 无模块分解 ✅ 无行为变更 ✅ 无模型变更 ✅ 无玩法变更 |

**当前重复代码位置**:

`ai_engine.py:222-228`:
```python
if action in {115, 116, 121, 122, 129, 119, 98, 99, 68, 69, 70, 71, 72, 149, 150, 151, 32, 19, 197, 219, 222}:
    shared_state['posture'] = 1
elif action in {138, 49, 50, 51, 52, 73, 30, 74, 75}:
    shared_state['posture'] = 0
elif action in {107, 108, 167, 179}:
    shared_state['posture'] = 2
```

`data_cleaner.py:49-55`（完全相同）:
```python
if action_id in {115, 116, 121, 122, 129, 119, 98, 99, 68, 69, 70, 71, 72, 149, 150, 151, 32, 19, 197, 219, 222}:
    current_posture = 1
elif action_id in {138, 49, 50, 51, 52, 73, 30, 74, 75}:
    current_posture = 0
elif action_id in {107, 108, 167, 179}:
    current_posture = 2
```

---

### 🟡 优先级 2：P2.5 — 修复 `train_lgbm.py:15` 裸 `except:`（P2.1 遗漏）

| 维度 | 详情 |
|------|------|
| **目标** | 将 `except: return print(...)` 替换为 `except Exception:` + 结构化日志。当前裸 except 会捕获 `KeyboardInterrupt`/`SystemExit`，并且完全绕过日志系统。 |
| **受影响文件** | `train_lgbm.py:15` |
| **风险等级** | 🟢 低 — 仅改变错误处理路径 |
| **预估工作量** | 5 分钟 |
| **验证策略** | 1. 将 `except:` 改为 `except Exception:`，将 `print()` 改为 `logger.error()` <br>2. 无 CSV 文件时运行 `python train_lgbm.py` → 干净退出，日志记录到 `blackdragon.log` <br>3. Ctrl+C 仍可中断脚本 |
| **硬约束检查** | ✅ 无架构重构 ✅ 无模块分解 ✅ 无行为变更 ✅ 无模型变更 ✅ 无玩法变更 |

**当前代码** (`train_lgbm.py:14-15`):
```python
    try: df = pd.read_csv("data/ML_Ready_Dataset.csv")
    except: return print("❌ 找不到 data/ML_Ready_Dataset.csv！")
```

---

### 🟢 优先级 3：P2.6 — 修复 `enrage.py` 诊断工具中的裸 `except:`

| 维度 | 详情 |
|------|------|
| **目标** | 将 `enrage.py:13,30,72` 中的 3 个裸 `except:` 替换为 `except Exception:` + 日志记录。`enrage.py` 是诊断工具（非生产路径），但在回退时仍应使用结构化日志。 |
| **受影响文件** | `enrage.py`（3 处位置：`get_ptr` L13、`find_monster` L30、扫描循环 L72） |
| **风险等级** | 🟢 极低 — 仅限诊断工具；不参与生产数据管道或推理 |
| **预估工作量** | 10 分钟 |
| **验证策略** | 1. 添加 `from src.logging_config import setup_logging` 导入 <br>2. 将 3 个裸 `except:` 替换为 `except Exception:` + 日志记录 <br>3. 无游戏运行时执行 `python enrage.py` → 优雅退出 |
| **硬约束检查** | ✅ 无架构重构 ✅ 无模块分解 ✅ 无行为变更 ✅ 无模型变更 ✅ 无玩法变更 |

---

## 4. 汇总矩阵

| 优先级 | 编号 | 任务 | 状态 | 文件 | 风险 | 工作量 | 依赖 |
|--------|------|------|--------|------|------|--------|------|
| — | P2.1 | 结构化日志替代 `except: pass` | ✅ 已完成 | `src/logging_config.py`、`ai_engine.py` | 🟢 | — | — |
| — | P2.2 | ACTION_MAPPING 统一 | ✅ 已完成 | `src/config/actions.py`、`ai_engine.py`、`data_cleaner.py` | 🟢 | — | — |
| — | P2.3 | 偏移量集中化 | ✅ 已完成 | `src/config/offsets.py`、`ai_engine.py`、`enrage.py` | 🟢 | — | — |
| 🔴 P1 | P2.4 | 统一姿态 FSM 转移集 | ⬜ 待办 | `src/config/actions.py`、`ai_engine.py:222-228`、`data_cleaner.py:49-55` | 🟢 | 30m | P2.2 |
| 🟡 P2 | P2.5 | 修复 `train_lgbm.py` 裸 except | ⬜ 待办 | `train_lgbm.py:15` | 🟢 | 5m | P2.1 |
| 🟢 P3 | P2.6 | 修复 `enrage.py` 裸 except | ⬜ 待办 | `enrage.py:13,30,72` | 🟢 | 10m | P2.1 |

---

## 5. 排好优先级的执行顺序

```
第 1 步: P2.5 (5m)   ← 最快完成；修复 P2.1 最明显的遗漏
第 2 步: P2.4 (30m)  ← 与 P2.2 相同模式；消除最后的主要常量重复
第 3 步: P2.6 (10m)  ← 低优先级；诊断工具，非生产路径
                     ──
总计剩余工作量: ~45 分钟（3 个任务）
```

---

## 6. 硬约束验证（所有待办任务）

| 约束条件 | P2.4 | P2.5 | P2.6 |
|----------|------|------|------|
| 无架构重构 | ✅ 常量提取至已有模块 | ✅ 仅修改 except 子句 | ✅ 仅修改 except 子句 |
| 无模块分解 | ✅ 添加至已有 `src/config/actions.py` | ✅ 无新模块 | ✅ 无新模块 |
| 无行为变更 | ✅ 集合值保持不变 | ✅ 仅错误处理路径 | ✅ 仅错误处理路径 |
| 无模型变更 | ✅ 训练/推理逻辑不变 | ✅ 模型加载不变 | ✅ 不涉及模型 |
| 无玩法变更 | ✅ 姿态机产生相同输出 | ✅ 无玩法逻辑变更 | ✅ 无玩法逻辑变更 |

---

## 7. 已排除（P3/P4/P5）

以下项目在 `progress.md` 中明确定义为更高级别阶段，**严格排除**在 P2 范围之外：

| 项目 | 阶段 | 排除原因 |
|------|------|----------|
| 测试套件（pytest + CI） | P3 | 路线图定义 P3 = "测试体系" |
| `ai_engine.py` 拆分为 `src/core/`, `src/data/`, `src/model/`, `src/ui/` | P4 | 路线图定义 P4 = "架构重构" |
| 模型版本管理（元数据、增量训练） | P5 | 路线图定义 P5 = "模型工程化" |
| GitHub Actions CI/CD | P3/P5 | 测试基础设施（P3），发布自动化（P5） |
| `data_upgrade.py` 重构 | P4 | 工具脚本，非关键路径 |
| `mod.py` 代码（`archive/` 中） | — | 已归档；永久排除 |

---

*由 BlackDragon P2 审计生成。未修改任何代码。*
