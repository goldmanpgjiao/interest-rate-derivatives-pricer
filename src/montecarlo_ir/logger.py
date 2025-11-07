"""Logging configuration for the montecarlo_ir package."""

import logging
import sys

logger: logging.Logger | None = None


def setup_logger(
    name: str = "montecarlo_ir",
    level: int = logging.INFO,
    format_string: str | None = None,
) -> logging.Logger:
    """Set up and return a logger for the package.

    Args:
        name: Logger name. Defaults to "montecarlo_ir".
        level: Logging level. Defaults to logging.INFO.
        format_string: Custom format string. If None, uses default format.

    Returns:
        Configured logger instance.
    """
    global logger

    if logger is not None:
        return logger

    if format_string is None:
        format_string = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    formatter = logging.Formatter(format_string)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.addHandler(handler)

    return logger


def get_logger() -> logging.Logger:
    """Get the package logger, creating it if necessary.

    Returns:
        Logger instance.
    """
    global logger
    if logger is None:
        return setup_logger()
    return logger
