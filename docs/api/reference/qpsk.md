# QPSK (Quadrature PSK)

QPSK uses four phase states to encode 2 bits per symbol, effectively doubling the data rate compared to BPSK at the same baud rate.

## QPSK Encoder

::: pydigi.modems.qpsk
    options:
      show_root_heading: true
      show_source: true

## QPSK Decoder

The QPSK decoder supports all QPSK modes (QPSK31, QPSK63, QPSK125, QPSK250, QPSK500) using Viterbi FEC decoding for error correction.

### Overview

The QPSKDecoder class provides both synchronous and streaming APIs for decoding QPSK signals:

- **Synchronous API**: `demodulate(audio) → text` - Simple, mirrors the encoder
- **Streaming API**: `process(audio)` with callbacks - For real-time applications

### Module Reference

::: pydigi.modems.qpsk_decoder
    options:
      show_root_heading: true
      show_source: true
      members:
        - QPSKDecoder
        - QPSK_31_Decoder
        - QPSK_63_Decoder
        - QPSK_125_Decoder
        - QPSK_250_Decoder
        - QPSK_500_Decoder

### Examples

#### Basic Decoding

```python
from pydigi.modems.qpsk_decoder import QPSKDecoder

# Decode QPSK125 signal
decoder = QPSKDecoder(baud=125, frequency=1000)
text = decoder.demodulate(audio_samples)
print(text)
```

#### Using Convenience Functions

```python
from pydigi.modems.qpsk_decoder import QPSK_125_Decoder

# Simpler API for standard modes
decoder = QPSK_125_Decoder(frequency=1000)
text = decoder.demodulate(audio_samples)
```

#### Real-Time Streaming

```python
from pydigi.modems.qpsk_decoder import QPSKDecoder

decoder = QPSKDecoder(baud=125, frequency=1000)

# Set callback for character-by-character output
def on_character(char):
    print(char, end='', flush=True)

decoder.set_text_callback(on_character)

# Process audio stream
for audio_chunk in audio_stream:
    decoder.process(audio_chunk)
```

#### With AFC and Squelch

```python
from pydigi.modems.qpsk_decoder import QPSKDecoder

# AFC (Automatic Frequency Control) adjusts for frequency drift
# Squelch suppresses output during weak signals
decoder = QPSKDecoder(
    baud=125,
    frequency=1000,
    afc_enabled=True,
    squelch_enabled=True
)

# Monitor decoder statistics
stats = decoder.get_stats()
print(f"Signal quality: {stats['metric']:.1f}")
print(f"DCD: {stats['dcd']}")
print(f"Frequency: {stats['frequency']:.1f} Hz")
```
