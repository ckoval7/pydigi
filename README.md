# PyDigi

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Development Status](https://img.shields.io/badge/status-alpha-yellow.svg)](https://github.com/yourusername/pydigi)

**Pure Python implementation of digital modem algorithms from fldigi**

PyDigi is a Python library that reimplements digital mode modem algorithms from the popular [fldigi](http://www.w1hkj.com/) software. It provides a simple API for generating digital mode signals that can be used with GNU Radio, saved to WAV files, or used in other DSP applications.

**Status:** 100% Complete - 22/22 stable mode families implemented (~151 mode variants)

## Features

- **Pure Python Implementation**: No C++ dependencies, uses NumPy and SciPy for performance
- **Extensive Modem Support**: 22 mode families, ~151 mode variants implemented
- **Simple API**: Generate signals with a single function call
- **fldigi Validated**: All signals decode correctly in fldigi
- **Flexible Output**: Returns numpy arrays for integration with any audio pipeline
- **Comprehensive Documentation**: Full API docs and examples

## Installation

### From PyPI (Recommended - once published)

```bash
pip install pydigi
```

### From Source

Clone the repository:
```bash
git clone https://github.com/yourusername/pydigi.git
cd pydigi
```

Install the package:
```bash
pip install -e .
```

For development with testing tools:
```bash
pip install -e ".[dev]"
```

### Requirements

- Python 3.8 or later
- NumPy >= 1.20.0
- SciPy >= 1.7.0
- soundfile >= 0.10.0 (for WAV file support)

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

# Add silence padding (useful for PTT/VOX)
audio = modem.modulate("HELLO WORLD", leading_silence=0.5, trailing_silence=0.5)
save_wav("psk31_with_silence.wav", audio, sample_rate=8000)
```

### WEFAX (Weather Facsimile) - Text & Images
```python
from pydigi import WEFAX576, save_wav

modem = WEFAX576()

# Transmit text (automatically rendered as image)
text = """MARINE WEATHER FORECAST
Winds: NE 10-15 kt
Waves: 2-3 ft
Weather: Partly cloudy"""

audio = modem.modulate(text)
save_wav("wefax_text.wav", audio, sample_rate=11025)

# Or transmit images
import numpy as np
img = np.random.randint(0, 256, (200, 1809), dtype=np.uint8)
audio = modem.transmit_image(img)
save_wav("wefax_image.wav", audio, sample_rate=11025)
```

All generated WAV files can be decoded in fldigi!

See the [examples/](examples/) directory for more complete examples of each modem type.

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

### Phase Shift Keying (PSK) - 47 variants ✅
- **BPSK**: PSK31, PSK63, PSK125, PSK250, PSK500, PSK1000
- **QPSK**: QPSK31, QPSK63, QPSK125, QPSK250, QPSK500
- **8PSK**: 8PSK125, 8PSK250, 8PSK500, 8PSK1000
- **8PSK FEC**: 8PSK125F/FL, 8PSK250F/FL, 8PSK500F, 8PSK1000F, 8PSK1200F
- **Multi-carrier PSK**: 6 standard variants
- **Multi-carrier PSK-R**: 27 variants with soft-symbol FEC

### Multi-Frequency Shift Keying (MFSK) - 67 variants ✅
- **MFSK**: MFSK4, MFSK8, MFSK11, MFSK16, MFSK22, MFSK31, MFSK32, MFSK64, MFSK128
- **Olivia**: 7 configurations (4/125, 8/250, 8/500, 16/500, 16/1000, 32/1000)
- **Contestia**: 7 configurations (4/125, 4/250, 8/125, 8/250, 8/500, 16/500, 32/1000)
- **DominoEX**: 10 variants (Micro, 4, 5, 8, 11, 16, 22, 44, 88)
- **Thor**: 16 variants (Micro, 4, 5, 8, 11, 16, 22, 25, 32, 44, 56, 25x4, 50x1, 50x2, 100)
- **MT63**: 6 variants (MT63-500/1000/2000, Short/Long interleaver)

### Other Modes - 37 variants ✅
- **CW (Morse Code)** - Variable speed (5-200 WPM), prosign support, edge shaping
- **RTTY (Radioteletype)** - Multiple baud rates and shifts, ITA-2 and US-TTY
- **Hellschreiber**: 8 variants (Feld Hell, Slow Hell, HellX5/X9, FSK Hell 105/245, Hell80)
- **Throb**: 6 variants (Throb1/2/4, ThrobX1/X2/X4)
- **FSQ**: 3 variants (FSQ-2, FSQ-3, FSQ-6)
- **IFKP**: 3 variants (IFKP-0.5, IFKP-1.0, IFKP-2.0)
- **SCAMP**: 6 variants (SCAMPFSK, SCAMPOOK, SCFSKFST, SCFSKSLW, SCOOKSLW, SCFSKVSL)
- **NAVTEX/SITOR-B**: 2 variants (NAVTEX with headers, SITOR-B raw mode)
- **WEFAX (Weather Facsimile)**: 2 variants (WEFAX-576, WEFAX-288) - Image & text transmission mode

**Total: 22 mode families, ~151 mode variants - All validated and decode correctly in fldigi!**

## Project Status

**Current Status: 100% Complete - All 22 stable mode families implemented!**

- ✅ **Core DSP infrastructure** - Filters, oscillators, FEC encoders
- ✅ **22 mode families** - CW, RTTY, PSK (all variants), QPSK, 8PSK, 8PSK FEC, Multi-carrier PSK/PSK-R, MFSK, Olivia, Contestia, DominoEX, Thor, Throb, Hell, FSQ, MT63, IFKP, SCAMP, NAVTEX/SITOR-B, WEFAX
- ✅ **~151 mode variants** - All decode correctly in fldigi
- ⏳ **RX (receive/decode)** - Future enhancement
- 🎉 **All stable fldigi TX modes complete!**

See [PROJECT_TRACKER.md](PROJECT_TRACKER.md) for detailed implementation status and development roadmap.

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

## Documentation

Full documentation is available in the [docs/](docs/) directory and can be built with MkDocs:

```bash
pip install mkdocs mkdocs-material
mkdocs serve
```

Quick references:
- [Quick Start Guide](QUICKSTART.md) - Get started quickly
- [API Standard](API_STANDARD.md) - API conventions and usage
- [Project Tracker](PROJECT_TRACKER.md) - Detailed implementation status

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

### Building Documentation

```bash
mkdocs build
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

Contributions are welcome! We're actively working on:
- Adding receive/decode functionality
- Improving documentation and examples
- Bug fixes and optimizations
- Performance enhancements

Please see the [PROJECT_TRACKER.md](PROJECT_TRACKER.md) for detailed development priorities and status.

### How to Contribute

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/new-modem`)
3. Make your changes and add tests
4. Ensure tests pass (`pytest`)
5. Format your code (`black pydigi/`)
6. Submit a pull request

For questions or discussions, please open an issue on GitHub.

## Acknowledgments

PyDigi is based on the excellent work of the [fldigi](http://www.w1hkj.com/) project, particularly:
- Dave Freese, W1HKJ
- And all fldigi contributors

## Resources

- [fldigi Homepage](http://www.w1hkj.com/)
- [fldigi Documentation](http://www.w1hkj.com/FldigiHelp/)
- [Digital Mode Information](https://en.wikipedia.org/wiki/Radioteletype)
