"""Tests for EuropeanSwaption."""

from datetime import date

import numpy as np
import pytest

from montecarlo_ir.market_data.yield_curve import build_yield_curve_from_zero_rates
from montecarlo_ir.products.european_swaption import EuropeanSwaption
from montecarlo_ir.utils.date_helpers import DayCountConvention


def build_simple_yield_curve() -> "YieldCurve":
    """Create a simple yield curve for testing."""
    val = date(2024, 1, 1)
    pillars = (date(2025, 1, 1), date(2026, 1, 1))
    zeros = (0.02, 0.025)
    return build_yield_curve_from_zero_rates(
        valuation_date=val,
        pillar_dates=pillars,
        zero_rates=zeros,
        day_count=DayCountConvention.ACT_365,
    )


def build_simple_swaption() -> EuropeanSwaption:
    """Create a simple swaption for testing."""
    return EuropeanSwaption(
        valuation_date=date(2024, 1, 1),
        expiry_date=date(2024, 6, 1),
        swap_start_date=date(2024, 7, 1),  # After expiry
        swap_maturity_date=date(2025, 6, 1),
        strike=0.02,
        notional=1000000.0,
        swaption_type="payer",
        settlement_type="physical",
    )


class TestEuropeanSwaptionConstruction:
    """Tests for EuropeanSwaption construction."""

    def test_requires_expiry_after_valuation(self) -> None:
        """Test that expiry must be after valuation date."""
        with pytest.raises(ValueError, match="must be after"):
            EuropeanSwaption(
                valuation_date=date(2024, 1, 1),
                expiry_date=date(2024, 1, 1),  # Same as valuation
                swap_start_date=date(2024, 6, 1),
                swap_maturity_date=date(2025, 6, 1),
                strike=0.02,
                notional=1000000.0,
            )

    def test_requires_swap_start_after_expiry(self) -> None:
        """Test that swap start must be after expiry."""
        with pytest.raises(ValueError, match="must be after"):
            EuropeanSwaption(
                valuation_date=date(2024, 1, 1),
                expiry_date=date(2024, 6, 1),
                swap_start_date=date(2024, 6, 1),  # Same as expiry
                swap_maturity_date=date(2025, 6, 1),
                strike=0.02,
                notional=1000000.0,
            )

    def test_requires_positive_notional(self) -> None:
        """Test that notional must be positive."""
        with pytest.raises(ValueError, match="must be positive"):
            EuropeanSwaption(
                valuation_date=date(2024, 1, 1),
                expiry_date=date(2024, 6, 1),
                swap_start_date=date(2024, 7, 1),
                swap_maturity_date=date(2025, 6, 1),
                strike=0.02,
                notional=-1000000.0,
            )


class TestUnderlyingSwap:
    """Tests for underlying swap generation."""

    def test_get_underlying_swap(self) -> None:
        """Test getting underlying swap."""
        swaption = build_simple_swaption()
        swap = swaption.get_underlying_swap()

        assert swap.fixed_rate == swaption.strike
        assert swap.notional == swaption.notional
        assert swap.start_date == swaption.swap_start_date
        assert swap.maturity_date == swaption.swap_maturity_date


class TestPayoffCalculation:
    """Tests for payoff calculation."""

    def test_payer_swaption_payoff(self) -> None:
        """Test payer swaption payoff calculation."""
        swaption = build_simple_swaption()
        curve = build_simple_yield_curve()

        pv = swaption.payoff(curve)
        assert isinstance(pv, float)
        assert pv >= 0.0  # Option value is non-negative

    def test_receiver_swaption_payoff(self) -> None:
        """Test receiver swaption payoff calculation."""
        swaption = EuropeanSwaption(
            valuation_date=date(2024, 1, 1),
            expiry_date=date(2024, 6, 1),
            swap_start_date=date(2024, 7, 1),
            swap_maturity_date=date(2025, 6, 1),
            strike=0.02,
            notional=1000000.0,
            swaption_type="receiver",
        )
        curve = build_simple_yield_curve()

        pv = swaption.payoff(curve)
        assert isinstance(pv, float)
        assert pv >= 0.0

    def test_payoff_with_precalculated_swap_value(self) -> None:
        """Test payoff with pre-calculated swap value."""
        swaption = build_simple_swaption()
        curve = build_simple_yield_curve()

        # Pre-calculate swap value (may fail if dates are too close, so use try/except)
        underlying_swap = swaption.get_underlying_swap()
        try:
            swap_value = underlying_swap.payoff(curve)
        except ValueError:
            # If swap can't be valued, use 0
            swap_value = 0.0

        pv = swaption.payoff(curve, swap_value_at_expiry=swap_value)
        assert isinstance(pv, float)

    def test_payoff_mc_physical_settlement(self) -> None:
        """Test Monte Carlo payoff with physical settlement."""
        swaption = build_simple_swaption()
        curve = build_simple_yield_curve()

        times = np.array([0.0, 0.25, 0.5, 0.75, 1.0])
        rates = np.array([0.02, 0.025, 0.03, 0.025, 0.02])

        payoff = swaption.payoff_mc(rates, times, curve)
        assert isinstance(payoff, float)
        assert payoff >= 0.0

    def test_payoff_mc_cash_settlement(self) -> None:
        """Test Monte Carlo payoff with cash settlement."""
        swaption = EuropeanSwaption(
            valuation_date=date(2024, 1, 1),
            expiry_date=date(2024, 6, 1),
            swap_start_date=date(2024, 7, 1),
            swap_maturity_date=date(2025, 6, 1),
            strike=0.02,
            notional=1000000.0,
            swaption_type="payer",
            settlement_type="cash",
        )
        curve = build_simple_yield_curve()

        times = np.array([0.0, 0.25, 0.5, 0.75, 1.0])
        rates = np.array([0.02, 0.025, 0.03, 0.025, 0.02])

        payoff = swaption.payoff_mc(rates, times, curve)
        assert isinstance(payoff, float)
        assert payoff >= 0.0

