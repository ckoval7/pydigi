# Installation

## Requirements

- Python 3.8 or later
- NumPy >= 1.20.0
- SciPy >= 1.7.0

## Install from Source

Clone the repository and install in development mode:

```bash
git clone https://github.com/yourusername/pydigi.git
cd pydigi
pip install -e .
```

## Install with Development Dependencies

For development work (testing, documentation building):

```bash
pip install -e ".[dev]"
```

This includes:
- pytest for running tests
- mkdocs-material for building documentation
- Additional development tools

## Verify Installation

Test that PyDigi is installed correctly:

```python
from pydigi import PSK31
import numpy as np

# Quick test
psk = PSK31()
audio = psk.modulate("TEST")

print(f"Generated {len(audio)} samples")
print(f"Peak amplitude: {np.max(np.abs(audio)):.3f}")
print(f"Sample rate: {psk.sample_rate} Hz")
```

Expected output:
```
Generated 9600 samples
Peak amplitude: 1.000
Sample rate: 8000 Hz
```

## Optional Dependencies

### For WAV file support
PyDigi includes built-in WAV file support using Python's wave module and NumPy. No additional dependencies needed.

### For GNU Radio integration
PyDigi returns standard numpy arrays that work directly with GNU Radio. Install GNU Radio separately if needed:

```bash
# Via conda (recommended)
conda install -c conda-forge gnuradio

# Or via package manager
sudo apt install gnuradio  # Ubuntu/Debian
```

### For audio playback
To play generated audio directly:

```bash
pip install sounddevice
```

Example:
```python
import sounddevice as sd
from pydigi import PSK31

psk = PSK31()
audio = psk.modulate("HELLO")
sd.play(audio, psk.sample_rate)
sd.wait()
```

## Troubleshooting

### Import errors
If you get import errors, make sure you installed the package:
```bash
pip install -e .
```

### NumPy/SciPy issues
Update to the latest versions:
```bash
pip install --upgrade numpy scipy
```

### Permission errors on Linux
If you get permission errors during install:
```bash
pip install --user -e .
```

## Next Steps

- Try the [Quick Start](quickstart.md) guide
- Explore the [API Reference](api/overview.md)
- Run the example scripts in `examples/`
