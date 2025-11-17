"""Interest Rate Swap (IRS) product.

Vanilla interest rate swap implementation with cashflow generation and payoff calculation.
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

SwapType = Literal["payer", "receiver"]


@dataclass(frozen=True)
class Cashflow:
    """Single cashflow in a swap.

    Attributes:
        payment_date: Date of payment.
        reset_date: Date when rate is reset (for floating leg).
        notional: Notional amount.
        rate: Fixed or floating rate.
        day_count: Day count convention for accrual period.
    """

    payment_date: date
    reset_date: date | None
    notional: float
    rate: float
    day_count: DayCountConvention


@dataclass(frozen=True)
class InterestRateSwap:
    """Vanilla Interest Rate Swap.

    A swap where one party pays fixed rate and receives floating rate (payer swap),
    or receives fixed rate and pays floating rate (receiver swap).

    Attributes:
        valuation_date: Valuation date.
        start_date: Swap start date.
        maturity_date: Swap maturity date.
        fixed_rate: Fixed rate (annual).
        notional: Notional amount.
        swap_type: 'payer' (pay fixed, receive float) or 'receiver' (receive fixed, pay float).
        fixed_frequency: Fixed leg payment frequency (e.g., '6M', '1Y').
        floating_frequency: Floating leg payment frequency (e.g., '3M', '6M').
        fixed_day_count: Day count convention for fixed leg.
        floating_day_count: Day count convention for floating leg.
        business_day_rule: Business day adjustment rule.
        calendar: Holiday calendar (list of non-business days).
    """

    valuation_date: date
    start_date: date
    maturity_date: date
    fixed_rate: float
    notional: float
    swap_type: SwapType = "payer"
    fixed_frequency: str = "6M"
    floating_frequency: str = "6M"
    fixed_day_count: DayCountConvention = DayCountConvention.ACT_365
    floating_day_count: DayCountConvention = DayCountConvention.ACT_360
    business_day_rule: BusinessDayRule = BusinessDayRule.MODIFIED_FOLLOWING
    calendar: list[date] | None = None

    def __post_init__(self) -> None:
        """Validate swap parameters."""
        if self.maturity_date <= self.start_date:
            raise ValueError("maturity_date must be after start_date.")
        if self.start_date < self.valuation_date:
            raise ValueError("start_date must be on or after valuation_date.")
        if self.notional <= 0.0:
            raise ValueError("notional must be positive.")
        if self.fixed_rate < 0.0:
            raise ValueError("fixed_rate must be non-negative.")

    def get_fixed_leg_cashflows(self) -> list[Cashflow]:
        """Generate fixed leg cashflows.

        Returns:
            List of fixed leg cashflows.
        """
        schedule = generate_schedule(
            self.start_date,
            self.maturity_date,
            frequency=self.fixed_frequency,
            business_day_rule=self.business_day_rule,
            calendar=self.calendar,
        )

        cashflows = []
        prev_date = self.start_date

        for payment_date in schedule:
            if payment_date <= self.valuation_date:
                prev_date = payment_date
                continue

            tau = year_fraction(prev_date, payment_date, self.fixed_day_count)
            cashflows.append(
                Cashflow(
                    payment_date=payment_date,
                    reset_date=None,
                    notional=self.notional,
                    rate=self.fixed_rate,
                    day_count=self.fixed_day_count,
                )
            )
            prev_date = payment_date

        return cashflows

    def get_floating_leg_cashflows(self) -> list[Cashflow]:
        """Generate floating leg cashflows (reset dates).

        Returns:
            List of floating leg cashflows with reset dates.
        """
        schedule = generate_schedule(
            self.start_date,
            self.maturity_date,
            frequency=self.floating_frequency,
            business_day_rule=self.business_day_rule,
            calendar=self.calendar,
        )

        cashflows = []
        prev_date = self.start_date

        for payment_date in schedule:
            if payment_date <= self.valuation_date:
                prev_date = payment_date
                continue

            # Reset date is typically 2 business days before payment (spot lag)
            # For simplicity, use previous payment date as reset
            reset_date = prev_date

            cashflows.append(
                Cashflow(
                    payment_date=payment_date,
                    reset_date=reset_date,
                    notional=self.notional,
                    rate=0.0,  # Floating rate determined at reset
                    day_count=self.floating_day_count,
                )
            )
            prev_date = payment_date

        return cashflows

    def payoff(
        self,
        yield_curve: YieldCurve,
        floating_rates: dict[date, float] | None = None,
    ) -> float:
        """Calculate swap payoff (PV) using yield curve.

        Args:
            yield_curve: Yield curve for discounting and forward rates.
            floating_rates: Optional dict of floating rates by reset date.
                          If None, uses forward rates from yield curve.

        Returns:
            Present value of swap (positive = value to payer, negative = value to receiver).
        """
        fixed_cashflows = self.get_fixed_leg_cashflows()
        floating_cashflows = self.get_floating_leg_cashflows()

        # Fixed leg PV
        fixed_pv = 0.0
        for cf in fixed_cashflows:
            tau = year_fraction(
                self._get_prev_date(cf.payment_date, fixed_cashflows),
                cf.payment_date,
                cf.day_count,
            )
            df = yield_curve.discount_factor(cf.payment_date)
            fixed_pv += cf.notional * cf.rate * tau * df

        # Floating leg PV
        floating_pv = 0.0
        for cf in floating_cashflows:
            if cf.reset_date is None:
                continue

            prev_date = self._get_prev_date(cf.payment_date, floating_cashflows)

            # Get floating rate
            if floating_rates is not None and cf.reset_date in floating_rates:
                float_rate = floating_rates[cf.reset_date]
            else:
                # Use forward rate from yield curve
                float_rate = yield_curve.forward_rate(prev_date, cf.payment_date)

            tau = year_fraction(prev_date, cf.payment_date, cf.day_count)
            df = yield_curve.discount_factor(cf.payment_date)
            floating_pv += cf.notional * float_rate * tau * df

        # Swap value: floating - fixed for payer, fixed - floating for receiver
        if self.swap_type == "payer":
            return floating_pv - fixed_pv
        else:
            return fixed_pv - floating_pv

    def payoff_mc(
        self,
        rates: np.ndarray,
        times: np.ndarray,
        yield_curve: YieldCurve,
    ) -> float:
        """Calculate swap payoff for Monte Carlo path.

        Args:
            rates: Simulated rates [n_times] (short rates or forward rates).
            times: Time points [n_times] (years from valuation_date).
            yield_curve: Yield curve for discounting.

        Returns:
            Payoff value for this path.
        """
        from datetime import timedelta

        fixed_cashflows = self.get_fixed_leg_cashflows()
        floating_cashflows = self.get_floating_leg_cashflows()

        # Convert times to dates
        val_date = self.valuation_date
        time_to_date_map = {}
        for t, rate in zip(times, rates):
            days = int(t * 365.0)
            d = val_date + timedelta(days=days)
            time_to_date_map[d] = rate

        # Fixed leg PV
        fixed_pv = 0.0
        for cf in fixed_cashflows:
            prev_date = self._get_prev_date(cf.payment_date, fixed_cashflows)
            tau = year_fraction(prev_date, cf.payment_date, cf.day_count)
            df = yield_curve.discount_factor(cf.payment_date)
            fixed_pv += cf.notional * cf.rate * tau * df

        # Floating leg PV (use simulated rates)
        floating_pv = 0.0
        for cf in floating_cashflows:
            if cf.reset_date is None:
                continue

            prev_date = self._get_prev_date(cf.payment_date, floating_cashflows)
            tau = year_fraction(prev_date, cf.payment_date, cf.day_count)

            # Find closest simulated rate
            float_rate = self._get_rate_at_date(cf.reset_date, time_to_date_map, rates, times)
            df = yield_curve.discount_factor(cf.payment_date)
            floating_pv += cf.notional * float_rate * tau * df

        # Swap value
        if self.swap_type == "payer":
            return floating_pv - fixed_pv
        else:
            return fixed_pv - floating_pv

    def _get_prev_date(self, payment_date: date, cashflows: list[Cashflow]) -> date:
        """Get previous date for accrual period."""
        for cf in cashflows:
            if cf.payment_date == payment_date:
                idx = cashflows.index(cf)
                if idx > 0:
                    return cashflows[idx - 1].payment_date
                return self.start_date
        return self.start_date

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

