# P3.3 测试结果 — 核心逻辑测试套件

> **日期**: 2026-06-30
> **阶段**: P3.3A + P3.3B + P3.3C 全部完成
> **套件规模**: 85 项测试，100% 通过率

---

## 1. 总分

```
collected 85 items
============================= 85 passed in 0.45s ==============================
```

---

## 2. P3.3A — 纯数学逻辑 (`tests/test_math_logic.py`)

**被测函数**: `calc_distance_2d`, `calc_relative_angle`, `select_top_k`
**提取自**: `ai_engine.py:102,106,183-187,270-274` → 模块级纯函数

### 测试结果 (27 / 27)

| 类 | 测试 | 状态 |
|----|------|------|
| `TestCalcDistance2D` | `test_same_point_returns_zero` | ✅ |
| | `test_pythagorean_3_4_5` | ✅ |
| | `test_positive_distance` | ✅ |
| | `test_z_axis_distance` | ✅ |
| | `test_negative_coordinates` | ✅ |
| | `test_large_distance` | ✅ |
| | `test_y_axis_ignored` | ✅ |
| `TestCalcRelativeAngle` | `test_player_directly_ahead` | ✅ |
| | `test_player_directly_behind` | ✅ |
| | `test_player_to_right` | ✅ |
| | `test_player_to_left` | ✅ |
| | `test_normalized_to_range` | ✅ |
| | `test_co_located_returns_minus_180` | ✅ |
| | `test_monster_facing_east_player_north` | ✅ |
| | `test_monster_facing_north_player_ahead` | ✅ |
| `TestSelectTopK` | `test_returns_top_3_by_default` | ✅ |
| | `test_threshold_filters_low_probs` | ✅ |
| | `test_custom_k` | ✅ |
| | `test_custom_threshold` | ✅ |
| | `test_all_below_threshold_returns_empty` | ✅ |
| | `test_exactly_at_threshold_is_included` | ✅ |
| | `test_returns_float_probabilities` | ✅ |
| | `test_result_sorted_descending` | ✅ |
| | `test_fewer_than_k_available` | ✅ |
| | `test_empty_array` | ✅ |
| | `test_non_contiguous_class_ids` | ✅ |
| | `test_tie_breaking` | ✅ |

---

## 3. P3.3B — 预测过滤逻辑 (`tests/test_phase_filter.py`)

**被测函数**: `filter_probs_by_phase`, `filter_probs_by_posture`, `renormalize_probs`
**提取自**: `ai_engine.py:306-321` → 模块级纯函数

### 测试结果 (32 / 32)

| 类 | 测试 | 状态 |
|----|------|------|
| `TestFilterProbsByPhase` | `test_phase1_keeps_p1_only` | ✅ |
| | `test_phase1_zeros_p2_plus` | ✅ |
| | `test_phase1_zeros_p3_only` | ✅ |
| | `test_phase2_zeros_p1_only` | ✅ |
| | `test_phase2_keeps_p2_plus` | ✅ |
| | `test_phase2_zeros_p3_only` | ✅ |
| | `test_phase3_zeros_p1_only` | ✅ |
| | `test_phase3_keeps_p2_plus` | ✅ |
| | `test_phase3_keeps_p3_only` | ✅ |
| | `test_mixed_classes` | ✅ |
| | `test_modifies_in_place` | ✅ |
| | `test_empty_arrays` | ✅ |
| | `test_uses_default_sets_when_none_provided` | ✅ |
| `TestFilterProbsByPosture` | `test_standing_filters_stand_exclude` | ✅ |
| | `test_standing_does_not_affect_prone_exclude` | ✅ |
| | `test_prone_filters_prone_exclude` | ✅ |
| | `test_prone_does_not_affect_stand_exclude` | ✅ |
| | `test_flying_no_filter` | ✅ |
| | `test_modifies_in_place` | ✅ |
| | `test_uses_default_sets_when_none_provided` | ✅ |
| | `test_stand_exclude_uses_real_set` | ✅ |
| | `test_prone_exclude_uses_real_set` | ✅ |
| `TestRenormalizeProbs` | `test_normalizes_to_one` | ✅ |
| | `test_preserves_relative_ratios` | ✅ |
| | `test_all_zeros_unchanged` | ✅ |
| | `test_single_value` | ✅ |
| | `test_already_normalized` | ✅ |
| | `test_returns_same_object_when_already_normalized` | ✅ |
| | `test_small_residuals` | ✅ |
| `TestFilterPipeline` | `test_pipeline_phase1_standing` | ✅ |
| | `test_pipeline_all_zeroed` | ✅ |
| | `test_pipeline_preserves_non_zero_indices` | ✅ |

---

## 4. P3.3C — Nova 阈值逻辑 (`tests/test_nova.py`)

**被测函数**: `evaluate_nova`
**提取自**: `ai_engine.py:358-367` → 模块级纯函数

### 测试结果 (26 / 26)

| 类 | 测试 | 状态 |
|----|------|------|
| `TestInitialization` | `test_init_seeds_crossed_thresholds` | ✅ |
| | `test_init_full_hp_seeds_nothing` | ✅ |
| | `test_init_zero_hp_seeds_all` | ✅ |
| | `test_init_exactly_at_threshold` | ✅ |
| | `test_init_does_not_duplicate` | ✅ |
| `TestThresholdCrossing` | `test_crossing_generates_warning` | ✅ |
| | `test_crossing_multiple_at_once` | ✅ |
| | `test_hp_rising_does_not_untrack` | ✅ |
| `TestWarningGeneration` | `test_single_crossing_triggers_warning` | ✅ |
| | `test_no_crossing_no_warning` | ✅ |
| | `test_warning_on_last_threshold` | ✅ |
| `TestResetActions` | `test_action_197_resets_warning` | ✅ |
| | `test_action_167_resets_warning` | ✅ |
| | `test_action_179_resets_warning` | ✅ |
| | `test_non_reset_action_does_not_reset` | ✅ |
| | `test_reset_only_affects_warning_not_triggered_set` | ✅ |
| `TestIdempotency` | `test_second_crossing_no_warning` | ✅ |
| | `test_multiple_scans_dont_duplicate` | ✅ |
| | `test_init_after_init_is_noop` | ✅ |
| `TestEdgeCases` | `test_empty_thresholds` | ✅ |
| | `test_default_arguments` | ✅ |
| | `test_single_threshold` | ✅ |
| | `test_negative_hp_should_cross_all` | ✅ |
| | `test_hp_above_one` | ✅ |
| | `test_non_mutable_defaults` | ✅ |
| | `test_crossing_and_reset_same_frame` | ✅ |

---

## 5. 覆盖率

```
Name                     Stmts   Miss Branch BrPart  Cover
--------------------------------------------------------------------
ai_engine.py               248    153     82      0    43%
src/config/actions.py       12      0      0      0   100%
src/config/offsets.py       27      0      0      0   100%
src/logging_config.py        4      0      0      0   100%
--------------------------------------------------------------------
TOTAL (tested modules)     291    153     82      0    47%
TOTAL (all)                495    357    136      0    29%
```

| 阶段 | `ai_engine.py` | 整体 | 新增函数 |
|------|---------------|------|---------|
| P3.2 (基线) | 0% | 8% | — |
| P3.3A | 18% | 16% | `calc_distance_2d`, `calc_relative_angle`, `select_top_k` |
| P3.3B | 34% | 24% | `filter_probs_by_phase`, `filter_probs_by_posture`, `renormalize_probs` |
| P3.3C | **43%** | **29%** | `evaluate_nova` |

---

## 6. 提取总览

`ai_engine.py` 中新增 **8 个模块级纯函数**（共 ~130 行）：

| # | 函数 | P3 子阶段 | 行数 | 原内联代码 |
|---|------|----------|------|-----------|
| 1 | `calc_distance_2d` | P3.3A | 12 | 行 102, 183 |
| 2 | `calc_relative_angle` | P3.3A | 16 | 行 103-106, 184-187 |
| 3 | `select_top_k` | P3.3A | 18 | 行 270-274 |
| 4 | `filter_probs_by_phase` | P3.3B | 28 | 行 307-310 |
| 5 | `filter_probs_by_posture` | P3.3B | 24 | 行 311-318 |
| 6 | `renormalize_probs` | P3.3B | 10 | 行 320-321 |
| 7 | `evaluate_nova` | P3.3C | 50 | 行 358-367 |
| — | `_POSTURE_STAND_EXCLUDE` | P3.3B | 3 | 行 311-312 |
| — | `_POSTURE_PRONE_EXCLUDE` | P3.3B | 5 | 行 314-317 |

**行为变更**: 零。所有函数与原始内联代码输入/输出完全一致。

---

## 7. 验证命令

```bash
# P3.3A — 数学逻辑
pytest tests/test_math_logic.py -v

# P3.3B — 预测过滤
pytest tests/test_phase_filter.py -v

# P3.3C — Nova 阈值
pytest tests/test_nova.py -v

# P3.3 全部
pytest tests/test_math_logic.py tests/test_phase_filter.py tests/test_nova.py -v --cov

# 项目全量
pytest tests/ --cov -q
```
