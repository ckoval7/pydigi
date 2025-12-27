"""
MFSK Modem Examples

This script demonstrates the MFSK (Multiple Frequency Shift Keying) modem
implementation with various modes and configurations.

MFSK uses multiple frequency tones with FEC (Viterbi encoding) and interleaving
for reliable data transmission.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from pydigi import MFSK16, MFSK32, MFSK64, MFSK8, save_wav


def example_1_basic_mfsk16():
    """Example 1: Basic MFSK16 transmission."""
    print("\n=== Example 1: Basic MFSK16 ===")
    print("Standard MFSK16 mode (16 tones, 15.625 baud, ~1000 Hz center)")

    modem = MFSK16()
    text = "CQ CQ CQ DE W1ABC W1ABC K"

    # Generate signal
    audio = modem.modulate(text, frequency=1000)

    # Save to file
    filename = "examples/mfsk16_basic.wav"
    save_wav(filename, audio, modem.sample_rate)

    duration = len(audio) / modem.sample_rate
    print(f"Generated: {filename}")
    print(f"Duration: {duration:.2f}s")
    print(f"Sample count: {len(audio)}")
    print(f"Baud rate: {modem.baud_rate:.4f} baud")
    print(f"Tone spacing: {modem.tonespacing:.4f} Hz")
    print(f"Bandwidth: {modem.bandwidth:.2f} Hz")


def example_2_mfsk32():
    """Example 2: MFSK32 - Faster mode."""
    print("\n=== Example 2: MFSK32 - Faster Mode ===")
    print("MFSK32 mode (16 tones, 31.25 baud, ~500 Hz center)")

    modem = MFSK32()
    text = "TESTING MFSK32 - TWICE THE SPEED!"

    audio = modem.modulate(text, frequency=1000)

    filename = "examples/mfsk32_fast.wav"
    save_wav(filename, audio, modem.sample_rate)

    duration = len(audio) / modem.sample_rate
    print(f"Generated: {filename}")
    print(f"Duration: {duration:.2f}s")
    print(f"Baud rate: {modem.baud_rate:.4f} baud")


def example_3_mfsk64():
    """Example 3: MFSK64 - High speed mode."""
    print("\n=== Example 3: MFSK64 - High Speed ===")
    print("MFSK64 mode (16 tones, 62.5 baud)")

    modem = MFSK64()
    text = "MFSK64 HIGH SPEED TEST 123"

    audio = modem.modulate(text, frequency=1500)

    filename = "examples/mfsk64_highspeed.wav"
    save_wav(filename, audio, modem.sample_rate)

    duration = len(audio) / modem.sample_rate
    print(f"Generated: {filename}")
    print(f"Duration: {duration:.2f}s")
    print(f"Baud rate: {modem.baud_rate:.4f} baud")


def example_4_mfsk8():
    """Example 4: MFSK8 - More tones, slower."""
    print("\n=== Example 4: MFSK8 - More Tones ===")
    print("MFSK8 mode (32 tones, 7.8125 baud)")

    modem = MFSK8()
    text = "MFSK8 WEAK SIGNAL MODE"

    audio = modem.modulate(text, frequency=1000)

    filename = "examples/mfsk8_weaksignal.wav"
    save_wav(filename, audio, modem.sample_rate)

    duration = len(audio) / modem.sample_rate
    print(f"Generated: {filename}")
    print(f"Duration: {duration:.2f}s")
    print(f"Number of tones: {modem.numtones}")
    print(f"Baud rate: {modem.baud_rate:.4f} baud")


def example_5_mode_comparison():
    """Example 5: Mode comparison - same text, different modes."""
    print("\n=== Example 5: Mode Comparison ===")
    print("Comparing MFSK8, MFSK16, MFSK32, and MFSK64")

    text = "HELLO WORLD"
    modes = [
        ("MFSK8", MFSK8()),
        ("MFSK16", MFSK16()),
        ("MFSK32", MFSK32()),
        ("MFSK64", MFSK64()),
    ]

    for name, modem in modes:
        audio = modem.modulate(text, frequency=1000)
        filename = f"examples/{name.lower()}_comparison.wav"
        save_wav(filename, audio, modem.sample_rate)

        duration = len(audio) / modem.sample_rate
        print(f"{name:8s}: {duration:6.2f}s, {len(audio):6d} samples, "
              f"{modem.baud_rate:7.4f} baud")


def example_6_special_characters():
    """Example 6: Special characters and numbers."""
    print("\n=== Example 6: Special Characters ===")

    modem = MFSK16()
    text = "CALL: W1ABC/M GRID: FN42 QTH: BOSTON, MA 73!"

    audio = modem.modulate(text, frequency=1000)

    filename = "examples/mfsk16_special_chars.wav"
    save_wav(filename, audio, modem.sample_rate)

    duration = len(audio) / modem.sample_rate
    print(f"Generated: {filename}")
    print(f"Duration: {duration:.2f}s")
    print(f"Text: {text}")


def example_7_long_preamble():
    """Example 7: Extended preamble for better sync."""
    print("\n=== Example 7: Extended Preamble ===")

    modem = MFSK16()
    text = "TESTING LONG PREAMBLE"

    # Use 200 symbol preamble (default is 107)
    audio = modem.modulate(text, frequency=1000, preamble=200)

    filename = "examples/mfsk16_long_preamble.wav"
    save_wav(filename, audio, modem.sample_rate)

    duration = len(audio) / modem.sample_rate
    print(f"Generated: {filename}")
    print(f"Duration: {duration:.2f}s")
    print(f"Preamble: 200 symbols")


def example_8_multiple_frequencies():
    """Example 8: Multiple transmissions at different frequencies."""
    print("\n=== Example 8: Multiple Frequencies ===")

    modem = MFSK16()
    text = "FREQ TEST"
    frequencies = [800, 1000, 1200, 1500, 2000]

    for freq in frequencies:
        audio = modem.modulate(text, frequency=freq)
        filename = f"examples/mfsk16_freq_{freq}hz.wav"
        save_wav(filename, audio, modem.sample_rate)
        print(f"Generated: {filename} at {freq} Hz")


def example_9_long_message():
    """Example 9: Longer message transmission."""
    print("\n=== Example 9: Long Message ===")

    modem = MFSK16()
    text = ("THIS IS A LONGER MESSAGE TO DEMONSTRATE MFSK16 TRANSMISSION. "
            "THE MODEM USES VITERBI FEC AND INTERLEAVING FOR IMPROVED "
            "RELIABILITY. 73 DE W1ABC K")

    audio = modem.modulate(text, frequency=1000)

    filename = "examples/mfsk16_long_message.wav"
    save_wav(filename, audio, modem.sample_rate)

    duration = len(audio) / modem.sample_rate
    chars = len(text)
    cps = chars / duration
    print(f"Generated: {filename}")
    print(f"Duration: {duration:.2f}s")
    print(f"Characters: {chars}")
    print(f"Speed: {cps:.2f} characters/second")


def main():
    """Run all MFSK examples."""
    print("=" * 70)
    print("MFSK Modem Examples")
    print("=" * 70)

    # Create examples directory if it doesn't exist
    os.makedirs("examples", exist_ok=True)

    examples = [
        example_1_basic_mfsk16,
        example_2_mfsk32,
        example_3_mfsk64,
        example_4_mfsk8,
        example_5_mode_comparison,
        example_6_special_characters,
        example_7_long_preamble,
        example_8_multiple_frequencies,
        example_9_long_message,
    ]

    for example in examples:
        example()

    print("\n" + "=" * 70)
    print("All MFSK examples completed!")
    print("=" * 70)


if __name__ == "__main__":
    main()
