# API Interface Quick Reference

Quick reference for public interfaces in `montecarlo_ir`.

---

## `montecarlo_ir.utils.date_helpers`

Date handling utilities for interest rate derivatives.

### Enums

**`DayCountConvention`**
- `ACT_360`, `ACT_365`, `ACT_ACT`, `ACT_365_25`, `THIRTY_360`

**`BusinessDayRule`**
- `FOLLOWING`, `MODIFIED_FOLLOWING`, `PRECEDING`, `MODIFIED_PRECEDING`, `NONE`

### Functions

**`days_between(start_date: date, end_date: date, convention: DayCountConvention = ACT_360) -> float`**
- Calculate year fraction between two dates
- Raises `ValueError` if `end_date < start_date`

**`is_business_day(d: date, calendar: list[date] | None = None) -> bool`**
- Check if date is a business day (excludes weekends and holidays)

**`adjust_business_day(d: date, rule: BusinessDayRule = FOLLOWING, calendar: list[date] | None = None) -> date`**
- Adjust date according to business day rule

**`add_months(d: date, months: int) -> date`**
- Add months to date (handles month-end edge cases)

**`add_years(d: date, years: int) -> date`**
- Add years to date (handles leap year edge cases)

**`generate_schedule(start_date: date, end_date: date, frequency: str = "6M", business_day_rule: BusinessDayRule = MODIFIED_FOLLOWING, calendar: list[date] | None = None) -> list[date]`**
- Generate date schedule between start and end dates
- Frequency format: `"1M"`, `"3M"`, `"6M"`, `"1Y"` (number + M/Y)
- Raises `ValueError` for invalid date order or unsupported frequency

**`year_fraction(start_date: date, end_date: date, convention: DayCountConvention | str = ACT_360) -> float`**
- Convenience function accepting enum or string convention
- String formats: `"ACT/360"`, `"ACT/365"`, `"ACT/ACT"`, `"ACT/365.25"`, `"30/360"`

### Quick Examples

```python
from datetime import date
from montecarlo_ir.utils.date_helpers import (
    days_between, DayCountConvention,
    generate_schedule, BusinessDayRule,
    adjust_business_day
)

# Day count
year_frac = days_between(date(2024, 1, 1), date(2024, 7, 1), DayCountConvention.ACT_360)

# Schedule generation
schedule = generate_schedule(date(2024, 1, 1), date(2026, 1, 1), frequency="6M")

# Business day adjustment
adjusted = adjust_business_day(date(2024, 1, 6), BusinessDayRule.FOLLOWING)  # Saturday -> Monday
```

---

## `montecarlo_ir.market_data.yield_curve`

Yield curve for discount factors, zero rates, and forward rates.

### Types

**`InterpolationMethod`**: `"linear_zero"` | `"log_linear_df"`  
**`CompoundingMethod`**: `"cont"` | `"simple"` | `"annual"`

### Class

**`YieldCurve`** (dataclass, frozen)
- `valuation_date: date`
- `pillar_dates: tuple[date, ...]`
- `pillar_zero_rates: tuple[float, ...]`
- `day_count: DayCountConvention = ACT_365`
- `interpolation: InterpolationMethod = "log_linear_df"`
- `compounding: CompoundingMethod = "cont"`

**Methods:**
- `discount_factor(target_date: date) -> float`
- `zero_rate(target_date: date) -> float`
- `forward_rate(start_date: date, end_date: date) -> float`

### Bootstrapping Functions

**`build_yield_curve_from_discount_factors(...) -> YieldCurve`**
- Create curve from discount factors

**`build_yield_curve_from_zero_rates(...) -> YieldCurve`**
- Create curve from zero rates

**`build_yield_curve_from_deposits_simple(...) -> YieldCurve`**
- Bootstrap from simple deposit rates

**`build_yield_curve_from_swaps(valuation_date, swap_maturities, par_swap_rates, swap_frequency="6M", ...) -> YieldCurve`**
- Bootstrap from par swap rates

### Quick Examples

```python
from datetime import date
from montecarlo_ir.market_data.yield_curve import (
    YieldCurve, build_yield_curve_from_swaps
)
from montecarlo_ir.utils.date_helpers import DayCountConvention

# Direct construction
curve = YieldCurve(
    valuation_date=date(2024, 1, 1),
    pillar_dates=(date(2025, 1, 1), date(2026, 1, 1)),
    pillar_zero_rates=(0.02, 0.025),
)

# Query rates
df = curve.discount_factor(date(2025, 6, 1))
zero = curve.zero_rate(date(2025, 6, 1))
fwd = curve.forward_rate(date(2025, 1, 1), date(2026, 1, 1))

# Bootstrap from swaps
curve = build_yield_curve_from_swaps(
    valuation_date=date(2024, 1, 1),
    swap_maturities=(date(2025, 1, 1), date(2026, 1, 1)),
    par_swap_rates=(0.02, 0.025),
    swap_frequency="6M",
)
```

---

## `montecarlo_ir.market_data.vol_surface`

Volatility surface for caplets and swaptions.

### Types

**`InterpolationMethod`**: `"linear"` | `"flat"`  
**`ExtrapolationMethod`**: `"flat"` | `"linear"`

### Class

**`VolatilitySurface`** (dataclass, frozen)
- `valuation_date: date`
- `expiry_times: tuple[float, ...]` (years from valuation)
- `tenor_times: tuple[float, ...]` (years)
- `volatility_matrix: tuple[tuple[float, ...], ...]` (expiry x tenor)
- `interpolation: InterpolationMethod = "linear"`
- `extrapolation: ExtrapolationMethod = "flat"`
- `day_count: DayCountConvention = ACT_365`

**Methods:**
- `volatility(expiry_date: date, tenor_years: float) -> float`
- `volatility_at_times(expiry_time: float, tenor_time: float) -> float`

### Helper Functions

**`build_volatility_surface_from_matrix(...) -> VolatilitySurface`**
- Build surface from expiry dates, tenor years, and volatility matrix

### Quick Examples

```python
from datetime import date
from montecarlo_ir.market_data.vol_surface import (
    VolatilitySurface, build_volatility_surface_from_matrix
)

# Direct construction
surface = VolatilitySurface(
    valuation_date=date(2024, 1, 1),
    expiry_times=(0.25, 0.5, 1.0),
    tenor_times=(1.0, 2.0, 5.0),
    volatility_matrix=((0.15, 0.16, 0.17), (0.16, 0.17, 0.18), (0.17, 0.18, 0.19)),
)

# Query volatility
vol = surface.volatility(date(2024, 4, 1), 1.0)  # Using dates
vol = surface.volatility_at_times(0.25, 1.0)  # Using times

# Build from matrix
surface = build_volatility_surface_from_matrix(
    valuation_date=date(2024, 1, 1),
    expiry_dates=(date(2024, 4, 1), date(2024, 7, 1)),
    tenor_years=(1.0, 2.0),
    volatility_matrix=((0.15, 0.16), (0.16, 0.17)),
)
```

---

## `montecarlo_ir.models.base`

Base interface for all interest rate models.

### Protocol

**`InterestRateModel`** (Protocol)
- `yield_curve: YieldCurve`
- `simulate_path(times: np.ndarray, random_shocks: np.ndarray | None = None) -> np.ndarray`
- `discount_factor(t: float, T: float, state: float | np.ndarray) -> float`
- `bond_price(t: float, T: float, state: float | np.ndarray) -> float`

All models (`HullWhite1F`, `LIBORMarketModel`, etc.) implement this protocol, enabling model-agnostic pricers.

### Quick Examples

```python
from montecarlo_ir.models.base import InterestRateModel
from montecarlo_ir.models.hull_white import HullWhite1F
from montecarlo_ir.pricing.product_pricers import SwapPricer

# Any model implementing InterestRateModel works with pricers
model: InterestRateModel = HullWhite1F(...)
pricer = SwapPricer(model=model, num_paths=10000)
```

---

## `montecarlo_ir.models.hull_white`

Hull-White 1-Factor interest rate model.

### Types

**`DiscretizationScheme`**: `"exact"` | `"euler"`

### Class

**`HullWhite1F`** (dataclass, frozen)
- `yield_curve: YieldCurve`
- `mean_reversion: float` (a, positive)
- `volatility: float` (σ, positive)
- `scheme: DiscretizationScheme = "exact"`
- `day_count: DayCountConvention = ACT_365`

**Methods:**
- `simulate_path(times: list[float] | np.ndarray, random_shocks: np.ndarray | None = None) -> np.ndarray` (InterestRateModel protocol)
- `simulate_short_rate_path(times: list[float] | np.ndarray, random_shocks: np.ndarray | None = None) -> np.ndarray` (legacy)
- `bond_price(t: float, T: float, state: float | np.ndarray | None = None, *, r_t: float | None = None) -> float`
- `discount_factor(t: float, T: float, state: float | np.ndarray | None = None, *, r_t: float | None = None) -> float`

### Quick Examples

```python
from datetime import date
from montecarlo_ir.models.hull_white import HullWhite1F
from montecarlo_ir.market_data.yield_curve import build_yield_curve_from_zero_rates
import numpy as np

# Create yield curve
curve = build_yield_curve_from_zero_rates(
    valuation_date=date(2024, 1, 1),
    pillar_dates=(date(2025, 1, 1), date(2026, 1, 1)),
    zero_rates=(0.02, 0.025),
)

# Create model
model = HullWhite1F(
    yield_curve=curve,
    mean_reversion=0.1,
    volatility=0.01,
    scheme="exact",
)

# Simulate short rate path
times = [0.0, 0.25, 0.5, 1.0]
rates = model.simulate_short_rate_path(times)

# Calculate bond price
bond_price = model.bond_price(t=0.0, T=1.0, r_t=0.02)
```

---

## `montecarlo_ir.models.lmm`

LIBOR Market Model for forward rate simulation.

### Types

**`DiscretizationScheme`**: `"euler"` | `"log_euler"`  
**`NumeraireMeasure`**: `"spot"` | `"terminal"`

### Class

**`LIBORMarketModel`** (dataclass, frozen)
- `yield_curve: YieldCurve`
- `tenor_structure: tuple[date, ...]` (T_0, T_1, ..., T_N)
- `volatilities: tuple[float, ...] | tuple[tuple[float, ...], ...]` (σ_i or σ_i(t))
- `correlation_matrix: tuple[tuple[float, ...], ...] | None = None`
- `scheme: DiscretizationScheme = "log_euler"`
- `measure: NumeraireMeasure = "spot"`
- `day_count: DayCountConvention = ACT_365`

**Methods:**
- `simulate_path(times: list[float] | np.ndarray, random_shocks: np.ndarray | None = None) -> np.ndarray` (InterestRateModel protocol)
- `simulate_forward_rates(times: list[float] | np.ndarray, random_shocks: np.ndarray | None = None) -> np.ndarray` (legacy)
- `discount_factor(t: float, T: float, state: float | np.ndarray | None = None, *, forward_rates: np.ndarray | None = None) -> float`
- `bond_price(t: float, T: float, state: float | np.ndarray | None = None, *, forward_rates: np.ndarray | None = None) -> float` (InterestRateModel protocol)

### Quick Examples

```python
from datetime import date
from montecarlo_ir.models.lmm import LIBORMarketModel
from montecarlo_ir.market_data.yield_curve import build_yield_curve_from_zero_rates
import numpy as np

# Create yield curve
curve = build_yield_curve_from_zero_rates(
    valuation_date=date(2024, 1, 1),
    pillar_dates=(date(2025, 1, 1), date(2026, 1, 1)),
    zero_rates=(0.02, 0.025),
)

# Create LMM model
model = LIBORMarketModel(
    yield_curve=curve,
    tenor_structure=(date(2024, 1, 1), date(2025, 1, 1), date(2026, 1, 1)),
    volatilities=(0.15, 0.16),
    correlation_matrix=((1.0, 0.5), (0.5, 1.0)),
    scheme="log_euler",
    measure="spot",
)

# Simulate forward rates
times = [0.0, 0.25, 0.5, 1.0]
rates = model.simulate_forward_rates(times)  # Shape: [n_times, n_rates]
```

---

## `montecarlo_ir.pricing.mc_engine`

Monte Carlo pricing engine for interest rate derivatives.

### Classes

**`MonteCarloEngine`** (dataclass, frozen)
- `model: InterestRateModel` (any model implementing the protocol)
- `num_paths: int = 10000`
- `seed: int | None = None`
- `use_antithetic: bool = False`
- `day_count: DayCountConvention = ACT_365`

**Methods:**
- `price(payoff_fn: Callable, simulation_times: list[float] | np.ndarray, valuation_date: date, return_paths: bool = False) -> MonteCarloResult`
- `compute_discount_factors(paths: np.ndarray, times: np.ndarray, valuation_date: date) -> np.ndarray`

**`MonteCarloResult`** (dataclass, frozen)
- `price: float`
- `standard_error: float`
- `num_paths: int`
- `paths: np.ndarray | None = None`

### Functions

**`align_simulation_grid(valuation_date: date, important_dates: list[date], min_step_size: float = 0.01, max_step_size: float = 0.25) -> list[float]`**
- Create simulation grid aligned with important dates

### Quick Examples

```python
from datetime import date
from montecarlo_ir.pricing.mc_engine import MonteCarloEngine, align_simulation_grid
from montecarlo_ir.models.hull_white import HullWhite1F
import numpy as np

# Create model and engine
model = HullWhite1F(yield_curve=curve, mean_reversion=0.1, volatility=0.01)
engine = MonteCarloEngine(model=model, num_paths=10000, use_antithetic=True)

# Define payoff function
def payoff_fn(rates: np.ndarray, times: np.ndarray) -> float:
    return max(0.0, rates[-1] - 0.02)

# Price derivative
times = [0.0, 0.25, 0.5, 1.0]
result = engine.price(
    payoff_fn=payoff_fn,
    simulation_times=times,
    valuation_date=date(2024, 1, 1),
)

print(f"Price: {result.price:.6f} ± {result.standard_error:.6f}")

# Align grid with important dates
grid = align_simulation_grid(
    valuation_date=date(2024, 1, 1),
    important_dates=[date(2024, 6, 1), date(2025, 1, 1)],
)
```

---

## `montecarlo_ir.calibration.hw_calibrator`

Hull-White model calibration to market instruments.

### Classes

**`CalibrationInstrument`** (dataclass, frozen)
- `expiry_date: date`
- `maturity_date: date`
- `strike: float`
- `market_price: float`
- `instrument_type: str` (`"caplet"` or `"swaption"`)

**`CalibrationResult`** (dataclass, frozen)
- `mean_reversion: float`
- `volatility: float`
- `calibrated_model: HullWhite1F`
- `calibration_error: float` (RMSE)
- `num_iterations: int`

### Functions

**`calibrate_hull_white_to_instruments(yield_curve: YieldCurve, instruments: list[CalibrationInstrument], initial_mean_reversion: float = 0.1, initial_volatility: float = 0.01, *, day_count: DayCountConvention = ACT_365, num_paths: int = 5000, seed: int | None = None) -> CalibrationResult`**
- Calibrate Hull-White model to market instruments (caplets/swaptions)

**`calibrate_hull_white_to_vol_surface(yield_curve: YieldCurve, vol_surface: VolatilitySurface, caplet_strikes: list[float] | tuple[float, ...], *, day_count: DayCountConvention = ACT_365, num_paths: int = 5000, seed: int | None = None) -> CalibrationResult`**
- Calibrate Hull-White to caplet volatility surface

### Quick Examples

```python
from datetime import date
from montecarlo_ir.calibration.hw_calibrator import (
    CalibrationInstrument,
    calibrate_hull_white_to_instruments,
    calibrate_hull_white_to_vol_surface,
)
from montecarlo_ir.market_data.yield_curve import build_yield_curve_from_zero_rates
from montecarlo_ir.market_data.vol_surface import VolatilitySurface

# Create yield curve
curve = build_yield_curve_from_zero_rates(
    valuation_date=date(2024, 1, 1),
    pillar_dates=(date(2025, 1, 1), date(2026, 1, 1)),
    zero_rates=(0.02, 0.025),
)

# Calibrate to instruments
instruments = [
    CalibrationInstrument(
        expiry_date=date(2024, 4, 1),
        maturity_date=date(2024, 7, 1),
        strike=0.02,
        market_price=0.001,
        instrument_type="caplet",
    )
]

result = calibrate_hull_white_to_instruments(
    yield_curve=curve,
    instruments=instruments,
    initial_mean_reversion=0.1,
    initial_volatility=0.01,
    num_paths=5000,
)

# Use calibrated model
model = result.calibrated_model
print(f"Calibrated a={result.mean_reversion:.4f}, σ={result.volatility:.4f}")

# Calibrate to volatility surface
vol_surface = VolatilitySurface(
    valuation_date=date(2024, 1, 1),
    expiry_times=(0.25, 0.5, 1.0),
    tenor_times=(0.25,),
    volatility_matrix=((0.15,), (0.16,), (0.17,)),
)

result = calibrate_hull_white_to_vol_surface(
    yield_curve=curve,
    vol_surface=vol_surface,
    caplet_strikes=(0.02, 0.02, 0.02),
    num_paths=5000,
)
```

---

## `montecarlo_ir.products.interest_rate_swap`

Interest Rate Swap (IRS) product implementation.

### Types

**`SwapType`**: `"payer"` | `"receiver"`

### Classes

**`InterestRateSwap`** (dataclass, frozen)
- `valuation_date: date`
- `start_date: date`
- `maturity_date: date`
- `fixed_rate: float` (annual)
- `notional: float`
- `swap_type: SwapType = "payer"`
- `fixed_frequency: str = "6M"`
- `floating_frequency: str = "6M"`
- `fixed_day_count: DayCountConvention = ACT_365`
- `floating_day_count: DayCountConvention = ACT_360`
- `business_day_rule: BusinessDayRule = MODIFIED_FOLLOWING`
- `calendar: list[date] | None = None`

**Methods:**
- `get_fixed_leg_cashflows() -> list[Cashflow]`
- `get_floating_leg_cashflows() -> list[Cashflow]`
- `payoff(yield_curve: YieldCurve, floating_rates: dict[date, float] | None = None) -> float`
- `payoff_mc(rates: np.ndarray, times: np.ndarray, yield_curve: YieldCurve) -> float`

**`Cashflow`** (dataclass, frozen)
- `payment_date: date`
- `reset_date: date | None`
- `notional: float`
- `rate: float`
- `day_count: DayCountConvention`

### Quick Examples

```python
from datetime import date
from montecarlo_ir.products.interest_rate_swap import InterestRateSwap
from montecarlo_ir.market_data.yield_curve import build_yield_curve_from_zero_rates
import numpy as np

# Create swap
swap = InterestRateSwap(
    valuation_date=date(2024, 1, 1),
    start_date=date(2024, 1, 1),
    maturity_date=date(2025, 1, 1),
    fixed_rate=0.02,
    notional=1000000.0,
    swap_type="payer",
    fixed_frequency="6M",
    floating_frequency="6M",
)

# Get cashflows
fixed_cfs = swap.get_fixed_leg_cashflows()
floating_cfs = swap.get_floating_leg_cashflows()

# Calculate payoff using yield curve
curve = build_yield_curve_from_zero_rates(
    valuation_date=date(2024, 1, 1),
    pillar_dates=(date(2025, 1, 1),),
    zero_rates=(0.02,),
)
pv = swap.payoff(curve)

# Calculate payoff for MC path
times = np.array([0.0, 0.5, 1.0])
rates = np.array([0.02, 0.025, 0.03])
payoff = swap.payoff_mc(rates, times, curve)
```

---

## `montecarlo_ir.products.cap_floor`

Cap and Floor products for interest rate protection.

### Types

**`CapFloorType`**: `"cap"` | `"floor"`

### Classes

**`CapFloor`** (dataclass, frozen)
- `valuation_date: date`
- `start_date: date`
- `maturity_date: date`
- `strike: float` (annual)
- `notional: float`
- `cap_floor_type: CapFloorType = "cap"`
- `frequency: str = "3M"`
- `day_count: DayCountConvention = ACT_360`
- `business_day_rule: BusinessDayRule = MODIFIED_FOLLOWING`
- `calendar: list[date] | None = None`

**Methods:**
- `get_caplets_floorlets() -> list[CapletFloorlet]`
- `payoff(yield_curve: YieldCurve, floating_rates: dict[date, float] | None = None) -> float`
- `payoff_mc(rates: np.ndarray, times: np.ndarray, yield_curve: YieldCurve) -> float`

**`CapletFloorlet`** (dataclass, frozen)
- `reset_date: date`
- `payment_date: date`
- `strike: float`
- `notional: float`
- `day_count: DayCountConvention`
- `option_type: CapFloorType`

### Quick Examples

```python
from datetime import date
from montecarlo_ir.products.cap_floor import CapFloor
from montecarlo_ir.market_data.yield_curve import build_yield_curve_from_zero_rates
import numpy as np

# Create cap
cap = CapFloor(
    valuation_date=date(2024, 1, 1),
    start_date=date(2024, 1, 1),
    maturity_date=date(2025, 1, 1),
    strike=0.02,
    notional=1000000.0,
    cap_floor_type="cap",
    frequency="3M",
)

# Get caplets
caplets = cap.get_caplets_floorlets()

# Calculate payoff using yield curve
curve = build_yield_curve_from_zero_rates(
    valuation_date=date(2024, 1, 1),
    pillar_dates=(date(2025, 1, 1),),
    zero_rates=(0.02,),
)
pv = cap.payoff(curve)

# Calculate payoff for MC path
times = np.array([0.0, 0.25, 0.5, 0.75, 1.0])
rates = np.array([0.02, 0.025, 0.03, 0.025, 0.02])
payoff = cap.payoff_mc(rates, times, curve)
```

---

## `montecarlo_ir.products.european_swaption`

European Swaption product.

### Types

**`SwaptionType`**: `"payer"` | `"receiver"`  
**`SettlementType`**: `"physical"` | `"cash"`

### Class

**`EuropeanSwaption`** (dataclass, frozen)
- `valuation_date: date`
- `expiry_date: date`
- `swap_start_date: date`
- `swap_maturity_date: date`
- `strike: float` (annual)
- `notional: float`
- `swaption_type: SwaptionType = "payer"`
- `settlement_type: SettlementType = "physical"`
- `swap_fixed_frequency: str = "6M"`
- `swap_floating_frequency: str = "6M"`
- `swap_fixed_day_count: DayCountConvention = ACT_365`
- `swap_floating_day_count: DayCountConvention = ACT_360`

**Methods:**
- `get_underlying_swap() -> InterestRateSwap`
- `payoff(yield_curve: YieldCurve, swap_value_at_expiry: float | None = None) -> float`
- `payoff_mc(rates: np.ndarray, times: np.ndarray, yield_curve: YieldCurve) -> float`

### Quick Examples

```python
from datetime import date
from montecarlo_ir.products.european_swaption import EuropeanSwaption
from montecarlo_ir.market_data.yield_curve import build_yield_curve_from_zero_rates
import numpy as np

# Create swaption
swaption = EuropeanSwaption(
    valuation_date=date(2024, 1, 1),
    expiry_date=date(2024, 6, 1),
    swap_start_date=date(2024, 7, 1),
    swap_maturity_date=date(2025, 6, 1),
    strike=0.02,
    notional=1000000.0,
    swaption_type="payer",
    settlement_type="physical",
)

# Get underlying swap
underlying_swap = swaption.get_underlying_swap()

# Calculate payoff using yield curve
curve = build_yield_curve_from_zero_rates(
    valuation_date=date(2024, 1, 1),
    pillar_dates=(date(2025, 1, 1),),
    zero_rates=(0.02,),
)
pv = swaption.payoff(curve)

# Calculate payoff for MC path
times = np.array([0.0, 0.25, 0.5, 0.75, 1.0])
rates = np.array([0.02, 0.025, 0.03, 0.025, 0.02])
payoff = swaption.payoff_mc(rates, times, curve)
```

---

## `montecarlo_ir.pricing.product_pricers`

Product pricers that connect products to the Monte Carlo engine.

### Classes

**`SwapPricer`** (dataclass, frozen)
- `model: InterestRateModel` (any model implementing the protocol)
- `num_paths: int = 10000`
- `seed: int | None = None`
- `use_antithetic: bool = False`

**Methods:**
- `price(swap: InterestRateSwap) -> MonteCarloResult`

**`CapFloorPricer`** (dataclass, frozen)
- `model: InterestRateModel` (any model implementing the protocol)
- `num_paths: int = 10000`
- `seed: int | None = None`
- `use_antithetic: bool = False`

**Methods:**
- `price(cap_floor: CapFloor) -> MonteCarloResult`

**`EuropeanSwaptionPricer`** (dataclass, frozen)
- `model: InterestRateModel` (any model implementing the protocol)
- `num_paths: int = 10000`
- `seed: int | None = None`
- `use_antithetic: bool = False`

**Methods:**
- `price(swaption: EuropeanSwaption) -> MonteCarloResult`

### Quick Examples

```python
from datetime import date
from montecarlo_ir.pricing.product_pricers import SwapPricer, CapFloorPricer, EuropeanSwaptionPricer
from montecarlo_ir.models.hull_white import HullWhite1F
from montecarlo_ir.products.interest_rate_swap import InterestRateSwap
from montecarlo_ir.products.cap_floor import CapFloor
from montecarlo_ir.products.european_swaption import EuropeanSwaption

# Create model
model = HullWhite1F(yield_curve=curve, mean_reversion=0.1, volatility=0.01)

# Price swap
swap = InterestRateSwap(...)
swap_pricer = SwapPricer(model=model, num_paths=10000, seed=42)
swap_result = swap_pricer.price(swap)
print(f"Swap price: {swap_result.price:.6f} ± {swap_result.standard_error:.6f}")

# Price cap
cap = CapFloor(...)
cap_pricer = CapFloorPricer(model=model, num_paths=10000, seed=42)
cap_result = cap_pricer.price(cap)
print(f"Cap price: {cap_result.price:.6f} ± {cap_result.standard_error:.6f}")

# Price swaption
swaption = EuropeanSwaption(...)
swaption_pricer = EuropeanSwaptionPricer(model=model, num_paths=10000, seed=42)
swaption_result = swaption_pricer.price(swaption)
print(f"Swaption price: {swaption_result.price:.6f} ± {swaption_result.standard_error:.6f}")
```

---

## `montecarlo_ir.utils.model_comparison`

Model comparison utilities for comparing pricing across different models.

### Classes

**`ComparisonResult`** (dataclass, frozen)
- `model_names: tuple[str, ...]`
- `prices: tuple[float, ...]`
- `standard_errors: tuple[float, ...]`
- `num_paths: int`
- `statistics: dict[str, float]` (mean, std, min, max, range, relative_std)

### Functions

**`compare_models(pricer_factory: Callable[[InterestRateModel], Callable], product: object, models: list[tuple[InterestRateModel, str]]) -> ComparisonResult`**
- Compare pricing results across multiple models
- Returns statistics on price differences

### Quick Examples

```python
from montecarlo_ir.utils.model_comparison import compare_models
from montecarlo_ir.pricing.product_pricers import SwapPricer
from montecarlo_ir.models.hull_white import HullWhite1F

def create_pricer(model: InterestRateModel):
    return SwapPricer(model=model, num_paths=5000, seed=42).price

models = [
    (HullWhite1F(yield_curve=curve, mean_reversion=0.1, volatility=0.01), "HW1F_a=0.1"),
    (HullWhite1F(yield_curve=curve, mean_reversion=0.15, volatility=0.015), "HW1F_a=0.15"),
]

result = compare_models(create_pricer, swap, models)
print(f"Mean price: {result.statistics['mean']:.6f}")
print(f"Price range: {result.statistics['range']:.6f}")
```

---

## Error Handling

- **`ValueError`**: Invalid date order, unsupported convention/rule/frequency, invalid curve/surface/model inputs, invalid MC parameters, invalid calibration inputs, invalid swap/cap/swaption parameters
