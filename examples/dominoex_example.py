#!/usr/bin/env python3
"""
DominoEX Example - Demonstrate all 9 DominoEX modes

This script generates example WAV files for all DominoEX modes from Micro to 88 baud.
DominoEX is an Incremental Frequency Keying (IFK) mode that's very robust to
frequency drift and multi-path propagation.

Author: PyDigi Project
Date: 2025-12-15
"""

from pydigi.modems.dominoex import (
    DominoEX,
    DominoEX_Micro,
    DominoEX_4,
    DominoEX_5,
    DominoEX_8,
    DominoEX_11,
    DominoEX_16,
    DominoEX_22,
    DominoEX_44,
    DominoEX_88,
)
from pydigi.utils.audio import save_wav


def example1_dominoex8_basic():
    """Example 1: Basic DominoEX 8 transmission"""
    print("Example 1: DominoEX 8 - Basic transmission")

    text = "CQ CQ CQ DE W1ABC W1ABC K"

    # Generate audio using convenience function
    audio = DominoEX_8(text, frequency=1500, sample_rate=8000)

    # Save to WAV file
    filename = "examples/dominoex_8_basic.wav"
    save_wav(filename, audio, 8000)

    print(f"  Generated: {filename}")
    print(f"  Duration: {len(audio)/8000:.2f} seconds")
    print(f"  Samples: {len(audio)}")
    print()


def example2_dominoex16_standard():
    """Example 2: DominoEX 16 - Standard mode (most popular)"""
    print("Example 2: DominoEX 16 - Standard mode")

    text = "HELLO WORLD! This is DominoEX 16, the standard mode."

    audio = DominoEX_16(text, frequency=1500, sample_rate=8000)

    filename = "examples/dominoex_16_standard.wav"
    save_wav(filename, audio, 8000)

    print(f"  Generated: {filename}")
    print(f"  Duration: {len(audio)/8000:.2f} seconds")
    print()


def example3_dominoex_micro():
    """Example 3: DominoEX Micro - Ultra-slow weak signal mode"""
    print("Example 3: DominoEX Micro - Ultra-slow weak signal")

    text = "QRP"  # Short message for ultra-slow mode

    audio = DominoEX_Micro(text, frequency=1500, sample_rate=8000)

    filename = "examples/dominoex_micro.wav"
    save_wav(filename, audio, 8000)

    print(f"  Generated: {filename}")
    print(f"  Duration: {len(audio)/8000:.2f} seconds")
    print(f"  Baud rate: ~2.0 baud (ultra-slow!)")
    print()


def example4_dominoex22():
    """Example 4: DominoEX 22 - Medium-fast mode"""
    print("Example 4: DominoEX 22 - Medium-fast mode")

    text = "The quick brown fox jumps over the lazy dog."

    audio = DominoEX_22(text, frequency=1500, sample_rate=11025)

    filename = "examples/dominoex_22_medfast.wav"
    save_wav(filename, audio, 11025)

    print(f"  Generated: {filename}")
    print(f"  Duration: {len(audio)/11025:.2f} seconds")
    print(f"  Sample rate: 11025 Hz")
    print()


def example5_mode_comparison():
    """Example 5: Speed comparison - Same text in different modes"""
    print("Example 5: Mode comparison - Same text, different speeds")

    text = "TEST"

    modes = [
        ("Micro", DominoEX_Micro, 8000, "~2.0 baud"),
        ("4", DominoEX_4, 8000, "~3.9 baud"),
        ("8", DominoEX_8, 8000, "~7.8 baud"),
        ("16", DominoEX_16, 8000, "~15.6 baud"),
        ("22", DominoEX_22, 11025, "~21.5 baud"),
        ("44", DominoEX_44, 11025, "~43.1 baud"),
    ]

    for name, func, sr, desc in modes:
        audio = func(text, frequency=1500, sample_rate=sr)
        filename = f"examples/dominoex_{name}_test.wav"
        save_wav(filename, audio, sr)
        duration = len(audio) / sr
        print(f"  DominoEX {name:5s}: {duration:6.2f}s  ({desc})")

    print()


def example6_special_characters():
    """Example 6: Special characters and punctuation"""
    print("Example 6: Special characters and punctuation")

    text = "CALL: W1ABC/P, QTH: Grid FN42, 73!"

    audio = DominoEX_16(text, frequency=1500, sample_rate=8000)

    filename = "examples/dominoex_16_special.wav"
    save_wav(filename, audio, 8000)

    print(f"  Generated: {filename}")
    print(f"  Text: {text}")
    print()


def example7_frequency_comparison():
    """Example 7: Different frequencies"""
    print("Example 7: Different carrier frequencies")

    text = "FREQ TEST"

    frequencies = [800, 1200, 1500, 2000, 2500]

    for freq in frequencies:
        audio = DominoEX_16(text, frequency=freq, sample_rate=8000)
        filename = f"examples/dominoex_16_freq{freq}.wav"
        save_wav(filename, audio, 8000)
        print(f"  Generated @ {freq} Hz: {filename}")

    print()


def example8_all_modes():
    """Example 8: Generate samples for all 9 modes"""
    print("Example 8: All 9 DominoEX modes")

    text = "DominoEX Test"

    modes = [
        ("Micro", DominoEX_Micro, 8000),
        ("4", DominoEX_4, 8000),
        ("5", DominoEX_5, 11025),
        ("8", DominoEX_8, 8000),
        ("11", DominoEX_11, 11025),
        ("16", DominoEX_16, 8000),
        ("22", DominoEX_22, 11025),
        ("44", DominoEX_44, 11025),
        ("88", DominoEX_88, 11025),
    ]

    for name, func, sr in modes:
        audio = func(text, frequency=1500, sample_rate=sr)
        filename = f"examples/dominoex_all_{name}.wav"
        save_wav(filename, audio, sr)
        duration = len(audio) / sr
        print(f"  DominoEX {name:5s}: {duration:6.2f}s, {len(audio):7d} samples @ {sr} Hz")

    print()


def example9_duration_estimation():
    """Example 9: Duration estimation"""
    print("Example 9: Duration estimation vs actual")

    text = "HELLO WORLD"

    modem = DominoEX(symlen=512, doublespaced=1, sample_rate=8000)
    estimated = modem.estimate_duration(text, mode_micro=False)
    audio = modem.modulate(text, frequency=1500, sample_rate=8000)
    actual = len(audio) / 8000

    print(f"  Text: '{text}'")
    print(f"  Estimated: {estimated:.2f} seconds")
    print(f"  Actual: {actual:.2f} seconds")
    print(f"  Error: {abs(estimated - actual):.2f} seconds")
    print()


def example10_long_message():
    """Example 10: Longer message test"""
    print("Example 10: Longer message (DominoEX 22)")

    text = """CQ CQ CQ DE W1ABC W1ABC W1ABC
This is a test of DominoEX digital mode.
Operating on 20 meters. Weather is sunny.
Signal report 599. QSL via bureau.
73 and best DX!"""

    audio = DominoEX_22(text, frequency=1500, sample_rate=11025)

    filename = "examples/dominoex_22_long.wav"
    save_wav(filename, audio, 11025)

    print(f"  Generated: {filename}")
    print(f"  Duration: {len(audio)/11025:.2f} seconds")
    print(f"  Characters: {len(text)}")
    print()


if __name__ == "__main__":
    print("=" * 60)
    print("DominoEX Modem Examples")
    print("=" * 60)
    print()

    example1_dominoex8_basic()
    example2_dominoex16_standard()
    example3_dominoex_micro()
    example4_dominoex22()
    example5_mode_comparison()
    example6_special_characters()
    example7_frequency_comparison()
    example8_all_modes()
    example9_duration_estimation()
    example10_long_message()

    print("=" * 60)
    print("All examples complete!")
    print("=" * 60)
