#!/usr/bin/env python3
"""
WEFAX (Weather Facsimile) Example

This example demonstrates how to use the WEFAX modem to transmit images.
WEFAX is different from other pydigi modems - it transmits images rather
than text.

Requirements:
    - pydigi
    - numpy
    - Pillow (PIL) for image loading (optional, can use numpy arrays directly)

Reference: fldigi/src/wefax/wefax.cxx
"""

import numpy as np
from pydigi.modems import WEFAX, WEFAX576, WEFAX288
from pydigi.utils.audio import save_wav


def example_1_test_pattern():
    """
    Example 1: Transmit WEFAX test pattern (no image file needed)

    The transmit_test_pattern() method generates a black/white bar test pattern.
    This is useful for testing without requiring an image file or text input.
    """
    print("Example 1: WEFAX Test Pattern")
    print("-" * 50)

    # Create WEFAX_576 modem
    wefax = WEFAX576()

    # Generate test pattern transmission using transmit_test_pattern()
    audio = wefax.transmit_test_pattern()

    # Save to WAV file
    save_wav("wefax_test_pattern.wav", audio, wefax.sample_rate)

    duration = len(audio) / wefax.sample_rate
    print(f"Generated test pattern transmission")
    print(f"Duration: {duration:.1f} seconds ({len(audio)} samples)")
    print(f"Saved to: wefax_test_pattern.wav")
    print()

    # You can also use modulate("") for backwards compatibility
    print('Note: modulate("") also generates test pattern for backwards compatibility')
    print()


def example_2_numpy_array():
    """
    Example 2: Transmit image from numpy array

    Create a simple gradient image and transmit it.
    No PIL/Pillow required for this example.
    """
    print("Example 2: WEFAX from Numpy Array")
    print("-" * 50)

    # Create a gradient image (200 rows, 1809 columns)
    # WEFAX_576 has image width of 1809 pixels
    width = 1809
    height = 200

    # Create horizontal gradient (black to white)
    gradient = np.zeros((height, width), dtype=np.uint8)
    for col in range(width):
        gradient[:, col] = int(255 * col / width)

    # Create WEFAX_576 modem
    wefax = WEFAX576()

    # Transmit the image
    audio = wefax.transmit_image(gradient)

    # Save to WAV file
    save_wav("wefax_gradient.wav", audio, wefax.sample_rate)

    duration = len(audio) / wefax.sample_rate
    print(f"Generated gradient image transmission")
    print(f"Image size: {height}x{width} pixels")
    print(f"Duration: {duration:.1f} seconds ({len(audio)} samples)")
    print(f"Saved to: wefax_gradient.wav")
    print()


def example_3_image_file():
    """
    Example 3: Transmit image from file

    Requires Pillow (PIL) to be installed.
    If you don't have an image file, this will create one.
    """
    print("Example 3: WEFAX from Image File")
    print("-" * 50)

    try:
        from PIL import Image

        # Create a sample image with text and patterns
        width = 1809
        height = 300
        img = Image.new("L", (width, height), color=128)  # Gray background

        # Add some patterns
        pixels = img.load()

        # Top third: white
        for y in range(height // 3):
            for x in range(width):
                pixels[x, y] = 255

        # Middle third: gray (already set)

        # Bottom third: black
        for y in range(2 * height // 3, height):
            for x in range(width):
                pixels[x, y] = 0

        # Add vertical bars
        for x in range(0, width, 100):
            for y in range(height):
                if (x // 100) % 2 == 0:
                    pixels[x, y] = 0 if pixels[x, y] > 128 else 255

        # Save sample image
        img.save("sample_wefax.png")
        print(f"Created sample image: sample_wefax.png")

        # Transmit the image
        wefax = WEFAX576()
        audio = wefax.transmit_image("sample_wefax.png")

        # Save to WAV file
        save_wav("wefax_from_file.wav", audio, wefax.sample_rate)

        duration = len(audio) / wefax.sample_rate
        print(f"Transmitted image from file")
        print(f"Duration: {duration:.1f} seconds")
        print(f"Saved to: wefax_from_file.wav")
        print()

    except ImportError:
        print("Pillow (PIL) not installed. Skipping this example.")
        print("Install with: pip install Pillow")
        print()


def example_4_both_modes():
    """
    Example 4: Compare WEFAX_576 and WEFAX_288 modes

    Shows the difference between the two WEFAX modes.
    """
    print("Example 4: WEFAX_576 vs WEFAX_288")
    print("-" * 50)

    # Create a simple checkerboard pattern
    width = 1809  # Will be resized for WEFAX_288
    height = 100
    checkerboard = np.zeros((height, width), dtype=np.uint8)

    # Create checkerboard (20x20 pixel squares)
    square_size = 20
    for y in range(height):
        for x in range(width):
            if ((x // square_size) + (y // square_size)) % 2 == 0:
                checkerboard[y, x] = 255

    # WEFAX_576 transmission
    print("WEFAX_576 mode:")
    wefax576 = WEFAX576()
    audio576 = wefax576.transmit_image(checkerboard)
    save_wav("wefax_576_checkerboard.wav", audio576, wefax576.sample_rate)
    duration576 = len(audio576) / wefax576.sample_rate
    print(f"  IOC: {wefax576.ioc}")
    print(f"  Default LPM: {wefax576.default_lpm}")
    print(f"  APT START: {wefax576.apt_start_freq} Hz")
    print(f"  Image width: {wefax576.image_width} pixels")
    print(f"  Duration: {duration576:.1f} seconds")
    print(f"  Saved to: wefax_576_checkerboard.wav")
    print()

    # WEFAX_288 transmission
    print("WEFAX_288 mode:")
    wefax288 = WEFAX288()
    audio288 = wefax288.transmit_image(checkerboard)
    save_wav("wefax_288_checkerboard.wav", audio288, wefax288.sample_rate)
    duration288 = len(audio288) / wefax288.sample_rate
    print(f"  IOC: {wefax288.ioc}")
    print(f"  Default LPM: {wefax288.default_lpm}")
    print(f"  APT START: {wefax288.apt_start_freq} Hz")
    print(f"  Image width: {wefax288.image_width} pixels")
    print(f"  Duration: {duration288:.1f} seconds")
    print(f"  Saved to: wefax_288_checkerboard.wav")
    print()


def example_5_custom_lpm():
    """
    Example 5: Custom LPM (Lines Per Minute) setting

    Shows how to override the default LPM to speed up or slow down transmission.
    """
    print("Example 5: Custom LPM Settings")
    print("-" * 50)

    # Create a simple image
    width = 1809
    height = 50
    stripes = np.zeros((height, width), dtype=np.uint8)

    # Horizontal stripes
    for y in range(height):
        if (y // 10) % 2 == 0:
            stripes[y, :] = 255

    wefax = WEFAX576()

    # Default LPM (120)
    print(f"Default LPM: {wefax.default_lpm}")
    audio_default = wefax.transmit_image(stripes)
    duration_default = len(audio_default) / wefax.sample_rate
    print(f"  Duration: {duration_default:.1f} seconds")
    save_wav("wefax_lpm_default.wav", audio_default, wefax.sample_rate)
    print(f"  Saved to: wefax_lpm_default.wav")
    print()

    # Fast transmission (240 LPM)
    print("Fast LPM: 240")
    audio_fast = wefax.transmit_image(stripes, lpm=240)
    duration_fast = len(audio_fast) / wefax.sample_rate
    print(f"  Duration: {duration_fast:.1f} seconds")
    save_wav("wefax_lpm_fast.wav", audio_fast, wefax.sample_rate)
    print(f"  Saved to: wefax_lpm_fast.wav")
    print()

    # Slow transmission (60 LPM)
    print("Slow LPM: 60")
    audio_slow = wefax.transmit_image(stripes, lpm=60)
    duration_slow = len(audio_slow) / wefax.sample_rate
    print(f"  Duration: {duration_slow:.1f} seconds")
    save_wav("wefax_lpm_slow.wav", audio_slow, wefax.sample_rate)
    print(f"  Saved to: wefax_lpm_slow.wav")
    print()


def example_6_partial_transmission():
    """
    Example 6: Partial transmission (disable APT/phasing/black)

    Shows how to transmit just the image data without APT tones and phasing.
    """
    print("Example 6: Partial Transmission Options")
    print("-" * 50)

    # Create a simple image
    width = 1809
    height = 100
    circle_pattern = np.zeros((height, width), dtype=np.uint8)

    # Create concentric circles
    center_y = height // 2
    center_x = width // 2
    for y in range(height):
        for x in range(width):
            distance = np.sqrt((x - center_x) ** 2 + (y - center_y) ** 2)
            circle_pattern[y, x] = int((np.sin(distance / 20) + 1) * 127.5)

    wefax = WEFAX576()

    # Full transmission (default)
    print("Full transmission (with all components):")
    audio_full = wefax.transmit_image(circle_pattern)
    duration_full = len(audio_full) / wefax.sample_rate
    print(f"  Duration: {duration_full:.1f} seconds")
    save_wav("wefax_full.wav", audio_full, wefax.sample_rate)
    print(f"  Saved to: wefax_full.wav")
    print()

    # Image only (no APT tones, no phasing, no black)
    print("Image data only (no APT/phasing/black):")
    audio_image_only = wefax.transmit_image(
        circle_pattern,
        include_apt_start=False,
        include_phasing=False,
        include_apt_stop=False,
        include_black=False,
    )
    duration_image = len(audio_image_only) / wefax.sample_rate
    print(f"  Duration: {duration_image:.1f} seconds")
    save_wav("wefax_image_only.wav", audio_image_only, wefax.sample_rate)
    print(f"  Saved to: wefax_image_only.wav")
    print()


def example_7_text_transmission():
    """
    Example 7: Transmit text rendered as image

    Shows how to use tx_process() and modulate() to transmit text.
    Text is rendered as monospace on letter-sized pages with 1" margins.
    """
    print("Example 7: WEFAX Text Transmission")
    print("-" * 50)

    # Short text (single page)
    wefax = WEFAX576()
    text = """WEATHER REPORT

Temperature: 20°C
Wind: 15 knots NE
Pressure: 1013 hPa
Conditions: Partly cloudy

FORECAST:
Tomorrow - Rain expected
Winds increasing to 25kt"""

    print("Transmitting short weather report (single page)...")
    audio = wefax.modulate(text)
    save_wav("wefax_text_short.wav", audio, wefax.sample_rate)

    duration = len(audio) / wefax.sample_rate
    print(f"  Duration: {duration:.1f} seconds")
    print(f"  Saved to: wefax_text_short.wav")
    print()

    # Long text (multi-page)
    print("Transmitting long weather bulletin (multi-page)...")
    long_text = "WEATHER BULLETIN\n\n" + "\n".join(
        [
            f"Hour {i:02d}: Temperature {20+i%10}°C, Wind {10+i%15}kt, Pressure {1010+i%20} hPa"
            for i in range(100)
        ]
    )

    audio_long = wefax.modulate(long_text)
    save_wav("wefax_text_long.wav", audio_long, wefax.sample_rate)

    duration_long = len(audio_long) / wefax.sample_rate
    print(f"  Duration: {duration_long:.1f} seconds")
    print(f"  Saved to: wefax_text_long.wav")
    print()

    # WEFAX_288 mode (lower resolution, faster)
    print("Transmitting with WEFAX_288 mode (lower resolution)...")
    wefax288 = WEFAX288()
    text_288 = """WEFAX_288 MODE TEST

This is transmitted using
WEFAX_288 mode which has
lower resolution but faster
transmission time.

Image width: 904 pixels
~106 DPI"""

    audio_288 = wefax288.modulate(text_288)
    save_wav("wefax_text_288.wav", audio_288, wefax288.sample_rate)

    duration_288 = len(audio_288) / wefax288.sample_rate
    print(f"  Duration: {duration_288:.1f} seconds")
    print(f"  Saved to: wefax_text_288.wav")
    print()


def example_8_markdown_transmission():
    """
    Example 8: Transmit markdown-formatted text

    Shows how to use markdown formatting for rich text rendering.
    Requires Pillow to be installed.
    """
    print("Example 8: WEFAX Markdown Transmission")
    print("-" * 50)

    try:
        # Create WEFAX modem with markdown enabled
        wefax = WEFAX576(text_markdown=True)

        # Markdown text with various formatting
        markdown_text = """# Weather Report
## Marine Forecast for Region 7

### Current Conditions
**Date**: December 27, 2025
**Time**: 20:00 UTC
**Location**: North Atlantic

---

### Wind Conditions
- **Current Speed**: 15 knots
- **Direction**: Northeast (045°)
- **Gusts**: Up to 22 knots

### Temperature
- Air: *20°C* (68°F)
- Sea: *18°C* (64°F)
- Dewpoint: *15°C* (59°F)

### Pressure
Current pressure: `1013.2 hPa`

> **Warning**: Pressure falling rapidly.
> Storm system approaching from west.

---

### Extended Forecast

#### Tomorrow (Dec 28)
1. Morning: Rain expected, winds 20-25kt
2. Afternoon: Clearing, winds decreasing
3. Evening: Partly cloudy, calm

#### Day After (Dec 29)
- Clear skies
- Light winds (5-10kt)
- Temperature rising

### Code Example
```python
# Sample weather data
conditions = {
    "wind": "15kt NE",
    "temp": "20C",
    "pressure": "1013 hPa"
}
```

---

### Safety Notice
***MARINERS ADVISED TO MONITOR CONDITIONS***

For updates, contact marine weather service.

*End of Report*
"""

        print("Transmitting markdown weather report...")
        audio = wefax.modulate(markdown_text)
        save_wav("wefax_markdown.wav", audio, wefax.sample_rate)

        duration = len(audio) / wefax.sample_rate
        print(f"  Duration: {duration:.1f} seconds")
        print(f"  Saved to: wefax_markdown.wav")
        print()

        # Short markdown example
        print("Transmitting short markdown document...")
        short_markdown = """# Quick Reference

## Text Styles
- **Bold text** for emphasis
- *Italic text* for foreign words
- ***Bold and italic*** for strong emphasis
- `inline code` for technical terms

## Lists
1. First item
2. Second item
3. Third item

> Important note in blockquote

---

End of document.
"""

        wefax_short = WEFAX576(text_markdown=True)
        audio_short = wefax_short.modulate(short_markdown)
        save_wav("wefax_markdown_short.wav", audio_short, wefax_short.sample_rate)

        duration_short = len(audio_short) / wefax_short.sample_rate
        print(f"  Duration: {duration_short:.1f} seconds")
        print(f"  Saved to: wefax_markdown_short.wav")
        print()

    except ImportError as e:
        print("Pillow (PIL) not installed. Skipping markdown examples.")
        print(f"Error: {e}")
        print("Install with: pip install 'pydigi[image]'")
        print()


def main():
    """Run all WEFAX examples."""
    print("=" * 50)
    print("WEFAX (Weather Facsimile) Examples")
    print("=" * 50)
    print()

    # Run all examples
    example_1_test_pattern()
    example_2_numpy_array()
    example_3_image_file()
    example_4_both_modes()
    example_5_custom_lpm()
    example_6_partial_transmission()
    example_7_text_transmission()
    example_8_markdown_transmission()

    print("=" * 50)
    print("All examples completed!")
    print("=" * 50)
    print()
    print("To decode these transmissions:")
    print("1. Open fldigi")
    print("2. Set mode to WEFAX-576 or WEFAX-288")
    print("3. Set carrier frequency to 1900 Hz")
    print("4. Play the WAV file through fldigi")
    print("5. Watch the image (or rendered text) appear in the WEFAX window")
    print()
    print("Note: Text transmissions use the bundled DejaVu Sans Mono font")
    print("for consistent cross-platform rendering.")
    print("Markdown transmissions use DejaVu Sans Mono variants (Bold, Oblique)")
    print("for rich text formatting.")
    print()


if __name__ == "__main__":
    main()
