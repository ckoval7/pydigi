# PyPI Release Guide

This document describes how to build and release PyDigi to PyPI.

## Prerequisites

1. Install build tools:
   ```bash
   pip install build twine
   ```

2. Create accounts:
   - [PyPI Account](https://pypi.org/account/register/) - For production releases
   - [TestPyPI Account](https://test.pypi.org/account/register/) - For testing releases

3. Set up API tokens (recommended over passwords):
   - PyPI: https://pypi.org/manage/account/token/
   - TestPyPI: https://test.pypi.org/manage/account/token/

4. Configure `~/.pypirc` (optional but recommended):
   ```ini
   [distutils]
   index-servers =
       pypi
       testpypi

   [pypi]
   username = __token__
   password = pypi-YOUR-API-TOKEN-HERE

   [testpypi]
   username = __token__
   password = pypi-YOUR-TESTPYPI-API-TOKEN-HERE
   ```

## Pre-Release Checklist

Before releasing, ensure:

- [ ] All tests pass: `pytest`
- [ ] Code is formatted: `black pydigi/ tests/`
- [ ] Type checking passes: `mypy pydigi/`
- [ ] Version number is updated in:
  - [ ] `pyproject.toml`
  - [ ] `pydigi/__init__.py`
- [ ] `CHANGELOG.md` is updated (create if needed)
- [ ] Documentation is up to date
- [ ] All changes are committed to git
- [ ] Repository URLs in `pyproject.toml` are correct

## Version Numbering

PyDigi follows [Semantic Versioning](https://semver.org/):
- **Major** (X.0.0): Breaking changes
- **Minor** (0.X.0): New features, backward compatible
- **Patch** (0.0.X): Bug fixes, backward compatible

Pre-release versions:
- Alpha: `0.1.0a1`, `0.1.0a2`, ...
- Beta: `0.1.0b1`, `0.1.0b2`, ...
- Release Candidate: `0.1.0rc1`, `0.1.0rc2`, ...

## Building the Package

1. Clean previous builds:
   ```bash
   rm -rf dist/ build/ *.egg-info
   ```

2. Build source distribution and wheel:
   ```bash
   python -m build
   ```

   This creates:
   - `dist/pydigi-X.Y.Z.tar.gz` - Source distribution
   - `dist/pydigi-X.Y.Z-py3-none-any.whl` - Wheel distribution

3. Check the built package:
   ```bash
   twine check dist/*
   ```

   This validates:
   - Package metadata
   - README rendering on PyPI
   - Distribution formats

## Testing the Package Locally

Before uploading, test the package locally:

```bash
# Install from the built wheel
pip install dist/pydigi-X.Y.Z-py3-none-any.whl

# Or install from source distribution
pip install dist/pydigi-X.Y.Z.tar.gz

# Test in Python
python -c "import pydigi; print(pydigi.__version__)"
python -c "from pydigi import PSK31; print(PSK31)"
```

## Uploading to TestPyPI (Recommended First)

Test your package on TestPyPI before uploading to the real PyPI:

```bash
# Upload to TestPyPI
twine upload --repository testpypi dist/*

# Or without ~/.pypirc configuration:
twine upload --repository-url https://test.pypi.org/legacy/ dist/*
```

Install and test from TestPyPI:
```bash
# Create a fresh virtual environment
python -m venv test_env
source test_env/bin/activate  # On Windows: test_env\Scripts\activate

# Install from TestPyPI (use --extra-index-url for dependencies from PyPI)
pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ pydigi

# Test the installation
python -c "from pydigi import PSK31, save_wav; print('Success!')"

# Clean up
deactivate
rm -rf test_env
```

## Uploading to PyPI (Production)

Once tested on TestPyPI:

```bash
# Upload to PyPI
twine upload dist/*

# Or without ~/.pypirc configuration:
twine upload --repository-url https://upload.pypi.org/legacy/ dist/*
```

## Post-Release Steps

1. Create a git tag:
   ```bash
   git tag -a v0.1.0 -m "Release version 0.1.0"
   git push origin v0.1.0
   ```

2. Create a GitHub release:
   - Go to: https://github.com/yourusername/pydigi/releases/new
   - Select the tag you just created
   - Add release notes (copy from CHANGELOG.md)
   - Attach the distribution files from `dist/`

3. Update documentation if hosted separately

4. Announce the release:
   - GitHub Discussions
   - Social media
   - Relevant forums (ham radio communities, etc.)

## Common Issues

### Issue: "File already exists"
If you get this error, you're trying to upload a version that already exists on PyPI. PyPI doesn't allow overwriting releases. Solutions:
- Increment the version number
- Use a pre-release version (e.g., `0.1.1a1`)

### Issue: README not rendering correctly
- Ensure README.md is valid Markdown
- Check with: `twine check dist/*`
- Test locally by viewing on GitHub

### Issue: Missing files in distribution
- Check `MANIFEST.in` includes all necessary files
- Verify with: `tar -tzf dist/pydigi-X.Y.Z.tar.gz`
- Ensure `pyproject.toml` is properly configured

### Issue: Import errors after installation
- Ensure all `__init__.py` files exist
- Check that `__all__` exports are correct
- Verify dependencies are specified in `pyproject.toml`

## Quick Release Script

For experienced maintainers, here's a quick script:

```bash
#!/bin/bash
# release.sh - Quick release script (use with caution!)

set -e  # Exit on error

# Ensure we're on main branch
git checkout main
git pull

# Run tests
pytest

# Clean and build
rm -rf dist/ build/ *.egg-info
python -m build

# Check package
twine check dist/*

# Upload to TestPyPI first
echo "Uploading to TestPyPI..."
twine upload --repository testpypi dist/*

echo ""
echo "Please test from TestPyPI. If everything works, run:"
echo "  twine upload dist/*"
echo "  git tag -a vX.Y.Z -m 'Release version X.Y.Z'"
echo "  git push origin vX.Y.Z"
```

## Resources

- [Python Packaging User Guide](https://packaging.python.org/)
- [PyPI Help](https://pypi.org/help/)
- [Twine Documentation](https://twine.readthedocs.io/)
- [Semantic Versioning](https://semver.org/)
