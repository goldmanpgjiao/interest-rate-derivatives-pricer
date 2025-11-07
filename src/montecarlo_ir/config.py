"""Global configuration for the montecarlo_ir package."""

from typing import Final

# Default Monte Carlo parameters
DEFAULT_NUM_PATHS: Final[int] = 10000
DEFAULT_NUM_STEPS: Final[int] = 252
DEFAULT_SEED: Final[int] = 42

# Default numerical tolerances
DEFAULT_TOLERANCE: Final[float] = 1e-6
DEFAULT_MAX_ITERATIONS: Final[int] = 1000

# Default day count conventions
DEFAULT_DAY_COUNT: Final[str] = "ACT/360"
