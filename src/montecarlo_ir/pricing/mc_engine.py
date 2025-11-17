"""Monte Carlo pricing engine.

Core engine for multi-path simulation and pricing of interest rate derivatives.
Supports grid alignment, antithetic variates, and path-based discounting.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Callable, Protocol

import numpy as np

from montecarlo_ir.market_data.yield_curve import YieldCurve
from montecarlo_ir.models.hull_white import HullWhite1F
from montecarlo_ir.models.lmm import LIBORMarketModel
from montecarlo_ir.utils.date_helpers import DayCountConvention, year_fraction


class InterestRateModel(Protocol):
    """Protocol for interest rate models."""

    yield_curve: YieldCurve

    def simulate_short_rate_path(
        self, times: list[float] | np.ndarray, random_shocks: np.ndarray | None = None
    ) -> np.ndarray:
        """Simulate short rate path."""
        ...

    def discount_factor(self, t: float, T: float, r_t: float) -> float:
        """Calculate discount factor."""
        ...


@dataclass(frozen=True)
class MonteCarloResult:
    """Result from Monte Carlo simulation.

    Attributes:
        price: Estimated price.
        standard_error: Standard error of the estimate.
        num_paths: Number of paths simulated.
        paths: Optional array of simulated paths (if requested).
    """

    price: float
    standard_error: float
    num_paths: int
    paths: np.ndarray | None = None


@dataclass(frozen=True)
class MonteCarloEngine:
    """Monte Carlo pricing engine for interest rate derivatives.

    The engine simulates multiple paths of interest rates and computes
    payoffs with proper discounting.

    Attributes:
        model: Interest rate model (HullWhite1F or LIBORMarketModel).
        num_paths: Number of Monte Carlo paths to simulate.
        seed: Random seed for reproducibility.
        use_antithetic: Whether to use antithetic variates.
        day_count: Day count convention for time calculations.
    """

    model: HullWhite1F | LIBORMarketModel
    num_paths: int = 10000
    seed: int | None = None
    use_antithetic: bool = False
    day_count: DayCountConvention = DayCountConvention.ACT_365

    def __post_init__(self) -> None:
        """Validate engine parameters."""
        if self.num_paths <= 0:
            raise ValueError("num_paths must be positive.")
        if self.seed is not None:
            np.random.seed(self.seed)

    def price(
        self,
        payoff_fn: Callable[[np.ndarray, np.ndarray], np.ndarray],
        simulation_times: list[float] | np.ndarray,
        valuation_date: date,
        return_paths: bool = False,
    ) -> MonteCarloResult:
        """Price a derivative using Monte Carlo simulation.

        Args:
            payoff_fn: Function that computes payoff for each path.
                     Signature: payoff_fn(rates, times) -> payoffs
                     - rates: Array of rates [n_paths, n_times] or [n_paths, n_times, n_rates]
                     - times: Array of time points [n_times]
                     - Returns: Array of payoffs [n_paths]
            simulation_times: Time points for simulation (years from valuation_date).
            valuation_date: Valuation date.
            return_paths: Whether to return simulated paths in result.

        Returns:
            MonteCarloResult with price, standard error, and optional paths.
        """
        times_array = np.asarray(simulation_times, dtype=float)
        if len(times_array) == 0:
            raise ValueError("simulation_times must not be empty.")

        # Determine number of paths (with antithetic)
        n_paths_base = self.num_paths
        if self.use_antithetic:
            n_paths_base = (self.num_paths + 1) // 2

        # Generate random shocks
        if isinstance(self.model, HullWhite1F):
            n_times = len(times_array)
            shocks = np.random.standard_normal((n_paths_base, n_times - 1))
        else:  # LIBORMarketModel
            n_times = len(times_array)
            n_rates = len(self.model.tenor_structure) - 1
            shocks = np.random.standard_normal((n_paths_base, n_times - 1, n_rates))

        # Apply antithetic if requested
        if self.use_antithetic:
            shocks = np.concatenate([shocks, -shocks], axis=0)
            # Trim to exact num_paths
            shocks = shocks[: self.num_paths]

        # Simulate paths
        all_paths = []
        payoffs = np.zeros(self.num_paths)

        for path_idx in range(self.num_paths):
            path_shocks = shocks[path_idx]
            path = self._simulate_path(times_array, path_shocks)
            all_paths.append(path)

            # Compute payoff
            path_payoff = payoff_fn(path, times_array)
            if np.isscalar(path_payoff):
                payoffs[path_idx] = path_payoff
            else:
                payoffs[path_idx] = float(path_payoff)

        # Calculate statistics
        price = np.mean(payoffs)
        std_err = np.std(payoffs, ddof=1) / np.sqrt(self.num_paths)

        paths_array = np.array(all_paths) if return_paths else None

        return MonteCarloResult(
            price=float(price),
            standard_error=float(std_err),
            num_paths=self.num_paths,
            paths=paths_array,
        )

    def _simulate_path(
        self, times: np.ndarray, shocks: np.ndarray
    ) -> np.ndarray:
        """Simulate a single path."""
        if isinstance(self.model, HullWhite1F):
            return self.model.simulate_short_rate_path(times, shocks)
        else:  # LIBORMarketModel
            return self.model.simulate_forward_rates(times, shocks)

    def compute_discount_factors(
        self, paths: np.ndarray, times: np.ndarray, valuation_date: date
    ) -> np.ndarray:
        """Compute discount factors for each path.

        Args:
            paths: Simulated paths [n_paths, n_times] or [n_paths, n_times, n_rates].
            times: Time points [n_times].
            valuation_date: Valuation date.

        Returns:
            Discount factors [n_paths, n_times].
        """
        n_paths, n_times = paths.shape[0], paths.shape[1]
        dfs = np.ones((n_paths, n_times))

        if isinstance(self.model, HullWhite1F):
            # Short rate model: integrate rates to get discount factors
            for path_idx in range(n_paths):
                rates = paths[path_idx]
                for t_idx in range(1, n_times):
                    t_prev = times[t_idx - 1]
                    t_curr = times[t_idx]
                    # Simple trapezoidal integration
                    dt = t_curr - t_prev
                    avg_rate = 0.5 * (rates[t_idx - 1] + rates[t_idx])
                    dfs[path_idx, t_idx] = dfs[path_idx, t_idx - 1] * np.exp(-avg_rate * dt)
        else:  # LIBORMarketModel
            # Forward rate model: use forward rates to build discount factors
            for path_idx in range(n_paths):
                forward_rates = paths[path_idx]  # [n_times, n_rates]
                for t_idx in range(n_times):
                    t = times[t_idx]
                    # Use yield curve for discounting (model discount factor needs rates)
                    dfs[path_idx, t_idx] = self.model.yield_curve.discount_factor(
                        self._time_to_date(t, valuation_date)
                    )

        return dfs

    def _time_to_date(self, t: float, val_date: date) -> date:
        """Convert time to date."""
        from datetime import timedelta

        if self.day_count == DayCountConvention.ACT_365:
            days = int(t * 365.0)
        elif self.day_count == DayCountConvention.ACT_360:
            days = int(t * 360.0)
        else:
            days = int(t * 365.0)

        return val_date + timedelta(days=days)


def align_simulation_grid(
    valuation_date: date,
    important_dates: list[date],
    min_step_size: float = 0.01,
    max_step_size: float = 0.25,
) -> list[float]:
    """Create simulation grid aligned with important dates.

    Args:
        valuation_date: Valuation date.
        important_dates: Dates that must be included in grid (reset, payment, exercise).
        min_step_size: Minimum time step in years.
        max_step_size: Maximum time step in years.

    Returns:
        Array of time points (years from valuation_date).
    """
    from montecarlo_ir.utils.date_helpers import DayCountConvention

    # Convert dates to times
    times_set = {0.0}  # Always include t=0
    for d in important_dates:
        if d >= valuation_date:
            t = year_fraction(valuation_date, d, DayCountConvention.ACT_365)
            times_set.add(t)

    times = sorted(times_set)

    # Add intermediate points if gaps are too large
    refined_times = [times[0]]
    for i in range(1, len(times)):
        dt = times[i] - refined_times[-1]
        if dt > max_step_size:
            # Add intermediate points
            n_steps = int(np.ceil(dt / max_step_size))
            step = dt / n_steps
            for j in range(1, n_steps):
                refined_times.append(refined_times[-1] + step)
        refined_times.append(times[i])

    return refined_times

