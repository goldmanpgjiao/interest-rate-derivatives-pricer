# Development Workflow

## Phase 1: Environment Setup with uv

### Step 1: Install uv (if not already installed)

```bash
# Install uv using the recommended method
curl -LsSf https://astral.sh/uv/install.sh | sh

# Or using Homebrew (macOS)
brew install uv

# Or using pip
pip install uv
```

### Step 2: Initialize Python Project with uv

```bash
# Create a new Python project with uv
uv init --name montecarlo_ir --lib

# This creates:
# - pyproject.toml (with project metadata and dependencies)
# - src/montecarlo_ir/ (package directory)
# - tests/ (test directory)
# - README.md
```

### Step 3: Set Python Version

```bash
# Pin Python version (recommended: 3.11 or 3.12)
uv python pin 3.12

# Or specify in pyproject.toml under [project] -> requires-python = ">=3.11"
```

### Step 4: Install Core Dependencies

```bash
# Add core dependencies for quantitative finance
uv add numpy scipy
uv add pandas
uv add matplotlib  # For plotting and visualization
uv add jupyter  # For notebook examples

# Optional: For advanced features
uv add jax jaxlib  # For autodiff and GPU acceleration
uv add quantlib-python  # For QuantLib integration (optional)

# Development dependencies
uv add --dev pytest pytest-cov black mypy ruff
uv add --dev ipykernel  # For Jupyter notebook support
```

### Step 5: Create Project Structure

```bash
# Create directory structure as per PRD
mkdir -p src/montecarlo_ir/{models,products,pricing,calibration,market_data,utils}
mkdir -p tests
mkdir -p notebooks
mkdir -p docs
```

### Step 6: Configure Development Tools

```bash
# Create .gitignore
cat > .gitignore << EOF
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Virtual environments
.venv/
venv/
ENV/
env/

# IDE
.vscode/
.idea/
*.swp
*.swo
*~

# Jupyter
.ipynb_checkpoints/
*.ipynb_checkpoints

# Testing
.pytest_cache/
.coverage
htmlcov/
.tox/

# Documentation
docs/_build/
docs/.doctrees/

# OS
.DS_Store
Thumbs.db

# uv
.uv/
EOF

# Create pyproject.toml configuration sections
```

---

## Phase 2: Project Configuration

### Step 7: Configure pyproject.toml

Update `pyproject.toml` with:
- Project metadata
- Build system configuration
- Tool configurations (black, mypy, ruff, pytest)

### Step 8: Create Initial Package Files

- `src/montecarlo_ir/__init__.py` - Package initialization
- `src/montecarlo_ir/config.py` - Global configuration
- `src/montecarlo_ir/logger.py` - Logging setup

---

## Phase 3: Core Development (Iterative)

### Development Order (Recommended):

1. **Foundation Layer** (Week 1-2)
   - `utils/date_helpers.py` - Date handling utilities
   - `market_data/yield_curve.py` - Yield curve construction
   - `market_data/vol_surface.py` - Volatility surface handling
   - `config.py` and `logger.py` - Infrastructure

2. **Models Layer** (Week 3-5)
   - `models/hull_white.py` - Hull-White 1F model
   - `models/lmm.py` - LIBOR Market Model
   - `models/sabr_lmm.py` - SABR-LMM hybrid (optional)

3. **Calibration Layer** (Week 6-7)
   - `calibration/hw_calibrator.py` - Hull-White calibration
   - `calibration/lmm_calibrator.py` - LMM calibration

4. **Pricing Engine** (Week 8-9)
   - `pricing/mc_engine.py` - Core Monte Carlo engine
   - `pricing/lsm_pricer.py` - Least Squares Monte Carlo

5. **Products Layer** (Week 10-13)
   - `products/interest_rate_swap.py` - Vanilla IRS
   - `products/cap_floor.py` - Cap/Floor products
   - `products/european_swaption.py` - European swaptions
   - `products/bermudan_swaption.py` - Bermudan swaptions
   - `products/range_accrual.py` - Range accrual notes
   - `products/callable_note.py` - Callable notes

6. **Pricers** (Week 14-15)
   - `pricing/product_pricers.py` - Product-specific pricers
   - Integration with MC engine

7. **Testing** (Ongoing)
   - Unit tests alongside development
   - Integration tests
   - Validation against analytical formulas

8. **Documentation** (Ongoing)
   - Docstrings for all modules
   - README.md updates
   - Jupyter notebook examples

---

## Phase 4: Daily Development Workflow

### Starting a Development Session

```bash
# Activate uv environment
uv sync

# Run tests
uv run pytest

# Run type checking
uv run mypy src/

# Run linter
uv run ruff check src/

# Format code
uv run black src/ tests/

# Start Jupyter notebook
uv run jupyter notebook notebooks/
```

### Adding New Dependencies

```bash
# Add a new dependency
uv add package-name

# Add a development dependency
uv add --dev package-name

# Update all dependencies
uv sync --upgrade
```

### Running Tests

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=src/montecarlo_ir --cov-report=html

# Run specific test file
uv run pytest tests/test_models.py

# Run with verbose output
uv run pytest -v
```

### Code Quality Checks

```bash
# Type checking
uv run mypy src/

# Linting
uv run ruff check src/ tests/

# Format checking
uv run black --check src/ tests/

# Auto-fix issues
uv run ruff check --fix src/ tests/
uv run black src/ tests/
```

---

## Phase 5: Building and Distribution

### Build Package

```bash
# Build distribution
uv build

# This creates dist/ directory with wheel and source distribution
```

### Install Locally for Testing

```bash
# Install in development mode
uv pip install -e .

# Or use uv sync (already handles editable install)
```

---

## Recommended Development Practices

1. **Type Hints**: Always use type hints for function parameters and return types
2. **Docstrings**: Use Google-style or NumPy-style docstrings for all public functions/classes
3. **Testing**: Write tests alongside code (TDD approach)
4. **Commits**: Make frequent, atomic commits
5. **Code Review**: Review code before merging to main branch
6. **Documentation**: Update documentation as you develop

---

## Quick Reference Commands

```bash
# Environment
uv sync                    # Sync dependencies
uv python pin 3.12        # Pin Python version
uv add package            # Add dependency
uv remove package         # Remove dependency

# Development
uv run pytest             # Run tests
uv run mypy src/          # Type check
uv run black src/         # Format code
uv run ruff check src/    # Lint code

# Jupyter
uv run jupyter notebook   # Start Jupyter
uv run jupyter lab        # Start JupyterLab

# Building
uv build                  # Build package
```

---

## Phase 6: Git Workflow

### Initial Setup

```bash
# Initialize git repository (if not already done)
git init

# Add remote repository
git remote add origin https://github.com/yourusername/interest-rate-derivatives-pricer.git

# Verify remote
git remote -v
```

### Making Commits

```bash
# Check status
git status

# Stage changes
git add .

# Or stage specific files
git add src/montecarlo_ir/models/hull_white.py
git add tests/test_models.py

# Commit with descriptive message
git commit -m "feat: implement Hull-White 1F model with exact simulation"

# Push to remote
git push -u origin master
# Or if using main branch
git push -u origin master:main
```

### Commit Message Convention

Use conventional commit messages:
- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation changes
- `test:` - Test additions or changes
- `refactor:` - Code refactoring
- `chore:` - Maintenance tasks
- `style:` - Code style changes (formatting, etc.)

Examples:
```bash
git commit -m "feat: add yield curve interpolation methods"
git commit -m "fix: correct day count convention in IRS cashflows"
git commit -m "test: add unit tests for Hull-White calibration"
git commit -m "docs: update README with usage examples"
```

### Branching Strategy

```bash
# Create feature branch
git checkout -b feature/hull-white-model

# Work on feature, commit changes
git add .
git commit -m "feat: implement Hull-White model"

# Push feature branch
git push -u origin feature/hull-white-model

# Merge to main (after review)
git checkout master
git merge feature/hull-white-model
git push origin master
```

### Keeping Up to Date

```bash
# Fetch latest changes
git fetch origin

# Pull latest changes
git pull origin master

# Rebase feature branch on latest main
git checkout feature/your-feature
git rebase master
```

---

## Next Steps

1. ✅ Execute Phase 1: Environment Setup (COMPLETED)
2. ✅ Initialize the project structure (COMPLETED)
3. ✅ Set up initial configuration files (COMPLETED)
4. Begin with Foundation Layer development

---

## Progress Tracking

See `PROGRESS.md` for detailed progress tracking and task status.

