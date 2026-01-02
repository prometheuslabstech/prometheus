# Agent Best Practices and Anti-Patterns

This document outlines best practices and anti-patterns to follow when making changes to this project.

## Best Practices

### 1. Code Quality
- **Always use type hints** for function parameters and return values
- **Follow PEP 8** style guidelines (enforced by flake8 and black)
- **Write docstrings** for all public functions and classes
- **Keep functions small and focused** - single responsibility principle

### 2. Testing
- **Write tests** for all new functionality
- **Run tests** before committing changes: `pytest tests/`
- **Maintain test coverage** - aim for high coverage of critical paths
- **Test edge cases** and error conditions

### 3. Documentation
- **Update README.md** if adding new features or changing setup
- **Update DESIGNS.md** if making architectural changes
- **Update AGENTS.md** if making best practice or anti-pattern changes
- **Keep docstrings** up to date with code changes

### 4. Dependencies
- **Pin dependency versions** in requirements.txt when adding new packages
- **Test with Python 3.12+** only
- **Update requirements.txt** when adding or removing dependencies

## Anti-Patterns

### 1. Code Quality Anti-Patterns
- ❌ **Don't use `print()` for logging** - use the `logging` module
- ❌ **Don't ignore type hints** - always add them for better code clarity
- ❌ **Don't write functions without docstrings** - document your code
- ❌ **Don't create overly complex functions** - break them down

### 2. Testing Anti-Patterns
- ❌ **Don't skip tests** - write tests for new code
- ❌ **Don't commit failing tests** - ensure all tests pass
- ❌ **Don't test implementation details** - test behavior and outcomes

### 3. Project Structure Anti-Patterns
- ❌ **Don't add files to root** - use appropriate directories (src/, tests/, docs/)
- ❌ **Don't modify .gitignore** unnecessarily - keep it focused
- ❌ **Don't hardcode paths** - use relative imports and proper package structure

### 4. Python Version Anti-Patterns
- ❌ **Don't use Python < 3.12** - this project requires Python 3.12 or above
- ❌ **Don't use deprecated Python features** - use modern Python 3.12+ syntax

