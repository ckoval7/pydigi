# Audio Utilities Reference

The `pydigi.utils.audio` module provides utilities for audio file I/O and signal processing.

## WAV File I/O

### save_wav

Save audio samples to a WAV file.

```python
from pydigi.utils.audio import save_wav

save_wav(filename, audio, sample_rate=8000, bits=16)
```

**Parameters**:
- `filename` (str): Output WAV file path
- `audio` (numpy.ndarray): Audio samples (float, range [-1.0, 1.0])
- `sample_rate` (int): Sample rate in Hz (default: 8000)
- `bits` (int): Bit depth - 16 or 24 (default: 16)

**Example**:
```python
from pydigi import PSK31, save_wav

psk = PSK31()
audio = psk.modulate("TEST")
save_wav("output.wav", audio, sample_rate=psk.sample_rate)
```

**Details**:
- Automatically converts float [-1.0, 1.0] to integer PCM
- Creates mono (single channel) WAV files
- Normalizes if input exceeds [-1.0, 1.0] range
- Raises warning if clipping occurs

### load_wav

Load audio samples from a WAV file.

```python
from pydigi.utils.audio import load_wav

audio, sample_rate = load_wav(filename)
```

**Parameters**:
- `filename` (str): Input WAV file path

**Returns**:
- `audio` (numpy.ndarray): Audio samples as float in range [-1.0, 1.0]
- `sample_rate` (int): Sample rate in Hz

**Example**:
```python
from pydigi.utils.audio import load_wav

audio, sr = load_wav("input.wav")
print(f"Loaded {len(audio)} samples at {sr} Hz")
```

**Details**:
- Automatically converts integer PCM to float [-1.0, 1.0]
- Handles 8-bit, 16-bit, and 24-bit WAV files
- Converts stereo to mono (averages channels)

## Audio Measurement

### rms

Calculate RMS (Root Mean Square) level.

```python
from pydigi.utils.audio import rms

rms_value = rms(audio)
```

**Parameters**:
- `audio` (numpy.ndarray): Audio samples

**Returns**:
- `float`: RMS value

**Example**:
```python
from pydigi import CW
from pydigi.utils.audio import rms

cw = CW()
audio = cw.modulate("TEST")
rms_level = rms(audio)
print(f"RMS level: {rms_level:.4f}")
```

**Details**:
- Calculates sqrt(mean(x^2))
- Useful for measuring average signal power
- Returns 0.0 for silent signals

### peak

Find peak (maximum absolute) value.

```python
from pydigi.utils.audio import peak

peak_value = peak(audio)
```

**Parameters**:
- `audio` (numpy.ndarray): Audio samples

**Returns**:
- `float`: Peak absolute value

**Example**:
```python
from pydigi.utils.audio import peak

peak_level = peak(audio)
print(f"Peak level: {peak_level:.4f}")
```

**Details**:
- Calculates max(abs(x))
- Useful for checking clipping
- Should be <= 1.0 for normalized audio

## Audio Processing

### normalize

Normalize audio to target peak level.

```python
from pydigi.utils.audio import normalize

normalized = normalize(audio, target_peak=1.0)
```

**Parameters**:
- `audio` (numpy.ndarray): Input audio samples
- `target_peak` (float): Target peak level (default: 1.0)

**Returns**:
- `numpy.ndarray`: Normalized audio

**Example**:
```python
from pydigi.utils.audio import normalize, peak

# Normalize to -3 dB (0.707)
audio_3db = normalize(audio, target_peak=0.707)
print(f"New peak: {peak(audio_3db):.4f}")  # 0.707
```

**Details**:
- Scales audio so peak = target_peak
- Preserves waveform shape (linear scaling)
- Does nothing if audio is already at target

### db_to_linear

Convert decibels to linear amplitude.

```python
from pydigi.utils.audio import db_to_linear

amplitude = db_to_linear(db)
```

**Parameters**:
- `db` (float): Level in decibels

**Returns**:
- `float`: Linear amplitude

**Example**:
```python
from pydigi.utils.audio import db_to_linear

amp_0db = db_to_linear(0.0)    # 1.0
amp_3db = db_to_linear(-3.0)   # 0.707
amp_6db = db_to_linear(-6.0)   # 0.501
amp_20db = db_to_linear(-20.0) # 0.1
```

**Formula**: `10^(db/20)`

**Common Values**:
- 0 dB → 1.0 (full scale)
- -3 dB → 0.707 (half power)
- -6 dB → 0.501 (half voltage)
- -20 dB → 0.1 (10% amplitude)

### linear_to_db

Convert linear amplitude to decibels.

```python
from pydigi.utils.audio import linear_to_db

db = linear_to_db(amplitude)
```

**Parameters**:
- `amplitude` (float): Linear amplitude (>0)

**Returns**:
- `float`: Level in decibels

**Example**:
```python
from pydigi.utils.audio import linear_to_db

db_1 = linear_to_db(1.0)    # 0.0 dB
db_half = linear_to_db(0.5) # -6.02 dB
db_tenth = linear_to_db(0.1) # -20.0 dB
```

**Formula**: `20 * log10(amplitude)`

## Complete Example

```python
from pydigi import PSK31
from pydigi.utils.audio import save_wav, load_wav, rms, peak, normalize

# Generate signal
psk = PSK31(frequency=1000)
audio = psk.modulate("CQ CQ CQ DE W1ABC")

# Measure levels
print(f"RMS: {rms(audio):.4f}")
print(f"Peak: {peak(audio):.4f}")

# Save to file
save_wav("psk31_test.wav", audio, sample_rate=psk.sample_rate)

# Load back
loaded_audio, sr = load_wav("psk31_test.wav")
print(f"Loaded {len(loaded_audio)} samples at {sr} Hz")

# Normalize to -3 dB and save
normalized = normalize(loaded_audio, target_peak=0.707)
save_wav("psk31_normalized.wav", normalized, sample_rate=sr)
```

## Using with GNU Radio

PyDigi audio works directly with GNU Radio:

```python
import numpy as np
from gnuradio import gr, blocks, audio
from pydigi import PSK31

class psk31_source(gr.sync_block):
    def __init__(self):
        gr.sync_block.__init__(
            self,
            name="PSK31 Source",
            in_sig=None,
            out_sig=[np.float32]
        )
        self.psk = PSK31()
        self.audio = self.psk.modulate("CQ CQ CQ DE W1ABC")
        self.offset = 0

    def work(self, input_items, output_items):
        out = output_items[0]
        n = min(len(out), len(self.audio) - self.offset)
        if n > 0:
            out[:n] = self.audio[self.offset:self.offset+n]
            self.offset += n
            return n
        return -1  # EOF
```

## Using with sounddevice

Direct audio playback:

```python
import sounddevice as sd
from pydigi import PSK31

psk = PSK31()
audio = psk.modulate("HELLO WORLD")

# Play audio
sd.play(audio, psk.sample_rate)
sd.wait()  # Wait until playback finishes
```

## Using with matplotlib

Visualize signals:

```python
import matplotlib.pyplot as plt
import numpy as np
from pydigi import PSK31

psk = PSK31()
audio = psk.modulate("TEST")

# Time domain plot
time = np.arange(len(audio)) / psk.sample_rate
plt.figure(figsize=(12, 4))
plt.plot(time, audio)
plt.xlabel("Time (s)")
plt.ylabel("Amplitude")
plt.title("PSK31 Signal")
plt.grid()
plt.show()

# Frequency domain plot
from scipy import signal
f, t, Sxx = signal.spectrogram(audio, psk.sample_rate)
plt.figure(figsize=(12, 4))
plt.pcolormesh(t, f, 10*np.log10(Sxx), shading='gouraud')
plt.ylabel('Frequency (Hz)')
plt.xlabel('Time (s)')
plt.title('Spectrogram')
plt.colorbar(label='Power (dB)')
plt.show()
```

## See Also

- [API Overview](overview.md) - General API patterns
- [Examples](../examples/basic.md) - Usage examples
- [DSP Core](dsp.md) - Low-level DSP functions
