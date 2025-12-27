# RTTY (Radioteletype)

RTTY uses frequency shift keying (FSK) to transmit Baudot-encoded text.

## Quick Start

```python
from pydigi import RTTY, save_wav

# Standard RTTY: 45.45 baud, 170 Hz shift
rtty = RTTY(baud=45.45, shift=170, frequency=1500)

# Generate audio
audio = rtty.modulate("RYRYRY THE QUICK BROWN FOX")

save_wav("rtty_test.wav", audio, sample_rate=rtty.sample_rate)
```

## Parameters

- `baud` (float): Baud rate (45, 45.45, 50, 75, 100)
- `shift` (float): Frequency shift in Hz (170, 200, 425, 850)
- `frequency` (float): Center frequency in Hz
- `sample_rate` (float): Sample rate in Hz (default: 8000)

## Common Configurations

### Standard RTTY (45.45 baud, 170 Hz)
```python
rtty = RTTY(baud=45.45, shift=170)
```

### Amateur Radio (45 baud, 170 Hz)
```python
rtty = RTTY(baud=45, shift=170)
```

### Weather FAX (50 baud, 450 Hz)
```python
rtty_wx = RTTY(baud=50, shift=450)
```

## Character Set

RTTY uses Baudot/ITA2 encoding:
- Uppercase letters only (A-Z)
- Numbers (0-9)
- Limited punctuation

Special characters not in Baudot are silently skipped.

## See Also

- [API Reference](../api/modems.md#rtty-radioteletype)
- [Basic Examples](../examples/basic.md)
