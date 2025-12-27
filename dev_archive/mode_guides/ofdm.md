# OFDM Modes

Orthogonal Frequency Division Multiplexing modes use multiple carriers.

## MT63

MT63 is a robust OFDM mode with 64 carriers:

```python
from pydigi import mt63_1000l_modulate, save_wav

# MT63-1000 with long interleaver
audio = mt63_1000l_modulate(
    text="MT63 TEST MESSAGE",
    frequency=1500,
    sample_rate=8000
)

save_wav("mt63.wav", audio, sample_rate=8000)
```

**Available variants**:
- `mt63_500s_modulate` / `mt63_500l_modulate` - 500 Hz bandwidth
- `mt63_1000s_modulate` / `mt63_1000l_modulate` - 1000 Hz bandwidth
- `mt63_2000s_modulate` / `mt63_2000l_modulate` - 2000 Hz bandwidth

Suffix `s` = short interleaver (faster decode), `l` = long interleaver (better error correction)

## See Also

- [API Reference](../api/modems.md#mt63)
- [MFSK Family](mfsk.md)
