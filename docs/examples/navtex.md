# NAVTEX User Guide

NAVTEX (Navigational Telex) is a maritime safety broadcast system using SITOR-B (AMTOR-B) modulation with Forward Error Correction. It transmits weather warnings, navigational warnings, and safety information to ships at sea.

## Overview

NAVTEX uses FSK (Frequency Shift Keying) with CCIR-476 encoding for robust error detection and correction. The system employs character-level forward error correction by transmitting each character twice with interleaving.

**Technical Specifications:**
- **Modulation:** FSK (Frequency Shift Keying)
- **Baud Rate:** 100 baud (fixed)
- **Shift:** 170 Hz (±85 Hz deviation)
- **Encoding:** CCIR-476 (7-bit with 4 marks for error detection)
- **FEC:** Each character transmitted twice with interleaving
- **Standard Frequencies:** 490 kHz, 518 kHz, 4209.5 kHz

## Quick Start

### NAVTEX with Full Protocol

```python
from pydigi import NAVTEX, save_wav

# Create NAVTEX modem
navtex = NAVTEX()

# Transmit safety message
text = "GALE WARNING NORTH SEA"
audio = navtex.modulate(text, frequency=1000, sample_rate=11025)
save_wav("navtex_message.wav", audio, 11025)
```

### SITOR-B (Raw Mode)

```python
from pydigi import SITORB, save_wav

# Create SITOR-B modem (no NAVTEX headers)
sitor = SITORB()

# Transmit text message
audio = sitor.modulate("TEST MESSAGE", frequency=1000, sample_rate=11025)
save_wav("sitor_message.wav", audio, 11025)
```

## How NAVTEX Works

### NAVTEX Message Format

NAVTEX transmissions follow a strict format for maritime safety:

#### Full NAVTEX Transmission

1. **Phasing Signal** (carrier at center frequency)
   - First message: 10 seconds
   - Subsequent messages: 5 seconds
   - Allows receivers to lock onto the signal

2. **Header**
   - Format: `ZCZC <origin><subject><number>CR LF`
   - Origin: Single letter (station identifier)
   - Subject: Single letter (message type)
   - Number: Two digits (00-99, auto-increments)
   - Example: `ZCZC ZI01` (Z=test/unknown, I=not used, 01=message #1)

3. **Message Text**
   - Plain text content
   - CCIR-476 encoded

4. **Trailer**
   - Format: `CR LF NNNN CR LF LF`
   - Marks end of message

5. **End Phasing** (alpha signal)
   - 2 seconds at center frequency

#### SITOR-B Transmission

SITOR-B mode omits NAVTEX headers and uses simplified format:

1. **Leading Silence**: 1 second
2. **Message Text**: CCIR-476 encoded with FEC
3. **Trailing Silence**: 1 second

### CCIR-476 Encoding

NAVTEX uses CCIR-476 encoding for robust error detection:

- **7-bit codes** with exactly **4 marks (1s)** and **3 spaces (0s)**
- Invalid codes (wrong number of marks) are detected and rejected
- **Error detection** without requiring acknowledgment

### Forward Error Correction (FEC)

Each character is transmitted twice with interleaving:

```
Original: A B C D
Transmitted: A A B B C C D D (sequential)
With FEC: A B C D A B C D (interleaved)
```

This allows receivers to correct errors by comparing the two copies.

### FSK Modulation

NAVTEX uses FSK to encode binary data as audio frequencies:

```
Center Frequency: fc
Mark (binary 1):  fc + 85 Hz
Space (binary 0): fc - 85 Hz

Example (fc = 1000 Hz):
  Mark:  1085 Hz
  Space: 915 Hz
  Shift: 170 Hz
```

#### Baseband Filtering

NAVTEX uses baseband filtering for clean spectral characteristics:

1. **Generate baseband**: ±1.0 for mark/space bits
2. **Apply lowpass filter**: Butterworth filter at ~1.2× baud rate (120 Hz)
3. **Modulate to FSK**: Frequency varies based on filtered baseband

This approach:
- Reduces spectral splatter
- Smooths mark/space transitions
- Maintains signal integrity
- Follows fldigi implementation

### Timing

At 100 baud with 11025 Hz sample rate:

```
Samples per bit = 11025 / 100 = 110.25 samples
Bit duration = 10 ms
Character duration (7 bits) = 70 ms
```

## Mode Comparison

| Feature | NAVTEX | SITOR-B |
|---------|--------|---------|
| Protocol Headers | Yes (ZCZC/NNNN) | No |
| Phasing Signal | 5-10 seconds | 1 second silence |
| Message Counter | Auto-increment | N/A |
| End Signal | 2 second phasing | 1 second silence |
| Use Case | Maritime safety | General teletype |

## Examples

### Basic NAVTEX Message

```python
from pydigi import NAVTEX, save_wav

navtex = NAVTEX()
text = "GALE WARNING NORTH SEA. WINDS NE 40-50 KT."
audio = navtex.modulate(text, frequency=1000, sample_rate=11025)
save_wav("navtex_warning.wav", audio, 11025)
```

### SITOR-B Test Message

```python
from pydigi import SITORB, save_wav

sitor = SITORB()
audio = sitor.modulate("THE QUICK BROWN FOX", frequency=1500, sample_rate=11025)
save_wav("sitor_test.wav", audio, 11025)
```

### Low-Level Transmission

```python
from pydigi import NAVTEX

navtex = NAVTEX()
navtex.frequency = 1000
navtex.sample_rate = 11025
navtex.tx_init()

# Process message
audio = navtex.tx_process("WEATHER BULLETIN")

# Audio is ready for output
print(f"Generated {len(audio)} samples")
```

### US-TTY Encoding

```python
# Use US-TTY encoding instead of ITA-2
from pydigi import NAVTEX, save_wav

navtex = NAVTEX(use_ita2=False)
audio = navtex.modulate("MESSAGE", frequency=1000, sample_rate=11025)
save_wav("ustty_message.wav", audio, 11025)
```

### Custom Amplitude

```python
from pydigi import NAVTEX, save_wav

# Lower transmission amplitude
navtex = NAVTEX(tx_amplitude=0.5)
audio = navtex.modulate("TEST", frequency=1000, sample_rate=11025)
save_wav("low_amplitude.wav", audio, 11025)
```

### Disable Filtering

```python
from pydigi import NAVTEX, save_wav

# Use unfiltered baseband (sharper transitions, more bandwidth)
navtex = NAVTEX(use_filtering=False)
audio = navtex.modulate("TEST", frequency=1000, sample_rate=11025)
save_wav("unfiltered.wav", audio, 11025)
```

### Maritime Weather Warning

```python
from pydigi import NAVTEX, save_wav

navtex = NAVTEX()

# Format a proper maritime warning
warning = """GALE WARNING ISSUED 1200 UTC.
AREA NORTH SEA.
WINDS NE 40-50 KT INCREASING.
ROUGH TO VERY ROUGH SEAS.
VALID UNTIL 0000 UTC TOMORROW."""

audio = navtex.modulate(warning, frequency=1000, sample_rate=11025)
save_wav("gale_warning.wav", audio, 11025)
```

## Character Set

NAVTEX supports:
- **Letters**: A-Z
- **Numbers**: 0-9
- **Punctuation**: Space, period, comma, etc.
- **Control**: CR (carriage return), LF (line feed)
- **Shifts**: LTRS (letters), FIGS (figures)

## Standard Frequencies

NAVTEX operates on specific frequencies worldwide:

- **518 kHz**: International NAVTEX frequency (SOLAS requirement)
- **490 kHz**: Regional frequency (some countries)
- **4209.5 kHz**: HF NAVTEX (NAVAREA XVI)

**Note:** PyDigi generates audio at baseband frequencies (e.g., 1000 Hz). For actual NAVTEX transmission on maritime frequencies, you would need to:
1. Generate audio with PyDigi
2. Use SSB modulation to shift to HF/MF frequencies
3. Transmit with appropriate marine radio equipment

## Common Use Cases

### Maritime Safety

NAVTEX is primarily used for:
- Navigational warnings
- Weather warnings and forecasts
- Search and rescue information
- Distress alerts
- Ice reports
- Piracy warnings

### Amateur Radio

Ham radio operators use NAVTEX/SITOR-B for:
- Robust data communication experiments
- Emergency communication practice
- HF digital mode testing

### Technical Education

NAVTEX is useful for learning about:
- Forward error correction
- FSK modulation
- Maritime communication protocols
- Reliable data transmission

## Configuration Options

### Encoding Selection

NAVTEX supports two character encoding standards:

- **ITA-2** (default): International Telecommunication Alphabet No. 2 (European standard)
- **US-TTY**: US Teletype encoding

```python
# ITA-2 (default)
navtex_ita2 = NAVTEX(use_ita2=True)

# US-TTY
navtex_us = NAVTEX(use_ita2=False)
```

### Amplitude Control

Adjust transmission amplitude for different applications:

```python
# Full amplitude (default: 0.9 to prevent clipping)
navtex_full = NAVTEX(tx_amplitude=0.9)

# Reduced amplitude for testing
navtex_low = NAVTEX(tx_amplitude=0.5)

# Very quiet for background
navtex_quiet = NAVTEX(tx_amplitude=0.1)
```

### Filtering

Control baseband filtering to trade off spectral efficiency vs. transition sharpness:

```python
# Filtered (default - cleaner spectrum)
navtex_filtered = NAVTEX(use_filtering=True)

# Unfiltered (sharper transitions, more bandwidth)
navtex_unfiltered = NAVTEX(use_filtering=False)
```

## Installation

NAVTEX is included in the base PyDigi installation:

```bash
pip install pydigi
```

No additional dependencies required for NAVTEX/SITOR-B transmission.

## Reference Standards

- **ITU-R M.540-2**: NAVTEX technical characteristics
- **CCIR Recommendation 476-4**: CCIR-476 encoding

Based on fldigi implementation: `fldigi/src/navtex/navtex.cxx`

## See Also

- [NAVTEX API Reference](../api/reference/navtex.md)
- [RTTY (similar FSK mode)](../api/reference/rtty.md)
- [Basic Examples](basic.md)
- [Advanced Usage](advanced.md)
