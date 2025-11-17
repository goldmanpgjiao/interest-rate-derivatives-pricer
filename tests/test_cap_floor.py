"""Tests for CapFloor."""

from datetime import date

import numpy as np
import pytest

from montecarlo_ir.market_data.yield_curve import build_yield_curve_from_zero_rates
from montecarlo_ir.products.cap_floor import CapFloor, CapletFloorlet
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


def build_simple_cap() -> CapFloor:
    """Create a simple cap for testing."""
    return CapFloor(
        valuation_date=date(2024, 1, 1),
        start_date=date(2024, 1, 1),
        maturity_date=date(2025, 1, 1),
        strike=0.02,
        notional=1000000.0,
        cap_floor_type="cap",
        frequency="3M",
    )


class TestCapFloorConstruction:
    """Tests for CapFloor construction."""

    def test_requires_maturity_after_start(self) -> None:
        """Test that maturity must be after start date."""
        with pytest.raises(ValueError, match="must be after"):
            CapFloor(
                valuation_date=date(2024, 1, 1),
                start_date=date(2024, 1, 1),
                maturity_date=date(2024, 1, 1),
                strike=0.02,
                notional=1000000.0,
            )

    def test_requires_positive_notional(self) -> None:
        """Test that notional must be positive."""
        with pytest.raises(ValueError, match="must be positive"):
            CapFloor(
                valuation_date=date(2024, 1, 1),
                start_date=date(2024, 1, 1),
                maturity_date=date(2025, 1, 1),
                strike=0.02,
                notional=-1000000.0,
            )

    def test_requires_non_negative_strike(self) -> None:
        """Test that strike must be non-negative."""
        with pytest.raises(ValueError, match="must be non-negative"):
            CapFloor(
                valuation_date=date(2024, 1, 1),
                start_date=date(2024, 1, 1),
                maturity_date=date(2025, 1, 1),
                strike=-0.01,
                notional=1000000.0,
            )


class TestCapletGeneration:
    """Tests for caplet/floorlet generation."""

    def test_get_caplets(self) -> None:
        """Test caplet generation."""
        cap = build_simple_cap()
        caplets = cap.get_caplets_floorlets()

        assert len(caplets) > 0
        for caplet in caplets:
            assert caplet.payment_date > cap.valuation_date
            assert caplet.strike == cap.strike
            assert caplet.notional == cap.notional
            assert caplet.option_type == "cap"

    def test_get_floorlets(self) -> None:
        """Test floorlet generation."""
        floor = CapFloor(
            valuation_date=date(2024, 1, 1),
            start_date=date(2024, 1, 1),
            maturity_date=date(2025, 1, 1),
            strike=0.02,
            notional=1000000.0,
            cap_floor_type="floor",
            frequency="3M",
        )

        floorlets = floor.get_caplets_floorlets()
        assert len(floorlets) > 0
        for floorlet in floorlets:
            assert floorlet.option_type == "floor"


class TestPayoffCalculation:
    """Tests for payoff calculation."""

    def test_cap_payoff_with_yield_curve(self) -> None:
        """Test cap payoff calculation using yield curve."""
        cap = build_simple_cap()
        curve = build_simple_yield_curve()

        pv = cap.payoff(curve)
        assert isinstance(pv, float)
        assert pv >= 0.0  # Cap value is non-negative

    def test_floor_payoff_with_yield_curve(self) -> None:
        """Test floor payoff calculation using yield curve."""
        floor = CapFloor(
            valuation_date=date(2024, 1, 1),
            start_date=date(2024, 1, 1),
            maturity_date=date(2025, 1, 1),
            strike=0.02,
            notional=1000000.0,
            cap_floor_type="floor",
        )
        curve = build_simple_yield_curve()

        pv = floor.payoff(curve)
        assert isinstance(pv, float)
        assert pv >= 0.0  # Floor value is non-negative

    def test_cap_payoff_with_custom_rates(self) -> None:
        """Test cap payoff with custom floating rates."""
        cap = build_simple_cap()
        curve = build_simple_yield_curve()

        caplets = cap.get_caplets_floorlets()
        floating_rates = {}
        for caplet in caplets:
            floating_rates[caplet.reset_date] = 0.025  # 2.5% rate

        pv = cap.payoff(curve, floating_rates=floating_rates)
        assert isinstance(pv, float)

    def test_cap_payoff_mc(self) -> None:
        """Test Monte Carlo payoff calculation."""
        cap = build_simple_cap()
        curve = build_simple_yield_curve()

        times = np.array([0.0, 0.25, 0.5, 0.75, 1.0])
        rates = np.array([0.02, 0.025, 0.03, 0.025, 0.02])

        payoff = cap.payoff_mc(rates, times, curve)
        assert isinstance(payoff, float)
        assert payoff >= 0.0

    def test_floor_payoff_mc(self) -> None:
        """Test floor Monte Carlo payoff calculation."""
        floor = CapFloor(
            valuation_date=date(2024, 1, 1),
            start_date=date(2024, 1, 1),
            maturity_date=date(2025, 1, 1),
            strike=0.02,
            notional=1000000.0,
            cap_floor_type="floor",
        )
        curve = build_simple_yield_curve()

        times = np.array([0.0, 0.25, 0.5, 0.75, 1.0])
        rates = np.array([0.02, 0.015, 0.01, 0.015, 0.02])  # Rates below strike

        payoff = floor.payoff_mc(rates, times, curve)
        assert isinstance(payoff, float)
        assert payoff >= 0.0


class TestCapletFloorlet:
    """Tests for CapletFloorlet dataclass."""

    def test_caplet_creation(self) -> None:
        """Test creating a caplet."""
        caplet = CapletFloorlet(
            reset_date=date(2024, 1, 1),
            payment_date=date(2024, 4, 1),
            strike=0.02,
            notional=1000000.0,
            day_count=DayCountConvention.ACT_360,
            option_type="cap",
        )

        assert caplet.strike == 0.02
        assert caplet.option_type == "cap"

