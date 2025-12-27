# PSK Family

The PSK (Phase Shift Keying) family includes BPSK, QPSK, and 8PSK modes commonly used in amateur radio.

## Overview

PSK modes encode data by shifting the phase of a carrier signal. They're popular for keyboard-to-keyboard communication due to narrow bandwidth and good performance in poor conditions.

### Available Modes

| Mode | Class | Baud Rate | Bits/Symbol | Effective Speed |
|------|-------|-----------|-------------|-----------------|
| PSK31 | `PSK31` | 31.25 | 1 (BPSK) | 31 baud |
| PSK63 | `PSK63` | 62.5 | 1 (BPSK) | 63 baud |
| PSK125 | `PSK125` | 125 | 1 (BPSK) | 125 baud |
| PSK250 | `PSK250` | 250 | 1 (BPSK) | 250 baud |
| PSK500 | `PSK500` | 500 | 1 (BPSK) | 500 baud |
| QPSK31 | `QPSK31` | 31.25 | 2 (QPSK) | 63 baud |
| QPSK63 | `QPSK63` | 62.5 | 2 (QPSK) | 125 baud |
| QPSK125 | `QPSK125` | 125 | 2 (QPSK) | 250 baud |
| QPSK250 | `QPSK250` | 250 | 2 (QPSK) | 500 baud |
| QPSK500 | `QPSK500` | 500 | 2 (QPSK) | 1000 baud |
| 8PSK125 | `EightPSK_125` | 125 | 3 (8PSK) | 375 baud |
| 8PSK250 | `EightPSK_250` | 250 | 3 (8PSK) | 750 baud |
| 8PSK500 | `EightPSK_500` | 500 | 3 (8PSK) | 1500 baud |
| 8PSK1000 | `EightPSK_1000` | 1000 | 3 (8PSK) | 3000 baud |

## Basic Usage

### BPSK (PSK31, PSK63, etc.)

```python
from pydigi import PSK31, PSK63, PSK125, save_wav

# Create a PSK31 modem
psk31 = PSK31(frequency=1000)

# Generate audio
audio = psk31.modulate("CQ CQ CQ DE W1ABC W1ABC PSK31")

# Save to WAV
save_wav("psk31.wav", audio, sample_rate=psk31.sample_rate)
```

### QPSK

```python
from pydigi import QPSK31, QPSK63, save_wav

# QPSK is 2x faster than BPSK at same baud rate
qpsk31 = QPSK31(frequency=1000)

audio = qpsk31.modulate("QPSK TEST MESSAGE")
save_wav("qpsk31.wav", audio, sample_rate=qpsk31.sample_rate)
```

### 8PSK

```python
from pydigi import EightPSK_250, save_wav

# 8PSK is 3x faster than BPSK at same baud rate (matches fldigi's 8PSK250)
modem = EightPSK_250(frequency=1000)

audio = modem.modulate("8PSK HIGH SPEED MESSAGE")
save_wav("8psk250.wav", audio, sample_rate=modem.sample_rate)
```

## Custom Baud Rates

You can create PSK modems with custom baud rates:

```python
from pydigi.modems.psk import PSK
from pydigi.modems.qpsk import QPSK
from pydigi.modems.psk8 import EightPSK

# Custom BPSK at 100 baud
psk100 = PSK(baud=100, frequency=1000)

# Custom QPSK at 80 baud
qpsk80 = QPSK(baud=80, frequency=1000)

# Custom 8PSK at 150 baud (matches fldigi's 8PSK150)
modem_150 = EightPSK(baud=150, frequency=1000)
```

## Preamble Control

PSK modes send a preamble (phase reversals) before data to help receivers synchronize:

```python
from pydigi import PSK31

psk = PSK31()

# Default preamble (32 symbols for PSK31, scales with baud rate)
audio = psk.modulate("TEST")

# Custom preamble length
audio = psk.modulate("TEST", preamble_symbols=64)  # Longer preamble

# Minimal preamble
audio = psk.modulate("TEST", preamble_symbols=16)  # Shorter preamble
```

**Preamble Guidelines**:
- **Short messages**: Use longer preamble (64+ symbols) for better sync
- **Continuous transmission**: Can use shorter preamble (16-32 symbols)
- **Poor conditions**: Increase preamble length

## Character Encoding

PSK modes use **varicode** encoding:

- Variable-length encoding (like Morse code)
- Common characters (E, T, A, etc.) = shorter codes
- Efficient for normal text
- Supports uppercase, lowercase, numbers, and punctuation
- Zero-length gaps between characters for synchronization

**Supported Characters**:
- A-Z, a-z (full alphabet)
- 0-9 (numbers)
- Punctuation: `.,?!@#$%&*()[]{}:;'"-_/\`
- Control: Space, newline, carriage return

**Not Supported**: Extended Unicode, emojis

## Signal Characteristics

### BPSK (PSK31, PSK63, etc.)

- **Modulation**: Binary Phase Shift Keying (0° and 180°)
- **Bandwidth**: Approximately equal to baud rate
- **Constellation**: 2 points (0° and 180°)
- **Error rate**: Best performance of PSK family
- **SNR requirement**: Works in very poor conditions

### QPSK

- **Modulation**: Quadrature PSK (0°, 90°, 180°, 270°)
- **Bandwidth**: Same as BPSK at same baud rate
- **Constellation**: 4 points
- **Speed**: 2x faster than BPSK
- **SNR requirement**: Requires ~3 dB more SNR than BPSK

### 8PSK

- **Modulation**: 8-ary PSK (0°, 45°, 90°, 135°, 180°, 225°, 270°, 315°)
- **Bandwidth**: Same as BPSK at same baud rate
- **Constellation**: 8 points
- **Speed**: 3x faster than BPSK
- **SNR requirement**: Requires ~6 dB more SNR than BPSK

## Estimating Transmission Time

```python
from pydigi import PSK31, PSK63, QPSK31

psk31 = PSK31()
psk63 = PSK63()
qpsk31 = QPSK31()

text = "CQ CQ CQ DE W1ABC W1ABC PSK K"

# Compare transmission times
time_psk31 = psk31.estimate_duration(text)
time_psk63 = psk63.estimate_duration(text)
time_qpsk31 = qpsk31.estimate_duration(text)

print(f"PSK31:  {time_psk31:.2f}s")
print(f"PSK63:  {time_psk63:.2f}s")
print(f"QPSK31: {time_qpsk31:.2f}s")
```

## When to Use Each Mode

### PSK31
- **Best for**: Weak signal DX, crowded bands
- **Pros**: Narrow bandwidth, works in very poor conditions
- **Cons**: Slow (50-60 WPM effective)
- **Typical use**: Keyboard QSOs, contesting

### PSK63
- **Best for**: Faster QSOs with good signals
- **Pros**: 2x faster than PSK31, still narrow
- **Cons**: Requires better SNR than PSK31
- **Typical use**: Ragchewing, local contacts

### PSK125/250/500
- **Best for**: High-speed digital modes, good conditions
- **Pros**: Much faster than PSK31/63
- **Cons**: Wider bandwidth, requires stronger signals
- **Typical use**: High-speed data, file transfers

### QPSK Variants
- **Best for**: 2x speed improvement over BPSK
- **Pros**: Same bandwidth as BPSK, double speed
- **Cons**: Requires ~3 dB more SNR, not as common
- **Typical use**: When you need speed but have limited bandwidth

### 8PSK Variants
- **Best for**: Maximum speed in narrow bandwidth
- **Pros**: 3x faster than BPSK
- **Cons**: Requires good SNR, phase noise sensitive
- **Typical use**: Experimental high-speed modes

## PSK with FEC

For error correction, see the [EightPSK with FEC modes](../api/modems.md#eightpsk-with-fec):

```python
from pydigi.modems import EightPSK_250F, EightPSK_250FL

# 8PSK250F - Short interleaver (faster)
modem_f = EightPSK_250F()

# 8PSK250FL - Long interleaver (better error correction)
modem_fl = EightPSK_250FL()
```

FEC modes add forward error correction for better performance in noisy conditions.

## Complete Example

```python
from pydigi import PSK31, PSK63, QPSK31, EightPSK_250, save_wav

# Generate the same message in different modes
text = "CQ CQ CQ DE W1ABC W1ABC PSK K"

modes = [
    ("PSK31", PSK31()),
    ("PSK63", PSK63()),
    ("QPSK31", QPSK31()),
    ("8PSK250", EightPSK_250()),
]

for mode_name, modem in modes:
    # Generate audio
    audio = modem.modulate(text, frequency=1000)

    # Get info
    duration = modem.estimate_duration(text)

    # Save to file
    filename = f"psk_{mode_name.lower()}.wav"
    save_wav(filename, audio, sample_rate=modem.sample_rate)

    print(f"{mode_name:10} {duration:6.2f}s  {filename}")
```

## See Also

- [API Reference - Modem Classes](../api/modems.md#psk-phase-shift-keying)
- [Examples - Basic Usage](../examples/basic.md)
- [MFSK Family](mfsk.md) - For frequency-based modes
