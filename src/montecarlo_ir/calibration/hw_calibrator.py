"""Hull-White model calibration.

Calibrates Hull-White 1F model parameters to market instruments (caplets/swaptions).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Callable

import numpy as np
from scipy.optimize import minimize

from montecarlo_ir.market_data.vol_surface import VolatilitySurface
from montecarlo_ir.market_data.yield_curve import YieldCurve
from montecarlo_ir.models.hull_white import HullWhite1F
from montecarlo_ir.pricing.mc_engine import MonteCarloEngine
from montecarlo_ir.utils.date_helpers import DayCountConvention, year_fraction


@dataclass(frozen=True)
class CalibrationInstrument:
    """Market instrument for calibration.

    Attributes:
        expiry_date: Option expiry date.
        maturity_date: Underlying instrument maturity date.
        strike: Strike rate.
        market_price: Market price of the instrument.
        instrument_type: Type of instrument ('caplet' or 'swaption').
    """

    expiry_date: date
    maturity_date: date
    strike: float
    market_price: float
    instrument_type: str  # 'caplet' or 'swaption'


@dataclass(frozen=True)
class CalibrationResult:
    """Result from model calibration.

    Attributes:
        mean_reversion: Calibrated mean reversion parameter.
        volatility: Calibrated volatility parameter.
        calibrated_model: Calibrated HullWhite1F model.
        calibration_error: Final calibration error (RMSE).
        num_iterations: Number of optimization iterations.
    """

    mean_reversion: float
    volatility: float
    calibrated_model: HullWhite1F
    calibration_error: float
    num_iterations: int


def calibrate_hull_white_to_instruments(
    yield_curve: YieldCurve,
    instruments: list[CalibrationInstrument],
    initial_mean_reversion: float = 0.1,
    initial_volatility: float = 0.01,
    *,
    day_count: DayCountConvention = DayCountConvention.ACT_365,
    num_paths: int = 5000,
    seed: int | None = None,
) -> CalibrationResult:
    """Calibrate Hull-White model to market instruments.

    Args:
        yield_curve: Reference yield curve.
        instruments: List of calibration instruments (caplets/swaptions).
        initial_mean_reversion: Initial guess for mean reversion.
        initial_volatility: Initial guess for volatility.
        day_count: Day count convention.
        num_paths: Number of MC paths for pricing.
        seed: Random seed for MC simulation.

    Returns:
        CalibrationResult with calibrated parameters and model.
    """
    if len(instruments) == 0:
        raise ValueError("At least one calibration instrument is required.")

    val_date = yield_curve.valuation_date

    # Objective function: minimize pricing error
    def objective(params: np.ndarray) -> float:
        a, sigma = params[0], params[1]
        if a <= 0.0 or sigma <= 0.0:
            return 1e10  # Penalty for invalid parameters

        try:
            model = HullWhite1F(
                yield_curve=yield_curve,
                mean_reversion=a,
                volatility=sigma,
                day_count=day_count,
            )
            engine = MonteCarloEngine(model=model, num_paths=num_paths, seed=seed)

            errors = []
            for inst in instruments:
                market_price = inst.market_price
                model_price = _price_instrument(engine, model, inst, val_date)
                error = (model_price - market_price) ** 2
                errors.append(error)

            return np.sqrt(np.mean(errors))  # RMSE
        except Exception:
            return 1e10  # Penalty for errors

    # Optimize
    initial_params = np.array([initial_mean_reversion, initial_volatility])
    bounds = [(1e-4, 1.0), (1e-4, 0.1)]  # Reasonable bounds

    result = minimize(
        objective,
        initial_params,
        method="L-BFGS-B",
        bounds=bounds,
        options={"maxiter": 100, "ftol": 1e-6},
    )

    calibrated_a = float(result.x[0])
    calibrated_sigma = float(result.x[1])

    calibrated_model = HullWhite1F(
        yield_curve=yield_curve,
        mean_reversion=calibrated_a,
        volatility=calibrated_sigma,
        day_count=day_count,
    )

    return CalibrationResult(
        mean_reversion=calibrated_a,
        volatility=calibrated_sigma,
        calibrated_model=calibrated_model,
        calibration_error=float(result.fun),
        num_iterations=int(result.nit),
    )


def calibrate_hull_white_to_vol_surface(
    yield_curve: YieldCurve,
    vol_surface: VolatilitySurface,
    caplet_strikes: list[float] | tuple[float, ...],
    *,
    day_count: DayCountConvention = DayCountConvention.ACT_365,
    num_paths: int = 5000,
    seed: int | None = None,
) -> CalibrationResult:
    """Calibrate Hull-White to caplet volatility surface.

    Converts volatility surface to implied prices and calibrates.

    Args:
        yield_curve: Reference yield curve.
        vol_surface: Caplet volatility surface.
        caplet_strikes: Strikes for caplets (one per expiry in surface).
        day_count: Day count convention.
        num_paths: Number of MC paths for pricing.
        seed: Random seed for MC simulation.

    Returns:
        CalibrationResult with calibrated parameters.
    """
    val_date = yield_curve.valuation_date
    expiry_times = vol_surface.expiry_times

    if len(caplet_strikes) != len(expiry_times):
        raise ValueError(
            f"caplet_strikes must have length {len(expiry_times)}, "
            f"got {len(caplet_strikes)}."
        )

    # Convert volatility surface to calibration instruments
    instruments = []
    for i, (expiry_time, strike) in enumerate(zip(expiry_times, caplet_strikes)):
        expiry_date = _time_to_date(expiry_time, val_date, day_count)
        # Assume 3M tenor for caplets
        maturity_date = _time_to_date(expiry_time + 0.25, val_date, day_count)

        # Get volatility from surface
        vol = vol_surface.volatility_at_times(expiry_time, 0.25)

        # Approximate market price using Black formula (simplified)
        # This is a placeholder - in practice, you'd use actual market prices
        market_price = _black_caplet_price(
            yield_curve, expiry_date, maturity_date, strike, vol, day_count
        )

        instruments.append(
            CalibrationInstrument(
                expiry_date=expiry_date,
                maturity_date=maturity_date,
                strike=strike,
                market_price=market_price,
                instrument_type="caplet",
            )
        )

    return calibrate_hull_white_to_instruments(
        yield_curve=yield_curve,
        instruments=instruments,
        day_count=day_count,
        num_paths=num_paths,
        seed=seed,
    )


# -------- Internal helpers --------


def _price_instrument(
    engine: MonteCarloEngine,
    model: HullWhite1F,
    instrument: CalibrationInstrument,
    val_date: date,
) -> float:
    """Price a calibration instrument using MC."""
    if instrument.instrument_type == "caplet":
        return _price_caplet_mc(engine, model, instrument, val_date)
    elif instrument.instrument_type == "swaption":
        return _price_swaption_mc(engine, model, instrument, val_date)
    else:
        raise ValueError(f"Unknown instrument type: {instrument.instrument_type}")


def _price_caplet_mc(
    engine: MonteCarloEngine,
    model: HullWhite1F,
    instrument: CalibrationInstrument,
    val_date: date,
) -> float:
    """Price caplet using Monte Carlo."""
    expiry_time = year_fraction(val_date, instrument.expiry_date, model.day_count)
    maturity_time = year_fraction(val_date, instrument.maturity_date, model.day_count)

    if expiry_time <= 0.0:
        return 0.0  # Expired

    # Simulation times
    times = [0.0, expiry_time, maturity_time]

    def payoff_fn(rates: np.ndarray, sim_times: np.ndarray) -> float:
        # Caplet payoff: max(0, L(T) - K) * tau * DF
        # Simplified: use rate at expiry
        rate_at_expiry = rates[1] if len(rates) > 1 else rates[0]
        tau = maturity_time - expiry_time
        payoff = max(0.0, rate_at_expiry - instrument.strike) * tau
        return payoff

    result = engine.price(
        payoff_fn=payoff_fn,
        simulation_times=times,
        valuation_date=val_date,
    )

    return result.price


def _price_swaption_mc(
    engine: MonteCarloEngine,
    model: HullWhite1F,
    instrument: CalibrationInstrument,
    val_date: date,
) -> float:
    """Price swaption using Monte Carlo (simplified)."""
    expiry_time = year_fraction(val_date, instrument.expiry_date, model.day_count)

    if expiry_time <= 0.0:
        return 0.0  # Expired

    # Simplified swaption pricing
    times = [0.0, expiry_time]

    def payoff_fn(rates: np.ndarray, sim_times: np.ndarray) -> float:
        # Simplified swaption payoff
        rate_at_expiry = rates[1] if len(rates) > 1 else rates[0]
        payoff = max(0.0, rate_at_expiry - instrument.strike)
        return payoff

    result = engine.price(
        payoff_fn=payoff_fn,
        simulation_times=times,
        valuation_date=val_date,
    )

    return result.price


def _black_caplet_price(
    yield_curve: YieldCurve,
    expiry_date: date,
    maturity_date: date,
    strike: float,
    volatility: float,
    day_count: DayCountConvention,
) -> float:
    """Approximate caplet price using Black formula."""
    import math

    val_date = yield_curve.valuation_date
    forward = yield_curve.forward_rate(expiry_date, maturity_date)
    tau = year_fraction(expiry_date, maturity_date, day_count)
    t_expiry = year_fraction(val_date, expiry_date, day_count)

    if t_expiry <= 0.0:
        return 0.0

    # Black formula
    d1 = (math.log(forward / strike) + 0.5 * volatility**2 * t_expiry) / (
        volatility * math.sqrt(t_expiry)
    )
    d2 = d1 - volatility * math.sqrt(t_expiry)

    # Normal CDF approximation
    def norm_cdf(x: float) -> float:
        return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

    price = tau * yield_curve.discount_factor(maturity_date) * (
        forward * norm_cdf(d1) - strike * norm_cdf(d2)
    )

    return max(0.0, price)


def _time_to_date(t: float, val_date: date, day_count: DayCountConvention) -> date:
    """Convert time to date."""
    from datetime import timedelta

    if day_count == DayCountConvention.ACT_365:
        days = int(t * 365.0)
    elif day_count == DayCountConvention.ACT_360:
        days = int(t * 360.0)
    else:
        days = int(t * 365.0)

    return val_date + timedelta(days=days)

