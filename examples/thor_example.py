"""
Thor MFSK Modem Examples

Demonstrates all 15 Thor modes with various test scenarios.

Thor uses 18-tone MFSK with incremental frequency keying, Viterbi FEC,
and interleaving for robust HF communications.

Reference: fldigi/src/thor/thor.cxx
"""

import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from pydigi import (
    ThorMicro, Thor4, Thor5, Thor8, Thor11, Thor16, Thor22,
    Thor25, Thor32, Thor44, Thor56, Thor25x4, Thor50x1, Thor50x2, Thor100,
    save_wav
)


def example1_thor16_basic():
    """Example 1: Basic Thor16 test (most popular mode)"""
    print("\n=== Example 1: Thor16 Basic ===")

    thor = Thor16()
    text = "CQ CQ CQ DE W1ABC W1ABC K"

    print(f"Mode: Thor16")
    print(f"Sample rate: {thor.samplerate} Hz")
    print(f"Symbol length: {thor.symlen} samples")
    print(f"Baud rate: {thor.baud_rate:.2f} symbols/sec")
    print(f"Tone spacing: {thor.tonespacing:.2f} Hz")
    print(f"Bandwidth: {thor.bandwidth:.2f} Hz")
    print(f"Text: {text}")

    audio = thor.modulate(text, frequency=1500)
    duration = thor.estimate_duration(text)

    print(f"Generated {len(audio)} samples ({len(audio)/thor.samplerate:.2f}s)")
    print(f"Estimated duration: {duration:.2f}s")

    save_wav("thor16_basic.wav", audio, thor.samplerate)
    print("Saved: thor16_basic.wav")


def example2_thor_modes_comparison():
    """Example 2: Compare different Thor modes (8kHz sample rate)"""
    print("\n=== Example 2: Thor Modes Comparison (8kHz) ===")

    text = "HELLO WORLD"
    modes = [
        ("Thor Micro", ThorMicro()),
        ("Thor 4", Thor4()),
        ("Thor 8", Thor8()),
        ("Thor 16", Thor16()),
        ("Thor 32", Thor32()),
    ]

    for name, modem in modes:
        audio = modem.modulate(text, frequency=1500)
        duration = len(audio) / modem.samplerate

        print(f"\n{name}:")
        print(f"  Baud: {modem.baud_rate:.2f} symbols/sec")
        print(f"  Bandwidth: {modem.bandwidth:.2f} Hz")
        print(f"  Duration: {duration:.2f}s")
        print(f"  Samples: {len(audio)}")

        filename = f"thor_{name.lower().replace(' ', '')}_test.wav"
        save_wav(filename, audio, modem.samplerate)
        print(f"  Saved: {filename}")


def example3_thor_11khz_modes():
    """Example 3: Thor modes with 11.025 kHz sample rate"""
    print("\n=== Example 3: Thor 11.025kHz Modes ===")

    text = "THE QUICK BROWN FOX"
    modes = [
        ("Thor 5", Thor5()),
        ("Thor 11", Thor11()),
        ("Thor 22", Thor22()),
        ("Thor 44", Thor44()),
    ]

    for name, modem in modes:
        audio = modem.modulate(text, frequency=1500)
        duration = len(audio) / modem.samplerate

        print(f"\n{name}:")
        print(f"  Sample rate: {modem.samplerate} Hz")
        print(f"  Baud: {modem.baud_rate:.2f} symbols/sec")
        print(f"  Duration: {duration:.2f}s")

        filename = f"thor{name.split()[-1]}_11khz.wav"
        save_wav(filename, audio, modem.samplerate)
        print(f"  Saved: {filename}")


def example4_thor_high_speed_k15():
    """Example 4: High-speed modes using K=15 encoder"""
    print("\n=== Example 4: High-Speed K=15 Modes ===")

    text = "TESTING K15 ENCODER"
    modes = [
        ("Thor 25", Thor25()),
        ("Thor 50x1", Thor50x1()),
        ("Thor 50x2", Thor50x2()),
        ("Thor 100", Thor100()),
    ]

    print("These modes use IEEE K=15 encoder for improved FEC")
    for name, modem in modes:
        audio = modem.modulate(text, frequency=1500)
        duration = len(audio) / modem.samplerate

        print(f"\n{name}:")
        print(f"  Encoder: K=15 (IEEE)")
        print(f"  Interleave depth: {modem.interleave_depth}")
        print(f"  Baud: {modem.baud_rate:.2f} symbols/sec")
        print(f"  Duration: {duration:.2f}s")

        filename = f"thor{name.split()[-1].replace('x', '_')}_k15.wav"
        save_wav(filename, audio, modem.samplerate)
        print(f"  Saved: {filename}")


def example5_thor_multicarrier():
    """Example 5: Multi-carrier modes (Thor 25x4, Thor 50x2)"""
    print("\n=== Example 5: Multi-Carrier Modes ===")

    text = "MULTICARRIER TEST 123"

    # Thor 25x4 - 4x tone spacing
    print("\nThor 25x4 (4-carrier, 2-second interleave):")
    thor = Thor25x4()
    audio = thor.modulate(text, frequency=1500)
    duration = len(audio) / thor.samplerate

    print(f"  Doublespaced: {thor.doublespaced}x")
    print(f"  Bandwidth: {thor.bandwidth:.2f} Hz")
    print(f"  Interleave: {thor.interleave_depth} (2 seconds)")
    print(f"  Duration: {duration:.2f}s")

    save_wav("thor_25x4_multicarrier.wav", audio, thor.samplerate)
    print("  Saved: thor_25x4_multicarrier.wav")

    # Thor 50x2 - 2x tone spacing
    print("\nThor 50x2 (2-carrier, 1-second interleave):")
    thor = Thor50x2()
    audio = thor.modulate(text, frequency=1500)
    duration = len(audio) / thor.samplerate

    print(f"  Doublespaced: {thor.doublespaced}x")
    print(f"  Bandwidth: {thor.bandwidth:.2f} Hz")
    print(f"  Interleave: {thor.interleave_depth} (1 second)")
    print(f"  Duration: {duration:.2f}s")

    save_wav("thor_50x2_multicarrier.wav", audio, thor.samplerate)
    print("  Saved: thor_50x2_multicarrier.wav")


def example6_thor56_16khz():
    """Example 6: Thor 56 - highest speed mode at 16kHz"""
    print("\n=== Example 6: Thor56 (16kHz) ===")

    text = "FASTEST THOR MODE"
    thor = Thor56()

    print(f"Sample rate: {thor.samplerate} Hz (highest for Thor)")
    print(f"Baud rate: {thor.baud_rate:.2f} symbols/sec")
    print(f"Bandwidth: {thor.bandwidth:.2f} Hz")

    audio = thor.modulate(text, frequency=1500)
    duration = len(audio) / thor.samplerate

    print(f"Duration: {duration:.2f}s")
    print(f"Samples: {len(audio)}")

    save_wav("thor56_16khz.wav", audio, thor.samplerate)
    print("Saved: thor56_16khz.wav")


def example7_thor_special_chars():
    """Example 7: Special characters and numbers"""
    print("\n=== Example 7: Special Characters ===")

    thor = Thor16()
    text = "HELLO! TEST #123 @ 7.150 MHz :)"

    print(f"Text with special chars: {text}")
    audio = thor.modulate(text, frequency=1500)
    duration = len(audio) / thor.samplerate

    print(f"Duration: {duration:.2f}s")

    save_wav("thor16_special.wav", audio, thor.samplerate)
    print("Saved: thor16_special.wav")


def example8_thor_frequencies():
    """Example 8: Different center frequencies"""
    print("\n=== Example 8: Different Frequencies ===")

    thor = Thor16()
    text = "FREQ TEST"
    frequencies = [1000, 1500, 2000]

    for freq in frequencies:
        audio = thor.modulate(text, frequency=freq)
        filename = f"thor16_{freq}hz.wav"

        print(f"\nFrequency: {freq} Hz")
        print(f"Bandwidth: {thor.bandwidth:.2f} Hz")
        print(f"Range: {freq - thor.bandwidth/2:.1f} - {freq + thor.bandwidth/2:.1f} Hz")
        print(f"Saved: {filename}")

        save_wav(filename, audio, thor.samplerate)


def example9_thor_secondary_chars():
    """Example 9: Using secondary character set"""
    print("\n=== Example 9: Secondary Character Set ===")

    thor = Thor16()
    text = "Testing secondary set"

    print("Primary character set (MFSK varicode):")
    audio_primary = thor.modulate(text, frequency=1500, use_secondary=False)
    print(f"  Duration: {len(audio_primary)/thor.samplerate:.2f}s")
    save_wav("thor16_primary.wav", audio_primary, thor.samplerate)
    print("  Saved: thor16_primary.wav")

    print("\nSecondary character set (12-bit codes):")
    audio_secondary = thor.modulate(text, frequency=1500, use_secondary=True)
    print(f"  Duration: {len(audio_secondary)/thor.samplerate:.2f}s")
    save_wav("thor16_secondary.wav", audio_secondary, thor.samplerate)
    print("  Saved: thor16_secondary.wav")


def example10_all_thor_modes():
    """Example 10: Generate test files for all 15 Thor modes"""
    print("\n=== Example 10: All 15 Thor Modes ===")

    text = "THOR"
    modes = [
        ("Micro", ThorMicro()),
        ("4", Thor4()),
        ("5", Thor5()),
        ("8", Thor8()),
        ("11", Thor11()),
        ("16", Thor16()),
        ("22", Thor22()),
        ("25", Thor25()),
        ("32", Thor32()),
        ("44", Thor44()),
        ("56", Thor56()),
        ("25x4", Thor25x4()),
        ("50x1", Thor50x1()),
        ("50x2", Thor50x2()),
        ("100", Thor100()),
    ]

    print(f"Generating test files for all Thor modes...")
    print(f"Text: '{text}'")

    for name, modem in modes:
        audio = modem.modulate(text, frequency=1500)
        duration = len(audio) / modem.samplerate

        filename = f"thor_all_{name.replace('x', '_')}.wav"
        save_wav(filename, audio, modem.samplerate)

        print(f"  Thor {name:6s}: {modem.baud_rate:6.2f} baud, "
              f"{duration:6.2f}s, {modem.samplerate:5d} Hz - {filename}")


def main():
    """Run all Thor examples"""
    print("=" * 70)
    print("Thor MFSK Modem Examples")
    print("=" * 70)
    print("\nThor is a robust MFSK mode using:")
    print("- 18 tones with Incremental Frequency Keying (IFK)")
    print("- Viterbi FEC (K=7 or K=15)")
    print("- Variable interleaving for time diversity")
    print("- Highly resistant to frequency drift and multipath")

    # Run all examples
    example1_thor16_basic()
    example2_thor_modes_comparison()
    example3_thor_11khz_modes()
    example4_thor_high_speed_k15()
    example5_thor_multicarrier()
    example6_thor56_16khz()
    example7_thor_special_chars()
    example8_thor_frequencies()
    example9_thor_secondary_chars()
    example10_all_thor_modes()

    print("\n" + "=" * 70)
    print("All Thor examples completed!")
    print("=" * 70)
    print("\nGenerated WAV files can be decoded in fldigi.")
    print("Modes summary:")
    print("  8kHz:  Micro, 4, 8, 16, 25, 32, 25x4, 50x1, 50x2, 100")
    print("  11kHz: 5, 11, 22, 44")
    print("  16kHz: 56")
    print("  K=15:  25, 25x4, 50x1, 50x2, 100 (high-speed modes)")


if __name__ == "__main__":
    main()
