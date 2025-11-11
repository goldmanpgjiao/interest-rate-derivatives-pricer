"""Yield curve utilities.

Provides a minimal, typed `YieldCurve` for discount factors, zero rates, and forward rates
with simple interpolation choices. Prefers pure computations and immutability.
"""

from __future__ import annotations

import bisect
import math
from dataclasses import dataclass
from datetime import date
from typing import Literal

from montecarlo_ir.utils.date_helpers import DayCountConvention, year_fraction

InterpolationMethod = Literal["linear_zero", "log_linear_df"]
CompoundingMethod = Literal["cont", "simple", "annual"]


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
class YieldCurve:
    """Yield curve defined by pillar dates and zero rates.

    The curve supports:
    - Discount factor queries
    - Zero rate queries
    - Forward rate queries
    with two interpolation methods:
      - 'linear_zero'     : linear interpolation on zero rates
      - 'log_linear_df'   : linear interpolation on log discount factors

    All calculations use a specified day count convention for time conversion.
    """

    valuation_date: date
    pillar_dates: tuple[date, ...]
    pillar_zero_rates: tuple[float, ...]
    day_count: DayCountConvention = DayCountConvention.ACT_365
    interpolation: InterpolationMethod = "log_linear_df"
    compounding: CompoundingMethod = "cont"

    def __post_init__(self) -> None:
        if len(self.pillar_dates) != len(self.pillar_zero_rates):
            raise ValueError("pillar_dates and pillar_zero_rates must have the same length.")
        if len(self.pillar_dates) == 0:
            raise ValueError("At least one pillar is required.")
        if any(d < self.valuation_date for d in self.pillar_dates):
            raise ValueError("All pillar_dates must be on or after valuation_date.")

        # Ensure strictly increasing pillar_dates
        sorted_pairs = sorted(zip(self.pillar_dates, self.pillar_zero_rates), key=lambda x: x[0])
        dates_sorted = [d for d, _ in sorted_pairs]
        _validate_strictly_increasing([d.toordinal() for d in dates_sorted])

        # Compute strictly increasing times from valuation_date
        times = [
            year_fraction(self.valuation_date, d, self.day_count) for d in dates_sorted
        ]
        _validate_strictly_increasing(times)

        # Freeze canonical sorted data in object state
        object.__setattr__(self, "pillar_dates", tuple(dates_sorted))
        object.__setattr__(self, "pillar_zero_rates", tuple(r for _, r in sorted_pairs))
        object.__setattr__(self, "_pillar_times", tuple(times))  # years

    # -------- Public API --------
    def discount_factor(self, target_date: date) -> float:
        """Compute discount factor to a target date."""
        if target_date < self.valuation_date:
            raise ValueError("target_date must be on or after valuation_date.")
        t = self._time_from_valuation(target_date)
        if t == 0.0:
            return 1.0
        r = self._zero_rate_at_time(t)
        return self._df_from_rate(r, t)

    def zero_rate(self, target_date: date) -> float:
        """Compute zero rate to a target date (consistent with curve interpolation)."""
        if target_date < self.valuation_date:
            raise ValueError("target_date must be on or after valuation_date.")
        t = self._time_from_valuation(target_date)
        if t == 0.0:
            # Define zero-maturity zero rate as first pillar's implied instantaneous rate
            return self.pillar_zero_rates[0]
        return self._zero_rate_at_time(t)

    def forward_rate(self, start_date: date, end_date: date) -> float:
        """Compute simple forward rate between two dates."""
        if end_date <= start_date:
            raise ValueError("end_date must be after start_date.")
        df_start = self.discount_factor(start_date)
        df_end = self.discount_factor(end_date)
        tau = year_fraction(start_date, end_date, self.day_count)
        # Return simple forward rate over the period
        return (df_start / df_end - 1.0) / tau

    # -------- Internal helpers --------
    def _time_from_valuation(self, d: date) -> float:
        return year_fraction(self.valuation_date, d, self.day_count)

    def _df_from_rate(self, r: float, t: float) -> float:
        if self.compounding == "cont":
            return math.exp(-r * t)
        if self.compounding == "annual":
            return 1.0 / ((1.0 + r) ** t)
        if self.compounding == "simple":
            return 1.0 / (1.0 + r * t)
        raise ValueError(f"Unsupported compounding method: {self.compounding}")

    def _rate_from_df(self, df: float, t: float) -> float:
        if t == 0.0:
            return self.pillar_zero_rates[0]
        if self.compounding == "cont":
            return -math.log(df) / t
        if self.compounding == "annual":
            return (df ** (-1.0 / t)) - 1.0
        if self.compounding == "simple":
            return (1.0 / df - 1.0) / t
        raise ValueError(f"Unsupported compounding method: {self.compounding}")

    def _zero_rate_at_time(self, t: float) -> float:
        times = self._pillar_times
        zeros = self.pillar_zero_rates

        # Exact match or out-of-bounds
        if t <= times[0]:
            return zeros[0]
        if t >= times[-1]:
            return zeros[-1]

        idx = bisect.bisect_right(times, t)
        t0, t1 = times[idx - 1], times[idx]
        z0, z1 = zeros[idx - 1], zeros[idx]

        if self.interpolation == "linear_zero":
            return _linear_interpolate(t0, z0, t1, z1, t)

        if self.interpolation == "log_linear_df":
            # interpolate log DF linearly, then convert back to zero rate
            df0 = self._df_from_rate(z0, t0)
            df1 = self._df_from_rate(z1, t1)
            log_df0 = math.log(df0)
            log_df1 = math.log(df1)
            log_df_t = _linear_interpolate(t0, log_df0, t1, log_df1, t)
            df_t = math.exp(log_df_t)
            return self._rate_from_df(df_t, t)

        raise ValueError(f"Unsupported interpolation method: {self.interpolation}")


# --------- Bootstrapping helpers (simple) ---------
def build_yield_curve_from_discount_factors(
    valuation_date: date,
    pillar_dates: list[date] | tuple[date, ...],
    discount_factors: list[float] | tuple[float, ...],
    *,
    day_count: DayCountConvention = DayCountConvention.ACT_365,
    interpolation: InterpolationMethod = "log_linear_df",
    compounding: CompoundingMethod = "cont",
) -> YieldCurve:
    """Create YieldCurve from discount factors by converting to zero rates."""
    if len(pillar_dates) != len(discount_factors):
        raise ValueError("pillar_dates and discount_factors must have the same length.")
    zeros: list[float] = []
    for d, df in zip(pillar_dates, discount_factors):
        t = year_fraction(valuation_date, d, day_count)
        if t <= 0.0:
            raise ValueError("All pillar dates must be after valuation_date.")
        if df <= 0.0 or df >= 1.0 + 1e-12:
            raise ValueError("Discount factors must be in (0, 1].")
        # Convert DF to zero consistent with compounding
        if compounding == "cont":
            z = -math.log(df) / t
        elif compounding == "annual":
            z = df ** (-1.0 / t) - 1.0
        elif compounding == "simple":
            z = (1.0 / df - 1.0) / t
        else:
            raise ValueError(f"Unsupported compounding method: {compounding}")
        zeros.append(z)
    return YieldCurve(
        valuation_date=valuation_date,
        pillar_dates=tuple(pillar_dates),
        pillar_zero_rates=tuple(zeros),
        day_count=day_count,
        interpolation=interpolation,
        compounding=compounding,
    )


def build_yield_curve_from_zero_rates(
    valuation_date: date,
    pillar_dates: list[date] | tuple[date, ...],
    zero_rates: list[float] | tuple[float, ...],
    *,
    day_count: DayCountConvention = DayCountConvention.ACT_365,
    interpolation: InterpolationMethod = "log_linear_df",
    compounding: CompoundingMethod = "cont",
) -> YieldCurve:
    """Create YieldCurve directly from zero rates."""
    return YieldCurve(
        valuation_date=valuation_date,
        pillar_dates=tuple(pillar_dates),
        pillar_zero_rates=tuple(zero_rates),
        day_count=day_count,
        interpolation=interpolation,
        compounding=compounding,
    )


def build_yield_curve_from_deposits_simple(
    valuation_date: date,
    deposit_maturities: list[date] | tuple[date, ...],
    deposit_simple_rates: list[float] | tuple[float, ...],
    *,
    day_count: DayCountConvention = DayCountConvention.ACT_365,
    interpolation: InterpolationMethod = "log_linear_df",
    compounding: CompoundingMethod = "cont",
) -> YieldCurve:
    """Create YieldCurve from simple deposit quotes r over [0, T]:
    DF = 1 / (1 + r * T), then convert to zero consistent with chosen compounding."""
    if len(deposit_maturities) != len(deposit_simple_rates):
        raise ValueError("deposit_maturities and deposit_simple_rates must have the same length.")
    dfs: list[float] = []
    for d, r in zip(deposit_maturities, deposit_simple_rates):
        t = year_fraction(valuation_date, d, day_count)
        if t <= 0.0:
            raise ValueError("All deposit maturities must be after valuation_date.")
        df = 1.0 / (1.0 + r * t)
        dfs.append(df)
    return build_yield_curve_from_discount_factors(
        valuation_date=valuation_date,
        pillar_dates=tuple(deposit_maturities),
        discount_factors=tuple(dfs),
        day_count=day_count,
        interpolation=interpolation,
        compounding=compounding,
    )


def build_yield_curve_from_swaps(
    valuation_date: date,
    swap_maturities: list[date] | tuple[date, ...],
    par_swap_rates: list[float] | tuple[float, ...],
    swap_frequency: str = "6M",
    *,
    day_count: DayCountConvention = DayCountConvention.ACT_365,
    interpolation: InterpolationMethod = "log_linear_df",
    compounding: CompoundingMethod = "cont",
) -> YieldCurve:
    """Bootstrap YieldCurve from par swap rates.

    For each swap, the par rate S satisfies:
        sum(DF(t_i) * S * tau_i) = 1 - DF(T)
    where tau_i are the period lengths and T is the swap maturity.

    This function bootstraps discount factors sequentially and converts to zero rates.

    Args:
        valuation_date: Curve valuation date.
        swap_maturities: Maturity dates for each swap.
        par_swap_rates: Par swap rates (as decimals, e.g., 0.05 for 5%).
        swap_frequency: Frequency string for swap payments (e.g., "6M", "3M").
        day_count: Day count convention for time calculations.
        interpolation: Interpolation method for the curve.
        compounding: Compounding method for zero rates.

    Returns:
        YieldCurve bootstrapped from swap rates.

    Raises:
        ValueError: If inputs are invalid or bootstrapping fails.
    """
    from montecarlo_ir.utils.date_helpers import BusinessDayRule, generate_schedule

    if len(swap_maturities) != len(par_swap_rates):
        raise ValueError("swap_maturities and par_swap_rates must have the same length.")
    if len(swap_maturities) == 0:
        raise ValueError("At least one swap is required.")

    # Sort by maturity
    sorted_pairs = sorted(zip(swap_maturities, par_swap_rates), key=lambda x: x[0])
    sorted_maturities = [d for d, _ in sorted_pairs]
    sorted_rates = [r for _, r in sorted_pairs]

    # Bootstrap discount factors sequentially
    pillar_dates: list[date] = []
    discount_factors: list[float] = []

    for swap_maturity, swap_rate in zip(sorted_maturities, sorted_rates):
        # Generate payment schedule for this swap
        schedule = generate_schedule(
            valuation_date,
            swap_maturity,
            frequency=swap_frequency,
            business_day_rule=BusinessDayRule.NONE,  # Use exact dates for bootstrapping
        )

        # Remove valuation_date if present (no payment at start)
        if schedule and schedule[0] == valuation_date:
            schedule = schedule[1:]

        if not schedule:
            raise ValueError(f"Invalid swap schedule for maturity {swap_maturity}.")

        # Build temporary curve from existing pillars for interpolation
        if pillar_dates:
            temp_curve = build_yield_curve_from_discount_factors(
                valuation_date=valuation_date,
                pillar_dates=tuple(pillar_dates),
                discount_factors=tuple(discount_factors),
                day_count=day_count,
                interpolation=interpolation,
                compounding=compounding,
            )
        else:
            # First swap: use simple rate approximation
            t = year_fraction(valuation_date, swap_maturity, day_count)
            if t <= 0.0:
                raise ValueError("All swap maturities must be after valuation_date.")
            # For first swap, assume simple rate: DF = 1 / (1 + r * t)
            df_maturity = 1.0 / (1.0 + swap_rate * t)
            pillar_dates.append(swap_maturity)
            discount_factors.append(df_maturity)
            continue

        # Calculate fixed leg PV using existing curve
        # Fixed leg: sum of DF(t_i) * swap_rate * tau_i for all payment periods
        # We need to solve for DF(T) where T is the swap maturity
        fixed_leg_pv_known = 0.0  # PV of payments before maturity
        tau_maturity = 0.0  # Period length for final payment at maturity

        # Iterate through payment periods
        for i in range(len(schedule)):
            if i == 0:
                # First period: from valuation_date to first payment
                start_date = valuation_date
                end_date = schedule[0]
            else:
                # Subsequent periods: from previous payment to current payment
                start_date = schedule[i - 1]
                end_date = schedule[i]

            tau = year_fraction(start_date, end_date, day_count)

            if end_date == swap_maturity:
                # This is the maturity payment - we'll solve for its DF
                tau_maturity = tau
            else:
                # Known payment - use existing curve
                df_pay = temp_curve.discount_factor(end_date)
                fixed_leg_pv_known += df_pay * swap_rate * tau

        # Handle case where maturity is not in schedule
        if schedule[-1] != swap_maturity:
            tau_maturity = year_fraction(schedule[-1], swap_maturity, day_count)

        # Floating leg PV = 1 - DF(T)
        # Fixed leg PV = fixed_leg_pv_known + DF(T) * swap_rate * tau_maturity
        # At par: 1 - DF(T) = fixed_leg_pv_known + DF(T) * swap_rate * tau_maturity
        # Solving: DF(T) = (1 - fixed_leg_pv_known) / (1 + swap_rate * tau_maturity)

        if tau_maturity > 0.0:
            df_maturity = (1.0 - fixed_leg_pv_known) / (1.0 + swap_rate * tau_maturity)
        else:
            # Edge case: maturity equals valuation date (shouldn't happen)
            df_maturity = 1.0

        if df_maturity <= 0.0 or df_maturity > 1.0:
            raise ValueError(
                f"Bootstrapping failed for swap maturity {swap_maturity}: "
                f"invalid discount factor {df_maturity}."
            )

        pillar_dates.append(swap_maturity)
        discount_factors.append(df_maturity)

    return build_yield_curve_from_discount_factors(
        valuation_date=valuation_date,
        pillar_dates=tuple(pillar_dates),
        discount_factors=tuple(discount_factors),
        day_count=day_count,
        interpolation=interpolation,
        compounding=compounding,
    )


