# Prometheus

A Python project template with a clean, professional structure.

## Development

### Run Tests
```bash
pytest tests/
```

### Check Linting
```bash
flake8 src/ tests/
```

### Format Code
```bash
black src/ tests/
```

### Type Checking
```bash
mypy src/
```

### Verify Package Compiles
```bash
python -m py_compile src/prometheus/*.py
```

### Build Package
```bash
python setup.py sdist bdist_wheel
```
