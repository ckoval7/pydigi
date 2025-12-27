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

## See Also

- [Basic Examples](basic.md)
- [GNU Radio Integration](gnuradio.md)
- [API Reference](../api/overview.md)
