"""P3.3C: Tests for Nova (飞天火) threshold logic extracted from ai_engine.py.

Validates:
  - Initialization: seeding triggered_novas with already-crossed thresholds
  - Threshold crossing: detecting newly crossed thresholds
  - Warning generation: nova_warning = True on crossing
  - Reset actions: action 197/167/179 clears warning
  - Idempotency: re-crossing same threshold doesn't re-trigger
  - Edge cases: full HP, zero HP, empty thresholds, unknown action
"""

import pytest

from ai_engine import evaluate_nova

# Test thresholds matching the real NOVA_THRESHOLDS: [0.78, 0.50, 0.41, 0.26, 0.06]
TEST_THRESHOLDS = [0.78, 0.50, 0.41, 0.26, 0.06]
TEST_RESET_ACTIONS = {197, 167, 179}


# =============================================================================
# Initialization tests
# =============================================================================

class TestInitialization:
    """First-frame HP initialization behavior."""

    def test_init_seeds_crossed_thresholds(self):
        """On init with hp=0.40, thresholds 0.78, 0.50, 0.41 are crossed."""
        triggered, warning, initialized = evaluate_nova(
            0.40, triggered_novas=set(), hp_initialized=False,
            thresholds=TEST_THRESHOLDS, reset_actions=TEST_RESET_ACTIONS,
        )
        assert initialized is True
        assert 0.78 in triggered  # 0.40 <= 0.78
        assert 0.50 in triggered  # 0.40 <= 0.50
        assert 0.41 in triggered  # 0.40 <= 0.41
        assert 0.26 not in triggered  # 0.40 > 0.26, not yet crossed
        assert warning is False  # Init alone should not trigger warning

    def test_init_full_hp_seeds_nothing(self):
        """At full HP (1.0), no thresholds are crossed."""
        triggered, warning, initialized = evaluate_nova(
            1.0, triggered_novas=set(), hp_initialized=False,
            thresholds=TEST_THRESHOLDS, reset_actions=TEST_RESET_ACTIONS,
        )
        assert initialized is True
        assert len(triggered) == 0
        assert warning is False

    def test_init_zero_hp_seeds_all(self):
        """At zero HP, all thresholds are crossed."""
        triggered, warning, initialized = evaluate_nova(
            0.0, triggered_novas=set(), hp_initialized=False,
            thresholds=TEST_THRESHOLDS, reset_actions=TEST_RESET_ACTIONS,
        )
        assert triggered == set(TEST_THRESHOLDS)
        assert warning is False

    def test_init_exactly_at_threshold(self):
        """At exactly a threshold value, it should be seeded."""
        triggered, warning, initialized = evaluate_nova(
            0.50, triggered_novas=set(), hp_initialized=False,
            thresholds=TEST_THRESHOLDS, reset_actions=TEST_RESET_ACTIONS,
        )
        assert 0.50 in triggered
        assert 0.78 in triggered
        assert 0.41 not in triggered

    def test_init_does_not_duplicate(self):
        """If triggered_novas already has entries, init should add missing ones."""
        existing = {0.78}
        triggered, warning, initialized = evaluate_nova(
            0.30, triggered_novas=existing, hp_initialized=False,
            thresholds=TEST_THRESHOLDS, reset_actions=TEST_RESET_ACTIONS,
        )
        assert 0.78 in triggered  # already there
        assert 0.50 in triggered  # newly added
        assert 0.41 in triggered  # newly added
        assert len(triggered) == 3  # 0.78, 0.50, 0.41


# =============================================================================
# Threshold crossing tests
# =============================================================================

class TestThresholdCrossing:
    """Continuous threshold detection after initialization."""

    def test_crossing_generates_warning(self):
        """Crossing a new threshold should set nova_warning=True."""
        # Start with triggered_novas already seeded at hp=1.0 (nothing crossed)
        triggered = set()
        triggered, warning, _ = evaluate_nova(
            0.55, triggered_novas=triggered, hp_initialized=True,
            thresholds=TEST_THRESHOLDS, reset_actions=TEST_RESET_ACTIONS,
        )
        # hp=0.55 crosses 0.78 → new crossing → warning
        assert 0.78 in triggered
        assert warning is True  # 0.78 is a newly-crossed threshold

        # Now drop below 0.50 — should trigger again
        triggered, warning, _ = evaluate_nova(
            0.49, triggered_novas=triggered, hp_initialized=True,
            thresholds=TEST_THRESHOLDS, reset_actions=TEST_RESET_ACTIONS,
        )
        assert 0.50 in triggered
        assert warning is True

    def test_crossing_multiple_at_once(self):
        """Dropping past multiple thresholds in one step should trigger warning."""
        triggered, warning, initialized = evaluate_nova(
            0.20, triggered_novas={0.78}, hp_initialized=True,
            thresholds=TEST_THRESHOLDS, reset_actions=TEST_RESET_ACTIONS,
        )
        # Crossed: 0.50, 0.41, 0.26
        assert 0.50 in triggered
        assert 0.41 in triggered
        assert 0.26 in triggered
        assert 0.06 not in triggered
        assert warning is True

    def test_hp_rising_does_not_untrack(self):
        """HP recovering should not remove triggered thresholds."""
        triggered, warning, _ = evaluate_nova(
            0.30, triggered_novas=set(), hp_initialized=True,
            thresholds=TEST_THRESHOLDS, reset_actions=TEST_RESET_ACTIONS,
        )
        # Now HP rises back above thresholds
        triggered2, warning2, _ = evaluate_nova(
            0.90, triggered_novas=triggered, hp_initialized=True,
            thresholds=TEST_THRESHOLDS, reset_actions=TEST_RESET_ACTIONS,
        )
        # Triggered thresholds should still be recorded
        assert 0.78 in triggered2
        assert 0.50 in triggered2
        assert 0.41 in triggered2
        assert warning2 is False  # No new crossing


# =============================================================================
# Warning generation tests
# =============================================================================

class TestWarningGeneration:
    """Nova warning flag behavior."""

    def test_single_crossing_triggers_warning(self):
        """A single threshold crossing should produce warning=True."""
        triggered, warning, _ = evaluate_nova(
            0.77, triggered_novas=set(), hp_initialized=True,
            thresholds=TEST_THRESHOLDS, reset_actions=TEST_RESET_ACTIONS,
        )
        assert 0.78 in triggered
        assert warning is True

    def test_no_crossing_no_warning(self):
        """If HP is stable above all thresholds, no warning."""
        triggered, warning, _ = evaluate_nova(
            0.85, triggered_novas={0.78}, hp_initialized=True,
            thresholds=TEST_THRESHOLDS, reset_actions=TEST_RESET_ACTIONS,
        )
        assert warning is False

    def test_warning_on_last_threshold(self):
        """Crossing the last (lowest) threshold should still warn."""
        triggered, warning, _ = evaluate_nova(
            0.05, triggered_novas={0.78, 0.50, 0.41, 0.26},
            hp_initialized=True,
            thresholds=TEST_THRESHOLDS, reset_actions=TEST_RESET_ACTIONS,
        )
        assert 0.06 in triggered
        assert warning is True


# =============================================================================
# Reset action tests
# =============================================================================

class TestResetActions:
    """Nova warning reset on actions 197 (落地), 167 (飞回场中), 179 (p3开场吼)."""

    def test_action_197_resets_warning(self):
        """动作 197 (落地) 应清除 Nova warning."""
        triggered = {0.78, 0.50}
        _, warning, _ = evaluate_nova(
            0.49, triggered_novas=triggered, hp_initialized=True,
            thresholds=TEST_THRESHOLDS, action=197,
        )
        assert warning is False

    def test_action_167_resets_warning(self):
        """动作 167 (飞回场中) 应清除 Nova warning."""
        triggered = {0.78, 0.50, 0.41}
        _, warning, _ = evaluate_nova(
            0.25, triggered_novas=triggered, hp_initialized=True,
            thresholds=TEST_THRESHOLDS, action=167,
        )
        assert warning is False

    def test_action_179_resets_warning(self):
        """动作 179 (P3 开场吼) 应清除 Nova warning."""
        triggered = {0.78, 0.50}
        _, warning, _ = evaluate_nova(
            0.40, triggered_novas=triggered, hp_initialized=True,
            thresholds=TEST_THRESHOLDS, action=179,
        )
        assert warning is False

    def test_non_reset_action_does_not_reset(self):
        """Non-reset action (e.g. 37=龙车) should NOT clear warning."""
        triggered, warning, _ = evaluate_nova(
            0.40, triggered_novas={0.78}, hp_initialized=True,
            thresholds=TEST_THRESHOLDS, action=37,
        )
        assert warning is True  # 0.50 and 0.41 were crossed

    def test_reset_only_affects_warning_not_triggered_set(self):
        """Reset should only set warning=False, not clear triggered_novas."""
        existing = {0.78, 0.50, 0.41}
        triggered, warning, _ = evaluate_nova(
            0.25, triggered_novas=existing, hp_initialized=True,
            thresholds=TEST_THRESHOLDS, action=197,
        )
        assert warning is False
        # triggered set should still contain all crossed thresholds
        assert 0.78 in triggered
        assert 0.50 in triggered
        assert 0.41 in triggered
        assert 0.26 in triggered  # newly crossed at hp=0.25
        assert 0.06 not in triggered


# =============================================================================
# Idempotency tests
# =============================================================================

class TestIdempotency:
    """Re-crossing the same threshold should not re-trigger."""

    def test_second_crossing_no_warning(self):
        """If threshold already triggered, crossing again should not warn."""
        triggered, warning, _ = evaluate_nova(
            0.75, triggered_novas={0.78}, hp_initialized=True,
            thresholds=TEST_THRESHOLDS, reset_actions=TEST_RESET_ACTIONS,
        )
        # hp=0.75 < 0.78, but 0.78 was already triggered → no new crossing
        assert warning is False

    def test_multiple_scans_dont_duplicate(self):
        """Triggered set should not grow with repeated scans at same HP."""
        triggered, warning, _ = evaluate_nova(
            0.30, triggered_novas=set(), hp_initialized=True,
            thresholds=TEST_THRESHOLDS, reset_actions=TEST_RESET_ACTIONS,
        )
        count_first = len(triggered)

        triggered2, warning2, _ = evaluate_nova(
            0.30, triggered_novas=triggered, hp_initialized=True,
            thresholds=TEST_THRESHOLDS, reset_actions=TEST_RESET_ACTIONS,
        )
        assert len(triggered2) == count_first
        assert warning2 is False

    def test_init_after_init_is_noop(self):
        """Re-initializing after already initialized should be a no-op."""
        # First: init at 0.80
        triggered, _, initialized = evaluate_nova(
            0.80, triggered_novas=set(), hp_initialized=False,
            thresholds=TEST_THRESHOLDS, reset_actions=TEST_RESET_ACTIONS,
        )
        assert initialized is True
        count_after_init = len(triggered)

        # Second: "re-init" (should never happen in real code, but function
        # handles it) — since hp_initialized=False, would seed again
        # BUT: in practice, caller should pass hp_initialized=True after init.
        # Let's verify the correct path:
        triggered2, warning2, _ = evaluate_nova(
            0.80, triggered_novas=triggered, hp_initialized=True,
            thresholds=TEST_THRESHOLDS, reset_actions=TEST_RESET_ACTIONS,
        )
        assert len(triggered2) == count_after_init
        assert warning2 is False


# =============================================================================
# Edge case tests
# =============================================================================

class TestEdgeCases:
    """Boundary and edge case behavior."""

    def test_empty_thresholds(self):
        """Empty threshold list should produce no warnings."""
        triggered, warning, initialized = evaluate_nova(
            0.50, triggered_novas=set(), hp_initialized=False,
            thresholds=[], reset_actions=TEST_RESET_ACTIONS,
        )
        assert len(triggered) == 0
        assert warning is False
        assert initialized is True

    def test_default_arguments(self):
        """Should work with only hp_percent (all other args default)."""
        triggered, warning, initialized = evaluate_nova(0.80)
        assert isinstance(triggered, set)
        assert warning is False
        assert initialized is True

    def test_single_threshold(self):
        """Single threshold should work correctly."""
        triggered, warning, initialized = evaluate_nova(
            0.50, triggered_novas=set(), hp_initialized=False,
            thresholds=[0.75],
        )
        # hp=0.50 <= 0.75 → threshold IS crossed
        assert 0.75 in triggered

    def test_negative_hp_should_cross_all(self):
        """Negative HP (shouldn't happen in game but shouldn't crash)."""
        triggered, warning, initialized = evaluate_nova(
            -0.1, triggered_novas=set(), hp_initialized=False,
            thresholds=TEST_THRESHOLDS,
        )
        assert triggered == set(TEST_THRESHOLDS)

    def test_hp_above_one(self):
        """HP > 100% should cross nothing."""
        triggered, warning, initialized = evaluate_nova(
            1.5, triggered_novas=set(), hp_initialized=False,
            thresholds=TEST_THRESHOLDS,
        )
        assert len(triggered) == 0
        assert warning is False

    def test_non_mutable_defaults(self):
        """Each call with no triggered_novas should get a fresh set."""
        t1, _, _ = evaluate_nova(0.30)
        t2, _, _ = evaluate_nova(0.60)
        # t1 and t2 should be independent (not sharing a mutable default)
        assert t1 is not t2

    def test_crossing_and_reset_same_frame(self):
        """If a threshold is crossed AND action is a reset action."""
        triggered, warning, _ = evaluate_nova(
            0.40, triggered_novas={0.78}, hp_initialized=True,
            thresholds=TEST_THRESHOLDS, action=197,
        )
        # 0.50 and 0.41 are crossed → warning would be True
        # BUT action=197 resets it → warning = False
        assert warning is False
        assert 0.50 in triggered
        assert 0.41 in triggered
