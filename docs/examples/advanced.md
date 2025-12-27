# Advanced Examples

Advanced usage patterns for PyDigi.

## Custom DSP

### Using NCO Directly

```python
from pydigi.core import NCO
import numpy as np

# Create oscillator
nco = NCO(sample_rate=8000, frequency=1000)

# Generate complex baseband signal
iq_samples = nco.step_complex(1000)

# Generate real carrier
carrier = nco.step_real(1000)
```

### Applying Custom Filters

```python
from pydigi.core import FIRFilter
from pydigi import PSK31
import numpy as np

# Generate PSK31 signal
psk = PSK31()
audio = psk.modulate("TEST MESSAGE")

# Design custom filter
lpf = FIRFilter.design_lowpass(
    length=128,
    cutoff=0.05,
    window='blackman'
)

# Apply filter
filtered = lpf.filter_array(audio.astype(complex))
```

## Batch Processing

### Generate Test Signals

```python
from pydigi import PSK31, PSK63, QPSK31, save_wav
import os

# Create output directory
os.makedirs("test_signals", exist_ok=True)

modes = [PSK31(), PSK63(), QPSK31()]
frequencies = [500, 1000, 1500, 2000]

for modem in modes:
    for freq in frequencies:
        audio = modem.modulate("TEST", frequency=freq)
        filename = f"test_signals/{modem.mode_name}_{freq}hz.wav"
        save_wav(filename, audio, sample_rate=8000)
```

## Sample Rate Conversion

### Basic Resampling

```python
from pydigi.modems.scamp import SCAMP
from pydigi.utils import resample_to_48k, save_wav

# SCAMP is locked at 8000 Hz
scamp = SCAMP(mode='SCAMPFSK', frequency=1500)
audio_8k = scamp.modulate("HELLO WORLD")

# Resample to 48000 Hz for modern audio hardware
audio_48k = resample_to_48k(audio_8k)

# Save at high sample rate
save_wav("scamp_48khz.wav", audio_48k, sample_rate=48000)
```

### Modem-Aware Resampling

```python
from pydigi import PSK31
from pydigi.utils import resample_from_modem, save_wav

# Generate at native sample rate
psk31 = PSK31(sample_rate=8000)
audio = psk31.modulate("CQ CQ DE W1ABC")

# Automatically detect and resample to target rate
audio_44k = resample_from_modem(audio, psk31, 44100)

save_wav("psk31_44khz.wav", audio_44k, sample_rate=44100)
```

### Using Presets

```python
from pydigi.modems.scamp import SCAMP
from pydigi.utils import resample_preset

# Generate signal
scamp = SCAMP(mode='SCAMPFSK')
audio = scamp.modulate("TEST")

# Use convenient presets for common conversions
audio_48k = resample_preset(audio, '8k_to_48k')
audio_44k = resample_preset(audio, '8k_to_44k')
audio_16k = resample_preset(audio, '8k_to_16k')
```

### Resampling Quality Information

```python
from pydigi.utils import get_resampling_info

# Get detailed info about a resampling operation
info = get_resampling_info(8000, 48000)

print(f"Ratio: {info['ratio']}")  # 6.0
print(f"Quality: {info['quality']}")  # 'perfect'
print(f"Method: {info['recommended_method']}")  # 'polyphase'
print(f"Up/Down: {info['up']}/{info['down']}")  # 6/1
```

## See Also

- [Basic Examples](basic.md)
- [GNU Radio Integration](gnuradio.md)
- [API Reference](../api/overview.md)
