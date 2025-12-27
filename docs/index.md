# PyDigi - Python Digital Modem Library

PyDigi is a pure Python library for generating digital amateur radio signals. It provides clean, simple APIs for creating modulated audio that can be used with GNU Radio, saved to WAV files, or integrated into other radio applications.

## Features

- **Pure Python implementation** - No compiled dependencies, easy to understand and modify
- **Extensive modem support** - 20 mode families, ~147 mode variants
- **Clean API** - Simple `modulate(text)` interface returns audio samples
- **fldigi compatible** - All generated signals decode correctly in fldigi
- **Flexible output** - Returns numpy arrays for use with GNU Radio, WAV files, or direct audio playback
- **Comprehensive documentation** - Full API docs with clear examples
- **Advanced features** - FEC encoding (Golay, Viterbi, Reed-Solomon), interleaving, Gray coding

## Quick Example

```python
from pydigi import PSK31, save_wav

# Create a PSK31 modem
psk = PSK31(frequency=1000)

# Generate audio from text
audio = psk.modulate("CQ CQ CQ DE W1ABC")

# Save to WAV file
save_wav("output.wav", audio, sample_rate=8000)
```

## Supported Modes

### Phase Shift Keying (PSK) - 47 variants
- **BPSK**: PSK31, PSK63, PSK125, PSK250, PSK500, PSK1000
- **QPSK**: QPSK31, QPSK63, QPSK125, QPSK250, QPSK500
- **8PSK**: 8PSK125, 8PSK250, 8PSK500, 8PSK1000
- **8PSK with FEC**: 8PSK125F/FL, 8PSK250F/FL, 8PSK500F, 8PSK1000F, 8PSK1200F
- **Multi-carrier PSK**: 6 standard variants
- **Multi-carrier PSK-R**: 27 variants with soft-symbol FEC

### Multi-Frequency Shift Keying (MFSK) - 67 variants
- **MFSK**: MFSK4, MFSK8, MFSK11, MFSK16, MFSK22, MFSK31, MFSK32, MFSK64, MFSK128
- **Olivia**: Olivia 4/125, 8/250, 8/500, 16/500, 16/1000, 32/1000
- **Contestia**: Contestia 4/125, 4/250, 8/125, 8/250, 8/500, 16/500, 32/1000
- **DominoEX**: Micro, 4, 5, 8, 11, 16, 22, 44, 88
- **Thor**: Micro, 4, 5, 8, 11, 16, 22, 25, 32, 44, 56, 25x4, 50x1, 50x2, 100
- **MT63**: MT63-500/1000/2000 (Short/Long interleaver)

### Other Modes - 33 variants
- **CW** (Morse Code) - Variable WPM with prosign support
- **RTTY** (Radioteletype) - Baudot encoding with configurable shift
- **Hell** (Hellschreiber) - Feld Hell, Slow Hell, HellX5/X9, FSK Hell
- **Throb** - Throb1, Throb2, Throb4, ThrobX1/X2/X4
- **FSQ** - FSQ-2, FSQ-3, FSQ-6
- **IFKP** - IFKP-0.5, IFKP-1.0, IFKP-2.0 (Incremental Frequency Keying with FEC)
- **SCAMP** - SCAMPFSK, SCAMPOOK, SCFSKFST, SCFSKSLW, SCOOKSLW, SCFSKVSL (Golay FEC)

**Total: 20 mode families, ~147 mode variants**

## Design Philosophy

PyDigi is designed to be:

1. **Simple** - Each modem has a straightforward API: create, configure, modulate
2. **Understandable** - Pure Python code based directly on fldigi's reference implementation
3. **Flexible** - Returns numpy arrays that work with any audio pipeline
4. **Correct** - All modes verified to decode in fldigi

## Use Cases

- **Software Defined Radio** - Generate baseband signals for GNU Radio or other SDR frameworks
- **Testing** - Create test signals for decoder validation
- **Education** - Learn how digital modes work with readable Python code
- **Experimentation** - Try new parameters or create hybrid modes
- **Automation** - Batch generate signals for automated testing

## Project Status

PyDigi implements modulation (TX) for all supported modes. Most modes decode correctly in fldigi. Demodulation (RX) support is planned for future releases.

## Getting Started

1. [Install PyDigi](installation.md)
2. Try the [Quick Start](quickstart.md) examples
3. Browse the [API Reference](api/overview.md) to see all available modem modes
4. Check out the [User Guide](examples/basic.md) for usage examples

## License

PyDigi is open source software. See the repository for license details.
