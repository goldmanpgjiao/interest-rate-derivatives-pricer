"""Volatility surface utilities.

Provides a minimal, typed `VolatilitySurface` for caplet and swaption volatility
queries with interpolation/extrapolation. Prefers pure computations and immutability.
"""

from __future__ import annotations

import bisect
from dataclasses import dataclass
from datetime import date
from typing import Literal

from montecarlo_ir.utils.date_helpers import DayCountConvention, year_fraction

InterpolationMethod = Literal["linear", "flat"]
ExtrapolationMethod = Literal["flat", "linear"]


def _validate_strictly_increasing(values: list[float]) -> None:
    """Validate a strictly increasing numeric sequence."""
    for i in range(1, len(values)):
        if not (values[i] > values[i - 1]):
            raise ValueError("Values must be strictly increasing.")


def _linear_interpolate(x0: float, y0: float, x1: float, y1: float, x: float) -> float:
    """Simple linear interpolation on y vs. x."""
    if x1 == x0:
        return y0
    w = (x - x0) / (x1 - x0)
    return (1.0 - w) * y0 + w * y1


@dataclass(frozen=True)
class VolatilitySurface:
    """Volatility surface for caplets or swaptions.

    The surface is defined by:
    - Expiry times (option expiry dates)
    - Tenor times (underlying instrument tenors)
    - Volatility matrix (expiry x tenor)

    Supports interpolation and extrapolation for volatility queries.

    Attributes:
        valuation_date: Curve valuation date.
        expiry_times: Option expiry times in years from valuation_date.
        tenor_times: Underlying instrument tenor times in years.
        volatility_matrix: 2D matrix of volatilities [expiry][tenor].
        interpolation: Interpolation method ('linear' or 'flat').
        extrapolation: Extrapolation method ('flat' or 'linear').
        day_count: Day count convention for time calculations.
    """

    valuation_date: date
    expiry_times: tuple[float, ...]  # Years from valuation_date
    tenor_times: tuple[float, ...]  # Years
    volatility_matrix: tuple[tuple[float, ...], ...]  # [expiry][tenor]
    interpolation: InterpolationMethod = "linear"
    extrapolation: ExtrapolationMethod = "flat"
    day_count: DayCountConvention = DayCountConvention.ACT_365

    def __post_init__(self) -> None:
        """Validate surface data."""
        if len(self.expiry_times) == 0:
            raise ValueError("At least one expiry time is required.")
        if len(self.tenor_times) == 0:
            raise ValueError("At least one tenor time is required.")

        # Validate strictly increasing times
        _validate_strictly_increasing(list(self.expiry_times))
        _validate_strictly_increasing(list(self.tenor_times))

        # Validate matrix dimensions
        if len(self.volatility_matrix) != len(self.expiry_times):
            raise ValueError(
                f"volatility_matrix must have {len(self.expiry_times)} rows (expiries), "
                f"got {len(self.volatility_matrix)}."
            )

        for i, row in enumerate(self.volatility_matrix):
            if len(row) != len(self.tenor_times):
                raise ValueError(
                    f"volatility_matrix row {i} must have {len(self.tenor_times)} columns (tenors), "
                    f"got {len(row)}."
                )

            # Validate volatilities are positive
            for j, vol in enumerate(row):
                if vol < 0.0:
                    raise ValueError(f"Volatility at [{i}][{j}] must be non-negative, got {vol}.")

    def volatility(self, expiry_date: date, tenor_years: float) -> float:
        """Get volatility for given expiry date and tenor.

        Args:
            expiry_date: Option expiry date.
            tenor_years: Underlying instrument tenor in years.

        Returns:
            Interpolated/extrapolated volatility.

        Raises:
            ValueError: If expiry_date is before valuation_date or tenor_years is invalid.
        """
        if expiry_date < self.valuation_date:
            raise ValueError("expiry_date must be on or after valuation_date.")

        expiry_time = year_fraction(self.valuation_date, expiry_date, self.day_count)
        return self.volatility_at_times(expiry_time, tenor_years)

    def volatility_at_times(self, expiry_time: float, tenor_time: float) -> float:
        """Get volatility for given expiry and tenor times.

        Args:
            expiry_time: Option expiry time in years from valuation_date.
            tenor_time: Underlying instrument tenor time in years.

        Returns:
            Interpolated/extrapolated volatility.

        Raises:
            ValueError: If times are negative.
        """
        if expiry_time < 0.0:
            raise ValueError("expiry_time must be non-negative.")
        if tenor_time < 0.0:
            raise ValueError("tenor_time must be non-negative.")

        # Find indices for interpolation
        exp_idx = self._find_index(self.expiry_times, expiry_time)
        ten_idx = self._find_index(self.tenor_times, tenor_time)

        # Get surrounding values
        exp_low, exp_high = self._get_bounds(self.expiry_times, exp_idx)
        ten_low, ten_high = self._get_bounds(self.tenor_times, ten_idx)

        # Extract volatility values at corners
        if exp_idx < 0:
            # Below first expiry - extrapolate
            vol_row_low = self.volatility_matrix[0]
            vol_row_high = self.volatility_matrix[0] if len(self.expiry_times) == 1 else self.volatility_matrix[1]
        elif exp_idx >= len(self.expiry_times) - 1:
            # Above last expiry - extrapolate
            if len(self.expiry_times) > 1 and self.extrapolation == "linear":
                # Use last two rows for linear extrapolation
                vol_row_low = self.volatility_matrix[-2]
                vol_row_high = self.volatility_matrix[-1]
            else:
                # Flat extrapolation - use last row
                vol_row_low = self.volatility_matrix[-1]
                vol_row_high = self.volatility_matrix[-1]
        else:
            # Between expiries - interpolate
            vol_row_low = self.volatility_matrix[exp_idx]
            vol_row_high = self.volatility_matrix[exp_idx + 1]

        # Interpolate/extrapolate in tenor dimension first
        if ten_idx < 0:
            # Below first tenor
            vol_low = vol_row_low[0]
            vol_high = vol_row_high[0]
        elif ten_idx >= len(self.tenor_times) - 1:
            # Above last tenor
            vol_low = vol_row_low[-1]
            vol_high = vol_row_high[-1]
        else:
            # Between tenors
            vol_low = self._interpolate_1d(
                ten_low, vol_row_low[ten_idx], ten_high, vol_row_low[ten_idx + 1], tenor_time
            )
            vol_high = self._interpolate_1d(
                ten_low, vol_row_high[ten_idx], ten_high, vol_row_high[ten_idx + 1], tenor_time
            )

        # Interpolate/extrapolate in expiry dimension
        return self._interpolate_1d(exp_low, vol_low, exp_high, vol_high, expiry_time)

    def _find_index(self, times: tuple[float, ...], t: float) -> int:
        """Find index for interpolation/extrapolation."""
        if t <= times[0]:
            return -1  # Below first
        if t >= times[-1]:
            return len(times) - 1  # At or above last
        return bisect.bisect_right(times, t) - 1

    def _get_bounds(self, times: tuple[float, ...], idx: int) -> tuple[float, float]:
        """Get lower and upper bounds for interpolation."""
        if idx < 0:
            # Extrapolation below
            if self.extrapolation == "flat":
                return (times[0], times[0])
            # Linear extrapolation
            if len(times) > 1:
                return (times[0], times[1])
            return (times[0], times[0])

        if idx >= len(times) - 1:
            # Extrapolation above
            if self.extrapolation == "flat":
                return (times[-1], times[-1])
            # Linear extrapolation
            if len(times) > 1:
                return (times[-2], times[-1])
            return (times[-1], times[-1])

        # Interpolation
        return (times[idx], times[idx + 1])

    def _interpolate_1d(
        self, x0: float, y0: float, x1: float, y1: float, x: float
    ) -> float:
        """1D interpolation with flat or linear method."""
        if self.interpolation == "flat":
            return y0
        return _linear_interpolate(x0, y0, x1, y1, x)


def build_volatility_surface_from_matrix(
    valuation_date: date,
    expiry_dates: list[date] | tuple[date, ...],
    tenor_years: list[float] | tuple[float, ...],
    volatility_matrix: list[list[float]] | tuple[tuple[float, ...], ...],
    *,
    day_count: DayCountConvention = DayCountConvention.ACT_365,
    interpolation: InterpolationMethod = "linear",
    extrapolation: ExtrapolationMethod = "flat",
) -> VolatilitySurface:
    """Build volatility surface from expiry dates, tenor years, and volatility matrix.

    Args:
        valuation_date: Curve valuation date.
        expiry_dates: Option expiry dates.
        tenor_years: Underlying instrument tenors in years.
        volatility_matrix: 2D matrix [expiry][tenor] of volatilities.
        day_count: Day count convention for time calculations.
        interpolation: Interpolation method.
        extrapolation: Extrapolation method.

    Returns:
        VolatilitySurface instance.

    Raises:
        ValueError: If inputs are invalid.
    """
    # Convert expiry dates to times
    expiry_times = tuple(
        year_fraction(valuation_date, d, day_count) for d in expiry_dates
    )

    # Validate and convert inputs
    tenor_times = tuple(float(t) for t in tenor_years)
    vol_matrix = tuple(tuple(float(v) for v in row) for row in volatility_matrix)

    return VolatilitySurface(
        valuation_date=valuation_date,
        expiry_times=expiry_times,
        tenor_times=tenor_times,
        volatility_matrix=vol_matrix,
        interpolation=interpolation,
        extrapolation=extrapolation,
        day_count=day_count,
    )

