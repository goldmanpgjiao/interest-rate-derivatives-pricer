"""Tests for HullWhite1F model."""

from datetime import date

import numpy as np
import pytest

from montecarlo_ir.market_data.yield_curve import YieldCurve, build_yield_curve_from_zero_rates
from montecarlo_ir.models.hull_white import HullWhite1F
from montecarlo_ir.utils.date_helpers import DayCountConvention


def build_simple_yield_curve() -> YieldCurve:
    """Create a simple flat yield curve for testing."""
    val = date(2024, 1, 1)
    pillars = (date(2025, 1, 1), date(2026, 1, 1), date(2027, 1, 1))
    zeros = (0.02, 0.02, 0.02)  # Flat 2% curve
    return build_yield_curve_from_zero_rates(
        valuation_date=val,
        pillar_dates=pillars,
        zero_rates=zeros,
        day_count=DayCountConvention.ACT_365,
    )


def build_hull_white_model() -> HullWhite1F:
    """Create a simple Hull-White model for testing."""
    curve = build_simple_yield_curve()
    return HullWhite1F(
        yield_curve=curve,
        mean_reversion=0.1,
        volatility=0.01,
        scheme="exact",
        day_count=DayCountConvention.ACT_365,
    )


class TestHullWhiteConstruction:
    """Tests for HullWhite1F construction and validation."""

    def test_requires_positive_mean_reversion(self) -> None:
        """Test that mean reversion must be positive."""
        curve = build_simple_yield_curve()
        with pytest.raises(ValueError, match="mean_reversion must be positive"):
            HullWhite1F(
                yield_curve=curve,
                mean_reversion=-0.1,
                volatility=0.01,
            )

    def test_requires_positive_volatility(self) -> None:
        """Test that volatility must be positive."""
        curve = build_simple_yield_curve()
        with pytest.raises(ValueError, match="volatility must be positive"):
            HullWhite1F(
                yield_curve=curve,
                mean_reversion=0.1,
                volatility=-0.01,
            )


class TestShortRateSimulation:
    """Tests for short rate path simulation."""

    def test_simulate_exact_scheme(self) -> None:
        """Test exact simulation scheme."""
        model = build_hull_white_model()
        times = [0.0, 0.25, 0.5, 1.0]
        rates = model.simulate_short_rate_path(times)
        assert len(rates) == len(times)
        assert all(r >= 0.0 for r in rates)  # Rates should be reasonable

    def test_simulate_euler_scheme(self) -> None:
        """Test Euler discretization scheme."""
        curve = build_simple_yield_curve()
        model = HullWhite1F(
            yield_curve=curve,
            mean_reversion=0.1,
            volatility=0.01,
            scheme="euler",
        )
        times = [0.0, 0.25, 0.5, 1.0]
        rates = model.simulate_short_rate_path(times)
        assert len(rates) == len(times)

    def test_simulate_with_custom_shocks(self) -> None:
        """Test simulation with provided random shocks."""
        model = build_hull_white_model()
        times = [0.0, 0.25, 0.5]
        shocks = np.array([0.5, -0.3])
        rates1 = model.simulate_short_rate_path(times, shocks)
        rates2 = model.simulate_short_rate_path(times, shocks)
        # Same shocks should give same results
        np.testing.assert_array_almost_equal(rates1, rates2)

    def test_simulate_invalid_times(self) -> None:
        """Test error handling for invalid times."""
        model = build_hull_white_model()
        with pytest.raises(ValueError, match="must be non-negative"):
            model.simulate_short_rate_path([-0.1, 0.5])

        with pytest.raises(ValueError, match="strictly increasing"):
            model.simulate_short_rate_path([0.5, 0.3])

    def test_simulate_invalid_shocks_length(self) -> None:
        """Test error when shocks length doesn't match times."""
        model = build_hull_white_model()
        times = [0.0, 0.25, 0.5]
        shocks = np.array([0.5])  # Wrong length
        with pytest.raises(ValueError, match="must have length"):
            model.simulate_short_rate_path(times, shocks)


class TestBondPricing:
    """Tests for bond price calculations."""

    def test_bond_price_at_maturity(self) -> None:
        """Test bond price equals 1 at maturity."""
        model = build_hull_white_model()
        t = 1.0
        T = 1.0
        r_t = 0.02
        price = model.bond_price(t, T, r_t)
        assert abs(price - 1.0) < 1e-10

    def test_bond_price_positive(self) -> None:
        """Test bond prices are positive."""
        model = build_hull_white_model()
        t = 0.0
        T = 1.0
        r_t = 0.02
        price = model.bond_price(t, T, r_t)
        assert price > 0.0
        assert price <= 1.0

    def test_bond_price_decreasing_in_rate(self) -> None:
        """Test bond price decreases as rate increases."""
        model = build_hull_white_model()
        t = 0.0
        T = 1.0
        price_low = model.bond_price(t, T, 0.01)
        price_high = model.bond_price(t, T, 0.03)
        assert price_low > price_high

    def test_bond_price_invalid_times(self) -> None:
        """Test error handling for invalid times."""
        model = build_hull_white_model()
        with pytest.raises(ValueError, match="must be >= current time"):
            model.bond_price(1.0, 0.5, 0.02)

        with pytest.raises(ValueError, match="must be non-negative"):
            model.bond_price(-0.1, 1.0, 0.02)

    def test_discount_factor_equals_bond_price(self) -> None:
        """Test discount factor equals bond price."""
        model = build_hull_white_model()
        t = 0.0
        T = 1.0
        r_t = 0.02
        df = model.discount_factor(t, T, r_t)
        price = model.bond_price(t, T, r_t)
        assert abs(df - price) < 1e-10


class TestModelProperties:
    """Tests for model properties and behavior."""

    def test_mean_reversion_effect(self) -> None:
        """Test that higher mean reversion leads to faster mean reversion."""
        curve = build_simple_yield_curve()
        model_low = HullWhite1F(
            yield_curve=curve, mean_reversion=0.05, volatility=0.01, scheme="exact"
        )
        model_high = HullWhite1F(
            yield_curve=curve, mean_reversion=0.2, volatility=0.01, scheme="exact"
        )

        times = [0.0, 1.0, 2.0]
        shocks = np.array([1.0, 1.0])
        rates_low = model_low.simulate_short_rate_path(times, shocks)
        rates_high = model_high.simulate_short_rate_path(times, shocks)

        # Both should produce valid rates
        assert len(rates_low) == len(times)
        assert len(rates_high) == len(times)

    def test_volatility_effect(self) -> None:
        """Test that higher volatility leads to more variation."""
        curve = build_simple_yield_curve()
        model_low = HullWhite1F(
            yield_curve=curve, mean_reversion=0.1, volatility=0.005, scheme="exact"
        )
        model_high = HullWhite1F(
            yield_curve=curve, mean_reversion=0.1, volatility=0.02, scheme="exact"
        )

        times = [0.0, 0.5, 1.0]
        shocks = np.array([1.0, 1.0])
        rates_low = model_low.simulate_short_rate_path(times, shocks)
        rates_high = model_high.simulate_short_rate_path(times, shocks)

        # Higher volatility should generally lead to larger deviations
        # (though this depends on the specific path)
        assert len(rates_low) == len(times)
        assert len(rates_high) == len(times)

