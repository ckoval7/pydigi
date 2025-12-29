# Session 8: Reception & Reassembly

**Duration**: 2-3 hours
**Priority**: HIGH
**Status**: 🔄 In Progress

## Goal

Validate and enhance text reception functionality for the ARQ protocol. This includes comprehensive testing of block reassembly, out-of-order handling, gap detection, and end-to-end text transfer.

## Prerequisites

- Sessions 1-7 complete (CRC, Frames, Blocks, Config/State, Protocol, Handlers, TX)
- Python 3.8+
- pytest installed
- fldigi source code available for reference

## Deliverables

1. Enhanced reception tests in `tests/test_arq/test_protocol.py`
2. End-to-end loopback tests
3. Integration test example in `examples/arq_loopback_test.py`
4. This session guide document

## Reception Flow Overview

The reception infrastructure is already implemented in `protocol.py` (`_handle_data()` method). This session validates and tests it thoroughly.

### Current Reception Flow

```
DATA frame received
    ↓
_handle_data() extracts block number
    ↓
Check for duplicates
    ↓
Add to _rx_pending queue
    ↓
Sort by block number (modulo-64)
    ↓
Update EndHeader (last received)
    ↓
Process consecutive blocks
    ↓
Add to _rx_queue, call RX callback
    ↓
Update GoodHeader
```

### Key Data Structures

**Reception Queues**:
- `_rx_pending`: Received blocks not yet consecutive (out-of-order)
- `_rx_queue`: Reassembled text ready for delivery
- `_rx_tracker`: Block tracking (GoodHeader, EndHeader)

**Block Tracking**:
- `GoodHeader`: Last consecutive block received (no gaps before this)
- `EndHeader`: Last block received (may have gaps)
- Missing blocks: Calculated as gaps between GoodHeader and EndHeader

## Implementation Steps

### Step 1: Review Existing Reception Code (15 minutes)

The `_handle_data()` method in `protocol.py` (lines 555-623) already implements:
- Duplicate detection
- Out-of-order block queuing
- Consecutive block processing
- GoodHeader/EndHeader tracking
- RX callback invocation

**Validation**: Read through `_handle_data()` and verify it matches the fldigi reference.

### Step 2: Create Reception Tests (60 minutes)

Add comprehensive tests to `tests/test_arq/test_protocol.py`:

```python
def test_receive_single_block():
    """Test receiving a single data block."""
    protocol = ARQProtocol()
    protocol.config.my_call = "W1ABC"
    protocol.state.transition_to(LinkState.ARQ_CONNECTED)

    # Track received text
    received_text = []
    protocol.set_rx_text_callback(lambda text: received_text.append(text))

    # Build DATA frame (block 0)
    frame = ARQFrame(
        protocol_version='0',
        stream_id='0',
        block_type=0,  # Block 0
        payload="Hello World"
    )

    # Receive frame
    protocol.receive_frame(frame.build())
    protocol.process()

    # Should have received text
    assert len(received_text) == 1
    assert received_text[0] == "Hello World"

    # Check block tracking
    assert protocol._rx_tracker.good_header == 0
    assert protocol._rx_tracker.end_header == 0
    assert len(protocol._rx_pending) == 0


def test_receive_consecutive_blocks():
    """Test receiving consecutive blocks in order."""
    protocol = ARQProtocol()
    protocol.config.my_call = "W1ABC"
    protocol.state.transition_to(LinkState.ARQ_CONNECTED)

    received_text = []
    protocol.set_rx_text_callback(lambda text: received_text.append(text))

    # Send 3 consecutive blocks
    for i in range(3):
        frame = ARQFrame(
            protocol_version='0',
            stream_id='0',
            block_type=i,
            payload=f"Block {i}"
        )
        protocol.receive_frame(frame.build())
        protocol.process()

    # Should have received all 3 blocks
    assert len(received_text) == 3
    assert received_text[0] == "Block 0"
    assert received_text[1] == "Block 1"
    assert received_text[2] == "Block 2"

    # GoodHeader should be at block 2
    assert protocol._rx_tracker.good_header == 2
    assert protocol._rx_tracker.end_header == 2


def test_receive_out_of_order_blocks():
    """Test receiving blocks out of order."""
    protocol = ARQProtocol()
    protocol.config.my_call = "W1ABC"
    protocol.state.transition_to(LinkState.ARQ_CONNECTED)

    received_text = []
    protocol.set_rx_text_callback(lambda text: received_text.append(text))

    # Receive blocks 0, 2, 1 (out of order)
    for block_num in [0, 2, 1]:
        frame = ARQFrame(
            protocol_version='0',
            stream_id='0',
            block_type=block_num,
            payload=f"Block {block_num}"
        )
        protocol.receive_frame(frame.build())
        protocol.process()

    # Should have received all 3 blocks in order
    assert len(received_text) == 3
    assert received_text[0] == "Block 0"
    assert received_text[1] == "Block 1"
    assert received_text[2] == "Block 2"

    # GoodHeader should be at block 2
    assert protocol._rx_tracker.good_header == 2


def test_receive_with_gaps():
    """Test receiving blocks with gaps (missing blocks)."""
    protocol = ARQProtocol()
    protocol.config.my_call = "W1ABC"
    protocol.state.transition_to(LinkState.ARQ_CONNECTED)

    received_text = []
    protocol.set_rx_text_callback(lambda text: received_text.append(text))

    # Receive blocks 0, 1, 3 (missing block 2)
    for block_num in [0, 1, 3]:
        frame = ARQFrame(
            protocol_version='0',
            stream_id='0',
            block_type=block_num,
            payload=f"Block {block_num}"
        )
        protocol.receive_frame(frame.build())
        protocol.process()

    # Should have received only blocks 0 and 1 (consecutive)
    assert len(received_text) == 2
    assert received_text[0] == "Block 0"
    assert received_text[1] == "Block 1"

    # GoodHeader should be at block 1 (last consecutive)
    assert protocol._rx_tracker.good_header == 1

    # EndHeader should be at block 3 (last received)
    assert protocol._rx_tracker.end_header == 3

    # Block 3 should be in pending queue
    assert len(protocol._rx_pending) == 1
    assert protocol._rx_pending[0]['block_num'] == 3

    # Missing blocks should be [2]
    missing = protocol._rx_tracker.get_missing_blocks()
    assert missing == [2]


def test_receive_fill_gap():
    """Test receiving a missing block to fill a gap."""
    protocol = ARQProtocol()
    protocol.config.my_call = "W1ABC"
    protocol.state.transition_to(LinkState.ARQ_CONNECTED)

    received_text = []
    protocol.set_rx_text_callback(lambda text: received_text.append(text))

    # Receive blocks 0, 1, 3 (missing block 2)
    for block_num in [0, 1, 3]:
        frame = ARQFrame(
            protocol_version='0',
            stream_id='0',
            block_type=block_num,
            payload=f"Block {block_num}"
        )
        protocol.receive_frame(frame.build())
        protocol.process()

    # Now receive block 2 to fill the gap
    frame = ARQFrame(
        protocol_version='0',
        stream_id='0',
        block_type=2,
        payload="Block 2"
    )
    protocol.receive_frame(frame.build())
    protocol.process()

    # Should have received all 4 blocks
    assert len(received_text) == 4
    assert received_text[0] == "Block 0"
    assert received_text[1] == "Block 1"
    assert received_text[2] == "Block 2"
    assert received_text[3] == "Block 3"

    # GoodHeader should be at block 3
    assert protocol._rx_tracker.good_header == 3

    # No blocks in pending
    assert len(protocol._rx_pending) == 0


def test_receive_duplicate_blocks():
    """Test that duplicate blocks are ignored."""
    protocol = ARQProtocol()
    protocol.config.my_call = "W1ABC"
    protocol.state.transition_to(LinkState.ARQ_CONNECTED)

    received_text = []
    protocol.set_rx_text_callback(lambda text: received_text.append(text))

    # Receive block 0 twice
    for _ in range(2):
        frame = ARQFrame(
            protocol_version='0',
            stream_id='0',
            block_type=0,
            payload="Block 0"
        )
        protocol.receive_frame(frame.build())
        protocol.process()

    # Should have received block 0 only once
    assert len(received_text) == 1
    assert received_text[0] == "Block 0"


def test_receive_wrapping_blocks():
    """Test receiving blocks that wrap at 64."""
    protocol = ARQProtocol()
    protocol.config.my_call = "W1ABC"
    protocol.state.transition_to(LinkState.ARQ_CONNECTED)

    # Set GoodHeader near the wrap boundary
    protocol._rx_tracker.good_header = 62

    received_text = []
    protocol.set_rx_text_callback(lambda text: received_text.append(text))

    # Receive blocks 63, 0, 1 (wrapping)
    for block_num in [63, 0, 1]:
        frame = ARQFrame(
            protocol_version='0',
            stream_id='0',
            block_type=block_num,
            payload=f"Block {block_num}"
        )
        protocol.receive_frame(frame.build())
        protocol.process()

    # Should have received all 3 blocks
    assert len(received_text) == 3
    assert received_text[0] == "Block 63"
    assert received_text[1] == "Block 0"
    assert received_text[2] == "Block 1"

    # GoodHeader should be at block 1
    assert protocol._rx_tracker.good_header == 1


### Step 3: Create End-to-End Loopback Tests (45 minutes)

Add loopback tests that send and receive through two protocol instances:

```python
def test_loopback_simple_text():
    """Test sending text from one protocol to another."""
    # Create two protocol instances
    sender = ARQProtocol()
    sender.config.my_call = "W1ABC"
    receiver = ARQProtocol()
    receiver.config.my_call = "K6XYZ"

    # Connect sender -> receiver callbacks
    sender.set_send_callback(lambda frame: receiver.receive_frame(frame))
    receiver.set_send_callback(lambda frame: sender.receive_frame(frame))

    # Track received text
    received_text = []
    receiver.set_rx_text_callback(lambda text: received_text.append(text))

    # Establish connection
    sender.connect("K6XYZ")
    sender.process()
    receiver.process()  # Receives CONREQ
    sender.process()    # Receives CONACK

    # Send text
    sender.send_text("Hello, World!")
    sender.process()    # Sends DATA + POLL
    receiver.process()  # Receives DATA, sends STATUS
    sender.process()    # Receives STATUS (acknowledges)

    # Check received text
    assert len(received_text) == 1
    assert received_text[0] == "Hello, World!"


def test_loopback_multiple_blocks():
    """Test sending multiple blocks through loopback."""
    sender = ARQProtocol()
    sender.config.my_call = "W1ABC"
    sender.config.exponent = 5  # 32-byte blocks for testing

    receiver = ARQProtocol()
    receiver.config.my_call = "K6XYZ"

    # Connect
    sender.set_send_callback(lambda frame: receiver.receive_frame(frame))
    receiver.set_send_callback(lambda frame: sender.receive_frame(frame))

    received_text = []
    receiver.set_rx_text_callback(lambda text: received_text.append(text))

    # Establish connection
    sender.connect("K6XYZ")
    for _ in range(5):
        sender.process()
        receiver.process()

    # Send long text (100 bytes = 4 blocks of 32 bytes)
    long_text = "A" * 100
    sender.send_text(long_text)

    # Process until all blocks received
    for _ in range(10):
        sender.process()
        receiver.process()

    # Reassemble received text
    full_text = "".join(received_text)
    assert full_text == long_text


def test_loopback_out_of_order():
    """Test that out-of-order delivery is handled correctly."""
    sender = ARQProtocol()
    sender.config.my_call = "W1ABC"
    sender.config.exponent = 5  # Small blocks

    receiver = ARQProtocol()
    receiver.config.my_call = "K6XYZ"

    # Create frame reorder buffer
    frame_buffer = []

    def reordering_callback(frame):
        """Buffer frames and deliver out of order."""
        frame_buffer.append(frame)

    sender.set_send_callback(reordering_callback)
    receiver.set_send_callback(lambda frame: sender.receive_frame(frame))

    received_text = []
    receiver.set_rx_text_callback(lambda text: received_text.append(text))

    # Establish connection
    sender.connect("K6XYZ")

    # Deliver CONREQ
    receiver.receive_frame(frame_buffer.pop(0))
    receiver.process()
    sender.process()

    # Send 3 blocks
    sender.send_text("Block0Block1Block2")
    sender.process()

    # Deliver frames out of order (skip control frames, reorder data)
    data_frames = [f for f in frame_buffer if len(f) > 20]
    if len(data_frames) >= 3:
        receiver.receive_frame(data_frames[0])  # Block 0
        receiver.receive_frame(data_frames[2])  # Block 2 (out of order)
        receiver.receive_frame(data_frames[1])  # Block 1 (fills gap)
        receiver.process()

    # Text should be reassembled in order
    full_text = "".join(received_text)
    assert "Block0" in full_text
    assert "Block1" in full_text
    assert "Block2" in full_text
```

### Step 4: Create Integration Example (30 minutes)

Create `examples/arq_loopback_test.py`:

```python
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
```

Make the file executable:
```bash
chmod +x examples/arq_loopback_test.py
```

## Testing

Run the test suite:

```bash
# Run all reception tests
pytest tests/test_arq/test_protocol.py -v -k "receive"

# Run loopback tests
pytest tests/test_arq/test_protocol.py -v -k "loopback"

# Run integration example
python examples/arq_loopback_test.py
```

## Validation Checklist

- [ ] Single block reception works correctly
- [ ] Multiple consecutive blocks received in order
- [ ] Out-of-order blocks are queued and reassembled correctly
- [ ] Gaps are detected and missing blocks identified
- [ ] Filling gaps triggers reassembly of queued blocks
- [ ] Duplicate blocks are ignored
- [ ] Block wrapping at 64 handled correctly
- [ ] Loopback test passes for simple text
- [ ] Loopback test passes for multiple blocks
- [ ] Out-of-order delivery handled in loopback
- [ ] Integration example runs successfully
- [ ] All tests pass

## Common Issues

1. **Modulo-64 wrapping**: Ensure block sorting handles wrap boundary correctly
2. **Gap detection**: Missing blocks between GoodHeader and EndHeader must be tracked
3. **Duplicate detection**: Check _rx_pending queue, not just GoodHeader
4. **Callback timing**: RX callback should fire when block is added to output, not when queued
5. **Block sorting**: Sort key must handle wrap boundary (blocks < GoodHeader get +64)

## Next Session

**Session 9: Retransmission & Error Recovery**
- Timeout handling for missing blocks
- Automatic retransmission requests
- Retry logic and limits
- Error recovery strategies

## References

- fldigi source: `fldigi/src/flarq-src/arq.cxx`
  - `rxTextFrame()`: lines 685-753 (reception logic)
  - `checkBlocks()`: lines 755-802 (gap detection)
  - `processQueue()`: lines 804-850 (reassembly)
- K9PS ARQ Specification: `fldigi/aux/ARQ2.pdf`
- IMPLEMENTATION_STATUS.md: Overall progress tracking
