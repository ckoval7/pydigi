# Throb Decoder

The Throb decoder supports all 6 Throb modes (Throb1/2/4 and ThrobX1/2/4) using correlation-based dual-tone detection.

## Overview

The ThrobDecoder class decodes Throb signals using a correlation-based approach that matches the received signal against pre-computed tone templates. Throb is a dual-tone amplitude-modulated mode that is highly resistant to propagation-induced phase shifts and requires no carrier tracking.

**Key Features:**
- Dual-tone correlation detection
- Hilbert transform for analytic signal creation
- Symbol timing recovery via sync tracking
- SNR measurement and squelch
- Optional AFC for frequency tracking
- Real-time character callbacks

## Module Reference

::: pydigi.modems.throb_decoder
    options:
      show_root_heading: true
      show_source: true
      members:
        - ThrobDecoder
        - Throb1Decoder
        - Throb2Decoder
        - Throb4Decoder
        - ThrobX1Decoder
        - ThrobX2Decoder
        - ThrobX4Decoder

## Examples

### Basic Decoding

```python
from pydigi.modems.throb import Throb1
from pydigi.modems.throb_decoder import Throb1Decoder

# Encode a message
encoder = Throb1()
audio = encoder.modulate("HELLO WORLD")

# Decode the signal
decoder = Throb1Decoder()
text = decoder.process(audio)
print(f"Received: {text}")
print(f"SNR: {decoder.get_snr():.1f} dB")
```

### All Modes

```python
from pydigi.modems.throb import Throb1, Throb2, Throb4, ThrobX1, ThrobX2, ThrobX4
from pydigi.modems.throb_decoder import (
    Throb1Decoder, Throb2Decoder, Throb4Decoder,
    ThrobX1Decoder, ThrobX2Decoder, ThrobX4Decoder
)

modes = [
    ("Throb1", Throb1, Throb1Decoder),
    ("Throb2", Throb2, Throb2Decoder),
    ("Throb4", Throb4, Throb4Decoder),
    ("ThrobX1", ThrobX1, ThrobX1Decoder),
    ("ThrobX2", ThrobX2, ThrobX2Decoder),
    ("ThrobX4", ThrobX4, ThrobX4Decoder),
]

message = "TEST 123"

for mode_name, encoder_func, decoder_func in modes:
    encoder = encoder_func()
    audio = encoder.modulate(message)

    decoder = decoder_func()
    decoded = decoder.process(audio)

    print(f"{mode_name}: '{decoded}' (SNR: {decoder.get_snr():.1f} dB)")
```

### Real-Time Character Callback

```python
from pydigi.modems.throb_decoder import Throb2Decoder

decoder = Throb2Decoder()

# Set callback for character-by-character output
def on_character(char):
    print(char, end='', flush=True)

decoder.text_callback = on_character

# Process audio stream
decoder.process(audio_samples)
```

### With Frequency Offset and AFC

```python
from pydigi.modems.throb_decoder import Throb4Decoder

# Decoder with AFC enabled for frequency tracking
decoder = Throb4Decoder(frequency=1500, use_afc=True)
text = decoder.process(audio)

print(f"Decoded: {text}")
print(f"Final frequency: {decoder.frequency:.1f} Hz")
```

### With Squelch

```python
from pydigi.modems.throb_decoder import Throb1Decoder
import numpy as np

# Add noise to signal
signal_power = np.var(audio)
noise = np.random.normal(0, np.sqrt(signal_power * 0.1), len(audio))
noisy_audio = audio + noise

# Decode with squelch
decoder = Throb1Decoder()
decoder.squelch = 10.0  # 10 dB threshold
decoder.squelch_enabled = True

text = decoder.process(noisy_audio)
print(f"Decoded: {text}")
print(f"SNR: {decoder.get_snr():.1f} dB")
```

### Decoder Reset

```python
from pydigi.modems.throb_decoder import Throb2Decoder

decoder = Throb2Decoder()

# First transmission
text1 = decoder.process(audio1)

# Reset before next transmission
decoder.reset()

# Second transmission
text2 = decoder.process(audio2)
```

## Mode Characteristics

### Regular Throb Modes (9 tones, 45 characters)

| Mode | Baud Rate | Tone Spacing | Bandwidth | Pulse Shape |
|------|-----------|--------------|-----------|-------------|
| Throb1 | ~1 baud | 8 Hz | ~64 Hz | Semi-pulse |
| Throb2 | ~2 baud | 8 Hz | ~64 Hz | Semi-pulse |
| Throb4 | ~4 baud | 16 Hz | ~128 Hz | Full-pulse |

**Character Set:** A-Z, 0-9, limited punctuation
**Special Characters:** ?, @, =, newline (via shift codes)

### ThrobX Modes (11 tones, 55 characters)

| Mode | Baud Rate | Tone Spacing | Bandwidth | Pulse Shape |
|------|-----------|--------------|-----------|-------------|
| ThrobX1 | ~1 baud | 7.8125 Hz | ~78 Hz | Semi-pulse |
| ThrobX2 | ~2 baud | 7.8125 Hz | ~78 Hz | Semi-pulse |
| ThrobX4 | ~4 baud | 15.625 Hz | ~156 Hz | Full-pulse |

**Character Set:** A-Z, 0-9, extended punctuation (#@+-;:?!=)
**Special Features:** Alternating idle/space symbols for word spacing

## Decoder Parameters

### ThrobDecoder

- **mode** (str): Throb mode ('throb1', 'throb2', 'throb4', 'throbx1', 'throbx2', 'throbx4')
- **sample_rate** (float): Audio sample rate in Hz (default: 8000, fixed for Throb)
- **frequency** (float): Center frequency in Hz (default: 1500)
- **use_afc** (bool): Enable automatic frequency control (default: True)
- **squelch** (float): Squelch threshold in dB (default: 3.0)
- **squelch_enabled** (bool): Enable squelch (default: True)
- **text_callback** (callable): Optional callback for decoded characters

### Methods

- **process(samples)**: Process audio samples and return decoded text
- **get_snr()**: Get current SNR estimate in dB
- **get_metric()**: Get current signal quality metric
- **reset()**: Reset decoder state

## Technical Details

### Signal Processing Pipeline

1. **Hilbert Transform**: Convert real signal to analytic (complex) signal
2. **Complex Mixing**: Frequency translation to baseband
3. **Downsampling**: 32x decimation for efficient processing
4. **Correlation**: Correlate against pre-computed tone templates
5. **Tone Detection**: Find two strongest tones for each symbol
6. **Character Decoding**: Map tone pairs to characters
7. **Text Output**: Assemble characters into text

### Correlation-Based Detection

The decoder uses correlation against pre-computed complex tone templates:

- Each tone template is a complex sinusoid modulated by the pulse shape
- Correlation is performed using complex multiply-accumulate (cmac)
- The two strongest correlations identify the dual-tone symbol
- Single-tone symbols are detected when one tone is much stronger (Throb only)

### Character Decoding

**Regular Throb:**
- Direct tone pair → character lookup
- Shift state machine for special characters (?, @, =, newline)
- Shift symbol: tone pair (3,5)

**ThrobX:**
- Direct tone pair → character lookup (extended charset)
- Alternating idle/space symbols for word spacing
- Idle and space symbols flip after each occurrence

## Performance

### Test Results

- **Loopback Accuracy**: 100% for all 6 modes in clean conditions
- **Noise Tolerance**:
  - 20 dB SNR: 100% accuracy
  - 10 dB SNR: 92%+ accuracy
  - 5 dB SNR: Variable (depends on noise instance)
- **AFC Range**: ±5 Hz (degrades beyond ±10 Hz)
- **Code Coverage**: 97% (21/21 tests passing)

### Typical SNR Values (Clean Signal)

| Mode | Typical SNR |
|------|-------------|
| Throb1 | 24-28 dB |
| Throb2 | 22-26 dB |
| Throb4 | 24-28 dB |
| ThrobX1 | 28-32 dB |
| ThrobX2 | 24-28 dB |
| ThrobX4 | 32-36 dB |

## See Also

- [Throb Encoder](throb.md) - Transmit side
- [Decoder Infrastructure](decoder_api.md) - Core decoder components
- [Examples](../../examples/throb_decoder_example.py) - Complete example code
- [Project Tracker](../../PROJECT_TRACKER.md) - Implementation status
