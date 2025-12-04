# TODO Plan: Model-Agnostic Interface and Extended Models

## Overview

This TODO plan outlines the implementation of:
1. Model-agnostic interface for pricers
2. 2-factor short rate models (HW2F, G2++)
3. Quadratic Gaussian model
4. Model comparison framework

---

## Phase 8: Model Interface Refactoring

### Task 8.1: Create Base Model Interface
- [ ] Create `src/montecarlo_ir/models/base.py`
  - [ ] Define `InterestRateModel` Protocol
  - [ ] Document required methods:
    - `yield_curve: YieldCurve` (property)
    - `simulate_path(times, random_shocks) -> np.ndarray`
    - `discount_factor(t, T, state) -> float`
    - `bond_price(t, T, state) -> float` (optional)
  - [ ] Add type hints and docstrings
  - [ ] Create `ModelState` type alias for state vectors
  - [ ] Add validation helpers

### Task 8.2: Refactor HullWhite1F
- [ ] Update `src/montecarlo_ir/models/hull_white.py`
  - [ ] Make class implement `InterestRateModel` protocol
  - [ ] Add `simulate_path()` method (alias or rename `simulate_short_rate_path`)
  - [ ] Update `discount_factor()` signature to accept state
  - [ ] Ensure state is single float (1-factor)
  - [ ] Add protocol compliance tests
  - [ ] Maintain backward compatibility

### Task 8.3: Refactor LIBORMarketModel
- [ ] Update `src/montecarlo_ir/models/lmm.py`
  - [ ] Make class implement `InterestRateModel` protocol
  - [ ] Rename `simulate_forward_rates()` → `simulate_path()` (or add alias)
  - [ ] Update `discount_factor()` to work with forward rate state
  - [ ] Handle multi-rate state vector `[n_times, n_rates]`
  - [ ] Add protocol compliance tests

### Task 8.4: Refactor MonteCarloEngine
- [ ] Update `src/montecarlo_ir/pricing/mc_engine.py`
  - [ ] Replace `HullWhite1F | LIBORMarketModel` with `InterestRateModel`
  - [ ] Update `_simulate_path()` to use protocol method
  - [ ] Handle different state vector shapes (1D, 2D, etc.)
  - [ ] Update type hints throughout
  - [ ] Add tests with multiple model types

### Task 8.5: Refactor Product Pricers
- [ ] Update `src/montecarlo_ir/pricing/product_pricers.py`
  - [ ] Replace specific model types with `InterestRateModel` in:
    - `SwapPricer`
    - `CapFloorPricer`
    - `EuropeanSwaptionPricer`
  - [ ] Update all type hints
  - [ ] Ensure pricers work with any compliant model
  - [ ] Add validation that model implements protocol

### Task 8.6: Create Model Comparison Utilities
- [ ] Create `src/montecarlo_ir/utils/model_comparison.py`
  - [ ] Implement `compare_models()` function
    - Signature: `compare_models(pricer, product, models: list[InterestRateModel]) -> ComparisonResult`
  - [ ] Create `ComparisonResult` dataclass:
    - `model_names: list[str]`
    - `prices: list[float]`
    - `standard_errors: list[float]`
    - `num_paths: int`
    - `statistics: dict` (mean, std, min, max, etc.)
  - [ ] Add visualization helpers
  - [ ] Add statistical analysis functions

### Task 8.7: Update Tests
- [ ] Create `tests/test_model_interface.py`
  - [ ] Test protocol compliance for all models
  - [ ] Test pricers with different models
  - [ ] Test model comparison utilities
- [ ] Update existing tests
  - [ ] Ensure all tests pass with refactored code
  - [ ] Add tests for backward compatibility

---

## Phase 9: 2-Factor Models

### Task 9.1: Implement Hull-White 2F
- [ ] Create `src/montecarlo_ir/models/hull_white_2f.py`
  - [ ] Define `HullWhite2F` dataclass
    - Parameters: `mean_reversion_r`, `mean_reversion_x`, `volatility_r`, `volatility_x`, `correlation`
    - `yield_curve: YieldCurve`
    - `scheme: DiscretizationScheme`
  - [ ] Implement `simulate_path()` returning `[n_times, 2]` state
  - [ ] Implement `discount_factor(t, T, state)` where state is `[r, x]`
  - [ ] Implement `bond_price(t, T, state)`
  - [ ] Implement `_theta()` for yield curve fitting
  - [ ] Add exact and Euler discretization schemes
  - [ ] Implement `__post_init__()` validation

### Task 9.2: Implement G2++
- [ ] Create `src/montecarlo_ir/models/g2pp.py`
  - [ ] Define `G2PP` dataclass
    - Parameters: `mean_reversion_x`, `mean_reversion_y`, `volatility_x`, `volatility_y`, `correlation`
    - `yield_curve: YieldCurve`
  - [ ] Implement `simulate_path()` returning `[n_times, 2]` state `[x, y]`
  - [ ] Implement `r(t) = x(t) + y(t) + φ(t)` calculation
  - [ ] Implement analytical bond pricing formulas
  - [ ] Implement `discount_factor(t, T, state)`
  - [ ] Add exact and Euler discretization
  - [ ] Implement `__post_init__()` validation

### Task 9.3: Add Calibration for 2-Factor Models
- [ ] Create `src/montecarlo_ir/calibration/hw2f_calibrator.py`
  - [ ] Implement `calibrate_hull_white_2f_to_instruments()`
  - [ ] Implement `calibrate_hull_white_2f_to_vol_surface()`
  - [ ] 5-6 parameter optimization (a, c, σ, η, ρ, possibly b)
  - [ ] Use scipy.optimize
- [ ] Create `src/montecarlo_ir/calibration/g2pp_calibrator.py`
  - [ ] Implement `calibrate_g2pp_to_instruments()`
  - [ ] Implement `calibrate_g2pp_to_vol_surface()`
  - [ ] 5 parameter optimization (a, b, σ, η, ρ)

### Task 9.4: Tests for 2-Factor Models
- [ ] Create `tests/test_hull_white_2f.py`
  - [ ] Construction validation
  - [ ] Path simulation tests
  - [ ] Bond pricing tests
  - [ ] Discount factor tests
  - [ ] State vector shape validation
- [ ] Create `tests/test_g2pp.py`
  - [ ] Construction validation
  - [ ] Path simulation tests
  - [ ] Analytical bond pricing validation
  - [ ] State vector handling
- [ ] Create `tests/test_hw2f_calibrator.py`
- [ ] Create `tests/test_g2pp_calibrator.py`

### Task 9.5: Export 2-Factor Models
- [ ] Update `src/montecarlo_ir/models/__init__.py`
  - [ ] Export `HullWhite2F`
  - [ ] Export `G2PP`
- [ ] Update `src/montecarlo_ir/calibration/__init__.py`
  - [ ] Export calibration functions

---

## Phase 10: Quadratic Models

### Task 10.1: Implement Quadratic Gaussian
- [ ] Create `src/montecarlo_ir/models/quadratic_gaussian.py`
  - [ ] Define `QuadraticGaussian` dataclass
    - Parameters: `mean_reversion`, `volatility`, `power` (γ), `theta` (optional)
    - `yield_curve: YieldCurve`
    - `scheme: DiscretizationScheme`
  - [ ] Implement SDE: `dr = κ(θ - r)dt + σ*r^γ*dW`
  - [ ] Implement `simulate_path()` with non-negativity checks
  - [ ] Implement `discount_factor(t, T, state)`
  - [ ] Implement `bond_price(t, T, state)` (analytical if possible, else numerical)
  - [ ] Handle special cases (CIR: γ=0.5, etc.)
  - [ ] Add validation for non-negative rates

### Task 10.2: Add Calibration for QG
- [ ] Create `src/montecarlo_ir/calibration/qg_calibrator.py`
  - [ ] Implement `calibrate_quadratic_gaussian_to_instruments()`
  - [ ] Implement `calibrate_quadratic_gaussian_to_vol_surface()`
  - [ ] Power parameter estimation
  - [ ] Non-negativity constraints

### Task 10.3: Tests for QG Model
- [ ] Create `tests/test_quadratic_gaussian.py`
  - [ ] Construction validation
  - [ ] Path simulation tests
  - [ ] Non-negativity validation
  - [ ] Bond pricing tests
  - [ ] Special case tests (CIR)

### Task 10.4: Export QG Model
- [ ] Update `src/montecarlo_ir/models/__init__.py`
  - [ ] Export `QuadraticGaussian`
- [ ] Update `src/montecarlo_ir/calibration/__init__.py`
  - [ ] Export QG calibration functions

---

## Phase 11: Model Comparison Framework

### Task 11.1: Create Comparison Utilities
- [ ] Create `src/montecarlo_ir/utils/model_comparison.py`
  - [ ] Implement `compare_models()` function
  - [ ] Create `ComparisonResult` dataclass
  - [ ] Add statistical analysis:
    - Mean, std, min, max prices
    - Relative differences
    - Convergence analysis
  - [ ] Add visualization helpers:
    - Price comparison plots
    - Error bar charts
    - Convergence plots

### Task 11.2: Create Comparison Notebook
- [ ] Create `notebooks/model_comparison.ipynb`
  - [ ] Compare HW1F vs HW2F vs G2++ vs QG
  - [ ] Price same product with all models
  - [ ] Visualize price differences
  - [ ] Analyze convergence
  - [ ] Sensitivity analysis
  - [ ] Performance benchmarks

### Task 11.3: Model Comparison Tests
- [ ] Create `tests/test_model_comparison.py`
  - [ ] Test `compare_models()` function
  - [ ] Test `ComparisonResult` dataclass
  - [ ] Test with different product types
  - [ ] Test statistical calculations
  - [ ] Validate consistency across models

### Task 11.4: Update Documentation
- [ ] Update `INTERFACE.md`
  - [ ] Document `InterestRateModel` protocol
  - [ ] Document new models (HW2F, G2++, QG)
  - [ ] Document model comparison utilities
- [ ] Update `README.md`
  - [ ] Add model comparison section
  - [ ] Add examples of comparing models
  - [ ] Document model selection guidance

---

## Phase 12: Integration and Validation

### Task 12.1: End-to-End Testing
- [ ] Test all pricers with all models
  - [ ] SwapPricer with HW1F, HW2F, G2++, QG, LMM
  - [ ] CapFloorPricer with all models
  - [ ] EuropeanSwaptionPricer with all models
- [ ] Validate pricing consistency
- [ ] Performance benchmarking

### Task 12.2: Update Examples
- [ ] Update existing notebooks to use new interface
- [ ] Create new examples showing model comparison
- [ ] Add best practices documentation

### Task 12.3: Final Documentation
- [ ] Complete API documentation
- [ ] Model selection guide
- [ ] Performance characteristics
- [ ] Known limitations

---

## Priority Order

1. **Phase 8** (Model Interface) - Foundation for everything else
2. **Phase 9** (2-Factor Models) - High value, commonly used
3. **Phase 10** (Quadratic Models) - Specialized use cases
4. **Phase 11** (Comparison Framework) - Enables research and validation
5. **Phase 12** (Integration) - Final polish

---

## Estimated Effort

- **Phase 8**: 2-3 days (refactoring, careful testing)
- **Phase 9**: 4-5 days (2 models + calibration + tests)
- **Phase 10**: 2-3 days (1 model + calibration + tests)
- **Phase 11**: 2-3 days (utilities + notebook + tests)
- **Phase 12**: 1-2 days (integration + docs)

**Total**: ~11-16 days of focused development

---

## Success Criteria

- [ ] All pricers work with any model implementing `InterestRateModel`
- [ ] No code changes needed in pricers when adding new models
- [ ] All models can be compared side-by-side
- [ ] Comprehensive test coverage (>80%)
- [ ] Documentation complete
- [ ] Model comparison notebook demonstrates value

