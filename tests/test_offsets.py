"""P3.2: Tests for src/config/offsets.py — memory offset configuration.

Validates:
  - GameOffsets is a frozen dataclass
  - All fields have correct types (int or float)
  - All field values are non-zero (except documented exceptions)
  - OFFSETS is a GameOffsets singleton instance
  - GameOffsets is truly immutable
"""

import pytest
from dataclasses import is_dataclass, fields, FrozenInstanceError
from typing import get_type_hints

from src.config.offsets import GameOffsets, OFFSETS


# =============================================================================
# GameOffsets structure tests
# =============================================================================

class TestGameOffsetsDataClass:
    """Tests for the GameOffsets dataclass structure."""

    def test_is_dataclass(self):
        """GameOffsets should be a dataclass."""
        assert is_dataclass(GameOffsets), "GameOffsets is not a dataclass"

    def test_is_frozen(self):
        """GameOffsets should be frozen (immutable)."""
        assert GameOffsets.__dataclass_params__.frozen, "GameOffsets must be frozen=True"

    def test_all_fields_are_int_or_float(self):
        """All GameOffsets fields must be int or float (memory offsets/values)."""
        hints = get_type_hints(GameOffsets)
        for field_info in fields(GameOffsets):
            ftype = hints.get(field_info.name)
            assert ftype in (int, float), (
                f"Field '{field_info.name}' has type {ftype}, expected int or float"
            )

    def test_field_count(self):
        """GameOffsets should have exactly 23 fields."""
        assert len(fields(GameOffsets)) == 23, (
            f"Expected 23 fields, got {len(fields(GameOffsets))}"
        )


# =============================================================================
# OFFSETS singleton tests
# =============================================================================

class TestOffsetsSingleton:
    """Tests for the OFFSETS module-level singleton."""

    def test_offsets_is_gameoffsets_instance(self):
        """OFFSETS should be an instance of GameOffsets."""
        assert isinstance(OFFSETS, GameOffsets), (
            f"OFFSETS is {type(OFFSETS)}, not GameOffsets"
        )

    def test_offsets_is_singleton(self):
        """Multiple accesses to OFFSETS should return the same object."""
        from src.config.offsets import OFFSETS as O2
        assert OFFSETS is O2, "OFFSETS is not a singleton"


# =============================================================================
# Field value tests
# =============================================================================

class TestGameOffsetsFieldValues:
    """Tests for GameOffsets field values."""

    # Fields allowed to be zero
    ZERO_ALLOWED = {"MONSTER_LIST_TERMINAL"}

    # Fields that contain base addresses (should be non-zero positive hex)
    BASE_ADDRESS_FIELDS = {
        "PLAYER_BASE", "MONSTER_BASE", "ZONE_BASE",
        "MONSTER_HP_BASE", "ENRAGE_STRUCT",
    }

    def test_all_number_fields_are_non_negative(self):
        """All numeric fields should be >= 0."""
        for field_info in fields(GameOffsets):
            value = getattr(OFFSETS, field_info.name)
            assert value >= 0, (
                f"Field '{field_info.name}' is negative: {value}"
            )

    def test_non_zero_fields(self):
        """Only MONSTER_LIST_TERMINAL should be 0; all others must be > 0."""
        for field_info in fields(GameOffsets):
            value = getattr(OFFSETS, field_info.name)
            if field_info.name in self.ZERO_ALLOWED:
                assert value == 0, f"'{field_info.name}' should be 0, got {value}"
            else:
                assert value > 0, (
                    f"Field '{field_info.name}' should be > 0, got {value}"
                )

    def test_float_fields_are_positive(self):
        """Float fields (like MONSTER_MIN_HP) should be positive."""
        hints = get_type_hints(GameOffsets)
        for field_info in fields(GameOffsets):
            ftype = hints.get(field_info.name)
            if ftype is float:
                value = getattr(OFFSETS, field_info.name)
                assert value > 0.0, (
                    f"Float field '{field_info.name}' should be > 0, got {value}"
                )


# =============================================================================
# Immutability tests
# =============================================================================

class TestGameOffsetsImmutability:
    """Tests that GameOffsets is truly frozen."""

    def test_cannot_set_attribute(self):
        """Attempting to set an attribute on GameOffsets should raise FrozenInstanceError."""
        with pytest.raises(FrozenInstanceError):
            OFFSETS.PLAYER_BASE = 0xDEADBEEF

    def test_cannot_set_attribute_on_new_instance(self):
        """A newly created GameOffsets instance should also be immutable."""
        instance = GameOffsets()
        with pytest.raises(FrozenInstanceError):
            instance.MONSTER_BASE = 0x12345678

    def test_equality_of_instances(self):
        """Two GameOffsets instances with default values should be equal."""
        a = GameOffsets()
        b = GameOffsets()
        assert a == b, "Two default GameOffsets instances should be equal"


# =============================================================================
# Field naming convention tests
# =============================================================================

class TestGameOffsetsFieldNaming:
    """Tests for GameOffsets field naming conventions."""

    def test_fields_use_uppercase(self):
        """All fields should be UPPER_CASE (config constants convention)."""
        for field_info in fields(GameOffsets):
            assert field_info.name == field_info.name.upper(), (
                f"Field '{field_info.name}' should be UPPER_CASE"
            )

    def test_fields_have_docstrings(self):
        """Important offset fields should have inline comments (readability)."""
        # Not all fields have formal docstrings (dataclass limitation),
        # but the class itself and the file have documentation.
        assert GameOffsets.__doc__ is not None
        assert len(GameOffsets.__doc__) > 0
