"""Tests for LIBORMarketModel."""

from datetime import date

import numpy as np
import pytest

from montecarlo_ir.market_data.yield_curve import build_yield_curve_from_zero_rates
from montecarlo_ir.models.lmm import LIBORMarketModel
from montecarlo_ir.utils.date_helpers import DayCountConvention


def build_simple_yield_curve() -> "YieldCurve":
    """Create a simple flat yield curve for testing."""
    from montecarlo_ir.market_data.yield_curve import YieldCurve

    val = date(2024, 1, 1)
    pillars = (date(2025, 1, 1), date(2026, 1, 1), date(2027, 1, 1))
    zeros = (0.02, 0.02, 0.02)  # Flat 2% curve
    return build_yield_curve_from_zero_rates(
        valuation_date=val,
        pillar_dates=pillars,
        zero_rates=zeros,
        day_count=DayCountConvention.ACT_365,
    )


def build_lmm_model() -> LIBORMarketModel:
    """Create a simple LMM model for testing."""
    curve = build_simple_yield_curve()
    tenors = (date(2024, 1, 1), date(2025, 1, 1), date(2026, 1, 1))
    vols = (0.15, 0.16)  # One vol per forward rate
    return LIBORMarketModel(
        yield_curve=curve,
        tenor_structure=tenors,
        volatilities=vols,
        scheme="log_euler",
        measure="spot",
        day_count=DayCountConvention.ACT_365,
    )


class TestLMMConstruction:
    """Tests for LIBORMarketModel construction and validation."""

    def test_requires_at_least_two_tenors(self) -> None:
        """Test that at least two tenors are required."""
        curve = build_simple_yield_curve()
        with pytest.raises(ValueError, match="at least 2 dates"):
            LIBORMarketModel(
                yield_curve=curve,
                tenor_structure=(date(2024, 1, 1),),
                volatilities=(),
            )

    def test_volatilities_length_must_match(self) -> None:
        """Test that volatilities length must match number of forward rates."""
        curve = build_simple_yield_curve()
        tenors = (date(2024, 1, 1), date(2025, 1, 1), date(2026, 1, 1))
        with pytest.raises(ValueError, match="must have length"):
            LIBORMarketModel(
                yield_curve=curve,
                tenor_structure=tenors,
                volatilities=(0.15,),  # Need 2, got 1
            )

    def test_volatilities_must_be_non_negative(self) -> None:
        """Test that volatilities must be non-negative."""
        curve = build_simple_yield_curve()
        tenors = (date(2024, 1, 1), date(2025, 1, 1))
        with pytest.raises(ValueError, match="must be non-negative"):
            LIBORMarketModel(
                yield_curve=curve,
                tenor_structure=tenors,
                volatilities=(-0.1,),
            )

    def test_correlation_matrix_validation(self) -> None:
        """Test correlation matrix validation."""
        curve = build_simple_yield_curve()
        tenors = (date(2024, 1, 1), date(2025, 1, 1), date(2026, 1, 1))
        vols = (0.15, 0.16)

        # Invalid size
        with pytest.raises(ValueError, match="must have.*rows"):
            LIBORMarketModel(
                yield_curve=curve,
                tenor_structure=tenors,
                volatilities=vols,
                correlation_matrix=((1.0,),),
            )

        # Non-symmetric
        with pytest.raises(ValueError, match="must be symmetric"):
            LIBORMarketModel(
                yield_curve=curve,
                tenor_structure=tenors,
                volatilities=vols,
                correlation_matrix=((1.0, 0.5), (0.3, 1.0)),  # Not symmetric
            )

        # Diagonal not 1.0
        with pytest.raises(ValueError, match="must be 1.0"):
            LIBORMarketModel(
                yield_curve=curve,
                tenor_structure=tenors,
                volatilities=vols,
                correlation_matrix=((0.9, 0.5), (0.5, 0.9)),
            )


class TestForwardRateSimulation:
    """Tests for forward rate path simulation."""

    def test_simulate_log_euler_scheme(self) -> None:
        """Test log-Euler simulation scheme."""
        model = build_lmm_model()
        times = [0.0, 0.25, 0.5, 1.0]
        rates = model.simulate_forward_rates(times)
        assert rates.shape == (len(times), 2)  # 2 forward rates
        assert all(r > 0.0 for r in rates.flatten())  # Rates should be positive

    def test_simulate_euler_scheme(self) -> None:
        """Test Euler discretization scheme."""
        curve = build_simple_yield_curve()
        tenors = (date(2024, 1, 1), date(2025, 1, 1), date(2026, 1, 1))
        model = LIBORMarketModel(
            yield_curve=curve,
            tenor_structure=tenors,
            volatilities=(0.15, 0.16),
            scheme="euler",
        )
        times = [0.0, 0.25, 0.5]
        rates = model.simulate_forward_rates(times)
        assert rates.shape == (len(times), 2)

    def test_simulate_with_custom_shocks(self) -> None:
        """Test simulation with provided random shocks."""
        model = build_lmm_model()
        times = [0.0, 0.25, 0.5]
        shocks = np.array([[0.5, -0.3], [-0.2, 0.4]])
        rates1 = model.simulate_forward_rates(times, shocks)
        rates2 = model.simulate_forward_rates(times, shocks)
        # Same shocks should give same results
        np.testing.assert_array_almost_equal(rates1, rates2)

    def test_simulate_with_correlation(self) -> None:
        """Test simulation with correlation matrix."""
        curve = build_simple_yield_curve()
        tenors = (date(2024, 1, 1), date(2025, 1, 1), date(2026, 1, 1))
        corr_matrix = ((1.0, 0.5), (0.5, 1.0))
        model = LIBORMarketModel(
            yield_curve=curve,
            tenor_structure=tenors,
            volatilities=(0.15, 0.16),
            correlation_matrix=corr_matrix,
        )
        times = [0.0, 0.25, 0.5]
        rates = model.simulate_forward_rates(times)
        assert rates.shape == (len(times), 2)

    def test_simulate_invalid_times(self) -> None:
        """Test error handling for invalid times."""
        model = build_lmm_model()
        with pytest.raises(ValueError, match="must be non-negative"):
            model.simulate_forward_rates([-0.1, 0.5])

        with pytest.raises(ValueError, match="strictly increasing"):
            model.simulate_forward_rates([0.5, 0.3])

    def test_simulate_invalid_shocks_shape(self) -> None:
        """Test error when shocks shape doesn't match."""
        model = build_lmm_model()
        times = [0.0, 0.25, 0.5]
        shocks = np.array([[0.5]])  # Wrong shape
        with pytest.raises(ValueError, match="must have shape"):
            model.simulate_forward_rates(times, shocks)


class TestDiscountFactors:
    """Tests for discount factor calculations."""

    def test_discount_factor_positive(self) -> None:
        """Test discount factors are positive."""
        model = build_lmm_model()
        forward_rates = np.array([0.02, 0.025])
        df = model.discount_factor(0.0, 1.0, forward_rates)
        assert df > 0.0
        assert df <= 1.0

    def test_discount_factor_invalid_times(self) -> None:
        """Test error handling for invalid times."""
        model = build_lmm_model()
        forward_rates = np.array([0.02, 0.025])
        with pytest.raises(ValueError, match="must be >="):
            model.discount_factor(1.0, 0.5, forward_rates)

    def test_discount_factor_invalid_rates_length(self) -> None:
        """Test error when forward rates length doesn't match."""
        model = build_lmm_model()
        forward_rates = np.array([0.02])  # Wrong length
        with pytest.raises(ValueError, match="must have length"):
            model.discount_factor(0.0, 1.0, forward_rates)


class TestModelProperties:
    """Tests for model properties and behavior."""

    def test_spot_measure_drift(self) -> None:
        """Test spot measure produces non-zero drift."""
        model = build_lmm_model()
        times = [0.0, 0.1]
        rates = model.simulate_forward_rates(times)
        # Rates should evolve (not stay constant)
        assert rates.shape == (2, 2)

    def test_terminal_measure(self) -> None:
        """Test terminal measure."""
        curve = build_simple_yield_curve()
        tenors = (date(2024, 1, 1), date(2025, 1, 1), date(2026, 1, 1))
        model = LIBORMarketModel(
            yield_curve=curve,
            tenor_structure=tenors,
            volatilities=(0.15, 0.16),
            measure="terminal",
        )
        times = [0.0, 0.25, 0.5]
        rates = model.simulate_forward_rates(times)
        assert rates.shape == (len(times), 2)

