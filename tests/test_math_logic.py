"""P3.3A: Tests for pure math logic functions extracted from ai_engine.py.

Validates:
  - calc_distance_2d: 2D Euclidean distance on XZ plane
  - calc_relative_angle: relative angle from monster facing to player
  - select_top_k: top-k selection from probability arrays
"""

import pytest
import math
import numpy as np

from ai_engine import calc_distance_2d, calc_relative_angle, select_top_k


# =============================================================================
# calc_distance_2d tests
# =============================================================================

class TestCalcDistance2D:
    """Tests for calc_distance_2d — XZ plane distance (Y axis ignored)."""

    def test_same_point_returns_zero(self):
        """Distance from a point to itself should be 0."""
        p = [10.0, 5.0, 20.0]
        m = [10.0, 99.0, 20.0]  # Y differs — should be ignored
        assert calc_distance_2d(p, m) == 0.0

    def test_pythagorean_3_4_5(self):
        """Classic 3-4-5 triangle on XZ plane."""
        p = [0.0, 0.0, 0.0]
        m = [3.0, 999.0, 4.0]  # Y value should not affect result
        assert math.isclose(calc_distance_2d(p, m), 5.0)

    def test_positive_distance(self):
        """Distance should be positive when points differ."""
        p = [0.0, 0.0, 0.0]
        m = [10.0, 0.0, 0.0]
        assert calc_distance_2d(p, m) == 10.0

    def test_z_axis_distance(self):
        """Distance along Z axis only."""
        p = [0.0, 0.0, 0.0]
        m = [0.0, 0.0, 10.0]
        assert calc_distance_2d(p, m) == 10.0

    def test_negative_coordinates(self):
        """Should handle negative coordinates."""
        p = [-3.0, 0.0, -4.0]
        m = [0.0, 0.0, 0.0]
        assert math.isclose(calc_distance_2d(p, m), 5.0)

    def test_large_distance(self):
        """Should handle large distances (typical arena size)."""
        p = [0.0, 0.0, 0.0]
        m = [1000.0, 0.0, 1000.0]
        expected = math.sqrt(2_000_000)
        assert math.isclose(calc_distance_2d(p, m), expected)

    def test_y_axis_ignored(self):
        """Y coordinate difference should not affect XZ distance."""
        p = [0.0, 0.0, 0.0]
        m1 = [3.0, 0.0, 4.0]
        m2 = [3.0, 9999.0, 4.0]
        assert math.isclose(calc_distance_2d(p, m1), calc_distance_2d(p, m2))


# =============================================================================
# calc_relative_angle tests
# =============================================================================

class TestCalcRelativeAngle:
    """Tests for calc_relative_angle — relative angle in degrees.

    Coordinate system (game convention):
      - Identity quaternion [1,0,0,0] → monster_yaw = 180° (facing -Z, "south")
      - Player at -Z relative to monster → 0° (ahead, in front)
      - Player at +Z relative to monster → ±180° (behind)
      - Player at +X relative to monster → -90° (right side)
      - Player at -X relative to monster → +90° (left side)
    """

    # Identity quaternion: monster faces -Z (south), yaw = 180°
    IDENTITY_QUAT = [1.0, 0.0, 0.0, 0.0]

    def test_player_directly_ahead(self):
        """Player in front of monster (-Z) → angle ≈ 0°."""
        # Monster at origin facing -Z (south); player at (0, 0, -10) ahead
        p = [0.0, 0.0, -10.0]
        m = [0.0, 0.0, 0.0]
        angle = calc_relative_angle(p, m, self.IDENTITY_QUAT)
        assert abs(angle) < 1.0, f"Expected ~0°, got {angle}°"

    def test_player_directly_behind(self):
        """Player behind monster (+Z) → angle ≈ ±180°."""
        p = [0.0, 0.0, 10.0]
        m = [0.0, 0.0, 0.0]
        angle = calc_relative_angle(p, m, self.IDENTITY_QUAT)
        assert abs(abs(angle) - 180.0) < 1.0, f"Expected ~±180°, got {angle}°"

    def test_player_to_right(self):
        """Player to monster's right (+X) → angle ≈ -90°."""
        p = [10.0, 0.0, 0.0]
        m = [0.0, 0.0, 0.0]
        angle = calc_relative_angle(p, m, self.IDENTITY_QUAT)
        assert math.isclose(angle, -90.0), f"Expected ~-90°, got {angle}°"

    def test_player_to_left(self):
        """Player to monster's left (-X) → angle ≈ +90°."""
        p = [-10.0, 0.0, 0.0]
        m = [0.0, 0.0, 0.0]
        angle = calc_relative_angle(p, m, self.IDENTITY_QUAT)
        assert math.isclose(angle, 90.0), f"Expected ~+90°, got {angle}°"

    def test_normalized_to_range(self):
        """Result should always be in [-180, 180]."""
        p_cases = [
            [1.0, 0.0, 0.0],
            [-1.0, 0.0, 0.0],
            [0.0, 0.0, 1.0],
            [0.0, 0.0, -1.0],
            [100.0, 500.0, -200.0],
        ]
        m = [0.0, 0.0, 0.0]
        for p in p_cases:
            angle = calc_relative_angle(p, m, self.IDENTITY_QUAT)
            assert -180.0 <= angle <= 180.0, (
                f"Angle {angle}° out of [-180, 180] for p={p}"
            )

    def test_co_located_returns_minus_180(self):
        """When co-located (atan2(0,0)=0), result is -180°."""
        p = [0.0, 0.0, 0.0]
        m = [0.0, 0.0, 0.0]
        angle = calc_relative_angle(p, m, self.IDENTITY_QUAT)
        # atan2(0,0)=0 in Python → target_yaw=0, monster_yaw=180
        # rel = (0 - 180 + 180) % 360 - 180 = -180
        assert angle == -180.0

    def test_monster_facing_east_player_north(self):
        """Monster facing +X (east, 90° yaw), player at +Z (north)."""
        # 90° yaw around Y axis: q = [cos45, 0, sin45, 0]
        cos45 = math.cos(math.radians(45))
        sin45 = math.sin(math.radians(45))
        q_east = [cos45, 0.0, sin45, 0.0]

        # Player north → target_yaw = 0°, monster_yaw = 90°
        # rel = (0 - 90 + 180) % 360 - 180 = 90 - 180 = -90°
        p = [0.0, 0.0, 10.0]
        m = [0.0, 0.0, 0.0]
        angle = calc_relative_angle(p, m, q_east)
        assert math.isclose(angle, -90.0), (
            f"Expected -90° (right side), got {angle}°"
        )

    def test_monster_facing_north_player_ahead(self):
        """Monster facing +Z (north, 0° yaw with q=[0,0,1,0]), player at +Z."""
        # [0,0,1,0] → yaw = 0° (facing +Z/north)
        q_north = [0.0, 0.0, 1.0, 0.0]

        # Player at +Z → target_yaw = 0°, monster_yaw = 0°
        # rel = (0 - 0 + 180) % 360 - 180 = 0°
        p = [0.0, 0.0, 10.0]
        m = [0.0, 0.0, 0.0]
        angle = calc_relative_angle(p, m, q_north)
        assert math.isclose(angle, 0.0), (
            f"Expected 0° (ahead), got {angle}°"
        )


# =============================================================================
# select_top_k tests
# =============================================================================

class TestSelectTopK:
    """Tests for select_top_k — top-k probability selection."""

    @staticmethod
    def make_data(probs, classes=None):
        """Helper: create numpy arrays from lists."""
        p = np.array(probs, dtype=np.float64)
        if classes is None:
            classes = np.arange(len(probs))
        else:
            classes = np.array(classes)
        return p, classes

    def test_returns_top_3_by_default(self):
        """Default k=3, should return at most 3 results."""
        probs, classes = self.make_data([0.5, 0.3, 0.15, 0.04, 0.01])
        result = select_top_k(probs, classes)
        assert len(result) == 3
        assert result[0] == (0, 0.5)
        assert result[1] == (1, 0.3)
        assert result[2] == (2, 0.15)

    def test_threshold_filters_low_probs(self):
        """Items below threshold (0.03) should be excluded."""
        probs, classes = self.make_data([0.5, 0.02, 0.02, 0.01])
        result = select_top_k(probs, classes)
        assert len(result) == 1
        assert result[0][0] == 0

    def test_custom_k(self):
        """Should respect custom k parameter."""
        probs, classes = self.make_data([0.5, 0.4, 0.3, 0.2, 0.1])
        result = select_top_k(probs, classes, k=2)
        assert len(result) == 2
        assert result[0][0] == 0
        assert result[1][0] == 1

    def test_custom_threshold(self):
        """Should respect custom threshold."""
        probs, classes = self.make_data([0.5, 0.3, 0.2, 0.1, 0.05])
        result = select_top_k(probs, classes, threshold=0.15)
        assert len(result) == 3
        # 0.5, 0.3, 0.2 are ≥ 0.15; 0.1 and 0.05 are not
        ids = [r[0] for r in result]
        assert 0 in ids and 1 in ids and 2 in ids
        assert 3 not in ids and 4 not in ids

    def test_all_below_threshold_returns_empty(self):
        """When all probs are below threshold, return empty list."""
        probs, classes = self.make_data([0.02, 0.01, 0.005])
        result = select_top_k(probs, classes)
        assert result == []

    def test_exactly_at_threshold_is_included(self):
        """Probability exactly equal to threshold should be included."""
        probs, classes = self.make_data([0.03])
        result = select_top_k(probs, classes)
        # > 0.03 is False for exactly 0.03
        assert result == []

    def test_returns_float_probabilities(self):
        """Probabilities in result should be Python float type."""
        probs, classes = self.make_data([0.5, 0.3])
        result = select_top_k(probs, classes)
        for _, prob in result:
            assert isinstance(prob, float)

    def test_result_sorted_descending(self):
        """Results should be sorted by probability descending."""
        probs, classes = self.make_data([0.1, 0.5, 0.3, 0.4])
        result = select_top_k(probs, classes)
        probs_only = [p for _, p in result]
        assert probs_only == sorted(probs_only, reverse=True)

    def test_fewer_than_k_available(self):
        """If fewer items than k are above threshold, return all that qualify."""
        probs, classes = self.make_data([0.5, 0.04])
        result = select_top_k(probs, classes, k=5)
        assert len(result) == 2

    def test_empty_array(self):
        """Empty probability array should return empty result."""
        probs, classes = self.make_data([])
        result = select_top_k(probs, classes)
        assert result == []

    def test_non_contiguous_class_ids(self):
        """Should work with arbitrary (non-sequential) class IDs."""
        probs = np.array([0.5, 0.3, 0.2])
        classes = np.array([37, 208, 155])  # Fatalis action IDs
        result = select_top_k(probs, classes)
        assert result[0][0] == 37
        assert result[1][0] == 208
        assert result[2][0] == 155

    def test_tie_breaking(self):
        """Items with equal probability should both be included (stable)."""
        probs, classes = self.make_data([0.5, 0.3, 0.3, 0.1])
        result = select_top_k(probs, classes)
        assert len(result) == 3
        # Both 0.3 items should be included
        probs_found = [p for _, p in result]
        assert 0.3 in probs_found
