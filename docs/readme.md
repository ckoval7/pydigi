# PyDigi

**Pure Python implementation of digital modem algorithms from fldigi**

PyDigi is a Python library that reimplements digital mode modem algorithms from the popular [fldigi](http://www.w1hkj.com/) software. It provides a simple API for generating digital mode signals that can be used with GNU Radio, saved to WAV files, or used in other DSP applications.

## Features

- **Pure Python Implementation**: No C++ dependencies, uses NumPy and SciPy for performance
- **Simple API**: Generate signals with a single function call
- **Multiple Modems**: Support for CW, RTTY, PSK31, MFSK16, and more (in development)
- **Flexible Output**: Returns numpy arrays for integration with any audio pipeline
- **Reference Validated**: All signals are validated against fldigi for correctness

## Installation

```bash
pip install -e .
```

For development with testing tools:
```bash
pip install -e ".[dev]"
```

For audio file support:
```bash
pip install -e ".[audio]"
```

## Quick Start

### CW (Morse Code)
```python
from pydigi import CW, save_wav

modem = CW(wpm=20)
audio = modem.modulate("CQ CQ CQ DE W1ABC", frequency=800)
save_wav("cw_output.wav", audio, sample_rate=8000)
```

### RTTY
```python
from pydigi import RTTY, save_wav

modem = RTTY(baud=45.45, shift=170)
audio = modem.modulate("RYRYRY THE QUICK BROWN FOX", frequency=1500)
save_wav("rtty_output.wav", audio, sample_rate=8000)
```

### PSK31
```python
from pydigi import PSK31, save_wav

modem = PSK31()
audio = modem.modulate("HELLO WORLD", frequency=1000)
save_wav("psk31_output.wav", audio, sample_rate=8000)
```

All generated WAV files can be decoded in fldigi!

### Multiple Modes Example

```python
from pydigi import CW, RTTY, PSK31, PSK63, PSK125, save_wav

# CW at 20 WPM
cw = CW(wpm=20)
audio_cw = cw.modulate("CQ DE W1ABC", frequency=800)
save_wav("output_cw.wav", audio_cw, 8000)

# RTTY at 45.45 baud
rtty = RTTY(baud=45.45, shift=170)
audio_rtty = rtty.modulate("HELLO WORLD", frequency=1500)
save_wav("output_rtty.wav", audio_rtty, 8000)

# PSK31
psk31 = PSK31()
audio_psk = psk31.modulate("TEST PSK31", frequency=1000)
save_wav("output_psk31.wav", audio_psk, 8000)
```

## Supported Modems

### Currently Implemented ✅
- **CW (Morse Code)** - Variable speed (5-200 WPM), prosign support, edge shaping
- **RTTY** - Multiple baud rates (45, 45.45, 50, 75, 100+), multiple shifts (170, 200, 425, 850 Hz), ITA-2 and US-TTY
- **PSK31/63/125/250/500** - Binary PSK with differential encoding and varicode

**All modes validated and decode correctly in fldigi!**

### Planned
- **MFSK16** - Multi-frequency shift keying with FEC
- **DominoEX** - IFK+ modulation
- **Olivia** - Robust MFSK with heavy FEC
- **Contestia** - Similar to Olivia with different parameters
- **QPSK/8PSK** - Higher-order PSK modes

## Project Status

PyDigi implements modulation (TX) for 151+ modem variants across 22 mode families. All modes decode correctly in fldigi. Demodulation (RX) support is planned for future releases.

## Architecture

PyDigi is structured as follows:

```
pydigi/
├── core/          # DSP building blocks (filters, oscillators, FFT)
├── varicode/      # Character encoding tables (Baudot, PSK varicode, etc.)
├── modems/        # Modem implementations (CW, RTTY, PSK, MFSK, etc.)
└── utils/         # Helper utilities (audio I/O, constants, etc.)
```

Each modem inherits from a base `Modem` class and implements:
- `tx_init()`: Initialize transmitter
- `tx_process()`: Process symbols and generate audio
- `modulate(text, frequency, sample_rate)`: High-level API

## Development

### Running Tests

```bash
pytest
```

### Code Formatting

```bash
black pydigi/ tests/
```

### Type Checking

```bash
mypy pydigi/
```

## Reference

PyDigi reimplements algorithms from the fldigi source code. The fldigi source is included in the `fldigi/` directory for reference purposes only and is not modified.

Key reference files:
- `fldigi/src/include/modem.h` - Base modem interface
- `fldigi/src/cw/cw.cxx` - CW implementation
- `fldigi/src/rtty/rtty.cxx` - RTTY implementation
- `fldigi/src/psk/psk.cxx` - PSK implementation

## License

PyDigi is licensed under the GNU General Public License v3.0 or later (GPL-3.0+), the same license as fldigi.

## Contributing

Contributions are welcome! Please see the [Contributing Guide](contributing.md) for guidelines.

## Acknowledgments

PyDigi is based on the excellent work of the [fldigi](http://www.w1hkj.com/) project, particularly:
- Dave Freese, W1HKJ
- And all fldigi contributors

## Resources

- [fldigi Homepage](http://www.w1hkj.com/)
- [fldigi Documentation](http://www.w1hkj.com/FldigiHelp/)
- [Digital Mode Information](https://en.wikipedia.org/wiki/Radioteletype)
