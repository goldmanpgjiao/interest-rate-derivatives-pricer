"""Cap and Floor products.

Implementation of interest rate caps and floors, including individual caplets and floorlets.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal

import numpy as np

from montecarlo_ir.market_data.yield_curve import YieldCurve
from montecarlo_ir.utils.date_helpers import (
    BusinessDayRule,
    DayCountConvention,
    generate_schedule,
    year_fraction,
)

CapFloorType = Literal["cap", "floor"]


@dataclass(frozen=True)
class CapletFloorlet:
    """Single caplet or floorlet.

    Attributes:
        reset_date: Date when rate is reset.
        payment_date: Date when payment is made.
        strike: Strike rate.
        notional: Notional amount.
        day_count: Day count convention.
        option_type: 'cap' (caplet) or 'floor' (floorlet).
    """

    reset_date: date
    payment_date: date
    strike: float
    notional: float
    day_count: DayCountConvention
    option_type: CapFloorType


@dataclass(frozen=True)
class CapFloor:
    """Interest Rate Cap or Floor.

    A cap provides protection against rising rates (pays when rate > strike).
    A floor provides protection against falling rates (pays when rate < strike).

    Attributes:
        valuation_date: Valuation date.
        start_date: Cap/Floor start date.
        maturity_date: Cap/Floor maturity date.
        strike: Strike rate (annual).
        notional: Notional amount.
        cap_floor_type: 'cap' or 'floor'.
        frequency: Payment frequency (e.g., '3M', '6M').
        day_count: Day count convention.
        business_day_rule: Business day adjustment rule.
        calendar: Holiday calendar.
    """

    valuation_date: date
    start_date: date
    maturity_date: date
    strike: float
    notional: float
    cap_floor_type: CapFloorType = "cap"
    frequency: str = "3M"
    day_count: DayCountConvention = DayCountConvention.ACT_360
    business_day_rule: BusinessDayRule = BusinessDayRule.MODIFIED_FOLLOWING
    calendar: list[date] | None = None

    def __post_init__(self) -> None:
        """Validate cap/floor parameters."""
        if self.maturity_date <= self.start_date:
            raise ValueError("maturity_date must be after start_date.")
        if self.start_date < self.valuation_date:
            raise ValueError("start_date must be on or after valuation_date.")
        if self.notional <= 0.0:
            raise ValueError("notional must be positive.")
        if self.strike < 0.0:
            raise ValueError("strike must be non-negative.")

    def get_caplets_floorlets(self) -> list[CapletFloorlet]:
        """Generate list of caplets/floorlets.

        Returns:
            List of caplets (for cap) or floorlets (for floor).
        """
        schedule = generate_schedule(
            self.start_date,
            self.maturity_date,
            frequency=self.frequency,
            business_day_rule=self.business_day_rule,
            calendar=self.calendar,
        )

        caplets = []
        prev_date = self.start_date

        for payment_date in schedule:
            if payment_date <= self.valuation_date:
                prev_date = payment_date
                continue

            # Reset date is typically the start of the period
            reset_date = prev_date

            caplets.append(
                CapletFloorlet(
                    reset_date=reset_date,
                    payment_date=payment_date,
                    strike=self.strike,
                    notional=self.notional,
                    day_count=self.day_count,
                    option_type=self.cap_floor_type,
                )
            )
            prev_date = payment_date

        return caplets

    def payoff(
        self,
        yield_curve: YieldCurve,
        floating_rates: dict[date, float] | None = None,
    ) -> float:
        """Calculate cap/floor payoff (PV) using yield curve.

        Args:
            yield_curve: Yield curve for discounting and forward rates.
            floating_rates: Optional dict of floating rates by reset date.
                          If None, uses forward rates from yield curve.

        Returns:
            Present value of cap/floor.
        """
        caplets = self.get_caplets_floorlets()
        total_pv = 0.0

        for caplet in caplets:
            # Get floating rate
            if floating_rates is not None and caplet.reset_date in floating_rates:
                float_rate = floating_rates[caplet.reset_date]
            else:
                # Use forward rate from yield curve
                float_rate = yield_curve.forward_rate(caplet.reset_date, caplet.payment_date)

            # Calculate payoff
            tau = year_fraction(caplet.reset_date, caplet.payment_date, caplet.day_count)

            if caplet.option_type == "cap":
                payoff = max(0.0, float_rate - caplet.strike)
            else:  # floor
                payoff = max(0.0, caplet.strike - float_rate)

            # Discount to present
            df = yield_curve.discount_factor(caplet.payment_date)
            total_pv += caplet.notional * payoff * tau * df

        return total_pv

    def payoff_mc(
        self,
        rates: np.ndarray,
        times: np.ndarray,
        yield_curve: YieldCurve,
    ) -> float:
        """Calculate cap/floor payoff for Monte Carlo path.

        Args:
            rates: Simulated rates [n_times] (short rates or forward rates).
            times: Time points [n_times] (years from valuation_date).
            yield_curve: Yield curve for discounting.

        Returns:
            Payoff value for this path.
        """
        from datetime import timedelta

        caplets = self.get_caplets_floorlets()
        total_pv = 0.0

        # Convert times to dates
        val_date = self.valuation_date
        time_to_date_map = {}
        for t, rate in zip(times, rates):
            days = int(t * 365.0)
            d = val_date + timedelta(days=days)
            time_to_date_map[d] = rate

        for caplet in caplets:
            # Get rate at reset date
            float_rate = self._get_rate_at_date(
                caplet.reset_date, time_to_date_map, rates, times
            )

            # Calculate payoff
            tau = year_fraction(caplet.reset_date, caplet.payment_date, caplet.day_count)

            if caplet.option_type == "cap":
                payoff = max(0.0, float_rate - caplet.strike)
            else:  # floor
                payoff = max(0.0, caplet.strike - float_rate)

            # Discount to present
            df = yield_curve.discount_factor(caplet.payment_date)
            total_pv += caplet.notional * payoff * tau * df

        return total_pv

    def _get_rate_at_date(
        self,
        target_date: date,
        time_to_date_map: dict[date, float],
        rates: np.ndarray,
        times: np.ndarray,
    ) -> float:
        """Get rate at target date from simulated path."""
        # Try exact match first
        if target_date in time_to_date_map:
            return time_to_date_map[target_date]

        # Interpolate from times
        val_date = self.valuation_date
        from datetime import timedelta

        target_days = (target_date - val_date).days
        target_time = target_days / 365.0

        # Find closest time points
        if target_time <= times[0]:
            return float(rates[0])
        if target_time >= times[-1]:
            return float(rates[-1])

        # Linear interpolation
        for i in range(len(times) - 1):
            if times[i] <= target_time <= times[i + 1]:
                t1, t2 = times[i], times[i + 1]
                r1, r2 = rates[i], rates[i + 1]
                w = (target_time - t1) / (t2 - t1)
                return float((1.0 - w) * r1 + w * r2)

        return float(rates[-1])

