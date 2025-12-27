#!/usr/bin/env python3
"""
RTTY (Radioteletype) Modem Examples

Demonstrates RTTY signal generation with different configurations:
- Standard 45.45 baud, 170 Hz shift
- Different baud rates
- Different shifts
- ITA-2 vs US-TTY encoding
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from pydigi import RTTY, save_wav


def example_basic():
    """Basic RTTY transmission - standard configuration."""
    print("Example 1: Basic RTTY (45.45 baud, 170 Hz shift)")
    print("-" * 60)

    # Create RTTY modem with standard settings
    rtty = RTTY(baud=45.45, shift=170)

    # Generate signal
    text = "CQ CQ CQ DE W1AW W1AW W1AW K"
    print(f"Text: {text}")
    print(f"Settings: {rtty}")

    # Estimate duration
    duration = rtty.estimate_duration(text)
    print(f"Estimated duration: {duration:.2f} seconds")

    # Modulate
    audio = rtty.modulate(text, frequency=1500, sample_rate=8000)
    print(f"Generated {len(audio)} samples ({len(audio)/8000:.2f} seconds)")

    # Save to file
    filename = "rtty_basic.wav"
    save_wav(filename, audio, sample_rate=8000)
    print(f"Saved to: {filename}")
    print()

    return audio


def example_fast():
    """Fast RTTY - 75 baud."""
    print("Example 2: Fast RTTY (75 baud, 170 Hz shift)")
    print("-" * 60)

    # Create fast RTTY modem
    rtty = RTTY(baud=75, shift=170)

    text = "THE QUICK BROWN FOX JUMPS OVER THE LAZY DOG 1234567890"
    print(f"Text: {text}")
    print(f"Settings: {rtty}")

    duration = rtty.estimate_duration(text)
    print(f"Estimated duration: {duration:.2f} seconds")

    audio = rtty.modulate(text, frequency=1500, sample_rate=8000)
    print(f"Generated {len(audio)} samples ({len(audio)/8000:.2f} seconds)")

    filename = "rtty_fast.wav"
    save_wav(filename, audio, sample_rate=8000)
    print(f"Saved to: {filename}")
    print()


def example_wide_shift():
    """Wide shift RTTY - 850 Hz (used for HF)."""
    print("Example 3: Wide Shift RTTY (45.45 baud, 850 Hz shift)")
    print("-" * 60)

    # Create wide-shift RTTY modem
    rtty = RTTY(baud=45.45, shift=850)

    text = "RYRYRYRYRY THE QUICK BROWN FOX"
    print(f"Text: {text}")
    print(f"Settings: {rtty}")

    audio = rtty.modulate(text, frequency=1500, sample_rate=8000)

    filename = "rtty_wide.wav"
    save_wav(filename, audio, sample_rate=8000)
    print(f"Saved to: {filename}")
    print()


def example_unshaped():
    """Unshaped RTTY - no raised cosine filtering."""
    print("Example 4: Unshaped RTTY (sharp transitions)")
    print("-" * 60)

    # Create unshaped RTTY modem
    rtty = RTTY(baud=45.45, shift=170, shaped=False)

    text = "UNSHAPED FSK TEST"
    print(f"Text: {text}")
    print(f"Settings: {rtty}")

    audio = rtty.modulate(text, frequency=1500, sample_rate=8000)

    filename = "rtty_unshaped.wav"
    save_wav(filename, audio, sample_rate=8000)
    print(f"Saved to: {filename}")
    print()


def example_ustty():
    """US-TTY encoding vs ITA-2."""
    print("Example 5: US-TTY encoding")
    print("-" * 60)

    # Create US-TTY modem
    rtty = RTTY(baud=45.45, shift=170, use_ita2=False)

    text = "US-TTY: $123.45 \"HELLO\" (TEST)"
    print(f"Text: {text}")
    print(f"Settings: {rtty}")

    audio = rtty.modulate(text, frequency=1500, sample_rate=8000)

    filename = "rtty_ustty.wav"
    save_wav(filename, audio, sample_rate=8000)
    print(f"Saved to: {filename}")
    print()


def example_comparison():
    """Compare different baud rates."""
    print("Example 6: Baud Rate Comparison")
    print("-" * 60)

    text = "BAUDOT"
    bauds = [45, 45.45, 50, 75]

    for baud in bauds:
        rtty = RTTY(baud=baud, shift=170)
        duration = rtty.estimate_duration(text)
        audio = rtty.modulate(text, frequency=1500, sample_rate=8000)

        filename = f"rtty_{baud}baud.wav"
        save_wav(filename, audio, sample_rate=8000)

        print(f"{baud:6.2f} baud: {duration:5.2f}s, {len(audio):6} samples - {filename}")

    print()


def example_numbers():
    """Test numbers and punctuation."""
    print("Example 7: Numbers and Punctuation")
    print("-" * 60)

    rtty = RTTY(baud=45.45, shift=170)

    # Text with shift between letters and figures
    text = "TEST 123 ABC 456 XYZ 789"
    print(f"Text: {text}")

    audio = rtty.modulate(text, frequency=1500, sample_rate=8000)

    filename = "rtty_numbers.wav"
    save_wav(filename, audio, sample_rate=8000)
    print(f"Saved to: {filename}")
    print()


def main():
    """Run all examples."""
    print("=" * 60)
    print("RTTY Modem Examples")
    print("=" * 60)
    print()

    example_basic()
    example_fast()
    example_wide_shift()
    example_unshaped()
    example_ustty()
    example_comparison()
    example_numbers()

    print("=" * 60)
    print("All examples complete!")
    print("Generated WAV files can be decoded with fldigi or other RTTY software.")
    print("=" * 60)


if __name__ == '__main__':
    main()
