# FLARQ ARQ Protocol - API Reference

Complete API reference for the pydigi ARQ implementation.

## Table of Contents

1. [ARQProtocol](#arqprotocol)
2. [ARQConfig](#arqconfig)
3. [ARQStatistics](#arqstatistics)
4. [LinkState](#linkstate)
5. [ARQStateMachine](#arqstatemachine)
6. [Exceptions](#exceptions)
7. [Supporting Classes](#supporting-classes)

---

## ARQProtocol

Main protocol class for FLARQ ARQ implementation.

### Constructor

```python
ARQProtocol(
    config: Optional[ARQConfig] = None,
    send_callback: Optional[Callable[[bytes], None]] = None
)
```

Creates a new ARQ protocol instance.

**Parameters**:
- `config` (ARQConfig, optional): Protocol configuration. Uses defaults if None.
- `send_callback` (callable, optional): Callback function to send frames. Takes frame bytes as parameter.

**Returns**: ARQProtocol instance

**Example**:
```python
from pydigi.arq import ARQProtocol, ARQConfig

# Simple creation
arq = ARQProtocol()

# With configuration
config = ARQConfig()
config.my_call = "W1ABC"
arq = ARQProtocol(config=config)

# With callback
def send(frame):
    print(f"Sending {len(frame)} bytes")

arq = ARQProtocol(send_callback=send)
```

---

### Connection Methods

#### connect()

```python
connect(remote_call: str) -> None
```

Initiate connection to a remote station.

**Parameters**:
- `remote_call` (str): Remote station callsign

**Raises**:
- `ARQStateError`: If already connected or connecting

**Example**:
```python
arq.connect("K6XYZ")

# Wait for connection
while not arq.is_connected():
    arq.process()
    time.sleep(0.1)
```

#### disconnect()

```python
disconnect() -> None
```

Gracefully disconnect from remote station.

**Raises**:
- `ARQStateError`: If not connected

**Example**:
```python
arq.disconnect()

# Process final frames
for _ in range(10):
    arq.process()
```

#### abort()

```python
abort() -> None
```

Abort current transfer (soft reset, keeps connection alive).

**Example**:
```python
# Abort current file transfer
arq.abort()

# Can continue using connection
arq.send_text("Transfer cancelled")
```

---

### Data Transfer Methods

#### send_text()

```python
send_text(text: str) -> None
```

Send text over the ARQ connection.

**Parameters**:
- `text` (str): Text to send (any length)

**Raises**:
- `ARQStateError`: If not connected

**Example**:
```python
arq.send_text("Hello World!")

# Long message (automatically split into blocks)
arq.send_text("Long message " * 1000)
```

#### send_file()

```python
send_file(file_path: str, description: Optional[str] = None) -> None
```

Send a file over the ARQ connection.

**Parameters**:
- `file_path` (str): Path to file to send
- `description` (str, optional): File description (not currently used)

**Raises**:
- `ARQStateError`: If not connected
- `FileNotFoundError`: If file doesn't exist
- `ARQError`: If file read fails

**Example**:
```python
# Send text file
arq.send_file("/path/to/document.txt")

# Send binary file
arq.send_file("/path/to/image.jpg")

# Monitor progress
while arq.statistics.tx_blocks_pending > 0:
    arq.process()
    time.sleep(0.1)
```

---

### Frame Processing

#### receive_frame()

```python
receive_frame(frame_bytes: bytes) -> None
```

Process a received frame.

**Parameters**:
- `frame_bytes` (bytes): Raw frame data received from modem

**Example**:
```python
# When modem receives data
def on_modem_rx(data: bytes):
    arq.receive_frame(data)

modem.set_rx_callback(on_modem_rx)
```

#### process()

```python
process() -> None
```

Process ARQ protocol state machine. Must be called regularly.

**Recommended**: Call every 100-200ms

**Example**:
```python
# Main loop
while True:
    arq.process()
    time.sleep(0.1)
```

---

### Callback Setters

#### set_send_callback()

```python
set_send_callback(callback: Callable[[bytes], None]) -> None
```

Set callback for frame transmission.

**Parameters**:
- `callback`: Function that takes frame bytes and transmits them

**Example**:
```python
def send_frame(frame: bytes):
    modem.transmit(frame)

arq.set_send_callback(send_frame)
```

#### set_rx_text_callback()

```python
set_rx_text_callback(callback: Callable[[str], None]) -> None
```

Set callback for received text.

**Parameters**:
- `callback`: Function that takes received text string

**Example**:
```python
def on_text(text: str):
    print(f"Received: {text}")

arq.set_rx_text_callback(on_text)
```

#### set_rx_file_callback()

```python
set_rx_file_callback(callback: Callable[[str, bytes], None]) -> None
```

Set callback for received files.

**Parameters**:
- `callback`: Function that takes filename (str) and file data (bytes)

**Example**:
```python
def on_file(filename: str, data: bytes):
    with open(filename, 'wb') as f:
        f.write(data)
    print(f"Saved {filename}")

arq.set_rx_file_callback(on_file)
```

#### set_status_callback()

```python
set_status_callback(callback: Callable[[str], None]) -> None
```

Set callback for status messages.

**Parameters**:
- `callback`: Function that takes status message string

**Example**:
```python
def on_status(msg: str):
    logging.info(f"ARQ: {msg}")

arq.set_status_callback(on_status)
```

---

### State Query Methods

#### is_connected()

```python
is_connected() -> bool
```

Check if connected to remote station.

**Returns**: True if connected, False otherwise

**Example**:
```python
if arq.is_connected():
    arq.send_text("Hello")
```

#### is_connecting()

```python
is_connecting() -> bool
```

Check if connection is in progress.

**Returns**: True if connecting, False otherwise

**Example**:
```python
if arq.is_connecting():
    print("Connection in progress...")
```

#### get_state()

```python
get_state() -> LinkState
```

Get current connection state.

**Returns**: Current LinkState

**Example**:
```python
state = arq.get_state()
if state == LinkState.ARQ_CONNECTED:
    print("Connected!")
```

---

### Properties

#### config

```python
@property
config -> ARQConfig
```

Access protocol configuration.

**Example**:
```python
arq.config.my_call = "W1ABC"
arq.config.retries = 10
```

#### state

```python
@property
state -> ARQStateMachine
```

Access state machine.

**Example**:
```python
print(f"Current state: {arq.state.current_state}")
```

#### statistics

```python
@property
statistics -> ARQStatistics
```

Access protocol statistics.

**Example**:
```python
stats = arq.statistics
print(f"TX: {stats.tx_blocks_total}, RX: {stats.rx_blocks_total}")
```

---

## ARQConfig

Configuration parameters for ARQ protocol.

### Constructor

```python
ARQConfig(
    my_call: str = "",
    exponent: int = 7,
    max_headers: int = 8,
    retry_time: int = 10000,
    retries: int = 5,
    tx_delay: int = 500,
    timeout: int = 60000,
    loop_time: int = 100,
    my_stream_id: str = "0"
)
```

**Parameters**:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `my_call` | str | "" | Local station callsign |
| `exponent` | int | 7 | Buffer length exponent (buffer = 2^exp) |
| `max_headers` | int | 8 | Max missing blocks to report |
| `retry_time` | int | 10000 | Milliseconds between retries |
| `retries` | int | 5 | Number of retry attempts |
| `tx_delay` | int | 500 | RX-to-TX turnaround delay (ms) |
| `timeout` | int | 60000 | Connection timeout (ms) |
| `loop_time` | int | 100 | Main loop timing interval (ms) |
| `my_stream_id` | str | "0" | Stream ID (0 = unknown) |

**Example**:
```python
config = ARQConfig()
config.my_call = "W1ABC"
config.exponent = 8        # 256 byte buffer
config.retries = 10        # More retries
config.timeout = 120000    # 2 minute timeout

arq = ARQProtocol(config=config)
```

---

### Properties

#### buffer_length

```python
@property
buffer_length -> int
```

Calculate buffer length from exponent.

**Returns**: 2^exponent

**Example**:
```python
config = ARQConfig()
config.exponent = 7
print(config.buffer_length)  # 128
```

#### max_payload_size

```python
@property
max_payload_size -> int
```

Maximum payload size in bytes.

**Returns**: min(512, buffer_length)

---

### Configuration Guidelines

**exponent** (buffer size):
- 4 = 16 bytes (very small, poor conditions)
- 5 = 32 bytes
- 6 = 64 bytes
- 7 = 128 bytes (default, good balance)
- 8 = 256 bytes (maximum, good conditions)

**retries**:
- 3-5: Quick timeout, testing
- 5-8: Normal operation (default: 5)
- 10+: Poor conditions, patient

**max_headers** (send window):
- 1-2: Sequential, reliable
- 4-8: Parallel, faster (default: 8)
- Higher numbers allow more blocks in flight

**timeout**:
- 30000 (30s): Quick timeout
- 60000 (60s): Default
- 120000+ (2min+): Poor conditions

---

## ARQStatistics

Statistics data class for monitoring ARQ performance.

### Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `tx_blocks_total` | int | Total blocks transmitted |
| `tx_blocks_pending` | int | Blocks waiting to send |
| `rx_blocks_total` | int | Total blocks received |
| `retransmissions` | int | Number of retransmissions |
| `crc_errors` | int | CRC checksum errors |
| `frames_sent` | int | Total frames sent |
| `frames_received` | int | Total frames received |

**Example**:
```python
stats = arq.statistics

print(f"Sent: {stats.tx_blocks_total} blocks")
print(f"Received: {stats.rx_blocks_total} blocks")
print(f"Retries: {stats.retransmissions}")
print(f"Errors: {stats.crc_errors}")

# Monitor transfer progress
if stats.tx_blocks_pending > 0:
    progress = 100 * (1 - stats.tx_blocks_pending / stats.tx_blocks_total)
    print(f"Progress: {progress:.1f}%")
```

---

## LinkState

Enumeration of ARQ connection states.

### States

| State | Value | Description |
|-------|-------|-------------|
| `DOWN` | 0 | No connection |
| `TIMEDOUT` | 1 | Connection timed out |
| `ABORT` | 2 | Transfer aborted |
| `ARQ_CONNECTING` | 3 | Connection in progress |
| `ARQ_CONNECTED` | 4 | Connected and ready |
| `WAITING` | 5 | Waiting for response |
| `WAITFORACK` | 6 | Waiting for acknowledgment |
| `DISCONNECT` | 7 | Disconnect requested |
| `DISCONNECTING` | 8 | Disconnection in progress |
| `ABORTING` | 9 | Abort in progress |
| `STOPPED` | 10 | Protocol stopped |

**Example**:
```python
from pydigi.arq import LinkState

state = arq.get_state()

if state == LinkState.DOWN:
    print("Not connected")
elif state == LinkState.ARQ_CONNECTING:
    print("Connecting...")
elif state == LinkState.ARQ_CONNECTED:
    print("Connected!")
elif state == LinkState.TIMEDOUT:
    print("Connection timeout")
```

### State Transitions

Normal connection flow:
```
DOWN → ARQ_CONNECTING → ARQ_CONNECTED
```

Normal disconnection flow:
```
ARQ_CONNECTED → DISCONNECT → DISCONNECTING → DOWN
```

Abort flow:
```
ARQ_CONNECTED → ABORTING → ABORT → ARQ_CONNECTED
```

Timeout flow:
```
ARQ_CONNECTING → TIMEDOUT → DOWN
ARQ_CONNECTED → TIMEDOUT → DOWN
```

---

## ARQStateMachine

State machine for ARQ protocol connection management.

### Methods

#### transition()

```python
transition(new_state: LinkState) -> None
```

Transition to a new state.

**Parameters**:
- `new_state` (LinkState): Target state

**Raises**:
- `ARQStateError`: If transition is not allowed

**Example**:
```python
# Generally called internally, but you can check validity
try:
    arq.state.transition(LinkState.ARQ_CONNECTED)
except ARQStateError as e:
    print(f"Invalid transition: {e}")
```

#### is_connected()

```python
is_connected() -> bool
```

Check if in a connected state.

**Returns**: True if connected

#### reset()

```python
reset() -> None
```

Reset to initial state (DOWN).

---

### Properties

#### current_state

```python
@property
current_state -> LinkState
```

Get current state.

**Example**:
```python
if arq.state.current_state == LinkState.ARQ_CONNECTED:
    print("Connected")
```

---

## Exceptions

ARQ-specific exception hierarchy.

### Exception Hierarchy

```
ARQError (base)
├── ARQFrameError
│   └── ARQCRCError
├── ARQTimeoutError
├── ARQConnectionError
├── ARQStateError
└── ARQAbortError
```

### ARQError

Base exception for all ARQ errors.

```python
class ARQError(Exception):
    """Base exception for ARQ protocol errors."""
```

### ARQFrameError

Raised for frame-related errors (parsing, validation).

```python
class ARQFrameError(ARQError):
    """Exception raised for frame-related errors."""
```

**When Raised**:
- Invalid frame format
- Missing frame components
- Malformed frame data

### ARQCRCError

Raised when CRC checksum validation fails.

```python
class ARQCRCError(ARQFrameError):
    """Exception raised when frame CRC validation fails."""
```

**When Raised**:
- CRC mismatch in received frame
- Corrupted data detected

**Note**: Usually handled internally with automatic retransmission.

### ARQTimeoutError

Raised when an operation times out.

```python
class ARQTimeoutError(ARQError):
    """Exception raised when ARQ operation times out."""
```

**When Raised**:
- Connection attempt timeout
- Data transfer timeout
- No response from remote station

### ARQConnectionError

Raised for connection-related errors.

```python
class ARQConnectionError(ARQError):
    """Exception raised for connection-related errors."""
```

**When Raised**:
- Connection refused by remote
- Connection already exists
- Connection failed

### ARQStateError

Raised for invalid state transitions or operations.

```python
class ARQStateError(ARQError):
    """Exception raised for invalid state transitions."""
```

**When Raised**:
- Calling `send_text()` when not connected
- Invalid state transition attempted
- Operation not valid in current state

**Example**:
```python
try:
    arq.send_text("Hello")
except ARQStateError:
    print("Not connected - connecting first")
    arq.connect("K6XYZ")
```

### ARQAbortError

Raised when a transfer is aborted.

```python
class ARQAbortError(ARQError):
    """Exception raised when transfer is aborted."""
```

**When Raised**:
- User calls `abort()`
- Remote station sends ABORT
- Transfer cancelled

---

## Supporting Classes

### BlockTracker

Internal class for tracking block sequence numbers with modulo-64 wrapping.

**Not part of public API** - used internally by ARQProtocol.

### ARQFrame

Internal class for building and parsing ARQ frames.

**Not part of public API** - used internally by ARQProtocol.

### CRC16

Internal class for CRC-16 checksum calculation.

**Not part of public API** - used internally by ARQProtocol.

### Base64Codec

Internal class for Base64 encoding/decoding files.

**Not part of public API** - used internally by ARQProtocol.

---

## Type Hints

For type checking, all public methods include type hints:

```python
from typing import Optional, Callable
from pydigi.arq import ARQProtocol, ARQConfig, LinkState

def create_arq(callsign: str) -> ARQProtocol:
    """Create ARQ instance."""
    config = ARQConfig()
    config.my_call = callsign
    return ARQProtocol(config=config)

def send_callback(frame: bytes) -> None:
    """Send frame callback."""
    print(f"Sending {len(frame)} bytes")

arq: ARQProtocol = create_arq("W1ABC")
arq.set_send_callback(send_callback)
```

---

## Compatibility Notes

### fldigi Compatibility

This implementation is compatible with fldigi's FLARQ:

- Frame format matches byte-for-byte
- CRC-16 calculation identical
- Block numbering and wrapping compatible
- File transfer format compatible
- Base64 encoding compatible

**Tested with**: fldigi 4.x FLARQ implementation

### Protocol Version

Implements K9PS ARQ Protocol Specification as used by fldigi.

---

## See Also

- [User Guide](user_guide.md) - Getting started and examples
- [Protocol Reference](protocol_reference.md) - Technical protocol details
- [Overview](overview.md) - Architecture and design
- [Testing Guide](testing_guide.md) - Testing strategies
