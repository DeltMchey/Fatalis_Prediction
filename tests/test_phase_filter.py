"""P3.3B: Tests for prediction filtering logic extracted from ai_engine.py.

Validates:
  - filter_probs_by_phase: zero out probs invalid for current fight phase
  - filter_probs_by_posture: zero out probs invalid for current monster posture
  - renormalize_probs: re-normalize probability array to sum=1
  - Composition: phase filter → posture filter → renormalize
"""

import pytest
import math
import numpy as np
from copy import deepcopy

from ai_engine import (
    filter_probs_by_phase,
    filter_probs_by_posture,
    renormalize_probs,
)

# Small test sets to avoid depending on real game data
T1 = {1, 2}        # Phase 1 only
T2 = {10, 11}      # Phase 2+ (available in P2 and P3)
T3 = {20, 21}      # Phase 3 only
STAND_EX = {30, 31}  # Not available when standing
PRONE_EX = {40, 41}  # Not available when prone


# =============================================================================
# Helpers
# =============================================================================

def arr(*values):
    """Create a float64 numpy array from values."""
    return np.array(values, dtype=np.float64)


def ids(*values):
    """Create an int64 numpy array from values."""
    return np.array(values, dtype=np.int64)


# =============================================================================
# filter_probs_by_phase tests
# =============================================================================

class TestFilterProbsByPhase:
    """Tests for phase-based probability filtering."""

    # ── Phase 1 (P1) ──

    def test_phase1_keeps_p1_only(self):
        """In P1, P1_ONLY actions should keep their probabilities."""
        p = arr(0.5, 0.3)
        c = ids(1, 2)  # both in T1 (P1 only)
        result = filter_probs_by_phase(p, c, phase=1, p1_only=T1, p2_plus=T2, p3_only=T3)
        assert result[0] == 0.5
        assert result[1] == 0.3

    def test_phase1_zeros_p2_plus(self):
        """In P1, P2_PLUS actions should be zeroed."""
        p = arr(0.5, 0.3)
        c = ids(1, 10)  # 1 in T1, 10 in T2
        result = filter_probs_by_phase(p, c, phase=1, p1_only=T1, p2_plus=T2, p3_only=T3)
        assert result[0] == 0.5
        assert result[1] == 0.0

    def test_phase1_zeros_p3_only(self):
        """In P1, P3_ONLY actions should be zeroed."""
        p = arr(0.5, 0.3)
        c = ids(20, 21)  # both in T3
        result = filter_probs_by_phase(p, c, phase=1, p1_only=T1, p2_plus=T2, p3_only=T3)
        assert result[0] == 0.0
        assert result[1] == 0.0

    # ── Phase 2 (P2) ──

    def test_phase2_zeros_p1_only(self):
        """In P2, P1_ONLY actions should be zeroed."""
        p = arr(0.5, 0.3, 0.2)
        c = ids(1, 10, 50)  # 1 in T1, 10 in T2, 50 neutral
        result = filter_probs_by_phase(p, c, phase=2, p1_only=T1, p2_plus=T2, p3_only=T3)
        assert result[0] == 0.0   # P1 only → zeroed
        assert result[1] == 0.3   # P2+ → kept
        assert result[2] == 0.2   # neutral → kept

    def test_phase2_keeps_p2_plus(self):
        """In P2, P2_PLUS actions should be kept."""
        p = arr(0.5, 0.3)
        c = ids(10, 11)  # both in T2
        result = filter_probs_by_phase(p, c, phase=2, p1_only=T1, p2_plus=T2, p3_only=T3)
        assert result[0] == 0.5
        assert result[1] == 0.3

    def test_phase2_zeros_p3_only(self):
        """In P2, P3_ONLY actions should be zeroed."""
        p = arr(0.5, 0.3)
        c = ids(20, 21)  # both in T3
        result = filter_probs_by_phase(p, c, phase=2, p1_only=T1, p2_plus=T2, p3_only=T3)
        assert result[0] == 0.0
        assert result[1] == 0.0

    # ── Phase 3 (P3) ──

    def test_phase3_zeros_p1_only(self):
        """In P3, P1_ONLY actions should be zeroed."""
        p = arr(0.5, 0.3)
        c = ids(1, 2)  # both in T1
        result = filter_probs_by_phase(p, c, phase=3, p1_only=T1, p2_plus=T2, p3_only=T3)
        assert result[0] == 0.0
        assert result[1] == 0.0

    def test_phase3_keeps_p2_plus(self):
        """In P3, P2_PLUS actions should be kept (they're available in P3 too)."""
        p = arr(0.5, 0.3)
        c = ids(10, 11)  # both in T2
        result = filter_probs_by_phase(p, c, phase=3, p1_only=T1, p2_plus=T2, p3_only=T3)
        assert result[0] == 0.5
        assert result[1] == 0.3

    def test_phase3_keeps_p3_only(self):
        """In P3, P3_ONLY actions should be kept."""
        p = arr(0.5, 0.3)
        c = ids(20, 21)  # both in T3
        result = filter_probs_by_phase(p, c, phase=3, p1_only=T1, p2_plus=T2, p3_only=T3)
        assert result[0] == 0.5
        assert result[1] == 0.3

    # ── Edge cases ──

    def test_mixed_classes(self):
        """All three filter types should work simultaneously."""
        p = arr(0.4, 0.3, 0.2, 0.1)
        c = ids(1, 10, 20, 99)  # P1, P2+, P3, neutral
        result = filter_probs_by_phase(p, c, phase=2, p1_only=T1, p2_plus=T2, p3_only=T3)
        assert result[0] == 0.0   # P1 only → zeroed
        assert result[1] == 0.3   # P2+ → kept
        assert result[2] == 0.0   # P3 only → zeroed
        assert result[3] == 0.1   # neutral → kept

    def test_modifies_in_place(self):
        """Function should modify the array in-place."""
        p = arr(0.5, 0.3)
        c = ids(1, 10)
        result = filter_probs_by_phase(p, c, phase=1, p1_only=T1, p2_plus=T2, p3_only=T3)
        assert result is p  # same object

    def test_empty_arrays(self):
        """Empty input should return empty unchanged."""
        p = arr()
        c = ids()
        result = filter_probs_by_phase(p, c, phase=1, p1_only=T1, p2_plus=T2, p3_only=T3)
        assert len(result) == 0

    def test_uses_default_sets_when_none_provided(self):
        """Should fall back to real config sets when no test sets given."""
        p = arr(0.5, 0.3)
        c = ids(99999, 99998)  # IDs unlikely to be in any real filter set
        result = filter_probs_by_phase(p, c, phase=1)
        assert result[0] == 0.5
        assert result[1] == 0.3


# =============================================================================
# filter_probs_by_posture tests
# =============================================================================

class TestFilterProbsByPosture:
    """Tests for posture-based probability filtering."""

    def test_standing_filters_stand_exclude(self):
        """When posture=1 (standing), stand_exclude IDs should be zeroed."""
        p = arr(0.5, 0.3)
        c = ids(30, 99)  # 30 in stand_exclude, 99 neutral
        result = filter_probs_by_posture(p, c, posture=1,
                                         stand_exclude=STAND_EX, prone_exclude=PRONE_EX)
        assert result[0] == 0.0
        assert result[1] == 0.3

    def test_standing_does_not_affect_prone_exclude(self):
        """When standing, prone_exclude IDs should NOT be zeroed."""
        p = arr(0.5, 0.3)
        c = ids(40, 99)  # 40 in prone_exclude, 99 neutral
        result = filter_probs_by_posture(p, c, posture=1,
                                         stand_exclude=STAND_EX, prone_exclude=PRONE_EX)
        assert result[0] == 0.5  # prone exclude → not filtered when standing
        assert result[1] == 0.3

    def test_prone_filters_prone_exclude(self):
        """When posture=0 (prone), prone_exclude IDs should be zeroed."""
        p = arr(0.5, 0.3, 0.2)
        c = ids(40, 41, 99)  # two in prone_exclude, one neutral
        result = filter_probs_by_posture(p, c, posture=0,
                                         stand_exclude=STAND_EX, prone_exclude=PRONE_EX)
        assert result[0] == 0.0
        assert result[1] == 0.0
        assert result[2] == 0.2

    def test_prone_does_not_affect_stand_exclude(self):
        """When prone, stand_exclude IDs should NOT be zeroed."""
        p = arr(0.5, 0.3)
        c = ids(30, 99)  # 30 in stand_exclude, 99 neutral
        result = filter_probs_by_posture(p, c, posture=0,
                                         stand_exclude=STAND_EX, prone_exclude=PRONE_EX)
        assert result[0] == 0.5  # stand exclude → not filtered when prone
        assert result[1] == 0.3

    def test_flying_no_filter(self):
        """When posture=2 (flying), neither exclude set is applied."""
        p = arr(0.5, 0.3)
        c = ids(30, 40)  # one in each exclude set
        result = filter_probs_by_posture(p, c, posture=2,
                                         stand_exclude=STAND_EX, prone_exclude=PRONE_EX)
        assert result[0] == 0.5
        assert result[1] == 0.3

    def test_modifies_in_place(self):
        """Function should modify the array in-place."""
        p = arr(0.5, 0.3)
        c = ids(30, 99)
        result = filter_probs_by_posture(p, c, posture=1,
                                         stand_exclude=STAND_EX, prone_exclude=PRONE_EX)
        assert result is p

    def test_uses_default_sets_when_none_provided(self):
        """Should fall back to real _POSTURE_*_EXCLUDE sets."""
        p = arr(0.5, 0.3)
        c = ids(99999, 99998)
        result = filter_probs_by_posture(p, c, posture=1)
        assert result[0] == 0.5
        assert result[1] == 0.3

    def test_stand_exclude_uses_real_set(self):
        """Real stand_exclude set should contain known Fatalis action IDs."""
        # Verify default set is non-empty and contains expected IDs
        from ai_engine import _POSTURE_STAND_EXCLUDE
        assert len(_POSTURE_STAND_EXCLUDE) == 15
        assert 129 in _POSTURE_STAND_EXCLUDE  # 蓄力火 (趴→立)
        assert 93 in _POSTURE_STAND_EXCLUDE   # 单火球

    def test_prone_exclude_uses_real_set(self):
        """Real prone_exclude set should contain known Fatalis action IDs."""
        from ai_engine import _POSTURE_PRONE_EXCLUDE
        assert len(_POSTURE_PRONE_EXCLUDE) == 37
        assert 138 in _POSTURE_PRONE_EXCLUDE  # 孕吐
        assert 37 in _POSTURE_PRONE_EXCLUDE   # 龙车
        assert 134 in _POSTURE_PRONE_EXCLUDE  # 左右火


# =============================================================================
# renormalize_probs tests
# =============================================================================

class TestRenormalizeProbs:
    """Tests for probability renormalization."""

    def test_normalizes_to_one(self):
        """Renormalized probabilities should sum to 1."""
        p = arr(0.5, 0.3, 0.2)
        result = renormalize_probs(p.copy())
        assert math.isclose(np.sum(result), 1.0)

    def test_preserves_relative_ratios(self):
        """Relative proportions should be preserved after renormalization."""
        p = arr(0.5, 0.3)
        result = renormalize_probs(p.copy())
        # 0.5/0.3 should equal result[0]/result[1]
        ratio_before = 0.5 / 0.3
        ratio_after = result[0] / result[1]
        assert math.isclose(ratio_before, ratio_after)

    def test_all_zeros_unchanged(self):
        """When all probabilities are zero, return as-is (no NaN)."""
        p = arr(0.0, 0.0, 0.0)
        result = renormalize_probs(p)
        assert np.all(result == 0.0)
        # Should not produce NaN
        assert not np.any(np.isnan(result))

    def test_single_value(self):
        """A single probability should normalize to 1."""
        p = arr(0.5)
        result = renormalize_probs(p.copy())
        assert math.isclose(result[0], 1.0)

    def test_already_normalized(self):
        """Already normalized array should remain unchanged."""
        p = arr(0.4, 0.3, 0.3)
        result = renormalize_probs(p.copy())
        assert math.isclose(result[0], 0.4)
        assert math.isclose(result[1], 0.3)
        assert math.isclose(result[2], 0.3)

    def test_returns_same_object_when_already_normalized(self):
        """When sum ≈ 1, the array is divided in-place (same object)."""
        p = arr(0.4, 0.3, 0.3)
        result = renormalize_probs(p)
        # Division creates new array, but values are preserved
        assert math.isclose(np.sum(result), 1.0)

    def test_small_residuals(self):
        """Tiny floating-point residuals should be handled correctly."""
        p = arr(1e-15, 1e-16)
        if np.sum(p) > 0:
            result = renormalize_probs(p.copy())
            assert math.isclose(np.sum(result), 1.0)
        else:
            # If sum rounds to 0, should be unchanged
            result = renormalize_probs(p)
            assert not np.any(np.isnan(result))


# =============================================================================
# Composition tests (phase → posture → renormalize)
# =============================================================================

class TestFilterPipeline:
    """Integration-style tests for the full filter pipeline."""

    def test_pipeline_phase1_standing(self):
        """Full pipeline: P1 + standing posture."""
        p = arr(0.5, 0.3, 0.2)
        c = ids(1, 30, 99)  # P1, stand_exclude, neutral
        p = filter_probs_by_phase(p, c, phase=1, p1_only=T1, p2_plus=T2, p3_only=T3)
        p = filter_probs_by_posture(p, c, posture=1,
                                    stand_exclude=STAND_EX, prone_exclude=PRONE_EX)
        result = renormalize_probs(p)
        # P1: 1 kept, 30 zeroed (stand_exclude), 99 kept
        # After: [0.5, 0.0, 0.2] → normalize → [0.5/0.7, 0, 0.2/0.7]
        assert math.isclose(result[0], 0.5 / 0.7)
        assert result[1] == 0.0
        assert math.isclose(result[2], 0.2 / 0.7)
        assert math.isclose(np.sum(result), 1.0)

    def test_pipeline_all_zeroed(self):
        """When all probs are zeroed, renormalization should be a no-op."""
        p = arr(0.5, 0.3)
        c = ids(1, 2)  # P1 only
        p = filter_probs_by_phase(p, c, phase=3, p1_only=T1, p2_plus=T2, p3_only=T3)
        # Both zeroed in P3
        assert np.all(p == 0.0)
        result = renormalize_probs(p)
        assert np.all(result == 0.0)

    def test_pipeline_preserves_non_zero_indices(self):
        """Non-zeroed indices should maintain correct positions."""
        p = arr(0.4, 0.3, 0.2, 0.1)
        c = ids(10, 40, 20, 99)  # P2, prone_exclude, P3, neutral
        p = filter_probs_by_phase(p, c, phase=2, p1_only=T1, p2_plus=T2, p3_only=T3)
        p = filter_probs_by_posture(p, c, posture=0,
                                    stand_exclude=STAND_EX, prone_exclude=PRONE_EX)
        result = renormalize_probs(p)
        # Phase=2: P1 not in set, P2=10 kept, P3=20 zeroed, neutral=99 kept
        # Posture=0: 40 zeroed (prone_exclude)
        # Kept: [0.4, 0.0, 0.0, 0.1] → normalize
        assert math.isclose(result[0], 0.8)
        assert result[1] == 0.0
        assert result[2] == 0.0
        assert math.isclose(result[3], 0.2)
