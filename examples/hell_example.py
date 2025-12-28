#!/usr/bin/env python3
"""
Example usage of Hellschreiber modems.

Demonstrates all 7 Hell modes:
- FeldHell (original)
- SlowHell
- HellX5 (5x faster)
- HellX9 (9x faster)
- FSKHell245 (FSK mode, 245 baud)
- FSKHell105 (FSK mode, 105 baud)
- Hell80 (80 column mode)
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pydigi.modems.hell import FeldHell, SlowHell, HellX5, HellX9, FSKHell245, FSKHell105, Hell80
from pydigi.utils.audio import save_wav


def example_feldhell():
    """Generate FeldHell (original Hellschreiber) transmission."""
    print("\n=== FeldHell (Original) ===")
    print("Column rate: 17.5 col/sec")
    print("Modulation: Amplitude (ON/OFF keying)")
    print("Bandwidth: ~245 Hz")

    modem = FeldHell(frequency=1000.0)
    text = "HELLO WORLD"
    audio = modem.modulate(text)

    filename = "hell_feldhell.wav"
    save_wav(filename, audio, modem.sample_rate)
    print(f"Saved: {filename}")
    print(f"Duration: {len(audio) / modem.sample_rate:.2f} seconds")


def example_slowhell():
    """Generate SlowHell transmission."""
    print("\n=== SlowHell ===")
    print("Column rate: 2.1875 col/sec (8x slower)")
    print("Modulation: Amplitude (ON/OFF keying)")
    print("Bandwidth: ~30 Hz")

    modem = SlowHell(frequency=1000.0)
    text = "SLOW"
    audio = modem.modulate(text)

    filename = "hell_slowhell.wav"
    save_wav(filename, audio, modem.sample_rate)
    print(f"Saved: {filename}")
    print(f"Duration: {len(audio) / modem.sample_rate:.2f} seconds")


def example_hellx5():
    """Generate HellX5 transmission."""
    print("\n=== HellX5 ===")
    print("Column rate: 87.5 col/sec (5x faster)")
    print("Modulation: Amplitude (ON/OFF keying)")
    print("Bandwidth: ~1225 Hz")

    modem = HellX5(frequency=1500.0)
    text = "HELLX5 FAST"
    audio = modem.modulate(text)

    filename = "hell_hellx5.wav"
    save_wav(filename, audio, modem.sample_rate)
    print(f"Saved: {filename}")
    print(f"Duration: {len(audio) / modem.sample_rate:.2f} seconds")


def example_hellx9():
    """Generate HellX9 transmission."""
    print("\n=== HellX9 ===")
    print("Column rate: 157.5 col/sec (9x faster)")
    print("Modulation: Amplitude (ON/OFF keying)")
    print("Bandwidth: ~2205 Hz")

    modem = HellX9(frequency=2000.0)
    text = "X9 FASTEST"
    audio = modem.modulate(text)

    filename = "hell_hellx9.wav"
    save_wav(filename, audio, modem.sample_rate)
    print(f"Saved: {filename}")
    print(f"Duration: {len(audio) / modem.sample_rate:.2f} seconds")


def example_fskh245():
    """Generate FSKHell245 transmission."""
    print("\n=== FSKHell245 ===")
    print("Column rate: 17.5 col/sec")
    print("Modulation: FSK (Frequency Shift Keying)")
    print("Bandwidth: 122.5 Hz (245 baud)")

    modem = FSKHell245(frequency=1000.0)
    text = "FSK HELL 245"
    audio = modem.modulate(text)

    filename = "hell_fskh245.wav"
    save_wav(filename, audio, modem.sample_rate)
    print(f"Saved: {filename}")
    print(f"Duration: {len(audio) / modem.sample_rate:.2f} seconds")


def example_fskh105():
    """Generate FSKHell105 transmission."""
    print("\n=== FSKHell105 ===")
    print("Column rate: 17.5 col/sec")
    print("Modulation: FSK (Frequency Shift Keying)")
    print("Bandwidth: 55 Hz (105 baud)")

    modem = FSKHell105(frequency=1000.0)
    text = "FSK 105"
    audio = modem.modulate(text)

    filename = "hell_fskh105.wav"
    save_wav(filename, audio, modem.sample_rate)
    print(f"Saved: {filename}")
    print(f"Duration: {len(audio) / modem.sample_rate:.2f} seconds")


def example_hell80():
    """Generate Hell80 transmission."""
    print("\n=== Hell80 ===")
    print("Column rate: 35 col/sec (80 column mode)")
    print("Modulation: FSK (Frequency Shift Keying)")
    print("Bandwidth: 300 Hz")

    modem = Hell80(frequency=1500.0)
    text = "HELL 80 COLUMN MODE"
    audio = modem.modulate(text)

    filename = "hell_hell80.wav"
    save_wav(filename, audio, modem.sample_rate)
    print(f"Saved: {filename}")
    print(f"Duration: {len(audio) / modem.sample_rate:.2f} seconds")


def example_all_modes_comparison():
    """Generate a file with all modes for comparison."""
    print("\n=== All Modes Comparison ===")
    print("Generating single file with all modes...")

    test_text = "TEST"
    all_audio = []

    modes = [
        ("FeldHell", FeldHell),
        ("SlowHell", SlowHell),
        ("HellX5", HellX5),
        ("HellX9", HellX9),
        ("FSKHell245", FSKHell245),
        ("FSKHell105", FSKHell105),
        ("Hell80", Hell80),
    ]

    for name, modem_class in modes:
        modem = modem_class(frequency=1500.0)
        audio = modem.modulate(test_text)
        all_audio.extend(audio)
        # Add silence between modes
        silence = [0.0] * int(modem.sample_rate * 0.5)
        all_audio.extend(silence)

    import numpy as np

    all_audio = np.array(all_audio, dtype=np.float64)

    filename = "hell_all_modes.wav"
    save_wav(filename, all_audio, 8000.0)
    print(f"Saved: {filename}")
    print(f"Total duration: {len(all_audio) / 8000.0:.2f} seconds")


def example_pulse_shaping():
    """Demonstrate different pulse shaping options (AM modes only)."""
    print("\n=== Pulse Shaping Comparison (FeldHell) ===")
    print("Comparing different rise times...")

    text = "SHAPING"
    shaping_modes = [
        (0, "slow 4ms", "hell_shaping_slow.wav"),
        (1, "medium 2ms", "hell_shaping_medium.wav"),
        (2, "fast 1ms", "hell_shaping_fast.wav"),
        (3, "square wave", "hell_shaping_square.wav"),
    ]

    for shaping, desc, filename in shaping_modes:
        modem = FeldHell(frequency=1000.0, pulse_shaping=shaping)
        audio = modem.modulate(text)
        save_wav(filename, audio, modem.sample_rate)
        print(f"  {desc:15s} -> {filename}")


def example_column_width():
    """Demonstrate column width parameter (wider characters)."""
    print("\n=== Column Width Comparison ===")
    print("Wider columns = easier to read, slower transmission")

    text = "WIDTH"
    widths = [1, 2, 3, 4]

    for width in widths:
        modem = FeldHell(frequency=1000.0, column_width=width)
        audio = modem.modulate(text)
        filename = f"hell_width_{width}.wav"
        save_wav(filename, audio, modem.sample_rate)
        duration = len(audio) / modem.sample_rate
        print(f"  Width {width}: {filename} ({duration:.2f} sec)")


def main():
    """Run all examples."""
    print("Hellschreiber Modem Examples")
    print("=" * 60)

    # Generate individual mode examples
    example_feldhell()
    example_slowhell()
    example_hellx5()
    example_hellx9()
    example_fskh245()
    example_fskh105()
    example_hell80()

    # Generate comparison examples
    example_all_modes_comparison()
    example_pulse_shaping()
    example_column_width()

    print("\n" + "=" * 60)
    print("All examples complete!")
    print("\nGenerated WAV files can be decoded using fldigi or other")
    print("Hellschreiber decoder software.")
    print("\nNote: Hellschreiber is a 'facsimile' mode - characters are")
    print("painted visually on the screen rather than decoded as text.")


if __name__ == "__main__":
    main()
