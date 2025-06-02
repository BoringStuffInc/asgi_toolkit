# Justfile for ASGI Toolkit Development
# This file provides convenient commands for project management and development

# List all available commands
default:
    @just --list

# Create virtual environment and install project dependencies
# Uses uv to manage virtual environment and synchronize dependencies
install:
    uv venv
    uv sync --dev

# Run project test suite using pytest
# Executes all tests in the 'tests/' directory
test:
    pytest tests/

# Perform static type checking using mypy
# Checks type annotations in the 'src/' directory
typecheck:
    mypy src/

# Run linter to check code quality
lint:
    ruff check src/

# Format code using ruff
# Automatically formats Python code in source and test directories
format:
    ruff format src/ tests/

# Automatically fix linting issues
# Applies automatic fixes for both code style and formatting
lint-fix:
    ruff check --fix src/ tests/
    ruff format src/ tests/

# Run comprehensive code quality checks
# Combines linting, type checking, and testing
check: lint typecheck test

# Clean up project artifacts and temporary files
# Removes cache files, build artifacts, and other generated files
clean:
    find . -type d -name "__pycache__" -exec rm -rf {} +
    find . -type f -name "*.pyc" -delete
    find . -type f -name "*.pyo" -delete
    find . -type f -name "*.pyd" -delete
    find . -type f -name "*.so" -delete
    find . -type d -name "*.egg-info" -exec rm -rf {} +
    find . -type d -name "*.egg" -exec rm -rf {} +
    rm -rf .venv/ build/ dist/ .pytest_cache/ .coverage htmlcov/

# Build distribution packages
# Uses uv to build project distribution files
build:
    uv build
