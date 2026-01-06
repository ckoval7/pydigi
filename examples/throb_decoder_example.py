#!/usr/bin/env python3
"""
Throb Decoder Examples

This script demonstrates the Throb decoder functionality with various test scenarios.

The Throb decoder can receive and decode all six Throb modes:
- Throb1, Throb2, Throb4 (9 tones, 45 characters)
- ThrobX1, ThrobX2, ThrobX4 (11 tones, 55 characters)

Reference: fldigi/src/throb/throb.cxx
"""

from pydigi import (
    Throb1, Throb2, Throb4, ThrobX1, ThrobX2, ThrobX4,
)
from pydigi.modems.throb_decoder import (
    Throb1Decoder, Throb2Decoder, Throb4Decoder,
    ThrobX1Decoder, ThrobX2Decoder, ThrobX4Decoder,
)
import numpy as np


def example1_basic_loopback():
    """Example 1: Basic encode-decode loopback."""
    print("Example 1: Basic Loopback Test")
    print("-" * 50)

    message = "HELLO WORLD"

    # Encode
    encoder = Throb1()
    audio = encoder.modulate(message)

    # Decode
    decoder = Throb1Decoder()
    decoded = decoder.process(audio)

    print(f"  Transmitted: {message}")
    print(f"  Received:    {decoded}")
    print(f"  SNR:         {decoder.get_snr():.1f} dB")
    print(f"  Metric:      {decoder.get_metric():.2f}")
    print()


def example2_all_modes():
    """Example 2: Test all six Throb modes."""
    print("Example 2: All Throb Modes")
    print("-" * 50)

    message = "TEST 123"

    modes = [
        ("Throb1", Throb1, Throb1Decoder),
        ("Throb2", Throb2, Throb2Decoder),
        ("Throb4", Throb4, Throb4Decoder),
        ("ThrobX1", ThrobX1, ThrobX1Decoder),
        ("ThrobX2", ThrobX2, ThrobX2Decoder),
        ("ThrobX4", ThrobX4, ThrobX4Decoder),
    ]

    for mode_name, encoder_func, decoder_func in modes:
        # Encode
        encoder = encoder_func()
        audio = encoder.modulate(message)

        # Decode
        decoder = decoder_func()
        decoded = decoder.process(audio)

        print(f"  {mode_name:8s}: '{decoded}' (SNR: {decoder.get_snr():.1f} dB)")

    print()


def example3_with_noise():
    """Example 3: Decode with added noise."""
    print("Example 3: Decoding with Noise")
    print("-" * 50)

    message = "CQ CQ DE TEST"

    # SNR levels to test
    snr_levels = [20, 10, 5]

    for target_snr in snr_levels:
        # Encode
        encoder = Throb2()
        audio = encoder.modulate(message)

        # Add noise to achieve target SNR
        signal_power = np.var(audio)
        noise_power = signal_power / (10 ** (target_snr / 10.0))
        noise = np.random.normal(0, np.sqrt(noise_power), len(audio))
        noisy_audio = audio + noise

        # Decode
        decoder = Throb2Decoder()
        decoded = decoder.process(noisy_audio)

        # Calculate accuracy
        accuracy = sum(1 for a, b in zip(message, decoded) if a == b) / len(message) * 100

        print(f"  SNR {target_snr:2d} dB: '{decoded[:len(message)]}'")
        print(f"            Measured SNR: {decoder.get_snr():.1f} dB")
        print(f"            Accuracy:     {accuracy:.1f}%")
        print()


def example4_callback():
    """Example 4: Using character callback."""
    print("Example 4: Character Callback")
    print("-" * 50)

    message = "CALLBACK TEST"
    received_chars = []

    def char_callback(char):
        """Called for each decoded character."""
        received_chars.append(char)
        print(f"  Received: '{char}'")

    # Encode
    encoder = Throb1()
    audio = encoder.modulate(message)

    # Decode with callback
    decoder = Throb1Decoder(text_callback=char_callback)
    decoder.process(audio)

    print(f"\n  Full message: {''.join(received_chars)}")
    print()


def example5_frequency_offset():
    """Example 5: Decoder with frequency offset (AFC test)."""
    print("Example 5: Frequency Offset & AFC")
    print("-" * 50)

    message = "AFC TEST"

    # Encode at one frequency
    encoder = Throb4()
    encoder.frequency = 1500
    audio = encoder.modulate(message)

    # Try different frequency offsets
    offsets = [0, 5, 10, 20]

    for offset in offsets:
        # Decode at different frequency
        decoder = Throb4Decoder(frequency=1500 + offset, use_afc=True)
        decoded = decoder.process(audio)

        print(f"  Offset +{offset:2d} Hz: '{decoded}' (Final freq: {decoder.frequency:.1f} Hz)")

    print()


def example6_special_characters():
    """Example 6: Special character decoding."""
    print("Example 6: Special Characters")
    print("-" * 50)

    # Throb special characters (using shift codes)
    throb_messages = [
        "TEST?",      # Question mark
        "HELLO@ALL",  # At symbol (@ is special in Throb)
    ]

    print("  Throb special characters:")
    for message in throb_messages:
        encoder = Throb1()
        audio = encoder.modulate(message)

        decoder = Throb1Decoder()
        decoded = decoder.process(audio)

        print(f"    Sent: '{message}' -> Received: '{decoded}'")

    # ThrobX extended characters (no shift codes needed)
    throbx_messages = [
        "TEST: #@",
        "HELLO + WORLD",
        "A=B; C-D",
    ]

    print("\n  ThrobX extended characters:")
    for message in throbx_messages:
        encoder = ThrobX1()
        audio = encoder.modulate(message)

        decoder = ThrobX1Decoder()
        decoded = decoder.process(audio)

        print(f"    Sent: '{message}' -> Received: '{decoded}'")

    print()


def example7_squelch():
    """Example 7: Squelch functionality."""
    print("Example 7: Squelch Control")
    print("-" * 50)

    message = "SQUELCH TEST"

    # Encode
    encoder = Throb1()
    audio = encoder.modulate(message)

    # Add heavy noise
    signal_power = np.var(audio)
    noise_power = signal_power * 10.0  # Very low SNR
    noise = np.random.normal(0, np.sqrt(noise_power), len(audio))
    noisy_audio = audio + noise

    # Decode with squelch disabled
    decoder1 = Throb1Decoder()
    decoder1.squelch_enabled = False
    decoded1 = decoder1.process(noisy_audio)

    # Decode with squelch enabled (high threshold)
    decoder2 = Throb1Decoder()
    decoder2.squelch = 20.0
    decoder2.squelch_enabled = True
    decoded2 = decoder2.process(noisy_audio)

    print(f"  Heavy noise added (very low SNR)")
    print(f"  Without squelch: '{decoded1}' ({len(decoded1)} chars)")
    print(f"  With squelch:    '{decoded2}' ({len(decoded2)} chars)")
    print(f"  Measured SNR:    {decoder1.get_snr():.1f} dB")
    print()


def example8_snr_measurement():
    """Example 8: SNR measurement across modes."""
    print("Example 8: SNR Measurement")
    print("-" * 50)

    message = "SNR TEST"

    modes = [
        ("Throb1", Throb1, Throb1Decoder),
        ("Throb4", Throb4, Throb4Decoder),
        ("ThrobX1", ThrobX1, ThrobX1Decoder),
    ]

    print(f"  Clean signal (no noise):")
    for mode_name, encoder_func, decoder_func in modes:
        encoder = encoder_func()
        audio = encoder.modulate(message)

        decoder = decoder_func()
        decoded = decoder.process(audio)

        print(f"    {mode_name:8s}: SNR = {decoder.get_snr():.1f} dB, Metric = {decoder.get_metric():.2f}")

    print()


def example9_long_message():
    """Example 9: Long message decoding."""
    print("Example 9: Long Message")
    print("-" * 50)

    message = "THE QUICK BROWN FOX JUMPS OVER THE LAZY DOG 0123456789"

    # Use faster mode for long messages
    encoder = ThrobX2()
    audio = encoder.modulate(message)

    decoder = ThrobX2Decoder()
    decoded = decoder.process(audio)

    # Calculate accuracy
    min_len = min(len(message), len(decoded))
    correct = sum(1 for i in range(min_len) if message[i] == decoded[i])
    accuracy = correct / len(message) * 100

    print(f"  Sent:     {message}")
    print(f"  Received: {decoded}")
    print(f"  Length:   {len(decoded)} chars")
    print(f"  Accuracy: {accuracy:.1f}%")
    print()


def example10_reset_decoder():
    """Example 10: Decoder reset between transmissions."""
    print("Example 10: Decoder Reset")
    print("-" * 50)

    decoder = Throb2Decoder()
    encoder = Throb2()

    # First transmission
    message1 = "FIRST MSG"
    audio1 = encoder.modulate(message1)
    decoded1 = decoder.process(audio1)

    print(f"  Transmission 1: '{decoded1}'")

    # Reset decoder
    decoder.reset()

    # Second transmission
    message2 = "SECOND MSG"
    audio2 = encoder.modulate(message2)
    decoded2 = decoder.process(audio2)

    print(f"  Transmission 2: '{decoded2}'")
    print()


if __name__ == "__main__":
    print("=" * 70)
    print("Throb Decoder Examples")
    print("=" * 70)
    print()

    example1_basic_loopback()
    example2_all_modes()
    example3_with_noise()
    example4_callback()
    example5_frequency_offset()
    example6_special_characters()
    example7_squelch()
    example8_snr_measurement()
    example9_long_message()
    example10_reset_decoder()

    print("=" * 70)
    print("All decoder examples completed successfully!")
    print("=" * 70)
