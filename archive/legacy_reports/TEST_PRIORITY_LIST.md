# 测试优先级列表 — P3

> **日期**: 2026-06-25
> **原则**: 先易后难。先高价值后低价值。先无外部依赖后有外部依赖。

---

## 三层分类

| 层级 | 定义 | 模块数 | 预计测试数 | 预计覆盖率贡献 |
|------|------------|-------------|-----------------|----------------------------|
| **Tier 1** — 易于测试 | 纯函数、纯数据。无 mock 或最少 mock。即时反馈。 | 4 | ~75 | +40% |
| **Tier 2** — 需要 mock | 文件 I/O、pandas、lightgbm。需要 fixtures 和临时文件。 | 3 | ~27 | +20% |
| **Tier 3** — 仅手动验证 | 游戏内存、GUI、线程、Win32 API。不适合自动化。 | 2 | 0 | 0%（手动检查表） |

---

## Tier 1: 易于测试（按执行顺序排列）

### 批次 1A: 配置模块（P3.2，0.5 天）

这些文件是**纯数据**——不可能出错，但测试成本极低，并且是 Tier 1 批次其余部分的构建块。

#### 优先级 1 — `tests/test_offsets.py`（~8 个测试，15 分钟）

**为何先测**: 零依赖。冻结数据类。测试运行 < 1 秒。

| 编号 | 测试 | 断言 |
|------|------|----------|
| 1.1 | `test_offsets_is_singleton` | `OFFSETS` 是 `GameOffsets` 的实例 |
| 1.2 | `test_offsets_frozen` | 属性赋值引发 `FrozenInstanceError` |
| 1.3 | `test_offsets_player_base` | `PLAYER_BASE == 0x050139A0` |
| 1.4 | `test_offsets_monster_base` | `MONSTER_BASE == 0x051238C8` |
| 1.5 | `test_offsets_zone_base` | `ZONE_BASE == 0x0500ECA0` |
| 1.6 | `test_offsets_zone_fatalis` | `ZONE_FATALIS == 417` |
| 1.7 | `test_offsets_max_slots` | `MONSTER_MAX_SLOTS == 10` |
| 1.8 | `test_offsets_field_count` | `GameOffsets` 中的字段数 >= 20 |

#### 优先级 2 — `tests/test_actions.py`（~15 个测试，30 分钟）

**为何先测**: 零依赖。每个其他模块都从该文件导入。如果常量错误，所有其他测试都会失败。

| 编号 | 测试 | 断言 |
|------|------|----------|
| 2.1 | `test_action_db_size` | `len(ACTION_DB) == 127` |
| 2.2 | `test_action_mapping_size` | `len(ACTION_MAPPING) == 54` |
| 2.3 | `test_mapping_keys_in_db` | `ACTION_MAPPING` 的每个键都是 `ACTION_DB` 的键 |
| 2.4 | `test_mapping_values_in_db` | `ACTION_MAPPING` 的每个值都是 `ACTION_DB` 的键 |
| 2.5 | `test_phase_sets_disjoint` | `P1_ONLY & P2_PLUS == P2_PLUS & P3_ONLY == P1_ONLY & P3_ONLY == set()` |
| 2.6 | `test_posture_sets_disjoint` | `STAND & PRONE == PRONE & FLY == STAND & FLY == set()` |
| 2.7 | `test_posture_stand_size` | `len(POSTURE_STAND) == 21` |
| 2.8 | `test_posture_prone_size` | `len(POSTURE_PRONE) == 9` |
| 2.9 | `test_posture_fly_size` | `len(POSTURE_FLY) == 4` |
| 2.10 | `test_nova_thresholds_descending` | `NOVA_THRESHOLDS` 严格降序排列 |
| 2.11 | `test_nova_thresholds_count` | `len(NOVA_THRESHOLDS) == 5` |
| 2.12 | `test_scripted_ids_range` | `SCRIPTED_IDS == set(range(157, 198))` |
| 2.13 | `test_down_ids_non_empty` | `len(DOWN_IDS) > 0` |
| 2.14 | `test_minor_and_passive_non_empty` | `len(MINOR_AND_PASSIVE) > 0` |
| 2.15 | `test_all_ids_positive_integers` | 所有集合中的所有 ID 均为 `int` 且 `> 0` |

#### 优先级 3 — `tests/test_logging.py`（~5 个测试，10 分钟）

| 编号 | 测试 | 断言 |
|------|------|----------|
| 3.1 | `test_logger_is_logger` | `isinstance(logger, logging.Logger)` |
| 3.2 | `test_logger_name` | `logger.name == "BlackDragon"` |
| 3.3 | `test_logger_level_warning` | `logger.level == logging.WARNING` |
| 3.4 | `test_logger_has_file_handler` | 至少存在一个 `FileHandler` |
| 3.5 | `test_logger_handler_encoding` | FileHandler 编码为 `utf-8` |

---

### 批次 1B: 从 ai_engine.py 提取的核心逻辑（P3.3，1 天）

这些函数**必须先从 `ai_engine.py` 中提取**为模块级函数（不创建新模块 - 那是 P4）。每个函数都有一个清晰、可测试的签名，不依赖游戏内存。

#### 优先级 4 — `tests/test_core_phase.py`（~10 个测试，20 分钟）

**提取**: `compute_phase(hp_percent: float) -> int`

| 编号 | 测试 | 输入 | 预期 |
|------|------|------|--------|
| 4.1 | `test_phase_1_full_hp` | 1.0 | 1 |
| 4.2 | `test_phase_1_above_78` | 0.79 | 1 |
| 4.3 | `test_phase_1_boundary` | 0.7800001 | 1 |
| 4.4 | `test_phase_2_boundary` | 0.78 | 2 |
| 4.5 | `test_phase_2_mid` | 0.64 | 2 |
| 4.6 | `test_phase_2_above_50` | 0.51 | 2 |
| 4.7 | `test_phase_3_boundary` | 0.50 | 3 |
| 4.8 | `test_phase_3_low` | 0.25 | 3 |
| 4.9 | `test_phase_3_min` | 0.0 | 3 |
| 4.10 | `test_phase_3_negative`（边缘情况） | -1.0 | 3 |

#### 优先级 5 — `tests/test_core_nova.py`（~10 个测试，20 分钟）

**提取**: `check_nova_thresholds(hp, triggered, thresholds) -> tuple[bool, set]`、`check_nova_reset(action) -> bool`

| 编号 | 测试 | 输入 | 预期 |
|------|------|------|--------|
| 5.1 | `test_nova_trigger_first` | hp=0.77, triggered=set() | `(True, {0.78})` |
| 5.2 | `test_nova_no_retrigger` | hp=0.77, triggered={0.78} | `(False, {0.78})` |
| 5.3 | `test_nova_second_threshold` | hp=0.49, triggered={0.78} | `(True, {0.78, 0.50})` |
| 5.4 | `test_nova_all_thresholds` | hp=0.03, triggered=set() | 全部 5 个已触发 |
| 5.5 | `test_nova_above_all` | hp=0.90, triggered=set() | `(False, set())` |
| 5.6 | `test_nova_below_all` | hp=0.01, triggered=set() | 全部 5 个已触发 |
| 5.7 | `test_nova_reset_action_197` | action=197 | `True` |
| 5.8 | `test_nova_reset_action_167` | action=167 | `True` |
| 5.9 | `test_nova_reset_action_179` | action=179 | `True` |
| 5.10 | `test_nova_reset_other` | action=37（龙车） | `False` |

#### 优先级 6 — `tests/test_core_enrage.py`（~8 个测试，15 分钟）

**提取**: `detect_enrage(timer: float, max_val: float) -> int`

| 编号 | 测试 | 输入 | 预期 |
|------|------|------|--------|
| 6.1 | `test_enrage_active_mid` | timer=50.0, max_val=120.0 | 1 |
| 6.2 | `test_enrage_active_just_started` | timer=0.001, max_val=120.0 | 1 |
| 6.3 | `test_enrage_inactive_timer_zero` | timer=0.0, max_val=120.0 | 0 |
| 6.4 | `test_enrage_inactive_timer_equals_max` | timer=120.0, max_val=120.0 | 0 |
| 6.5 | `test_enrage_inactive_timer_exceeds_max` | timer=121.0, max_val=120.0 | 0 |
| 6.6 | `test_enrage_inactive_negative_timer` | timer=-5.0, max_val=120.0 | 0 |
| 6.7 | `test_enrage_inactive_zero_max` | timer=5.0, max_val=0.0 | 0 |
| 6.8 | `test_enrage_inactive_both_zero` | timer=0.0, max_val=0.0 | 0 |

#### 优先级 7 — `tests/test_core_posture.py`（~10 个测试，20 分钟）

**提取**: `apply_posture_fsm(action: int, last_action: int) -> int | None`

| 编号 | 测试 | 输入 | 预期 |
|------|------|------|--------|
| 7.1 | `test_posture_to_standing` | 每个 `POSTURE_STAND` 中的 ID | 返回 1 |
| 7.2 | `test_posture_to_prone` | 每个 `POSTURE_PRONE` 中的 ID | 返回 0 |
| 7.3 | `test_posture_to_flying` | 每个 `POSTURE_FLY` 中的 ID | 返回 2 |
| 7.4 | `test_posture_same_action_no_change` | action==last_action | 返回 None |
| 7.5 | `test_posture_unknown_action` | action=99999 | 返回 None |
| 7.6 | `test_posture_negative_action` | action=-1 | 返回 None |
| 7.7 | `test_posture_last_action_negative` | action=115, last_action=-1 | None（last_action == -1 被跳过） |

#### 优先级 8 — `tests/test_core_mapping.py`（~5 个测试，10 分钟）

**提取**: `apply_action_mapping(raw_id: int) -> int`

| 编号 | 测试 | 输入 | 预期 |
|------|------|------|--------|
| 8.1 | `test_mapping_known` | raw=38 | 37（龙车动画帧 → 基础） |
| 8.2 | `test_mapping_known_deep` | raw=54 | 53（连咬动画帧） |
| 8.3 | `test_mapping_unknown` | raw=37（已为基础 ID） | 37（通过） |
| 8.4 | `test_mapping_invalid` | raw=99999 | 99999（通过） |
| 8.5 | `test_mapping_negative` | raw=-1 | -1（通过） |

#### 优先级 9 — `tests/test_core_geometry.py`（~8 个测试，15 分钟）

**提取**: `compute_distance(px, pz, mx, mz) -> float`、`compute_relative_angle(...) -> float`

| 编号 | 测试 | 输入 | 预期 |
|------|------|------|--------|
| 9.1 | `test_distance_zero` | (0,0, 0,0) | 0.0 |
| 9.2 | `test_distance_same_point` | (10,5, 10,5) | 0.0 |
| 9.3 | `test_distance_positive` | (0,0, 3,4) | 5.0（3-4-5 三角形） |
| 9.4 | `test_distance_negative_coords` | (-1,-1, 2,3) | 5.0 |
| 9.5 | `test_angle_in_front` | 玩家在怪物前方 | 0° ± ε |
| 9.6 | `test_angle_behind` | 玩家在怪物后方 | 180° ± ε |
| 9.7 | `test_angle_range` | 各种角度 | 始终在 [-180, 180] 范围内 |

#### 优先级 10 — `tests/test_core_filters.py`（~12 个测试，25 分钟）

**提取**: `apply_phase_filter(probs, classes, phase) -> np.ndarray`、`apply_posture_filter(probs, classes, posture) -> np.ndarray`、`renormalize_probs(probs) -> np.ndarray`、`select_top_k(probs, classes, k, min_p) -> list`

| 编号 | 测试 | 输入 | 预期 |
|------|------|------|--------|
| 10.1 | `test_phase_filter_p1` | phase=1, P1-only 动作存在 | P1-only 动作未归零 |
| 10.2 | `test_phase_filter_p2` | phase=2, P1-only 动作存在 | P1-only 动作归零，P2+ 动作未归零 |
| 10.3 | `test_phase_filter_p3` | phase=3, P1-only + P2+ 动作存在 | 两者均未归零（P3 解锁全部） |
| 10.4 | `test_posture_filter_standing` | posture=1, 仅趴下动作 | 仅趴下动作归零 |
| 10.5 | `test_posture_filter_prone` | posture=0, 仅站立动作 | 仅站立动作归零 |
| 10.6 | `test_renormalize_normal` | 概率总和 = 1.0 | 总和保持 1.0 |
| 10.7 | `test_renormalize_scaling` | 概率总和 = 0.5 | 缩放至总和 = 1.0 |
| 10.8 | `test_renormalize_all_zeros` | 全部概率 = 0 | 不崩溃，处理零除 |
| 10.9 | `test_top_k_normal` | 5 个类别，不同概率 | 返回 Top-3 |
| 10.10 | `test_top_k_min_prob` | 所有概率 < 0.03 | 返回空列表 |
| 10.11 | `test_top_k_fewer_than_k` | 2 个类别 | 返回 2 个结果 |
| 10.12 | `test_top_k_empty` | 0 个类别 | 返回空列表 |

---

## Tier 2: 需要 Mock（按依赖顺序排列）

### 批次 2A: 使用临时 CSV 的集成测试（P3.4，0.5 天）

#### 优先级 11 — `tests/test_data_upgrade.py`（~10 个测试，30 分钟）

| 编号 | 测试 | 方法 |
|------|------|------|
| 11.1 | `test_upgrade_adds_phase_column` | 旧格式 CSV（无 phase）→ 升级后具有 phase |
| 11.2 | `test_upgrade_adds_enrage_column` | 旧格式 CSV（无 is_enraged）→ 升级后具有 is_enraged |
| 11.3 | `test_upgrade_phase_calculation` | hp_percent=0.80 → phase=1; hp=0.60 → phase=2 |
| 11.4 | `test_upgrade_enrage_soft_timer` | 动作 4（怒吼）触发 180s 发怒窗口 |
| 11.5 | `test_upgrade_enrage_window_expires` | 180s 后发怒标志回落到 0 |
| 11.6 | `test_upgrade_skip_already_upgraded` | 带两列的 CSV 未被修改 |
| 11.7 | `test_upgrade_column_order` | 输出列与预期顺序匹配 |
| 11.8 | `test_upgrade_empty_directory` | 零个 CSV → 无崩溃 |
| 11.9 | `test_upgrade_preserves_posture` | 旧数据中的 posture 列被保留 |
| 11.10 | `test_upgrade_multiple_files` | 升级 3 个旧文件 |

#### 优先级 12 — `tests/test_data_cleaner.py`（~12 个测试，45 分钟）

| 编号 | 测试 | 方法 |
|------|------|------|
| 12.1 | `test_clean_empty_input` | 0 个 CSV → 无错误 |
| 12.2 | `test_clean_single_transition` | 2 动作序列 → 1 个转换对 |
| 12.3 | `test_clean_action_mapping_applied` | 原始 54,55 → 映射输出中为 53 |
| 12.4 | `test_clean_scripted_excluded` | 动作 159（1 转 2）不在输出中 |
| 12.5 | `test_clean_minor_excluded` | 动作 306（等待）不在输出中 |
| 12.6 | `test_clean_posture_fsm_advances` | 站立 → 趴下转移正确发生 |
| 12.7 | `test_clean_posture_fsm_down_recovery` | DOWN_IDS → 306,307,308 → 姿态 0 |
| 12.8 | `test_clean_distance_filter` | 距离 > 5000 的行已排除 |
| 12.9 | `test_clean_action_id_1_excluded` | action_id == 1 的行已排除 |
| 12.10 | `test_clean_output_columns` | 输出 CSV 有 7 列，名称正确 |
| 12.11 | `test_clean_corrupted_csv_skipped` | 畸形 CSV 不停止处理 |
| 12.12 | `test_clean_output_reproducible` | 相同输入 → 相同输出（两次运行） |

#### 优先级 13 — `tests/test_train_lgbm.py`（~5 个冒烟测试，30 分钟）

| 编号 | 测试 | 方法 |
|------|------|------|
| 13.1 | `test_train_smoke_runs` | mini 数据集（15 行 × 3 类）训练成功 |
| 13.2 | `test_train_model_created` | 训练后 `models/fatalis_ai_model.pkl` 存在 |
| 13.3 | `test_train_plot_created` | 训练后 `models/feature_importance.png` 存在 |
| 13.4 | `test_train_csv_missing` | 无 CSV → 错误已记录，未崩溃 |
| 13.5 | `test_train_action_count_filter` | 出现 < 3 次的类别已丢弃 |

---

## Tier 3: 仅手动验证

#### 优先级 14 — `tests/manual_checklist.md`（已有文件，扩展）

| 编号 | 检查项 | 步骤 |
|------|-------|------|
| 14.1 | `ai_engine.py` 导入成功 | `python -c "from ai_engine import *"` 无错误 |
| 14.2 | `ai_engine.py` 启动（无需游戏） | 运行 → "未找到游戏进程" |
| 14.3 | `data_cleaner.py` 处理真实数据 | 使用 17 个真实 CSV 端到端运行 |
| 14.4 | `train_lgbm.py` 训练真实模型 | 使用真实 `ML_Ready_Dataset.csv` 运行 |
| 14.5 | `enrage.py` 导入成功 | `python -c "import enrage"` 无错误 |
| 14.6 | `data_upgrade.py` 升级旧 CSV | 使用备份旧 CSV 文件运行 |

---

## 5. 执行顺序（含依赖关系）

```
第 1 批次（天 0.5）：优先级 1-3
├── P1: test_offsets.py       ← 零依赖，< 1 分钟
├── P2: test_actions.py       ← 零依赖，< 1 分钟
└── P3: test_logging.py       ← 零依赖，< 1 分钟

第 2 批次（天 1.5）：优先级 4-10
├── P4: test_core_phase.py    ← 需要 compute_phase 提取
├── P5: test_core_nova.py     ← 需要 check_nova_* 提取
├── P6: test_core_enrage.py   ← 需要 detect_enrage 提取
├── P7: test_core_posture.py  ← 需要 apply_posture_fsm 提取
├── P8: test_core_mapping.py  ← 需要 apply_action_mapping 提取
├── P9: test_core_geometry.py ← 需要 compute_* 提取
└── P10: test_core_filters.py ← 需要 apply_*_filter + renormalize + select_top_k 提取

第 3 批次（天 2.5）：优先级 11-13
├── P11: test_data_upgrade.py ← 需要临时 CSV fixtures（conftest.py）
├── P12: test_data_cleaner.py ← 需要临时 CSV fixtures（conftest.py）
└── P13: test_train_lgbm.py   ← 需要 mini ML_Ready_Dataset.csv

第 4 批次（天 3）：优先级 14 + CI
└── P14: 手动检查 + CI 最终确定
```

---

## 6. 快速统计

| 指标 | Tier 1 | Tier 2 | Tier 3 | 总计 |
|--------|---------|---------|---------|-------|
| 测试文件 | 8 | 3 | 1 | 12 |
| 测试数量 | ~75 | ~27 | 6 次检查 | ~102 + 6 次检查 |
| 预计运行时间 | < 5 秒 | ~30 秒 | 5 分钟（手动） | ~35 秒（自动化） |
| 覆盖率贡献 | +40% | +20% | 0% | +60% |
| 预计工作量 | 1.5 天 | 1.5 天 | 0.5 天 | 3.5 天 |

---

*测试优先级列表。未修改任何代码。未生成任何测试。*
