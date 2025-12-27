#!/usr/bin/env python3
"""
FSQ Modem Examples

This script demonstrates the FSQ (Fast Simple QSO) modem implementation
in PyDigi, showing various use cases and features.

FSQ is a robust MFSK mode designed for keyboard-to-keyboard QSO and
automated operations on HF bands.

Run this script to generate example WAV files that can be decoded in fldigi.
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from pydigi.modems.fsq import FSQ, FSQ_2, FSQ_3, FSQ_6
from pydigi.utils.audio import save_wav


def example_1_basic_fsq():
    """Example 1: Basic FSQ transmission at 3.0 baud (standard speed)"""
    print("\n=== Example 1: Basic FSQ (3.0 baud) ===")

    fsq = FSQ(baud_rate=3.0, callsign="W1ABC")
    text = "CQ CQ CQ DE W1ABC W1ABC K"

    print(f"Text: {text}")
    print(f"Baud rate: {fsq.baud_rate} baud")
    print(f"Symbol length: {fsq.symlen} samples")
    print(f"Tones: {fsq.num_tones}")
    print(f"Tone spacing: {fsq.tone_spacing} Hz")

    # Generate audio
    audio = fsq.modulate(text, frequency=1500.0)
    duration = len(audio) / fsq.sample_rate

    print(f"Generated {len(audio)} samples ({duration:.2f}s)")
    print(f"Estimated duration: {fsq.estimate_duration(text):.2f}s")

    # Save to WAV
    filename = "fsq_basic_3baud.wav"
    save_wav(filename, audio, fsq.sample_rate)
    print(f"Saved to {filename}")

    return audio


def example_2_slow_fsq():
    """Example 2: Slow FSQ at 2.0 baud for weak signal work"""
    print("\n=== Example 2: Slow FSQ (2.0 baud) ===")

    fsq = FSQ_2()  # 2.0 baud
    fsq.callsign = "KA1XYZ"
    text = "CQ DX CQ DX DE KA1XYZ KA1XYZ PSE K"

    print(f"Text: {text}")
    print(f"Baud rate: {fsq.baud_rate} baud (slower for weak signals)")
    print(f"Symbol length: {fsq.symlen} samples")

    # Generate audio
    audio = fsq.modulate(text, frequency=1500.0)
    duration = len(audio) / fsq.sample_rate

    print(f"Generated {len(audio)} samples ({duration:.2f}s)")
    print(f"Estimated duration: {fsq.estimate_duration(text):.2f}s")

    # Save to WAV
    filename = "fsq_slow_2baud.wav"
    save_wav(filename, audio, fsq.sample_rate)
    print(f"Saved to {filename}")

    return audio


def example_3_fast_fsq():
    """Example 3: Fast FSQ at 6.0 baud for good conditions"""
    print("\n=== Example 3: Fast FSQ (6.0 baud) ===")

    fsq = FSQ_6()  # 6.0 baud
    fsq.callsign = "N2DEF"
    text = "W1ABC DE N2DEF TNX QSO 73"

    print(f"Text: {text}")
    print(f"Baud rate: {fsq.baud_rate} baud (faster for good conditions)")
    print(f"Symbol length: {fsq.symlen} samples")

    # Generate audio
    audio = fsq.modulate(text, frequency=1500.0)
    duration = len(audio) / fsq.sample_rate

    print(f"Generated {len(audio)} samples ({duration:.2f}s)")
    print(f"Estimated duration: {fsq.estimate_duration(text):.2f}s")

    # Save to WAV
    filename = "fsq_fast_6baud.wav"
    save_wav(filename, audio, fsq.sample_rate)
    print(f"Saved to {filename}")

    return audio


def example_4_different_frequencies():
    """Example 4: FSQ at different audio frequencies"""
    print("\n=== Example 4: FSQ at Different Frequencies ===")

    fsq = FSQ(baud_rate=3.0, callsign="VE3XYZ")
    text = "FSQ TEST"

    frequencies = [1000, 1500, 2000]

    for freq in frequencies:
        print(f"\nFrequency: {freq} Hz")

        audio = fsq.modulate(text, frequency=freq)
        duration = len(audio) / fsq.sample_rate

        print(f"Generated {len(audio)} samples ({duration:.2f}s)")

        filename = f"fsq_freq_{freq}hz.wav"
        save_wav(filename, audio, fsq.sample_rate)
        print(f"Saved to {filename}")


def example_5_special_characters():
    """Example 5: FSQ with special characters and numbers"""
    print("\n=== Example 5: Special Characters and Numbers ===")

    fsq = FSQ(baud_rate=3.0, callsign="K5ABC")
    text = "RST 599 QTH: NEW YORK, NY 73!"

    print(f"Text: {text}")
    print(f"Baud rate: {fsq.baud_rate} baud")

    # Generate audio
    audio = fsq.modulate(text, frequency=1500.0)
    duration = len(audio) / fsq.sample_rate

    print(f"Generated {len(audio)} samples ({duration:.2f}s)")
    print(f"Estimated duration: {fsq.estimate_duration(text):.2f}s")

    # Save to WAV
    filename = "fsq_special_chars.wav"
    save_wav(filename, audio, fsq.sample_rate)
    print(f"Saved to {filename}")

    return audio


def example_6_no_preamble():
    """Example 6: FSQ without preamble/postamble (raw data)"""
    print("\n=== Example 6: FSQ Without Preamble/Postamble ===")

    fsq = FSQ(baud_rate=3.0, callsign="AB1CD")
    text = "TESTING 123"

    print(f"Text: {text}")
    print("Mode: No preamble/postamble (raw data mode)")

    # Generate audio without preamble/postamble
    audio = fsq.modulate(text, frequency=1500.0,
                        add_preamble=False, add_postamble=False)
    duration = len(audio) / fsq.sample_rate

    print(f"Generated {len(audio)} samples ({duration:.2f}s)")
    print(f"Estimated duration: {fsq.estimate_duration(text, add_preamble=False, add_postamble=False):.2f}s")

    # Save to WAV
    filename = "fsq_no_preamble.wav"
    save_wav(filename, audio, fsq.sample_rate)
    print(f"Saved to {filename}")

    return audio


def example_7_speed_comparison():
    """Example 7: Compare all FSQ speeds with same text"""
    print("\n=== Example 7: Speed Comparison ===")

    text = "QUICK BROWN FOX"
    baud_rates = [2.0, 3.0, 4.5, 6.0]

    print(f"Text: {text}")
    print(f"Comparing baud rates: {baud_rates}")
    print()

    for baud_rate in baud_rates:
        fsq = FSQ(baud_rate=baud_rate, callsign="TEST")

        audio = fsq.modulate(text, frequency=1500.0)
        duration = len(audio) / fsq.sample_rate
        estimated = fsq.estimate_duration(text)

        print(f"{baud_rate} baud: {len(audio):6d} samples, {duration:6.2f}s (est: {estimated:6.2f}s)")

        filename = f"fsq_speed_comp_{baud_rate}baud.wav"
        save_wav(filename, audio, fsq.sample_rate)


def example_8_long_message():
    """Example 8: Longer message transmission"""
    print("\n=== Example 8: Long Message ===")

    fsq = FSQ(baud_rate=3.0, callsign="W9XYZ")
    text = """CQ CQ CQ DE W9XYZ W9XYZ W9XYZ K
W9XYZ HERE QTH CHICAGO IL
WX SUNNY 72F
RIG IC7300 ANT DIPOLE @ 40FT
PSE K"""

    print(f"Text ({len(text)} chars):")
    print(text)
    print()

    # Generate audio
    audio = fsq.modulate(text, frequency=1500.0)
    duration = len(audio) / fsq.sample_rate

    print(f"Generated {len(audio)} samples ({duration:.2f}s)")
    print(f"Estimated duration: {fsq.estimate_duration(text):.2f}s")

    # Save to WAV
    filename = "fsq_long_message.wav"
    save_wav(filename, audio, fsq.sample_rate)
    print(f"Saved to {filename}")

    return audio


def example_9_all_speeds():
    """Example 9: Generate files for all valid FSQ speeds"""
    print("\n=== Example 9: All FSQ Speeds ===")

    text = "FSQ SPEED TEST MESSAGE"

    print(f"Text: {text}")
    print(f"Generating files for all speeds: {FSQ.VALID_BAUD_RATES}")
    print()

    for baud_rate in FSQ.VALID_BAUD_RATES:
        fsq = FSQ(baud_rate=baud_rate, callsign="TEST")

        audio = fsq.modulate(text, frequency=1500.0)
        duration = len(audio) / fsq.sample_rate

        print(f"{baud_rate:4.1f} baud: {len(audio):6d} samples, {duration:6.2f}s")

        # Use baud rate string that's filesystem-safe
        baud_str = str(baud_rate).replace('.', '_')
        filename = f"fsq_all_speeds_{baud_str}baud.wav"
        save_wav(filename, audio, fsq.sample_rate)
        print(f"  Saved to {filename}")


def main():
    """Run all examples."""
    print("=" * 70)
    print("FSQ Modem Examples")
    print("=" * 70)
    print("\nGenerating FSQ example WAV files...")
    print("These files can be decoded in fldigi by selecting FSQ mode.")

    # Run all examples
    example_1_basic_fsq()
    example_2_slow_fsq()
    example_3_fast_fsq()
    example_4_different_frequencies()
    example_5_special_characters()
    example_6_no_preamble()
    example_7_speed_comparison()
    example_8_long_message()
    example_9_all_speeds()

    print("\n" + "=" * 70)
    print("All examples complete!")
    print("Generated WAV files are ready for testing in fldigi.")
    print("=" * 70)


if __name__ == "__main__":
    main()
