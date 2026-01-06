# PyDigi - Python Digital Modem Library

PyDigi is a pure Python library for generating digital amateur radio signals. It provides clean, simple APIs for creating modulated audio that can be used with GNU Radio, saved to WAV files, or integrated into other radio applications.

## Features

- **Pure Python implementation** - No compiled dependencies, easy to understand and modify
- **Extensive modem support** - 22 mode families, ~151 mode variants
- **Clean API** - Simple `modulate(text)` interface returns audio samples
- **fldigi compatible** - All generated signals decode correctly in fldigi
- **Flexible output** - Returns numpy arrays for use with GNU Radio, WAV files, or direct audio playback
- **Comprehensive documentation** - Full API docs with clear examples
- **Advanced features** - FEC encoding (Golay, Viterbi, Reed-Solomon), interleaving, Gray coding
- **Decoder API** - Reusable components for building decoders (timing recovery, AFC, DCD, sync detection)

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

### Other Modes - 37 variants
- **CW** (Morse Code) - Variable WPM with prosign support
- **RTTY** (Radioteletype) - Baudot encoding with configurable shift
- **Hell** (Hellschreiber) - Feld Hell, Slow Hell, HellX5/X9, FSK Hell
- **Throb** - Throb1, Throb2, Throb4, ThrobX1/X2/X4
- **FSQ** - FSQ-2, FSQ-3, FSQ-6
- **IFKP** - IFKP-0.5, IFKP-1.0, IFKP-2.0 (Incremental Frequency Keying with FEC)
- **SCAMP** - SCAMPFSK, SCAMPOOK, SCFSKFST, SCFSKSLW, SCOOKSLW, SCFSKVSL (Golay FEC)
- **NAVTEX/SITOR-B** - Maritime safety broadcast modes
- **WEFAX** (Weather Facsimile) - WEFAX-576, WEFAX-288 (Image transmission)

**Total: 22 mode families, ~151 mode variants - All modes decode correctly in fldigi!**

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

**Transmit (TX)**: ✅ Complete - All 22 mode families, ~151 mode variants fully implemented

**Receive (RX)**: 🔄 In Progress
- ✅ 6 decoder families working (PSK, QPSK, 8PSK, 8PSK FEC, RTTY, CW)
- ✅ Complete decoder API with reusable components
- ✅ **Framework integration complete** - PSK/QPSK/8PSK/RTTY/CW decoders use framework components
- 📋 16 decoder families remaining

**Decoder API**: ✅ Complete (2026-01-05)
- **Timing recovery** (SymbolSlicer, Gardner, Early-Late)
- **AFC** (Phase-based, Tone-based, PLL)
- **DCD** (Energy, Preamble, Tone detection)
- **Sync detection** (Pattern matching, state machine)
- **De-interleavers** (Block, Convolutional)
- **Testing utilities** (AWGN, BER/SER, profiling)
- **Integrated into production decoders** - PSK, QPSK, and 8PSK decoders now use framework components

See the [Decoder API Guide](guides/decoder-api.md) to learn how to build decoders.

## Getting Started

### For Transmit (TX)

1. [Install PyDigi](installation.md)
2. Try the [Quick Start](quickstart.md) examples
3. Browse the [API Reference](api/overview.md) to see all available modem modes
4. Check out the [User Guide](examples/basic.md) for usage examples

### For Decoders (RX)

1. Read the [Decoder API Guide](guides/decoder-api.md) to learn the components
2. See the [Decoder API Reference](api/reference/decoder_api.md) for detailed documentation
3. Study decoder examples:
   - [PSK Decoder Guide](guides/decoders.md) - BPSK/QPSK/8PSK decoding
   - [CW Decoder Guide](guides/cw-decoder.md) - Morse code decoding
   - [RTTY Decoder Guide](guides/rtty-decoder.md) - Radioteletype decoding
4. Review [Signal Detection](guides/signal-detection.md) for DCD techniques

## License

PyDigi is open source software. See the repository for license details.
