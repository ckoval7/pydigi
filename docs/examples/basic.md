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

### NAVTEX (Maritime Safety Broadcast)

```python
from pydigi import NAVTEX, SITORB, save_wav

# Create NAVTEX modem (includes headers, phasing, and FEC)
navtex = NAVTEX(frequency=1000)

# Maritime safety message - header and trailer added automatically
text = "WEATHER WARNING: GALE FORCE 8 EXPECTED IN SEA AREA VIKING"
audio = navtex.modulate(text)

# NAVTEX uses 11025 Hz sample rate (100 baud, 170 Hz shift)
save_wav("navtex_test.wav", audio, sample_rate=11025)

# Or use SITOR-B for raw transmission without NAVTEX structure
sitorb = SITORB(frequency=1000)
audio = sitorb.modulate("CQ CQ CQ DE NAVAREA1 K")
save_wav("sitorb_test.wav", audio, sample_rate=11025)
```

### WEFAX (Weather Facsimile - Image Transmission)

```python
from pydigi import WEFAX576, save_wav
import numpy as np

# Create WEFAX-576 modem
wefax = WEFAX576()

# Option 1: Transmit test pattern (no image needed)
audio_test = wefax.modulate("")
save_wav("wefax_test.wav", audio_test, sample_rate=11025)

# Option 2: Transmit from numpy array
# Create gradient image (200 rows x 1809 columns)
img = np.zeros((200, 1809), dtype=np.uint8)
for col in range(1809):
    img[:, col] = int(255 * col / 1809)

audio_gradient = wefax.transmit_image(img, lpm=120)
save_wav("wefax_gradient.wav", audio_gradient, sample_rate=11025)

# Option 3: Transmit from image file (requires Pillow)
# audio = wefax.transmit_image("weather_map.png")
# save_wav("wefax_image.wav", audio, sample_rate=11025)
```

**Note:** WEFAX transmits images, not text. Use `transmit_image()` for image data.

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

## Silence Padding

### Add Silence Before and After Signal

```python
from pydigi import PSK31, CW, save_wav

# Set default silence at modem creation
psk = PSK31(leading_silence=0.5, trailing_silence=0.5)
audio = psk.modulate("TEST MESSAGE")
save_wav("psk_with_silence.wav", audio, sample_rate=psk.sample_rate)

# Override per transmission
cw = CW(wpm=20)
audio = cw.modulate("CQ DE W1ABC", leading_silence=1.0, trailing_silence=0.5)
save_wav("cw_with_silence.wav", audio, sample_rate=cw.sample_rate)
```

### Use Cases for Silence Padding

```python
from pydigi import RTTY, save_wav

rtty = RTTY(baud=45.45, shift=170)

# PTT activation (1 second lead-in for transmitter to stabilize)
audio = rtty.modulate("RYRYRY", leading_silence=1.0, trailing_silence=0.5)
save_wav("rtty_ptt.wav", audio, sample_rate=rtty.sample_rate)

# VOX triggering (500ms lead-in for VOX to activate)
audio = rtty.modulate("TEST", leading_silence=0.5, trailing_silence=0.3)
save_wav("rtty_vox.wav", audio, sample_rate=rtty.sample_rate)

# Visual separation (easy to see start/end in audio editor)
audio = rtty.modulate("DEBUG", leading_silence=0.2, trailing_silence=0.2)
save_wav("rtty_debug.wav", audio, sample_rate=rtty.sample_rate)
```

### Calculating Total Duration

```python
from pydigi import PSK31

psk = PSK31()
text = "HELLO WORLD"

# Without silence
audio_no_silence = psk.modulate(text)
duration_no_silence = len(audio_no_silence) / psk.sample_rate

# With silence
audio_with_silence = psk.modulate(text, leading_silence=0.5, trailing_silence=0.5)
duration_with_silence = len(audio_with_silence) / psk.sample_rate

print(f"Without silence: {duration_no_silence:.2f}s ({len(audio_no_silence)} samples)")
print(f"With silence: {duration_with_silence:.2f}s ({len(audio_with_silence)} samples)")
print(f"Added silence: {duration_with_silence - duration_no_silence:.2f}s")
```

## Next Steps

- [Advanced Examples](advanced.md) - More complex usage patterns
- [GNU Radio Integration](gnuradio.md) - Using with GNU Radio
- [API Reference](../api/overview.md) - Complete API documentation
