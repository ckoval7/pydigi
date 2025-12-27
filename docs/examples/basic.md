# Basic Usage Examples

This page shows common usage patterns for PyDigi.

## Getting Started

### Import and Create a Modem

```python
from pydigi import PSK31, save_wav

# Create a modem
psk = PSK31(frequency=1000)

# Generate audio
audio = psk.modulate("HELLO WORLD")

# Save to file
save_wav("output.wav", audio, sample_rate=psk.sample_rate)
```

## Simple Examples by Mode

### CW (Morse Code)

```python
from pydigi import CW, save_wav

# Create CW modem at 20 WPM
cw = CW(wpm=20, frequency=800)

# Transmit with prosigns
text = "CQ CQ CQ DE W1ABC W1ABC <AR> <SK>"
audio = cw.modulate(text)

save_wav("cw_test.wav", audio, sample_rate=cw.sample_rate)

# Estimate duration
duration = cw.estimate_duration(text)
print(f"Transmission duration: {duration:.2f} seconds")
```

### RTTY

```python
from pydigi import RTTY, save_wav

# Standard RTTY (45.45 baud, 170 Hz shift)
rtty = RTTY(baud=45.45, shift=170, frequency=1500)

# Test message
text = "RYRYRY THE QUICK BROWN FOX JUMPS OVER THE LAZY DOG"
audio = rtty.modulate(text)

save_wav("rtty_test.wav", audio, sample_rate=rtty.sample_rate)
```

### PSK31

```python
from pydigi import PSK31, save_wav

# Create PSK31 modem
psk = PSK31(frequency=1000)

# Typical PSK31 QSO
text = """
CQ CQ CQ DE W1ABC W1ABC PSK31 K
"""

audio = psk.modulate(text.strip())
save_wav("psk31_cq.wav", audio, sample_rate=psk.sample_rate)
```

### MFSK16

```python
from pydigi import MFSK16, save_wav

# Create MFSK16 modem
mfsk = MFSK16(frequency=1500)

# Generate signal
audio = mfsk.modulate("MFSK16 TEST MESSAGE")
save_wav("mfsk16_test.wav", audio, sample_rate=mfsk.sample_rate)
```

### Olivia 8/250

```python
from pydigi import Olivia8_250, save_wav

# Create Olivia modem (8 tones, 250 Hz bandwidth)
olivia = Olivia8_250(frequency=1500)

# Olivia is robust in poor conditions
audio = olivia.modulate("OLIVIA TEST - ROBUST MODE")
save_wav("olivia_test.wav", audio, sample_rate=olivia.sample_rate)
```

## Working with Audio Files

### Save to WAV

```python
from pydigi import PSK31, save_wav

psk = PSK31()
audio = psk.modulate("TEST MESSAGE")

# Save as 16-bit WAV (default)
save_wav("output_16bit.wav", audio, sample_rate=8000, bits=16)

# Save as 24-bit WAV
save_wav("output_24bit.wav", audio, sample_rate=8000, bits=24)
```

### Load from WAV

```python
from pydigi.utils.audio import load_wav

# Load audio file
audio, sample_rate = load_wav("input.wav")

print(f"Loaded {len(audio)} samples")
print(f"Sample rate: {sample_rate} Hz")
print(f"Duration: {len(audio)/sample_rate:.2f} seconds")
```

### Normalize Audio

```python
from pydigi import PSK31
from pydigi.utils.audio import normalize, save_wav, peak

psk = PSK31()
audio = psk.modulate("TEST")

# Check original level
print(f"Original peak: {peak(audio):.3f}")

# Normalize to -3 dB (0.707)
normalized = normalize(audio, target_peak=0.707)
print(f"Normalized peak: {peak(normalized):.3f}")

save_wav("normalized.wav", normalized, sample_rate=8000)
```

## Comparing Modes

### Same Message, Multiple Modes

```python
from pydigi import PSK31, PSK63, QPSK31, MFSK16, save_wav

text = "TESTING 123"

modes = [
    ("PSK31", PSK31()),
    ("PSK63", PSK63()),
    ("QPSK31", QPSK31()),
    ("MFSK16", MFSK16()),
]

print(f"{'Mode':<10} {'Duration':<10} {'Samples':<10}")
print("-" * 30)

for mode_name, modem in modes:
    audio = modem.modulate(text, frequency=1000)
    duration = len(audio) / modem.sample_rate

    print(f"{mode_name:<10} {duration:<10.3f} {len(audio):<10}")

    filename = f"{mode_name.lower()}_test.wav"
    save_wav(filename, audio, sample_rate=modem.sample_rate)
```

### Speed Comparison

```python
from pydigi import PSK31, PSK63, PSK125, PSK250

text = "THE QUICK BROWN FOX JUMPS OVER THE LAZY DOG"

modems = [PSK31(), PSK63(), PSK125(), PSK250()]

for modem in modems:
    duration = modem.estimate_duration(text)
    wpm = len(text.split()) / (duration / 60)

    print(f"{modem.mode_name:8} {duration:6.2f}s  ~{wpm:.0f} WPM")
```

## Different Frequencies

### Generate Signals at Different Frequencies

```python
from pydigi import PSK31, save_wav

psk = PSK31()
text = "FREQ TEST"

frequencies = [500, 1000, 1500, 2000, 2500]

for freq in frequencies:
    audio = psk.modulate(text, frequency=freq)
    filename = f"psk31_{freq}hz.wav"
    save_wav(filename, audio, sample_rate=psk.sample_rate)
    print(f"Generated {filename} at {freq} Hz")
```

## Measuring Signal Levels

### Check Audio Levels

```python
from pydigi import PSK31
from pydigi.utils.audio import rms, peak, linear_to_db

psk = PSK31()
audio = psk.modulate("TESTING LEVELS")

# Measure levels
rms_value = rms(audio)
peak_value = peak(audio)

# Convert to dB
rms_db = linear_to_db(rms_value)
peak_db = linear_to_db(peak_value)

print(f"RMS:  {rms_value:.4f} ({rms_db:+.2f} dB)")
print(f"Peak: {peak_value:.4f} ({peak_db:+.2f} dB)")
```

## Custom Parameters

### CW with Different Speeds

```python
from pydigi import CW, save_wav

text = "PARIS"  # Standard test word

speeds = [10, 15, 20, 25, 30]  # WPM

for wpm in speeds:
    cw = CW(wpm=wpm, frequency=800)
    audio = cw.modulate(text)
    duration = cw.estimate_duration(text)

    filename = f"cw_{wpm}wpm.wav"
    save_wav(filename, audio, sample_rate=cw.sample_rate)

    print(f"{wpm} WPM: {duration:.2f}s - {filename}")
```

### RTTY with Different Shifts

```python
from pydigi import RTTY, save_wav

text = "RYRYRY"

shifts = [170, 200, 425, 850]  # Common RTTY shifts

for shift in shifts:
    rtty = RTTY(baud=45.45, shift=shift, frequency=1500)
    audio = rtty.modulate(text)

    filename = f"rtty_{shift}hz_shift.wav"
    save_wav(filename, audio, sample_rate=rtty.sample_rate)

    print(f"{shift} Hz shift - {filename}")
```

### PSK with Custom Preamble

```python
from pydigi import PSK31, save_wav

psk = PSK31()
text = "SHORT MSG"

# Short preamble (16 symbols)
audio_short = psk.modulate(text, preamble_symbols=16)

# Default preamble (32 symbols)
audio_default = psk.modulate(text)

# Long preamble (64 symbols)
audio_long = psk.modulate(text, preamble_symbols=64)

save_wav("psk_short_preamble.wav", audio_short, sample_rate=8000)
save_wav("psk_default_preamble.wav", audio_default, sample_rate=8000)
save_wav("psk_long_preamble.wav", audio_long, sample_rate=8000)

print(f"Short:   {len(audio_short)} samples")
print(f"Default: {len(audio_default)} samples")
print(f"Long:    {len(audio_long)} samples")
```

## Batch Processing

### Generate Multiple Files

```python
from pydigi import PSK31, save_wav
import os

# Create output directory
os.makedirs("output", exist_ok=True)

psk = PSK31()

messages = [
    "CQ CQ CQ DE W1ABC",
    "TEST MESSAGE 1",
    "TEST MESSAGE 2",
    "73 DE W1ABC SK",
]

for i, msg in enumerate(messages):
    audio = psk.modulate(msg)
    filename = f"output/message_{i+1:02d}.wav"
    save_wav(filename, audio, sample_rate=psk.sample_rate)
    print(f"Created {filename}")
```

## Next Steps

- [Advanced Examples](advanced.md) - More complex usage patterns
- [GNU Radio Integration](gnuradio.md) - Using with GNU Radio
- [API Reference](../api/overview.md) - Complete API documentation
