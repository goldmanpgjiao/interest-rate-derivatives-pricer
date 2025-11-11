"""Tests for YieldCurve."""

from datetime import date
import math
import pytest

from montecarlo_ir.market_data.yield_curve import (
    YieldCurve,
    build_yield_curve_from_discount_factors,
    build_yield_curve_from_zero_rates,
    build_yield_curve_from_deposits_simple,
    build_yield_curve_from_swaps,
)
from montecarlo_ir.utils.date_helpers import DayCountConvention


def build_simple_curve() -> YieldCurve:
    val = date(2024, 1, 1)
    pillars = (date(2025, 1, 1), date(2026, 1, 1), date(2027, 1, 1))
    zeros = (0.02, 0.022, 0.025)  # flat-ish upward
    return YieldCurve(
        valuation_date=val,
        pillar_dates=pillars,
        pillar_zero_rates=zeros,
        day_count=DayCountConvention.ACT_365,
        interpolation="log_linear_df",
        compounding="cont",
    )


class TestYieldCurveConstruction:
    def test_requires_at_least_one_pillar(self) -> None:
        with pytest.raises(ValueError):
            YieldCurve(
                valuation_date=date(2024, 1, 1),
                pillar_dates=(),
                pillar_zero_rates=(),
            )

    def test_dates_and_rates_same_length(self) -> None:
        with pytest.raises(ValueError):
            YieldCurve(
                valuation_date=date(2024, 1, 1),
                pillar_dates=(date(2025, 1, 1),),
                pillar_zero_rates=(),
            )

    def test_dates_must_be_after_valuation(self) -> None:
        with pytest.raises(ValueError):
            YieldCurve(
                valuation_date=date(2024, 1, 2),
                pillar_dates=(date(2024, 1, 1),),
                pillar_zero_rates=(0.02,),
            )


class TestDiscountFactors:
    def test_df_at_valuation_is_one(self) -> None:
        curve = build_simple_curve()
        assert curve.discount_factor(curve.valuation_date) == 1.0

    def test_df_monotone_decreasing(self) -> None:
        curve = build_simple_curve()
        d1 = curve.discount_factor(date(2025, 1, 1))
        d2 = curve.discount_factor(date(2026, 1, 1))
        d3 = curve.discount_factor(date(2027, 1, 1))
        assert d1 > d2 > d3


class TestZeroRates:
    def test_zero_rate_at_first_pillar(self) -> None:
        curve = build_simple_curve()
        r = curve.zero_rate(date(2025, 1, 1))
        assert abs(r - 0.02) < 1e-12

    def test_zero_rate_bounds(self) -> None:
        curve = build_simple_curve()
        # before first pillar (but >= valuation): should use first pillar's rate
        r0 = curve.zero_rate(date(2024, 6, 30))
        assert abs(r0 - 0.02) < 1e-6
        # after last pillar: should use last pillar's rate
        r1 = curve.zero_rate(date(2028, 1, 1))
        assert abs(r1 - 0.025) < 1e-6


class TestForwardRates:
    def test_forward_positive(self) -> None:
        curve = build_simple_curve()
        fwd = curve.forward_rate(date(2025, 1, 1), date(2026, 1, 1))
        assert fwd > 0.0

    def test_forward_invalid_period(self) -> None:
        curve = build_simple_curve()
        with pytest.raises(ValueError):
            curve.forward_rate(date(2025, 1, 1), date(2025, 1, 1))
        with pytest.raises(ValueError):
            curve.forward_rate(date(2026, 1, 1), date(2025, 1, 1))


class TestInterpolationModes:
    def test_linear_zero_mode(self) -> None:
        val = date(2024, 1, 1)
        pillars = (date(2025, 1, 1), date(2026, 1, 1))
        zeros = (0.02, 0.03)
        curve = YieldCurve(
            valuation_date=val,
            pillar_dates=pillars,
            pillar_zero_rates=zeros,
            day_count=DayCountConvention.ACT_365,
            interpolation="linear_zero",
            compounding="cont",
        )
        r_mid = curve.zero_rate(date(2025, 7, 2))  # roughly half year after 2025-01-01
        assert 0.02 < r_mid < 0.03


class TestBootstrappingHelpers:
    def test_build_from_discount_factors(self) -> None:
        val = date(2024, 1, 1)
        pillars = (date(2025, 1, 1), date(2026, 1, 1))
        # Assume 2% cont rate 1Y -> DF = exp(-0.02*1) ~ 0.9801987
        # Assume 2.5% cont rate 2Y -> DF = exp(-0.025*2) ~ 0.951229
        dfs = (math.exp(-0.02 * 1.0), math.exp(-0.025 * 2.0))
        curve = build_yield_curve_from_discount_factors(
            valuation_date=val,
            pillar_dates=pillars,
            discount_factors=dfs,
            day_count=DayCountConvention.ACT_365,
            interpolation="log_linear_df",
            compounding="cont",
        )
        r1 = curve.zero_rate(pillars[0])
        r2 = curve.zero_rate(pillars[1])
        # Expected from DF and actual ACT/365 year fractions
        from montecarlo_ir.utils.date_helpers import year_fraction

        t1 = year_fraction(val, pillars[0], DayCountConvention.ACT_365)
        t2 = year_fraction(val, pillars[1], DayCountConvention.ACT_365)
        exp_r1 = -math.log(dfs[0]) / t1
        exp_r2 = -math.log(dfs[1]) / t2
        assert abs(r1 - exp_r1) < 1e-10
        assert abs(r2 - exp_r2) < 1e-10

    def test_build_from_zero_rates(self) -> None:
        val = date(2024, 1, 1)
        pillars = (date(2025, 1, 1), date(2026, 1, 1))
        zeros = (0.02, 0.025)
        curve = build_yield_curve_from_zero_rates(
            valuation_date=val,
            pillar_dates=pillars,
            zero_rates=zeros,
            day_count=DayCountConvention.ACT_365,
            interpolation="linear_zero",
            compounding="cont",
        )
        assert abs(curve.zero_rate(pillars[0]) - 0.02) < 1e-12
        assert abs(curve.zero_rate(pillars[1]) - 0.025) < 1e-12

    def test_build_from_deposits_simple(self) -> None:
        val = date(2024, 1, 1)
        maturities = (date(2025, 1, 1), date(2026, 1, 1))
        # Simple rates for 1Y and 2Y
        simple_rates = (0.02, 0.025)
        curve = build_yield_curve_from_deposits_simple(
            valuation_date=val,
            deposit_maturities=maturities,
            deposit_simple_rates=simple_rates,
            day_count=DayCountConvention.ACT_365,
            interpolation="log_linear_df",
            compounding="cont",
        )
        # The corresponding continuous zero at 1Y will be close to ln(1+0.02)/1 ~ 0.0198
        r1 = curve.zero_rate(maturities[0])
        assert 0.018 < r1 < 0.022

    def test_build_from_swaps_single(self) -> None:
        """Test bootstrapping from a single swap."""
        val = date(2024, 1, 1)
        swap_maturity = date(2025, 1, 1)  # 1 year swap
        par_rate = 0.02  # 2% par swap rate

        curve = build_yield_curve_from_swaps(
            valuation_date=val,
            swap_maturities=(swap_maturity,),
            par_swap_rates=(par_rate,),
            swap_frequency="6M",
            day_count=DayCountConvention.ACT_365,
            compounding="cont",
        )

        # For a 1Y swap with 6M frequency, we should have 2 payments
        # The bootstrapped zero rate should be close to the par rate
        r = curve.zero_rate(swap_maturity)
        assert 0.015 < r < 0.025  # Should be in reasonable range

    def test_build_from_swaps_multiple(self) -> None:
        """Test bootstrapping from multiple swaps."""
        val = date(2024, 1, 1)
        swap_maturities = (date(2025, 1, 1), date(2026, 1, 1))  # 1Y and 2Y swaps
        par_rates = (0.02, 0.025)  # 2% and 2.5% par swap rates

        curve = build_yield_curve_from_swaps(
            valuation_date=val,
            swap_maturities=swap_maturities,
            par_swap_rates=par_rates,
            swap_frequency="6M",
            day_count=DayCountConvention.ACT_365,
            compounding="cont",
        )

        # Verify we can query rates at both maturities
        r1 = curve.zero_rate(swap_maturities[0])
        r2 = curve.zero_rate(swap_maturities[1])
        assert r1 > 0.0
        assert r2 > 0.0
        assert r2 > r1  # Upward sloping curve

    def test_build_from_swaps_invalid_inputs(self) -> None:
        """Test error handling for invalid swap inputs."""
        val = date(2024, 1, 1)

        # Empty swaps
        with pytest.raises(ValueError, match="At least one swap"):
            build_yield_curve_from_swaps(
                valuation_date=val,
                swap_maturities=(),
                par_swap_rates=(),
            )

        # Mismatched lengths
        with pytest.raises(ValueError, match="must have the same length"):
            build_yield_curve_from_swaps(
                valuation_date=val,
                swap_maturities=(date(2025, 1, 1),),
                par_swap_rates=(0.02, 0.03),
            )


