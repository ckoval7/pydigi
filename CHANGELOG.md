# Changelog

All notable changes to PyDigi will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned
- Receive/decode functionality for all implemented modes
- Additional modem families: WEFAX, NAVTEX, SITOR-B, OFDM
- Performance optimizations for real-time applications
- Enhanced documentation and examples

## [0.1.0] - TBD

### Added
- Initial release of PyDigi
- Pure Python implementation of 20 modem families (~147 mode variants)
- **CW (Morse Code)**: Variable speed (5-200 WPM), prosign support
- **RTTY**: Multiple baud rates and shifts, ITA-2 and US-TTY support
- **PSK modes**: BPSK (31/63/125/250/500/1000), QPSK (31/63/125/250/500)
- **8PSK modes**: 125/250/500/1000, with FEC variants
- **Multi-carrier PSK**: 6 standard variants
- **Multi-carrier PSK-R**: 27 variants with soft-symbol FEC
- **MFSK**: 9 variants (MFSK4/8/11/16/22/31/32/64/128)
- **Olivia**: 7 configurations (4/125, 8/250, 8/500, 16/500, 16/1000, 32/1000)
- **Contestia**: 7 configurations (4/125, 4/250, 8/125, 8/250, 8/500, 16/500, 32/1000)
- **DominoEX**: 10 variants (Micro, 4, 5, 8, 11, 16, 22, 44, 88)
- **Thor**: 16 variants (Micro through 100, including multi-tone variants)
- **MT63**: 6 variants (500/1000/2000, Short/Long interleaver)
- **Hellschreiber**: 8 variants (Feld Hell, Slow Hell, HellX5/X9, FSK Hell, Hell80)
- **Throb**: 6 variants (Throb1/2/4, ThrobX1/X2/X4)
- **FSQ**: 3 variants (FSQ-2, FSQ-3, FSQ-6)
- **IFKP**: 3 variants (IFKP-0.5, IFKP-1.0, IFKP-2.0)
- **SCAMP**: 6 variants (FSK and OOK modes)
- Simple API: `modem.modulate(text, frequency, sample_rate)`
- Audio utilities: `save_wav()` and `load_wav()`
- Resampler utility: High-quality sample rate conversion for all modems
  - Supports polyphase and FFT-based resampling methods
  - Convenient presets for common conversions (8k→48k, 8k→44.1k, etc.)
  - Modem-aware automatic resampling
  - Quality analysis and method recommendations
- Signal analyzer utility for debugging and analysis
- Comprehensive examples for all modem families
- Full documentation with MkDocs

### Validated
- All generated signals decode correctly in fldigi
- Extensive testing against fldigi reference implementation
- Signal analysis and spectrum verification

## Release Notes

### Version 0.1.0 - Initial Release

This is the first public release of PyDigi, featuring transmit (TX) functionality for 20 modem families. The library is based on the fldigi source code and has been extensively tested to ensure all generated signals decode correctly in fldigi.

**Key Features:**
- Pure Python implementation using NumPy and SciPy
- No C++ dependencies or external binaries required
- Compatible with Python 3.8+
- Simple, intuitive API
- Flexible output for integration with GNU Radio, file I/O, or custom applications

**Current Limitations:**
- TX (transmit) only - RX (receive/decode) planned for future releases
- Some specialty modes not yet implemented (WEFAX, NAVTEX, SITOR-B, OFDM)
- Documentation is still evolving

**Getting Started:**
See [QUICKSTART.md](QUICKSTART.md) for quick start guide and [examples/](examples/) for comprehensive examples.

---

[Unreleased]: https://github.com/yourusername/pydigi/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/yourusername/pydigi/releases/tag/v0.1.0
