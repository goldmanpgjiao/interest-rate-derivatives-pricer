"""Tests for configuration module."""

from montecarlo_ir import config


def test_default_num_paths() -> None:
    """Test default number of paths."""
    assert config.DEFAULT_NUM_PATHS == 10000


def test_default_num_steps() -> None:
    """Test default number of steps."""
    assert config.DEFAULT_NUM_STEPS == 252


def test_default_seed() -> None:
    """Test default seed."""
    assert config.DEFAULT_SEED == 42


def test_default_tolerance() -> None:
    """Test default tolerance."""
    assert config.DEFAULT_TOLERANCE == 1e-6


def test_default_day_count() -> None:
    """Test default day count convention."""
    assert config.DEFAULT_DAY_COUNT == "ACT/360"
