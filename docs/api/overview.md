# API Overview

PyDigi provides a clean, object-oriented API for generating digital mode signals. This page gives an overview of the main components.

## Architecture

PyDigi is organized into three main layers:

1. **Modem Classes** (`pydigi.modems`) - High-level modem implementations
2. **Core DSP** (`pydigi.core`) - Low-level DSP building blocks (oscillators, filters, FFT, encoders)
3. **Utilities** (`pydigi.utils`) - Audio I/O, constants, and helper functions

## Basic Usage Pattern

All modems follow the same basic pattern:

```python
from pydigi import ModemClass, save_wav

# 1. Create a modem instance
modem = ModemClass(frequency=1000)

# 2. Generate audio from text
audio = modem.modulate("YOUR MESSAGE HERE")

# 3. Use the audio
save_wav("output.wav", audio, sample_rate=modem.sample_rate)
```

## Common Parameters

### Modem Initialization

Most modems accept these parameters:

- `frequency` (float): Audio frequency in Hz (default: 1000)
- `sample_rate` (float): Sample rate in Hz (default: 8000)

Mode-specific parameters:

- **CW**: `wpm` (words per minute), `rise_time` (edge rise time)
- **RTTY**: `baud` (baud rate), `shift` (frequency shift)
- **PSK**: `baud` (symbol rate), varies by mode
- **MFSK**: `tones` (number of tones), `bandwidth` (signal bandwidth)

### Modulate Method

The `modulate()` method converts text to audio:

```python
audio = modem.modulate(
    text,                    # Text string to transmit
    frequency=None,          # Override frequency (optional)
    sample_rate=None,        # Override sample rate (optional)
    preamble_symbols=None    # Custom preamble length (some modes)
)
```

Returns: `numpy.ndarray` of float32 samples in range [-1.0, 1.0]

## Output Format

All modems return audio as numpy arrays:

- **Type**: `numpy.ndarray` with dtype `float32` or `float64`
- **Range**: Normalized to [-1.0, 1.0]
- **Shape**: 1D array (mono audio)
- **Sample Rate**: Typically 8000 Hz (configurable)

This format works directly with:
- WAV file I/O (`save_wav`, `load_wav`)
- GNU Radio blocks (numpy array input)
- Audio playback libraries (sounddevice, pyaudio, etc.)
- Scientific Python tools (matplotlib, scipy, etc.)

## Import Patterns

### Direct Import (Recommended)

Import specific modems from the main package:

```python
from pydigi import PSK31, QPSK63, RTTY, CW
from pydigi import save_wav, load_wav
```

### From Submodules

Import from specific submodules:

```python
from pydigi.modems import PSK31, MFSK16
from pydigi.utils.audio import save_wav, normalize
from pydigi.core import NCO, FIRFilter
```

### Wildcard Import (Not Recommended)

Import everything (avoid in production code):

```python
from pydigi import *  # Imports all modem classes and utilities
```

## Available Modules

### Main Package (`pydigi`)

Exports all modem classes and common utilities:
- All modem classes (PSK31, RTTY, etc.)
- Audio utilities (`save_wav`, `load_wav`)

### Modems (`pydigi.modems`)

Individual modem implementations:
- `cw` - CW (Morse Code)
- `rtty` - RTTY (Radioteletype)
- `psk` - BPSK variants
- `qpsk` - QPSK variants
- `psk8` - 8PSK variants
- `psk8_fec` - 8PSK with FEC
- `mfsk` - MFSK
- `olivia` - Olivia (MFSK with FEC)
- `contestia` - Contestia (MFSK with FEC)
- `dominoex` - DominoEX
- `thor` - Thor
- `throb` - Throb
- `hell` - Hellschreiber
- `fsq` - FSQ
- `mt63` - MT63
- `ifkp` - IFKP

### Core DSP (`pydigi.core`)

Low-level DSP components:
- `oscillator` - NCO (Numerically Controlled Oscillator)
- `filters` - FIR filters, moving averages, Goertzel
- `fft` - FFT/IFFT functions
- `fht` - Fast Hartley Transform
- `encoder` - FEC encoders (Viterbi, etc.)
- `interleave` - Interleaver/deinterleaver
- `mfsk_encoder` - MFSK-specific encoding
- `mfsk_modulator` - MFSK modulation
- `dsp_utils` - General DSP utilities

### Utilities (`pydigi.utils`)

Helper functions and constants:
- `audio` - WAV I/O, normalization, level measurement
- `constants` - Common constants (sample rates, etc.)

### Varicode (`pydigi.varicode`)

Character encoding tables:
- `baudot` - Baudot (RTTY) encoding
- `psk_varicode` - PSK varicode
- `mfsk_varicode` - MFSK varicode
- `dominoex_varicode` - DominoEX varicode
- `thor_varicode` - Thor varicode
- `throb_varicode` - Throb varicode
- `fsq_varicode` - FSQ encoding
- `feld_font` - Hellschreiber font

## Error Handling

PyDigi modems generally normalize output automatically:

```python
# If audio peak exceeds 1.0, it's automatically normalized
audio = modem.modulate(text)
# audio is guaranteed to be in [-1.0, 1.0]
```

Common issues:

1. **Invalid characters**: Unknown characters may be skipped or replaced
2. **Empty text**: Returns empty or minimal audio (preamble/postamble only)
3. **Invalid parameters**: Raises `ValueError` during initialization

## Performance Considerations

- **First call overhead**: Initial `modulate()` call may be slower due to filter initialization
- **Sample rate**: Lower sample rates (8000 Hz) process faster than higher rates
- **Text length**: Processing time scales linearly with text length
- **Mode complexity**: More complex modes (MT63, Olivia) take longer than simple modes (CW, RTTY)

## Next Steps

- [Modem Classes Reference](modems.md) - Detailed modem class documentation
- [Audio Utilities](audio.md) - WAV file I/O and audio processing
- [DSP Core](dsp.md) - Low-level DSP components
- [Examples](../examples/basic.md) - Code examples
