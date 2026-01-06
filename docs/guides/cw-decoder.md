# CW Decoder User Guide

This guide covers everything you need to know about decoding CW (Morse Code) signals with pydigi.

## Table of Contents

1. [Quick Start](#quick-start)
2. [Understanding CW Decoding](#understanding-cw-decoding)
3. [Basic Usage](#basic-usage)
4. [Advanced Features](#advanced-features)
5. [Troubleshooting](#troubleshooting)
6. [Integration Examples](#integration-examples)

## Quick Start

The simplest way to decode a CW signal:

```python
from pydigi.modems import CWDecoder

# Create decoder
decoder = CWDecoder(
    wpm=20,              # Expected speed in WPM
    sample_rate=8000,    # 8 kHz audio
    frequency=800        # CW tone frequency
)

# Decode audio
text = decoder.demodulate(audio_samples)
print(text)
```

## Understanding CW Decoding

### What the Decoder Does

The CW decoder performs these steps:

1. **Bandpass Filtering** - Extracts the CW tone from noise
2. **Envelope Detection** - Detects when the tone is on/off
3. **AGC (Automatic Gain Control)** - Normalizes signal levels
4. **Key Detection** - Detects key-up and key-down events (with hysteresis)
5. **Timing Measurement** - Measures dit and dah durations
6. **Pattern Matching** - Decodes morse patterns to characters
7. **Spacing Detection** - Detects character and word boundaries

### Supported Characters

The decoder supports:

- **Letters**: A-Z
- **Numbers**: 0-9
- **Punctuation**: . , ? ' ! / ( ) & : ; = + - _ " $ @
- **Prosigns**: `<AR>`, `<SK>`, `<BT>`, `<KN>`, `<AS>`

### Speed Range

- **Minimum**: 5 WPM
- **Maximum**: 200 WPM
- **Typical**: 10-40 WPM
- **Recommended**: 15-25 WPM for best accuracy

## Basic Usage

### Synchronous API (Simple)

The synchronous API mirrors the encoder:

```python
from pydigi.modems import CW, CWDecoder

# Encode
encoder = CW(wpm=20, frequency=800)
audio = encoder.modulate("HELLO WORLD")

# Decode
decoder = CWDecoder(wpm=20, frequency=800)
text = decoder.demodulate(audio)

print(text)  # "HELLO WORLD"
```

### Streaming API (Real-Time)

For real-time applications:

```python
from pydigi.modems import CWDecoder

# Create decoder with callback
def on_text(text):
    print(text, end='', flush=True)

decoder = CWDecoder(
    wpm=20,
    frequency=800,
    text_callback=on_text
)

# Process audio in chunks
for chunk in audio_stream:
    decoder.process(chunk)
```

### Decoding WAV Files

```python
from pydigi.modems import CWDecoder
from pydigi.utils.audio import load_wav

# Load WAV file
samples, sample_rate = load_wav("morse.wav")

# Decode
decoder = CWDecoder(
    wpm=20,
    sample_rate=sample_rate,
    frequency=800
)
text = decoder.demodulate(samples)

print(f"Decoded: {text}")
```

## Advanced Features

### Automatic Gain Control (AGC)

The decoder includes built-in AGC to handle varying signal levels:

```python
decoder = CWDecoder(
    wpm=20,
    frequency=800,
    # AGC is always enabled and adapts automatically
)

# Get AGC statistics
stats = decoder.get_statistics()
print(f"Signal level: {stats['metric']:.1f}")
print(f"SNR: {stats['snr_db']:.1f} dB")
```

### Adaptive Speed Tracking

The decoder can estimate WPM from the signal:

```python
decoder = CWDecoder(
    wpm=20,  # Initial estimate
    frequency=800
)

text = decoder.demodulate(audio)
stats = decoder.get_statistics()

print(f"Initial WPM: 20")
print(f"Estimated WPM: {stats['wpm']:.1f}")
print(f"Decoded: {text}")
```

**Note**: Speed tracking works best when initial WPM is within ±5% of actual speed.

### Noise Handling

The decoder includes several noise rejection features:

```python
decoder = CWDecoder(
    wpm=20,
    frequency=800,
    bandwidth=100.0,      # Filter bandwidth (Hz)
    noise_char='*'        # Character for decode errors
)

# Decoder automatically:
# - Rejects noise spikes shorter than 1/4 dit time
# - Uses hysteresis to prevent flutter
# - Filters out-of-band noise
```

### Signal Detection (DCD)

Enable Data Carrier Detect for automatic squelching:

```python
decoder = CWDecoder(
    wpm=20,
    frequency=800,
    use_dcd=True,          # Enable DCD
    dcd_threshold=6.0      # Threshold in dB
)

# Check DCD status
stats = decoder.get_statistics()
if 'dcd_active' in stats:
    print(f"Signal present: {stats['dcd_active']}")
```

### Squelch Control

Set a squelch threshold to ignore weak signals:

```python
decoder = CWDecoder(
    wpm=20,
    frequency=800,
    squelch=50.0  # 0-100, only decode when metric > 50
)
```

### Prosign Support

The decoder automatically recognizes prosigns:

```python
from pydigi.modems import CW, CWDecoder

# Encode message with prosigns
encoder = CW(wpm=20, frequency=800)
audio = encoder.modulate("CQ DE W1ABC <AR> <SK>")

# Decode
decoder = CWDecoder(wpm=20, frequency=800)
text = decoder.demodulate(audio)

print(text)  # "CQ DE W1ABC <AR> <SK>"
```

Common prosigns:
- `<AR>` - End of message
- `<SK>` - End of contact
- `<BT>` - Break/separator
- `<KN>` - Invitation to specific station
- `<AS>` - Wait/standby

## Troubleshooting

### Problem: No Text Decoded

**Possible causes:**

1. **Wrong frequency** - Verify the CW tone frequency
   ```python
   # Try different frequencies
   for freq in [600, 700, 800, 900, 1000]:
       decoder = CWDecoder(wpm=20, frequency=freq)
       text = decoder.demodulate(audio[:10000])  # Test snippet
       if text:
           print(f"Found signal at {freq} Hz: {text}")
   ```

2. **Wrong WPM** - Speed mismatch prevents decoding
   ```python
   # Try different speeds
   for wpm in [15, 20, 25, 30]:
       decoder = CWDecoder(wpm=wpm, frequency=800)
       text = decoder.demodulate(audio)
       if text and '*' not in text:  # No decode errors
           print(f"Decoded at {wpm} WPM: {text}")
   ```

3. **Signal too weak** - Check SNR
   ```python
   decoder = CWDecoder(wpm=20, frequency=800, use_dcd=False)
   text = decoder.demodulate(audio)
   stats = decoder.get_statistics()
   print(f"SNR: {stats['snr_db']:.1f} dB")
   # Minimum ~0 dB needed
   ```

4. **Squelch too high** - Disable squelch
   ```python
   decoder = CWDecoder(wpm=20, frequency=800, squelch=None)
   ```

### Problem: Garbled Text (Many '*' Characters)

**Possible causes:**

1. **Speed mismatch** - WPM setting doesn't match actual speed
   ```python
   # Decoder needs accurate WPM (±5%)
   # If signal is 25 WPM, decoder should be 24-26 WPM
   decoder = CWDecoder(wpm=25, frequency=800)
   ```

2. **Bandwidth too narrow** - Increase filter bandwidth
   ```python
   decoder = CWDecoder(
       wpm=20,
       frequency=800,
       bandwidth=150.0  # Try wider bandwidth
   )
   ```

3. **Signal fading** - Check signal quality
   ```python
   stats = decoder.get_statistics()
   print(f"Signal quality: {stats['metric']:.1f}")  # Should be >20
   ```

### Problem: Missing Characters

**Possible causes:**

1. **Edge shaping** - Encoder uses raised cosine edges
   - Decoder accounts for this automatically
   - Ensure signal has clean key-up/down transitions

2. **Timing recovery** - Check signal timing
   ```python
   stats = decoder.get_statistics()
   print(f"Estimated WPM: {stats['wpm']:.1f}")
   # Should be close to expected WPM
   ```

### Problem: Extra Spaces

This can occur if:

1. **Actual spacing > 4 dit times** - Decoder interprets as word space
2. **Signal dropouts** - Causes premature word spacing

```python
# The decoder uses these spacing rules:
# - 2-4 dit times = character complete
# - >4 dit times = word space

# If you have non-standard spacing, adjust WPM setting
```

## Integration Examples

### With Audio Input

```python
from pydigi.modems import CWDecoder
import pyaudio

# Setup audio input
p = pyaudio.PyAudio()
stream = p.open(
    format=pyaudio.paFloat32,
    channels=1,
    rate=8000,
    input=True,
    frames_per_buffer=1024
)

# Create decoder
decoder = CWDecoder(
    wpm=20,
    sample_rate=8000,
    frequency=800,
    text_callback=lambda text: print(text, end='', flush=True)
)

# Process audio stream
print("Listening for CW signals...")
try:
    while True:
        audio_data = stream.read(1024)
        samples = np.frombuffer(audio_data, dtype=np.float32)
        decoder.process(samples)
except KeyboardInterrupt:
    print("\nStopped")

stream.close()
p.terminate()
```

### With GNU Radio

```python
import numpy as np
from pydigi.modems import CWDecoder

class CWDecoderBlock:
    """GNU Radio sink block for CW decoding."""

    def __init__(self, wpm=20, frequency=800):
        self.decoder = CWDecoder(
            wpm=wpm,
            frequency=frequency,
            sample_rate=8000
        )
        self.text_buffer = []
        self.decoder.text_callback = self.text_buffer.append

    def work(self, input_items, output_items):
        audio = input_items[0]
        self.decoder.process(audio)

        if self.text_buffer:
            text = ''.join(self.text_buffer)
            self.text_buffer.clear()
            print(text, end='', flush=True)

        return len(input_items[0])
```

### Logging and Statistics

```python
from pydigi.modems import CWDecoder
import datetime
import json

class LoggingCWDecoder:
    """CW decoder with logging."""

    def __init__(self, wpm, frequency, log_file):
        self.log_file = log_file
        self.decoder = CWDecoder(
            wpm=wpm,
            frequency=frequency,
            text_callback=self.on_char
        )

    def on_char(self, char):
        stats = self.decoder.get_statistics()

        log_entry = {
            'time': datetime.datetime.now().isoformat(),
            'char': char,
            'wpm': stats['wpm'],
            'snr_db': stats['snr_db'],
            'metric': stats['metric'],
        }

        with open(self.log_file, 'a') as f:
            f.write(json.dumps(log_entry) + '\n')

        print(char, end='', flush=True)

# Use it
decoder = LoggingCWDecoder(wpm=20, frequency=800, log_file='cw.log')
decoder.decoder.process(audio)
```

### Batch Processing Multiple Files

```python
from pydigi.modems import CWDecoder
from pydigi.utils.audio import load_wav
import os

def decode_cw_files(directory, wpm=20, frequency=800):
    """Decode all WAV files in a directory."""

    results = {}

    for filename in os.listdir(directory):
        if not filename.endswith('.wav'):
            continue

        filepath = os.path.join(directory, filename)
        print(f"Processing {filename}...")

        # Load and decode
        samples, sample_rate = load_wav(filepath)
        decoder = CWDecoder(
            wpm=wpm,
            sample_rate=sample_rate,
            frequency=frequency
        )

        text = decoder.demodulate(samples)
        stats = decoder.get_statistics()

        results[filename] = {
            'text': text,
            'wpm': stats['wpm'],
            'snr_db': stats['snr_db'],
            'errors': stats['decode_errors'],
            'error_rate': stats['error_rate']
        }

        print(f"  Decoded: {text}")
        print(f"  WPM: {stats['wpm']:.1f}, SNR: {stats['snr_db']:.1f} dB")
        print()

    return results

# Process all files
results = decode_cw_files('/path/to/cw/recordings', wpm=20, frequency=800)
```

## Performance

### Noise Immunity

The CW decoder is highly robust:

| SNR | Decoding Accuracy |
|-----|-------------------|
| 20 dB | 100% |
| 10 dB | 100% |
| 5 dB | 100% |
| 0 dB | 100% |
| -3 dB | 90-95% |

### Speed Range

Tested and verified at:

- **10 WPM**: ✓ Working
- **20 WPM**: ✓ Working (recommended)
- **30 WPM**: ✓ Working
- **40 WPM**: ✓ Working

### CPU Usage

Typical CPU usage (single core):
- **Decoding**: ~2-5%
- **With DCD**: +1-2%
- **Real-time**: No problem

### Memory Usage

- **Per decoder**: ~50 KB
- **Filter buffers**: ~10 KB
- **Total**: <100 KB per instance

## Best Practices

### 1. Set Accurate WPM

```python
# Good: Accurate WPM setting (±5%)
decoder = CWDecoder(wpm=20, frequency=800)

# Bad: Large WPM mismatch will fail
# If signal is 25 WPM, don't use wpm=15
```

### 2. Use Appropriate Bandwidth

```python
# Default 100 Hz is good for most cases
decoder = CWDecoder(wpm=20, frequency=800, bandwidth=100.0)

# Wider for noisy signals or key clicks
decoder = CWDecoder(wpm=20, frequency=800, bandwidth=150.0)
```

### 3. Disable DCD for Clean Signals

```python
# For known clean signals, DCD adds overhead
decoder = CWDecoder(wpm=20, frequency=800, use_dcd=False)

# For weak or noisy signals, enable DCD
decoder = CWDecoder(wpm=20, frequency=800, use_dcd=True)
```

### 4. Monitor Statistics

```python
def on_char(char):
    stats = decoder.get_statistics()
    if stats['snr_db'] < 3.0:
        print(f"WARNING: Low SNR: {stats['snr_db']:.1f} dB")
    if stats['error_rate'] > 0.1:
        print(f"WARNING: High error rate: {stats['error_rate']:.1%}")
    print(char, end='')
```

### 5. Handle Reset Properly

```python
# Reset between different signals
decoder.reset()

# Or create new decoder instance
decoder = CWDecoder(wpm=20, frequency=800)
```

## Next Steps

- [CW Encoder Guide](../api/reference/cw.md) - Transmitting CW
- [Decoder API Reference](../api/reference/decoder_api.md) - Low-level components
- [Examples](../../examples/cw_decoder_example.py) - Complete working examples

## FAQ

**Q: What WPM speed should I use?**
A: Set decoder WPM to match the transmitter speed (±5%). Use 20 WPM as a good starting point.

**Q: Do I need to know the exact frequency?**
A: Yes, CW requires knowing the tone frequency. Use a spectrum analyzer or waterfall display to find it.

**Q: Can I decode multiple CW signals at once?**
A: Yes, create one decoder per signal (at different frequencies). They operate independently.

**Q: Why do I get '*' characters in the output?**
A: '*' indicates decode errors, usually from:
- WPM mismatch (most common)
- Weak signal
- Noise interference
- Incorrect frequency

**Q: What's the minimum SNR needed?**
A: The decoder can work down to 0 dB SNR with high accuracy. Below -3 dB, errors increase.

**Q: How accurate is WPM estimation?**
A: Typically ±0.3 WPM when initial setting is close to actual speed.

**Q: Does it support Farnsworth spacing?**
A: Standard character spacing is supported. Farnsworth (extended character spacing) will work but may be interpreted as word spaces if spacing exceeds 4 dit times.

**Q: What sample rate should I use?**
A: 8000 Hz is recommended. Higher rates work but waste CPU. Minimum ~4000 Hz.
