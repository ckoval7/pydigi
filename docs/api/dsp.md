# DSP Core Reference

The `pydigi.core` module provides low-level DSP building blocks used by the modem implementations.

## Oscillators

### NCO (Numerically Controlled Oscillator)

Generate sine/cosine waves at precise frequencies.

```python
from pydigi.core import NCO

nco = NCO(sample_rate=8000, frequency=1000)
```

**Parameters**:
- `sample_rate` (float): Sample rate in Hz
- `frequency` (float): Initial frequency in Hz
- `phase` (float): Initial phase in radians (default: 0.0)

**Methods**:

#### `step_real(n)`
Generate real (cosine) samples.

```python
samples = nco.step_real(1000)  # Generate 1000 samples
```

Returns: `numpy.ndarray` of float

#### `step_complex(n)`
Generate complex samples (I/Q).

```python
samples = nco.step_complex(1000)  # Returns complex array
```

Returns: `numpy.ndarray` of complex

#### `set_frequency(freq)`
Update frequency.

```python
nco.set_frequency(1500)  # Change to 1500 Hz
```

#### `set_phase(phase)`
Set phase directly.

```python
nco.set_phase(np.pi/2)  # 90 degree phase shift
```

**Example**:
```python
from pydigi.core import NCO
import numpy as np

# Generate 1 second of 440 Hz tone
nco = NCO(sample_rate=8000, frequency=440)
audio = nco.step_real(8000)

# Generate complex baseband signal
nco_complex = NCO(sample_rate=8000, frequency=0)
baseband = nco_complex.step_complex(8000)
```

### generate_tone

Convenience function to generate a tone.

```python
from pydigi.core import generate_tone

tone = generate_tone(frequency=440, duration=1.0, sample_rate=8000)
```

**Parameters**:
- `frequency` (float): Frequency in Hz
- `duration` (float): Duration in seconds
- `sample_rate` (float): Sample rate in Hz
- `phase` (float): Initial phase in radians (default: 0.0)

**Returns**: `numpy.ndarray` of float samples

## Filters

### FIRFilter

Finite Impulse Response filter.

```python
from pydigi.core import FIRFilter
import numpy as np

# Create filter from coefficients
coeffs = np.array([0.1, 0.2, 0.4, 0.2, 0.1])
fir = FIRFilter(coeffs)

# Filter a signal
output = fir.filter_array(input_signal)
```

**Methods**:

#### `FIRFilter.design_lowpass(length, cutoff, window='hamming')`

Design a lowpass filter.

```python
lpf = FIRFilter.design_lowpass(
    length=64,           # Number of taps
    cutoff=0.1,         # Normalized cutoff (0 to 0.5)
    window='hamming'    # Window type
)
```

**Parameters**:
- `length` (int): Filter length (number of taps)
- `cutoff` (float): Normalized cutoff frequency (0 to 0.5)
- `window` (str): Window type ('hamming', 'hann', 'blackman', etc.)

**Returns**: `FIRFilter` instance

#### `filter_array(input)`

Filter an array of samples.

```python
filtered = fir.filter_array(signal)
```

**Parameters**:
- `input` (numpy.ndarray): Input samples (real or complex)

**Returns**: `numpy.ndarray` of same type as input

**Example**:
```python
from pydigi.core import FIRFilter
import numpy as np

# Design a lowpass filter
lpf = FIRFilter.design_lowpass(length=64, cutoff=0.1)

# Generate noisy signal
signal = np.random.randn(1000) + 0j
signal += np.exp(2j * np.pi * 0.05 * np.arange(1000))  # Add tone

# Filter it
filtered = lpf.filter_array(signal)
```

### MovingAverageFilter

Simple moving average filter (efficient boxcar filter).

```python
from pydigi.core import MovingAverageFilter

maf = MovingAverageFilter(length=16)
output = maf.filter_array(input_signal)
```

**Parameters**:
- `length` (int): Window length

**Methods**: Same as `FIRFilter`

**Example**:
```python
from pydigi.core import MovingAverageFilter

# Smooth a signal
smoother = MovingAverageFilter(length=32)
smoothed = smoother.filter_array(noisy_signal)
```

### GoertzelFilter

Efficient single-frequency tone detector.

```python
from pydigi.core import GoertzelFilter

goertzel = GoertzelFilter(
    frequency=1000,
    sample_rate=8000,
    N=256
)

magnitude = goertzel.magnitude(signal)
```

**Parameters**:
- `frequency` (float): Frequency to detect in Hz
- `sample_rate` (float): Sample rate in Hz
- `N` (int): Number of samples to process

**Methods**:

#### `magnitude(samples)`

Compute magnitude at target frequency.

```python
mag = goertzel.magnitude(signal_chunk)
```

**Returns**: `float` - Magnitude

## FFT Functions

### fft

Forward FFT.

```python
from pydigi.core import fft

spectrum = fft(signal)
```

**Parameters**:
- `signal` (numpy.ndarray): Time-domain signal

**Returns**: `numpy.ndarray` of complex values

### ifft

Inverse FFT.

```python
from pydigi.core import ifft

signal = ifft(spectrum)
```

**Parameters**:
- `spectrum` (numpy.ndarray): Frequency-domain spectrum

**Returns**: `numpy.ndarray` of complex values

### power_spectrum

Compute power spectrum.

```python
from pydigi.core import power_spectrum

power = power_spectrum(signal)
```

**Returns**: `numpy.ndarray` of power values (linear scale)

### power_spectrum_db

Compute power spectrum in dB.

```python
from pydigi.core import power_spectrum_db

power_db = power_spectrum_db(signal)
```

**Returns**: `numpy.ndarray` of power values in dB

**Example**:
```python
from pydigi.core import fft, power_spectrum_db
import numpy as np

# Generate signal with two tones
t = np.arange(1024) / 8000
signal = np.sin(2*np.pi*440*t) + 0.5*np.sin(2*np.pi*880*t)

# Compute spectrum
spectrum = fft(signal)
power_db = power_spectrum_db(signal)

# Find peak
peak_bin = np.argmax(power_db)
peak_freq = peak_bin * 8000 / 1024
print(f"Peak at {peak_freq:.1f} Hz")
```

## Fast Hartley Transform

### fht_forward

Forward Fast Hartley Transform.

```python
from pydigi.core import fht_forward

result = fht_forward(signal)
```

Used in MFSK demodulation.

### fht_inverse

Inverse Fast Hartley Transform.

```python
from pydigi.core import fht_inverse

signal = fht_inverse(transformed)
```

## Encoders

### Viterbi Encoder/Decoder

Forward error correction encoding.

```python
from pydigi.core import Encoder

encoder = Encoder(constraint=7, rate=0.5)
encoded = encoder.encode(data)
```

Used in EightPSKFEC (8-PSK with FEC), Olivia, Contestia, etc.

### Interleaver

Interleave/deinterleave data for burst error protection.

```python
from pydigi.core import Interleaver

interleaver = Interleaver(size=100)
interleaved = interleaver.interleave(data)
deinterleaved = interleaver.deinterleave(interleaved)
```

**Parameters**:
- `size` (int): Interleaver depth

**Methods**:
- `interleave(data)` - Interleave data array
- `deinterleave(data)` - Deinterleave data array

## MFSK-Specific DSP

### MFSKEncoder

MFSK encoding with varicode and FEC.

```python
from pydigi.core import MFSKEncoder

encoder = MFSKEncoder(
    tones=16,
    use_fec=True,
    use_image=False
)

symbols = encoder.encode_text("HELLO")
```

**Parameters**:
- `tones` (int): Number of tones
- `use_fec` (bool): Enable FEC
- `use_image` (bool): Enable image coding (DominoEX)

### MFSKModulator

Generate MFSK modulated audio.

```python
from pydigi.core import MFSKModulator

modulator = MFSKModulator(
    tones=16,
    bandwidth=250,
    sample_rate=8000,
    frequency=1500
)

audio = modulator.modulate_symbols(symbols)
```

**Parameters**:
- `tones` (int): Number of tones
- `bandwidth` (float): Signal bandwidth in Hz
- `sample_rate` (float): Sample rate in Hz
- `frequency` (float): Center frequency in Hz

## DSP Utilities

### blackman

Generate Blackman window.

```python
from pydigi.core.dsp_utils import blackman

window = blackman(n=64)
```

### hamming

Generate Hamming window.

```python
from pydigi.core.dsp_utils import hamming

window = hamming(n=64)
```

### hann

Generate Hann window.

```python
from pydigi.core.dsp_utils import hann

window = hann(n=64)
```

### sinc

Sinc function (sin(x)/x).

```python
from pydigi.core.dsp_utils import sinc

y = sinc(x)
```

### raised_cosine

Raised cosine pulse shape.

```python
from pydigi.core.dsp_utils import raised_cosine

pulse = raised_cosine(
    length=128,
    alpha=0.5,
    sample_rate=8000,
    symbol_rate=31.25
)
```

**Parameters**:
- `length` (int): Pulse length in samples
- `alpha` (float): Rolloff factor (0 to 1)
- `sample_rate` (float): Sample rate in Hz
- `symbol_rate` (float): Symbol rate in Hz

## Complete Example

```python
from pydigi.core import NCO, FIRFilter, fft, power_spectrum_db
import numpy as np
import matplotlib.pyplot as plt

# Generate a PSK-like signal
sample_rate = 8000
nco = NCO(sample_rate=sample_rate, frequency=1000)

# Create some random data
bits = np.random.randint(0, 2, 100)

# BPSK modulation (manually)
symbols = 2*bits - 1  # Convert 0/1 to -1/+1
samples_per_symbol = 256
signal = []

for symbol in symbols:
    carrier = nco.step_complex(samples_per_symbol)
    modulated = carrier * symbol
    signal.extend(modulated)

signal = np.array(signal)

# Filter the signal
lpf = FIRFilter.design_lowpass(length=64, cutoff=0.05)
filtered = lpf.filter_array(signal)

# Analyze spectrum
power_db = power_spectrum_db(filtered)
freqs = np.fft.fftfreq(len(filtered), 1/sample_rate)

# Plot
plt.figure(figsize=(12, 4))
plt.plot(freqs[:len(freqs)//2], power_db[:len(power_db)//2])
plt.xlabel('Frequency (Hz)')
plt.ylabel('Power (dB)')
plt.title('BPSK Signal Spectrum')
plt.grid()
plt.show()
```

## See Also

- [API Overview](overview.md) - General API patterns
- [Modem Classes](modems.md) - High-level modem APIs
- [Examples](../examples/advanced.md) - Advanced DSP examples
