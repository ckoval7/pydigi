#!/usr/bin/env python3
"""
8PSK FEC Silence Demo - Demonstrates leading/trailing silence for better decoding.

This example shows how to use leading and trailing silence with 8PSK FEC modes
to improve decoder synchronization, especially important when using virtual audio
cables or when signals are being looped/repeated.

The garbage characters you may have seen at the start of each transmission are
caused by the decoder trying to decode before it has fully synchronized. Adding
leading and trailing silence gives the decoder time to:
1. Detect the carrier (DCD - Data Carrier Detect)
2. Establish symbol timing
3. Train the equalizer
4. Synchronize the FEC decoder
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import numpy as np
from pydigi.modems.psk8_fec import EightPSKFEC


def demo_no_silence():
    """Generate 8PSK250F without silence padding."""
    print("=" * 70)
    print("Demo 1: WITHOUT Silence Padding")
    print("=" * 70)

    modem = EightPSKFEC(
        baud=250,
        sample_rate=8000,
        frequency=1000,
        tx_amplitude=0.5,
    )

    audio = modem.modulate("This is a test message for 8PSK250F.")

    duration = len(audio) / modem.sample_rate
    print(f"Mode: {modem.mode_name}")
    print(f"Audio duration: {duration:.2f} seconds")
    print(f"Leading silence: 0.0s")
    print(f"Trailing silence: 0.0s")
    print()
    print("⚠ When decoded by fldigi over virtual audio cable:")
    print("   - May show garbage characters at the start")
    print("   - Decoder needs time to synchronize")
    print("   - First few characters might be lost")
    print()

    return audio


def demo_with_silence():
    """Generate 8PSK250F with silence padding (RECOMMENDED)."""
    print("=" * 70)
    print("Demo 2: WITH Silence Padding (RECOMMENDED)")
    print("=" * 70)

    modem = EightPSKFEC(
        baud=250,
        sample_rate=8000,
        frequency=1000,
        tx_amplitude=0.5,
        leading_silence=0.5,   # 500ms before signal starts
        trailing_silence=1.0,  # 1 second after signal ends
    )

    audio = modem.modulate("This is a test message for 8PSK250F.")

    duration = len(audio) / modem.sample_rate
    print(f"Mode: {modem.mode_name}")
    print(f"Audio duration: {duration:.2f} seconds")
    print(f"Leading silence: {modem.leading_silence}s")
    print(f"Trailing silence: {modem.trailing_silence}s")
    print()
    print("✓ Benefits:")
    print("   - Leading silence gives decoder time to detect carrier")
    print("   - Trailing silence ensures complete decode before next message")
    print("   - Greatly reduces garbage characters at start")
    print("   - Better for looping audio or repeated transmissions")
    print()

    return audio


def demo_runtime_override():
    """Demonstrate overriding silence at modulation time."""
    print("=" * 70)
    print("Demo 3: Runtime Override of Silence Parameters")
    print("=" * 70)

    # Create modem with default silence
    modem = EightPSKFEC(
        baud=250,
        sample_rate=8000,
        frequency=1000,
        leading_silence=0.5,
        trailing_silence=1.0,
    )

    print("Default silence settings:")
    print(f"  Leading: {modem.leading_silence}s, Trailing: {modem.trailing_silence}s")
    print()

    # Override for a specific message (e.g., shorter for file storage)
    audio1 = modem.modulate(
        "Short message",
        leading_silence=0.1,
        trailing_silence=0.1
    )

    duration1 = len(audio1) / modem.sample_rate
    print(f"Message 1 (with overrides): {duration1:.2f}s (0.1s lead, 0.1s trail)")
    print()

    # Use defaults for another message (e.g., for live transmission)
    audio2 = modem.modulate("Another message")

    duration2 = len(audio2) / modem.sample_rate
    print(f"Message 2 (using defaults): {duration2:.2f}s (0.5s lead, 1.0s trail)")
    print()

    return audio1, audio2


def main():
    """Run all demos."""
    print("\n")
    print("╔" + "═" * 68 + "╗")
    print("║" + " " * 15 + "8PSK FEC Silence Padding Demo" + " " * 24 + "║")
    print("╚" + "═" * 68 + "╝")
    print()

    # Demo 1: No silence
    audio1 = demo_no_silence()

    # Demo 2: With silence (recommended)
    audio2 = demo_with_silence()

    # Demo 3: Runtime override
    audio3a, audio3b = demo_runtime_override()

    print("=" * 70)
    print("Recommendations for Virtual Audio Cable Testing:")
    print("=" * 70)
    print()
    print("1. Use leading_silence=0.5 or higher")
    print("   - Gives fldigi time to detect carrier and sync")
    print("2. Use trailing_silence=1.0 or higher")
    print("   - Ensures complete decode before next message")
    print("3. For looped audio, use even longer trailing silence (1.5-2.0s)")
    print("   - Prevents overlap between repeated messages")
    print()
    print("Example for looped playback:")
    print("    modem = EightPSKFEC(")
    print("        baud=250,")
    print("        leading_silence=0.5,")
    print("        trailing_silence=2.0,  # Extra time between loops")
    print("    )")
    print()
    print("The garbage characters you see are NORMAL during the preamble/sync phase.")
    print("Silence padding minimizes them by giving the decoder adequate setup time.")
    print()


if __name__ == "__main__":
    main()
