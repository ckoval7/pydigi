#!/usr/bin/env python3
"""
Simple RTTY decoder example.

Demonstrates how to use the RTTYDecoder to decode RTTY signals.
"""

import numpy as np
from pydigi.modems import RTTY, RTTYDecoder


def main():
    """Simple RTTY encode/decode example."""
    print("RTTY Decoder Example")
    print("=" * 60)

    # Create a message
    message = "CQ CQ DE W1AW K"
    print(f"Original message: '{message}'")

    # Encode with RTTY transmitter
    tx = RTTY(baud=45.45, shift=170)
    audio = tx.modulate(message, frequency=1000, sample_rate=8000)
    print(f"Encoded to {len(audio)} audio samples")

    # Decode with RTTY receiver
    rx = RTTYDecoder(baud=45.45, shift=170, sample_rate=8000, frequency=1000)

    # Method 1: Synchronous API (returns all decoded text)
    decoded = rx.demodulate(audio)
    print(f"Decoded message: '{decoded}'")

    # Method 2: Asynchronous API with callback
    print("\nUsing callback API:")
    rx2 = RTTYDecoder(baud=45.45, shift=170, sample_rate=8000, frequency=1000)
    rx2.text_callback = lambda char: print(char, end="", flush=True)
    rx2.process(audio)
    print()  # Newline after callback output

    # Show statistics
    stats = rx.get_statistics()
    print(f"\nDecoder Statistics:")
    print(f"  Characters decoded: {stats['total_chars']}")
    print(f"  Frame errors: {stats['errors']}")
    print(f"  Error rate: {stats['error_rate']:.2%}")


if __name__ == "__main__":
    main()
