#!/usr/bin/env python3
"""ARQ Loopback Test - Demonstrates end-to-end text transfer.

This example creates two ARQ protocol instances and connects them
via callbacks, demonstrating bidirectional text transfer.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from pydigi.arq import ARQProtocol


def main():
    """Run ARQ loopback test."""
    # Create two stations
    station_a = ARQProtocol()
    station_a.config.my_call = "W1ABC"

    station_b = ARQProtocol()
    station_b.config.my_call = "K6XYZ"

    # Connect callbacks (simulating radio link)
    station_a.set_send_callback(lambda frame: station_b.receive_frame(frame))
    station_b.set_send_callback(lambda frame: station_a.receive_frame(frame))

    # Set up status callbacks
    station_a.set_status_callback(lambda msg: print(f"[A] {msg}"))
    station_b.set_status_callback(lambda msg: print(f"[B] {msg}"))

    # Set up RX callbacks
    received_by_b = []
    received_by_a = []

    station_a.set_rx_text_callback(lambda text: received_by_a.append(text))
    station_b.set_rx_text_callback(lambda text: received_by_b.append(text))

    print("=== ARQ Loopback Test ===\n")

    # Test 1: Connection
    print("Test 1: Establishing connection...")
    station_a.connect("K6XYZ")

    for i in range(5):
        station_a.process()
        station_b.process()

    if station_a.is_connected() and station_b.is_connected():
        print("✓ Connection established\n")
    else:
        print("✗ Connection failed\n")
        return

    # Test 2: Send short message A -> B
    print("Test 2: Sending short message A -> B...")
    station_a.send_text("Hello from W1ABC!")

    for i in range(10):
        station_a.process()
        station_b.process()

    text_b = "".join(received_by_b)
    if text_b == "Hello from W1ABC!":
        print(f"✓ Received: {text_b}\n")
    else:
        print(f"✗ Expected 'Hello from W1ABC!', got '{text_b}'\n")

    # Test 3: Send short message B -> A
    print("Test 3: Sending short message B -> A...")
    station_b.send_text("Hello from K6XYZ!")

    for i in range(10):
        station_a.process()
        station_b.process()

    text_a = "".join(received_by_a)
    if text_a == "Hello from K6XYZ!":
        print(f"✓ Received: {text_a}\n")
    else:
        print(f"✗ Expected 'Hello from K6XYZ!', got '{text_a}'\n")

    # Test 4: Send long message (multiple blocks)
    print("Test 4: Sending long message (multiple blocks)...")
    received_by_b.clear()

    long_msg = "This is a longer message that will be split into multiple blocks. " * 5
    station_a.send_text(long_msg)

    for i in range(20):
        station_a.process()
        station_b.process()

    text_b = "".join(received_by_b)
    if text_b == long_msg:
        print(f"✓ Received {len(text_b)} bytes correctly\n")
    else:
        print(f"✗ Message mismatch (expected {len(long_msg)}, got {len(text_b)})\n")

    # Test 5: Disconnect
    print("Test 5: Disconnecting...")
    station_a.disconnect()

    for i in range(5):
        station_a.process()
        station_b.process()

    if not station_a.is_connected() and not station_b.is_connected():
        print("✓ Disconnected\n")
    else:
        print("✗ Disconnect failed\n")

    print("=== Tests Complete ===")


if __name__ == "__main__":
    main()
