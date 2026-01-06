#!/usr/bin/env python3
"""
CW Decoder Example

Demonstrates the CW (Morse Code) decoder with various test scenarios:
1. Encoding text to CW audio
2. Decoding the audio back to text
3. Testing with different speeds
4. Adding noise to test robustness
5. Demonstrating adaptive speed tracking

Usage:
    python cw_decoder_example.py
"""

import numpy as np
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from pydigi.modems import CW, CWDecoder


def add_noise(signal, snr_db):
    """
    Add white Gaussian noise to signal.

    Args:
        signal: Input signal
        snr_db: Desired SNR in dB

    Returns:
        Noisy signal
    """
    signal_power = np.mean(signal ** 2)
    noise_power = signal_power / (10 ** (snr_db / 10))
    noise = np.random.normal(0, np.sqrt(noise_power), len(signal))
    return signal + noise


def test_basic_decode():
    """Test basic CW encoding and decoding."""
    print("=" * 60)
    print("Test 1: Basic CW Encode/Decode")
    print("=" * 60)

    # Test message
    message = "HELLO WORLD"
    wpm = 20
    sample_rate = 8000.0
    frequency = 800.0

    print(f"Message: {message}")
    print(f"Speed: {wpm} WPM")
    print(f"Frequency: {frequency} Hz")
    print()

    # Encode the message
    encoder = CW(sample_rate=sample_rate, frequency=frequency, wpm=wpm)
    audio = encoder.modulate(message)

    print(f"Generated {len(audio)} samples ({len(audio)/sample_rate:.2f} seconds)")

    # Decode the message
    decoder = CWDecoder(
        wpm=wpm,
        sample_rate=sample_rate,
        frequency=frequency,
        use_dcd=False  # DCD not needed for clean signals
    )

    decoded = decoder.demodulate(audio)

    print(f"Decoded: {decoded}")
    print()

    # Get statistics
    stats = decoder.get_statistics()
    print("Decoder Statistics:")
    print(f"  Estimated WPM: {stats['wpm']:.1f}")
    print(f"  Signal Quality: {stats['metric']:.1f}")
    print(f"  SNR: {stats['snr_db']:.1f} dB")
    print(f"  Characters: {stats['total_characters']}")
    print(f"  Errors: {stats['decode_errors']}")
    print(f"  Error Rate: {stats['error_rate']:.2%}")
    print()

    # Check if decode was successful
    if decoded == message:
        print("✓ PASS: Decoded message matches original")
    else:
        print("✗ FAIL: Decoded message does not match")
        print(f"  Expected: {message}")
        print(f"  Got: {decoded}")

    print()


def test_with_noise():
    """Test CW decoding with added noise."""
    print("=" * 60)
    print("Test 2: CW Decode with Noise")
    print("=" * 60)

    message = "TEST"
    wpm = 25
    sample_rate = 8000.0
    frequency = 800.0

    print(f"Message: {message}")
    print(f"Speed: {wpm} WPM")
    print()

    # Encode the message
    encoder = CW(sample_rate=sample_rate, frequency=frequency, wpm=wpm)
    audio = encoder.modulate(message)

    # Test with different noise levels
    for snr_db in [20, 10, 5, 0]:
        print(f"Testing with SNR = {snr_db} dB:")

        # Add noise
        noisy_audio = add_noise(audio, snr_db)

        # Decode
        decoder = CWDecoder(
            wpm=wpm,
            sample_rate=sample_rate,
            frequency=frequency,
            use_dcd=False
        )

        decoded = decoder.demodulate(noisy_audio)
        stats = decoder.get_statistics()

        print(f"  Decoded: {decoded}")
        print(f"  Measured SNR: {stats['snr_db']:.1f} dB")
        print(f"  Errors: {stats['decode_errors']}")

        if decoded == message:
            print("  ✓ PASS")
        else:
            print("  ✗ FAIL")

        print()


def test_speed_tracking():
    """Test adaptive speed tracking."""
    print("=" * 60)
    print("Test 3: Adaptive Speed Tracking")
    print("=" * 60)

    message = "PARIS PARIS"  # Standard test word
    actual_wpm = 20
    initial_wpm = 20  # Start with correct speed
    sample_rate = 8000.0
    frequency = 800.0

    print(f"Message: {message}")
    print(f"Actual Speed: {actual_wpm} WPM")
    print(f"Initial Decoder Speed: {initial_wpm} WPM")
    print()

    # Encode at actual speed
    encoder = CW(sample_rate=sample_rate, frequency=frequency, wpm=actual_wpm)
    audio = encoder.modulate(message)

    # Decode with wrong initial speed
    decoder = CWDecoder(
        wpm=initial_wpm,
        sample_rate=sample_rate,
        frequency=frequency,
        use_dcd=False
    )

    decoded = decoder.demodulate(audio)
    stats = decoder.get_statistics()

    print(f"Decoded: {decoded}")
    print(f"Initial WPM Setting: {initial_wpm}")
    print(f"Final WPM Estimate: {stats['wpm']:.1f}")
    print(f"Actual WPM: {actual_wpm}")
    print(f"Tracking Error: {abs(stats['wpm'] - actual_wpm):.1f} WPM")
    print()

    # Check if message decoded correctly and WPM estimated accurately
    if decoded == message and abs(stats['wpm'] - actual_wpm) < 2.0:
        print("✓ PASS: Message decoded and WPM estimated correctly")
    else:
        if decoded != message:
            print("✗ FAIL: Message decode failed")
            print(f"  Expected: {message}")
            print(f"  Got: {decoded}")
        else:
            print("✗ FAIL: WPM estimation inaccurate")

    print()
    print("Note: Decoder requires accurate initial WPM (±5%) for best results.")

    print()


def test_callback_mode():
    """Test asynchronous callback-based decoding."""
    print("=" * 60)
    print("Test 4: Callback-Based Decoding")
    print("=" * 60)

    message = "CQ CQ DE W1ABC"
    wpm = 20
    sample_rate = 8000.0
    frequency = 800.0

    print(f"Message: {message}")
    print("Decoded output: ", end='', flush=True)

    # Encode
    encoder = CW(sample_rate=sample_rate, frequency=frequency, wpm=wpm)
    audio = encoder.modulate(message)

    # Decode with callback
    decoded_chars = []

    def text_callback(text):
        """Callback function for real-time text output."""
        print(text, end='', flush=True)
        decoded_chars.append(text)

    decoder = CWDecoder(
        wpm=wpm,
        sample_rate=sample_rate,
        frequency=frequency,
        text_callback=text_callback,
        use_dcd=False
    )

    # Process in chunks to simulate real-time streaming
    chunk_size = 1000
    for i in range(0, len(audio), chunk_size):
        chunk = audio[i:i + chunk_size]
        decoder.process(chunk)

    print()
    print()

    decoded = ''.join(decoded_chars)
    if decoded == message:
        print("✓ PASS: Callback mode decoded correctly")
    else:
        print("✗ FAIL: Callback mode decode mismatch")
        print(f"  Expected: {message}")
        print(f"  Got: {decoded}")

    print()


def test_different_speeds():
    """Test decoding at different speeds."""
    print("=" * 60)
    print("Test 5: Different Speeds")
    print("=" * 60)

    message = "QRZ"
    sample_rate = 8000.0
    frequency = 800.0

    for wpm in [10, 20, 30, 40]:
        print(f"Testing at {wpm} WPM:")

        # Encode
        encoder = CW(sample_rate=sample_rate, frequency=frequency, wpm=wpm)
        audio = encoder.modulate(message)

        # Decode
        decoder = CWDecoder(
            wpm=wpm,
            sample_rate=sample_rate,
            frequency=frequency,
            use_dcd=False
        )

        decoded = decoder.demodulate(audio)
        stats = decoder.get_statistics()

        print(f"  Decoded: {decoded}")
        print(f"  Duration: {len(audio)/sample_rate:.2f} seconds")
        print(f"  Success: {'✓' if decoded == message else '✗'}")
        print()


def test_prosigns():
    """Test decoding prosigns."""
    print("=" * 60)
    print("Test 6: Prosigns")
    print("=" * 60)

    message = "CQ DE W1ABC <AR> <SK>"
    wpm = 20
    sample_rate = 8000.0
    frequency = 800.0

    print(f"Message: {message}")

    # Encode
    encoder = CW(sample_rate=sample_rate, frequency=frequency, wpm=wpm)
    audio = encoder.modulate(message)

    # Decode
    decoder = CWDecoder(
        wpm=wpm,
        sample_rate=sample_rate,
        frequency=frequency,
        use_dcd=False
    )

    decoded = decoder.demodulate(audio)

    print(f"Decoded: {decoded}")

    if decoded == message:
        print("✓ PASS: Prosigns decoded correctly")
    else:
        print("✗ FAIL: Prosign decode mismatch")

    print()


def main():
    """Run all CW decoder tests."""
    print()
    print("CW DECODER TEST SUITE")
    print()

    try:
        test_basic_decode()
        test_with_noise()
        test_speed_tracking()
        test_callback_mode()
        test_different_speeds()
        test_prosigns()

        print("=" * 60)
        print("All tests complete!")
        print("=" * 60)

    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == '__main__':
    sys.exit(main())
