# Hell (Hellschreiber) Family

Hellschreiber is a facsimile mode that "paints" text on screen.

## Quick Start

```python
from pydigi.modems import FeldHell, save_wav

# Standard Feld Hell
hell = FeldHell(frequency=1000)
audio = hell.modulate("HELL TEST")

save_wav("feldhell.wav", audio, sample_rate=8000)
```

**Available modes**: FeldHell, SlowHell, HellX5, HellX9, FSKHell245, FSKHell105, Hell80

## See Also

- [API Reference](../api/modems.md#hell-hellschreiber)
