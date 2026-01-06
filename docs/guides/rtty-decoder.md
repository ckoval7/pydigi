# RTTY Decoder Guide

The RTTY (Radioteletype) decoder implements FSK demodulation and Baudot character decoding for receiving RTTY signals.

## Features

- **FSK Demodulation**: Dual Goertzel filters for mark/space tone detection
- **Baudot Decoding**: Full support for ITA-2 and US-TTY character sets
- **Frame Synchronization**: Start/stop bit detection with configurable stop bits (1.0, 1.5, 2.0)
- **Multiple Baud Rates**: Supports 45, 45.45, 50, 56, 75, 100, 110, 150, 200, 300 baud
- **Flexible Shifts**: Configurable frequency shift (23-850 Hz)
- **Data Carrier Detect (DCD)**: Energy-based signal detection with SNR estimation
- **Error Tracking**: Frame error detection and statistics

## Basic Usage

### Simple Decode Example

```python
from pydigi.modems import RTTY, RTTYDecoder

# Create transmitter and encode a message
tx = RTTY(baud=45.45, shift=170)
audio = tx.modulate("CQ CQ DE W1AW", frequency=1000, sample_rate=8000)

# Create decoder and decode
rx = RTTYDecoder(baud=45.45, shift=170, sample_rate=8000, frequency=1000)
decoded = rx.demodulate(audio)
print(f"Received: {decoded}")
```

### Streaming API with Callback

```python
def handle_char(char):
    print(char, end="", flush=True)

decoder = RTTYDecoder(
    baud=45.45,
    shift=170,
    sample_rate=8000,
    frequency=1000,
    text_callback=handle_char
)

# Process audio samples as they arrive
decoder.process(audio_samples)
```

## Parameters

### RTTYDecoder Constructor

```python
RTTYDecoder(
    baud=45.45,          # Symbol rate in baud
    shift=170.0,         # Frequency shift in Hz
    bits=5,              # Data bits (5 for Baudot)
    stop_bits=1.5,       # Stop bits (1.0, 1.5, 2.0)
    sample_rate=8000.0,  # Audio sample rate
    frequency=1000.0,    # Center frequency
    use_ita2=True,       # Use ITA-2 (True) or US-TTY (False)
    use_afc=True,        # Enable AFC (future)
    use_dcd=True,        # Enable DCD (future)
    text_callback=None   # Character callback function
)
```

### Common RTTY Configurations

| Mode | Baud | Shift | Stop Bits | Use Case |
|------|------|-------|-----------|----------|
| Standard RTTY | 45.45 | 170 | 1.5 | Amateur radio |
| RTTY-45 | 45 | 170 | 1.5 | Commercial |
| RTTY-50 | 50 | 170 | 1.5 | Commercial |
| RTTY-75 | 75 | 850 | 1.0 | Weather fax |

## How It Works

### 1. FSK Demodulation

The decoder uses dual **Goertzel filters** to detect mark and space tones:

```
Mark frequency = center + shift/2  (logic 1)
Space frequency = center - shift/2 (logic 0)
```

Each Goertzel filter efficiently detects a single frequency by computing:
- Magnitude squared at the target frequency
- Updated every symbol period (samples_per_bit)

**Bit decision**: Compare mark energy vs space energy
- If mark > space: bit = 1
- If space > mark: bit = 0

### 2. Frame Synchronization

RTTY uses asynchronous serial framing:

```
[START] [D0] [D1] [D2] [D3] [D4] [STOP...]
   0     LSB                 MSB      1
```

- **Start bit**: Always 0 (space)
- **Data bits**: 5 bits transmitted LSB-first
- **Stop bit(s)**: Always 1 (mark), duration = 1.0-2.0 bit periods

The decoder implements a state machine:
1. **IDLE**: Wait for start bit (0)
2. **START**: Start bit detected, prepare for data
3. **DATA**: Collect 5 data bits
4. **STOP**: Verify stop bit(s) are mark (1)

### 3. Baudot Character Decoding

Baudot is a 5-bit character encoding with two shift states:

- **LETTERS mode**: Standard alphabet (A-Z, space, CR, LF)
- **FIGURES mode**: Numbers and punctuation (0-9, +, -, /, etc.)

Special shift codes:
- **LTRS** (0x1F): Switch to LETTERS mode
- **FIGS** (0x1B): Switch to FIGURES mode

Example:
```
Codes:  [14] [23]     → "CQ"  (letters)
Codes:  [27] [1]      → "3"   (shift to figures, then digit 3)
Codes:  [31] [14]     → "C"   (shift to letters, then C)
```

## Performance

### Test Results

| Test | SNR | Status | Notes |
|------|-----|--------|-------|
| Clean loopback | ∞ dB | ✅ Pass | Perfect decode |
| AWGN @ 20 dB | 20 dB | ✅ Pass | No errors |
| AWGN @ 10 dB | 10 dB | ✅ Pass | No errors |
| AWGN @ 5 dB | 5 dB | ✅ Pass | No errors |
| AWGN @ 0 dB | 0 dB | ✅ Pass | Works even at 0 dB! |
| DCD | - | ✅ Pass | Detects signal vs silence |
| Multiple modes | - | ✅ Pass | All baud rates work |

### Limitations

1. **No AFC**: Frequency offset causes decoding failures
   - Works perfectly at 0 Hz offset
   - Fails at ±10 Hz offset or more
   - Future: Implement AFC for frequency tracking

2. **Fixed timing**: Uses simple symbol slicer
   - Works well for clean signals
   - Future: Add Early-Late Gate timing recovery for better performance

## Architecture

### Core Components Used

- **GoertzelFilter** (`pydigi.core.filters`): Efficient single-tone detection
- **SymbolSlicer** (`pydigi.core.timing_recovery`): Basic timing recovery
- **EnergyDCD** (`pydigi.core.dcd`): Energy-based data carrier detect with SNR estimation
- **BaudotDecoder** (`pydigi.varicode.baudot`): Character decoding with shift handling

### Signal Flow

```
Audio samples
    ↓
[Energy DCD] → SNR estimation, carrier detect
    ↓
[Goertzel Filter (Mark)] → Mark energy
[Goertzel Filter (Space)] → Space energy
    ↓
[Bit Decision: mark > space?]
    ↓
[Frame Sync State Machine]
    ↓
[Baudot Character Decoder]
    ↓
Text output
```

## Examples

### Decode from WAV file

```python
import wave
import numpy as np
from pydigi.modems import RTTYDecoder

# Read WAV file
with wave.open('rtty_signal.wav', 'rb') as wf:
    sample_rate = wf.getframerate()
    audio_bytes = wf.readframes(wf.getnframes())
    audio = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32)
    audio = audio / 32768.0  # Normalize to [-1, 1]

# Decode RTTY
decoder = RTTYDecoder(
    baud=45.45,
    shift=170,
    sample_rate=sample_rate,
    frequency=1000
)

text = decoder.demodulate(audio)
print(f"Decoded: {text}")

# Get statistics
stats = decoder.get_statistics()
print(f"Characters: {stats['total_chars']}")
print(f"Errors: {stats['errors']}")
print(f"Error rate: {stats['error_rate']:.2%}")
```

### Real-time streaming

```python
import sounddevice as sd
from pydigi.modems import RTTYDecoder

def audio_callback(indata, frames, time, status):
    """Process audio from microphone."""
    audio = indata[:, 0]  # Mono
    decoder.process(audio)

def char_callback(char):
    """Handle decoded characters."""
    print(char, end="", flush=True)

# Create decoder
decoder = RTTYDecoder(
    baud=45.45,
    shift=170,
    sample_rate=8000,
    frequency=1000,
    text_callback=char_callback
)

# Start audio stream
with sd.InputStream(
    samplerate=8000,
    channels=1,
    callback=audio_callback
):
    print("Listening for RTTY... Press Ctrl+C to stop")
    sd.sleep(100000)
```

## Comparison with fldigi

The PyDigi RTTY decoder is based on the fldigi RTTY implementation (`fldigi/src/rtty/rtty.cxx`) and provides equivalent functionality:

| Feature | fldigi | PyDigi RTTY Decoder |
|---------|--------|---------------------|
| Goertzel filters | ✅ | ✅ |
| ITA-2 / US-TTY | ✅ | ✅ |
| Configurable baud | ✅ | ✅ (45-300) |
| Configurable shift | ✅ | ✅ (23-850 Hz) |
| AFC | ✅ | 🔧 Future |
| DCD/Squelch | ✅ | ✅ Energy-based |
| SNR estimation | ✅ | ✅ |
| Frame error detect | ✅ | ✅ |

## Future Enhancements

1. **AFC (Automatic Frequency Control)**
   - Track frequency offset automatically
   - Adapt Goertzel filter frequencies
   - Handle ±50 Hz offset or more

2. **Advanced Timing Recovery**
   - Early-Late Gate algorithm
   - Better handling of timing errors
   - Clock drift correction

4. **Additional Features**
   - Reverse mode (mark/space swapped)
   - Usos mode (unshifted on space)
   - Diddles (idle patterns)

## References

- fldigi source: `fldigi/src/rtty/rtty.cxx`
- PyDigi transmitter: `pydigi/modems/rtty.py`
- ITU-R M.476: RTTY standard
- Baudot code: `pydigi/varicode/baudot.py`
