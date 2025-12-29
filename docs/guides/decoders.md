# PSK Decoder User Guide

This guide covers everything you need to know about decoding PSK signals with pydigi.

## Table of Contents

1. [Quick Start](#quick-start)
2. [Understanding PSK Decoding](#understanding-psk-decoding)
3. [Basic Usage](#basic-usage)
4. [Advanced Features](#advanced-features)
5. [Troubleshooting](#troubleshooting)
6. [Performance Tuning](#performance-tuning)
7. [Integration Examples](#integration-examples)

## Quick Start

The simplest way to decode a PSK signal:

```python
from pydigi.modems.psk_decoder import PSKDecoder

# Create decoder
decoder = PSKDecoder(
    baud=125,           # PSK125
    sample_rate=8000,   # 8 kHz audio
    frequency=1000      # Carrier at 1 kHz
)

# Decode audio
text = decoder.demodulate(audio_samples)
print(text)
```

## Understanding PSK Decoding

### What the Decoder Does

The PSK decoder performs these steps:

1. **Baseband Conversion** - Mixes carrier to baseband (removes the frequency offset)
2. **Matched Filtering** - Filters noise while preserving signal
3. **Symbol Timing Recovery** - Locks onto symbol boundaries
4. **Phase Detection** - Measures phase of each symbol
5. **Differential Decoding** - Converts phase changes to bits
6. **Varicode Decoding** - Converts bit stream to text

### Supported Modes

All BPSK modes use the **same decoder** with different baud rates:

| Mode | Baud Rate | Speed | Use Case |
|------|-----------|-------|----------|
| PSK31 | 31.25 | Slow | Most common, very robust |
| PSK63 | 62.5 | Medium | Good compromise |
| PSK125 | 125 | Fast | **Recommended for ARQ** |
| PSK250 | 250 | Very Fast | High-speed links |
| PSK500 | 500 | Ultra Fast | Best conditions only |

## Basic Usage

### Synchronous API (Simple)

The synchronous API mirrors the encoder for simplicity:

```python
from pydigi.modems.psk import PSK
from pydigi.modems.psk_decoder import PSKDecoder

# Encode
encoder = PSK(baud=125, frequency=1000)
audio = encoder.modulate("Hello World!")

# Decode
decoder = PSKDecoder(baud=125, frequency=1000)
text = decoder.demodulate(audio)

print(text)  # "Hello World!"
```

### Streaming API (Real-Time)

For real-time applications or ARQ integration:

```python
from pydigi.modems.psk_decoder import PSKDecoder

decoder = PSKDecoder(baud=125, frequency=1000)

# Callback receives characters as they're decoded
def on_char(char):
    print(char, end='', flush=True)

decoder.set_text_callback(on_char)

# Process audio in chunks
for chunk in audio_stream:
    decoder.process(chunk)
```

### Decoding WAV Files

```python
from pydigi.modems.psk_decoder import PSKDecoder
from pydigi.utils.audio import load_wav

# Load WAV file
samples, sample_rate = load_wav("signal.wav")

# Decode
decoder = PSKDecoder(baud=125, sample_rate=sample_rate, frequency=1000)
text = decoder.demodulate(samples)

print(f"Decoded: {text}")
```

## Advanced Features

### Automatic Frequency Detection

Don't know the carrier frequency? Detect it automatically:

```python
from pydigi.core.signal_detector import SignalDetector
from pydigi.modems.psk_decoder import PSKDecoder

# Auto-detect carrier
detector = SignalDetector(sample_rate=8000)
peaks = detector.detect(audio_samples)

if peaks:
    freq = peaks[0].frequency
    print(f"Detected signal at {freq:.1f} Hz")

    # Decode at detected frequency
    decoder = PSKDecoder(baud=125, frequency=freq)
    text = decoder.demodulate(audio_samples)
    print(text)
else:
    print("No signal detected")
```

### AFC (Automatic Frequency Control)

The decoder can track frequency drift:

```python
decoder = PSKDecoder(
    baud=125,
    frequency=1000,
    afc_enabled=True   # Track frequency changes (default: True)
)

# Check AFC results
text = decoder.demodulate(audio)
stats = decoder.get_stats()
print(f"Final frequency: {stats['frequency']:.2f} Hz")
print(f"Frequency drift: {stats['freqerr']:.4f} Hz")
```

### Squelch (Signal Detection)

Enable squelch to only decode when signal is present:

```python
decoder = PSKDecoder(
    baud=125,
    frequency=1000,
    squelch_enabled=True,  # Only decode when DCD active
)

decoder.dcd_threshold = 10.0  # Adjust threshold (0-100)
```

### Signal Quality Monitoring

Monitor signal quality in real-time:

```python
decoder = PSKDecoder(baud=125, frequency=1000)

def on_char(char):
    stats = decoder.get_stats()
    quality = stats['metric']  # 0-100, higher is better
    dcd = stats['dcd']         # Data carrier detect

    if dcd and quality > 50:
        print(char, end='')
    else:
        print('?', end='')  # Poor quality

decoder.set_text_callback(on_char)
decoder.process(audio)
```

### Multi-Signal Decoding

Decode multiple simultaneous PSK signals:

```python
from pydigi.core.signal_detector import SignalDetector
from pydigi.modems.psk_decoder import PSKDecoder

# Detect all signals
detector = SignalDetector()
peaks = detector.detect(audio, num_peaks=5, min_spacing_hz=200)

print(f"Found {len(peaks)} signals")

# Create decoder for each
decoders = {}
for i, peak in enumerate(peaks):
    decoder = PSKDecoder(
        baud=125,
        frequency=peak.frequency,
        squelch_enabled=True  # Important for multi-signal!
    )
    decoders[i] = decoder

# Decode all in parallel
results = {}
for i, decoder in decoders.items():
    results[i] = decoder.demodulate(audio)

# Display results
for i, text in results.items():
    freq = peaks[i].frequency
    print(f"Signal {i+1} at {freq:.1f} Hz: {text}")
```

## Troubleshooting

### Problem: No Text Decoded

**Possible causes:**

1. **Wrong frequency** - Check carrier frequency
   ```python
   # Use auto-detection
   detector = SignalDetector()
   peaks = detector.detect(audio)
   print(f"Signals found at: {[p.frequency for p in peaks]}")
   ```

2. **Wrong baud rate** - PSK31 vs PSK125 etc.
   ```python
   # Try different baud rates
   for baud in [31.25, 63, 125, 250]:
       decoder = PSKDecoder(baud=baud, frequency=1000)
       text = decoder.demodulate(audio)
       if text:
           print(f"PSK{int(baud)}: {text}")
   ```

3. **Signal too weak** - Check SNR
   ```python
   detector = SignalDetector(threshold_db=3.0)  # Lower threshold
   peaks = detector.detect(audio)
   if peaks:
       print(f"SNR: {peaks[0].snr:.1f} dB")
   ```

4. **Squelch too high** - Disable or lower threshold
   ```python
   decoder = PSKDecoder(baud=125, squelch_enabled=False)
   ```

### Problem: Garbled Text

**Possible causes:**

1. **Frequency offset** - Enable AFC
   ```python
   decoder = PSKDecoder(baud=125, frequency=1000, afc_enabled=True)
   ```

2. **Timing sync issues** - Check signal quality
   ```python
   stats = decoder.get_stats()
   print(f"Metric: {stats['metric']:.2f}")  # Should be >50
   ```

3. **Multipath/fading** - Try slower baud rate
   ```python
   # PSK31 is more robust than PSK125
   decoder = PSKDecoder(baud=31.25, frequency=1000)
   ```

### Problem: Missing First Characters

This is **normal** - the decoder needs a few symbols to lock on:

1. **Preamble helps** - Transmitters should send preamble
2. **Ignore first 1-2 chars** - They're often garbled during lock-on
3. **Check AFC** - May have started at wrong frequency

```python
text = decoder.demodulate(audio)
# Strip leading garbage
clean_text = text.lstrip(' \x00\xff')
```

### Problem: Slow Performance

**Optimization tips:**

1. **Use appropriate baud rate** - Don't use PSK31 if you need PSK125
2. **Disable AFC if not needed** - Saves CPU
   ```python
   decoder = PSKDecoder(baud=125, afc_enabled=False)
   ```
3. **Reduce sample rate** - 8 kHz is plenty for PSK
4. **Process in chunks** - Don't load entire file at once

## Performance Tuning

### CPU Usage

Typical CPU usage (on modern CPU, real-time):

- **Single decoder**: ~5-10%
- **3 simultaneous signals**: ~15-20%
- **With auto-detection**: +1-2%

### Latency

- **Detection latency**: 1-2 seconds (initial FFT accumulation)
- **Decoding latency**: <100 ms (symbol timing)
- **Character latency**: Depends on baud rate
  - PSK31: ~320 ms per character average
  - PSK125: ~80 ms per character average

### Memory Usage

- **Per decoder**: ~100 KB
- **Signal detector**: ~50 KB
- **10 decoders**: ~1.5 MB total

### Accuracy

Under good conditions (SNR >10 dB):

- **Frequency detection**: ±0.05-0.15 Hz (multi-estimator)
- **Character error rate**: <0.1% (PSK125)
- **Lock-on time**: 0.5-1.0 seconds

## Integration Examples

### With ARQ Protocol

```python
from pydigi.modems.psk_decoder import PSKDecoder
from pydigi.arq import ARQProtocol

# Create decoder
decoder = PSKDecoder(baud=125, frequency=1000)

# Create ARQ protocol handler
arq = ARQProtocol()

# Connect decoder to ARQ
def on_text(text):
    # Feed decoded text to ARQ
    arq.receive_frame(text.encode())

decoder.set_text_callback(on_text)

# Process audio stream
decoder.process(audio_stream)
```

### With GNU Radio

```python
import numpy as np
from pydigi.modems.psk_decoder import PSKDecoder

class PSKDecoderBlock:
    """GNU Radio sink block for PSK decoding."""

    def __init__(self, baud=125, frequency=1000):
        self.decoder = PSKDecoder(baud=baud, frequency=frequency)
        self.text_buffer = []

        self.decoder.set_text_callback(self.text_buffer.append)

    def work(self, input_items, output_items):
        # Get audio from GNU Radio
        audio = input_items[0]

        # Process through decoder
        self.decoder.process(audio)

        # Output text if available
        if self.text_buffer:
            text = ''.join(self.text_buffer)
            self.text_buffer.clear()
            print(text, end='', flush=True)

        return len(input_items[0])
```

### Spectrum Analyzer Display

```python
from pydigi.core.signal_detector import SignalDetector
import time

detector = SignalDetector(sample_rate=8000, fft_size=8192)

while True:
    # Get audio chunk
    audio = get_audio_chunk()

    # Get spectrum
    freqs, mags = detector.get_spectrum(audio)

    # Detect peaks
    peaks = detector.detect(audio, num_peaks=10)

    # Display
    plot_spectrum(freqs, mags, peaks)

    time.sleep(0.1)
```

### Logging and Monitoring

```python
from pydigi.modems.psk_decoder import PSKDecoder
import datetime

class LoggingDecoder:
    """Decoder with logging capabilities."""

    def __init__(self, baud, frequency, log_file):
        self.decoder = PSKDecoder(baud=baud, frequency=frequency)
        self.log_file = log_file
        self.decoder.set_text_callback(self.on_char)

    def on_char(self, char):
        stats = self.decoder.get_stats()

        # Log with timestamp and quality
        timestamp = datetime.datetime.now().isoformat()
        log_entry = {
            'time': timestamp,
            'char': char,
            'metric': stats['metric'],
            'frequency': stats['frequency'],
            'dcd': stats['dcd'],
        }

        with open(self.log_file, 'a') as f:
            f.write(f"{log_entry}\n")

        print(char, end='', flush=True)

# Use it
decoder = LoggingDecoder(baud=125, frequency=1000, log_file='decode.log')
decoder.decoder.process(audio)
```

## Best Practices

### 1. Always Use Auto-Detection in Production

```python
# Good: Auto-detect frequency
detector = SignalDetector()
peaks = detector.detect(audio)
if peaks:
    decoder = PSKDecoder(baud=125, frequency=peaks[0].frequency)
else:
    # Fallback to default
    decoder = PSKDecoder(baud=125, frequency=1000)
```

### 2. Enable AFC for Real-World Signals

```python
# Real-world signals drift - use AFC
decoder = PSKDecoder(baud=125, frequency=1000, afc_enabled=True)
```

### 3. Use Squelch for Multi-Signal

```python
# When decoding multiple signals, use squelch
decoder = PSKDecoder(baud=125, frequency=1000, squelch_enabled=True)
```

### 4. Monitor Signal Quality

```python
def on_char(char):
    stats = decoder.get_stats()
    if stats['metric'] < 20:
        print(f"WARNING: Low signal quality: {stats['metric']:.1f}")
    print(char, end='')
```

### 5. Handle Errors Gracefully

```python
try:
    text = decoder.demodulate(audio)
except Exception as e:
    print(f"Decoding error: {e}")
    decoder.reset()  # Reset state and try again
```

## Next Steps

- [API Reference](../api/reference/psk_decoder.md) - Complete API documentation
- [Signal Detection Guide](signal-detection.md) - Auto-detection details
- [Frequency Estimation](frequency-estimation.md) - Advanced frequency methods
- [ARQ Integration](../arq/README.md) - Using decoder with ARQ protocol

## FAQ

**Q: Which baud rate should I use?**
A: PSK125 for ARQ (good balance), PSK31 for maximum robustness, PSK250+ for high-speed links.

**Q: Do I need to know the exact frequency?**
A: No, use `SignalDetector` to auto-detect, or enable AFC to track small offsets.

**Q: Can I decode multiple signals at once?**
A: Yes! Create one decoder per signal, all process the same audio independently.

**Q: Why are the first few characters garbled?**
A: Normal - decoder needs time to lock onto timing and phase. Transmitters should send preamble.

**Q: How accurate is frequency detection?**
A: ±0.05-0.15 Hz with multi-estimator, ±0.3-0.5 Hz with basic parabolic.

**Q: What sample rate should I use?**
A: 8000 Hz is recommended. Higher rates waste CPU, lower rates may miss signal.
