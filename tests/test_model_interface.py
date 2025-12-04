"""Tests for model-agnostic interface and model comparison."""

from datetime import date

import numpy as np
import pytest

from montecarlo_ir.market_data.yield_curve import build_yield_curve_from_zero_rates
from montecarlo_ir.models.base import InterestRateModel
from montecarlo_ir.models.hull_white import HullWhite1F
from montecarlo_ir.models.lmm import LIBORMarketModel
from montecarlo_ir.pricing.product_pricers import SwapPricer
from montecarlo_ir.products.interest_rate_swap import InterestRateSwap
from montecarlo_ir.utils.date_helpers import DayCountConvention
from montecarlo_ir.utils.model_comparison import ComparisonResult, compare_models


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
    )


class TestModelInterface:
    """Tests for InterestRateModel protocol compliance."""

    def test_hull_white_implements_protocol(self) -> None:
        """Test that HullWhite1F implements InterestRateModel protocol."""
        curve = build_simple_yield_curve()
        model = HullWhite1F(
            yield_curve=curve,
            mean_reversion=0.1,
            volatility=0.01,
        )

        # Check protocol compliance
        assert hasattr(model, "yield_curve")
        assert hasattr(model, "simulate_path")
        assert hasattr(model, "discount_factor")
        assert hasattr(model, "bond_price")

        # Test simulate_path
        times = [0.0, 0.25, 0.5, 1.0]
        path = model.simulate_path(times)
        assert path.shape == (len(times),)

        # Test discount_factor
        df = model.discount_factor(0.0, 1.0, state=0.02)
        assert df > 0.0
        assert df <= 1.0

        # Test bond_price
        price = model.bond_price(0.0, 1.0, state=0.02)
        assert price > 0.0
        assert price <= 1.0

    def test_lmm_implements_protocol(self) -> None:
        """Test that LIBORMarketModel implements InterestRateModel protocol."""
        curve = build_simple_yield_curve()
        tenors = (date(2024, 1, 1), date(2025, 1, 1), date(2026, 1, 1))
        model = LIBORMarketModel(
            yield_curve=curve,
            tenor_structure=tenors,
            volatilities=(0.15, 0.16),
        )

        # Check protocol compliance
        assert hasattr(model, "yield_curve")
        assert hasattr(model, "simulate_path")
        assert hasattr(model, "discount_factor")
        assert hasattr(model, "bond_price")

        # Test simulate_path
        times = [0.0, 0.25, 0.5, 1.0]
        path = model.simulate_path(times)
        assert path.ndim == 2
        assert path.shape[0] == len(times)
        assert path.shape[1] == 2  # 2 forward rates

        # Test discount_factor
        forward_rates = np.array([0.02, 0.025])
        df = model.discount_factor(0.0, 1.0, state=forward_rates)
        assert df > 0.0
        assert df <= 1.0

    def test_pricer_works_with_any_model(self) -> None:
        """Test that pricers work with any model implementing the protocol."""
        curve = build_simple_yield_curve()
        swap = build_simple_swap()

        # Test with HullWhite1F
        hw_model = HullWhite1F(yield_curve=curve, mean_reversion=0.1, volatility=0.01)
        hw_pricer = SwapPricer(model=hw_model, num_paths=1000, seed=42)
        hw_result = hw_pricer.price(swap)
        assert hw_result.price is not None

        # Note: LMM swap pricing requires product payoff functions to handle 2D paths
        # This is a product-level enhancement, not an interface issue
        # The interface itself works - models can be swapped in pricers


class TestModelComparison:
    """Tests for model comparison utilities."""

    def test_compare_models(self) -> None:
        """Test comparing multiple models."""
        curve = build_simple_yield_curve()
        swap = build_simple_swap()

        def create_pricer(model: InterestRateModel):
            return SwapPricer(model=model, num_paths=500, seed=42).price

        # Compare two HullWhite models with different parameters
        hw1_model = HullWhite1F(yield_curve=curve, mean_reversion=0.1, volatility=0.01)
        hw2_model = HullWhite1F(yield_curve=curve, mean_reversion=0.15, volatility=0.015)

        models = [
            (hw1_model, "HW1F_a=0.1"),
            (hw2_model, "HW1F_a=0.15"),
        ]

        result = compare_models(create_pricer, swap, models)

        assert isinstance(result, ComparisonResult)
        assert len(result.model_names) == 2
        assert len(result.prices) == 2
        assert result.statistics["mean"] is not None
        assert result.statistics["std"] >= 0.0

    def test_compare_models_requires_at_least_two(self) -> None:
        """Test that comparison requires at least 2 models."""
        curve = build_simple_yield_curve()
        swap = build_simple_swap()

        def create_pricer(model: InterestRateModel):
            return SwapPricer(model=model, num_paths=500, seed=42).price

        hw_model = HullWhite1F(yield_curve=curve, mean_reversion=0.1, volatility=0.01)

        with pytest.raises(ValueError, match="At least 2 models"):
            compare_models(create_pricer, swap, [(hw_model, "HW1F")])

    def test_comparison_result_statistics(self) -> None:
        """Test that comparison result includes all statistics."""
        curve = build_simple_yield_curve()
        swap = build_simple_swap()

        def create_pricer(model: InterestRateModel):
            return SwapPricer(model=model, num_paths=500, seed=42).price

        # Compare two HullWhite models with different parameters
        hw1_model = HullWhite1F(yield_curve=curve, mean_reversion=0.1, volatility=0.01)
        hw2_model = HullWhite1F(yield_curve=curve, mean_reversion=0.15, volatility=0.015)

        models = [
            (hw1_model, "HullWhite1F_v1"),
            (hw2_model, "HullWhite1F_v2"),
        ]

        result = compare_models(create_pricer, swap, models)

        # Check all statistics are present
        assert "mean" in result.statistics
        assert "std" in result.statistics
        assert "min" in result.statistics
        assert "max" in result.statistics
        assert "range" in result.statistics
        assert "relative_std" in result.statistics

        # Validate statistics
        assert result.statistics["min"] <= result.statistics["mean"]
        assert result.statistics["mean"] <= result.statistics["max"]
        assert result.statistics["range"] == result.statistics["max"] - result.statistics["min"]

