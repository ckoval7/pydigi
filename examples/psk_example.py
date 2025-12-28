"""
PSK Modem Example

Demonstrates the PSK (Phase Shift Keying) modem implementation.
Generates WAV files for PSK31, PSK63, PSK125, and other modes.

These files can be decoded in fldigi or other PSK software to verify
the implementation.
"""

import sys
import os

# Add parent directory to path to import pydigi
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from pydigi.modems.psk import PSK, PSK31, PSK63, PSK125, PSK250, PSK500
from pydigi.utils.audio import save_wav


def example1_psk31_basic():
    """Example 1: Basic PSK31 transmission."""
    print("Example 1: PSK31 Basic")
    print("-" * 50)

    # Create PSK31 modem
    psk31 = PSK31(frequency=1000)

    # Test message
    text = "CQ CQ CQ DE W1ABC W1ABC PSK31 TEST"

    # Generate audio
    print(f"Mode: {psk31.mode_name}")
    print(f"Text: {text}")
    print(f"Baud rate: {psk31.baud}")
    print(f"Frequency: {psk31.frequency} Hz")
    print(f"Sample rate: {psk31.sample_rate} Hz")

    duration = psk31.estimate_duration(text)
    print(f"Estimated duration: {duration:.2f} seconds")

    audio = psk31.modulate(text)
    print(f"Generated {len(audio)} samples ({len(audio)/psk31.sample_rate:.2f}s)")

    # Save to WAV file
    filename = "psk31_basic.wav"
    save_wav(filename, audio, sample_rate=psk31.sample_rate)
    print(f"Saved to {filename}")
    print()


def example2_psk63():
    """Example 2: PSK63 (faster mode)."""
    print("Example 2: PSK63 (faster)")
    print("-" * 50)

    # Create PSK63 modem (2x faster than PSK31)
    psk63 = PSK63(frequency=1500)

    text = "PSK63 TEST MESSAGE - TWICE AS FAST AS PSK31"

    print(f"Mode: {psk63.mode_name}")
    print(f"Text: {text}")
    duration = psk63.estimate_duration(text)
    print(f"Estimated duration: {duration:.2f} seconds")

    audio = psk63.modulate(text)

    filename = "psk63_fast.wav"
    save_wav(filename, audio, sample_rate=psk63.sample_rate)
    print(f"Saved to {filename}")
    print()


def example3_psk125():
    """Example 3: PSK125 (even faster)."""
    print("Example 3: PSK125 (even faster)")
    print("-" * 50)

    psk125 = PSK125(frequency=1000)

    text = "PSK125 HIGH SPEED MODE - 4X FASTER THAN PSK31"

    print(f"Mode: {psk125.mode_name}")
    print(f"Text: {text}")
    duration = psk125.estimate_duration(text)
    print(f"Estimated duration: {duration:.2f} seconds")

    audio = psk125.modulate(text)

    filename = "psk125_highspeed.wav"
    save_wav(filename, audio, sample_rate=psk125.sample_rate)
    print(f"Saved to {filename}")
    print()


def example4_mode_comparison():
    """Example 4: Compare multiple PSK modes with same message."""
    print("Example 4: PSK Mode Comparison")
    print("-" * 50)

    text = "TESTING 123"

    modes = [
        ("PSK31", PSK31(frequency=1000)),
        ("PSK63", PSK63(frequency=1000)),
        ("PSK125", PSK125(frequency=1000)),
        ("PSK250", PSK250(frequency=1000)),
    ]

    print(f"Message: {text}")
    print(f"\n{'Mode':<10} {'Baud':<10} {'Duration':<12} {'Samples':<10}")
    print("-" * 50)

    for mode_name, modem in modes:
        duration = modem.estimate_duration(text)
        audio = modem.modulate(text)
        samples = len(audio)

        print(f"{mode_name:<10} {modem.baud:<10.2f} {duration:<12.3f} {samples:<10}")

        filename = f"psk_compare_{mode_name.lower()}.wav"
        save_wav(filename, audio, sample_rate=modem.sample_rate)

    print(f"\nSaved 4 comparison files")
    print()


def example5_special_characters():
    """Example 5: PSK31 with punctuation and numbers."""
    print("Example 5: PSK31 with Special Characters")
    print("-" * 50)

    psk31 = PSK31(frequency=1200)

    # Test various character types
    text = "TEST: ABC 123 !@# $%& (OK?)"

    print(f"Text: {text}")

    audio = psk31.modulate(text)

    filename = "psk31_special_chars.wav"
    save_wav(filename, audio, sample_rate=psk31.sample_rate)
    print(f"Saved to {filename}")
    print()


def example6_long_preamble():
    """Example 6: PSK31 with long preamble for better sync."""
    print("Example 6: PSK31 with Long Preamble")
    print("-" * 50)

    psk31 = PSK31(frequency=1000)

    text = "AFTER LONG PREAMBLE"

    # Use longer preamble (64 symbols instead of default 32)
    # This helps receivers lock on to the signal
    audio = psk31.modulate(text, preamble_symbols=64)

    filename = "psk31_long_preamble.wav"
    save_wav(filename, audio, sample_rate=psk31.sample_rate)
    print(f"Saved to {filename} (64 symbol preamble)")
    print()


def example7_custom_baud():
    """Example 7: Custom baud rate."""
    print("Example 7: Custom Baud Rate")
    print("-" * 50)

    # Create PSK modem with custom baud rate
    # For example, PSK100 (100 baud)
    psk100 = PSK(baud=100, frequency=1500)

    text = "CUSTOM PSK100 MODE"

    print(f"Mode: {psk100.mode_name}")
    print(f"Baud: {psk100.baud}")

    audio = psk100.modulate(text)

    filename = "psk100_custom.wav"
    save_wav(filename, audio, sample_rate=psk100.sample_rate)
    print(f"Saved to {filename}")
    print()


def example8_different_frequencies():
    """Example 8: Same mode, different frequencies."""
    print("Example 8: PSK31 at Different Frequencies")
    print("-" * 50)

    text = "FREQ TEST"

    frequencies = [500, 1000, 1500, 2000]

    print(f"Generating PSK31 at {len(frequencies)} different frequencies")

    for freq in frequencies:
        psk = PSK31(frequency=freq)
        audio = psk.modulate(text)

        filename = f"psk31_freq{freq}hz.wav"
        save_wav(filename, audio, sample_rate=psk.sample_rate)
        print(f"  {freq} Hz -> {filename}")

    print()


def main():
    """Run all examples."""
    print("=" * 50)
    print("PSK Modem Examples")
    print("=" * 50)
    print()

    examples = [
        ("Basic PSK31", example1_psk31_basic),
        ("PSK63 Fast Mode", example2_psk63),
        ("PSK125 High Speed", example3_psk125),
        ("Mode Comparison", example4_mode_comparison),
        ("Special Characters", example5_special_characters),
        ("Long Preamble", example6_long_preamble),
        ("Custom Baud Rate", example7_custom_baud),
        ("Different Frequencies", example8_different_frequencies),
    ]

    # Run all examples
    for name, func in examples:
        try:
            func()
        except Exception as e:
            print(f"ERROR in {name}: {e}")
            import traceback

            traceback.print_exc()
            print()

    print("=" * 50)
    print("All examples completed!")
    print("=" * 50)
    print("\nGenerated WAV files can be decoded in fldigi:")
    print("1. Open fldigi")
    print("2. Select PSK31/PSK63/PSK125 mode")
    print("3. Op Mode -> PSK -> PSK31 (or appropriate mode)")
    print("4. File -> Audio -> Playback -> [select WAV file]")
    print("5. Watch the decoded text appear!")
    print()


if __name__ == "__main__":
    main()
