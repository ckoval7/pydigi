"""
MFSK Extended Modes Examples

This script demonstrates the MFSK Extended modes including:
- MFSK4: 32 tones, 3.90625 baud (very slow, extreme weak signal)
- MFSK11: 16 tones, 10.77 baud (11025 Hz sample rate)
- MFSK22: 16 tones, 21.53 baud (11025 Hz sample rate)
- MFSK31: 8 tones, 31.25 baud (narrow bandwidth)
- MFSK64L: 16 tones, 62.5 baud (long interleave for multipath)
- MFSK128L: 16 tones, 125 baud (very long interleave)

These modes extend the base MFSK implementation with different tone counts,
sample rates, and interleaving depths for various propagation conditions.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pydigi import (
    MFSK4,
    MFSK11,
    MFSK22,
    MFSK31,
    MFSK64L,
    MFSK128L,
    MFSK16,
    MFSK64,
    MFSK128,  # Include base modes for comparison
    save_wav,
)


def example_1_mfsk4():
    """Example 1: MFSK4 - Extreme weak signal mode."""
    print("\n=== Example 1: MFSK4 - Extreme Weak Signal ===")
    print("MFSK4 mode (32 tones, 3.90625 baud)")
    print("Very slow mode for extreme weak signal conditions")

    modem = MFSK4()
    text = "MFSK4 WEAK"  # Keep short - very slow!

    audio = modem.modulate(text, frequency=1000)

    filename = "examples/mfsk4_weaksignal.wav"
    save_wav(filename, audio, modem.sample_rate)

    duration = len(audio) / modem.sample_rate
    print(f"Generated: {filename}")
    print(f"Duration: {duration:.2f}s")
    print(f"Baud rate: {modem.baud_rate:.5f} baud")
    print(f"Number of tones: {modem.numtones}")
    print(f"Bandwidth: {modem.bandwidth:.2f} Hz")


def example_2_mfsk11():
    """Example 2: MFSK11 - 11025 Hz sample rate mode."""
    print("\n=== Example 2: MFSK11 - 11025 Hz Sample Rate ===")
    print("MFSK11 mode (16 tones, 10.77 baud, 11025 Hz)")
    print("Uses 11025 Hz sample rate for sound card compatibility")

    modem = MFSK11()
    text = "MFSK11 TEST MESSAGE"

    audio = modem.modulate(text, frequency=1000)

    filename = "examples/mfsk11_11khz.wav"
    save_wav(filename, audio, modem.sample_rate)

    duration = len(audio) / modem.sample_rate
    print(f"Generated: {filename}")
    print(f"Duration: {duration:.2f}s")
    print(f"Sample rate: {modem.sample_rate} Hz")
    print(f"Baud rate: {modem.baud_rate:.5f} baud")
    print(f"Tone spacing: {modem.tonespacing:.5f} Hz")


def example_3_mfsk22():
    """Example 3: MFSK22 - Faster 11025 Hz mode."""
    print("\n=== Example 3: MFSK22 - Faster 11025 Hz Mode ===")
    print("MFSK22 mode (16 tones, 21.53 baud, 11025 Hz)")
    print("Faster mode still using 11025 Hz sample rate")

    modem = MFSK22()
    text = "MFSK22 FASTER MODE TEST"

    audio = modem.modulate(text, frequency=1000)

    filename = "examples/mfsk22_fast_11khz.wav"
    save_wav(filename, audio, modem.sample_rate)

    duration = len(audio) / modem.sample_rate
    print(f"Generated: {filename}")
    print(f"Duration: {duration:.2f}s")
    print(f"Sample rate: {modem.sample_rate} Hz")
    print(f"Baud rate: {modem.baud_rate:.5f} baud")


def example_4_mfsk31():
    """Example 4: MFSK31 - Narrow bandwidth mode."""
    print("\n=== Example 4: MFSK31 - Narrow Bandwidth ===")
    print("MFSK31 mode (8 tones, 31.25 baud)")
    print("Uses only 8 tones for reduced bandwidth")

    modem = MFSK31()
    text = "MFSK31 NARROW BAND MODE"

    audio = modem.modulate(text, frequency=1000)

    filename = "examples/mfsk31_narrowband.wav"
    save_wav(filename, audio, modem.sample_rate)

    duration = len(audio) / modem.sample_rate
    print(f"Generated: {filename}")
    print(f"Duration: {duration:.2f}s")
    print(f"Number of tones: {modem.numtones}")
    print(f"Baud rate: {modem.baud_rate:.5f} baud")
    print(f"Bandwidth: {modem.bandwidth:.2f} Hz")


def example_5_mfsk64l():
    """Example 5: MFSK64L - Long interleave for multipath."""
    print("\n=== Example 5: MFSK64L - Long Interleave ===")
    print("MFSK64L mode (16 tones, 62.5 baud, depth=400)")
    print("Very long interleave for extreme multipath conditions")
    print("Preamble: 2500 symbols (vs 180 for MFSK64)")

    modem = MFSK64L()
    text = "MFSK64L MULTIPATH"

    audio = modem.modulate(text, frequency=1000)

    filename = "examples/mfsk64l_longinterleave.wav"
    save_wav(filename, audio, modem.sample_rate)

    duration = len(audio) / modem.sample_rate
    print(f"Generated: {filename}")
    print(f"Duration: {duration:.2f}s")
    print(f"Interleave depth: {modem.depth}")
    print(f"Preamble symbols: {modem.default_preamble}")
    print(f"Baud rate: {modem.baud_rate:.5f} baud")


def example_6_mfsk128l():
    """Example 6: MFSK128L - Very long interleave."""
    print("\n=== Example 6: MFSK128L - Very Long Interleave ===")
    print("MFSK128L mode (16 tones, 125 baud, depth=800)")
    print("Extremely long interleave for severe multipath")
    print("Preamble: 5000 symbols (vs 214 for MFSK128)")

    modem = MFSK128L()
    text = "MFSK128L"  # Keep short due to very long preamble!

    audio = modem.modulate(text, frequency=1000)

    filename = "examples/mfsk128l_verylonginterleave.wav"
    save_wav(filename, audio, modem.sample_rate)

    duration = len(audio) / modem.sample_rate
    print(f"Generated: {filename}")
    print(f"Duration: {duration:.2f}s")
    print(f"Interleave depth: {modem.depth}")
    print(f"Preamble symbols: {modem.default_preamble}")
    print(f"Baud rate: {modem.baud_rate:.5f} baud")


def example_7_mode_comparison():
    """Example 7: Compare all MFSK extended modes."""
    print("\n=== Example 7: Extended Mode Comparison ===")
    print("Comparing all MFSK extended modes with same text")

    text = "TEST"  # Short text for comparison
    modes = [
        ("MFSK4", MFSK4()),
        ("MFSK11", MFSK11()),
        ("MFSK22", MFSK22()),
        ("MFSK31", MFSK31()),
        ("MFSK64L", MFSK64L()),
        ("MFSK128L", MFSK128L()),
    ]

    print(f"\nText: '{text}'")
    print(f"{'Mode':<12} {'Duration':>10} {'Samples':>10} {'Baud':>10} " f"{'Tones':>6} {'SR':>6}")
    print("-" * 70)

    for name, modem in modes:
        audio = modem.modulate(text, frequency=1000)
        filename = f"examples/{name.lower()}_comparison.wav"
        save_wav(filename, audio, modem.sample_rate)

        duration = len(audio) / modem.sample_rate
        print(
            f"{name:<12} {duration:>9.2f}s {len(audio):>10d} "
            f"{modem.baud_rate:>9.4f} {modem.numtones:>6d} "
            f"{modem.sample_rate:>6d}"
        )


def example_8_interleave_comparison():
    """Example 8: Compare normal vs long interleave modes."""
    print("\n=== Example 8: Interleave Depth Comparison ===")
    print("Comparing normal vs long interleave modes")

    text = "INTERLEAVE TEST"
    comparisons = [
        ("MFSK64", MFSK64(), "MFSK64L", MFSK64L()),
        ("MFSK128", MFSK128(), "MFSK128L", MFSK128L()),
    ]

    for name1, modem1, name2, modem2 in comparisons:
        print(f"\n{name1} vs {name2}:")

        # Normal mode
        audio1 = modem1.modulate(text, frequency=1000)
        duration1 = len(audio1) / modem1.sample_rate
        print(
            f"  {name1:9s}: depth={modem1.depth:>3d}, preamble={modem1.default_preamble:>4d}, "
            f"duration={duration1:>7.2f}s"
        )

        # Long mode
        audio2 = modem2.modulate(text, frequency=1000)
        duration2 = len(audio2) / modem2.sample_rate
        print(
            f"  {name2:9s}: depth={modem2.depth:>3d}, preamble={modem2.default_preamble:>4d}, "
            f"duration={duration2:>7.2f}s"
        )

        print(f"  Ratio: {duration2/duration1:.2f}x longer (for multipath resistance)")


def example_9_tone_count_comparison():
    """Example 9: Compare different tone counts."""
    print("\n=== Example 9: Tone Count Comparison ===")
    print("Comparing modes with different numbers of tones")

    text = "TONES"
    modes = [
        ("MFSK31", MFSK31(), "8 tones (narrow)"),
        ("MFSK16", MFSK16(), "16 tones (standard)"),
        ("MFSK4", MFSK4(), "32 tones (wide)"),
    ]

    print(f"\n{'Mode':<12} {'Tones':>6} {'Bandwidth':>12} {'Description'}")
    print("-" * 70)

    for name, modem, desc in modes:
        audio = modem.modulate(text, frequency=1000)
        print(f"{name:<12} {modem.numtones:>6d} {modem.bandwidth:>10.2f} Hz  {desc}")


def example_10_all_modes():
    """Example 10: Generate files for all MFSK extended modes."""
    print("\n=== Example 10: All Extended Modes ===")
    print("Generating WAV files for all MFSK extended modes")

    text = "CQ CQ CQ DE W1ABC K"
    modes = [
        ("MFSK4", MFSK4()),
        ("MFSK11", MFSK11()),
        ("MFSK22", MFSK22()),
        ("MFSK31", MFSK31()),
        ("MFSK64L", MFSK64L()),
        ("MFSK128L", MFSK128L()),
    ]

    for name, modem in modes:
        audio = modem.modulate(text, frequency=1000)
        filename = f"examples/{name.lower()}_test.wav"
        save_wav(filename, audio, modem.sample_rate)

        duration = len(audio) / modem.sample_rate
        print(f"  {name:<10s}: {filename:<40s} ({duration:>6.2f}s)")


def main():
    """Run all MFSK extended mode examples."""
    print("=" * 70)
    print("MFSK Extended Modes Examples")
    print("=" * 70)
    print("\nNew modes: MFSK4, MFSK11, MFSK22, MFSK31, MFSK64L, MFSK128L")

    # Create examples directory if it doesn't exist
    os.makedirs("examples", exist_ok=True)

    examples = [
        example_1_mfsk4,
        example_2_mfsk11,
        example_3_mfsk22,
        example_4_mfsk31,
        example_5_mfsk64l,
        example_6_mfsk128l,
        example_7_mode_comparison,
        example_8_interleave_comparison,
        example_9_tone_count_comparison,
        example_10_all_modes,
    ]

    for example in examples:
        example()

    print("\n" + "=" * 70)
    print("All MFSK extended examples completed!")
    print("WAV files saved to examples/ directory")
    print("Test these files in fldigi to verify correct decoding")
    print("=" * 70)


if __name__ == "__main__":
    main()
