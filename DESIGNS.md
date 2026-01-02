# Project Design and Structure

## Overview

Prometheus is a Python project template with a clean, professional structure designed for maintainability and scalability.

## Project Structure

```
Prometheus/
├── src/
│   └── prometheus/          # Main package directory
│       ├── __init__.py      # Package initialization
│       └── main.py          # Application entry point
├── tests/                    # Test suite
│   ├── __init__.py
│   └── test_main.py         # Tests for main module
├── docs/                     # Documentation directory
├── README.md                 # Project documentation
├── AGENTS.md                 # Best practices for agents
├── DESIGNS.md                # This file - project design documentation
├── requirements.txt          # Python dependencies
├── setup.py                  # Package installation configuration
├── pyproject.toml            # Tooling configuration (Black, pytest, mypy, flake8)
└── .gitignore                # Git ignore patterns
```

## Architecture

### Package Structure
- **`src/prometheus/`**: Contains the main application code
  - Uses the `src/` layout pattern for better test isolation
  - All source code is organized in the `prometheus` package

### Entry Point
- **`main.py`**: Contains the main entry point function
  - Configured as a console script in `setup.py`
  - Can be run via `python -m prometheus.main` or `prometheus` command

### Testing
- **`tests/`**: Contains all test files
  - Mirrors the structure of the source code
  - Uses pytest for testing framework
  - Includes coverage reporting

## Configuration

### Python Version
- **Requires Python 3.12 or above**
- Configured in `setup.py` and `pyproject.toml`

### Development Tools
- **Black**: Code formatting
- **flake8**: Linting
- **mypy**: Type checking
- **pytest**: Testing framework
- **pytest-cov**: Test coverage reporting

### Package Management
- **`setup.py`**: Defines package metadata and installation
- **`requirements.txt`**: Lists all dependencies
- **`pyproject.toml`**: Modern Python tooling configuration

## Design Principles

1. **Separation of Concerns**: Main logic, utilities, and tests are clearly separated
2. **Type Safety**: Type hints used throughout for better code clarity
3. **Testability**: Tests are organized and comprehensive
4. **Maintainability**: Clear structure and documentation
5. **Modern Python**: Uses Python 3.12+ features and best practices

