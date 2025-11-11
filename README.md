# Monte Carlo Interest Rate Derivatives Library

A modular, production-grade Monte Carlo library in Python for pricing vanilla and exotic interest rate derivatives.

## Overview

This library provides:
- Monte Carlo simulation engines for interest rate modeling
- Support for vanilla products (IRS, Cap/Floor, European Swaptions)
- Support for exotic products (Bermudan Swaptions, Range Accrual Notes, Callable Notes, CMS Swaps)
- Multiple interest rate models (Hull-White 1F, LIBOR Market Model, SABR-LMM)
- Calibration tools for model parameters
- Comprehensive testing and validation

## Installation

```bash
# Install with uv
uv sync

# Install with development dependencies
uv sync --extra dev

# Install with optional dependencies (JAX for autodiff)
uv sync --extra jax

# Install with QuantLib support (optional)
uv sync --extra quantlib
```

## Quick Start

Coming soon - see examples in `notebooks/` directory.

## Documentation

See `prd.md` for detailed requirements and architecture.

## Development

See `WORKFLOW.md` for development workflow and guidelines.

