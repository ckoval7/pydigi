# RTTY (Radioteletype)

RTTY uses FSK (Frequency Shift Keying) modulation with Baudot character encoding. It's one of the oldest digital modes, dating back to the 1930s.

## Quick Example

```python
from pydigi.modems import RTTY, RTTYDecoder

# Transmit
tx = RTTY(baud=45.45, shift=170)
audio = tx.modulate("CQ CQ DE W1AW K", frequency=1000, sample_rate=8000)

# Receive
rx = RTTYDecoder(baud=45.45, shift=170, sample_rate=8000, frequency=1000)
text = rx.demodulate(audio)
print(f"Received: {text}")
```

## Common Configurations

| Mode | Baud | Shift | Stop Bits | Use Case |
|------|------|-------|-----------|----------|
| Standard RTTY | 45.45 | 170 | 1.5 | Amateur radio |
| RTTY-45 | 45 | 170 | 1.5 | Commercial |
| RTTY-50 | 50 | 170 | 1.5 | Commercial |
| RTTY-75 | 75 | 850 | 1.0 | Weather fax |

## Documentation

- **[RTTY Decoder Guide](../../guides/rtty-decoder.md)** - Complete guide with examples
- **[RTTY Decoder Example](../../../examples/rtty_decoder_example.py)** - Working code example

## Module Reference

### Transmitter

::: pydigi.modems.rtty
    options:
      show_root_heading: true
      show_source: true

### Decoder

::: pydigi.modems.rtty_decoder
    options:
      show_root_heading: true
      show_source: true
