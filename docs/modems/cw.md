# CW (Morse Code)

CW (Continuous Wave) is the oldest digital mode, using on-off keying to transmit Morse code.

## Overview

PyDigi's CW implementation generates properly-shaped Morse code with configurable speed, frequency, and rise time.

## Quick Start

```python
from pydigi import CW, save_wav

# Create CW modem at 20 WPM
cw = CW(wpm=20, frequency=800)

# Generate audio
audio = cw.modulate("CQ CQ CQ DE W1ABC")

# Save to file
save_wav("cw_test.wav", audio, sample_rate=cw.sample_rate)
```

## Parameters

- `wpm` (int/float): Words per minute (5-200), default: 20
- `frequency` (float): Tone frequency in Hz, default: 800
- `rise_time` (float): Edge rise/fall time in ms, default: 4.0
- `sample_rate` (float): Sample rate in Hz, default: 8000

## Prosigns

Prosigns are special character combinations sent as a single character:

```python
cw = CW(wpm=20)

# Use prosigns in angle brackets
text = "CQ CQ CQ DE W1ABC <AR> <SK>"
audio = cw.modulate(text)
```

**Common Prosigns**:
- `<AR>` - End of message (. -. -.)
- `<SK>` - End of contact (. . . -. -)
- `<BT>` - Break, pause (- . . . -)
- `<KN>` - Invitation to specific station (- . - -.)
- `<AS>` - Wait (. - . . .)
- `<HH>` - Error (. . . . . . . .)

## Speed Control

```python
# Slow code for learning
cw_slow = CW(wpm=5)

# Standard conversational speed
cw_medium = CW(wpm=20)

# High speed
cw_fast = CW(wpm=40)
```

## Estimating Duration

```python
cw = CW(wpm=20)

text = "PARIS"  # Standard test word
duration = cw.estimate_duration(text)

print(f"Duration: {duration:.2f} seconds")
```

## See Also

- [API Reference](../api/modems.md#cw-morse-code)
- [Basic Examples](../examples/basic.md)
