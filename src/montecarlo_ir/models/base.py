"""Base interfaces for interest rate models.

Defines the standard, model-agnostic interface that all interest rate models
in this library must implement. This allows pricers and the Monte Carlo engine
to work with any model in a uniform way.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import numpy as np

from montecarlo_ir.market_data.yield_curve import YieldCurve


class InterestRateModel(Protocol):
    """Standardized interface for all interest rate models.

    Implementations may be short-rate models, forward-rate models, or
    multi-factor term-structure models, but they must expose a common
    simulation and discounting interface so that pricers can remain
    model-agnostic.
    """

    yield_curve: YieldCurve

    def simulate_path(
        self,
        times: np.ndarray,
        random_shocks: np.ndarray | None = None,
    ) -> np.ndarray:
        """Simulate an interest rate (or state) path.

        Args:
            times: Time points for simulation (years from valuation_date),
                shape [n_times].
            random_shocks: Optional random shocks. The expected shape depends
                on the model implementation (e.g. [n_times-1] for 1-factor
                short-rate models, [n_times-1, n_factors] for multi-factor
                models, [n_times-1, n_rates] for LMM).

        Returns:
            State path with shape:
                - [n_times] for 1-factor short-rate models
                - [n_times, n_factors] for multi-factor short-rate models
                - [n_times, n_rates] for forward-rate models (e.g. LMM)
        """

    def discount_factor(
        self,
        t: float,
        T: float,
        state: float | np.ndarray,
    ) -> float:
        """Calculate discount factor from time t to T given current state.

        Args:
            t: Current time (years from valuation_date).
            T: Future time (years from valuation_date).
            state: Current model state at time t. For short-rate models this
                is typically a scalar short rate; for multi-factor models
                it is a state vector; for forward-rate models it may be a
                vector of current forward rates.

        Returns:
            Discount factor D(t, T).
        """

    def bond_price(
        self,
        t: float,
        T: float,
        state: float | np.ndarray,
    ) -> float:
        """Calculate zero-coupon bond price P(t, T) given current state.

        Models that do not have a natural notion of a single short rate
        (e.g. some forward-rate models) may implement this via discount
        factors or raise NotImplementedError where not applicable.
        """


@dataclass(frozen=True)
class ModelPath:
    """Container for simulated model paths.

    This is a light-weight structure that can be used in higher-level
    utilities if needed, but is not required by the core engine.
    """

    times: np.ndarray
    states: np.ndarray


