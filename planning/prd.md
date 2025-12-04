# Monte Carlo Interest Rate Derivatives Library: Requirements Document

## Objective

Design and implement a modular, production-grade Monte Carlo library in Python for pricing vanilla and exotic interest rate derivatives. The library should serve both as a robust quantitative tool for practitioners and as an educational reference for foundational financial modeling.

**Key Design Principle**: Model-agnostic pricers that enable easy comparison of pricing across different interest rate models.

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

* **1-Factor Models**:
  * Hull–White 1-Factor (HW1F) ✅
  * Quadratic Gaussian (QG) - NEW
* **2-Factor Models**:
  * Hull–White 2-Factor (HW2F) - NEW
  * G2++ (Gaussian 2-Factor) - NEW
* **Forward Rate Models**:
  * LIBOR Market Model (LMM) ✅
  * SABR-LMM hybrid (optional)

**Model Interface Requirements**:

All models must implement a standardized `InterestRateModel` protocol that provides:
* `yield_curve: YieldCurve` - Reference yield curve
* `simulate_path(times, random_shocks) -> np.ndarray` - Path simulation
* `discount_factor(t, T, state) -> float` - Discount factor calculation
* `bond_price(t, T, state) -> float` - Bond price (if applicable)

This ensures pricers work identically across all models, enabling direct comparison.

Each model module must:

* Allow calibration to caplet/swaption vol surfaces
* Support exact or Euler discretization schemes
* Provide simulation of rate paths and discount factors
* Implement the standardized `InterestRateModel` protocol

---

## Code Architecture

### 📁 Folder Layout

```
montecarlo_ir/
├── src/
│   ├── models/                # Interest rate models
│   │   ├── __init__.py        # Model registry and factory
│   │   ├── base.py            # InterestRateModel protocol/ABC
│   │   ├── hull_white.py      # HW1F (refactor to use base)
│   │   ├── hull_white_2f.py   # HW2F - NEW
│   │   ├── g2pp.py            # G2++ - NEW
│   │   ├── quadratic_gaussian.py  # QG - NEW
│   │   ├── lmm.py             # LMM (refactor to use base)
│   │   ├── sabr_lmm.py        # SABR-LMM (optional)
│   ├── products/              # IR instruments
│   │   ├── interest_rate_swap.py
│   │   ├── cap_floor.py
│   │   ├── european_swaption.py
│   │   ├── bermudan_swaption.py
│   │   ├── range_accrual.py
│   │   ├── callable_note.py
│   ├── pricing/               # Pricing engines
│   │   ├── mc_engine.py       # (refactor to use base protocol)
│   │   ├── lsm_pricer.py
│   │   ├── product_pricers.py # (refactor to use base protocol)
│   ├── calibration/           # Market fitting tools
│   │   ├── hw_calibrator.py
│   │   ├── hw2f_calibrator.py  # NEW
│   │   ├── g2pp_calibrator.py  # NEW
│   │   ├── qg_calibrator.py    # NEW
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
│   ├── test_model_comparison.py  # NEW - Compare models
│   ├── test_pricers.py
│   ├── test_products.py
├── notebooks/                 # Examples
│   ├── model_comparison.ipynb  # NEW - Compare pricing across models
│   ├── vanilla_products.ipynb
│   ├── bermudan_swaptions.ipynb
│   ├── range_accrual.ipynb
├── README.md
```

---

## Functional Requirements

### 🎯 Model Interface (NEW - CRITICAL)

**`InterestRateModel` Protocol/ABC**:

All interest rate models must implement:

```python
class InterestRateModel(Protocol):
    """Standardized interface for all interest rate models."""
    
    yield_curve: YieldCurve
    
    def simulate_path(
        self, 
        times: np.ndarray, 
        random_shocks: np.ndarray | None = None
    ) -> np.ndarray:
        """Simulate interest rate path.
        
        Args:
            times: Time points for simulation (years from valuation_date)
            random_shocks: Optional pre-generated random shocks
            
        Returns:
            Array of rates/states [n_times] or [n_times, n_factors]
            - For 1-factor: [n_times] (short rates)
            - For 2-factor: [n_times, 2] (state vector)
            - For LMM: [n_times, n_rates] (forward rates)
        """
        ...
    
    def discount_factor(
        self, 
        t: float, 
        T: float, 
        state: np.ndarray | float
    ) -> float:
        """Calculate discount factor from t to T.
        
        Args:
            t: Current time (years from valuation_date)
            T: Future time (years from valuation_date)
            state: Current state (rate for 1F, state vector for 2F)
            
        Returns:
            Discount factor D(t, T)
        """
        ...
    
    def bond_price(
        self, 
        t: float, 
        T: float, 
        state: np.ndarray | float
    ) -> float:
        """Calculate zero-coupon bond price (if applicable).
        
        Args:
            t: Current time
            T: Maturity time
            state: Current state
            
        Returns:
            Bond price P(t, T)
        """
        ...
```

**Benefits**:
- Pricers work with any model implementing the protocol
- Easy model comparison: swap models in pricers without code changes
- Type safety: Protocol ensures all models have required methods
- Extensibility: New models just need to implement the protocol

### 🎯 Product Interfaces

Each product class must:

* Store contract parameters (notional, strike, dates, day-count, etc.)
* Expose `get_cashflows()` or `payoff()` functions for Monte Carlo
* Be serializable and testable
* Work with any model via the standardized interface

### 🎯 Pricers (REFACTORED)

Each pricer should:

* Accept any `InterestRateModel` (not specific model types)
* Simulate scenarios under the appropriate measure
* Compute payoff per path and discount
* Return final price and standard error
* **Interface remains identical regardless of underlying model**

Special pricers:

* `LSMPricer` for Bermudan/callable instruments
* `CapFloorPricer` for multi-caplet pricing
* `EuropeanSwaptionPricer` for swap options
* `SwapPricer` for PV of IRS cashflows via MC

**Model Comparison Feature**:
* `compare_models(pricer, product, models: list[InterestRateModel]) -> ComparisonResult`
* Returns prices, standard errors, and statistics for all models
* Enables side-by-side comparison

### 🎯 Models

**1-Factor Models**:

* **Hull-White 1F** ✅
  * SDE: `dr(t) = (θ(t) - a*r(t))dt + σ*dW(t)`
  * Parameters: mean reversion (a), volatility (σ)
  
* **Quadratic Gaussian (QG)** - NEW
  * SDE: `dr(t) = (θ(t) - a*r(t))dt + σ*sqrt(r(t))*dW(t)` (CIR-like)
  * Or: `dr(t) = κ(θ - r(t))dt + σ*r(t)^γ*dW(t)` (general form)
  * Parameters: mean reversion, volatility, power parameter

**2-Factor Models**:

* **Hull-White 2F (HW2F)** - NEW
  * SDE: 
    * `dr(t) = (θ(t) - a*r(t) - b*x(t))dt + σ*dW₁(t)`
    * `dx(t) = -c*x(t)dt + η*dW₂(t)`
  * Parameters: mean reversions (a, c), volatilities (σ, η), correlation (ρ)
  * State: `[r(t), x(t)]`
  
* **G2++ (Gaussian 2-Factor)** - NEW
  * SDE:
    * `dx(t) = -a*x(t)dt + σ*dW₁(t)`
    * `dy(t) = -b*y(t)dt + η*dW₂(t)`
    * `r(t) = x(t) + y(t) + φ(t)`
  * Parameters: mean reversions (a, b), volatilities (σ, η), correlation (ρ)
  * State: `[x(t), y(t)]`

**Forward Rate Models**:

* **LIBOR Market Model (LMM)** ✅
  * Forward rate simulation with drift adjustments

Each model should:

* Implement the `InterestRateModel` protocol
* Simulate rates (short rate or forwards)
* Provide bond prices or discount factors
* Support calibration from market instruments
* Handle multi-factor state vectors appropriately

### 🎯 Monte Carlo Engine

* Simulate multi-path forward/short-rate evolution
* Align simulation grid with reset, payment, exercise dates
* Support:
  * Exact or Euler steps
  * Antithetic variates
  * Control variates (optional)
  * Bump-and-revalue for Greeks
* Work with any `InterestRateModel` implementation
* Optional:
  * Adjoint differentiation or autodiff (JAX, etc.)

---

## Testing and Validation

* Unit tests with known analytic values:
  * Black's caplet prices
  * HW1F European swaptions
  * HW2F/G2++ analytical formulas (where available)
  * PV of vanilla swaps from curve
* **Model comparison tests** - NEW
  * Compare pricing across models for same product
  * Validate convergence to same limits (where applicable)
  * Statistical convergence tests
* Regression-based continuation value in Bermudans (validate basis choice)
* **Cross-model validation** - NEW
  * Ensure pricers produce consistent results across models
  * Test model-agnostic interface compliance

---

## Documentation and Educational Features

* Code with complete type hints and docstrings
* A `README.md` that explains:
  * Project scope
  * Mathematical foundations of each model
  * Model comparison methodology
  * Monte Carlo methods and techniques
* Inline references to literature or textbooks
* Jupyter notebook examples:
  * **Model comparison notebook** - NEW
    * Compare HW1F vs HW2F vs G2++ vs QG pricing
    * Visualize differences
    * Analyze convergence
  * Vanilla products
  * Bermudan swaptions
  * Range accrual

---

## Optional Enhancements

* QuantLib curve-building wrapped for term structure bootstrapping
* GUI or CLI interface for batch product pricing
* Path recording for exposure analysis (e.g. CVA, PFE)
* Vega and convexity diagnostics for hybrid desks
* **Model selection tools** - NEW
  * Automated model comparison
  * Best-fit model recommendation based on market data

---

## Deliverables

* Full Python package with source, tests, documentation
* Unit and benchmark test results
* **Model comparison framework** - NEW
* Notebook demos: vanilla, Bermudan, range accrual, **model comparison**
* Modular design for future extension to credit and FX hybrids
* **Type-safe model-agnostic pricers** - NEW

---

## Model Comparison Use Cases

1. **Pricing Comparison**: Price the same product with different models
2. **Sensitivity Analysis**: Compare how different models respond to market changes
3. **Model Selection**: Choose best model for specific product/market conditions
4. **Research**: Study model behavior and limitations
5. **Validation**: Cross-check pricing results across models
