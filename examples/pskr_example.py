#!/usr/bin/env python3
"""
PSK-R (Robust) modes example.

Demonstrates multi-carrier PSK-R modes with FEC and interleaving.
PSK-R adds robustness through convolutional encoding (K=7) and bit interleaving.
"""

import numpy as np
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from pydigi.modems.psk_extended import (
    MultiCarrierPSKR,
    PSKR_12X_PSK125R,
    PSKR_4X_PSK125R,
    PSKR_2X_PSK250R,
    PSKR_2X_PSK500R,
    PSKR_2X_PSK1000R,
)


def save_wav(filename, audio, sample_rate=8000):
    """Save audio to WAV file."""
    try:
        from scipy.io import wavfile

        # Normalize to 16-bit PCM range
        audio_16bit = np.int16(audio * 32767)
        wavfile.write(filename, sample_rate, audio_16bit)
        print(f"Saved: {filename}")
    except ImportError:
        print("scipy not available, skipping WAV file save")


def example_12x_psk125r():
    """Example: 12X_PSK125R - 12 carriers at 125 baud with PSK-R."""
    print("\n" + "=" * 70)
    print("12X_PSK125R Example")
    print("=" * 70)
    print("Configuration:")
    print("  - 12 carriers @ 125 baud each")
    print("  - FEC: Convolutional K=7 (POLY1=0x6d, POLY2=0x4f)")
    print("  - Interleaving: 2x2x160")
    print("  - Varicode: MFSK (no delimiters)")
    print("  - Center frequency: 1500 Hz")

    # Create modem
    modem = PSKR_12X_PSK125R(frequency=1500)
    print(f"\nModem: {modem}")

    # Modulate text
    text = "CQ CQ DE W1AW W1AW PSK-R TEST"
    print(f"Text: '{text}'")

    audio = modem.modulate(text)
    print(f"Audio samples: {len(audio)}")
    print(f"Duration: {len(audio) / 8000:.2f} seconds")
    print(f"Peak amplitude: {np.max(np.abs(audio)):.3f}")

    # Save to WAV
    save_wav("output_12x_psk125r.wav", audio)

    return audio


def example_4x_psk125r():
    """Example: 4X_PSK125R - 4 carriers at 125 baud with PSK-R."""
    print("\n" + "=" * 70)
    print("4X_PSK125R Example")
    print("=" * 70)
    print("Configuration:")
    print("  - 4 carriers @ 125 baud each")
    print("  - FEC: Convolutional K=7")
    print("  - Interleaving: 2x2x80")
    print("  - Center frequency: 1500 Hz")

    modem = PSKR_4X_PSK125R(frequency=1500)
    print(f"\nModem: {modem}")

    text = "ROBUST PSK TEST"
    print(f"Text: '{text}'")

    audio = modem.modulate(text)
    print(f"Audio samples: {len(audio)}")
    print(f"Duration: {len(audio) / 8000:.2f} seconds")

    save_wav("output_4x_psk125r.wav", audio)

    return audio


def example_2x_psk250r():
    """Example: 2X_PSK250R - 2 carriers at 250 baud with PSK-R."""
    print("\n" + "=" * 70)
    print("2X_PSK250R Example")
    print("=" * 70)
    print("Configuration:")
    print("  - 2 carriers @ 250 baud each")
    print("  - FEC: Convolutional K=7")
    print("  - Interleaving: 2x2x160")
    print("  - Center frequency: 1500 Hz")

    modem = PSKR_2X_PSK250R(frequency=1500)
    print(f"\nModem: {modem}")

    text = "FAST ROBUST MODE"
    print(f"Text: '{text}'")

    audio = modem.modulate(text)
    print(f"Audio samples: {len(audio)}")
    print(f"Duration: {len(audio) / 8000:.2f} seconds")

    save_wav("output_2x_psk250r.wav", audio)

    return audio


def example_2x_psk500r():
    """Example: 2X_PSK500R - 2 carriers at 500 baud with PSK-R."""
    print("\n" + "=" * 70)
    print("2X_PSK500R Example")
    print("=" * 70)
    print("Configuration:")
    print("  - 2 carriers @ 500 baud each")
    print("  - FEC: Convolutional K=7")
    print("  - Interleaving: 2x2x160")
    print("  - Center frequency: 1500 Hz")

    modem = PSKR_2X_PSK500R(frequency=1500)
    print(f"\nModem: {modem}")

    text = "HIGH SPEED ROBUST"
    print(f"Text: '{text}'")

    audio = modem.modulate(text)
    print(f"Audio samples: {len(audio)}")
    print(f"Duration: {len(audio) / 8000:.2f} seconds")

    save_wav("output_2x_psk500r.wav", audio)

    return audio


def example_custom_pskr():
    """Example: Custom PSK-R configuration."""
    print("\n" + "=" * 70)
    print("Custom PSK-R Example")
    print("=" * 70)
    print("Configuration:")
    print("  - 6 carriers @ 250 baud each")
    print("  - FEC: Convolutional K=7")
    print("  - Interleaving: 2x2x160")
    print("  - Separation: 1.4")
    print("  - Center frequency: 1800 Hz")

    # Create custom configuration
    modem = MultiCarrierPSKR(
        num_carriers=6,
        baud=250,
        interleave_depth=160,
        separation=1.4,
        frequency=1800,
        tx_amplitude=0.8,
    )
    print(f"\nModem: {modem}")

    text = "CUSTOM PSK-R CONFIG"
    print(f"Text: '{text}'")

    audio = modem.modulate(text)
    print(f"Audio samples: {len(audio)}")
    print(f"Duration: {len(audio) / 8000:.2f} seconds")

    # Print carrier frequencies
    print("\nCarrier frequencies:")
    for i, freq in enumerate(modem._carrier_freqs):
        print(f"  Carrier {i}: {freq:.2f} Hz")

    save_wav("output_custom_pskr.wav", audio)

    return audio


def example_comparison():
    """Compare regular multi-carrier PSK vs PSK-R."""
    print("\n" + "=" * 70)
    print("PSK vs PSK-R Comparison")
    print("=" * 70)

    from pydigi.modems.psk_extended import MultiCarrierPSK

    text = "COMPARE"

    # Regular multi-carrier PSK (no FEC, no interleaving)
    print("\n1. Regular 2X_PSK500 (no FEC):")
    psk = MultiCarrierPSK(num_carriers=2, baud=500, frequency=1500)
    audio_psk = psk.modulate(text)
    print(f"   Duration: {len(audio_psk) / 8000:.2f} seconds")
    print(f"   Samples: {len(audio_psk)}")
    save_wav("output_2x_psk500_regular.wav", audio_psk)

    # PSK-R (with FEC and interleaving)
    print("\n2. 2X_PSK500R (with FEC + interleaving):")
    pskr = PSKR_2X_PSK500R(frequency=1500)
    audio_pskr = pskr.modulate(text)
    print(f"   Duration: {len(audio_pskr) / 8000:.2f} seconds")
    print(f"   Samples: {len(audio_pskr)}")
    save_wav("output_2x_psk500r_robust.wav", audio_pskr)

    # Analysis
    print("\nAnalysis:")
    ratio = len(audio_pskr) / len(audio_psk)
    print(f"  - PSK-R is {ratio:.2f}x longer (due to FEC rate 1/2 + interleaving + preamble)")
    print(f"  - PSK-R provides error correction and burst error protection")
    print(f"  - PSK-R uses MFSK varicode (more compact than PSK varicode)")


def main():
    """Run all examples."""
    print("PyDigi PSK-R (Robust) Modes Examples")
    print("=====================================")
    print("\nPSK-R adds robustness to PSK through:")
    print("  1. Convolutional FEC (K=7, POLY1=0x6d, POLY2=0x4f)")
    print("  2. Bit interleaving (2x2xN) for burst error protection")
    print("  3. MFSK varicode for efficient character encoding")
    print("  4. Multiple parallel carriers for frequency diversity")

    # Run examples
    example_12x_psk125r()
    example_4x_psk125r()
    example_2x_psk250r()
    example_2x_psk500r()
    example_custom_pskr()
    example_comparison()

    print("\n" + "=" * 70)
    print("All examples completed!")
    print("=" * 70)
    print("\nWAV files generated:")
    print("  - output_12x_psk125r.wav")
    print("  - output_4x_psk125r.wav")
    print("  - output_2x_psk250r.wav")
    print("  - output_2x_psk500r.wav")
    print("  - output_custom_pskr.wav")
    print("  - output_2x_psk500_regular.wav (comparison)")
    print("  - output_2x_psk500r_robust.wav (comparison)")
    print("\nThese files can be decoded with fldigi or other PSK-R compatible software.")


if __name__ == "__main__":
    main()
