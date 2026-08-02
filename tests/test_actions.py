"""P3.2: Tests for src/config/actions.py — action database integrity.

Validates:
  - ACTION_DB size and content
  - ACTION_MAPPING size and key validity
  - Phase-specific sets are mutually disjoint
  - Posture transition sets are mutually disjoint
  - NOVA_THRESHOLDS ordering
  - SCRIPTED_IDS range
  - DOWN_IDS / MINOR_AND_PASSIVE overlap (by design)
"""

import pytest
from src.config.actions import (
    ACTION_DB, ACTION_MAPPING,
    P1_ONLY_IDS, P2_PLUS_IDS, P3_ONLY_IDS,
    DOWN_IDS, SCRIPTED_IDS, MINOR_AND_PASSIVE,
    NOVA_THRESHOLDS,
    POSTURE_STAND, POSTURE_PRONE, POSTURE_FLY,
)


# =============================================================================
# ACTION_DB tests
# =============================================================================

class TestActionDB:
    """Tests for ACTION_DB: action ID → action name mapping."""

    def test_action_db_has_expected_size(self):
        """ACTION_DB should contain all known action ID→name mappings."""
        assert len(ACTION_DB) == 174

    def test_action_db_all_keys_are_positive_ints(self):
        """All ACTION_DB keys should be positive integers."""
        for key in ACTION_DB:
            assert isinstance(key, int), f"Key {key} is not int"
            assert key > 0, f"Key {key} is not positive"

    def test_action_db_all_values_are_non_empty_strings(self):
        """All ACTION_DB values should be non-empty strings."""
        for key, value in ACTION_DB.items():
            assert isinstance(value, str), f"Value for {key} is not str"
            assert len(value) > 0, f"Value for {key} is empty"

    def test_action_db_keys_are_unique(self):
        """ACTION_DB keys (action IDs) must all be unique."""
        assert len(ACTION_DB.keys()) == len(set(ACTION_DB.keys()))


# =============================================================================
# ACTION_MAPPING tests
# =============================================================================

class TestActionMapping:
    """Tests for ACTION_MAPPING: animation frame → base action ID."""

    def test_action_mapping_has_expected_size(self):
        """ACTION_MAPPING should contain 54 entries (per code comment)."""
        assert len(ACTION_MAPPING) == 54

    def test_action_mapping_keys_exist_in_action_db(self):
        """Every ACTION_MAPPING key must exist in ACTION_DB."""
        missing = [k for k in ACTION_MAPPING if k not in ACTION_DB]
        assert not missing, f"Missing from ACTION_DB: {missing}"

    def test_action_mapping_values_exist_in_action_db(self):
        """Every ACTION_MAPPING value must exist in ACTION_DB."""
        missing = [v for v in ACTION_MAPPING.values() if v not in ACTION_DB]
        assert not missing, f"Missing from ACTION_DB: {missing}"

    def test_action_mapping_keys_are_unique(self):
        """ACTION_MAPPING keys must be unique (no duplicate mappings)."""
        assert len(ACTION_MAPPING.keys()) == len(set(ACTION_MAPPING.keys()))


# =============================================================================
# Phase-specific set tests
# =============================================================================

class TestPhaseSets:
    """Tests for P1_ONLY_IDS, P2_PLUS_IDS, P3_ONLY_IDS."""

    def test_phase_sets_are_mutually_disjoint(self):
        """P1_ONLY, P2_PLUS, and P3_ONLY must not overlap."""
        assert P1_ONLY_IDS.isdisjoint(P2_PLUS_IDS), (
            f"Overlap: {P1_ONLY_IDS & P2_PLUS_IDS}"
        )
        assert P1_ONLY_IDS.isdisjoint(P3_ONLY_IDS), (
            f"Overlap: {P1_ONLY_IDS & P3_ONLY_IDS}"
        )
        assert P2_PLUS_IDS.isdisjoint(P3_ONLY_IDS), (
            f"Overlap: {P2_PLUS_IDS & P3_ONLY_IDS}"
        )

    def test_phase_ids_exist_in_action_db(self):
        """All phase set IDs should be valid action IDs."""
        for set_name, id_set in [
            ("P1_ONLY_IDS", P1_ONLY_IDS),
            ("P2_PLUS_IDS", P2_PLUS_IDS),
            ("P3_ONLY_IDS", P3_ONLY_IDS),
        ]:
            missing = [i for i in id_set if i not in ACTION_DB]
            assert not missing, f"{set_name} has invalid IDs: {missing}"


# =============================================================================
# Posture transition tests
# =============================================================================

class TestPostureSets:
    """Tests for POSTURE_STAND, POSTURE_PRONE, POSTURE_FLY."""

    def test_posture_sets_are_mutually_disjoint(self):
        """No action ID should trigger more than one posture."""
        assert POSTURE_STAND.isdisjoint(POSTURE_PRONE), (
            f"Overlap: {POSTURE_STAND & POSTURE_PRONE}"
        )
        assert POSTURE_STAND.isdisjoint(POSTURE_FLY), (
            f"Overlap: {POSTURE_STAND & POSTURE_FLY}"
        )
        assert POSTURE_PRONE.isdisjoint(POSTURE_FLY), (
            f"Overlap: {POSTURE_PRONE & POSTURE_FLY}"
        )

    def test_posture_ids_exist_in_action_db(self):
        """All posture trigger IDs should be valid action IDs."""
        for set_name, id_set in [
            ("POSTURE_STAND", POSTURE_STAND),
            ("POSTURE_PRONE", POSTURE_PRONE),
            ("POSTURE_FLY", POSTURE_FLY),
        ]:
            missing = [i for i in id_set if i not in ACTION_DB]
            assert not missing, f"{set_name} has invalid IDs: {missing}"

    def test_posture_sets_are_non_empty(self):
        """Each posture set should contain at least one trigger."""
        assert len(POSTURE_STAND) > 0
        assert len(POSTURE_PRONE) > 0
        assert len(POSTURE_FLY) > 0


# =============================================================================
# NOVA_THRESHOLDS tests
# =============================================================================

class TestNovaThresholds:
    """Tests for NOVA_THRESHOLDS."""

    def test_thresholds_are_descending(self):
        """NOVA_THRESHOLDS must be in strictly descending order."""
        for i in range(len(NOVA_THRESHOLDS) - 1):
            assert NOVA_THRESHOLDS[i] > NOVA_THRESHOLDS[i + 1], (
                f"NOVA_THRESHOLDS[{i}]={NOVA_THRESHOLDS[i]} "
                f"<= NOVA_THRESHOLDS[{i + 1}]={NOVA_THRESHOLDS[i + 1]}"
            )

    def test_thresholds_are_probabilities(self):
        """All NOVA_THRESHOLDS should be in (0, 1) range."""
        for t in NOVA_THRESHOLDS:
            assert 0.0 < t < 1.0, f"Threshold {t} not in (0, 1)"


# =============================================================================
# SCRIPTED_IDS range tests
# =============================================================================

class TestScriptedIDs:
    """Tests for SCRIPTED_IDS."""

    def test_scripted_ids_is_range_157_to_197(self):
        """SCRIPTED_IDS should be the contiguous range 157..197."""
        expected = set(range(157, 198))  # 157 inclusive, 198 exclusive
        assert SCRIPTED_IDS == expected, (
            f"SCRIPTED_IDS missing: {expected - SCRIPTED_IDS}, "
            f"extra: {SCRIPTED_IDS - expected}"
        )


# =============================================================================
# DOWN_IDS and MINOR_AND_PASSIVE overlap tests
# =============================================================================

class TestDownAndMinorSets:
    """Tests for DOWN_IDS and MINOR_AND_PASSIVE relationship."""

    def test_down_ids_are_subset_of_minor_and_passive(self):
        """DOWN_IDS should be a subset of MINOR_AND_PASSIVE (by design)."""
        assert DOWN_IDS.issubset(MINOR_AND_PASSIVE), (
            f"DOWN_IDS not in MINOR_AND_PASSIVE: {DOWN_IDS - MINOR_AND_PASSIVE}"
        )

    def test_minor_and_passive_has_more_than_down_ids(self):
        """MINOR_AND_PASSIVE should contain more than just DOWN_IDS."""
        assert len(MINOR_AND_PASSIVE) > len(DOWN_IDS), (
            "MINOR_AND_PASSIVE should be a strict superset of DOWN_IDS"
        )

    def test_down_ids_exist_in_action_db(self):
        """All DOWN_IDS should be valid action IDs."""
        missing = [i for i in DOWN_IDS if i not in ACTION_DB]
        assert not missing, f"DOWN_IDS has invalid IDs: {missing}"

    def test_minor_and_passive_ids_exist_in_action_db(self):
        """All MINOR_AND_PASSIVE IDs should be valid action IDs."""
        missing = [i for i in MINOR_AND_PASSIVE if i not in ACTION_DB]
        assert not missing, f"MINOR_AND_PASSIVE has invalid IDs: {missing}"
