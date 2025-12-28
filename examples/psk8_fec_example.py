#!/usr/bin/env python3
"""
8PSK FEC (8-Phase Shift Keying with Forward Error Correction) example.

Demonstrates all 7 8PSK FEC modes with different configurations:
- Standard FEC modes (8PSK125F, 8PSK250F)
- Long interleave FEC modes (8PSK125FL, 8PSK250FL)
- Punctured high-speed modes (8PSK500F, 8PSK1000F, 8PSK1200F)
"""

from pydigi.modems.psk8_fec import (
    PSK8_125F,
    PSK8_125FL,
    PSK8_250F,
    PSK8_250FL,
    PSK8_500F,
    PSK8_1000F,
    PSK8_1200F,
)
from pydigi.utils.audio import save_wav


def example_8psk125f():
    """Example: 8PSK125F - 125 baud with K=16 FEC."""
    print("\n" + "=" * 60)
    print("8PSK125F - 125 baud, K=16 FEC, 1/2 rate")
    print("=" * 60)

    # Create modem
    modem = PSK8_125F()
    print(f"Modem: {modem}")

    # Generate signal
    text = "CQ CQ DE W1ABC W1ABC K"
    print(f"Transmitting: '{text}'")
    audio = modem.modulate(text, frequency=1000)

    # Save to file
    save_wav("8psk125f_example.wav", audio, modem.sample_rate)
    print(f"Saved to: 8psk125f_example.wav")
    print(f"Duration: {len(audio)/modem.sample_rate:.2f} seconds")
    print(f"Data rate: ~188 bits/sec")


def example_8psk125fl():
    """Example: 8PSK125FL - 125 baud with K=13 FEC and long interleave."""
    print("\n" + "=" * 60)
    print("8PSK125FL - 125 baud, K=13 FEC, Long Interleave")
    print("=" * 60)

    # Create modem with long interleave
    modem = PSK8_125FL()
    print(f"Modem: {modem}")

    # Generate signal
    text = "TESTING 8PSK125FL WITH LONG INTERLEAVE"
    print(f"Transmitting: '{text}'")
    audio = modem.modulate(text, frequency=1100)

    # Save to file
    save_wav("8psk125fl_example.wav", audio, modem.sample_rate)
    print(f"Saved to: 8psk125fl_example.wav")
    print(f"Duration: {len(audio)/modem.sample_rate:.2f} seconds")
    print(f"Data rate: ~188 bits/sec")
    print("Note: Long interleave provides better burst error protection")


def example_8psk250f():
    """Example: 8PSK250F - 250 baud with K=16 FEC."""
    print("\n" + "=" * 60)
    print("8PSK250F - 250 baud, K=16 FEC, 1/2 rate")
    print("=" * 60)

    # Create modem
    modem = PSK8_250F()
    print(f"Modem: {modem}")

    # Generate signal
    text = "THE QUICK BROWN FOX JUMPS OVER THE LAZY DOG"
    print(f"Transmitting: '{text}'")
    audio = modem.modulate(text, frequency=1200)

    # Save to file
    save_wav("8psk250f_example.wav", audio, modem.sample_rate)
    print(f"Saved to: 8psk250f_example.wav")
    print(f"Duration: {len(audio)/modem.sample_rate:.2f} seconds")
    print(f"Data rate: ~375 bits/sec")


def example_8psk500f():
    """Example: 8PSK500F - 500 baud with K=13 FEC and puncturing."""
    print("\n" + "=" * 60)
    print("8PSK500F - 500 baud, K=13 FEC, 2/3 rate (punctured)")
    print("=" * 60)

    # Create modem
    modem = PSK8_500F()
    print(f"Modem: {modem}")

    # Generate signal
    text = "8PSK500F USES PUNCTURING FOR HIGHER DATA RATE"
    print(f"Transmitting: '{text}'")
    audio = modem.modulate(text, frequency=1400)

    # Save to file
    save_wav("8psk500f_example.wav", audio, modem.sample_rate)
    print(f"Saved to: 8psk500f_example.wav")
    print(f"Duration: {len(audio)/modem.sample_rate:.2f} seconds")
    print(f"Data rate: ~1000 bits/sec")
    print("Note: Puncturing increases data rate from 1/2 to 2/3")


def example_8psk1000f():
    """Example: 8PSK1000F - 1000 baud with K=13 FEC and puncturing."""
    print("\n" + "=" * 60)
    print("8PSK1000F - 1000 baud, K=13 FEC, 2/3 rate (punctured)")
    print("=" * 60)

    # Create modem
    modem = PSK8_1000F()
    print(f"Modem: {modem}")

    # Generate signal
    text = "HIGH SPEED 8PSK1000F MODE"
    print(f"Transmitting: '{text}'")
    audio = modem.modulate(text, frequency=1500)

    # Save to file
    save_wav("8psk1000f_example.wav", audio, modem.sample_rate)
    print(f"Saved to: 8psk1000f_example.wav")
    print(f"Duration: {len(audio)/modem.sample_rate:.2f} seconds")
    print(f"Data rate: ~2000 bits/sec")


def example_comparison():
    """Example: Compare all 8PSK FEC modes."""
    print("\n" + "=" * 60)
    print("8PSK FEC Mode Comparison")
    print("=" * 60)

    modes = [
        (PSK8_125F(), "8PSK125F", 1000, "~188 bits/sec"),
        (PSK8_125FL(), "8PSK125FL", 1050, "~188 bits/sec (long IL)"),
        (PSK8_250F(), "8PSK250F", 1100, "~375 bits/sec"),
        (PSK8_250FL(), "8PSK250FL", 1150, "~375 bits/sec (long IL)"),
        (PSK8_500F(), "8PSK500F", 1200, "~1000 bits/sec"),
        (PSK8_1000F(), "8PSK1000F", 1250, "~2000 bits/sec"),
        (PSK8_1200F(), "8PSK1200F", 1300, "~2400 bits/sec"),
    ]

    text = "8PSK FEC TEST"

    print(f"\nTransmitting '{text}' on all modes:")
    print(f"{'Mode':<15} {'Freq':<8} {'Data Rate':<25} {'Duration'}")
    print("-" * 60)

    for modem, name, freq, rate in modes:
        audio = modem.modulate(text, frequency=freq)
        duration = len(audio) / modem.sample_rate
        print(f"{name:<15} {freq:<8} {rate:<25} {duration:.2f}s")

    print("\nAll modes use:")
    print("- Gray-mapped 8PSK constellation")
    print("- Convolutional FEC (K=13 or K=16)")
    print("- Bit-level interleaving")
    print("- MFSK/ARQ varicode")


def main():
    """Run all examples."""
    print("\n" + "=" * 60)
    print("8PSK FEC Examples")
    print("=" * 60)

    example_8psk125f()
    example_8psk125fl()
    example_8psk250f()
    example_8psk500f()
    example_8psk1000f()
    example_comparison()

    print("\n" + "=" * 60)
    print("All examples complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
