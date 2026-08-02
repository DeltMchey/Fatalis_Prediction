"""P3.2: Tests for src/logging_config.py — unified logging setup.

Validates:
  - setup_logging() returns a Logger instance
  - Logger effective level is WARNING
  - FileHandler encoding is utf-8
  - Logger name is configurable
  - Debug messages are suppressed
  - Multiple calls are idempotent
"""

import pytest
import logging
from pathlib import Path

from src.logging_config import setup_logging


# =============================================================================
# Helpers
# =============================================================================

def _clear_root_handlers():
    """Remove all handlers from the root logger for test isolation."""
    root = logging.getLogger()
    for h in list(root.handlers):
        root.removeHandler(h)
        h.close()


# =============================================================================
# setup_logging() return value tests
# =============================================================================

class TestSetupLogging:
    """Tests for the setup_logging() factory function."""

    def test_returns_logger_instance(self):
        """setup_logging() should return a logging.Logger instance."""
        logger = setup_logging()
        assert isinstance(logger, logging.Logger)

    def test_default_logger_name(self):
        """Default logger name should be 'BlackDragon'."""
        logger = setup_logging()
        assert logger.name == "BlackDragon"

    def test_custom_logger_name(self):
        """Should accept a custom logger name."""
        logger = setup_logging(name="TestModule")
        assert logger.name == "TestModule"

    def test_root_logger_level_is_warning(self):
        """Root logger level should be WARNING after setup_logging()."""
        _clear_root_handlers()
        setup_logging()
        root = logging.getLogger()
        assert root.level == logging.WARNING, (
            f"Root level is {root.level}, expected {logging.WARNING}"
        )

    def test_logger_effective_level_is_warning(self):
        """Child logger should inherit WARNING level from root."""
        _clear_root_handlers()
        logger = setup_logging()
        assert logger.getEffectiveLevel() == logging.WARNING, (
            f"Effective level is {logger.getEffectiveLevel()}, "
            f"expected {logging.WARNING}"
        )

    def test_root_logger_has_handlers(self):
        """Root logger should have at least one handler after setup."""
        _clear_root_handlers()
        setup_logging()
        root = logging.getLogger()
        assert len(root.handlers) > 0, "Root logger has no handlers"


# =============================================================================
# FileHandler encoding tests
# =============================================================================

class TestFileHandlerEncoding:
    """Tests for the FileHandler configuration."""

    def test_file_handler_encoding_is_utf8(self):
        """The FileHandler should use utf-8 encoding."""
        _clear_root_handlers()
        setup_logging()
        root = logging.getLogger()

        file_handlers = [
            h for h in root.handlers
            if isinstance(h, logging.FileHandler)
        ]
        assert len(file_handlers) == 1, (
            f"Expected 1 FileHandler, got {len(file_handlers)}"
        )

        handler = file_handlers[0]
        assert handler.encoding == "utf-8", (
            f"Expected utf-8 encoding, got {handler.encoding}"
        )

    def test_file_handler_writes_to_blackdragon_log(self):
        """FileHandler should write to blackdragon.log."""
        _clear_root_handlers()
        setup_logging()
        root = logging.getLogger()

        file_handlers = [
            h for h in root.handlers
            if isinstance(h, logging.FileHandler)
        ]
        assert len(file_handlers) == 1
        handler = file_handlers[0]
        assert Path(handler.baseFilename).name == "blackdragon.log"


# =============================================================================
# Log output tests (isolated — create fresh loggers, do not use basicConfig)
# =============================================================================

class TestLogOutput:
    """Tests that log output is correctly formatted and written."""

    def test_warning_is_written_to_file(self, tmp_path):
        """A WARNING log message should be written to the log file."""
        logger_name = "TestLogOutput"
        log_path = tmp_path / "test.log"

        # Create isolated logger — no basicConfig side effects
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.WARNING)
        logger.handlers.clear()
        logger.propagate = False

        fh = logging.FileHandler(str(log_path), encoding="utf-8")
        fh.setLevel(logging.WARNING)
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        )
        fh.setFormatter(formatter)
        logger.addHandler(fh)

        logger.warning("Test warning message")
        # Force flush and close to ensure write
        fh.flush()
        fh.close()

        log_content = log_path.read_text(encoding="utf-8")
        assert "[WARNING]" in log_content
        assert logger_name in log_content
        assert "Test warning message" in log_content

    def test_debug_is_suppressed(self, tmp_path):
        """A DEBUG message below WARNING level should not be written."""
        logger_name = "TestDebugSuppress"
        log_path = tmp_path / "test2.log"

        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.WARNING)
        logger.handlers.clear()
        logger.propagate = False

        fh = logging.FileHandler(str(log_path), encoding="utf-8")
        fh.setLevel(logging.WARNING)
        logger.addHandler(fh)

        logger.debug("This should be suppressed")
        fh.flush()
        fh.close()

        log_content = log_path.read_text(encoding="utf-8")
        assert "This should be suppressed" not in log_content


# =============================================================================
# Idempotency tests
# =============================================================================

class TestSetupLoggingIdempotency:
    """Tests that setup_logging can be called multiple times safely."""

    def test_multiple_calls_do_not_add_duplicate_handlers(self):
        """Calling setup_logging twice should not duplicate handlers."""
        _clear_root_handlers()

        setup_logging()
        handler_count_first = len(logging.getLogger().handlers)

        setup_logging()
        handler_count_second = len(logging.getLogger().handlers)

        # basicConfig is a no-op after the first call
        assert handler_count_second == handler_count_first, (
            f"Handler count changed: {handler_count_first} → {handler_count_second}"
        )
