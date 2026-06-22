"""Unified logging configuration for BlackDragon.

Usage:
    from src.logging_config import setup_logging
    logger = setup_logging()
"""

import logging


def setup_logging(name: str = "BlackDragon") -> logging.Logger:
    """Configure and return a logger that writes to blackdragon.log.

    Log levels used across the project:
    - WARNING: Recoverable errors (recording thread glitch, font fallback)
    - ERROR:   Non-recoverable errors (model load failure, UI crash, process attach failure)
    """
    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler("blackdragon.log", encoding="utf-8"),
        ],
    )
    return logging.getLogger(name)
