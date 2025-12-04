"""Tests for product pricers."""

from datetime import date

import pytest

from montecarlo_ir.market_data.yield_curve import build_yield_curve_from_zero_rates
from montecarlo_ir.models.hull_white import HullWhite1F
from montecarlo_ir.pricing.mc_engine import MonteCarloResult
from montecarlo_ir.pricing.product_pricers import (
    CapFloorPricer,
    EuropeanSwaptionPricer,
    SwapPricer,
)
from montecarlo_ir.products.cap_floor import CapFloor
from montecarlo_ir.products.european_swaption import EuropeanSwaption
from montecarlo_ir.products.interest_rate_swap import InterestRateSwap
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


def build_simple_model() -> HullWhite1F:
    """Create a simple Hull-White model for testing."""
    curve = build_simple_yield_curve()
    return HullWhite1F(
        yield_curve=curve,
        mean_reversion=0.1,
        volatility=0.01,
        scheme="exact",
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
    )


def build_simple_swaption() -> EuropeanSwaption:
    """Create a simple swaption for testing."""
    return EuropeanSwaption(
        valuation_date=date(2024, 1, 1),
        expiry_date=date(2024, 6, 1),
        swap_start_date=date(2024, 7, 1),
        swap_maturity_date=date(2025, 6, 1),
        strike=0.02,
        notional=1000000.0,
        swaption_type="payer",
    )


class TestSwapPricer:
    """Tests for SwapPricer."""

    def test_price_swap(self) -> None:
        """Test pricing a swap."""
        model = build_simple_model()
        pricer = SwapPricer(model=model, num_paths=1000, seed=42)
        swap = build_simple_swap()

        result = pricer.price(swap)

        assert isinstance(result, MonteCarloResult)
        assert result.num_paths == 1000
        assert result.standard_error >= 0.0

    def test_price_swap_with_antithetic(self) -> None:
        """Test pricing a swap with antithetic variates."""
        model = build_simple_model()
        pricer = SwapPricer(
            model=model, num_paths=1000, seed=42, use_antithetic=True
        )
        swap = build_simple_swap()

        result = pricer.price(swap)

        assert result.num_paths == 1000
        assert result.standard_error >= 0.0


class TestCapFloorPricer:
    """Tests for CapFloorPricer."""

    def test_price_cap(self) -> None:
        """Test pricing a cap."""
        model = build_simple_model()
        pricer = CapFloorPricer(model=model, num_paths=1000, seed=42)
        cap = build_simple_cap()

        result = pricer.price(cap)

        assert isinstance(result, MonteCarloResult)
        assert result.num_paths == 1000
        assert result.standard_error >= 0.0
        assert result.price >= 0.0  # Cap value is non-negative

    def test_price_floor(self) -> None:
        """Test pricing a floor."""
        model = build_simple_model()
        pricer = CapFloorPricer(model=model, num_paths=1000, seed=42)
        floor = CapFloor(
            valuation_date=date(2024, 1, 1),
            start_date=date(2024, 1, 1),
            maturity_date=date(2025, 1, 1),
            strike=0.02,
            notional=1000000.0,
            cap_floor_type="floor",
        )

        result = pricer.price(floor)

        assert result.num_paths == 1000
        assert result.price >= 0.0  # Floor value is non-negative


class TestEuropeanSwaptionPricer:
    """Tests for EuropeanSwaptionPricer."""

    def test_price_swaption(self) -> None:
        """Test pricing a swaption."""
        model = build_simple_model()
        pricer = EuropeanSwaptionPricer(model=model, num_paths=1000, seed=42)
        swaption = build_simple_swaption()

        result = pricer.price(swaption)

        assert isinstance(result, MonteCarloResult)
        assert result.num_paths == 1000
        assert result.standard_error >= 0.0
        assert result.price >= 0.0  # Option value is non-negative

    def test_price_receiver_swaption(self) -> None:
        """Test pricing a receiver swaption."""
        model = build_simple_model()
        pricer = EuropeanSwaptionPricer(model=model, num_paths=1000, seed=42)
        swaption = EuropeanSwaption(
            valuation_date=date(2024, 1, 1),
            expiry_date=date(2024, 6, 1),
            swap_start_date=date(2024, 7, 1),
            swap_maturity_date=date(2025, 6, 1),
            strike=0.02,
            notional=1000000.0,
            swaption_type="receiver",
        )

        result = pricer.price(swaption)

        assert result.num_paths == 1000
        assert result.price >= 0.0

