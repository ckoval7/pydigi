#!/usr/bin/env python3
"""
Example usage of QPSK and 8PSK modems.

Demonstrates:
- QPSK31, QPSK63, QPSK125 modes
- 8PSK125, 8PSK250, 8PSK500 modes
- Generating WAV files
- Comparing throughput across modes
"""

import sys

sys.path.insert(0, "/home/corey/pydigi")

from pydigi import QPSK31, QPSK63, QPSK125, PSK8_125, PSK8_250, PSK8_500, save_wav


def example_1_qpsk31_basic():
    """Example 1: Basic QPSK31 transmission."""
    print("Example 1: QPSK31 (basic test)")

    qpsk31 = QPSK31(frequency=1000)
    text = "CQ CQ CQ DE W1ABC K"

    audio = qpsk31.modulate(text)
    duration = len(audio) / 8000

    save_wav("examples/qpsk31_basic.wav", audio, 8000)

    print(f"  Mode: QPSK31 (31.25 baud)")
    print(f"  Text: {text}")
    print(f"  Samples: {len(audio)}")
    print(f"  Duration: {duration:.2f}s")
    print(f"  File: examples/qpsk31_basic.wav")
    print()


def example_2_qpsk63():
    """Example 2: QPSK63 (faster mode)."""
    print("Example 2: QPSK63 (faster mode)")

    qpsk63 = QPSK63(frequency=1500)
    text = "QPSK63 TEST MESSAGE"

    audio = qpsk63.modulate(text)
    duration = len(audio) / 8000

    save_wav("examples/qpsk63_test.wav", audio, 8000)

    print(f"  Mode: QPSK63 (62.5 baud)")
    print(f"  Text: {text}")
    print(f"  Samples: {len(audio)}")
    print(f"  Duration: {duration:.2f}s")
    print(f"  File: examples/qpsk63_test.wav")
    print()


def example_3_qpsk125():
    """Example 3: QPSK125 (high-speed mode)."""
    print("Example 3: QPSK125 (high-speed mode)")

    qpsk125 = QPSK125(frequency=1000)
    text = "FAST QPSK125 MESSAGE"

    audio = qpsk125.modulate(text)
    duration = len(audio) / 8000

    save_wav("examples/qpsk125_test.wav", audio, 8000)

    print(f"  Mode: QPSK125 (125 baud)")
    print(f"  Text: {text}")
    print(f"  Samples: {len(audio)}")
    print(f"  Duration: {duration:.2f}s")
    print(f"  File: examples/qpsk125_test.wav")
    print()


def example_4_8psk125():
    """Example 4: 8PSK125 (3 bits/symbol)."""
    print("Example 4: 8PSK125 (basic test)")

    psk8 = PSK8_125(frequency=1000)
    text = "8PSK125 TEST DE W1ABC"

    audio = psk8.modulate(text)
    duration = len(audio) / 8000

    save_wav("examples/8psk125_basic.wav", audio, 8000)

    print(f"  Mode: 8PSK125 (125 baud, 375 bps)")
    print(f"  Text: {text}")
    print(f"  Samples: {len(audio)}")
    print(f"  Duration: {duration:.2f}s")
    print(f"  File: examples/8psk125_basic.wav")
    print()


def example_5_8psk250():
    """Example 5: 8PSK250 (faster 8PSK)."""
    print("Example 5: 8PSK250 (faster mode)")

    psk8 = PSK8_250(frequency=1500)
    text = "FASTER 8PSK250 MODE"

    audio = psk8.modulate(text)
    duration = len(audio) / 8000

    save_wav("examples/8psk250_test.wav", audio, 8000)

    print(f"  Mode: 8PSK250 (250 baud, 750 bps)")
    print(f"  Text: {text}")
    print(f"  Samples: {len(audio)}")
    print(f"  Duration: {duration:.2f}s")
    print(f"  File: examples/8psk250_test.wav")
    print()


def example_6_8psk500():
    """Example 6: 8PSK500 (high-speed)."""
    print("Example 6: 8PSK500 (high-speed mode)")

    psk8 = PSK8_500(frequency=1000)
    text = "HIGH SPEED 8PSK500"

    audio = psk8.modulate(text)
    duration = len(audio) / 8000

    save_wav("examples/8psk500_test.wav", audio, 8000)

    print(f"  Mode: 8PSK500 (500 baud, 1500 bps)")
    print(f"  Text: {text}")
    print(f"  Samples: {len(audio)}")
    print(f"  Duration: {duration:.2f}s")
    print(f"  File: examples/8psk500_test.wav")
    print()


def example_7_comparison():
    """Example 7: Mode comparison with same text."""
    print("Example 7: Mode comparison (same text)")

    text = "THE QUICK BROWN FOX JUMPS OVER THE LAZY DOG"

    modes = [
        (QPSK31(frequency=1000), "qpsk31_compare.wav"),
        (QPSK63(frequency=1000), "qpsk63_compare.wav"),
        (QPSK125(frequency=1000), "qpsk125_compare.wav"),
        (PSK8_125(frequency=1000), "8psk125_compare.wav"),
        (PSK8_250(frequency=1000), "8psk250_compare.wav"),
        (PSK8_500(frequency=1000), "8psk500_compare.wav"),
    ]

    print(f"  Text: {text}\n")

    for modem, filename in modes:
        audio = modem.modulate(text)
        duration = len(audio) / 8000
        save_wav(f"examples/{filename}", audio, 8000)
        print(f"  {modem.mode_name:12s}: {duration:5.2f}s, {len(audio):6d} samples")

    print()


def example_8_special_chars():
    """Example 8: Special characters and punctuation."""
    print("Example 8: Special characters in QPSK31 and 8PSK125")

    text = "HELLO! TEST? 123 @#$%"

    # QPSK31
    qpsk31 = QPSK31(frequency=1000)
    audio_qpsk = qpsk31.modulate(text)
    save_wav("examples/qpsk31_special.wav", audio_qpsk, 8000)

    # 8PSK125
    psk8 = PSK8_125(frequency=1500)
    audio_8psk = psk8.modulate(text)
    save_wav("examples/8psk125_special.wav", audio_8psk, 8000)

    print(f"  Text: {text}")
    print(f"  QPSK31:  {len(audio_qpsk)} samples, examples/qpsk31_special.wav")
    print(f"  8PSK125: {len(audio_8psk)} samples, examples/8psk125_special.wav")
    print()


def example_9_multiple_frequencies():
    """Example 9: Multiple frequencies (for multi-channel testing)."""
    print("Example 9: Multiple frequencies (QPSK31)")

    text = "CHANNEL"
    frequencies = [800, 1000, 1200, 1400, 1600]

    qpsk31 = QPSK31()

    for i, freq in enumerate(frequencies):
        audio = qpsk31.modulate(text, frequency=freq)
        filename = f"examples/qpsk31_freq_{freq}hz.wav"
        save_wav(filename, audio, 8000)
        print(f"  Ch{i+1}: {freq}Hz -> {filename}")

    print()


def main():
    """Run all examples."""
    print("=" * 60)
    print("QPSK and 8PSK Modem Examples")
    print("=" * 60)
    print()

    example_1_qpsk31_basic()
    example_2_qpsk63()
    example_3_qpsk125()
    example_4_8psk125()
    example_5_8psk250()
    example_6_8psk500()
    example_7_comparison()
    example_8_special_chars()
    example_9_multiple_frequencies()

    print("=" * 60)
    print("All examples complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
