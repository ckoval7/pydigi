# FLARQ ARQ Protocol - Dependencies

## Required Dependencies

### crcmod >= 1.7

**Purpose**: CRC-16-MODBUS calculation for frame checksums

**Why**: fldigi uses CRC-16 with polynomial 0xA001 and init 0xFFFF, which is the standard CRC-16-MODBUS algorithm. The `crcmod` library provides a well-tested, industry-standard implementation.

**Usage**:
```python
import crcmod

# Create CRC-16-MODBUS calculator (matches fldigi exactly)
crc_func = crcmod.predefined.mkCrcFun('modbus')
crc_value = crc_func(b"Hello")
print(f"{crc_value:04X}")  # "F377"
```

**Install**:
```bash
pip install crcmod
```

**Alternatives Considered**:
- ❌ Manual implementation: Unnecessary when standard variant exists
- ❌ Other CRC libraries: `crcmod` is the most widely used for Python
- ✅ `crcmod`: Industry standard, well-tested, predefined MODBUS variant

**References**:
- PyPI: https://pypi.org/project/crcmod/
- MODBUS CRC specification: https://en.wikipedia.org/wiki/Modbus

### Existing PyDigi Dependencies

These are already required by pydigi:

- **numpy >= 1.20.0** - Audio signal processing
- **scipy >= 1.7.0** - Digital signal processing
- **typing-extensions >= 4.0.0** - Type hints

## Development Dependencies

Already in pydigi's requirements:

- **pytest >= 7.0.0** - Testing framework
- **pytest-cov >= 3.0.0** - Test coverage
- **black >= 22.0.0** - Code formatting
- **mypy >= 0.950** - Type checking

## Installation

### Full Installation

Install all dependencies including ARQ support:

```bash
pip install -r requirements.txt
```

### Minimal Installation (ARQ only)

If you only need ARQ support:

```bash
pip install numpy scipy crcmod
```

## Dependency Graph

```
pydigi.arq
├── crcmod (NEW - for CRC-16-MODBUS)
├── numpy (existing)
├── scipy (existing)
└── typing-extensions (existing)
```

## Version Compatibility

- **Python**: 3.8+ (same as pydigi)
- **crcmod**: 1.7+ (current stable is 1.7)
  - Works with Python 3.8-3.12
  - C extension optional (pure Python fallback)

## License Compatibility

- **pydigi**: GPL-3.0 (based on fldigi)
- **crcmod**: MIT License ✅ Compatible with GPL-3.0
- **numpy**: BSD License ✅ Compatible with GPL-3.0
- **scipy**: BSD License ✅ Compatible with GPL-3.0

All dependencies are compatible with pydigi's GPL-3.0 license.

## Performance Notes

### crcmod Performance

- **Pure Python**: ~1-2 µs per frame CRC calculation
- **With C extension**: ~0.1-0.5 µs per frame CRC calculation
- Either is fast enough for ARQ (frames sent every 100ms minimum)

Install C extension for best performance:
```bash
pip install crcmod
# If C compiler available, it will build C extension automatically
```

Check if C extension is installed:
```python
import crcmod
print(crcmod.predefined._usingExtension)  # True = C extension
```

## Optional Dependencies

None required for basic ARQ functionality.

Future optional dependencies might include:
- **soundfile** (already optional in pydigi) - For saving/loading audio files
- **matplotlib** (visualization) - For debugging frame timing

## Updating Dependencies

When updating, maintain minimum versions in `requirements.txt`:

```
# Core dependencies
numpy>=1.20.0
scipy>=1.7.0
typing-extensions>=4.0.0

# ARQ protocol support
crcmod>=1.7
```

This ensures compatibility while allowing users to get bug fixes and improvements.
