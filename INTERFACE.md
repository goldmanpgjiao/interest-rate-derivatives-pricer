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

## Error Handling

- **`ValueError`**: Invalid date order, unsupported convention/rule/frequency, invalid curve/surface inputs
