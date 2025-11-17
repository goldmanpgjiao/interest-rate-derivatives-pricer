"""Tests for Hull-White calibrator."""

from datetime import date

import pytest

from montecarlo_ir.calibration.hw_calibrator import (
    CalibrationInstrument,
    CalibrationResult,
    calibrate_hull_white_to_instruments,
    calibrate_hull_white_to_vol_surface,
)
from montecarlo_ir.market_data.vol_surface import VolatilitySurface
from montecarlo_ir.market_data.yield_curve import build_yield_curve_from_zero_rates
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


def build_simple_vol_surface() -> VolatilitySurface:
    """Create a simple volatility surface for testing."""
    val = date(2024, 1, 1)
    expiry_times = (0.25, 0.5, 1.0)
    tenor_times = (0.25,)
    vol_matrix = ((0.15,), (0.16,), (0.17,))
    return VolatilitySurface(
        valuation_date=val,
        expiry_times=expiry_times,
        tenor_times=tenor_times,
        volatility_matrix=vol_matrix,
    )


class TestCalibrationInstrument:
    """Tests for CalibrationInstrument."""

    def test_caplet_instrument(self) -> None:
        """Test creating a caplet instrument."""
        inst = CalibrationInstrument(
            expiry_date=date(2024, 4, 1),
            maturity_date=date(2024, 7, 1),
            strike=0.02,
            market_price=0.001,
            instrument_type="caplet",
        )
        assert inst.strike == 0.02
        assert inst.market_price == 0.001


class TestHullWhiteCalibration:
    """Tests for Hull-White calibration."""

    def test_calibrate_to_instruments_requires_at_least_one(self) -> None:
        """Test that at least one instrument is required."""
        curve = build_simple_yield_curve()
        with pytest.raises(ValueError, match="At least one"):
            calibrate_hull_white_to_instruments(
                yield_curve=curve,
                instruments=[],
                initial_mean_reversion=0.1,
                initial_volatility=0.01,
                num_paths=100,  # Small for speed
            )

    def test_calibrate_to_instruments_basic(self) -> None:
        """Test basic calibration to instruments."""
        curve = build_simple_yield_curve()
        instruments = [
            CalibrationInstrument(
                expiry_date=date(2024, 4, 1),
                maturity_date=date(2024, 7, 1),
                strike=0.02,
                market_price=0.001,
                instrument_type="caplet",
            )
        ]

        result = calibrate_hull_white_to_instruments(
            yield_curve=curve,
            instruments=instruments,
            initial_mean_reversion=0.1,
            initial_volatility=0.01,
            num_paths=500,  # Small for speed
            seed=42,
        )

        assert isinstance(result, CalibrationResult)
        assert result.mean_reversion > 0.0
        assert result.volatility > 0.0
        assert result.calibration_error >= 0.0
        assert result.num_iterations > 0

    def test_calibrate_to_vol_surface(self) -> None:
        """Test calibration to volatility surface."""
        curve = build_simple_yield_curve()
        vol_surface = build_simple_vol_surface()
        strikes = (0.02, 0.02, 0.02)

        result = calibrate_hull_white_to_vol_surface(
            yield_curve=curve,
            vol_surface=vol_surface,
            caplet_strikes=strikes,
            num_paths=500,  # Small for speed
            seed=42,
        )

        assert isinstance(result, CalibrationResult)
        assert result.mean_reversion > 0.0
        assert result.volatility > 0.0

    def test_calibrate_to_vol_surface_invalid_strikes_length(self) -> None:
        """Test error when strikes length doesn't match surface."""
        curve = build_simple_yield_curve()
        vol_surface = build_simple_vol_surface()
        strikes = (0.02, 0.02)  # Wrong length

        with pytest.raises(ValueError, match="must have length"):
            calibrate_hull_white_to_vol_surface(
                yield_curve=curve,
                vol_surface=vol_surface,
                caplet_strikes=strikes,
                num_paths=100,
            )

    def test_calibration_result_model(self) -> None:
        """Test that calibration result contains valid model."""
        curve = build_simple_yield_curve()
        instruments = [
            CalibrationInstrument(
                expiry_date=date(2024, 4, 1),
                maturity_date=date(2024, 7, 1),
                strike=0.02,
                market_price=0.001,
                instrument_type="caplet",
            )
        ]

        result = calibrate_hull_white_to_instruments(
            yield_curve=curve,
            instruments=instruments,
            initial_mean_reversion=0.1,
            initial_volatility=0.01,
            num_paths=500,
            seed=42,
        )

        # Test that the calibrated model works
        model = result.calibrated_model
        times = [0.0, 0.25, 0.5]
        rates = model.simulate_short_rate_path(times)
        assert len(rates) == len(times)

