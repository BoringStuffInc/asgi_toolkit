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
    ruff format --check src/ tests/

# Format code using ruff
# Automatically formats Python code in source and test directories
format:
    ruff format src/ tests/

# Run comprehensive code quality checks
# Combines linting, type checking, and testing
check: lint typecheck

# Build distribution packages
# Uses uv to build project distribution files
build:
    uv build
