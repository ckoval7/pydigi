# Modem Classes Reference

All modem classes in PyDigi inherit from a common base class and provide a consistent API.

## Base Modem Class

All modems inherit from `pydigi.modems.base.Modem`:

```python
class Modem(ABC):
    def __init__(self, mode_name, sample_rate=8000.0, frequency=1000.0):
        """Initialize modem."""

    def modulate(self, text, frequency=None, sample_rate=None):
        """Generate audio from text."""

    @property
    def frequency(self):
        """Get/set frequency in Hz."""

    @property
    def sample_rate(self):
        """Get sample rate in Hz."""

    @property
    def bandwidth(self):
        """Get signal bandwidth in Hz."""
```

## CW (Morse Code)

**Import**: `from pydigi import CW`

```python
cw = CW(
    wpm=20,              # Words per minute (5-200)
    frequency=800,       # Tone frequency in Hz
    rise_time=4.0,       # Edge rise time in ms
    sample_rate=8000     # Sample rate in Hz
)

audio = cw.modulate("CQ CQ CQ DE W1ABC <AR>")
duration = cw.estimate_duration("TEST")  # Estimate duration in seconds
```

**Prosigns**: Enclose in angle brackets: `<AR>`, `<SK>`, `<BT>`, `<KN>`

**Methods**:
- `modulate(text)` - Generate audio
- `estimate_duration(text)` - Calculate transmission duration

## RTTY (Radioteletype)

**Import**: `from pydigi import RTTY`

```python
rtty = RTTY(
    baud=45.45,          # Baud rate (45, 45.45, 50, 75, 100)
    shift=170,           # Frequency shift in Hz (170, 200, 425, 850)
    frequency=1500,      # Center frequency in Hz
    sample_rate=8000     # Sample rate in Hz
)

audio = rtty.modulate("RYRYRY THE QUICK BROWN FOX")
```

**Character Set**: Baudot/ITA2 encoding (uppercase letters, numbers, limited punctuation)

## PSK (Phase Shift Keying)

**Import**: `from pydigi import PSK, PSK31, PSK63, PSK125, PSK250, PSK500`

### BPSK Modes

```python
# Using preset modes
psk31 = PSK31(frequency=1000)      # 31.25 baud
psk63 = PSK63(frequency=1000)      # 62.5 baud
psk125 = PSK125(frequency=1000)    # 125 baud
psk250 = PSK250(frequency=1000)    # 250 baud
psk500 = PSK500(frequency=1000)    # 500 baud

# Using base class with custom baud
psk = PSK(baud=100, frequency=1000)

audio = psk31.modulate("CQ CQ CQ DE W1ABC", preamble_symbols=32)
duration = psk31.estimate_duration("TEST")
```

**Parameters**:
- `preamble_symbols` - Number of preamble symbols (default: 32, scales with baud rate)
- Uses PSK varicode for character encoding

**Methods**:
- `modulate(text, preamble_symbols=None)` - Generate audio
- `estimate_duration(text)` - Calculate transmission duration

## QPSK (Quadrature PSK)

**Import**: `from pydigi import QPSK, QPSK31, QPSK63, QPSK125, QPSK250, QPSK500`

```python
# Using preset modes
qpsk31 = QPSK31(frequency=1000)
qpsk63 = QPSK63(frequency=1000)
qpsk125 = QPSK125(frequency=1000)
qpsk250 = QPSK250(frequency=1000)
qpsk500 = QPSK500(frequency=1000)

# Using base class with custom baud
qpsk = QPSK(baud=100, frequency=1000)

audio = qpsk31.modulate("QPSK TEST MESSAGE")
```

**Note**: QPSK transmits 2 bits per symbol (2x faster than BPSK at same baud rate)

## 8PSK (EightPSK)

**Import**: `from pydigi import EightPSK, EightPSK_125, EightPSK_250, EightPSK_500, EightPSK_1000`

```python
# 8PSK250 - 250 baud, 8-phase PSK (3 bits/symbol = 750 bits/sec)
modem_250 = EightPSK_250(frequency=1000)

audio = modem_250.modulate("8PSK TESTING")
```

**Note**: 8PSK transmits 3 bits per symbol (3x faster than BPSK at same baud rate)

## 8PSK with FEC

**Import**: `from pydigi.modems import EightPSKFEC, EightPSK_125F, EightPSK_125FL, EightPSK_250F, EightPSK_250FL, EightPSK_500F, EightPSK_1000F, EightPSK_1200F`

```python
modem_250f = EightPSK_250F(frequency=1000)   # Short interleaver
modem_250fl = EightPSK_250FL(frequency=1000) # Long interleaver

audio = modem_250f.modulate("FEC PROTECTED MESSAGE")
```

**Modes**:
- `F` suffix: Short interleaver (faster decode)
- `FL` suffix: Long interleaver (better error correction)

## MFSK

**Import**: `from pydigi import MFSK, MFSK4, MFSK8, MFSK11, MFSK16, MFSK22, MFSK31, MFSK32, MFSK64, MFSK128`

```python
mfsk16 = MFSK16(frequency=1500)
mfsk32 = MFSK32(frequency=1500)

audio = mfsk16.modulate("MFSK TEST")
```

**Variants**:
- MFSK4, MFSK8, MFSK11, MFSK16, MFSK22 - Low speed, robust
- MFSK31, MFSK32 - Medium speed
- MFSK64, MFSK128 - Higher speed

## Olivia

**Import**: `from pydigi import Olivia, Olivia4_125, Olivia8_250, Olivia8_500, Olivia16_500, Olivia16_1000, Olivia32_1000`

```python
olivia8_250 = Olivia8_250(frequency=1500)  # 8 tones, 250 Hz bandwidth

# Or custom configuration
olivia = Olivia(tones=8, bandwidth=250, frequency=1500)

audio = olivia8_250.modulate("OLIVIA TEST MESSAGE")
```

**Common Modes**:
- `Olivia4_125` - 4 tones, 125 Hz BW
- `Olivia8_250` - 8 tones, 250 Hz BW (popular)
- `Olivia16_500` - 16 tones, 500 Hz BW
- `Olivia32_1000` - 32 tones, 1000 Hz BW

## Contestia

**Import**: `from pydigi import Contestia, Contestia4_125, Contestia4_250, Contestia8_125, Contestia8_250, Contestia8_500, Contestia16_500, Contestia32_1000`

```python
contestia8_250 = Contestia8_250(frequency=1500)

audio = contestia8_250.modulate("CONTESTIA MESSAGE")
```

**Note**: Similar to Olivia but with different interleaver settings

## DominoEX

**Import**: `from pydigi import DominoEX, DominoEX_Micro, DominoEX_4, DominoEX_5, DominoEX_8, DominoEX_11, DominoEX_16, DominoEX_22, DominoEX_44, DominoEX_88`

```python
dominoex11 = DominoEX_11(frequency=1500)
dominoex16 = DominoEX_16(frequency=1500)

audio = dominoex11.modulate("DOMINOEX TEST")
```

**Speed Variants**: Micro (slowest), 4, 5, 8, 11, 16, 22, 44, 88 (fastest)

## Thor

**Import**: `from pydigi import Thor, ThorMicro, Thor4, Thor5, Thor8, Thor11, Thor16, Thor22, Thor25, Thor32, Thor44, Thor56, Thor25x4, Thor50x1, Thor50x2, Thor100`

```python
thor22 = Thor22(frequency=1500)
thor25x4 = Thor25x4(frequency=1500)  # Multi-carrier

audio = thor22.modulate("THOR TEST MESSAGE")
```

**Variants**:
- Single carrier: Micro, 4, 5, 8, 11, 16, 22, 25, 32, 44, 56
- Multi-carrier: 25x4, 50x1, 50x2, 100

## Throb

**Import**: `from pydigi import Throb, Throb1, Throb2, Throb4, ThrobX1, ThrobX2, ThrobX4`

```python
throb2 = Throb2(frequency=1500)
throbx2 = ThrobX2(frequency=1500)  # Extended character set

audio = throb2.modulate("THROB TEST")
```

**Variants**:
- `Throb1/2/4` - Normal character set
- `ThrobX1/X2/X4` - Extended character set

## Hell (Hellschreiber)

**Import**: `from pydigi.modems import Hell, FeldHell, SlowHell, HellX5, HellX9, FSKHell245, FSKHell105, Hell80`

```python
feldhell = FeldHell(frequency=1000)
slowhell = SlowHell(frequency=1000)

audio = feldhell.modulate("HELL TEST")
```

**Variants**:
- `FeldHell` - Standard Feld Hell
- `SlowHell` - Slow version for poor conditions
- `HellX5`, `HellX9` - Horizontal expansion
- `FSKHell245`, `FSKHell105` - FSK versions
- `Hell80` - 80-column mode

## FSQ

**Import**: `from pydigi import FSQ, FSQ_2, FSQ_3, FSQ_6`

```python
fsq6 = FSQ_6(frequency=1500)  # 6 baud (fastest)

audio = fsq6.modulate("FSQ TEST")
```

**Variants**: FSQ_2 (2 baud), FSQ_3 (3 baud), FSQ_6 (6 baud)

## MT63

**Import**: `from pydigi import mt63_modulate, mt63_500s_modulate, mt63_1000s_modulate, mt63_2000s_modulate, mt63_500l_modulate, mt63_1000l_modulate, mt63_2000l_modulate`

```python
# MT63 uses functional interface (not class-based)
audio = mt63_1000l_modulate(
    text="MT63 TEST MESSAGE",
    frequency=1500,
    sample_rate=8000
)
```

**Variants**:
- `mt63_500s/l` - 500 Hz bandwidth (Short/Long interleaver)
- `mt63_1000s/l` - 1000 Hz bandwidth (Short/Long interleaver)
- `mt63_2000s/l` - 2000 Hz bandwidth (Short/Long interleaver)

## IFKP

**Import**: `from pydigi.modems import IFKP, create_ifkp_modem`

```python
ifkp = create_ifkp_modem(frequency=1500)

audio = ifkp.modulate("IFKP TEST")
```

## Common Methods

All modem classes support these methods:

### `modulate(text, frequency=None, sample_rate=None)`

Generate modulated audio from text.

**Args**:
- `text` (str): Text to transmit
- `frequency` (float, optional): Override frequency
- `sample_rate` (float, optional): Override sample rate

**Returns**: `numpy.ndarray` of float samples

### `estimate_duration(text)`

Estimate transmission duration (available on most modems).

**Args**:
- `text` (str): Text to estimate

**Returns**: `float` - Duration in seconds

### Properties

- `frequency` - Get/set frequency in Hz
- `sample_rate` - Get sample rate in Hz
- `bandwidth` - Get signal bandwidth in Hz
- `mode_name` - Get mode name string

## See Also

- [Modem Families](../modems/psk.md) - Detailed mode-specific documentation
- [Examples](../examples/basic.md) - Usage examples
- [Audio Utilities](audio.md) - WAV file I/O
