#!/usr/bin/env python3
"""
Generate a WEFAX transmission with markdown formatting
"""

from pydigi.modems import WEFAX576
from pydigi.utils.audio import save_wav

# Markdown-formatted text
markdown_text = """# PyDigi WEFAX Markdown Demo
## Demonstrating Rich Text Formatting

### Introduction
This transmission showcases **markdown rendering** capabilities
in the *PyDigi* WEFAX modem implementation.

---

### Text Formatting Examples

#### Bold and Italic
- **Bold text** for emphasis
- *Italic text* for foreign words or titles
- ***Bold and italic*** for strong emphasis

#### Code Examples
Inline code: `wefax.modulate(text)`

Code block:
```python
from pydigi.modems import WEFAX576

wefax = WEFAX576(text_markdown=True)
audio = wefax.modulate("# Hello World")
```

---

### Lists

#### Unordered Lists
- Weather forecasting
- Marine communications
- Emergency broadcasts
- Amateur radio operations

#### Ordered Lists
1. Initialize WEFAX modem
2. Prepare markdown text
3. Generate audio samples
4. Transmit or save to file

---

### Technical Information

**Frequency**: 1900 Hz carrier
**Mode**: WEFAX-576
**Resolution**: 1809 × 1056 pixels
**Sample Rate**: `11025 Hz`

> **Note**: WEFAX uses FM modulation where grayscale
> values are converted to audio frequencies.

---

### Markdown Features Supported

| Feature | Syntax | Status |
|---------|--------|--------|
| Headers | # ## ### | ✓ |
| Bold | **text** | ✓ |
| Italic | *text* | ✓ |
| Code | `code` | ✓ |
| Lists | - 1. | ✓ |
| Quotes | > | ✓ |

---

### Example Use Case: Weather Report

#### Current Conditions
**Date**: December 27, 2025
**Time**: 21:00 UTC
**Location**: North Pacific

**Wind**: 12 knots from Northwest
**Temperature**: 18°C (64°F)
**Pressure**: 1015.2 hPa (rising)
**Visibility**: 10+ nautical miles

> Weather conditions are favorable for marine operations.
> Next update in 6 hours.

---

### Safety Information

***IMPORTANT NOTICE FOR MARINERS***

1. Monitor VHF Channel 16
2. Check weather updates regularly
3. File float plan before departure

For emergencies, contact:
- Coast Guard: Channel 16 VHF
- SAR: `121.5 MHz` or `243.0 MHz`

---

### Code Example: Full Implementation

```python
#!/usr/bin/env python3
from pydigi.modems import WEFAX576
from pydigi.utils.audio import save_wav

# Create modem with markdown enabled
wefax = WEFAX576(text_markdown=True)

# Your markdown text
text = "# Title\\n**Bold** and *italic*"

# Generate and save
audio = wefax.modulate(text)
save_wav("output.wav", audio, wefax.sample_rate)
```

---

### Conclusion

This demonstrates the **PyDigi** WEFAX markdown rendering
system with support for:

- Multiple font styles (bold, italic, bold-italic)
- Headers at 6 different levels
- Code blocks with syntax highlighting placeholders
- Lists (ordered and unordered)
- Blockquotes with visual indicators
- Horizontal rules for section breaks

*End of transmission.*

**73 de PyDigi**
"""

print("=" * 60)
print("PyDigi WEFAX Markdown Demo Generator")
print("=" * 60)
print()

# Create WEFAX modem with markdown enabled
print("Initializing WEFAX-576 modem with markdown support...")
wefax = WEFAX576(text_markdown=True)

# Generate audio
print("Rendering markdown text to image...")
print("Generating FM-modulated audio samples...")
audio = wefax.modulate(markdown_text)

# Save to WAV file
output_file = "markdown_demo.wav"
print(f"Saving to {output_file}...")
save_wav(output_file, audio, wefax.sample_rate)

# Display statistics
duration = len(audio) / wefax.sample_rate
file_size = len(audio) * 4 / (1024 * 1024)  # Approximate size in MB

print()
print("=" * 60)
print("Generation Complete!")
print("=" * 60)
print(f"Output file: {output_file}")
print(f"Duration: {duration:.1f} seconds ({duration/60:.1f} minutes)")
print(f"Sample rate: {wefax.sample_rate} Hz")
print(f"Carrier frequency: {wefax.carrier} Hz")
print(f"Samples: {len(audio):,}")
print(f"Approximate size: {file_size:.1f} MB")
print()
print("To decode this transmission:")
print("1. Open fldigi")
print("2. Set mode to WEFAX-576")
print("3. Set carrier frequency to 1900 Hz")
print("4. Play the WAV file through fldigi")
print("5. Watch the formatted text appear as an image")
print()
print("=" * 60)
