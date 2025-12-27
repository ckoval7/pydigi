# Other Modes

## DominoEX

Incremental frequency shift keying with error detection:

```python
from pydigi import DominoEX_11, DominoEX_16, save_wav

dominoex = DominoEX_11(frequency=1500)
audio = dominoex.modulate("DOMINOEX TEST")

save_wav("dominoex.wav", audio, sample_rate=8000)
```

## Thor

MFSK with soft-symbol FEC:

```python
from pydigi import Thor22, save_wav

thor = Thor22(frequency=1500)
audio = thor.modulate("THOR TEST MESSAGE")

save_wav("thor.wav", audio, sample_rate=8000)
```

## Throb

Binary FSK with dual-tone modulation:

```python
from pydigi import Throb2, save_wav

throb = Throb2(frequency=1500)
audio = throb.modulate("THROB TEST")

save_wav("throb.wav", audio, sample_rate=8000)
```

## FSQ

Fast Simple QSO mode for keyboard-to-keyboard:

```python
from pydigi import FSQ_6, save_wav

fsq = FSQ_6(frequency=1500)
audio = fsq.modulate("FSQ TEST")

save_wav("fsq.wav", audio, sample_rate=8000)
```

## IFKP

Incremental Frequency Keying with FEC:

```python
from pydigi.modems import create_ifkp_modem, save_wav

ifkp = create_ifkp_modem(frequency=1500)
audio = ifkp.modulate("IFKP TEST")

save_wav("ifkp.wav", audio, sample_rate=8000)
```

## SCAMP

Spread spectrum mode with Golay(24,12) FEC:

```python
from pydigi import SCAMPFSK, SCAMPOOK, SCFSKFST, save_wav

# Standard FSK mode (33.33 baud, 133 Hz bandwidth)
scamp_fsk = SCAMPFSK(frequency=1500)
audio = scamp_fsk.modulate("SCAMP FSK TEST")
save_wav("scamp_fsk.wav", audio, sample_rate=8000)

# OOK mode (31.25 baud, 62.5 Hz bandwidth)
scamp_ook = SCAMPOOK(frequency=1500)
audio = scamp_ook.modulate("SCAMP OOK TEST")
save_wav("scamp_ook.wav", audio, sample_rate=8000)

# Fast FSK mode (83.33 baud, 333 Hz bandwidth)
scamp_fast = SCFSKFST(frequency=1500)
audio = scamp_fast.modulate("FAST SCAMP")
save_wav("scamp_fast.wav", audio, sample_rate=8000)
```

### SCAMP Mode Variants

SCAMP offers 6 variants with different speeds and modulation types:

| Mode | Type | Baud | Bandwidth | Description |
|------|------|------|-----------|-------------|
| **SCAMPFSK** | FSK | 33.33 | 133 Hz | Standard FSK |
| **SCAMPOOK** | OOK | 31.25 | 62.5 Hz | Standard OOK |
| **SCFSKFST** | FSK | 83.33 | 333 Hz | Fast FSK |
| **SCFSKSLW** | FSK | 13.89 | 69.44 Hz | Slow FSK |
| **SCOOKSLW** | OOK | 13.89 | 27.78 Hz | Slow OOK |
| **SCFSKVSL** | FSK | 6.94 | 34.72 Hz | Very Slow FSK |

**Features:**
- Golay(24,12) FEC - corrects up to 3 bit errors per frame
- 6-bit character encoding for efficiency
- Reversal bits for frame synchronization
- FSK (Frequency Shift Keying) or OOK (On-Off Keying) modulation
- Extremely narrow bandwidth modes available

## See Also

- [API Reference](../api/modems.md)
- [All Modem Families](../index.md#supported-modes)
