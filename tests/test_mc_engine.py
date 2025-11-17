"""Tests for MonteCarloEngine."""

from datetime import date

import numpy as np
import pytest

from montecarlo_ir.market_data.yield_curve import build_yield_curve_from_zero_rates
from montecarlo_ir.models.hull_white import HullWhite1F
from montecarlo_ir.models.lmm import LIBORMarketModel
from montecarlo_ir.pricing.mc_engine import (
    MonteCarloEngine,
    align_simulation_grid,
)
from montecarlo_ir.utils.date_helpers import DayCountConvention


def build_simple_yield_curve() -> "YieldCurve":
    """Create a simple flat yield curve for testing."""
    val = date(2024, 1, 1)
    pillars = (date(2025, 1, 1), date(2026, 1, 1))
    zeros = (0.02, 0.025)
    return build_yield_curve_from_zero_rates(
        valuation_date=val,
        pillar_dates=pillars,
        zero_rates=zeros,
        day_count=DayCountConvention.ACT_365,
    )


def build_hw_model() -> HullWhite1F:
    """Create a Hull-White model for testing."""
    curve = build_simple_yield_curve()
    return HullWhite1F(
        yield_curve=curve,
        mean_reversion=0.1,
        volatility=0.01,
        scheme="exact",
    )


def build_lmm_model() -> LIBORMarketModel:
    """Create an LMM model for testing."""
    curve = build_simple_yield_curve()
    tenors = (date(2024, 1, 1), date(2025, 1, 1), date(2026, 1, 1))
    return LIBORMarketModel(
        yield_curve=curve,
        tenor_structure=tenors,
        volatilities=(0.15, 0.16),
        scheme="log_euler",
    )


class TestMonteCarloEngineConstruction:
    """Tests for MonteCarloEngine construction."""

    def test_requires_positive_num_paths(self) -> None:
        """Test that num_paths must be positive."""
        model = build_hw_model()
        with pytest.raises(ValueError, match="num_paths must be positive"):
            MonteCarloEngine(model=model, num_paths=0)

    def test_seed_setting(self) -> None:
        """Test that seed can be set."""
        model = build_hw_model()
        engine = MonteCarloEngine(model=model, num_paths=100, seed=42)
        assert engine.seed == 42


class TestMonteCarloPricing:
    """Tests for Monte Carlo pricing."""

    def test_price_with_hull_white(self) -> None:
        """Test pricing with Hull-White model."""
        model = build_hw_model()
        engine = MonteCarloEngine(model=model, num_paths=1000, seed=42)

        def payoff_fn(rates: np.ndarray, times: np.ndarray) -> float:
            # Simple payoff: max(0, rate_at_end - 0.02)
            return max(0.0, rates[-1] - 0.02)

        times = [0.0, 0.25, 0.5, 1.0]
        result = engine.price(
            payoff_fn=payoff_fn,
            simulation_times=times,
            valuation_date=date(2024, 1, 1),
        )

        assert result.price >= 0.0
        assert result.standard_error >= 0.0
        assert result.num_paths == 1000

    def test_price_with_lmm(self) -> None:
        """Test pricing with LMM model."""
        model = build_lmm_model()
        engine = MonteCarloEngine(model=model, num_paths=1000, seed=42)

        def payoff_fn(forward_rates: np.ndarray, times: np.ndarray) -> float:
            # Simple payoff based on first forward rate at end
            return float(forward_rates[-1, 0] - 0.02)

        times = [0.0, 0.25, 0.5, 1.0]
        result = engine.price(
            payoff_fn=payoff_fn,
            simulation_times=times,
            valuation_date=date(2024, 1, 1),
        )

        assert result.standard_error >= 0.0
        assert result.num_paths == 1000

    def test_price_with_antithetic(self) -> None:
        """Test pricing with antithetic variates."""
        model = build_hw_model()
        engine = MonteCarloEngine(
            model=model, num_paths=1000, seed=42, use_antithetic=True
        )

        def payoff_fn(rates: np.ndarray, times: np.ndarray) -> float:
            return float(rates[-1])

        times = [0.0, 0.5, 1.0]
        result = engine.price(
            payoff_fn=payoff_fn,
            simulation_times=times,
            valuation_date=date(2024, 1, 1),
        )

        assert result.num_paths == 1000
        assert result.standard_error >= 0.0

    def test_price_returns_paths(self) -> None:
        """Test that paths can be returned."""
        model = build_hw_model()
        engine = MonteCarloEngine(model=model, num_paths=100, seed=42)

        def payoff_fn(rates: np.ndarray, times: np.ndarray) -> float:
            return float(rates[-1])

        times = [0.0, 0.5, 1.0]
        result = engine.price(
            payoff_fn=payoff_fn,
            simulation_times=times,
            valuation_date=date(2024, 1, 1),
            return_paths=True,
        )

        assert result.paths is not None
        assert result.paths.shape[0] == 100
        assert result.paths.shape[1] == len(times)

    def test_price_empty_times(self) -> None:
        """Test error when simulation_times is empty."""
        model = build_hw_model()
        engine = MonteCarloEngine(model=model, num_paths=100)

        def payoff_fn(rates: np.ndarray, times: np.ndarray) -> float:
            return 0.0

        with pytest.raises(ValueError, match="must not be empty"):
            engine.price(
                payoff_fn=payoff_fn,
                simulation_times=[],
                valuation_date=date(2024, 1, 1),
            )


class TestDiscountFactors:
    """Tests for discount factor computation."""

    def test_compute_discount_factors_hw(self) -> None:
        """Test discount factor computation for Hull-White."""
        model = build_hw_model()
        engine = MonteCarloEngine(model=model, num_paths=10, seed=42)

        times = [0.0, 0.5, 1.0]
        # Simulate a few paths
        paths = []
        for _ in range(10):
            path = model.simulate_short_rate_path(times)
            paths.append(path)
        paths_array = np.array(paths)

        dfs = engine.compute_discount_factors(
            paths_array, np.array(times), date(2024, 1, 1)
        )

        assert dfs.shape == (10, 3)
        assert np.all(dfs[:, 0] == 1.0)  # DF at t=0 is 1
        assert np.all(dfs > 0.0)  # All DFs positive
        assert np.all(dfs <= 1.0)  # All DFs <= 1


class TestGridAlignment:
    """Tests for simulation grid alignment."""

    def test_align_grid_basic(self) -> None:
        """Test basic grid alignment."""
        val_date = date(2024, 1, 1)
        important_dates = [date(2024, 6, 1), date(2025, 1, 1)]
        grid = align_simulation_grid(val_date, important_dates)

        assert 0.0 in grid
        assert len(grid) >= 3  # At least start + 2 dates
        assert all(t >= 0.0 for t in grid)
        assert grid == sorted(grid)  # Sorted

    def test_align_grid_with_large_gaps(self) -> None:
        """Test grid alignment with large gaps."""
        val_date = date(2024, 1, 1)
        important_dates = [date(2026, 1, 1)]  # 2 years away
        grid = align_simulation_grid(val_date, important_dates, max_step_size=0.25)

        # Should have intermediate points
        assert len(grid) > 2
        # Check step sizes
        for i in range(1, len(grid)):
            dt = grid[i] - grid[i - 1]
            assert dt <= 0.25 + 1e-6  # Allow small tolerance

    def test_align_grid_filters_past_dates(self) -> None:
        """Test that past dates are filtered out."""
        val_date = date(2024, 1, 1)
        important_dates = [date(2023, 12, 1), date(2024, 6, 1)]  # One past, one future
        grid = align_simulation_grid(val_date, important_dates)

        # Should only include future dates
        assert all(t >= 0.0 for t in grid)

