# Development guide for Prometheus

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Development

### Run Tests
```bash
pytest tests/
```

### Run Integration Tests
```bash
export AWS_ACCESS_KEY_ID="your-access-key-id"
export AWS_SECRET_ACCESS_KEY="your-secret-access-key"
export AWS_DEFAULT_REGION="us-west-2"  # Optional: set default region

pytest tests/ --run-integration
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
pip install setuptools wheel
python setup.py sdist bdist_wheel
```

### Verify MCP server runs
```bash
pip install -e .
prometheus research
prometheus analysis
```