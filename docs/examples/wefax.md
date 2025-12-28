# WEFAX User Guide

WEFAX (Weather Facsimile) is a mode used to transmit images and text, particularly weather maps, satellite imagery, and weather bulletins. WEFAX transmits grayscale images using FM (Frequency Modulation).

**New in pydigi:** WEFAX now supports **text-to-image rendering**, automatically converting text strings into formatted pages that are transmitted as images. This is perfect for weather bulletins, forecasts, and text-based reports.

## Quick Start

### Text Transmission

```python
from pydigi import WEFAX576, save_wav

# Create WEFAX modem
wefax = WEFAX576()

# Transmit weather bulletin as text
text = """MARINE WEATHER FORECAST
ISSUED: 2025-12-27 1800 UTC

SYNOPSIS:
High pressure over the region

TODAY:
Winds: NE 10-15 kt
Waves: 2-3 ft
Weather: Partly cloudy"""

audio = wefax.modulate(text)
save_wav("weather_bulletin.wav", audio, 11025)
```

### Image Transmission

```python
import numpy as np

# Transmit test pattern
audio = wefax.modulate("")
save_wav("wefax_test.wav", audio, 11025)

# Transmit image from numpy array
img = np.random.randint(0, 256, (200, 1809), dtype=np.uint8)
audio = wefax.transmit_image(img)
save_wav("wefax_image.wav", audio, 11025)
```

## How WEFAX Works

### Frequency Modulation

WEFAX uses FM where pixel values map to frequencies:

```
normalized = pixel_value / 256.0
frequency = carrier + 2.0 * (normalized - 0.5) * fm_deviation

Example (carrier=1900 Hz, deviation=400 Hz):
  Black (0)   → 1500 Hz
  Gray (128)  → 1900 Hz
  White (255) → 2300 Hz
```

### Transmission Sequence

Complete WEFAX transmission:

1. **APT START**: 5 seconds at 300 Hz (WEFAX-576) or 675 Hz (WEFAX-288)
2. **PHASING**: 20 lines of sync pattern (alternating black/white bars)
3. **IMAGE DATA**: Scanline-by-scanline transmission
4. **APT STOP**: 5 seconds at 450 Hz
5. **BLACK**: 10 seconds at lowest frequency (all black)

### Lines Per Minute (LPM)

Controls transmission speed:

```
samples_per_line = sample_rate * 60.0 / lpm

Examples at 11025 Hz:
  LPM=120 → 5512 samples/line (~0.5 seconds/line)
  LPM=60  → 11025 samples/line (~1.0 second/line)
```

## Mode Comparison

| Feature | WEFAX-576 | WEFAX-288 |
|---------|-----------|-----------|
| IOC | 576 | 288 |
| Image Width | 1809 pixels | 904 pixels |
| Default LPM | 120 | 60 |
| APT START | 300 Hz | 675 Hz |
| APT STOP | 450 Hz | 450 Hz |
| Text Font | 20pt | 18pt |
| Chars/Line | ~45 | ~42 |
| Common Use | Standard weather fax | Narrow bandwidth |

## Working with Images

### Image Dimensions

- **WEFAX-576**: 1809 pixels wide (IOC × π ≈ 576 × 3.14159)
- **WEFAX-288**: 904 pixels wide (IOC × π ≈ 288 × 3.14159)
- Height: Unlimited (depends on source image)
- Automatically resizes images to match mode width

### Numpy Array (No dependencies)

```python
import numpy as np
from pydigi import WEFAX576, save_wav

# Create gradient (200 rows × 1809 columns)
img = np.zeros((200, 1809), dtype=np.uint8)
for col in range(1809):
    img[:, col] = int(255 * col / 1809)

wefax = WEFAX576()
audio = wefax.transmit_image(img)
save_wav("gradient.wav", audio, 11025)
```

### PIL Image (Requires Pillow)

```python
from PIL import Image
from pydigi import WEFAX576, save_wav

# Load and convert to grayscale
pil_img = Image.open("weather_map.png").convert("L")

wefax = WEFAX576()
audio = wefax.transmit_image(pil_img)
save_wav("weather_map.wav", audio, 11025)
```

### File Path (Requires Pillow)

```python
from pydigi import WEFAX576, save_wav

wefax = WEFAX576()

# Automatically resizes to 1809 pixels wide
audio = wefax.transmit_image("any_size_image.png")
save_wav("wefax_output.wav", audio, 11025)
```

## Text Rendering

### Overview

WEFAX can automatically render text as images for transmission. This is perfect for weather bulletins, forecasts, and text-based reports.

**Features:**
- Automatic text-to-image rendering
- Letter-sized pages (8.5" × 11") with 1" margins
- Monospace font (DejaVu Sans Mono, bundled)
- 96 LPI vertical resolution (WEFAX standard)
- Multi-page support for long text
- Automatic pagination

### Text Rendering Specifications

**WEFAX_576:**
- Horizontal resolution: 212 DPI (~1809 pixels / 8.5")
- Vertical resolution: 96 LPI (fixed standard)
- Font size: 20pt (~26 pixels tall)
- Characters per line: ~45
- Lines per page: ~60
- Page dimensions: 1809 × 1056 pixels (W × H)
- Pixel aspect ratio: 2.21:1 (rectangular pixels)

**WEFAX_288:**
- Horizontal resolution: 106 DPI (~904 pixels / 8.5")
- Vertical resolution: 96 LPI (fixed standard)
- Font size: 18pt (~24 pixels tall)
- Characters per line: ~42
- Lines per page: ~60
- Page dimensions: 904 × 1056 pixels (W × H)
- Pixel aspect ratio: 1.10:1 (rectangular pixels)

### Weather Bulletin Example

```python
from pydigi import WEFAX576, save_wav

wefax = WEFAX576()

# Weather bulletin
text = """MARINE WEATHER FORECAST
ISSUED: 2025-12-27 1800 UTC
STATION: WXNOC NOAA

FORECAST ZONE: LAKE ERIE

TODAY:
Winds: NE 10-15 kt
Waves: 2-3 ft
Weather: Partly cloudy
Temperature: 18-22°C

TONIGHT:
Winds: E 15-20 kt increasing
Waves: 3-5 ft
Weather: Rain after midnight

HAZARDS:
- Small Craft Advisory in effect

END MARINE FORECAST"""

audio = wefax.modulate(text)
save_wav("marine_forecast.wav", audio, 11025)
```

### Multi-Page Text

Long text is automatically paginated across multiple pages. Pages are separated by a 2-second APT STOP tone (450 Hz).

```python
from pydigi import WEFAX576, save_wav

wefax = WEFAX576()

# Long bulletin automatically spans multiple pages
long_text = "WEATHER BULLETIN\n\n" + "\n".join([
    f"Hour {i:02d}: Temp {20+i%10}°C, Wind {10+i%15}kt"
    for i in range(100)
])

audio = wefax.modulate(long_text)
save_wav("multi_page_bulletin.wav", audio, 11025)
# Transmits multiple pages with APT STOP tone separators
```

### Custom Font and Margins

```python
from pydigi import WEFAX576, save_wav

# Custom font size and margins
wefax = WEFAX576(
    text_font_size=22,  # Larger font
    text_margins=(0.5, 0.5, 0.5, 0.5),  # Smaller margins (inches)
    text_font_path="/path/to/custom/font.ttf"  # Optional custom font
)

audio = wefax.modulate("Custom formatted text")
save_wav("custom_text.wav", audio, 11025)
```

### Bundled Font

PyDigi includes **DejaVu Sans Mono** font for consistent cross-platform text rendering:
- License: Bitstream Vera + Arev Fonts (permissive)
- Character coverage: Latin, Cyrillic, Greek, Arabic, and more
- Location: `pydigi/fonts/DejaVuSansMono.ttf`
- No external fonts required!

## Examples

### Basic Test Pattern

```python
from pydigi import WEFAX576, save_wav

wefax = WEFAX576()
audio = wefax.modulate("")  # Empty string generates test pattern
save_wav("wefax_test.wav", audio, 11025)
```

### Gradient Image

```python
import numpy as np
from pydigi import WEFAX576, save_wav

# Create horizontal gradient
width = 1809
height = 200
img = np.zeros((height, width), dtype=np.uint8)
for col in range(width):
    img[:, col] = int(255 * col / width)

wefax = WEFAX576()
audio = wefax.transmit_image(img, lpm=120)
save_wav("gradient.wav", audio, 11025)
```

### Checkerboard Pattern

```python
import numpy as np
from pydigi import WEFAX576, save_wav

width = 1809
height = 200
img = np.zeros((height, width), dtype=np.uint8)

# Create checkerboard (20×20 pixel squares)
square_size = 20
for y in range(height):
    for x in range(width):
        if ((x // square_size) + (y // square_size)) % 2 == 0:
            img[y, x] = 255

wefax = WEFAX576()
audio = wefax.transmit_image(img)
save_wav("checkerboard.wav", audio, 11025)
```

### Custom LPM Speed

```python
from pydigi import WEFAX576, save_wav
import numpy as np

img = np.random.randint(0, 256, (100, 1809), dtype=np.uint8)

wefax = WEFAX576()

# Fast transmission (240 LPM)
audio_fast = wefax.transmit_image(img, lpm=240)
save_wav("fast.wav", audio_fast, 11025)

# Slow transmission (60 LPM)
audio_slow = wefax.transmit_image(img, lpm=60)
save_wav("slow.wav", audio_slow, 11025)
```

### Partial Transmission

```python
from pydigi import WEFAX576, save_wav
import numpy as np

wefax = WEFAX576()
img = np.zeros((200, 1809), dtype=np.uint8)

# Transmit image only (no APT tones or phasing)
audio = wefax.transmit_image(
    img,
    include_apt_start=False,
    include_phasing=False,
    include_apt_stop=False,
    include_black=False
)
save_wav("image_only.wav", audio, 11025)
```

## Installation

### Basic Installation

```bash
pip install pydigi
```

### With Image Support

For image file support and text rendering (requires Pillow):

```bash
pip install pydigi[image]
```

Or install Pillow separately:

```bash
pip install Pillow
```

## Common Use Cases

### Weather Stations

WEFAX is commonly used by meteorological services to broadcast:
- Weather maps
- Satellite imagery
- Weather forecasts
- Marine bulletins

### Amateur Radio

Ham radio operators use WEFAX for:
- Weather information sharing
- Image transmission experiments
- Emergency communications (text bulletins)

### Marine Communications

Maritime applications include:
- Ship-to-shore weather forecasts
- Ice charts
- Storm warnings

## See Also

- [WEFAX API Reference](../api/reference/wefax.md)
- [Basic Examples](basic.md)
- [Advanced Usage](advanced.md)
