# MFSK Family

Multi-Frequency Shift Keying (MFSK) modes transmit data by switching between multiple tones.

## Overview

The MFSK family includes:
- **MFSK**: Basic multi-tone FSK
- **Olivia**: MFSK with FEC and interleaving (very robust)
- **Contestia**: Similar to Olivia with different settings
- **DominoEX**: MFSK with incremental frequency keying
- **Thor**: MFSK with soft-symbol FEC

## Basic MFSK

```python
from pydigi import MFSK16, MFSK32, save_wav

# 16-tone MFSK
mfsk16 = MFSK16(frequency=1500)
audio = mfsk16.modulate("MFSK16 TEST")

save_wav("mfsk16.wav", audio, sample_rate=8000)
```

**Available modes**: MFSK4, MFSK8, MFSK11, MFSK16, MFSK22, MFSK31, MFSK32, MFSK64, MFSK128

## Olivia

Very robust mode for poor conditions:

```python
from pydigi import Olivia8_250, Olivia16_500, save_wav

# 8 tones, 250 Hz bandwidth (popular)
olivia = Olivia8_250(frequency=1500)
audio = olivia.modulate("OLIVIA TEST - ROBUST MODE")

save_wav("olivia.wav", audio, sample_rate=8000)
```

**Available modes**: Olivia4_125, Olivia8_250, Olivia8_500, Olivia16_500, Olivia16_1000, Olivia32_1000

## Contestia

Similar to Olivia with different interleaver:

```python
from pydigi import Contestia8_250, save_wav

contestia = Contestia8_250(frequency=1500)
audio = contestia.modulate("CONTESTIA TEST")

save_wav("contestia.wav", audio, sample_rate=8000)
```

## See Also

- [API Reference](../api/modems.md#mfsk)
- [PSK Family](psk.md)
