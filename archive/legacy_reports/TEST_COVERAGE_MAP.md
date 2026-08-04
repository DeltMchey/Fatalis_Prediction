# 测试覆盖率映射 — P3

> **日期**: 2026-06-25
> **模块数**: 8 个活跃 Python 文件（不包括 `archive/`）
> **目标**: 总体 ≥ 60%，核心逻辑 ≥ 90%

---

## 1. 模块总览

| 编号 | 模块 | 行数 | 可测试性 | 主要测试类型 | 风险 | 预计覆盖率 |
|------|--------|------|------------|---------------|------|-------------------|
| M1 | `src/config/offsets.py` | 63 | 5/5 | 单元测试 | 🟢 | 100% |
| M2 | `src/config/actions.py` | 145 | 5/5 | 单元测试 | 🟢 | 100% |
| M3 | `src/logging_config.py` | 25 | 4/5 | 单元测试 | 🟢 | 100% |
| M4 | `ai_engine.py`（核心逻辑） | 299 | 3/5* | 单元测试（提取后） | 🟡 | 60%† |
| M5 | `data_cleaner.py` | 96 | 3/5 | 集成测试 | 🟡 | 85% |
| M6 | `data_upgrade.py` | 76 | 3/5 | 集成测试 | 🟡 | 80% |
| M7 | `train_lgbm.py` | 88 | 2/5 | 冒烟测试 | 🟡 | 50% |
| M8 | `enrage.py` | 92 | 1/5 | 手动验证 | 🟢 | 0% |

> \* 核心逻辑函数若提取则可达 5/5；文件整体因内存/UI 依赖为 2/5  
> † `ai_engine.py` 中提取的函数覆盖率 ≥ 90%；总体文件覆盖率因 UI/线程代码较低

---

## 2. 详细模块分析

### M1: `src/config/offsets.py` — 内存偏移量配置

| 属性 | 值 |
|----------|-------|
| **可测试性评分** | 5/5（纯冻结数据类，无副作用） |
| **推荐测试类型** | 单元测试 |
| **所需 Mock** | 无 |
| **依赖** | `dataclasses`（标准库） |
| **风险** | 🟢 低 — 仅纯数据 |

**可测试目标**:

| 目标 | 断言 | 优先级 |
|--------|----------|----------|
| `OFFSETS` 是 `GameOffsets` 的实例 | `isinstance(OFFSETS, GameOffsets)` | 🔴 高 |
| 数据类不可变 | 赋值引发 `FrozenInstanceError` | 🔴 高 |
| `PLAYER_BASE` | `isinstance(OFFSETS.PLAYER_BASE, int) and > 0` | 🟡 中 |
| `MONSTER_BASE` | `isinstance(OFFSETS.MONSTER_BASE, int) and > 0` | 🟡 中 |
| `ZONE_BASE` | `isinstance(OFFSETS.ZONE_BASE, int) and > 0` | 🟡 中 |
| `MONSTER_MAX_SLOTS` | `OFFSETS.MONSTER_MAX_SLOTS == 10` | 🟡 中 |
| `ZONE_FATALIS` | `OFFSETS.ZONE_FATALIS == 417` | 🟡 中 |
| 所有 20 个字段存在 | `len(dataclasses.fields(GameOffsets)) == 20` | 🟢 低 |

---

### M2: `src/config/actions.py` — 动作数据库

| 属性 | 值 |
|----------|-------|
| **可测试性评分** | 5/5（纯数据：字典、集合、列表） |
| **推荐测试类型** | 单元测试 |
| **所需 Mock** | 无 |
| **依赖** | 无（仅标准库） |
| **风险** | 🟢 低 — 仅纯数据 |

**可测试目标**:

| 目标 | 断言 | 优先级 |
|--------|----------|----------|
| `ACTION_DB` 有 127 个条目 | `len(ACTION_DB) == 127` | 🔴 高 |
| `ACTION_MAPPING` 有 54 个条目 | `len(ACTION_MAPPING) == 54` | 🔴 高 |
| 映射键存在于 DB 中 | `all(k in ACTION_DB for k in ACTION_MAPPING)` | 🔴 高 |
| 映射值存在于 DB 中 | `all(v in ACTION_DB for v in ACTION_MAPPING.values())` | 🔴 高 |
| P1/P2/P3 互不相交 | `P1 & P2 == P2 & P3 == P1 & P3 == set()` | 🔴 高 |
| POSTURE 集合互不相交 | `STAND & PRONE == PRONE & FLY == STAND & FLY == set()` | 🔴 高 |
| `NOVA_THRESHOLDS` 降序排列 | `all(NOVA_THRESHOLDS[i] > NOVA_THRESHOLDS[i+1] ...)` | 🟡 中 |
| `SCRIPTED_IDS` 范围 | `SCRIPTED_IDS == set(range(157, 198))` | 🟡 中 |
| `POSTURE_STAND` 有 21 个 ID | `len(POSTURE_STAND) == 21` | 🟡 中 |
| `POSTURE_PRONE` 有 9 个 ID | `len(POSTURE_PRONE) == 9` | 🟡 中 |
| `POSTURE_FLY` 有 4 个 ID | `len(POSTURE_FLY) == 4` | 🟡 中 |
| 所有 ID 均为正整数 | `all(isinstance(k, int) and k > 0 ...)` | 🟢 低 |
| `NOVA_THRESHOLDS` 有 5 个阈值 | `len(NOVA_THRESHOLDS) == 5` | 🟢 低 |

---

### M3: `src/logging_config.py` — 日志配置

| 属性 | 值 |
|----------|-------|
| **可测试性评分** | 4/5（工厂函数，轻微的 `basicConfig` 副作用） |
| **推荐测试类型** | 单元测试 |
| **所需 Mock** | `logging.basicConfig`（可选，用于隔离） |
| **依赖** | `logging`（标准库） |
| **风险** | 🟢 低 |

**可测试目标**:

| 目标 | 断言 | 优先级 |
|--------|----------|----------|
| 返回 Logger 实例 | `isinstance(logger, logging.Logger)` | 🔴 高 |
| 日志级别为 WARNING | `logger.level == logging.WARNING` | 🟡 中 |
| 名称参数已使用 | `logger.name == "BlackDragon"` | 🟡 中 |
| FileHandler 存在 | `any(isinstance(h, logging.FileHandler) for h in logger.handlers)` | 🟡 中 |
| FileHandler 编码为 utf-8 | handler 编码检查 | 🟢 低 |

---

### M4: `ai_engine.py` — 主程序（299 行）

| 属性 | 值 |
|----------|-------|
| **可测试性评分** | 3/5（核心逻辑，2/5 整体） |
| **推荐测试类型** | 单元测试（提取的函数）+ 烟雾测试（导入）+ 手动验证（UI/内存） |
| **所需 Mock** | `pymem`、`dearpygui`、`joblib`、`ctypes.windll` |
| **依赖** | `pymem`、`dearpygui`、`pandas`、`numpy`、`joblib`、`ctypes`（Win32）、`threading` |
| **风险** | 🟡 高 — 核心业务逻辑；测试覆盖关键 |

**可测试目标 — 核心逻辑函数（提取用于测试）**:

| 函数 | 输入 | 输出 | 可测试性 | 优先级 |
|----------|------|--------|------------|----------|
| `compute_phase(hp)` | HP 百分比浮点数 | 阶段 int | 5/5 | 🔴 高 |
| `check_nova_thresholds(hp, triggered, thresholds)` | HP + 已触发集合 | `(bool, set)` | 5/5 | 🔴 高 |
| `check_nova_reset(action)` | 动作 ID int | bool | 5/5 | 🔴 高 |
| `detect_enrage(timer, max_val)` | 发怒计时器浮点数 + 最大值 | 0 或 1 | 5/5 | 🔴 高 |
| `apply_posture_fsm(action, last_action)` | 两个动作 ID | 新姿态或 None | 5/5 | 🔴 高 |
| `apply_action_mapping(raw_id)` | 原始帧 ID | 基础 ID | 5/5 | 🔴 高 |
| `compute_distance(px, pz, mx, mz)` | 4 个浮点数坐标 | 浮点数 | 5/5 | 🟡 中 |
| `compute_relative_angle(px, pz, mx, mz, qw, qx, qy, qz)` | 8 个浮点数 | 角度 [-180,180] | 4/5 | 🟡 中 |
| `apply_phase_filter(probs, classes, phase)` | 概率数组 + 类别 + 阶段 | 过滤后的概率 | 4/5 | 🔴 高 |
| `apply_posture_filter(probs, classes, posture)` | 概率数组 + 类别 + 姿态 | 过滤后的概率 | 4/5 | 🔴 高 |
| `renormalize_probs(probs)` | 概率数组 | 归一化概率 | 5/5 | 🟡 中 |
| `select_top_k(probs, classes, k, min_p)` | 概率 + 类别 + k + 阈值 | (action, prob) 元组列表 | 5/5 | 🟡 中 |

**不可测试（手动验证）**:

| 组件 | 原因 |
|----------|--------|
| `get_ptr()` | 需要 pymem `read_longlong` — 无法在无游戏进程的情况下进行单元测试 |
| `find_monster()` | 需要 pymem + 游戏内存布局 |
| `data_logger_thread()` | 需要 pymem、线程、文件 I/O、`shared_state` 全局变量 |
| `Ultimate_Radar_UI.__init__()` | 需要 `dearpygui`、`ctypes.windll`、字体文件 |
| `Ultimate_Radar_UI.update_logic()` | 深度耦合 pymem 读取 + dearpygui UI 更新 |
| `Ultimate_Radar_UI.run()` | dearpygui 渲染循环 |
| `main()` | 需要实时游戏进程 `MonsterHunterWorld.exe` |

---

### M5: `data_cleaner.py` — ETL 管道

| 属性 | 值 |
|----------|-------|
| **可测试性评分** | 3/5（文件 I/O + 复杂状态机，但逻辑确定） |
| **推荐测试类型** | 集成测试（带 mini-CSV fixtures） |
| **所需 Mock** | 临时文件系统（`tmp_path` / `tmpdir`），示例原始 CSV 文件 |
| **依赖** | `pandas`、`glob`、`src.config.actions` |
| **风险** | 🟡 中 — 核心数据管道；错误会破坏 ML 训练数据 |

**可测试目标**:

| 目标 | 方法 | 优先级 |
|--------|------|----------|
| 空输入 → 空输出 | 0 个 CSV 文件 | 🔴 高 |
| 单行 CSV → 1 个转换 | 1 行动作对，验证输出 | 🔴 高 |
| 动作映射已应用 | 原始 ID 54 → 基础 ID 53 | 🔴 高 |
| SCRIPTED 动作已排除 | 动作 157–197 不出现在输出中 | 🔴 高 |
| MINOR_AND_PASSIVE 动作已排除 | 非战斗动作已过滤 | 🔴 高 |
| 姿态 FSM 正确转换 | 站立 → 趴下 → 飞行 → … | 🔴 高 |
| 倒地发呆 → 趴下 | DOWN_IDS 后跟 306/307/308 → 姿态 0 | 🟡 中 |
| 距离过滤器（< 5000） | 距离 > 5000 的行已丢弃 | 🟡 中 |
| action_id 过滤器（!= 1） | action_id == 1 的行已丢弃 | 🟡 中 |
| 输出 CSV 格式 | 列名与预期匹配 | 🟢 低 |
| 损坏的 CSV 被跳过 | 畸形 CSV 不崩溃管道 | 🟢 低 |

---

### M6: `data_upgrade.py` — 旧版 CSV 升级器

| 属性 | 值 |
|----------|-------|
| **可测试性评分** | 3/5（文件 I/O + pandas，逻辑简单） |
| **推荐测试类型** | 集成测试（带旧格式 CSV fixtures） |
| **所需 Mock** | 临时文件系统，示例旧版 CSV（无 `phase`/`is_enraged` 列） |
| **依赖** | `pandas`、`glob` |
| **风险** | 🟡 中 — 错误可能损坏历史数据文件 |

**可测试目标**:

| 目标 | 方法 | 优先级 |
|--------|------|----------|
| 阶段计算 | hp% > 0.78 → 1, ≤0.78 → 2, ≤0.50 → 3 | 🔴 高 |
| 发怒定时器回填 | 愤怒吼叫（4,5,179）→ +180s 发怒窗口 | 🔴 高 |
| 跳过已升级 | `phase` + `is_enraged` 存在 → 无变更 | 🟡 中 |
| 列重排序 | 输出列顺序与预期匹配 | 🟡 中 |
| 空目录 | 零个 CSV → 不崩溃 | 🟢 低 |

---

### M7: `train_lgbm.py` — 模型训练

| 属性 | 值 |
|----------|-------|
| **可测试性评分** | 2/5（ML 训练，重度依赖，非确定性） |
| **推荐测试类型** | 冒烟测试 + 集成测试（mini 数据集） |
| **所需 Mock** | 示例 `ML_Ready_Dataset.csv`（10 行 × 3 类）；可能需 mock `lightgbm.train` 以提升速度 |
| **依赖** | `pandas`、`numpy`、`lightgbm`、`scikit-learn`、`matplotlib`、`joblib` |
| **风险** | 🟡 中 — 模型输出变化影响预测 |

**可测试目标**:

| 目标 | 方法 | 优先级 |
|--------|------|----------|
| CSV 存在 → 训练运行 | mini 数据集，3 类各 3+ 样本 | 🔴 高 |
| 模型文件已创建 | `models/fatalis_ai_model.pkl` 在训练后存在 | 🔴 高 |
| 特征重要性图已保存 | `models/feature_importance.png` 存在 | 🟡 中 |
| CSV 缺失 → 错误已记录 | 移除 CSV，检查日志 | 🟡 中 |
| 类别计数过滤 (≥ 3) | 出现 < 3 次的类别已丢弃 | 🟡 中 |
| 分类特征已设置 | `posture`、`previous_action`、`phase`、`is_enraged` 设置为 category dtype | 🟢 低 |
| LightGBM 参数已验证 | `num_leaves=63`、`max_depth=7` 等 | 🟢 低 |

---

### M8: `enrage.py` — 诊断内存扫描器

| 属性 | 值 |
|----------|-------|
| **可测试性评分** | 1/5（每个函数都依赖 pymem，无限 `while True` 循环） |
| **推荐测试类型** | 手动验证 |
| **所需 Mock** | 不实际 — 整文件需要实时游戏进程 |
| **依赖** | `pymem`、`src.config.offsets` |
| **风险** | 🟢 低 — 诊断工具，无生产影响 |

**可测试目标**: 无 — 手动验证。通过检查导入成功（`python -c "import enrage"`）来验证语法正确性。

---

## 3. 预计覆盖率细分

| 层 | 模块 | 预计覆盖率 |
|-----|--------|-------------------|
| **Tier 1** | M1 偏移量 | 100% |
| **Tier 1** | M2 动作 | 100% |
| **Tier 1** | M3 日志 | 100% |
| **Tier 1** | M4 核心逻辑（提取的函数） | 95% |
| **Tier 2** | M5 data_cleaner | 85% |
| **Tier 2** | M6 data_upgrade | 80% |
| **Tier 2** | M7 train_lgbm（冒烟测试） | 50% |
| **Tier 3** | M4 ai_engine（完整文件） | 40%* |
| **Tier 3** | M8 enrage | 0%（手动） |
| **总体加权** | | **~62%** |

> \* Tier 1 提取的函数覆盖其逻辑；完整文件覆盖率因 UI/线程代码较低

---

## 4. 覆盖率缺口（不在 P3 范围内）

| 缺口 | 行数 | 为何无法测试 | 何时填补 |
|------|-------|-------------------|-----------|
| `Ultimate_Radar_UI.__init__()` | 41 行 | dearpygui + Win32 依赖 | P4（架构重构 + 依赖注入） |
| `Ultimate_Radar_UI.update_logic()` | 123 行 | 内存读取 + UI 更新深度耦合 | P4 |
| `data_logger_thread()` | 50 行 | pymem + 线程 + 全局状态 | P4 |
| `main()` | 13 行 | 游戏进程 | 手动验证 |
| `get_ptr()` + `find_monster()` | 25 行 | pymem 依赖 | P4（提取 MemoryReader 类时进行集成测试） |
| `enrage.py` — 全部 | 92 行 | 诊断工具 | 手动验证 |

---

*测试覆盖率映射。未修改任何代码。未生成任何测试。*
