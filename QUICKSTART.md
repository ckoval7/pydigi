# PyDigi Quick Start Guide

## Installation

```bash
cd /home/corey/pydigi
pip install -e .
```

Or with development dependencies:
```bash
pip install -e ".[dev]"
```

## Basic Usage

### CW (Morse Code)

```python
from pydigi import CW, save_wav

# Create a CW modem
cw = CW(wpm=20, frequency=800)

# Generate audio
audio = cw.modulate("HELLO WORLD")

# Save to WAV file
save_wav("cw_output.wav", audio, sample_rate=8000)
```

### RTTY (Radioteletype)

```python
from pydigi import RTTY, save_wav

# Create RTTY modem (45.45 baud, 170 Hz shift)
rtty = RTTY(baud=45.45, shift=170)

# Generate audio
audio = rtty.modulate("RYRYRY THE QUICK BROWN FOX", frequency=1500)

# Save to WAV file
save_wav("rtty_output.wav", audio, sample_rate=8000)
```

### PSK31 (Phase Shift Keying)

```python
from pydigi import PSK31, save_wav

# Create PSK31 modem
psk = PSK31()

# Generate audio
audio = psk.modulate("CQ CQ CQ DE W1ABC", frequency=1000)

# Save to WAV file
save_wav("psk31_output.wav", audio, sample_rate=8000)
```

### MFSK16 (Multi-Frequency Shift Keying)

```python
from pydigi import MFSK16, save_wav

# Create MFSK16 modem
mfsk = MFSK16()

# Generate audio
audio = mfsk.modulate("MFSK16 TEST MESSAGE", frequency=1500)

# Save to WAV file
save_wav("mfsk16_output.wav", audio, sample_rate=8000)
```

### Olivia (Robust MFSK with FEC)

```python
from pydigi import Olivia16_500, save_wav

# Create Olivia 16/500 modem
olivia = Olivia16_500()

# Generate audio
audio = olivia.modulate("OLIVIA TEST", frequency=1500)

# Save to WAV file
save_wav("olivia_output.wav", audio, sample_rate=8000)
```

### SCAMP (Spread Spectrum with Golay FEC)

```python
from pydigi import SCAMPFSK, save_wav

# Create SCAMP FSK modem
scamp = SCAMPFSK()

# Generate audio
audio = scamp.modulate("SCAMP TEST MESSAGE", frequency=1000)

# Save to WAV file
save_wav("scamp_output.wav", audio, sample_rate=8000)
```

**All modes decode correctly in fldigi!**

### Customize CW Parameters

```python
from pydigi import CW

# Different speeds and frequencies
cw = CW(
    wpm=25,              # Words per minute (5-200)
    frequency=1000,      # Tone frequency in Hz
    rise_time=4.0,       # Edge rise time in ms
    sample_rate=8000     # Sample rate in Hz
)

audio = cw.modulate("CQ CQ CQ DE W1ABC K")
```

### Use Prosigns

```python
cw = CW(wpm=20)

# Prosigns are enclosed in < >
text = "TEST <AR> <SK>"  # AR = end of message, SK = end of contact
audio = cw.modulate(text)
```

Common prosigns:
- `<AR>` - End of message (.-.-.)
- `<SK>` - End of contact (...-.- )
- `<BT>` - Break (-...-)
- `<KN>` - Invitation to specific station (-.--.)

### Estimate Duration

```python
cw = CW(wpm=20)

duration = cw.estimate_duration("HELLO WORLD")
print(f"Transmission will take {duration:.2f} seconds")
```

## Working with Audio

### Load WAV Files

```python
from pydigi import load_wav

audio, sample_rate = load_wav("input.wav")
print(f"Loaded {len(audio)} samples at {sample_rate} Hz")
```

### Audio Utilities

```python
from pydigi.utils.audio import rms, peak, normalize, db_to_linear

# Get signal statistics
rms_value = rms(audio)
peak_value = peak(audio)

# Normalize to specific level
normalized = normalize(audio, target_peak=0.9)

# Convert dB to linear
amplitude = db_to_linear(-3.0)  # -3 dB = 0.707
```

## Using DSP Components Directly

### Generate Tones with NCO

```python
from pydigi.core import NCO, generate_tone

# Using NCO class
nco = NCO(sample_rate=8000, frequency=440)
samples = nco.step_real(8000)  # Generate 1 second of 440 Hz

# Using convenience function
tone = generate_tone(frequency=440, duration=1.0, sample_rate=8000)
```

### Apply Filters

```python
from pydigi.core import FIRFilter
import numpy as np

# Design a lowpass filter
lpf = FIRFilter.design_lowpass(
    length=64,
    cutoff=0.1,  # Normalized frequency (0 to 0.5)
    window='hamming'
)

# Filter a signal
signal = np.random.randn(1000) + 0j  # Complex signal
filtered = lpf.filter_array(signal)
```

### FFT Analysis

```python
from pydigi.core import power_spectrum_db, fft
import numpy as np

# Generate a signal
signal = np.sin(2 * np.pi * 440 * np.arange(8000) / 8000)

# Compute power spectrum in dB
spectrum_db = power_spectrum_db(signal)

# Or use FFT directly
spectrum = fft(signal)
```

## Running Examples

```bash
# CW examples
python examples/cw_example.py

# RTTY examples
python examples/rtty_example.py

# PSK examples
python examples/psk_example.py
```

Each example script generates multiple WAV files demonstrating different features and modes.

## Testing Your Installation

```python
from pydigi import CW
import numpy as np

# Quick test
cw = CW()
audio = cw.modulate("TEST")

print(f"Generated {len(audio)} samples")
print(f"Peak amplitude: {np.max(np.abs(audio)):.3f}")
print(f"Sample rate: {cw.sample_rate} Hz")

# Should print something like:
# Generated 9600 samples
# Peak amplitude: 1.000
# Sample rate: 8000 Hz
```

## Next Steps

1. **Validate with fldigi:** Open the generated WAV files in fldigi to verify they decode correctly
   - All 20 mode families decode perfectly!
2. **Experiment with parameters:**
   - CW: Try different WPM speeds, frequencies, and rise times
   - RTTY: Different baud rates (45, 45.45, 50, 75) and shifts (170, 200, 425, 850 Hz)
   - PSK: All variants (PSK31/63/125/250/500, QPSK, 8PSK, Multi-carrier)
   - MFSK: Different tone counts and bandwidths (MFSK8/16/32, Olivia, Contestia)
   - SCAMP: All 6 variants (FSK/OOK modes at different speeds)
3. **GNU Radio integration:** Use the numpy arrays directly in GNU Radio flowgraphs
4. **Explore robust modes:** Try Olivia, Contestia, or MT63 for challenging conditions
5. **Advanced modes:** Experiment with Thor, DominoEX, or multi-carrier PSK-R

## Troubleshooting

### Import errors
Make sure you installed the package:
```bash
pip install -e .
```

### WAV files won't play
The WAV files are mono, 8 kHz, 16-bit PCM. Some players may need explicit codec support.

### Audio clipping
If you see warnings about clipping, the modem automatically normalizes to [-1.0, 1.0]. This is normal.

## Getting Help

- Check `README.md` for general information
- See `PROJECT_TRACKER.md` for implementation status
- Read `IMPLEMENTATION_SUMMARY.md` for technical details
- Refer to docstrings in the source code

## API Reference

### Main Imports
```python
from pydigi import CW              # CW modem
from pydigi import RTTY            # RTTY modem
from pydigi import PSK31, PSK63, PSK125, QPSK31, QPSK63  # PSK modems
from pydigi import MFSK16, MFSK32  # MFSK modems
from pydigi import Olivia16_500, Contestia8_250  # Olivia/Contestia
from pydigi import DominoEX_16, Thor22  # DominoEX/Thor
from pydigi import MT63_1000L      # MT63 modem
from pydigi import SCAMPFSK, SCAMPOOK  # SCAMP modems
from pydigi import save_wav        # Save audio to WAV
from pydigi import load_wav        # Load WAV file
```

### Core Components
```python
from pydigi.core import NCO                # Oscillator
from pydigi.core import FIRFilter          # FIR filter
from pydigi.core import MovingAverageFilter  # Moving average
from pydigi.core import GoertzelFilter     # Tone detector
from pydigi.core import fft, ifft          # FFT functions
```

### Utilities
```python
from pydigi.utils.audio import rms, peak, normalize
from pydigi.utils.constants import DEFAULT_SAMPLE_RATE
```
