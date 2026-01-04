# FLARQ ARQ Protocol - User Guide

This guide will help you get started with the FLARQ ARQ protocol implementation in pydigi.

## Table of Contents

1. [Introduction](#introduction)
2. [Quick Start](#quick-start)
3. [Installation](#installation)
4. [Basic Usage](#basic-usage)
5. [Text Transfer](#text-transfer)
6. [File Transfer](#file-transfer)
7. [Configuration](#configuration)
8. [Callbacks](#callbacks)
9. [State Management](#state-management)
10. [Error Handling](#error-handling)
11. [Best Practices](#best-practices)
12. [Examples](#examples)

## Introduction

### What is FLARQ?

FLARQ (Fast Light Automatic Repeat reQuest) is a reliable data transfer protocol designed for HF radio communications. It provides:

- **Automatic error detection** using CRC-16 checksums
- **Automatic retransmission** of corrupted or missing data
- **Block-based transfer** for efficient bandwidth usage
- **Transport agnostic** - works over any modem (PSK, MFSK, Thor, MT63, etc.)
- **File transfer support** with Base64 encoding

### When to Use ARQ

Use FLARQ when you need:

- **Reliable delivery** - Guarantee that files or messages arrive intact
- **File transfer** - Send documents, images, or data files over radio
- **Poor conditions** - Automatic retransmission handles fading and interference
- **Compatibility** - Interoperate with fldigi's FLARQ implementation

Don't use ARQ when:

- You need real-time communication (use plain PSK/RTTY instead)
- Bandwidth is extremely limited (ARQ has protocol overhead)
- Data loss is acceptable (direct transmission is simpler)

## Quick Start

Here's a minimal example to get you started:

```python
from pydigi.arq import ARQProtocol

# Create ARQ protocol instance
arq = ARQProtocol()
arq.config.my_call = "W1ABC"

# Set up a callback to send frames over your modem
def send_callback(frame_data: bytes):
    # Convert frame to audio and transmit
    # (Implementation depends on your modem)
    modem.send(frame_data)

arq.set_send_callback(send_callback)

# Set up a callback to receive text
def text_received(text: str):
    print(f"Received: {text}")

arq.set_rx_text_callback(text_received)

# Connect to another station
arq.connect("K6XYZ")

# In your main loop, process ARQ protocol
while True:
    # When you receive data from the modem
    arq.receive_frame(modem_data)

    # Process ARQ state machine
    arq.process()

    # Send text when connected
    if arq.is_connected():
        arq.send_text("Hello World!")
        break

# Disconnect when done
arq.disconnect()
```

## Installation

### Dependencies

The ARQ implementation requires:

```bash
pip install crcmod>=1.7
```

All other dependencies are already part of pydigi:
- `numpy>=1.20.0`
- `scipy>=1.7.0`

### Installing pydigi with ARQ Support

```bash
# Install from requirements
pip install -r requirements.txt

# Or manually install dependencies
pip install numpy scipy crcmod
```

### Verify Installation

```python
from pydigi.arq import ARQProtocol
print("ARQ support available!")
```

## Basic Usage

### Creating an ARQ Instance

```python
from pydigi.arq import ARQProtocol, ARQConfig

# Simple creation (uses default config)
arq = ARQProtocol()
arq.config.my_call = "W1ABC"

# Or with custom configuration
config = ARQConfig()
config.my_call = "W1ABC"
config.buffer_size = 256  # Larger blocks
config.send_window = 4    # More blocks in flight
config.retry_count = 10   # More retries

arq = ARQProtocol(config=config)
```

### Connection Lifecycle

```python
# Check connection state
if not arq.is_connected():
    # Initiate connection
    arq.connect("K6XYZ")

# Process ARQ protocol (call regularly)
arq.process()

# Check if connected
if arq.is_connected():
    # Send data
    arq.send_text("Connected!")

# Disconnect when done
arq.disconnect()

# Process final frames
for _ in range(10):
    arq.process()
```

### The Process Loop

The ARQ protocol requires regular calls to `process()`:

```python
import time

while True:
    # Process received frames
    arq.process()

    # Small delay to avoid busy-waiting
    time.sleep(0.1)

    # Your application logic here
    if should_disconnect:
        arq.disconnect()
        break
```

**Important**: Call `process()` at least every 100-200ms for responsive behavior.

## Text Transfer

### Sending Text

```python
# Must be connected first
arq.connect("K6XYZ")

# Wait for connection (or check in process loop)
while not arq.is_connected():
    arq.process()
    time.sleep(0.1)

# Send text (can be any length)
arq.send_text("This is a short message")

# Send long text (automatically split into blocks)
long_message = "This is a much longer message " * 100
arq.send_text(long_message)

# Continue processing to actually transmit
while arq.statistics.tx_blocks_pending > 0:
    arq.process()
    time.sleep(0.1)
```

### Receiving Text

Set up a callback to receive text:

```python
def handle_received_text(text: str):
    """Called when text is received."""
    print(f"RX: {text}")

    # Save to file, display to user, etc.
    with open("received.txt", "a") as f:
        f.write(text)

arq.set_rx_text_callback(handle_received_text)

# Now process() will call your callback when text arrives
while True:
    arq.process()
    time.sleep(0.1)
```

### Bidirectional Communication

Both stations can send and receive simultaneously:

```python
# Station A
arq_a = ARQProtocol()
arq_a.config.my_call = "W1ABC"
arq_a.set_rx_text_callback(lambda text: print(f"A received: {text}"))

# Station B
arq_b = ARQProtocol()
arq_b.config.my_call = "K6XYZ"
arq_b.set_rx_text_callback(lambda text: print(f"B received: {text}"))

# Connect them
arq_a.connect("K6XYZ")

# Both can send
arq_a.send_text("Hello from A")
arq_b.send_text("Hello from B")

# Process both sides
while True:
    arq_a.process()
    arq_b.process()
    time.sleep(0.1)
```

## File Transfer

### Sending Files

```python
# Connect first
arq.connect("K6XYZ")
while not arq.is_connected():
    arq.process()
    time.sleep(0.1)

# Send a file (any file type)
arq.send_file("/path/to/document.pdf")

# Or send a text file
arq.send_file("/path/to/message.txt")

# Monitor transfer progress
while arq.statistics.tx_blocks_pending > 0:
    arq.process()
    time.sleep(0.1)
    print(f"Blocks pending: {arq.statistics.tx_blocks_pending}")

print("File sent!")
```

### Receiving Files

Set up a callback to receive files:

```python
def handle_received_file(filename: str, data: bytes):
    """Called when a complete file is received."""
    print(f"Received file: {filename} ({len(data)} bytes)")

    # Save to disk
    output_path = f"/received/{filename}"
    with open(output_path, 'wb') as f:
        f.write(data)

    print(f"Saved to: {output_path}")

arq.set_rx_file_callback(handle_received_file)

# Process to receive
while True:
    arq.process()
    time.sleep(0.1)
```

### File Transfer Format

Files are transmitted with metadata headers:

```
ARQ:FILE::<filename>
ARQ:ENCODING::BASE64
ARQ:SIZE::<bytes>
ARQ::STX
<base64 encoded data>
ARQ::ETX
```

This format is compatible with fldigi's FLARQ implementation.

### Binary vs Text Files

The protocol handles both automatically:

```python
# Text file (.txt, .md, .log, etc.)
arq.send_file("message.txt")  # Sent as Base64

# Binary file (.pdf, .jpg, .bin, etc.)
arq.send_file("image.jpg")    # Sent as Base64

# The receiver gets the original bytes in the callback
```

## Configuration

### ARQConfig Options

```python
from pydigi.arq import ARQConfig

config = ARQConfig()

# Identity
config.my_call = "W1ABC"        # Your callsign (required)

# Transfer parameters
config.buffer_size = 128        # Block payload size (64-256 bytes)
config.send_window = 2          # Blocks in flight (1-4)
config.max_headers = 8          # Max frames per send (4-16)

# Timing
config.timeout_ms = 60000       # Connection timeout (ms)
config.retry_count = 5          # Retransmission attempts (3-10)
config.tx_delay_ms = 500        # RX-to-TX turnaround delay (ms)
config.id_timer_sec = 600       # Keepalive interval (seconds)

# Create ARQ with config
arq = ARQProtocol(config=config)
```

### Configuration Guidelines

**buffer_size**:
- **Smaller (64-96)**: Better for poor conditions, more overhead
- **Larger (192-256)**: Better for good conditions, less overhead
- **Default (128)**: Good balance for most conditions

**send_window**:
- **1**: Sequential transmission, most reliable
- **2 (default)**: Good balance of speed and reliability
- **4**: Maximum throughput, requires good signal

**retry_count**:
- **3-5**: Fast timeout, good for testing
- **5-8 (default)**: Standard operation
- **10+**: Poor conditions, may wait a long time

### Changing Configuration

```python
# Create with defaults
arq = ARQProtocol()

# Modify before connecting
arq.config.buffer_size = 256
arq.config.send_window = 4

# Connect
arq.connect("K6XYZ")

# Note: Don't change config while connected!
```

## Callbacks

### Available Callbacks

The ARQ protocol provides callbacks for events:

```python
# Text received
arq.set_rx_text_callback(callback)
# Signature: callback(text: str) -> None

# File received
arq.set_rx_file_callback(callback)
# Signature: callback(filename: str, data: bytes) -> None

# Frame transmission
arq.set_send_callback(callback)
# Signature: callback(frame: bytes) -> None

# Status messages
arq.set_status_callback(callback)
# Signature: callback(message: str) -> None
```

### Setting Up Callbacks

```python
def on_text_received(text: str):
    print(f"Received text: {text}")

def on_file_received(filename: str, data: bytes):
    print(f"Received file: {filename}")
    with open(filename, 'wb') as f:
        f.write(data)

def on_send_frame(frame: bytes):
    # Send frame over your modem/radio
    modem.transmit(frame)

def on_status(message: str):
    # Log status messages
    logging.info(f"ARQ: {message}")

# Register callbacks
arq.set_rx_text_callback(on_text_received)
arq.set_rx_file_callback(on_file_received)
arq.set_send_callback(on_send_frame)
arq.set_status_callback(on_status)
```

### Callback Thread Safety

**Important**: Callbacks are called from the thread that calls `process()`.

```python
# Single-threaded (safe)
while True:
    arq.process()  # Callbacks called here
    time.sleep(0.1)

# Multi-threaded (be careful)
def process_loop():
    while running:
        arq.process()  # Callbacks called from this thread
        time.sleep(0.1)

thread = threading.Thread(target=process_loop)
thread.start()
```

If using threads, ensure your callbacks are thread-safe or use locks.

## State Management

### Connection States

The ARQ protocol uses a state machine with these states:

```python
from pydigi.arq import LinkState

LinkState.DISCONNECTED    # No connection
LinkState.LISTENING       # Waiting for incoming connection
LinkState.CONNECTING      # Outgoing connection in progress
LinkState.WAITING_FOR_ACK # Waiting for connection acknowledgment
LinkState.CONNECTED       # Connected and ready
LinkState.DISCONNECTING   # Graceful disconnect in progress
# ... and others
```

### Checking State

```python
# Simple check
if arq.is_connected():
    arq.send_text("Hello")

# Detailed state
print(f"Current state: {arq.state.current_state}")

# State-specific logic
if arq.state.current_state == LinkState.CONNECTING:
    print("Connection in progress...")
elif arq.state.current_state == LinkState.CONNECTED:
    print("Connected!")
```

### State Transitions

Normal connection flow:

```
DISCONNECTED → CONNECTING → WAITING_FOR_ACK → CONNECTED
```

Normal disconnection flow:

```
CONNECTED → DISCONNECTING → DISCONNECTED
```

Timeout/error flow:

```
CONNECTING → DISCONNECTED (timeout)
CONNECTED → DISCONNECTED (timeout/error)
```

## Error Handling

### Exception Types

```python
from pydigi.arq import (
    ARQError,           # Base exception
    ARQFrameError,      # Invalid frame format
    ARQCRCError,        # CRC checksum mismatch
    ARQTimeoutError,    # Operation timeout
    ARQConnectionError, # Connection failed
    ARQStateError,      # Invalid state for operation
    ARQAbortError,      # Transfer aborted
)
```

### Handling Errors

```python
try:
    arq.send_text("Hello")
except ARQStateError:
    print("Error: Not connected")
    arq.connect("K6XYZ")
except ARQError as e:
    print(f"ARQ error: {e}")
```

### Common Error Scenarios

**Not Connected**:
```python
# Wrong
arq.send_text("Hello")  # Raises ARQStateError

# Right
if arq.is_connected():
    arq.send_text("Hello")
else:
    print("Not connected yet")
```

**Connection Timeout**:
```python
arq.connect("K6XYZ")

# Wait for connection with timeout
timeout = time.time() + 30  # 30 second timeout
while not arq.is_connected():
    arq.process()
    time.sleep(0.1)

    if time.time() > timeout:
        print("Connection timeout")
        break
```

**Frame Errors**:
```python
# CRC errors are logged but handled internally
arq.set_status_callback(lambda msg: print(msg))

# You'll see messages like:
# "CRC error in received frame"
# Frame is discarded and retransmission requested
```

### Graceful Error Recovery

```python
def safe_send(arq, text):
    """Send text with error handling."""
    if not arq.is_connected():
        print("Connecting...")
        arq.connect("K6XYZ")

        # Wait for connection
        for _ in range(100):  # 10 second timeout
            arq.process()
            time.sleep(0.1)
            if arq.is_connected():
                break
        else:
            print("Connection failed")
            return False

    try:
        arq.send_text(text)
        return True
    except ARQError as e:
        print(f"Send failed: {e}")
        return False
```

## Best Practices

### 1. Call process() Regularly

```python
# Good - Regular processing
while True:
    arq.process()
    time.sleep(0.1)

# Bad - Infrequent processing
while True:
    arq.process()
    time.sleep(5.0)  # Too slow!
```

**Recommendation**: Call `process()` every 100-200ms.

### 2. Wait for Connection

```python
# Good - Wait for connection
arq.connect("K6XYZ")
while not arq.is_connected():
    arq.process()
    time.sleep(0.1)
arq.send_text("Hello")

# Bad - Send immediately
arq.connect("K6XYZ")
arq.send_text("Hello")  # Will raise ARQStateError!
```

### 3. Handle Disconnections

```python
# Monitor connection state
while True:
    arq.process()

    if not arq.is_connected() and was_connected:
        print("Disconnected!")
        # Reconnect or exit
        break

    was_connected = arq.is_connected()
```

### 4. Use Appropriate Buffer Size

```python
# Poor HF conditions
config.buffer_size = 64   # Small blocks
config.send_window = 1    # Sequential

# Good conditions
config.buffer_size = 256  # Larger blocks
config.send_window = 4    # Parallel transmission
```

### 5. Monitor Statistics

```python
# Check transfer progress
stats = arq.statistics
print(f"TX blocks: {stats.tx_blocks_total}")
print(f"RX blocks: {stats.rx_blocks_total}")
print(f"Retries: {stats.retransmissions}")
print(f"Pending: {stats.tx_blocks_pending}")
```

### 6. Graceful Shutdown

```python
# Disconnect gracefully
arq.disconnect()

# Process final frames
for _ in range(20):
    arq.process()
    time.sleep(0.1)

# Now safe to exit
```

### 7. File Transfer Tips

```python
# Check file size before sending
import os
file_size = os.path.getsize("largefile.pdf")
if file_size > 1000000:  # 1MB
    print("Warning: Large file will take time")

# Send file
arq.send_file("largefile.pdf")

# Monitor progress
while arq.statistics.tx_blocks_pending > 0:
    progress = 100 * (1 - arq.statistics.tx_blocks_pending / arq.statistics.tx_blocks_total)
    print(f"Progress: {progress:.1f}%")
    arq.process()
    time.sleep(0.5)
```

## Examples

### Complete Examples

See the `examples/` directory for complete working examples:

1. **arq_loopback_test.py** - Basic loopback test
   - Shows connection establishment
   - Demonstrates text transfer
   - Includes bidirectional communication
   - Good for testing and learning

2. **arq_file_transfer.py** - File transfer demo
   - Shows file sending and receiving
   - Demonstrates binary file transfer
   - Includes progress monitoring
   - Production-ready patterns

### Running Examples

```bash
# Basic loopback test
python examples/arq_loopback_test.py

# File transfer demo
python examples/arq_file_transfer.py
```

### Integration with Modems

Example with PSK modem (conceptual):

```python
from pydigi import PSK31
from pydigi.arq import ARQProtocol

# Create modem
modem = PSK31(frequency=1000, sample_rate=8000)

# Create ARQ wrapper
arq = ARQProtocol()
arq.config.my_call = "W1ABC"

# Connect ARQ to modem
def send_frame(frame: bytes):
    # Encode frame as audio
    audio = modem.encode(frame)
    # Transmit audio
    radio.transmit(audio)

arq.set_send_callback(send_frame)

# Receive from modem
def on_modem_data(data: bytes):
    # Pass decoded data to ARQ
    arq.receive_frame(data)

modem.set_rx_callback(on_modem_data)

# Now use ARQ normally
arq.connect("K6XYZ")
```

## Troubleshooting

### Connection Fails

**Problem**: `connect()` never reaches CONNECTED state

**Solutions**:
- Verify both stations are calling `process()` regularly
- Check that `send_callback` is transmitting frames
- Verify callsigns match on both ends
- Check for radio/audio issues

### Text Not Received

**Problem**: Text sent but callback never called

**Solutions**:
- Verify `set_rx_text_callback()` was called
- Check that both sides are connected
- Call `process()` on receiving side
- Check for CRC errors in status messages

### Files Corrupted

**Problem**: Received file doesn't match sent file

**Solutions**:
- Check error rate (should be very low)
- Look for CRC errors in logs
- Verify file was completely transmitted
- Check disk space on receiver

### Performance Issues

**Problem**: Transfer is very slow

**Solutions**:
- Increase `buffer_size` for better conditions
- Increase `send_window` for more parallelism
- Reduce `retry_count` if conditions are good
- Check for excessive retransmissions

## Next Steps

- Read [API Reference](api_reference.md) for detailed API documentation
- Review [Protocol Reference](protocol_reference.md) for technical details
- See [Testing Guide](testing_guide.md) for testing strategies
- Check [Overview](overview.md) for architecture information

## Support

For issues or questions:
- Check the [examples/](../../examples/) directory
- Review the [test suite](../../tests/test_arq/) for usage patterns
- See [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md) for current status
