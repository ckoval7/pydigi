#!/usr/bin/env python3
"""
ARQ File Transfer Example

This example demonstrates how to send and receive files over an ARQ connection.
It uses a loopback setup where two ARQ protocol instances communicate with each
other through callbacks.

This mirrors the behavior of fldigi's FLARQ file transfer feature.

Usage:
    python examples/arq_file_transfer.py
"""

import os
import sys
import tempfile
import time

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from pydigi.arq.protocol import ARQProtocol
from pydigi.arq.config import ARQConfig


def main():
    """Run ARQ file transfer demo."""
    print("=" * 60)
    print("ARQ File Transfer Example")
    print("=" * 60)
    print()

    # Create two ARQ stations
    print("Setting up two ARQ stations (loopback)...")

    config1 = ARQConfig()
    config1.my_call = "STATION1"
    station1 = ARQProtocol(config=config1)

    config2 = ARQConfig()
    config2.my_call = "STATION2"
    station2 = ARQProtocol(config=config2)

    # Set up bidirectional communication
    def station1_send(frame: bytes):
        """Forward frames from station1 to station2."""
        station2.receive_frame(frame)

    def station2_send(frame: bytes):
        """Forward frames from station2 to station1."""
        station1.receive_frame(frame)

    station1.set_send_callback(station1_send)
    station2.set_send_callback(station2_send)

    # Set up callbacks
    def status_callback(station_name: str):
        """Create status callback for a station."""
        def callback(msg: str):
            print(f"[{station_name}] {msg}")
        return callback

    station1.set_status_callback(status_callback("STATION1"))
    station2.set_status_callback(status_callback("STATION2"))

    # Track received files on station2
    received_files = []

    def file_received_callback(filename: str, data: bytes):
        """Handle received files."""
        received_files.append((filename, data))
        print(f"\n✓ File received on STATION2:")
        print(f"  Filename: {filename}")
        print(f"  Size: {len(data)} bytes")

        # Save to temp directory
        output_path = os.path.join(tempfile.gettempdir(), f"received_{filename}")
        with open(output_path, 'wb') as f:
            f.write(data)
        print(f"  Saved to: {output_path}")
        print()

    station2.set_rx_file_callback(file_received_callback)

    # Connect the stations
    print("\nConnecting STATION1 to STATION2...")
    station1.connect("STATION2")

    # Process frames until connected
    for _ in range(20):
        station1.process()
        station2.process()

    if not station1.state.is_connected():
        print("ERROR: Failed to establish connection")
        return 1

    print("✓ Connection established\n")

    # Create a test file
    print("Creating test file...")
    with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.txt') as f:
        test_file_path = f.name
        test_content = b"""This is a test file for ARQ file transfer!

The FLARQ protocol allows sending files over unreliable radio links
by breaking them into blocks and automatically retransmitting any
that are corrupted or lost.

This implementation is based on the fldigi source code and is
compatible with the fldigi FLARQ protocol.

Supports:
- Text files
- Binary files (images, documents, etc.)
- Base64 encoding for reliable transmission
- Automatic error detection with CRC-16
"""
        f.write(test_content)

    print(f"  Created: {test_file_path}")
    print(f"  Size: {len(test_content)} bytes")
    print()

    # Send the file
    print(f"Sending file from STATION1 to STATION2...")
    try:
        station1.send_file(test_file_path)
    except Exception as e:
        print(f"ERROR sending file: {e}")
        os.unlink(test_file_path)
        return 1

    # Process frames to transfer the file
    print("Processing ARQ protocol...")
    for i in range(200):
        station1.process()
        station2.process()

        # Check if transfer is complete
        if len(received_files) > 0:
            print(f"✓ Transfer complete after {i+1} iterations")
            break

        # Progress indicator every 20 iterations
        if (i + 1) % 20 == 0:
            print(f"  ... processing (iteration {i+1})")

    # Verify the transfer
    print()
    if len(received_files) > 0:
        filename, received_content = received_files[0]
        print("Transfer verification:")
        print(f"  Original size:  {len(test_content)} bytes")
        print(f"  Received size:  {len(received_content)} bytes")

        if received_content == test_content:
            print("  ✓ Content matches perfectly!")
        else:
            print("  ✗ Content mismatch - transfer error!")
            return 1
    else:
        print("ERROR: No file was received")
        return 1

    # Cleanup
    os.unlink(test_file_path)

    # Demonstrate sending a binary file
    print("\n" + "=" * 60)
    print("Sending a binary file (simulated image)...")
    print("=" * 60)
    print()

    # Create a small binary file
    with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.bin') as f:
        binary_file_path = f.name
        # Create some binary data (simulating an image)
        binary_content = bytes(range(256)) + bytes(range(255, -1, -1))
        f.write(binary_content)

    print(f"Created binary file: {binary_file_path}")
    print(f"Size: {len(binary_content)} bytes")
    print()

    # Clear received files
    received_files.clear()

    # Send binary file
    print("Sending binary file...")
    station1.send_file(binary_file_path)

    # Process
    for i in range(200):
        station1.process()
        station2.process()

        if len(received_files) > 0:
            print(f"✓ Transfer complete after {i+1} iterations")
            break

    # Verify
    if len(received_files) > 0:
        _, received_binary = received_files[0]
        if received_binary == binary_content:
            print("✓ Binary file transferred successfully!")
        else:
            print("✗ Binary file mismatch!")
            return 1
    else:
        print("ERROR: Binary file not received")
        return 1

    # Cleanup
    os.unlink(binary_file_path)

    # Disconnect
    print("\n" + "=" * 60)
    print("Disconnecting...")
    print("=" * 60)
    station1.disconnect()

    for _ in range(10):
        station1.process()
        station2.process()

    print("✓ Demo complete!")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
