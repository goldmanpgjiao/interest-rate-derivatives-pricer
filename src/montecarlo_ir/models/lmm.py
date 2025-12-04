"""LIBOR Market Model (LMM) for forward rate simulation.

Implements the LIBOR Market Model for simulating forward LIBOR rates with
drift adjustments and correlation structure.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from typing import Literal

import numpy as np

from montecarlo_ir.market_data.yield_curve import YieldCurve
from montecarlo_ir.models.base import InterestRateModel  # noqa: F401 - Protocol for type checking
from montecarlo_ir.utils.date_helpers import DayCountConvention, year_fraction

DiscretizationScheme = Literal["euler", "log_euler"]
NumeraireMeasure = Literal["spot", "terminal"]


@dataclass(frozen=True)
class LIBORMarketModel:
    """LIBOR Market Model for forward rate simulation.

    The model simulates forward LIBOR rates L_i(t) with SDE:
        dL_i(t) = μ_i(t) * L_i(t) * dt + σ_i(t) * L_i(t) * dW_i(t)

    where:
        - μ_i(t): Drift term (depends on numeraire measure)
        - σ_i(t): Volatility (time-dependent)
        - dW_i(t): Correlated Wiener processes

    Attributes:
        yield_curve: Reference yield curve for initial forward rates.
        tenor_structure: Tenor dates for forward rates (T_0, T_1, ..., T_N).
        volatilities: Volatility structure σ_i(t) for each forward rate.
        correlation_matrix: Correlation matrix for forward rate shocks.
        scheme: Discretization scheme ('euler' or 'log_euler').
        measure: Numeraire measure ('spot' or 'terminal').
        day_count: Day count convention for time calculations.
    """

    yield_curve: YieldCurve
    tenor_structure: tuple[date, ...]  # T_0, T_1, ..., T_N
    volatilities: tuple[float, ...] | tuple[tuple[float, ...], ...]  # σ_i or σ_i(t)
    correlation_matrix: tuple[tuple[float, ...], ...] | None = None
    scheme: DiscretizationScheme = "log_euler"
    measure: NumeraireMeasure = "spot"
    day_count: DayCountConvention = DayCountConvention.ACT_365

    def __post_init__(self) -> None:
        """Validate model parameters."""
        if len(self.tenor_structure) < 2:
            raise ValueError("tenor_structure must have at least 2 dates.")
        if len(self.tenor_structure) != len(self.volatilities) + 1:
            raise ValueError(
                f"volatilities must have length {len(self.tenor_structure) - 1} "
                f"(one per forward rate), got {len(self.volatilities)}."
            )

        # Validate volatilities are positive
        for i, vol in enumerate(self.volatilities):
            if isinstance(vol, (list, tuple)):
                if any(v < 0.0 for v in vol):
                    raise ValueError(f"Volatility at index {i} must be non-negative.")
            else:
                if vol < 0.0:
                    raise ValueError(f"Volatility at index {i} must be non-negative.")

        # Validate correlation matrix if provided
        if self.correlation_matrix is not None:
            n_rates = len(self.tenor_structure) - 1
            if len(self.correlation_matrix) != n_rates:
                raise ValueError(
                    f"correlation_matrix must have {n_rates} rows, "
                    f"got {len(self.correlation_matrix)}."
                )
            for i, row in enumerate(self.correlation_matrix):
                if len(row) != n_rates:
                    raise ValueError(
                        f"correlation_matrix row {i} must have {n_rates} columns, "
                        f"got {len(row)}."
                    )
                # Check symmetry and diagonal
                for j, corr in enumerate(row):
                    if i == j and abs(corr - 1.0) > 1e-10:
                        raise ValueError(f"correlation_matrix[{i}][{j}] must be 1.0.")
                    if i != j and abs(corr - self.correlation_matrix[j][i]) > 1e-10:
                        raise ValueError("correlation_matrix must be symmetric.")

    def simulate_path(
        self, times: list[float] | np.ndarray, random_shocks: np.ndarray | None = None
    ) -> np.ndarray:
        """Simulate forward LIBOR rates (InterestRateModel protocol).

        Args:
            times: Array of time points (years from valuation_date).
            random_shocks: Optional array of random shocks (standard normal, shape: [n_times-1, n_rates]).
                         If None, generates random shocks.

        Returns:
            Array of forward rates at each time point, shape [n_times, n_rates].
        """
        return self.simulate_forward_rates(times, random_shocks)

    def simulate_forward_rates(
        self, times: list[float] | np.ndarray, random_shocks: np.ndarray | None = None
    ) -> np.ndarray:
        """Simulate forward LIBOR rates.

        Args:
            times: Array of time points (years from valuation_date).
            random_shocks: Optional array of random shocks (standard normal, shape: [n_times-1, n_rates]).
                         If None, generates random shocks.

        Returns:
            Array of forward rates at each time point, shape [n_times, n_rates].
        """
        times_array = np.asarray(times, dtype=float)
        if len(times_array) == 0:
            return np.array([]).reshape(0, len(self.tenor_structure) - 1)

        t0 = times_array[0]
        if t0 < 0.0:
            raise ValueError("All times must be non-negative.")

        # Initial forward rates from yield curve
        initial_rates = self._initial_forward_rates()

        if self.scheme == "log_euler":
            return self._simulate_log_euler(times_array, initial_rates, random_shocks)
        else:
            return self._simulate_euler(times_array, initial_rates, random_shocks)

    def discount_factor(
        self, t: float, T: float, state: float | np.ndarray | None = None, *, forward_rates: np.ndarray | None = None
    ) -> float:
        """Calculate discount factor from time t to T using forward rates.

        Supports both protocol interface (state parameter) and legacy interface (forward_rates parameter).

        Args:
            t: Current time (years from valuation_date).
            T: Future time (years from valuation_date).
            state: Current state (forward rates) at time t. Shape [n_rates].
            forward_rates: Legacy parameter - current forward rates at time t (deprecated, use state instead).

        Returns:
            Discount factor D(t, T).
        """
        if T < t:
            raise ValueError("T must be >= t.")

        # Handle both new (state) and legacy (forward_rates) interfaces
        if state is not None:
            # New interface: state should be forward rates array
            if isinstance(state, np.ndarray):
                rates = state
            else:
                # If scalar, convert to array (though LMM expects array)
                rates = np.array([float(state)])
        elif forward_rates is not None:
            # Legacy interface
            rates = np.asarray(forward_rates)
        else:
            raise ValueError("Either 'state' or 'forward_rates' must be provided.")

        if len(rates) != len(self.tenor_structure) - 1:
            raise ValueError(
                f"forward_rates/state must have length {len(self.tenor_structure) - 1}, "
                f"got {len(rates)}."
            )

        # Find relevant tenors
        val_date = self.yield_curve.valuation_date
        t_date = self._time_to_date(t)
        T_date = self._time_to_date(T)

        # Use forward rates to build discount factors
        df = 1.0
        for i in range(len(self.tenor_structure) - 1):
            T_i = self.tenor_structure[i]
            T_i_plus = self.tenor_structure[i + 1]

            if T_i <= t_date:
                continue
            if T_i >= T_date:
                break

            # Use forward rate for this period
            tau = year_fraction(T_i, T_i_plus, self.day_count)
            df *= 1.0 / (1.0 + rates[i] * tau)

        return df

    def bond_price(
        self, t: float, T: float, state: float | np.ndarray | None = None, *, forward_rates: np.ndarray | None = None
    ) -> float:
        """Calculate bond price using forward rates (InterestRateModel protocol).

        For LMM, bond price is calculated via discount factors from forward rates.

        Args:
            t: Current time (years from valuation_date).
            T: Maturity time (years from valuation_date).
            state: Current state (forward rates) at time t.
            forward_rates: Legacy parameter (deprecated, use state instead).

        Returns:
            Bond price P(t, T) = D(t, T).
        """
        return self.discount_factor(t, T, state=state, forward_rates=forward_rates)

    # -------- Internal methods --------

    def _initial_forward_rates(self) -> np.ndarray:
        """Get initial forward rates from yield curve."""
        val_date = self.yield_curve.valuation_date
        rates = np.zeros(len(self.tenor_structure) - 1)

        for i in range(len(self.tenor_structure) - 1):
            T_i = self.tenor_structure[i]
            T_i_plus = self.tenor_structure[i + 1]

            if T_i < val_date:
                # Use next available forward
                continue

            # Calculate forward rate from yield curve
            fwd = self.yield_curve.forward_rate(T_i, T_i_plus)
            rates[i] = fwd

        return rates

    def _simulate_log_euler(
        self, times: np.ndarray, initial_rates: np.ndarray, random_shocks: np.ndarray | None
    ) -> np.ndarray:
        """Log-Euler discretization scheme."""
        n_times = len(times)
        n_rates = len(initial_rates)
        rates = np.zeros((n_times, n_rates))
        rates[0] = initial_rates

        if random_shocks is None:
            random_shocks = self._generate_shocks(n_times - 1, n_rates)
        else:
            if random_shocks.shape != (n_times - 1, n_rates):
                raise ValueError(
                    f"random_shocks must have shape ({n_times - 1}, {n_rates}), "
                    f"got {random_shocks.shape}."
                )

        for i in range(1, n_times):
            dt = times[i] - times[i - 1]
            if dt <= 0.0:
                raise ValueError("Times must be strictly increasing.")

            # Get volatilities at current time
            vols = self._get_volatilities(times[i - 1])

            # Calculate drift
            drift = self._calculate_drift(times[i - 1], rates[i - 1])

            # Log-Euler: d(log L) = (μ - 0.5*σ²)dt + σ*dW
            log_rates = np.log(np.maximum(rates[i - 1], 1e-10))  # Avoid log(0)
            log_rates += (drift - 0.5 * vols**2) * dt
            log_rates += vols * math.sqrt(dt) * random_shocks[i - 1]

            rates[i] = np.exp(log_rates)

        return rates

    def _simulate_euler(
        self, times: np.ndarray, initial_rates: np.ndarray, random_shocks: np.ndarray | None
    ) -> np.ndarray:
        """Euler discretization scheme."""
        n_times = len(times)
        n_rates = len(initial_rates)
        rates = np.zeros((n_times, n_rates))
        rates[0] = initial_rates

        if random_shocks is None:
            random_shocks = self._generate_shocks(n_times - 1, n_rates)
        else:
            if random_shocks.shape != (n_times - 1, n_rates):
                raise ValueError(
                    f"random_shocks must have shape ({n_times - 1}, {n_rates}), "
                    f"got {random_shocks.shape}."
                )

        for i in range(1, n_times):
            dt = times[i] - times[i - 1]
            if dt <= 0.0:
                raise ValueError("Times must be strictly increasing.")

            # Get volatilities at current time
            vols = self._get_volatilities(times[i - 1])

            # Calculate drift
            drift = self._calculate_drift(times[i - 1], rates[i - 1])

            # Euler: dL = μ*L*dt + σ*L*dW
            rates[i] = rates[i - 1] + drift * rates[i - 1] * dt
            rates[i] += vols * rates[i - 1] * math.sqrt(dt) * random_shocks[i - 1]
            rates[i] = np.maximum(rates[i], 1e-10)  # Keep positive

        return rates

    def _calculate_drift(self, t: float, forward_rates: np.ndarray) -> np.ndarray:
        """Calculate drift terms for forward rates."""
        n_rates = len(forward_rates)
        drift = np.zeros(n_rates)

        if self.measure == "spot":
            # Spot LIBOR measure: drift depends on forward rates up to next reset
            for i in range(n_rates):
                T_i = self.tenor_structure[i]
                T_i_plus = self.tenor_structure[i + 1]
                val_date = self.yield_curve.valuation_date
                t_date = self._time_to_date(t)

                if T_i <= t_date:
                    continue

                # Drift: sum over j where T_j < T_{i+1}
                tau_i = year_fraction(T_i, T_i_plus, self.day_count)
                for j in range(i + 1):
                    if j >= len(forward_rates):
                        break
                    T_j = self.tenor_structure[j]
                    T_j_plus = self.tenor_structure[j + 1]
                    if T_j_plus > t_date:
                        tau_j = year_fraction(T_j, T_j_plus, self.day_count)
                        vol_i = self._get_volatility(i, t)
                        vol_j = self._get_volatility(j, t)
                        corr = self._get_correlation(i, j)
                        drift[i] += (
                            (tau_j * forward_rates[j] * vol_i * vol_j * corr)
                            / (1.0 + tau_j * forward_rates[j])
                        )

        else:  # terminal measure
            # Terminal measure: drift is zero for last rate, negative for others
            for i in range(n_rates - 1):
                T_i = self.tenor_structure[i]
                T_i_plus = self.tenor_structure[i + 1]
                val_date = self.yield_curve.valuation_date
                t_date = self._time_to_date(t)

                if T_i <= t_date:
                    continue

                tau_i = year_fraction(T_i, T_i_plus, self.day_count)
                vol_i = self._get_volatility(i, t)

                # Sum over j > i
                for j in range(i + 1, n_rates):
                    T_j = self.tenor_structure[j]
                    T_j_plus = self.tenor_structure[j + 1]
                    if T_j_plus > t_date:
                        tau_j = year_fraction(T_j, T_j_plus, self.day_count)
                        vol_j = self._get_volatility(j, t)
                        corr = self._get_correlation(i, j)
                        drift[i] -= (
                            (tau_j * forward_rates[j] * vol_i * vol_j * corr)
                            / (1.0 + tau_j * forward_rates[j])
                        )

        return drift

    def _get_volatilities(self, t: float) -> np.ndarray:
        """Get volatility vector at time t."""
        n_rates = len(self.tenor_structure) - 1
        vols = np.zeros(n_rates)

        for i in range(n_rates):
            vols[i] = self._get_volatility(i, t)

        return vols

    def _get_volatility(self, i: int, t: float) -> float:
        """Get volatility for forward rate i at time t."""
        vol = self.volatilities[i]
        if isinstance(vol, (list, tuple)):
            # Time-dependent volatility - simple interpolation
            # For now, use first value (can be enhanced)
            return float(vol[0])
        return float(vol)

    def _get_correlation(self, i: int, j: int) -> float:
        """Get correlation between forward rates i and j."""
        if self.correlation_matrix is None:
            # Default: identity (uncorrelated)
            return 1.0 if i == j else 0.0
        return float(self.correlation_matrix[i][j])

    def _generate_shocks(self, n_steps: int, n_rates: int) -> np.ndarray:
        """Generate correlated random shocks."""
        if self.correlation_matrix is None:
            # Uncorrelated
            return np.random.standard_normal((n_steps, n_rates))

        # Generate correlated shocks using Cholesky decomposition
        corr_matrix = np.array(self.correlation_matrix)
        try:
            L = np.linalg.cholesky(corr_matrix)
        except np.linalg.LinAlgError:
            # Fallback to identity if not positive definite
            L = np.eye(n_rates)

        # Generate independent shocks and apply correlation
        independent = np.random.standard_normal((n_steps, n_rates))
        return independent @ L.T

    def _time_to_date(self, t: float) -> date:
        """Convert time (years) to date using day count convention."""
        val_date = self.yield_curve.valuation_date
        from datetime import timedelta

        if self.day_count == DayCountConvention.ACT_365:
            days = int(t * 365.0)
        elif self.day_count == DayCountConvention.ACT_360:
            days = int(t * 360.0)
        else:
            days = int(t * 365.0)

        return val_date + timedelta(days=days)

