#!/usr/bin/env python3
"""
NAVTEX and SITOR-B Modem Examples

Demonstrates NAVTEX maritime safety broadcast system:
- Standard NAVTEX with headers and phasing
- SITOR-B mode (raw transmission without NAVTEX structure)
- ITA-2 vs US-TTY encoding
- Forward Error Correction (FEC)

NAVTEX Technical Specifications:
- Baud rate: 100 baud
- Shift: 170 Hz (±85 Hz deviation)
- Encoding: CCIR-476 (7-bit with error detection)
- FEC: Each character transmitted twice with interleaving
- Sample rate: 11025 Hz (NAVTEX standard)

References:
    - ITU-R M.540-2 (NAVTEX technical characteristics)
    - CCIR Recommendation 476-4
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pydigi import NAVTEX, SITORB, save_wav


def example_basic():
    """Basic NAVTEX transmission with headers."""
    print("Example 1: Basic NAVTEX Message")
    print("-" * 60)

    # Create NAVTEX modem
    navtex = NAVTEX()

    # NAVTEX message text (header will be added automatically)
    text = "WEATHER WARNING: GALE FORCE 8 EXPECTED IN SEA AREA VIKING"
    print(f"Text: {text}")
    print(f"Mode: {navtex.mode_name}")
    print(f"Baud: {navtex.BAUD_RATE} baud")
    print(f"Shift: {navtex.SHIFT} Hz")

    # Modulate (NAVTEX uses 11025 Hz sample rate)
    audio = navtex.modulate(text, frequency=1000, sample_rate=11025)
    duration = len(audio) / 11025
    print(f"Generated {len(audio)} samples ({duration:.2f} seconds)")
    print(f"Message includes:")
    print(f"  - 10 second phasing signal")
    print(f"  - ZCZC header with origin and message number")
    print(f"  - Message text with FEC")
    print(f"  - NNNN trailer")
    print(f"  - 2 second end phasing")

    # Save to file
    filename = "navtex_basic.wav"
    save_wav(filename, audio, sample_rate=11025)
    print(f"Saved to: {filename}")
    print()

    return audio


def example_sitor_b():
    """SITOR-B transmission (raw mode without NAVTEX headers)."""
    print("Example 2: SITOR-B (without NAVTEX headers)")
    print("-" * 60)

    # Create SITOR-B modem (NAVTEX without headers/trailers)
    sitor = SITORB()

    text = "CQ CQ CQ DE NAVAREA1 K"
    print(f"Text: {text}")
    print(f"Mode: {sitor.mode_name}")
    print(f"Note: No phasing, headers, or trailers - just FEC-encoded text")
    print(f"      Includes 1 second of silence before and after for clean decode")

    audio = sitor.modulate(text, frequency=1000, sample_rate=11025)
    duration = len(audio) / 11025
    print(f"Generated {len(audio)} samples ({duration:.2f} seconds)")

    filename = "sitorb_basic.wav"
    save_wav(filename, audio, sample_rate=11025)
    print(f"Saved to: {filename}")
    print()


def example_ustty():
    """NAVTEX with US-TTY encoding."""
    print("Example 3: NAVTEX with US-TTY Encoding")
    print("-" * 60)

    # Create NAVTEX modem with US-TTY encoding
    navtex = NAVTEX(use_ita2=False)

    text = 'TEST MESSAGE: $123.45 "HELLO" (NAVTEX)'
    print(f"Text: {text}")
    print(f"Encoding: US-TTY (use_ita2=False)")

    audio = navtex.modulate(text, frequency=1000, sample_rate=11025)

    filename = "navtex_ustty.wav"
    save_wav(filename, audio, sample_rate=11025)
    print(f"Saved to: {filename}")
    print()


def example_maritime_warning():
    """Realistic maritime safety warning."""
    print("Example 4: Maritime Safety Warning")
    print("-" * 60)

    navtex = NAVTEX()

    # Realistic NAVTEX message format
    text = """NAVIGATIONAL WARNING NR 123/24
AREA BALTIC SEA
FIRING PRACTICE IN AREA BOUNDED BY:
  55-30N 014-45E
  55-20N 015-00E
  55-10N 014-50E
  55-15N 014-30E
UNTIL 311800 UTC DEC
WIDE BERTH REQUESTED"""

    print(f"Text:\n{text}")
    print()

    audio = navtex.modulate(text, frequency=518, sample_rate=11025)
    duration = len(audio) / 11025
    print(f"Generated {len(audio)} samples ({duration:.2f} seconds)")
    print(f"Frequency: 518 Hz (simulating 518 kHz NAVTEX frequency)")

    filename = "navtex_warning.wav"
    save_wav(filename, audio, sample_rate=11025)
    print(f"Saved to: {filename}")
    print()


def example_weather_forecast():
    """Weather forecast message."""
    print("Example 5: Weather Forecast")
    print("-" * 60)

    navtex = NAVTEX()

    text = """FORECAST VALID 271200 UTC TO 281200 UTC
SEA AREA VIKING:
WIND NW 6-7 DECREASING 4-5
SEA STATE ROUGH BECOMING MODERATE
VISIBILITY GOOD OCCASIONALLY POOR IN RAIN"""

    print(f"Text:\n{text}")
    print()

    audio = navtex.modulate(text, frequency=1000, sample_rate=11025)
    duration = len(audio) / 11025
    print(f"Generated {len(audio)} samples ({duration:.2f} seconds)")

    filename = "navtex_weather.wav"
    save_wav(filename, audio, sample_rate=11025)
    print(f"Saved to: {filename}")
    print()


def example_short_messages():
    """Compare transmission times for different message lengths."""
    print("Example 6: Message Length Comparison")
    print("-" * 60)

    messages = {
        "Short": "TEST",
        "Medium": "THE QUICK BROWN FOX JUMPS OVER THE LAZY DOG",
        "Long": "NAVTEX PROVIDES MARITIME SAFETY INFORMATION INCLUDING "
        + "NAVIGATIONAL WARNINGS, METEOROLOGICAL WARNINGS, "
        + "SEARCH AND RESCUE INFORMATION AND OTHER URGENT MESSAGES",
    }

    navtex = NAVTEX()

    print("Message length comparison:")
    print()

    for name, text in messages.items():
        audio = navtex.modulate(text, frequency=1000, sample_rate=11025)
        duration = len(audio) / 11025
        filename = f"navtex_{name.lower()}.wav"
        save_wav(filename, audio, sample_rate=11025)

        print(f"{name:8}: {len(text):3} chars, {duration:6.2f}s - {filename}")

    print()
    print("Note: NAVTEX includes significant overhead (phasing, headers, FEC)")
    print()


def example_fec_demonstration():
    """Demonstrate FEC encoding."""
    print("Example 7: Forward Error Correction (FEC)")
    print("-" * 60)

    print("NAVTEX uses SITOR-B FEC mode:")
    print("- Each character is transmitted twice (alpha and rep)")
    print("- Characters are interleaved 5 positions apart (35 bits)")
    print("- Pattern: rep alpha rep alpha C1 alpha C2 C1 C3 C2 ...")
    print("- Allows receiver to correct errors using redundancy")
    print()

    navtex = NAVTEX()
    text = "FEC TEST"

    print(f"Text: {text}")
    audio = navtex.modulate(text, frequency=1000, sample_rate=11025)

    filename = "navtex_fec.wav"
    save_wav(filename, audio, sample_rate=11025)
    print(f"Saved to: {filename}")
    print()


def example_filtering():
    """Demonstrate baseband filtering to reduce spectral splatter."""
    print("Example 8: Baseband Filtering")
    print("-" * 60)

    print("FSK modulation creates sharp transitions between mark and space")
    print("frequencies, which causes spectral splatter (unwanted frequency")
    print("components outside the intended bandwidth).")
    print()
    print("Baseband lowpass filtering is applied BEFORE frequency modulation")
    print("to smooth these transitions, producing a cleaner signal with less")
    print("interference to adjacent channels.")
    print()

    text = "NAVTEX FILTERING TEST"

    # Filtered version (default)
    navtex_filtered = NAVTEX(use_filtering=True)
    audio_filtered = navtex_filtered.modulate(text, frequency=1000, sample_rate=11025)
    filename_filtered = "navtex_filtered.wav"
    save_wav(filename_filtered, audio_filtered, sample_rate=11025)
    print(f"Filtered:   {filename_filtered}")

    # Unfiltered version (for comparison)
    navtex_unfiltered = NAVTEX(use_filtering=False)
    audio_unfiltered = navtex_unfiltered.modulate(text, frequency=1000, sample_rate=11025)
    filename_unfiltered = "navtex_unfiltered.wav"
    save_wav(filename_unfiltered, audio_unfiltered, sample_rate=11025)
    print(f"Unfiltered: {filename_unfiltered}")
    print()
    print("Compare the spectrum of both signals in a spectrum analyzer")
    print("to see the reduction in spectral splatter with filtering.")
    print()


def main():
    """Run all examples."""
    print("=" * 60)
    print("NAVTEX and SITOR-B Modem Examples")
    print("=" * 60)
    print()
    print("NAVTEX is a maritime safety broadcast system used worldwide")
    print("for navigational warnings, weather forecasts, and SAR info.")
    print()

    example_basic()
    example_sitor_b()
    example_ustty()
    example_maritime_warning()
    example_weather_forecast()
    example_short_messages()
    example_fec_demonstration()
    example_filtering()

    print("=" * 60)
    print("All examples complete!")
    print()
    print("Generated WAV files can be decoded with:")
    print("  - fldigi (NAVTEX or SITOR-B mode)")
    print("  - JNX (Java NAVTEX decoder)")
    print("  - Other NAVTEX decoding software")
    print()
    print("Standard NAVTEX frequencies:")
    print("  - 518 kHz (international)")
    print("  - 490 kHz (some regions)")
    print("  - 4209.5 kHz (tropical regions)")
    print("=" * 60)


if __name__ == "__main__":
    main()
