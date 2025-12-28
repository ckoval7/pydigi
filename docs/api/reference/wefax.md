# WEFAX (Weather Facsimile) API Reference

WEFAX is a weather facsimile mode used to transmit images and text, particularly weather maps, satellite imagery, and weather bulletins. WEFAX transmits grayscale images using FM modulation.

## Overview

WEFAX uses Frequency Modulation (FM) where pixel grayscale values are mapped to audio frequencies. The transmission includes synchronization tones (APT START/STOP) and a phasing pattern to help receivers lock onto the signal.

**New in pydigi:** WEFAX now supports **text-to-image rendering**, automatically converting text strings into formatted pages that are transmitted as images. This is perfect for weather bulletins, forecasts, and text-based reports.

## Basic Usage

### Text Transmission (New!)

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

## Class Reference

### WEFAX

Main WEFAX modem class supporting both WEFAX-576 and WEFAX-288 modes.

```python
class WEFAX(mode="WEFAX_576", sample_rate=11025.0, carrier=1900.0,
            fm_deviation=400.0, apt_start_duration=5.0,
            apt_stop_duration=5.0, black_duration=10.0,
            phasing_lines=20, phase_inverted=False)
```

#### Parameters

- **mode** (str): WEFAX mode - "WEFAX_576" or "WEFAX_288"
  - WEFAX_576: IOC=576, default LPM=120, APT START=300 Hz, width=1809 pixels
  - WEFAX_288: IOC=288, default LPM=60, APT START=675 Hz, width=904 pixels

- **sample_rate** (float): Sample rate in Hz (default: 11025, fixed in fldigi)

- **carrier** (float): Center frequency in Hz (default: 1900)

- **fm_deviation** (float): FM deviation in Hz (default: 400, DWD uses 425)

- **apt_start_duration** (float): APT START tone duration in seconds (default: 5.0)

- **apt_stop_duration** (float): APT STOP tone duration in seconds (default: 5.0)

- **black_duration** (float): BLACK signal duration in seconds (default: 10.0)

- **phasing_lines** (int): Number of phasing lines for synchronization (default: 20)

- **phase_inverted** (bool): Invert phasing pattern black/white (default: False)

- **text_font_size** (int, optional): Font size in points for text rendering (default: auto-calculated, 20pt for WEFAX_576, 18pt for WEFAX_288)

- **text_margins** (tuple): Text margins in inches (top, right, bottom, left) (default: (1.0, 1.0, 1.0, 1.0))

- **text_font_path** (str, optional): Path to custom TTF font file (default: uses bundled DejaVu Sans Mono)

#### Attributes

- **ioc** (int): Index of Correlation (576 or 288)
- **default_lpm** (int): Default lines per minute (120 or 60)
- **apt_start_freq** (float): APT START tone frequency (300 or 675 Hz)
- **apt_stop_freq** (float): APT STOP tone frequency (450 Hz)
- **image_width** (int): Standard image width in pixels (1809 or 904)

### Methods

#### transmit_image()

Primary method for WEFAX transmission. Transmits an image with full WEFAX protocol.

```python
def transmit_image(image, lpm=None, include_apt_start=True,
                  include_phasing=True, include_apt_stop=True,
                  include_black=True) -> np.ndarray
```

**Parameters:**

- **image**: Input image, can be:
  - numpy array (H, W) with grayscale values 0-255
  - PIL Image object (converted to grayscale)
  - File path (str or Path) - requires Pillow

- **lpm** (int, optional): Lines per minute override (default: use mode's default_lpm)

- **include_apt_start** (bool): Include APT START tone (default: True)

- **include_phasing** (bool): Include phasing pattern (default: True)

- **include_apt_stop** (bool): Include APT STOP tone (default: True)

- **include_black** (bool): Include black signal (default: True)

**Returns:** numpy.ndarray of float64 audio samples

**Example:**
```python
wefax = WEFAX576()

# From file
audio = wefax.transmit_image("weather_map.png")

# From numpy array
img = np.zeros((200, 1809), dtype=np.uint8)
audio = wefax.transmit_image(img, lpm=120)

# Partial transmission (image only)
audio = wefax.transmit_image(img, include_apt_start=False,
                             include_phasing=False,
                             include_apt_stop=False,
                             include_black=False)
```

#### tx_process()

Renders text as an image and transmits it, or generates a test pattern if text is empty.

```python
def tx_process(text: str) -> np.ndarray
```

**Parameters:**

- **text** (str): Text to render and transmit. Empty string generates a test pattern.

**Returns:** numpy.ndarray of float64 audio samples

**Text Rendering Details:**
- Renders text as monospace (DejaVu Sans Mono) on letter-sized pages (8.5" × 11")
- Uses 96 LPI (Lines Per Inch) vertical resolution (WEFAX standard)
- Default margins: 1 inch on all sides
- Font size: 20pt for WEFAX_576, 18pt for WEFAX_288 (~45 chars/line)
- Multi-page text automatically paginated with 2-second APT STOP tone between pages

**Example:**
```python
wefax = WEFAX576()

# Text transmission
text = "WEATHER REPORT\\nWind: 15kt\\nTemp: 20°C"
audio = wefax.tx_process(text)

# Test pattern (empty text)
audio_test = wefax.tx_process("")
```

#### transmit_test_pattern()

Explicitly generates and transmits a test pattern.

```python
def transmit_test_pattern(width=None, height=200) -> np.ndarray
```

**Parameters:**

- **width** (int, optional): Image width in pixels (default: use mode's image_width)
- **height** (int): Image height in pixels (default: 200)

**Returns:** numpy.ndarray of float64 audio samples

**Example:**
```python
wefax = WEFAX576()
audio = wefax.transmit_test_pattern()
```

#### modulate()

High-level API inherited from base Modem class. Renders text as an image or generates test pattern.

```python
def modulate(text: str, frequency=None, sample_rate=None,
            leading_silence=None, trailing_silence=None) -> np.ndarray
```

**Parameters:**

- **text** (str): Text to render and transmit (empty string = test pattern)
- **frequency** (float, optional): Ignored (WEFAX uses fixed carrier frequency)
- **sample_rate** (float, optional): Ignored (WEFAX uses fixed 11025 Hz)
- **leading_silence** (float, optional): Seconds of silence before transmission
- **trailing_silence** (float, optional): Seconds of silence after transmission

**Returns:** numpy.ndarray of float64 audio samples

**Example:**
```python
wefax = WEFAX576()

# Text transmission
audio = wefax.modulate("WEATHER BULLETIN\\nWind: NE 15kt")

# Test pattern
audio_test = wefax.modulate("")
```

## Convenience Functions

### WEFAX576()

Creates a WEFAX-576 modem (most common mode).

```python
def WEFAX576(sample_rate=11025.0, carrier=1900.0, **kwargs) -> WEFAX
```

**Example:**
```python
wefax = WEFAX576()
print(f"Image width: {wefax.image_width} pixels")  # 1809
print(f"Default LPM: {wefax.default_lpm}")  # 120
```

### WEFAX288()

Creates a WEFAX-288 modem (less common, narrower bandwidth).

```python
def WEFAX288(sample_rate=11025.0, carrier=1900.0, **kwargs) -> WEFAX
```

**Example:**
```python
wefax = WEFAX288()
print(f"Image width: {wefax.image_width} pixels")  # 904
print(f"Default LPM: {wefax.default_lpm}")  # 60
```

## Technical Details

### FM Modulation

WEFAX uses FM modulation where pixel values map to frequencies:

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

### Image Dimensions

- **WEFAX-576**: 1809 pixels wide (IOC × π ≈ 576 × 3.14159)
- **WEFAX-288**: 904 pixels wide (IOC × π ≈ 288 × 3.14159)
- Height: Unlimited (depends on source image)
- Automatically resizes images to match mode width

## Image Input Formats

### Numpy Array (No dependencies)

```python
import numpy as np

# Create gradient (200 rows × 1809 columns)
img = np.zeros((200, 1809), dtype=np.uint8)
for col in range(1809):
    img[:, col] = int(255 * col / 1809)

wefax = WEFAX576()
audio = wefax.transmit_image(img)
```

### PIL Image (Requires Pillow)

```python
from PIL import Image

# Load and convert to grayscale
pil_img = Image.open("weather_map.png").convert("L")

wefax = WEFAX576()
audio = wefax.transmit_image(pil_img)
```

### File Path (Requires Pillow)

```python
# Install: pip install pydigi[image]

wefax = WEFAX576()
audio = wefax.transmit_image("weather_map.png")
```

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

### Image File with Auto-Resize

```python
from pydigi import WEFAX576, save_wav

wefax = WEFAX576()

# Automatically resizes to 1809 pixels wide
audio = wefax.transmit_image("any_size_image.png")
save_wav("wefax_output.wav", audio, 11025)
```

## Text Rendering

### Overview

WEFAX can automatically render text as images for transmission. This is perfect for weather bulletins, forecasts, and text-based reports that need to be transmitted via WEFAX.

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

### Text Example

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
# Long bulletin automatically spans multiple pages
long_text = "WEATHER BULLETIN\n\n" + "\n".join([
    f"Hour {i:02d}: Temp {20+i%10}°C, Wind {10+i%15}kt"
    for i in range(100)
])

audio = wefax.modulate(long_text)
# Transmits multiple pages with APT STOP tone separators
```

### Custom Font and Margins

```python
# Custom font size and margins
wefax = WEFAX576(
    text_font_size=22,  # Larger font
    text_margins=(0.5, 0.5, 0.5, 0.5),  # Smaller margins (inches)
    text_font_path="/path/to/custom/font.ttf"  # Optional custom font
)

audio = wefax.modulate("Custom formatted text")
```

### Bundled Font

PyDigi includes **DejaVu Sans Mono** font for consistent cross-platform text rendering:
- License: Bitstream Vera + Arev Fonts (permissive)
- Character coverage: Latin, Cyrillic, Greek, Arabic, and more
- Location: `pydigi/fonts/DejaVuSansMono.ttf`
- No external fonts required!

### Installation for Text Rendering

Text rendering requires Pillow (PIL):

```bash
pip install pydigi[image]
```

Or install Pillow separately:

```bash
pip install Pillow
```

## Mode Comparison

| Feature | WEFAX-576 | WEFAX-288 |
|---------|-----------|-----------|
| IOC | 576 | 288 |
| Image Width | 1809 pixels | 904 pixels |
| Default LPM | 120 | 60 |
| APT START | 300 Hz | 675 Hz |
| APT STOP | 450 Hz | 450 Hz |
| **Text Font** | **20pt** | **18pt** |
| **Chars/Line** | **~45** | **~42** |
| Common Use | Standard weather fax | Narrow bandwidth |

## Installation

For image file support (Pillow):

```bash
pip install pydigi[image]
```

Or install Pillow separately:

```bash
pip install Pillow
```

## Reference

Based on fldigi implementation: `fldigi/src/wefax/wefax.cxx`

## See Also

- [Basic Examples](../../examples/basic.md)
- [API Overview](../overview.md)
- [Base Modem Class](base.md)
