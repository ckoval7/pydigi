# PSK Decoder

The PSK decoder supports all BPSK modes (PSK31, PSK63, PSK125, PSK250, PSK500) using a universal architecture that adapts to different baud rates.

## Overview

The PSKDecoder class provides both synchronous and streaming APIs for decoding PSK signals:

- **Synchronous API**: `demodulate(audio) → text` - Simple, mirrors the encoder
- **Streaming API**: `process(audio)` with callbacks - For real-time applications

## Module Reference

::: pydigi.modems.psk_decoder
    options:
      show_root_heading: true
      show_source: true
      members:
        - PSKDecoder

## Signal Detection

::: pydigi.core.signal_detector
    options:
      show_root_heading: true
      show_source: true
      members:
        - SignalDetector
        - SignalPeak
        - MultiSignalDetector

## Frequency Estimation

::: pydigi.core.freq_estimators
    options:
      show_root_heading: true
      show_source: true
      members:
        - parabolic_interpolation
        - quinn_estimator
        - jacobsen_estimator
        - gaussian_interpolation
        - multi_estimator_average
        - zero_padded_fft_estimate
        - phase_vocoder_estimator
        - czt_zoom

## Examples

### Basic Decoding

```python
from pydigi.modems.psk_decoder import PSKDecoder

# Decode PSK125 signal
decoder = PSKDecoder(baud=125, frequency=1000)
text = decoder.demodulate(audio_samples)
print(text)
```

### With Automatic Frequency Detection

```python
from pydigi.core.signal_detector import SignalDetector
from pydigi.modems.psk_decoder import PSKDecoder

# Auto-detect carrier frequency
detector = SignalDetector()
peaks = detector.detect(audio_samples)

if peaks:
    # Decode using detected frequency
    decoder = PSKDecoder(baud=125, frequency=peaks[0].frequency)
    text = decoder.demodulate(audio_samples)
```

### Real-Time Streaming

```python
from pydigi.modems.psk_decoder import PSKDecoder

decoder = PSKDecoder(baud=125, frequency=1000)

# Set callback for character-by-character output
def on_character(char):
    print(char, end='', flush=True)

decoder.set_text_callback(on_character)

# Process audio stream
for audio_chunk in audio_stream:
    decoder.process(audio_chunk)
```

### Multi-Signal Decoding

```python
from pydigi.core.signal_detector import SignalDetector
from pydigi.modems.psk_decoder import PSKDecoder

# Detect all signals
detector = SignalDetector()
peaks = detector.detect(audio_samples, num_peaks=5)

# Create decoder for each signal
decoders = []
for peak in peaks:
    decoder = PSKDecoder(baud=125, frequency=peak.frequency)
    decoders.append(decoder)

# Decode all in parallel
for decoder in decoders:
    text = decoder.demodulate(audio_samples)
    print(f"Signal at {decoder.frequency:.1f} Hz: {text}")
```

## See Also

- [PSK Decoder User Guide](../../guides/decoders.md) - Comprehensive usage guide
- [Signal Detection Guide](../../guides/signal-detection.md) - Auto-detection details
- [Frequency Estimation Guide](../../guides/frequency-estimation.md) - Advanced frequency detection
- [PSK Encoder](psk.md) - Transmit side
