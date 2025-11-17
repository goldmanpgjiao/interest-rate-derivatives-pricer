"""European Swaption product.

European swaption implementation with payer/receiver options and settlement types.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal

import numpy as np

from montecarlo_ir.market_data.yield_curve import YieldCurve
from montecarlo_ir.products.interest_rate_swap import InterestRateSwap
from montecarlo_ir.utils.date_helpers import DayCountConvention, year_fraction

SwaptionType = Literal["payer", "receiver"]
SettlementType = Literal["physical", "cash"]


@dataclass(frozen=True)
class EuropeanSwaption:
    """European Swaption.

    An option to enter into an interest rate swap at a future date.

    Attributes:
        valuation_date: Valuation date.
        expiry_date: Option expiry date.
        swap_start_date: Start date of underlying swap (after expiry).
        swap_maturity_date: Maturity date of underlying swap.
        strike: Fixed rate of underlying swap (annual).
        notional: Notional amount.
        swaption_type: 'payer' (option to pay fixed) or 'receiver' (option to receive fixed).
        settlement_type: 'physical' (enter swap) or 'cash' (cash settlement).
        swap_fixed_frequency: Fixed leg payment frequency.
        swap_floating_frequency: Floating leg payment frequency.
        swap_fixed_day_count: Day count for fixed leg.
        swap_floating_day_count: Day count for floating leg.
    """

    valuation_date: date
    expiry_date: date
    swap_start_date: date
    swap_maturity_date: date
    strike: float
    notional: float
    swaption_type: SwaptionType = "payer"
    settlement_type: SettlementType = "physical"
    swap_fixed_frequency: str = "6M"
    swap_floating_frequency: str = "6M"
    swap_fixed_day_count: DayCountConvention = DayCountConvention.ACT_365
    swap_floating_day_count: DayCountConvention = DayCountConvention.ACT_360

    def __post_init__(self) -> None:
        """Validate swaption parameters."""
        if self.expiry_date <= self.valuation_date:
            raise ValueError("expiry_date must be after valuation_date.")
        if self.swap_start_date <= self.expiry_date:
            raise ValueError("swap_start_date must be after expiry_date.")
        if self.swap_maturity_date <= self.swap_start_date:
            raise ValueError("swap_maturity_date must be after swap_start_date.")
        if self.notional <= 0.0:
            raise ValueError("notional must be positive.")
        if self.strike < 0.0:
            raise ValueError("strike must be non-negative.")

    def get_underlying_swap(self) -> InterestRateSwap:
        """Get the underlying swap.

        Returns:
            InterestRateSwap representing the underlying swap.
        """
        # Determine swap type based on swaption type
        swap_type = "payer" if self.swaption_type == "payer" else "receiver"

        return InterestRateSwap(
            valuation_date=self.expiry_date,  # Swap valued at expiry
            start_date=self.swap_start_date,
            maturity_date=self.swap_maturity_date,
            fixed_rate=self.strike,
            notional=self.notional,
            swap_type=swap_type,
            fixed_frequency=self.swap_fixed_frequency,
            floating_frequency=self.swap_floating_frequency,
            fixed_day_count=self.swap_fixed_day_count,
            floating_day_count=self.swap_floating_day_count,
        )

    def payoff(
        self,
        yield_curve: YieldCurve,
        swap_value_at_expiry: float | None = None,
    ) -> float:
        """Calculate swaption payoff (PV) using yield curve.

        Args:
            yield_curve: Yield curve for discounting and swap valuation.
            swap_value_at_expiry: Optional swap value at expiry (if pre-calculated).

        Returns:
            Present value of swaption.
        """
        # Discount factor to expiry
        df_expiry = yield_curve.discount_factor(self.expiry_date)

        # Calculate swap value at expiry if not provided
        if swap_value_at_expiry is None:
            # Create underlying swap and calculate its value
            # Note: The swap is valued at expiry date, so we use forward rates
            underlying_swap = self.get_underlying_swap()
            try:
                swap_value_at_expiry = underlying_swap.payoff(yield_curve)
            except ValueError:
                # If swap can't be valued (e.g., dates too close), return 0
                swap_value_at_expiry = 0.0

        # Swaption payoff: max(0, swap_value) for payer, max(0, -swap_value) for receiver
        if self.swaption_type == "payer":
            payoff_at_expiry = max(0.0, swap_value_at_expiry)
        else:  # receiver
            payoff_at_expiry = max(0.0, -swap_value_at_expiry)

        # Discount to present
        return df_expiry * payoff_at_expiry

    def payoff_mc(
        self,
        rates: np.ndarray,
        times: np.ndarray,
        yield_curve: YieldCurve,
    ) -> float:
        """Calculate swaption payoff for Monte Carlo path.

        Args:
            rates: Simulated rates [n_times] (short rates or forward rates).
            times: Time points [n_times] (years from valuation_date).
            yield_curve: Yield curve for discounting.
        Returns:
            Payoff value for this path.
        """
        from datetime import timedelta

        # Find rate at expiry
        val_date = self.valuation_date
        expiry_time = year_fraction(val_date, self.expiry_date, yield_curve.day_count)

        # Get rate at expiry from simulated path
        rate_at_expiry = self._get_rate_at_time(expiry_time, rates, times)

        # For physical settlement, calculate swap value at expiry
        # For cash settlement, use simplified approximation
        if self.settlement_type == "physical":
            # Calculate swap value using simulated rate
            # Simplified: use rate at expiry to approximate swap value
            underlying_swap = self.get_underlying_swap()
            # Approximate swap value using forward rates
            swap_value = self._estimate_swap_value_at_expiry(
                rate_at_expiry, yield_curve, underlying_swap
            )
        else:  # cash settlement
            # Cash settlement: payoff based on swap value
            underlying_swap = self.get_underlying_swap()
            swap_value = self._estimate_swap_value_at_expiry(
                rate_at_expiry, yield_curve, underlying_swap
            )

        # Swaption payoff
        if self.swaption_type == "payer":
            payoff_at_expiry = max(0.0, swap_value)
        else:  # receiver
            payoff_at_expiry = max(0.0, -swap_value)

        # Discount to present
        df_expiry = yield_curve.discount_factor(self.expiry_date)
        return df_expiry * payoff_at_expiry

    def _estimate_swap_value_at_expiry(
        self,
        rate_at_expiry: float,
        yield_curve: YieldCurve,
        underlying_swap: InterestRateSwap,
    ) -> float:
        """Estimate swap value at expiry using rate at expiry."""
        # Simplified: use rate at expiry as forward rate
        # In practice, would use full yield curve at expiry
        floating_rates = {}
        floating_cfs = underlying_swap.get_floating_leg_cashflows()
        for cf in floating_cfs:
            if cf.reset_date:
                floating_rates[cf.reset_date] = rate_at_expiry

        return underlying_swap.payoff(yield_curve, floating_rates=floating_rates)

    def _get_rate_at_time(
        self, target_time: float, rates: np.ndarray, times: np.ndarray
    ) -> float:
        """Get rate at target time from simulated path."""
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

