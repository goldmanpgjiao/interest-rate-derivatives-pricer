"""Tests for VolatilitySurface."""

from datetime import date

import pytest

from montecarlo_ir.market_data.vol_surface import (
    VolatilitySurface,
    build_volatility_surface_from_matrix,
)
from montecarlo_ir.utils.date_helpers import DayCountConvention


def build_simple_surface() -> VolatilitySurface:
    """Create a simple test volatility surface."""
    val = date(2024, 1, 1)
    expiry_times = (0.25, 0.5, 1.0, 2.0)  # 3M, 6M, 1Y, 2Y
    tenor_times = (0.25, 0.5, 1.0, 2.0, 5.0)  # 3M, 6M, 1Y, 2Y, 5Y
    # Simple upward sloping surface
    vol_matrix = (
        (0.15, 0.16, 0.17, 0.18, 0.19),  # 3M expiry
        (0.16, 0.17, 0.18, 0.19, 0.20),  # 6M expiry
        (0.17, 0.18, 0.19, 0.20, 0.21),  # 1Y expiry
        (0.18, 0.19, 0.20, 0.21, 0.22),  # 2Y expiry
    )
    return VolatilitySurface(
        valuation_date=val,
        expiry_times=expiry_times,
        tenor_times=tenor_times,
        volatility_matrix=vol_matrix,
    )


class TestVolatilitySurfaceConstruction:
    """Tests for VolatilitySurface construction and validation."""

    def test_requires_at_least_one_expiry(self) -> None:
        """Test that at least one expiry is required."""
        with pytest.raises(ValueError, match="At least one expiry"):
            VolatilitySurface(
                valuation_date=date(2024, 1, 1),
                expiry_times=(),
                tenor_times=(1.0,),
                volatility_matrix=((0.2,),),
            )

    def test_requires_at_least_one_tenor(self) -> None:
        """Test that at least one tenor is required."""
        with pytest.raises(ValueError, match="At least one tenor"):
            VolatilitySurface(
                valuation_date=date(2024, 1, 1),
                expiry_times=(1.0,),
                tenor_times=(),
                volatility_matrix=((),),
            )

    def test_matrix_dimensions_must_match(self) -> None:
        """Test that matrix dimensions must match expiry and tenor counts."""
        with pytest.raises(ValueError, match="must have.*rows"):
            VolatilitySurface(
                valuation_date=date(2024, 1, 1),
                expiry_times=(1.0, 2.0),
                tenor_times=(1.0,),
                volatility_matrix=((0.2,),),  # Only 1 row, need 2
            )

        with pytest.raises(ValueError, match="must have.*columns"):
            VolatilitySurface(
                valuation_date=date(2024, 1, 1),
                expiry_times=(1.0,),
                tenor_times=(1.0, 2.0),
                volatility_matrix=((0.2,),),  # Only 1 column, need 2
            )

    def test_volatilities_must_be_non_negative(self) -> None:
        """Test that volatilities must be non-negative."""
        with pytest.raises(ValueError, match="must be non-negative"):
            VolatilitySurface(
                valuation_date=date(2024, 1, 1),
                expiry_times=(1.0,),
                tenor_times=(1.0,),
                volatility_matrix=((-0.1,),),
            )

    def test_times_must_be_strictly_increasing(self) -> None:
        """Test that expiry and tenor times must be strictly increasing."""
        with pytest.raises(ValueError, match="strictly increasing"):
            VolatilitySurface(
                valuation_date=date(2024, 1, 1),
                expiry_times=(1.0, 1.0),  # Not strictly increasing
                tenor_times=(1.0,),
                volatility_matrix=((0.2,), (0.2,)),
            )


class TestVolatilityQueries:
    """Tests for volatility queries."""

    def test_volatility_at_exact_grid_point(self) -> None:
        """Test querying volatility at exact grid point."""
        surface = build_simple_surface()
        # Query at first expiry, first tenor
        vol = surface.volatility_at_times(0.25, 0.25)
        assert abs(vol - 0.15) < 1e-10

    def test_volatility_interpolation(self) -> None:
        """Test linear interpolation between grid points."""
        surface = build_simple_surface()
        # Query between grid points
        vol = surface.volatility_at_times(0.375, 0.375)  # Midpoint
        # Should be between 0.15 and 0.17 (roughly)
        assert 0.14 < vol < 0.18

    def test_volatility_extrapolation_flat(self) -> None:
        """Test flat extrapolation beyond grid."""
        surface = build_simple_surface()
        # Query beyond last expiry
        vol_high = surface.volatility_at_times(5.0, 1.0)
        # Should use last expiry row, last tenor value
        assert vol_high > 0.0

        # Query below first expiry
        vol_low = surface.volatility_at_times(0.1, 1.0)
        assert vol_low > 0.0

    def test_volatility_extrapolation_linear(self) -> None:
        """Test linear extrapolation."""
        surface = VolatilitySurface(
            valuation_date=date(2024, 1, 1),
            expiry_times=(1.0, 2.0),
            tenor_times=(1.0, 2.0),
            volatility_matrix=((0.2, 0.21), (0.22, 0.23)),
            extrapolation="linear",
        )
        # Query beyond last expiry - should extrapolate using last two expiries
        vol = surface.volatility_at_times(3.0, 1.0)
        # Linear extrapolation from 1.0->2.0 (0.2->0.22) to 3.0 should give ~0.24
        assert vol > 0.22  # Should be above last expiry value
        assert vol < 0.26  # Reasonable upper bound

    def test_volatility_from_dates(self) -> None:
        """Test querying volatility using dates."""
        surface = build_simple_surface()
        expiry_date = date(2024, 4, 1)  # ~3 months
        vol = surface.volatility(expiry_date, 1.0)
        assert vol > 0.0

    def test_volatility_invalid_expiry_date(self) -> None:
        """Test error when expiry date is before valuation date."""
        surface = build_simple_surface()
        with pytest.raises(ValueError, match="must be on or after"):
            surface.volatility(date(2023, 12, 1), 1.0)

    def test_volatility_invalid_times(self) -> None:
        """Test error when times are negative."""
        surface = build_simple_surface()
        with pytest.raises(ValueError, match="must be non-negative"):
            surface.volatility_at_times(-0.1, 1.0)
        with pytest.raises(ValueError, match="must be non-negative"):
            surface.volatility_at_times(1.0, -0.1)


class TestBuildHelpers:
    """Tests for build helper functions."""

    def test_build_from_matrix(self) -> None:
        """Test building surface from matrix helper."""
        val = date(2024, 1, 1)
        expiry_dates = (date(2024, 4, 1), date(2024, 7, 1))
        tenor_years = (0.25, 0.5, 1.0)
        vol_matrix = ((0.15, 0.16, 0.17), (0.16, 0.17, 0.18))

        surface = build_volatility_surface_from_matrix(
            valuation_date=val,
            expiry_dates=expiry_dates,
            tenor_years=tenor_years,
            volatility_matrix=vol_matrix,
        )

        # Verify we can query
        vol = surface.volatility(expiry_dates[0], 0.25)
        assert abs(vol - 0.15) < 1e-6

    def test_build_from_matrix_flat_interpolation(self) -> None:
        """Test building with flat interpolation."""
        val = date(2024, 1, 1)
        expiry_dates = (date(2024, 4, 1),)
        tenor_years = (1.0,)
        vol_matrix = ((0.2,),)

        surface = build_volatility_surface_from_matrix(
            valuation_date=val,
            expiry_dates=expiry_dates,
            tenor_years=tenor_years,
            volatility_matrix=vol_matrix,
            interpolation="flat",
        )

        # With flat interpolation, should return same value
        vol = surface.volatility_at_times(0.3, 1.5)
        assert vol == 0.2

