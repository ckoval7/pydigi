#!/usr/bin/env python3
"""
8PSK Decoder Demo

Demonstrates 8PSK encoding and decoding with a simple example.
Shows both non-FEC and FEC modes.

Note: Decoders are slow in pure Python. For production use, consider
optimizing hot loops with Cython or numba.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import numpy as np


def demo_8psk_loopback():
    """Demonstrate 8PSK encode/decode loopback."""
    print("=" * 70)
    print("8PSK Decoder Demo - Encode/Decode Loopback")
    print("=" * 70)
    print()

    # Import encoder and decoder
    from pydigi.modems.psk8 import EightPSK_250
    from pydigi.modems.psk8_decoder import EightPSK_250_Decoder

    # Create message
    message = "HI"
    print(f"Message: '{message}'")
    print()

    # Encode
    print("Encoding with 8PSK250...")
    encoder = EightPSK_250(sample_rate=8000, frequency=1000)
    audio = encoder.modulate(message)
    print(f"  Generated {len(audio)} audio samples ({len(audio)/8000:.2f} seconds)")
    print()

    # Add some realistic noise (SNR ~15dB)
    noise_power = np.var(audio) / 30
    noisy_audio = audio + np.random.normal(0, np.sqrt(noise_power), len(audio))
    print(f"Added noise (SNR ~15dB)")
    print()

    # Decode
    print("Decoding with 8PSK250 decoder...")
    print("(Processing first 4000 samples for speed...)")
    decoder = EightPSK_250_Decoder(
        sample_rate=8000,
        frequency=1000,
        afc_enabled=True,
        squelch_enabled=False  # Disable squelch for demo
    )

    # Limit samples for demo (pure Python is slow)
    decoded_text = decoder.demodulate(noisy_audio[:4000])

    print(f"  Decoded: '{decoded_text}'")
    print()

    # Show stats
    stats = decoder.get_stats()
    print("Decoder Statistics:")
    print(f"  Symbols received:   {stats['symbols_received']}")
    print(f"  Characters decoded: {stats['chars_decoded']}")
    print(f"  Signal metric:      {stats['metric']:.1f}/100")
    print(f"  DCD (carrier det):  {stats['dcd']}")
    print(f"  Frequency:          {stats['frequency']:.2f} Hz")
    print(f"  Frequency error:    {stats['freqerr']:.3f} Hz")
    print()


def demo_fldigi_wav():
    """Demonstrate decoding of fldigi-generated WAV file."""
    print("=" * 70)
    print("8PSK Decoder Demo - fldigi WAV File")
    print("=" * 70)
    print()

    try:
        import scipy.io.wavfile as wavfile
    except ImportError:
        print("scipy not available, skipping WAV demo")
        return

    wav_path = "wav/fldigi_generated/fldigi_8psk500.wav"

    if not os.path.exists(wav_path):
        print(f"WAV file not found: {wav_path}")
        print("Skipping fldigi WAV demo")
        return

    # Load WAV
    print(f"Loading: {wav_path}")
    rate, audio = wavfile.read(wav_path)

    # Convert to mono float
    if len(audio.shape) > 1:
        audio = audio[:, 0]
    if audio.dtype == np.int16:
        audio = audio.astype(np.float32) / 32768.0

    print(f"  Loaded {len(audio)} samples at {rate} Hz ({len(audio)/rate:.2f} seconds)")
    print()

    # Decode
    print("Decoding with 8PSK500 decoder...")
    print("(Processing first 4000 samples for speed...)")

    from pydigi.modems.psk8_decoder import EightPSK_500_Decoder

    decoder = EightPSK_500_Decoder(
        sample_rate=rate,
        frequency=1000,  # Assume 1000 Hz carrier
        afc_enabled=True,
        squelch_enabled=False
    )

    decoded_text = decoder.demodulate(audio[:4000])

    print(f"  Decoded: '{decoded_text}'")
    print()

    # Show stats
    stats = decoder.get_stats()
    print("Decoder Statistics:")
    print(f"  Symbols received:   {stats['symbols_received']}")
    print(f"  Characters decoded: {stats['chars_decoded']}")
    print(f"  Signal metric:      {stats['metric']:.1f}/100")
    print(f"  DCD (carrier det):  {stats['dcd']}")
    print(f"  Frequency:          {stats['frequency']:.2f} Hz")
    print(f"  Frequency error:    {stats['freqerr']:.3f} Hz")
    print()

    if len(decoded_text) > 0:
        print("✓ Successfully decoded fldigi signal!")
    else:
        print("⚠ No characters decoded (may need more samples)")
    print()


def main():
    print()
    print("╔" + "=" * 68 + "╗")
    print("║" + " " * 20 + "8PSK Decoder Demo" + " " * 31 + "║")
    print("╚" + "=" * 68 + "╝")
    print()

    # Demo 1: Loopback test
    try:
        demo_8psk_loopback()
    except Exception as e:
        print(f"Error in loopback demo: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "-" * 70 + "\n")

    # Demo 2: fldigi WAV file
    try:
        demo_fldigi_wav()
    except Exception as e:
        print(f"Error in WAV demo: {e}")
        import traceback
        traceback.print_exc()

    print("=" * 70)
    print("Demo complete!")
    print()
    print("Note: Decoders are implemented in pure Python and process slowly.")
    print("For production use, consider optimizing with Cython or numba.")
    print("=" * 70)
    print()


if __name__ == "__main__":
    main()
