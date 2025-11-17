"""Tests for InterestRateSwap."""

from datetime import date

import numpy as np
import pytest

from montecarlo_ir.market_data.yield_curve import build_yield_curve_from_zero_rates
from montecarlo_ir.products.interest_rate_swap import Cashflow, InterestRateSwap
from montecarlo_ir.utils.date_helpers import BusinessDayRule, DayCountConvention


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


def build_simple_swap() -> InterestRateSwap:
    """Create a simple swap for testing."""
    return InterestRateSwap(
        valuation_date=date(2024, 1, 1),
        start_date=date(2024, 1, 1),
        maturity_date=date(2025, 1, 1),
        fixed_rate=0.02,
        notional=1000000.0,
        swap_type="payer",
        fixed_frequency="6M",
        floating_frequency="6M",
    )


class TestInterestRateSwapConstruction:
    """Tests for InterestRateSwap construction."""

    def test_requires_maturity_after_start(self) -> None:
        """Test that maturity must be after start date."""
        with pytest.raises(ValueError, match="must be after"):
            InterestRateSwap(
                valuation_date=date(2024, 1, 1),
                start_date=date(2024, 1, 1),
                maturity_date=date(2024, 1, 1),  # Same as start
                fixed_rate=0.02,
                notional=1000000.0,
            )

    def test_requires_start_on_or_after_valuation(self) -> None:
        """Test that start date must be on or after valuation date."""
        with pytest.raises(ValueError, match="must be on or after"):
            InterestRateSwap(
                valuation_date=date(2024, 1, 1),
                start_date=date(2023, 12, 1),  # Before valuation
                maturity_date=date(2025, 1, 1),
                fixed_rate=0.02,
                notional=1000000.0,
            )

    def test_requires_positive_notional(self) -> None:
        """Test that notional must be positive."""
        with pytest.raises(ValueError, match="must be positive"):
            InterestRateSwap(
                valuation_date=date(2024, 1, 1),
                start_date=date(2024, 1, 1),
                maturity_date=date(2025, 1, 1),
                fixed_rate=0.02,
                notional=-1000000.0,
            )

    def test_requires_non_negative_fixed_rate(self) -> None:
        """Test that fixed rate must be non-negative."""
        with pytest.raises(ValueError, match="must be non-negative"):
            InterestRateSwap(
                valuation_date=date(2024, 1, 1),
                start_date=date(2024, 1, 1),
                maturity_date=date(2025, 1, 1),
                fixed_rate=-0.01,
                notional=1000000.0,
            )


class TestCashflowGeneration:
    """Tests for cashflow generation."""

    def test_fixed_leg_cashflows(self) -> None:
        """Test fixed leg cashflow generation."""
        swap = build_simple_swap()
        cashflows = swap.get_fixed_leg_cashflows()

        assert len(cashflows) > 0
        for cf in cashflows:
            assert cf.payment_date > swap.valuation_date
            assert cf.rate == swap.fixed_rate
            assert cf.notional == swap.notional

    def test_floating_leg_cashflows(self) -> None:
        """Test floating leg cashflow generation."""
        swap = build_simple_swap()
        cashflows = swap.get_floating_leg_cashflows()

        assert len(cashflows) > 0
        for cf in cashflows:
            assert cf.payment_date > swap.valuation_date
            assert cf.reset_date is not None
            assert cf.notional == swap.notional

    def test_cashflows_exclude_past_dates(self) -> None:
        """Test that cashflows exclude dates before valuation."""
        swap = InterestRateSwap(
            valuation_date=date(2024, 1, 1),
            start_date=date(2024, 1, 1),
            maturity_date=date(2025, 1, 1),
            fixed_rate=0.02,
            notional=1000000.0,
        )

        # Test that cashflows only include future dates
        cashflows = swap.get_fixed_leg_cashflows()
        for cf in cashflows:
            assert cf.payment_date >= swap.valuation_date


class TestPayoffCalculation:
    """Tests for payoff calculation."""

    def test_payoff_with_yield_curve(self) -> None:
        """Test payoff calculation using yield curve."""
        swap = build_simple_swap()
        curve = build_simple_yield_curve()

        pv = swap.payoff(curve)
        assert isinstance(pv, float)

    def test_payoff_payer_vs_receiver(self) -> None:
        """Test that payer and receiver swaps have opposite signs."""
        curve = build_simple_yield_curve()

        payer_swap = InterestRateSwap(
            valuation_date=date(2024, 1, 1),
            start_date=date(2024, 1, 1),
            maturity_date=date(2025, 1, 1),
            fixed_rate=0.02,
            notional=1000000.0,
            swap_type="payer",
        )

        receiver_swap = InterestRateSwap(
            valuation_date=date(2024, 1, 1),
            start_date=date(2024, 1, 1),
            maturity_date=date(2025, 1, 1),
            fixed_rate=0.02,
            notional=1000000.0,
            swap_type="receiver",
        )

        payer_pv = payer_swap.payoff(curve)
        receiver_pv = receiver_swap.payoff(curve)

        # Should be opposite signs (approximately)
        assert abs(payer_pv + receiver_pv) < 1.0  # Allow small numerical differences

    def test_payoff_with_custom_floating_rates(self) -> None:
        """Test payoff with custom floating rates."""
        swap = build_simple_swap()
        curve = build_simple_yield_curve()

        floating_cashflows = swap.get_floating_leg_cashflows()
        floating_rates = {}
        for cf in floating_cashflows:
            if cf.reset_date:
                floating_rates[cf.reset_date] = 0.025  # 2.5% floating rate

        pv = swap.payoff(curve, floating_rates=floating_rates)
        assert isinstance(pv, float)

    def test_payoff_mc(self) -> None:
        """Test Monte Carlo payoff calculation."""
        swap = build_simple_swap()
        curve = build_simple_yield_curve()

        # Simulate rates
        times = np.array([0.0, 0.5, 1.0])
        rates = np.array([0.02, 0.025, 0.03])

        payoff = swap.payoff_mc(rates, times, curve)
        assert isinstance(payoff, float)


class TestCashflow:
    """Tests for Cashflow dataclass."""

    def test_cashflow_creation(self) -> None:
        """Test creating a cashflow."""
        cf = Cashflow(
            payment_date=date(2024, 7, 1),
            reset_date=date(2024, 1, 1),
            notional=1000000.0,
            rate=0.02,
            day_count=DayCountConvention.ACT_365,
        )

        assert cf.payment_date == date(2024, 7, 1)
        assert cf.rate == 0.02
        assert cf.notional == 1000000.0

