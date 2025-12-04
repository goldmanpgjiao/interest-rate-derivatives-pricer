"""Product pricers for interest rate derivatives.

Pricers that connect products to the Monte Carlo engine for pricing.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import numpy as np

from montecarlo_ir.models.base import InterestRateModel
from montecarlo_ir.pricing.mc_engine import MonteCarloEngine, MonteCarloResult, align_simulation_grid
from montecarlo_ir.products.cap_floor import CapFloor
from montecarlo_ir.products.european_swaption import EuropeanSwaption
from montecarlo_ir.products.interest_rate_swap import InterestRateSwap
from montecarlo_ir.utils.date_helpers import DayCountConvention


@dataclass(frozen=True)
class SwapPricer:
    """Pricer for Interest Rate Swaps.

    Attributes:
        model: Interest rate model (any model implementing InterestRateModel protocol).
        num_paths: Number of Monte Carlo paths.
        seed: Random seed for reproducibility.
        use_antithetic: Whether to use antithetic variates.
    """

    model: InterestRateModel
    num_paths: int = 10000
    seed: int | None = None
    use_antithetic: bool = False

    def price(self, swap: InterestRateSwap) -> MonteCarloResult:
        """Price an interest rate swap using Monte Carlo.

        Args:
            swap: InterestRateSwap to price.

        Returns:
            MonteCarloResult with price and standard error.
        """
        # Get important dates for simulation grid
        fixed_cfs = swap.get_fixed_leg_cashflows()
        floating_cfs = swap.get_floating_leg_cashflows()

        important_dates = [swap.valuation_date]
        for cf in fixed_cfs:
            important_dates.append(cf.payment_date)
        for cf in floating_cfs:
            important_dates.append(cf.reset_date)
            important_dates.append(cf.payment_date)

        # Align simulation grid
        times = align_simulation_grid(
            swap.valuation_date,
            important_dates,
            max_step_size=0.25,
        )

        # Create MC engine
        engine = MonteCarloEngine(
            model=self.model,
            num_paths=self.num_paths,
            seed=self.seed,
            use_antithetic=self.use_antithetic,
        )

        # Define payoff function
        def payoff_fn(rates: np.ndarray, sim_times: np.ndarray) -> float:
            return swap.payoff_mc(rates, sim_times, self.model.yield_curve)

        # Price
        return engine.price(
            payoff_fn=payoff_fn,
            simulation_times=times,
            valuation_date=swap.valuation_date,
        )


@dataclass(frozen=True)
class CapFloorPricer:
    """Pricer for Caps and Floors.

    Attributes:
        model: Interest rate model (any model implementing InterestRateModel protocol).
        num_paths: Number of Monte Carlo paths.
        seed: Random seed for reproducibility.
        use_antithetic: Whether to use antithetic variates.
    """

    model: InterestRateModel
    num_paths: int = 10000
    seed: int | None = None
    use_antithetic: bool = False

    def price(self, cap_floor: CapFloor) -> MonteCarloResult:
        """Price a cap or floor using Monte Carlo.

        Args:
            cap_floor: CapFloor to price.

        Returns:
            MonteCarloResult with price and standard error.
        """
        # Get important dates for simulation grid
        caplets = cap_floor.get_caplets_floorlets()

        important_dates = [cap_floor.valuation_date]
        for caplet in caplets:
            important_dates.append(caplet.reset_date)
            important_dates.append(caplet.payment_date)

        # Align simulation grid
        times = align_simulation_grid(
            cap_floor.valuation_date,
            important_dates,
            max_step_size=0.25,
        )

        # Create MC engine
        engine = MonteCarloEngine(
            model=self.model,
            num_paths=self.num_paths,
            seed=self.seed,
            use_antithetic=self.use_antithetic,
        )

        # Define payoff function
        def payoff_fn(rates: np.ndarray, sim_times: np.ndarray) -> float:
            return cap_floor.payoff_mc(rates, sim_times, self.model.yield_curve)

        # Price
        return engine.price(
            payoff_fn=payoff_fn,
            simulation_times=times,
            valuation_date=cap_floor.valuation_date,
        )


@dataclass(frozen=True)
class EuropeanSwaptionPricer:
    """Pricer for European Swaptions.

    Attributes:
        model: Interest rate model (any model implementing InterestRateModel protocol).
        num_paths: Number of Monte Carlo paths.
        seed: Random seed for reproducibility.
        use_antithetic: Whether to use antithetic variates.
    """

    model: InterestRateModel
    num_paths: int = 10000
    seed: int | None = None
    use_antithetic: bool = False

    def price(self, swaption: EuropeanSwaption) -> MonteCarloResult:
        """Price a European swaption using Monte Carlo.

        Args:
            swaption: EuropeanSwaption to price.

        Returns:
            MonteCarloResult with price and standard error.
        """
        # Get important dates for simulation grid
        underlying_swap = swaption.get_underlying_swap()
        fixed_cfs = underlying_swap.get_fixed_leg_cashflows()
        floating_cfs = underlying_swap.get_floating_leg_cashflows()

        important_dates = [
            swaption.valuation_date,
            swaption.expiry_date,
            swaption.swap_start_date,
        ]
        for cf in fixed_cfs:
            important_dates.append(cf.payment_date)
        for cf in floating_cfs:
            if cf.reset_date:
                important_dates.append(cf.reset_date)
            important_dates.append(cf.payment_date)

        # Align simulation grid
        times = align_simulation_grid(
            swaption.valuation_date,
            important_dates,
            max_step_size=0.25,
        )

        # Create MC engine
        engine = MonteCarloEngine(
            model=self.model,
            num_paths=self.num_paths,
            seed=self.seed,
            use_antithetic=self.use_antithetic,
        )

        # Define payoff function
        def payoff_fn(rates: np.ndarray, sim_times: np.ndarray) -> float:
            return swaption.payoff_mc(rates, sim_times, self.model.yield_curve)

        # Price
        return engine.price(
            payoff_fn=payoff_fn,
            simulation_times=times,
            valuation_date=swaption.valuation_date,
        )

