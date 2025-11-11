# Monte Carlo Interest Rate Derivatives Library: Requirements Document

## Objective

Design and implement a modular, production-grade Monte Carlo library in Python for pricing vanilla and exotic interest rate derivatives. The library should serve both as a robust quantitative tool for practitioners and as an educational reference for foundational financial modeling.

---

## Core Features

### ✅ Product Coverage

Support for both vanilla and exotic instruments:

* **Vanilla Products**:

  * Interest Rate Swaps (IRS)
  * Cap/Floor (and individual caplets/floorlets)
  * European Swaptions (payer/receiver, physical/cash settlement)
* **Exotic Products**:

  * Bermudan Swaptions
  * Range Accrual Notes
  * Callable Notes
  * CMS Swaps (convexity adjustments or stochastic pricing)

### ✅ Models and Calibration

Support and calibrate the following models:

* Hull–White 1-Factor (HW1F)
* LIBOR Market Model (LMM)
* SABR-LMM hybrid (optional)

Each model module must:

* Allow calibration to caplet/swaption vol surfaces
* Support exact or Euler discretization schemes
* Provide simulation of rate paths and discount factors

---

## Code Architecture

### 📁 Folder Layout

```
montecarlo_ir/
├── src/
│   ├── models/                # Interest rate models
│   │   ├── hull_white.py
│   │   ├── lmm.py
│   │   ├── sabr_lmm.py
│   ├── products/              # IR instruments
│   │   ├── interest_rate_swap.py
│   │   ├── cap_floor.py
│   │   ├── european_swaption.py
│   │   ├── bermudan_swaption.py
│   │   ├── range_accrual.py
│   │   ├── callable_note.py
│   ├── pricing/               # Pricing engines
│   │   ├── mc_engine.py
│   │   ├── lsm_pricer.py
│   │   ├── product_pricers.py
│   ├── calibration/           # Market fitting tools
│   │   ├── hw_calibrator.py
│   │   ├── lmm_calibrator.py
│   ├── market_data/           # Yield curves and vol surfaces
│   │   ├── yield_curve.py
│   │   ├── vol_surface.py
│   ├── utils/
│   │   ├── date_helpers.py
│   │   ├── quantlib_wrapper.py (optional)
│   ├── config.py              # Global config
│   ├── logger.py              # Logging setup
├── tests/                     # Unit tests
│   ├── test_models.py
│   ├── test_pricers.py
│   ├── test_products.py
├── README.md
```

---

## Functional Requirements

### 🎯 Product Interfaces

Each product class must:

* Store contract parameters (notional, strike, dates, day-count, etc.)
* Expose `get_cashflows()` or `payoff()` functions for Monte Carlo
* Be serializable and testable

### 🎯 Pricers

Each pricer should:

* Accept a model and product as inputs
* Simulate scenarios under the appropriate measure
* Compute payoff per path and discount
* Return final price and standard error

Special pricers:

* `LSMPricer` for Bermudan/callable instruments
* `CapFloorPricer` for multi-caplet pricing
* `EuropeanSwaptionPricer` for swap option under various settlement types
* `SwapPricer` for PV of IRS cashflows via MC

### 🎯 Models

Each model should:

* Simulate rates (short rate or forwards)
* Provide bond prices or discount factors
* Support calibration from market instruments

### 🎯 Monte Carlo Engine

* Simulate multi-path forward/short-rate evolution
* Align simulation grid with reset, payment, exercise dates
* Support:

  * Exact or Euler steps
  * Antithetic variates
  * Control variates (optional)
  * Bump-and-revalue for Greeks
* Optional:

  * Adjoint differentiation or autodiff (JAX, etc.)

---

## Testing and Validation

* Unit tests with known analytic values:

  * Black’s caplet prices
  * HW1F European swaptions
  * PV of vanilla swaps from curve
* Statistical convergence tests
* Regression-based continuation value in Bermudans (validate basis choice)

---

## Documentation and Educational Features

* Code with complete type hints and docstrings
* A `README.md` that explains:

  * Project scope
  * Mathematical foundations of each model
  * Monte Carlo methods and techniques
* Inline references to literature or textbooks
* Jupyter notebook examples for demonstration

---

## Optional Enhancements

* QuantLib curve-building wrapped for term structure bootstrapping
* GUI or CLI interface for batch product pricing
* Path recording for exposure analysis (e.g. CVA, PFE)
* Vega and convexity diagnostics for hybrid desks

---

## Deliverables

* Full Python package with source, tests, documentation
* Unit and benchmark test results
* Notebook demos: vanilla, Bermudan, range accrual
* Modular design for future extension to credit and FX hybrids
