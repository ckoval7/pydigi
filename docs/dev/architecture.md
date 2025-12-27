# Architecture

PyDigi is organized into three main layers:

## 1. Modem Layer (`pydigi.modems`)

High-level modem implementations that inherit from the base `Modem` class. Each modem:
- Implements `tx_init()` for initialization
- Implements `tx_process()` for modulation
- Provides a public `modulate()` API
- Manages mode-specific parameters

## 2. Core DSP Layer (`pydigi.core`)

Low-level DSP building blocks:
- **Oscillators** (`oscillator.py`) - NCO for tone generation
- **Filters** (`filters.py`) - FIR, moving average, Goertzel
- **FFT** (`fft.py`, `fht.py`) - Spectral analysis
- **Encoders** (`encoder.py`) - FEC encoders (Viterbi, etc.)
- **Modulators** (`mfsk_modulator.py`) - Mode-specific modulation

## 3. Utilities Layer (`pydigi.utils`)

Helper functions:
- **Audio** (`audio.py`) - WAV I/O, normalization
- **Constants** (`constants.py`) - Common constants

## Design Philosophy

1. **Pure Python** - Easy to understand and modify
2. **Based on fldigi** - Reference implementation for correctness
3. **Modular** - Reusable DSP components
4. **Simple API** - Consistent interface across all modes

## See Also

- [Project Status](project_tracker.md)
- [API Reference](../api/overview.md)
