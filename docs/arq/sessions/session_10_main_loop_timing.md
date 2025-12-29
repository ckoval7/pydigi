# Session 10: Main Loop & Timing

**Duration**: 3-4 hours
**Priority**: HIGH
**Status**: In Progress

## Goal

Complete the main loop timing implementation for the ARQ protocol. This includes:
- ID timer for keepalive frames
- Retry counter tracking for connection attempts
- TX delay (receive-to-transmit turnaround)
- Proper timing-based state transitions

## Prerequisites

- Sessions 1-9 complete
- Understanding of fldigi timing model
- Reference: `fldigi/src/flarq-src/arq.cxx` (arqloop function)

## Background

The ARQ protocol uses a 100ms loop timer (ARQLOOPTIME) for all timing operations. Timing counters are decremented each loop iteration, and actions are triggered when counters reach zero.

### Timing Features in fldigi

From `arq.cxx` analysis:

1. **ID Timer (_idtimer)**: Sends keepalive TALK frames when idle
   - Set to `(idtimer * 60 - 10) * 1000 / ARQLOOPTIME` or default 10 minutes
   - Decremented each loop iteration
   - When reaches 0, sends `talkFrame("auto ID")`
   - Reset after sending any frame

2. **Timeout Counter (timeout)**: Connection/transfer timeout
   - Set to `Timeout / ARQLOOPTIME` (default: 60000ms / 100ms = 600 iterations)
   - Decremented each loop iteration
   - When reaches 0 during CONNECTING/DISCONNECTING, transitions to TIMEDOUT → DOWN

3. **Retry Counter (retries)**: Connection retry attempts
   - Tracks number of retry attempts remaining
   - Decremented when timeout occurs during CONNECTING
   - If retries remain, resets timeout and tries again
   - If no retries, gives up

4. **TX Delay (tx2txdelay)**: RX-to-TX turnaround delay
   - Set to `TxDelay / ARQLOOPTIME` (default: 500ms / 100ms = 5 iterations)
   - Prevents transmitting immediately after receiving
   - Allows time for radio to switch from RX to TX mode

## Current State

From `pydigi/arq/protocol.py`:

**Already Implemented:**
- ✅ Basic `process()` method (lines 959-995)
- ✅ Timeout counter (`_timeout_counter`)
- ✅ Retry counter (`_retry_counter`) - but only for block retransmissions
- ✅ Timeout handling (`_handle_timeout()`)
- ✅ Block retry logic in `_send_blocks()`

**Missing:**
- ❌ ID timer for keepalive
- ❌ Connection retry counter (distinct from block retry)
- ❌ TX delay implementation
- ❌ Comprehensive timing tests

## Deliverables

1. **Enhanced protocol.py**:
   - Add `_id_timer` counter
   - Add `_connection_retries` counter
   - Add `_tx_delay` counter
   - Implement ID timer logic in `process()`
   - Implement connection retry logic
   - Implement TX delay logic

2. **Test file**: `tests/test_arq/test_timing.py`
   - Test ID timer triggering
   - Test connection retry logic
   - Test TX delay
   - Test timeout transitions

3. **Updated loopback test**: Validate timing in real scenario

## Implementation Steps

### Step 1: Add Timing Counters to ARQProtocol.__init__()

Add these counters to the `__init__` method in `protocol.py`:

```python
# Timing counters (in loop iterations)
self._retry_counter = 0          # Block retry timer (already exists)
self._timeout_counter = 0        # Connection timeout timer (already exists)
self._id_timer = 0               # Keepalive ID timer (NEW)
self._tx_delay_counter = 0       # RX-to-TX delay (NEW)
self._connection_retries = 0     # Connection retry attempts (NEW)
```

### Step 2: Implement set_id_timer() Method

Add method to reset ID timer (called after sending any frame):

```python
def _set_id_timer(self, minutes: Optional[int] = None) -> None:
    """Set or reset the ID timer for keepalive frames.

    Args:
        minutes: Minutes until next ID frame (default: 10)
    """
    if minutes is None:
        minutes = 10  # Default 10 minutes

    # Convert to loop iterations: (minutes * 60 - 10) seconds * 1000ms / loop_time
    self._id_timer = ((minutes * 60 - 10) * 1000) // self.config.loop_time
```

### Step 3: Update _send_frame() to Reset ID Timer

Modify `_send_frame()` to reset ID timer after sending:

```python
def _send_frame(self, frame: ARQFrame) -> None:
    """Send a frame via callback.

    Args:
        frame: ARQFrame object to send
    """
    if self._send_callback:
        frame_bytes = frame.build()
        self._send_callback(frame_bytes)
        self.stats.total_tx += 1

        # Reset ID timer after sending any frame
        self._set_id_timer()

        # Call TX callback if set
        if self._tx_text_callback:
            self._tx_text_callback(f"TX: {frame}")
```

### Step 4: Implement _send_talk() Method

Add method to send TALK frames (used for keepalive):

```python
def _send_talk(self, message: str = "auto ID") -> None:
    """Send TALK frame for keepalive/identification.

    Args:
        message: Message to include in TALK frame
    """
    # Build payload: "MYCALL:port message"
    payload = f"{self.config.my_call}:0 {message}"

    # Truncate to buffer length if needed
    if len(payload) > self.config.buffer_length:
        payload = payload[:self.config.buffer_length]

    frame = ARQFrame(
        protocol_version='0',
        stream_id=self._my_stream_id,
        block_type=TALK,
        payload=payload
    )

    self._send_frame(frame)
```

### Step 5: Enhance process() Method

Update the `process()` method to include all timing logic:

```python
def process(self) -> None:
    """Process one iteration of the ARQ protocol.

    This should be called regularly (every 100ms recommended).
    Processes received frames, handles timeouts, and sends blocks.
    """
    # Decrement ID timer (keepalive)
    if self._id_timer > 0:
        self._id_timer -= 1
        if self._id_timer == 0 and self.state.is_connected():
            # Send keepalive TALK frame
            self._send_talk("auto ID")
            # Timer will be reset by _send_frame()

    # Decrement TX delay counter
    if self._tx_delay_counter > 0:
        self._tx_delay_counter -= 1

    # Process received frames
    self._process_frames()

    # Check if we can transmit (TX delay expired)
    can_transmit = self._tx_delay_counter == 0

    # Send blocks if immediate flag set or in appropriate state
    if can_transmit and (self._immediate or (
        self.state.is_connected() and
        (self._tx_blocks or self._tx_missing)
    )):
        self._send_blocks()
        self._immediate = False

        # Reset retry counter
        self._retry_counter = self.config.retry_time // self.config.loop_time

    # Update timeout counter
    if self._timeout_counter > 0:
        self._timeout_counter -= 1

        if self._timeout_counter == 0:
            self._handle_timeout()

    # Update retry counter for block retransmissions
    if self._retry_counter > 0:
        self._retry_counter -= 1

        if self._retry_counter == 0:
            # Retry sending blocks
            if can_transmit and self.state.is_connected() and (self._tx_blocks or self._tx_missing):
                self._send_blocks()
                self._retry_counter = self.config.retry_time // self.config.loop_time
```

### Step 6: Enhance _process_frame() to Set TX Delay

Update `_process_frame()` to set TX delay after receiving:

```python
def _process_frame(self, frame_bytes: bytes) -> None:
    """Process a single received frame.

    Args:
        frame_bytes: Complete frame bytes to process
    """
    try:
        # Parse frame
        frame = ARQFrame.parse(frame_bytes)

        # Set TX delay - wait before transmitting after receiving
        self._tx_delay_counter = self.config.tx_delay // self.config.loop_time

        # Route to appropriate handler based on block type
        block_type = frame.block_type

        # ... rest of existing code ...
```

### Step 7: Enhance _handle_timeout() with Retry Logic

Update timeout handler to support connection retries:

```python
def _handle_timeout(self) -> None:
    """Handle timeout event."""
    if self.state.state == LinkState.ARQ_CONNECTING:
        # Connection timeout - check if we should retry
        if self._connection_retries > 0:
            self._connection_retries -= 1
            self._emit_status(f"Connection timeout, retrying... ({self._connection_retries} attempts left)")

            # Resend CONREQ
            block_length_char = chr(ord('0') + self.config.exponent)
            timeout_sec = self.config.timeout // 1000

            payload = (
                f"{self.config.my_call}:0 {self._ur_call}:0 "
                f"{self._my_stream_id} {block_length_char} "
                f"T{timeout_sec}R{self.config.retries}W{self.config.retry_time // 1000}"
            )

            frame = ARQFrame(
                protocol_version='0',
                stream_id=self._my_stream_id,
                block_type=CONREQ,
                payload=payload
            )

            self._send_frame(frame)

            # Reset timeout counter
            self._timeout_counter = self.config.timeout // self.config.loop_time
        else:
            # No retries left, give up
            self.state.transition_to(LinkState.TIMEDOUT)
            self.state.transition_to(LinkState.DOWN)
            self._emit_status("Connection timed out (no retries left)")

    elif self.state.state == LinkState.DISCONNECTING:
        # Disconnect timeout
        self.state.transition_to(LinkState.TIMEDOUT)
        self.state.transition_to(LinkState.DOWN)
        self._emit_status("Disconnect timed out")
```

### Step 8: Update connect() to Initialize Retry Counter

Modify `connect()` to set connection retry counter:

```python
def connect(self, remote_call: str) -> None:
    """Initiate connection to remote station.

    Args:
        remote_call: Remote station callsign

    Raises:
        ARQStateError: If not in DOWN state
        ARQConnectionError: If my_call not configured
    """
    # ... existing validation code ...

    # Update state
    self.state.transition_to(LinkState.ARQ_CONNECTING)
    self._ur_call = remote_call.upper()

    # Initialize connection retry counter
    self._connection_retries = self.config.retries - 1  # First attempt + retries

    # ... rest of existing code ...

    # Start timeout counter
    self._timeout_counter = self.config.timeout // self.config.loop_time

    # Initialize ID timer
    self._set_id_timer()
```

### Step 9: Create Timing Tests

Create `tests/test_arq/test_timing.py`:

```python
"""Tests for ARQ protocol timing features."""

import pytest
from pydigi.arq import ARQProtocol, ARQConfig
from pydigi.arq.frame import ARQFrame, CONREQ, TALK, DISREQ


def test_id_timer_initialization():
    """Test that ID timer is initialized on connection."""
    protocol = ARQProtocol()
    protocol.config.my_call = "W1ABC"

    # Connect should initialize ID timer
    protocol.connect("K6XYZ")

    # ID timer should be set (10 minutes - 10 seconds in loop iterations)
    expected_iterations = ((10 * 60 - 10) * 1000) // protocol.config.loop_time
    assert protocol._id_timer == expected_iterations


def test_id_timer_sends_talk_frame():
    """Test that ID timer sends TALK frame when expired."""
    protocol = ARQProtocol()
    protocol.config.my_call = "W1ABC"

    sent_frames = []
    protocol.set_send_callback(lambda f: sent_frames.append(f))

    # Set up connected state
    protocol.state.transition_to(protocol.state.ARQ_CONNECTED)

    # Set ID timer to expire soon
    protocol._id_timer = 1

    # Process - should not send yet
    protocol.process()
    assert len(sent_frames) == 0
    assert protocol._id_timer == 0

    # Process again - should send TALK frame
    protocol.process()
    assert len(sent_frames) == 1

    # Verify it's a TALK frame
    frame = ARQFrame.parse(sent_frames[0])
    assert frame.block_type == TALK
    assert "auto ID" in frame.payload


def test_id_timer_reset_on_send():
    """Test that ID timer resets after sending any frame."""
    protocol = ARQProtocol()
    protocol.config.my_call = "W1ABC"

    sent_frames = []
    protocol.set_send_callback(lambda f: sent_frames.append(f))

    # Connect
    protocol.connect("K6XYZ")
    assert len(sent_frames) == 1  # CONREQ sent

    # ID timer should be reset
    expected_iterations = ((10 * 60 - 10) * 1000) // protocol.config.loop_time
    assert protocol._id_timer == expected_iterations


def test_tx_delay_after_receive():
    """Test that TX delay is set after receiving frame."""
    protocol = ARQProtocol()
    protocol.config.my_call = "W1ABC"
    protocol.state.transition_to(protocol.state.ARQ_CONNECTED)

    # Receive a frame
    conreq = ARQFrame(
        protocol_version='0',
        stream_id='0',
        block_type=CONREQ,
        payload="K6XYZ:0 W1ABC:0 0 7"
    )

    protocol.receive_frame(conreq.build())
    protocol._process_frames()

    # TX delay should be set
    expected_delay = protocol.config.tx_delay // protocol.config.loop_time
    assert protocol._tx_delay_counter == expected_delay


def test_tx_delay_prevents_transmission():
    """Test that TX delay prevents immediate transmission."""
    protocol = ARQProtocol()
    protocol.config.my_call = "W1ABC"

    sent_frames = []
    protocol.set_send_callback(lambda f: sent_frames.append(f))

    # Set up connected state with data to send
    protocol.state.transition_to(protocol.state.ARQ_CONNECTED)
    protocol._ur_call = "K6XYZ"
    protocol.send_text("Hello")

    initial_count = len(sent_frames)

    # Set TX delay
    protocol._tx_delay_counter = 5

    # Process - should not send due to TX delay
    protocol.process()
    assert len(sent_frames) == initial_count  # No new frames
    assert protocol._tx_delay_counter == 4

    # Run until TX delay expires
    for _ in range(4):
        protocol.process()

    # Now should send
    assert protocol._tx_delay_counter == 0
    protocol.process()
    assert len(sent_frames) > initial_count  # Frame sent


def test_connection_timeout_with_retries():
    """Test connection retry logic on timeout."""
    config = ARQConfig()
    config.my_call = "W1ABC"
    config.timeout = 1000  # 1 second
    config.retries = 3

    protocol = ARQProtocol(config=config)

    sent_frames = []
    protocol.set_send_callback(lambda f: sent_frames.append(f))

    # Connect
    protocol.connect("K6XYZ")
    assert len(sent_frames) == 1  # Initial CONREQ

    # Should have retries set
    assert protocol._connection_retries == 2  # retries - 1

    # Run until timeout
    timeout_iterations = config.timeout // config.loop_time
    for _ in range(timeout_iterations):
        protocol.process()

    # Should have retried (sent another CONREQ)
    assert len(sent_frames) == 2
    assert protocol._connection_retries == 1

    # Verify it's still connecting
    assert protocol.state.is_connecting()


def test_connection_timeout_exhausted():
    """Test that connection fails after all retries exhausted."""
    config = ARQConfig()
    config.my_call = "W1ABC"
    config.timeout = 500  # 0.5 seconds
    config.retries = 1  # Only one attempt total

    protocol = ARQProtocol(config=config)

    sent_frames = []
    protocol.set_send_callback(lambda f: sent_frames.append(f))

    # Connect
    protocol.connect("K6XYZ")
    assert len(sent_frames) == 1  # Initial CONREQ
    assert protocol._connection_retries == 0  # No retries

    # Run until timeout
    timeout_iterations = config.timeout // config.loop_time
    for _ in range(timeout_iterations + 1):
        protocol.process()

    # Should not have retried
    assert len(sent_frames) == 1

    # Should be DOWN
    assert not protocol.is_connected()
    assert not protocol.is_connecting()


def test_block_retry_timing():
    """Test that block retry counter works correctly."""
    config = ARQConfig()
    config.retry_time = 1000  # 1 second
    config.my_call = "W1ABC"

    protocol = ARQProtocol(config=config)

    sent_frames = []
    protocol.set_send_callback(lambda f: sent_frames.append(f))

    # Set up connected state
    protocol.state.transition_to(protocol.state.ARQ_CONNECTED)
    protocol._ur_call = "K6XYZ"

    # Send text
    protocol.send_text("Test")

    # Process once to send initial blocks
    protocol.process()
    initial_count = len(sent_frames)

    # Retry counter should be set
    retry_iterations = config.retry_time // config.loop_time
    assert protocol._retry_counter == retry_iterations

    # Process until retry
    for _ in range(retry_iterations):
        protocol.process()

    # Should have sent blocks again
    assert len(sent_frames) > initial_count
```

### Step 10: Update Loopback Test

Enhance `examples/arq_loopback_test.py` to validate timing:

```python
# Add to end of main():

# Test 6: Timing validation
print("Test 6: Timing validation...")

# Reset stations
station_a.disconnect()
for i in range(5):
    station_a.process()
    station_b.process()

# Create fresh connections
station_a = ARQProtocol()
station_a.config.my_call = "W1ABC"
station_b = ARQProtocol()
station_b.config.my_call = "K6XYZ"

station_a.set_send_callback(lambda frame: station_b.receive_frame(frame))
station_b.set_send_callback(lambda frame: station_a.receive_frame(frame))

# Check ID timer is set on connection
station_a.connect("K6XYZ")
for i in range(5):
    station_a.process()
    station_b.process()

if station_a._id_timer > 0 and station_b._id_timer > 0:
    print("✓ ID timers initialized\n")
else:
    print("✗ ID timers not set\n")

# Check TX delay after receiving
initial_delay = station_a._tx_delay_counter
station_a.send_text("X")
station_a.process()
station_b.process()

if station_b._tx_delay_counter > 0:
    print("✓ TX delay set after receive\n")
else:
    print("✗ TX delay not set\n")

print("=== Timing Tests Complete ===")
```

## Validation Checkpoint

Session 10 is complete when:

1. ✅ All timing counters added to `ARQProtocol.__init__()`
2. ✅ ID timer implementation working
3. ✅ TX delay prevents immediate transmission after RX
4. ✅ Connection retry logic implemented
5. ✅ All tests in `test_timing.py` pass
6. ✅ Loopback test validates timing features
7. ✅ No regressions in existing tests

Run tests:
```bash
# Run new timing tests
pytest tests/test_arq/test_timing.py -v

# Run all ARQ tests to check for regressions
pytest tests/test_arq/ -v

# Run loopback test
python examples/arq_loopback_test.py
```

## Common Pitfalls

1. **Off-by-one errors**: Counter decrements happen BEFORE zero check
2. **Integer division**: Use `//` for loop iteration calculations
3. **Timer reset timing**: Reset ID timer AFTER sending frame, not before
4. **TX delay vs retry timer**: These are different - don't confuse them
5. **Connection retries vs block retries**: Track these separately

## Reference Files

- `fldigi/src/flarq-src/arq.cxx`: Lines with `arqloop()`, `_idtimer`, `tx2txdelay`
- `fldigi/src/flarq-src/include/arq.h`: Timer definitions and `ARQLOOPTIME`

## Next Session

**Session 11: Base64 & File Transfer** - Implement Base64 encoding and file transfer support.
