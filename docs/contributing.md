# Contributing to PyDigi

Thank you for your interest in contributing to PyDigi! This guide will help you get started.

## Development Setup

1. Clone the repository:
```bash
git clone https://github.com/yourusername/pydigi.git
cd pydigi
```

2. Install in development mode with dependencies:
```bash
pip install -e ".[dev]"
```

3. Run tests to verify setup:
```bash
pytest
```

## Project Structure

```
pydigi/
├── pydigi/
│   ├── modems/          # Modem implementations
│   ├── core/            # DSP building blocks
│   ├── utils/           # Audio utilities
│   └── varicode/        # Character encoding
├── tests/               # Test suite
├── fldigi/             # Reference implementation (read-only)
└── docs/               # Documentation
```

## Adding a New Modem

1. **Study the fldigi reference** (`fldigi/src/`)
   - Find the modulation math and parameters
   - Note preamble/postamble requirements (see CLAUDE.md)
   - Check character encoding scheme

2. **Create the modem class** in `pydigi/modems/`
   - Inherit from `pydigi.modems.base.Modem`
   - Implement `modulate()` method
   - Add comprehensive docstrings (Google style)

3. **Add character encoding** (if needed) in `pydigi/varicode/`

4. **Write tests** in `tests/`
   - Basic modulation test
   - Parameter validation
   - Character encoding verification

5. **Update documentation**
   - Add to appropriate API reference page
   - Include usage examples in docstrings

6. **Export from main package** in `pydigi/__init__.py`

## Code Style

- Follow PEP 8 style guidelines
- Use type hints for function signatures
- Write Google-style docstrings
- Keep functions focused and modular

## Testing

Run the test suite:
```bash
# All tests
pytest

# Specific mode
pytest tests/test_psk.py

# With coverage
pytest --cov=pydigi
```

## Documentation

Build documentation locally:
```bash
mkdocs serve
```

Then open http://127.0.0.1:8000 in your browser.

Documentation is automatically generated from docstrings using mkdocstrings. Focus on writing clear, comprehensive docstrings in your code.

## Pull Request Process

1. Create a feature branch from `main`
2. Make your changes with clear commit messages
3. Add/update tests as needed
4. Update documentation (docstrings)
5. Ensure all tests pass
6. Submit a pull request with description of changes

## Questions?

Open an issue on GitHub or join the discussion in existing issues.

## License

By contributing, you agree that your contributions will be licensed under the same license as the project.
