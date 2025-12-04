"""Model comparison utilities.

Tools for comparing pricing results across different interest rate models.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np

from montecarlo_ir.models.base import InterestRateModel
from montecarlo_ir.pricing.mc_engine import MonteCarloResult


@dataclass(frozen=True)
class ComparisonResult:
    """Results from comparing multiple models.

    Attributes:
        model_names: List of model names/identifiers.
        prices: List of prices from each model.
        standard_errors: List of standard errors from each model.
        num_paths: Number of paths used (should be same for all).
        statistics: Dictionary of statistical measures:
            - mean: Mean price across models
            - std: Standard deviation of prices
            - min: Minimum price
            - max: Maximum price
            - range: Price range (max - min)
            - relative_std: Coefficient of variation (std/mean)
    """

    model_names: tuple[str, ...]
    prices: tuple[float, ...]
    standard_errors: tuple[float, ...]
    num_paths: int
    statistics: dict[str, float]

    def __post_init__(self) -> None:
        """Validate comparison results."""
        if len(self.model_names) != len(self.prices):
            raise ValueError("model_names and prices must have same length.")
        if len(self.model_names) != len(self.standard_errors):
            raise ValueError("model_names and standard_errors must have same length.")
        if len(self.model_names) < 2:
            raise ValueError("At least 2 models required for comparison.")


def compare_models(
    pricer_factory: Callable[[InterestRateModel], Callable],
    product: object,
    models: list[tuple[InterestRateModel, str]],
) -> ComparisonResult:
    """Compare pricing results across multiple models.

    Args:
        pricer_factory: Function that takes a model and returns a pricer function.
                       Signature: (model: InterestRateModel) -> Callable[[product], MonteCarloResult]
        product: Product to price (e.g., InterestRateSwap, CapFloor, etc.).
        models: List of (model, name) tuples to compare.

    Returns:
        ComparisonResult with prices, errors, and statistics.

    Example:
        ```python
        def create_swap_pricer(model):
            return SwapPricer(model=model, num_paths=10000).price

        models = [
            (HullWhite1F(...), "HW1F"),
            (HullWhite2F(...), "HW2F"),
        ]
        result = compare_models(create_swap_pricer, swap, models)
        ```
    """
    if len(models) < 2:
        raise ValueError("At least 2 models required for comparison.")

    model_names = []
    prices = []
    standard_errors = []
    num_paths_list = []

    for model, name in models:
        pricer = pricer_factory(model)
        mc_result = pricer(product)

        model_names.append(name)
        prices.append(mc_result.price)
        standard_errors.append(mc_result.standard_error)
        num_paths_list.append(mc_result.num_paths)

    # Validate all used same number of paths
    if len(set(num_paths_list)) > 1:
        raise ValueError("All models must use the same number of paths for fair comparison.")

    num_paths = num_paths_list[0]

    # Calculate statistics
    prices_array = np.array(prices)
    mean_price = float(np.mean(prices_array))
    std_price = float(np.std(prices_array, ddof=1))
    min_price = float(np.min(prices_array))
    max_price = float(np.max(prices_array))
    price_range = max_price - min_price
    relative_std = std_price / mean_price if mean_price != 0.0 else float("inf")

    statistics = {
        "mean": mean_price,
        "std": std_price,
        "min": min_price,
        "max": max_price,
        "range": price_range,
        "relative_std": relative_std,
    }

    return ComparisonResult(
        model_names=tuple(model_names),
        prices=tuple(prices),
        standard_errors=tuple(standard_errors),
        num_paths=num_paths,
        statistics=statistics,
    )

