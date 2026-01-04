#!/usr/bin/env python3
"""ARQ Audio Loopback Test - Demonstrates ARQ over audio link.

This example creates two ARQ protocol instances connected via
audio bridges, demonstrating bidirectional ARQ communication
over a simulated audio link (in-memory loopback).

This validates the complete stack:
- ARQ Protocol → Audio Bridge → PSK Modulator → Audio
- Audio → PSK Decoder → Frame Extractor → ARQ Protocol
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import time
from pydigi.arq import ARQProtocol
from pydigi.arq.audio_bridge import ARQAudioBridge


def run_arq_audio_tests():
    """Run comprehensive ARQ over audio tests."""
    print("=" * 60)
    print("ARQ AUDIO LOOPBACK TEST")
    print("=" * 60)
    print()
    print("This test demonstrates ARQ protocol working over audio.")
    print("Two stations communicate via PSK125 modulation in loopback mode.")
    print()

    # Create two ARQ stations
    print("Setting up stations...")
    station_a = ARQProtocol()
    station_a.config.my_call = "W1ABC"
    station_a.config.retry_timeout = 50  # Faster timeouts for testing

    station_b = ARQProtocol()
    station_b.config.my_call = "K6XYZ"
    station_b.config.retry_timeout = 50

    # Create audio bridges (loopback mode)
    bridge_a = ARQAudioBridge(
        station_a,
        modem_baud=125,
        carrier_freq=1000,
        sample_rate=8000,
        loopback_mode=True,
        debug=False  # Set to True for verbose output
    )

    bridge_b = ARQAudioBridge(
        station_b,
        modem_baud=125,
        carrier_freq=1000,
        sample_rate=8000,
        loopback_mode=True,
        debug=False
    )

    # Connect bridges for bidirectional loopback
    bridge_a.connect_loopback(bridge_b)
    bridge_b.connect_loopback(bridge_a)

    # Start bridges
    bridge_a.start()
    bridge_b.start()

    # Set up status callbacks
    station_a.set_status_callback(lambda msg: print(f"[A] {msg}"))
    station_b.set_status_callback(lambda msg: print(f"[B] {msg}"))

    # Set up RX callbacks
    received_by_b = []
    received_by_a = []

    station_a.set_rx_text_callback(lambda text: received_by_a.append(text))
    station_b.set_rx_text_callback(lambda text: received_by_b.append(text))

    print("✓ Setup complete\n")

    # Track test results
    tests_passed = 0
    tests_total = 0

    # Test 1: Connection establishment
    print("Test 1: Establishing connection...")
    tests_total += 1

    station_a.connect("K6XYZ")

    # Process loop - both stations and bridges
    for i in range(10):
        bridge_a.process()
        bridge_b.process()
        time.sleep(0.01)  # Small delay to simulate timing

    if station_a.is_connected() and station_b.is_connected():
        print("✓ Connection established\n")
        tests_passed += 1
    else:
        print("✗ Connection failed\n")
        print_stats(bridge_a, bridge_b)
        return tests_passed, tests_total

    # Test 2: Short message A -> B
    print("Test 2: Sending short message A -> B...")
    tests_total += 1

    station_a.send_text("Hello from W1ABC!")

    for i in range(15):
        bridge_a.process()
        bridge_b.process()
        time.sleep(0.01)

    text_b = "".join(received_by_b)
    if text_b == "Hello from W1ABC!":
        print(f"✓ Received: '{text_b}'\n")
        tests_passed += 1
    else:
        print(f"✗ Expected 'Hello from W1ABC!', got '{text_b}'\n")

    # Test 3: Short message B -> A
    print("Test 3: Sending short message B -> A...")
    tests_total += 1

    station_b.send_text("Hello from K6XYZ!")

    for i in range(15):
        bridge_a.process()
        bridge_b.process()
        time.sleep(0.01)

    text_a = "".join(received_by_a)
    if text_a == "Hello from K6XYZ!":
        print(f"✓ Received: '{text_a}'\n")
        tests_passed += 1
    else:
        print(f"✗ Expected 'Hello from K6XYZ!', got '{text_a}'\n")

    # Test 4: Long message (multiple blocks)
    print("Test 4: Sending long message (multiple blocks)...")
    tests_total += 1
    received_by_b.clear()

    long_msg = "This is a longer message that will be split into multiple ARQ blocks. " * 5
    station_a.send_text(long_msg)

    for i in range(30):
        bridge_a.process()
        bridge_b.process()
        time.sleep(0.01)

    text_b = "".join(received_by_b)
    if text_b == long_msg:
        print(f"✓ Received {len(text_b)} bytes correctly\n")
        tests_passed += 1
    else:
        print(f"✗ Message mismatch (expected {len(long_msg)}, got {len(text_b)})\n")

    # Test 5: Bidirectional simultaneous transfer
    print("Test 5: Bidirectional simultaneous transfer...")
    tests_total += 1
    received_by_a.clear()
    received_by_b.clear()

    msg_a_to_b = "Message from A to B"
    msg_b_to_a = "Message from B to A"

    station_a.send_text(msg_a_to_b)
    station_b.send_text(msg_b_to_a)

    for i in range(20):
        bridge_a.process()
        bridge_b.process()
        time.sleep(0.01)

    text_a = "".join(received_by_a)
    text_b = "".join(received_by_b)

    if text_a == msg_b_to_a and text_b == msg_a_to_b:
        print("✓ Both messages received correctly\n")
        tests_passed += 1
    else:
        print(f"✗ Messages mismatch")
        print(f"  A received: '{text_a}' (expected '{msg_b_to_a}')")
        print(f"  B received: '{text_b}' (expected '{msg_a_to_b}')\n")

    # Test 6: Disconnect
    print("Test 6: Disconnecting...")
    tests_total += 1

    station_a.disconnect()

    for i in range(10):
        bridge_a.process()
        bridge_b.process()
        time.sleep(0.01)

    if not station_a.is_connected() and not station_b.is_connected():
        print("✓ Disconnected\n")
        tests_passed += 1
    else:
        print("✗ Disconnect failed\n")

    # Print statistics
    print_stats(bridge_a, bridge_b)

    # Stop bridges
    bridge_a.stop()
    bridge_b.stop()

    # Summary
    print()
    print("=" * 60)
    print(f"TESTS PASSED: {tests_passed}/{tests_total}")
    print("=" * 60)

    if tests_passed == tests_total:
        print("\n✓ All tests passed! ARQ over audio is working.")
        return 0
    else:
        print(f"\n✗ {tests_total - tests_passed} test(s) failed")
        return 1


def print_stats(bridge_a, bridge_b):
    """Print bridge statistics."""
    print("=" * 60)
    print("STATISTICS")
    print("=" * 60)

    stats_a = bridge_a.get_stats()
    stats_b = bridge_b.get_stats()

    print("\nStation A (W1ABC):")
    print(f"  Frames sent: {stats_a['frames_sent']}")
    print(f"  Frames received: {stats_a['frames_received']}")
    print(f"  Audio samples TX: {stats_a['audio_samples_tx']}")
    print(f"  Audio samples RX: {stats_a['audio_samples_rx']}")
    print(f"  Frame extraction:")
    print(f"    - Extracted: {stats_a['frame_extractor_stats']['frames_extracted']}")
    print(f"    - CRC errors: {stats_a['frame_extractor_stats']['crc_errors']}")
    print(f"  Decoder:")
    print(f"    - Chars decoded: {stats_a['decoder_stats']['chars_decoded']}")
    print(f"    - Signal quality: {stats_a['decoder_stats']['metric']:.1f}")

    print("\nStation B (K6XYZ):")
    print(f"  Frames sent: {stats_b['frames_sent']}")
    print(f"  Frames received: {stats_b['frames_received']}")
    print(f"  Audio samples TX: {stats_b['audio_samples_tx']}")
    print(f"  Audio samples RX: {stats_b['audio_samples_rx']}")
    print(f"  Frame extraction:")
    print(f"    - Extracted: {stats_b['frame_extractor_stats']['frames_extracted']}")
    print(f"    - CRC errors: {stats_b['frame_extractor_stats']['crc_errors']}")
    print(f"  Decoder:")
    print(f"    - Chars decoded: {stats_b['decoder_stats']['chars_decoded']}")
    print(f"    - Signal quality: {stats_b['decoder_stats']['metric']:.1f}")

    print()


def main():
    """Main entry point."""
    try:
        return run_arq_audio_tests()
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        return 1
    except Exception as e:
        print(f"\n\nError: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
