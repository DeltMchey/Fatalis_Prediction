"""P4 Step 1: CombatStateTracker tests.

覆盖：
  - 初始状态（与 ai_engine.py shared_state 默认值一致）
  - calc_distance_2d / calc_relative_angle / map_action（纯数学与映射）
  - update_phase（三阶段边界）
  - update_enrage（发怒秒表边界）
  - update_posture（姿态 FSM 转移 + last_action 游标）
  - update_nova（阈值交叉、重置、幂等）
  - reset_for_zone_change（区域切换重置）
"""

import pytest

from src.core.state_tracker import CombatStateTracker


# =============================================================================
# 1. 初始状态
# =============================================================================

class TestInitialization:
    def test_default_state_matches_shared_state(self):
        """默认状态与 ai_engine.py shared_state 初始化值一致。"""
        st = CombatStateTracker()
        assert st.posture == 1
        assert st.phase == 1
        assert st.is_enraged == 0
        assert st.is_recording is True
        assert st.nova_warning is False
        assert st.hp_initialized is False
        assert st.triggered_novas == set()
        assert st._last_action == -1

    def test_custom_is_recording(self):
        """is_recording 可由构造函数覆盖。"""
        st = CombatStateTracker(is_recording=False)
        assert st.is_recording is False


# =============================================================================
# 2. calc_distance_2d（P3.3A 镜像）
# =============================================================================

class TestCalcDistance2D:
    def test_same_point_returns_zero(self):
        assert CombatStateTracker.calc_distance_2d([0, 0, 0], [0, 0, 0]) == 0.0

    def test_pythagorean_3_4_5(self):
        """(3, 0, 4) → XZ 距离 5。"""
        assert CombatStateTracker.calc_distance_2d([0, 0, 0], [3, 0, 4]) == pytest.approx(5.0)

    def test_y_axis_ignored(self):
        """Y 轴坐标不参与计算。"""
        d1 = CombatStateTracker.calc_distance_2d([0, 0, 0], [3, 0, 4])
        d2 = CombatStateTracker.calc_distance_2d([0, 100, 0], [3, -50, 4])
        assert d1 == pytest.approx(d2)

    def test_negative_coordinates(self):
        assert CombatStateTracker.calc_distance_2d([-1, 0, -1], [-4, 0, -5]) == pytest.approx(5.0)


# =============================================================================
# 3. calc_relative_angle（P3.3A 镜像）
# =============================================================================

class TestCalcRelativeAngle:
    """测试 calc_relative_angle — 相对角度（度）。

    坐标系统（游戏约定，与 P3.3 test_math_logic.py 一致）：
      - 单位四元数 [1,0,0,0] → monster_yaw = 180°（面向 -Z，"南"）
      - 玩家在怪物 -Z（前方）→ 0°
      - 玩家在怪物 +Z（后方）→ ±180°
      - 玩家在怪物 +X（右侧）→ -90°
      - 玩家在怪物 -X（左侧）→ +90°
    """

    # 单位四元数：怪物面向 -Z（南），yaw = 180°
    IDENTITY_QUAT = [1.0, 0.0, 0.0, 0.0]

    def test_player_directly_ahead(self):
        """玩家在怪物正前方（-Z）→ 相对角 ≈ 0°。"""
        angle = CombatStateTracker.calc_relative_angle(
            [0, 0, -10], [0, 0, 0], self.IDENTITY_QUAT)
        assert abs(angle) < 1.0, f"Expected ~0°, got {angle}°"

    def test_player_directly_behind(self):
        """玩家在怪物正后方（+Z）→ 相对角 ≈ ±180°。"""
        angle = CombatStateTracker.calc_relative_angle(
            [0, 0, 10], [0, 0, 0], self.IDENTITY_QUAT)
        assert abs(abs(angle) - 180.0) < 1.0, f"Expected ~±180°, got {angle}°"

    def test_player_to_right(self):
        """玩家在怪物右侧（+X）→ 相对角 ≈ -90°。"""
        angle = CombatStateTracker.calc_relative_angle(
            [10, 0, 0], [0, 0, 0], self.IDENTITY_QUAT)
        assert angle == pytest.approx(-90.0)

    def test_player_to_left(self):
        """玩家在怪物左侧（-X）→ 相对角 ≈ +90°。"""
        angle = CombatStateTracker.calc_relative_angle(
            [-10, 0, 0], [0, 0, 0], self.IDENTITY_QUAT)
        assert angle == pytest.approx(90.0)

    def test_normalized_to_range(self):
        """相对角恒在 [-180, 180] 区间。"""
        for p in ([100, 0, 1], [1, 0, 100], [-100, 0, 1], [1, 0, -100]):
            angle = CombatStateTracker.calc_relative_angle(
                p, [0, 0, 0], self.IDENTITY_QUAT)
            assert -180 <= angle <= 180


# =============================================================================
# 4. map_action（动作映射）
# =============================================================================

class TestMapAction:
    def test_mapped_raw_id_to_base(self):
        """原始帧 ID → 起手 Base ID（38→37, 54→53, 82→81, 92→91）。"""
        assert CombatStateTracker.map_action(38) == 37
        assert CombatStateTracker.map_action(54) == 53
        assert CombatStateTracker.map_action(82) == 81
        assert CombatStateTracker.map_action(92) == 91

    def test_unmapped_id_unchanged(self):
        """无映射的 ID 原样返回（129, 81, 37）。"""
        assert CombatStateTracker.map_action(129) == 129
        assert CombatStateTracker.map_action(81) == 81
        assert CombatStateTracker.map_action(37) == 37

    def test_negative_id_unchanged(self):
        assert CombatStateTracker.map_action(-1) == -1


# =============================================================================
# 5. update_phase（三阶段边界）
# =============================================================================

class TestUpdatePhase:
    def test_above_78_is_phase1(self):
        st = CombatStateTracker()
        st.update_phase(0.90)
        assert st.phase == 1
        st.update_phase(0.79)
        assert st.phase == 1

    def test_exactly_78_is_phase2(self):
        st = CombatStateTracker()
        st.update_phase(0.78)
        assert st.phase == 2

    def test_between_50_78_is_phase2(self):
        st = CombatStateTracker()
        st.update_phase(0.60)
        assert st.phase == 2
        st.update_phase(0.51)
        assert st.phase == 2

    def test_exactly_50_is_phase3(self):
        st = CombatStateTracker()
        st.update_phase(0.50)
        assert st.phase == 3

    def test_below_50_is_phase3(self):
        st = CombatStateTracker()
        st.update_phase(0.30)
        assert st.phase == 3

    def test_full_and_zero_hp(self):
        st = CombatStateTracker()
        st.update_phase(1.0)
        assert st.phase == 1
        st.update_phase(0.0)
        assert st.phase == 3


# =============================================================================
# 6. update_enrage（发怒秒表边界）
# =============================================================================

class TestUpdateEnrage:
    def test_timer_in_window_is_enraged(self):
        st = CombatStateTracker()
        st.update_enrage(5.0, 10.0)
        assert st.is_enraged == 1

    def test_timer_fractional_window(self):
        st = CombatStateTracker()
        st.update_enrage(0.1, 180.0)
        assert st.is_enraged == 1

    def test_timer_zero_not_enraged(self):
        st = CombatStateTracker()
        st.update_enrage(0.0, 10.0)
        assert st.is_enraged == 0

    def test_timer_at_max_not_enraged(self):
        st = CombatStateTracker()
        st.update_enrage(10.0, 10.0)
        assert st.is_enraged == 0

    def test_timer_above_max_not_enraged(self):
        st = CombatStateTracker()
        st.update_enrage(20.0, 10.0)
        assert st.is_enraged == 0

    def test_timer_negative_not_enraged(self):
        st = CombatStateTracker()
        st.update_enrage(-1.0, 10.0)
        assert st.is_enraged == 0


# =============================================================================
# 7. update_posture（姿态 FSM + last_action 游标）
# =============================================================================

class TestUpdatePosture:
    def test_stand_action_sets_posture_1(self):
        """POSTURE_STAND 动作（115 俯冲）→ posture=1。"""
        st = CombatStateTracker()
        result = st.update_posture(115)
        assert st.posture == 1
        assert result == 1

    def test_prone_action_sets_posture_0(self):
        """POSTURE_PRONE 动作（138 孕吐）→ posture=0。"""
        st = CombatStateTracker()
        result = st.update_posture(138)
        assert st.posture == 0
        assert result == 0

    def test_fly_action_sets_posture_2(self):
        """POSTURE_FLY 动作（107 跳投）→ posture=2。"""
        st = CombatStateTracker()
        result = st.update_posture(107)
        assert st.posture == 2
        assert result == 2

    def test_same_action_returns_none(self):
        """同一动作重复 → 无姿态变化。"""
        st = CombatStateTracker()
        st.update_posture(115)      # → stand
        result = st.update_posture(115)  # 同动作
        assert result is None
        assert st.posture == 1

    def test_action_minus_one_returns_none(self):
        """action=-1 → 无姿态变化。"""
        st = CombatStateTracker()
        st.update_posture(115)
        result = st.update_posture(-1)
        assert result is None
        assert st.posture == 1

    def test_unknown_action_returns_posture(self):
        """未知动作（非姿态触发）→ 姿态不变，但返回当前 posture。

        与原 ai_engine.py 逻辑一致：last_action 无条件更新，但姿态只在
        POSTURE_* 集合中变化。未知动作不改变姿态，返回当前 posture。
        """
        st = CombatStateTracker()
        st.update_posture(115)       # stand, last_action=115
        result = st.update_posture(999)  # 未知动作
        assert st.posture == 1       # 姿态不变
        assert result == 1           # 返回当前 posture
        assert st._last_action == 999  # last_action 无条件更新

    def test_chain_stand_to_prone_to_fly(self):
        """动作序列驱动姿态链式转换。"""
        st = CombatStateTracker()
        st.update_posture(115)   # stand
        st.update_posture(138)   # prone
        assert st.posture == 0
        st.update_posture(107)   # fly
        assert st.posture == 2
        st.update_posture(115)   # stand again
        assert st.posture == 1

    def test_last_action_tracked(self):
        """last_action 游标随动作更新。"""
        st = CombatStateTracker()
        st.update_posture(115)
        assert st._last_action == 115
        st.update_posture(138)
        assert st._last_action == 138
        st.update_posture(-1)
        assert st._last_action == -1


# =============================================================================
# 8. update_nova（阈值交叉、重置、幂等）
# =============================================================================

class TestUpdateNova:
    def test_init_full_hp_seeds_nothing(self):
        """满血初始化 → 无阈值被标记，无 warning。"""
        st = CombatStateTracker()
        result = st.update_nova(0.90, -1)
        assert st.hp_initialized is True
        assert st.triggered_novas == set()
        assert result is False

    def test_init_crossed_thresholds_seeded(self):
        """低血初始化 → 所有已越过阈值被标记（0.30 → 0.78/0.50/0.41）。"""
        st = CombatStateTracker()
        st.update_nova(0.30, -1)
        assert 0.78 in st.triggered_novas
        assert 0.50 in st.triggered_novas
        assert 0.41 in st.triggered_novas
        assert 0.26 not in st.triggered_novas  # 0.30 > 0.26，未越过
        assert 0.06 not in st.triggered_novas
        assert st.hp_initialized is True

    def test_crossing_generates_warning(self):
        """HP 跨过新阈值 → warning=True。"""
        st = CombatStateTracker()
        st.update_nova(0.90, -1)   # 初始化，无越过
        result = st.update_nova(0.70, -1)  # 越过 0.78
        assert result is True
        assert st.nova_warning is True
        assert 0.78 in st.triggered_novas

    def test_no_crossing_no_warning(self):
        """HP 未跨新阈值 → warning=False。"""
        st = CombatStateTracker()
        st.update_nova(0.90, -1)
        result = st.update_nova(0.85, -1)
        assert result is False

    def test_crossing_multiple_at_once(self):
        """HP 一次跨多个阈值 → 全部标记。"""
        st = CombatStateTracker()
        st.update_nova(0.90, -1)
        st.update_nova(0.20, -1)  # 跨 0.78/0.50/0.41/0.26
        assert 0.78 in st.triggered_novas
        assert 0.50 in st.triggered_novas
        assert 0.41 in st.triggered_novas
        assert 0.26 in st.triggered_novas
        assert st.nova_warning is True

    def test_second_crossing_same_threshold_no_warning(self):
        """同一阈值不重复触发。"""
        st = CombatStateTracker()
        st.update_nova(0.90, -1)
        st.update_nova(0.70, -1)   # 跨 0.78 → warning
        st.nova_warning = False     # 模拟 warning 已被消费
        result = st.update_nova(0.72, -1)  # 仍在 0.78 以下但已标记
        assert result is False

    def test_hp_rising_does_not_untrack(self):
        """HP 回升不会撤销已触发阈值。"""
        st = CombatStateTracker()
        st.update_nova(0.90, -1)
        st.update_nova(0.70, -1)   # 标记 0.78
        st.update_nova(0.95, -1)   # HP 回升
        assert 0.78 in st.triggered_novas

    def test_reset_action_197_clears_warning(self):
        """动作 197（落地）清除 warning。"""
        st = CombatStateTracker()
        st.update_nova(0.90, -1)
        st.update_nova(0.70, -1)   # 跨 0.78 → warning
        assert st.nova_warning is True
        result = st.update_nova(0.70, 197)
        assert result is False
        assert st.nova_warning is False

    def test_reset_action_167_clears_warning(self):
        """动作 167（飞回场中）清除 warning。"""
        st = CombatStateTracker()
        st.update_nova(0.90, -1)
        st.update_nova(0.70, -1)
        result = st.update_nova(0.70, 167)
        assert result is False

    def test_reset_action_179_clears_warning(self):
        """动作 179（p3 开场吼）清除 warning。"""
        st = CombatStateTracker()
        st.update_nova(0.90, -1)
        st.update_nova(0.70, -1)
        result = st.update_nova(0.70, 179)
        assert result is False

    def test_non_reset_action_keeps_warning(self):
        """非重置动作不清除已触发的 warning。

        场景：先跨 0.78（warning=True），再跨 0.50（0.50 是新阈值 → 仍 warning）。
        """
        st = CombatStateTracker()
        st.update_nova(0.90, -1)      # 初始化，无越过
        st.update_nova(0.70, 37)      # 跨 0.78 → warning=True（动作 37 非重置）
        assert st.nova_warning is True
        # 0.70 已标记 0.78；无新阈值跨越 → warning 保持（但方法每次重置为 False 前，
        # 检查新阈值——0.50 未跨，所以本轮返回 False）
        result = st.update_nova(0.70, 37)
        assert result is False

    def test_crossing_new_threshold_keeps_warning_with_non_reset_action(self):
        """跨新阈值且动作非重置 → warning 持续。"""
        st = CombatStateTracker()
        st.update_nova(0.90, -1)      # 初始化
        st.update_nova(0.70, 37)      # 跨 0.78 → warning=True
        result = st.update_nova(0.30, 37)  # 跨 0.50/0.41/0.26 → warning=True
        assert result is True
        assert st.nova_warning is True

    def test_exactly_at_threshold(self):
        """HP 恰等于阈值 → 触发。"""
        st = CombatStateTracker()
        st.update_nova(0.90, -1)
        result = st.update_nova(0.78, -1)
        assert result is True
        assert 0.78 in st.triggered_novas


# =============================================================================
# 9. reset_for_zone_change（区域切换重置）
# =============================================================================

class TestResetForZoneChange:
    def test_reset_clears_all_state(self):
        """所有派生状态复位。"""
        st = CombatStateTracker()
        # 制造非默认状态
        st.update_phase(0.30)          # phase=3
        st.update_enrage(5.0, 10.0)    # is_enraged=1
        st.update_posture(107)         # posture=2
        st.update_nova(0.20, -1)       # nova warning + triggered
        assert st.phase == 3
        assert st.is_enraged == 1
        assert st.posture == 2
        assert st.triggered_novas

        st.reset_for_zone_change()

        assert st.posture == 1
        assert st.phase == 1
        assert st.is_enraged == 0
        assert st.nova_warning is False
        assert st.hp_initialized is False
        assert st.triggered_novas == set()
        assert st._last_action == -1

    def test_reset_preserves_is_recording(self):
        """is_recording（用户开关）跨区域保留。"""
        st = CombatStateTracker(is_recording=False)
        st.reset_for_zone_change()
        assert st.is_recording is False

    def test_reset_allows_reinit_nova(self):
        """重置后 Nova 状态机可重新初始化。"""
        st = CombatStateTracker()
        st.update_nova(0.20, -1)   # 初始化 + 触发
        st.reset_for_zone_change()
        st.update_nova(0.90, -1)   # 重新初始化
        assert st.hp_initialized is True
        assert st.triggered_novas == set()  # 满血无越过
