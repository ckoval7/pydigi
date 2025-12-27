# API Overview

PyDigi provides a clean, object-oriented API for generating amateur radio digital mode signals. All modems follow the same simple pattern: create a modem instance, call `modulate()` with your text, and get back audio samples ready to use.

## Quick Example

```python
from pydigi import PSK31, save_wav

# Create a PSK31 modem
modem = PSK31(frequency=1000)

# Generate audio
audio = modem.modulate("CQ CQ CQ DE W1ABC")

# Save to file or use with GNU Radio
save_wav("output.wav", audio, modem.sample_rate)
```

## Architecture

PyDigi is organized into three main layers:

1. **[Modem Classes](reference/base.md)** - High-level modem implementations with consistent API
2. **[Core DSP](reference/dsp.md)** - Low-level DSP building blocks (oscillators, filters, FFT, encoders)
3. **[Audio Utilities](reference/audio.md)** - WAV file I/O and audio processing helpers

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

## Available Modem Modes

PyDigi supports 140+ modem variants across 19 mode families:

- **[CW](reference/cw.md)** - Morse code
- **[RTTY](reference/rtty.md)** - Radioteletype with Baudot encoding
- **[PSK](reference/psk.md)** - PSK31/63/125/250/500/1000 and multi-carrier variants
- **[QPSK](reference/qpsk.md)** - Quadrature PSK variants
- **[8PSK](reference/8psk.md)** - Eight-phase PSK with optional FEC
- **[MFSK](reference/mfsk.md)** - Multi-frequency shift keying
- **[Olivia](reference/olivia.md)** - Robust MFSK with FEC (36 configurations)
- **[Contestia](reference/olivia.md)** - Similar to Olivia with different interleaving
- **[DominoEX](reference/dominoex.md)** - Incremental frequency keying
- **[Thor](reference/thor.md)** - IFK with FEC (15 modes)
- **[Throb](reference/throb.md)** - Multi-tone sequential pattern
- **[Hell](reference/hell.md)** - Hellschreiber facsimile modes
- **[FSQ](reference/fsq.md)** - Fast Simple QSO
- **[MT63](reference/mt63.md)** - 64-carrier OFDM mode
- **[IFKP](reference/ifkp.md)** - Incremental frequency keying plus

See the [Modem Reference](reference/base.md) section for detailed API documentation for each mode.

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

- [Modem Reference](reference/base.md) - Detailed modem class documentation
- [Audio Utilities](reference/audio.md) - WAV file I/O and audio processing
- [DSP Core](reference/dsp.md) - Low-level DSP components
- [Examples](../examples/basic.md) - Code examples
