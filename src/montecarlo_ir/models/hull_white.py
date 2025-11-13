"""Hull-White 1-Factor interest rate model.

Implements the Hull-White one-factor model for short rate simulation and bond pricing.
Supports both exact and Euler discretization schemes.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from typing import Literal

import numpy as np

from montecarlo_ir.market_data.yield_curve import YieldCurve
from montecarlo_ir.utils.date_helpers import DayCountConvention

DiscretizationScheme = Literal["exact", "euler"]


@dataclass(frozen=True)
class HullWhite1F:
    """Hull-White 1-Factor interest rate model.

    The model follows the SDE:
        dr(t) = (θ(t) - a*r(t))dt + σ*dW(t)

    where:
        - a: mean reversion speed (positive)
        - σ: volatility (positive)
        - θ(t): time-dependent drift calibrated to fit the yield curve
        - dW(t): Wiener process

    Attributes:
        yield_curve: Reference yield curve for calibration.
        mean_reversion: Mean reversion speed parameter (a).
        volatility: Volatility parameter (σ).
        scheme: Discretization scheme ('exact' or 'euler').
        day_count: Day count convention for time calculations.
    """

    yield_curve: YieldCurve
    mean_reversion: float  # a
    volatility: float  # σ
    scheme: DiscretizationScheme = "exact"
    day_count: DayCountConvention = DayCountConvention.ACT_365

    def __post_init__(self) -> None:
        """Validate model parameters."""
        if self.mean_reversion <= 0.0:
            raise ValueError("mean_reversion must be positive.")
        if self.volatility <= 0.0:
            raise ValueError("volatility must be positive.")

    def simulate_short_rate_path(
        self, times: list[float] | np.ndarray, random_shocks: np.ndarray | None = None
    ) -> np.ndarray:
        """Simulate a short rate path.

        Args:
            times: Array of time points (years from valuation_date).
            random_shocks: Optional array of random shocks (standard normal).
                         If None, generates random shocks.

        Returns:
            Array of short rates at each time point.
        """
        times_array = np.asarray(times, dtype=float)
        if len(times_array) == 0:
            return np.array([])

        t0 = times_array[0]
        if t0 < 0.0:
            raise ValueError("All times must be non-negative.")

        # Initial short rate from yield curve
        r0 = self._initial_short_rate(t0)

        if self.scheme == "exact":
            return self._simulate_exact(times_array, r0, random_shocks)
        else:
            return self._simulate_euler(times_array, r0, random_shocks)

    def bond_price(self, t: float, T: float, r_t: float) -> float:
        """Calculate zero-coupon bond price P(t, T) given short rate at time t.

        Args:
            t: Current time (years from valuation_date).
            T: Bond maturity time (years from valuation_date).
            r_t: Short rate at time t.

        Returns:
            Bond price P(t, T).
        """
        if T < t:
            raise ValueError("Bond maturity T must be >= current time t.")
        if t < 0.0 or T < 0.0:
            raise ValueError("Times must be non-negative.")

        tau = T - t
        if tau == 0.0:
            return 1.0

        a = self.mean_reversion
        sigma = self.volatility

        # Get market bond prices from yield curve
        t_date = self._time_to_date(t)
        T_date = self._time_to_date(T)

        P_market_t = self.yield_curve.discount_factor(t_date)
        P_market_T = self.yield_curve.discount_factor(T_date)

        # Calculate A(t, T) and B(t, T) for Hull-White
        B = (1.0 - math.exp(-a * tau)) / a
        A = (P_market_T / P_market_t) * math.exp(
            B * self._forward_rate_integral(t, T) - 0.5 * (sigma**2 / a**2) * (B - tau) * (1.0 - math.exp(-2.0 * a * t))
        )

        return A * math.exp(-B * r_t)

    def discount_factor(self, t: float, T: float, r_t: float) -> float:
        """Calculate discount factor from time t to T.

        Args:
            t: Current time (years from valuation_date).
            T: Future time (years from valuation_date).
            r_t: Short rate at time t.

        Returns:
            Discount factor D(t, T) = P(t, T).
        """
        return self.bond_price(t, T, r_t)

    # -------- Internal methods --------

    def _initial_short_rate(self, t: float) -> float:
        """Get initial short rate from yield curve."""
        t_date = self._time_to_date(t)
        return self.yield_curve.zero_rate(t_date)

    def _simulate_exact(
        self, times: np.ndarray, r0: float, random_shocks: np.ndarray | None
    ) -> np.ndarray:
        """Exact simulation using analytical solution."""
        n = len(times)
        if random_shocks is None:
            random_shocks = np.random.standard_normal(n - 1)
        else:
            if len(random_shocks) != n - 1:
                raise ValueError(f"random_shocks must have length {n - 1}.")

        a = self.mean_reversion
        sigma = self.volatility
        rates = np.zeros(n)
        rates[0] = r0

        for i in range(1, n):
            dt = times[i] - times[i - 1]
            if dt <= 0.0:
                raise ValueError("Times must be strictly increasing.")

            # Exact solution: r(t) = e^(-a*dt) * r(s) + integral_term + stochastic_term
            # Mean reversion term
            mean_rev_term = rates[i - 1] * math.exp(-a * dt)

            # Drift term (theta integral)
            drift_term = self._theta_integral(times[i - 1], times[i])

            # Stochastic term
            variance = (sigma**2 / (2.0 * a)) * (1.0 - math.exp(-2.0 * a * dt))
            stoch_term = math.sqrt(variance) * random_shocks[i - 1]

            rates[i] = mean_rev_term + drift_term + stoch_term

        return rates

    def _simulate_euler(
        self, times: np.ndarray, r0: float, random_shocks: np.ndarray | None
    ) -> np.ndarray:
        """Euler discretization scheme."""
        n = len(times)
        if random_shocks is None:
            random_shocks = np.random.standard_normal(n - 1)
        else:
            if len(random_shocks) != n - 1:
                raise ValueError(f"random_shocks must have length {n - 1}.")

        a = self.mean_reversion
        sigma = self.volatility
        rates = np.zeros(n)
        rates[0] = r0

        for i in range(1, n):
            dt = times[i] - times[i - 1]
            if dt <= 0.0:
                raise ValueError("Times must be strictly increasing.")

            # Euler scheme: dr = (theta - a*r)*dt + sigma*dW
            theta_t = self._theta(times[i - 1])
            drift = (theta_t - a * rates[i - 1]) * dt
            diffusion = sigma * math.sqrt(dt) * random_shocks[i - 1]

            rates[i] = rates[i - 1] + drift + diffusion

        return rates

    def _theta(self, t: float) -> float:
        """Calculate theta(t) to fit yield curve."""
        # Theta is derived from the requirement that the model fits the yield curve
        # θ(t) = ∂f/∂t + a*f(t) + (σ²/(2a))*(1 - exp(-2a*t))
        # where f(t) is the instantaneous forward rate

        t_date = self._time_to_date(t)

        # Use a minimum increment to avoid date equality issues
        eps = max(1e-4, t * 1e-6)  # Ensure eps is meaningful relative to t
        t1_date = self._time_to_date(t + eps)

        # Ensure dates are different
        if t1_date <= t_date:
            t1_date = self._time_to_date(t + max(0.01, t * 0.01))

        f_t = self.yield_curve.forward_rate(t_date, t1_date)

        # Approximate ∂f/∂t using finite difference
        t2_date = self._time_to_date(t + 2 * eps)
        if t2_date <= t1_date:
            t2_date = self._time_to_date(t + max(0.02, t * 0.02))
        f_t_plus = self.yield_curve.forward_rate(t1_date, t2_date)
        df_dt = (f_t_plus - f_t) / eps

        a = self.mean_reversion
        sigma = self.volatility

        return df_dt + a * f_t + (sigma**2 / (2.0 * a)) * (1.0 - math.exp(-2.0 * a * t))

    def _theta_integral(self, s: float, t: float) -> float:
        """Calculate integral of theta from s to t."""
        # For exact simulation, we need the integral of theta
        # This is approximated using numerical integration
        # For simplicity, use trapezoidal rule with a few points
        n_points = 10
        dt = (t - s) / n_points
        integral = 0.0

        for i in range(n_points + 1):
            tau = s + i * dt
            weight = 1.0 if (i == 0 or i == n_points) else 2.0
            integral += weight * self._theta(tau)

        return integral * dt / 2.0

    def _forward_rate_integral(self, t: float, T: float) -> float:
        """Calculate integral of forward rate from t to T."""
        # Approximate using yield curve forward rates
        t_date = self._time_to_date(t)
        T_date = self._time_to_date(T)

        # Use forward rate over the period
        fwd = self.yield_curve.forward_rate(t_date, T_date)
        return fwd * (T - t)

    def _time_to_date(self, t: float) -> date:
        """Convert time (years) to date using day count convention."""
        val_date = self.yield_curve.valuation_date
        # Use approximate conversion - for exact dates, we'd need to iterate
        # This is a simple approximation that works for most cases
        from datetime import timedelta

        if self.day_count == DayCountConvention.ACT_365:
            days = int(t * 365.0)
        elif self.day_count == DayCountConvention.ACT_360:
            days = int(t * 360.0)
        else:
            # Default to ACT/365
            days = int(t * 365.0)

        return val_date + timedelta(days=days)

