# Session 7: Text Transmission

**Duration**: 2-3 hours
**Priority**: CRITICAL
**Status**: ✅ Complete

## Goal

Implement text transmission functionality for the ARQ protocol. This includes breaking text into blocks, queuing them for transmission, sending data frames, and integrating with the main loop.

## Prerequisites

- Sessions 1-6 complete (CRC, Frames, Blocks, Config/State, Protocol, Handlers)
- Python 3.8+
- pytest installed
- fldigi source code available for reference

## Deliverables

1. Updated `pydigi/arq/protocol.py` - Add text transmission methods
2. Updated `tests/test_arq/test_protocol.py` - Add transmission tests
3. This session guide document

## Text Transmission Overview

### Transmission Flow

```
User calls send_text()
    ↓
Text broken into blocks (max buffer_length each)
    ↓
Blocks queued in _tx_blocks
    ↓
process() calls _send_blocks() periodically
    ↓
Blocks sent as DATA frames
    ↓
Blocks moved to _tx_pending (awaiting ACK)
    ↓
STATUS frame received with acknowledgments
    ↓
Acknowledged blocks removed from _tx_pending
```

### Key Data Structures

**Transmission Queues**:
- `_tx_blocks`: New blocks waiting to be sent
- `_tx_pending`: Blocks sent but not yet acknowledged
- `_tx_missing`: Blocks needing retransmission (populated from STATUS)

**Block Structure**:
```python
{
    'block_num': int,      # Block number (0-63)
    'text': str,           # Block payload
}
```

## Implementation Steps

### Step 1: Add send_text() Method (30 minutes)

This is the public API for sending text over the ARQ link.

**Reference**: `fldigi/src/flarq-src/arq.cxx` lines 1165-1180

Add to `protocol.py` after the `_send_ident()` method:

```python
    def send_text(self, text: str) -> None:
        """Queue text for transmission over ARQ link.

        Breaks text into blocks and queues them for transmission.
        Text will be sent when connected.

        Args:
            text: Text to send

        Raises:
            ARQConnectionError: If not connected
        """
        if not self.state.is_connected():
            raise ARQConnectionError("Cannot send text: not connected")

        # Break text into buffer-sized chunks
        buffer_length = self.config.buffer_length
        offset = 0
        blocks_added = 0

        while offset < len(text):
            # Get next chunk
            chunk = text[offset:offset + buffer_length]

            # Get next block number
            block_num = self._tx_tracker.next_block_number()

            # Add to transmission queue
            block = {
                'block_num': block_num,
                'text': chunk
            }
            self._tx_blocks.append(block)
            blocks_added += 1

            offset += buffer_length

        self._emit_status(f"Queued {blocks_added} blocks for transmission")
```

**What this does**:
- Validates connection state
- Breaks text into `buffer_length` chunks (default 128 bytes)
- Gets sequential block numbers from tracker
- Queues blocks for transmission
- Emits status message

### Step 2: Add _send_data_frame() Helper (15 minutes)

Helper method to send a single data block frame.

**Reference**: `fldigi/src/flarq-src/arq.cxx` lines 592-604

Add after `_send_ident()`:

```python
    def _send_data_frame(self, block: dict) -> None:
        """Send a data block frame.

        Args:
            block: Block dictionary with 'block_num' and 'text'
        """
        # Build DATA frame
        # Block type is block_num (0-63)
        frame = ARQFrame(
            protocol_version='0',
            stream_id=self._my_stream_id,
            block_type=block['block_num'],  # 0-63 for data blocks
            payload=block['text']
        )

        self._send_frame(frame)
```

### Step 3: Add _send_blocks() Method (45 minutes)

Main transmission logic - sends queued blocks.

**Reference**: `fldigi/src/flarq-src/arq.cxx` lines 1182-1221

Add after `send_text()`:

```python
    def _send_blocks(self) -> None:
        """Send queued data blocks.

        Sends missing blocks first (retransmissions), then new blocks.
        Limits total frames sent to max_headers to avoid flooding.
        """
        if not self.state.is_connected():
            return

        frames_sent = 0
        retransmissions = 0
        new_blocks = 0

        # First, send missing blocks (retransmissions)
        while self._tx_missing and frames_sent < self.config.max_headers:
            block = self._tx_missing.pop(0)
            self._send_data_frame(block)
            frames_sent += 1
            retransmissions += 1

        # Then send new blocks from queue
        while self._tx_blocks and frames_sent < self.config.max_headers:
            block = self._tx_blocks.pop(0)

            # Check if send window is full
            # Don't send if we're 2 blocks ahead of remote's GoodHeader
            # This prevents buffer overflow at receiver
            if (block['block_num'] + 2) % 64 == self._ur_good_header:
                # Window full, put block back
                self._tx_blocks.insert(0, block)
                break

            # Send the block
            self._send_data_frame(block)

            # Add to pending and missing queues
            self._tx_pending.append(block)
            self._tx_missing.append(block)

            # Update tracker
            self._tx_tracker.last_sent = block['block_num']

            frames_sent += 1
            new_blocks += 1

        # Send POLL if we sent anything
        if frames_sent > 0:
            self._send_poll()

        # Update status
        if frames_sent > 0:
            self._emit_status(
                f"TX: retransmit {retransmissions}, new {new_blocks}"
            )

        # Update state
        if self._tx_missing or self._tx_blocks:
            # Still have data to send
            if self.state.can_transition_to(LinkState.WAITING):
                self.state.transition_to(LinkState.WAITING)
```

**What this does**:
- Sends missing blocks first (retransmissions have priority)
- Sends new blocks up to `max_headers` limit (default 8)
- Checks send window to prevent buffer overflow
- Moves blocks to pending/missing queues
- Updates block tracker
- Sends POLL frame to request acknowledgment
- Transitions to WAITING state

### Step 4: Add _send_poll() Helper (10 minutes)

Helper to send POLL frame requesting STATUS.

Add after `_send_ident()`:

```python
    def _send_poll(self) -> None:
        """Send POLL frame to request STATUS."""
        frame = ARQFrame(
            protocol_version='0',
            stream_id=self._my_stream_id,
            block_type=POLL,
            payload=''
        )

        self._send_frame(frame)
```

### Step 5: Update process() to Call _send_blocks() (15 minutes)

Integrate transmission into main loop.

**Reference**: `fldigi/src/flarq-src/arq.cxx` lines 1302-1492 (arqloop)

Update the `process()` method in `protocol.py`:

```python
    def process(self) -> None:
        """Process one iteration of the ARQ protocol.

        This should be called regularly (every 100ms recommended).
        Processes received frames, handles timeouts, and sends blocks.
        """
        # Process received frames
        self._process_frames()

        # Send blocks if immediate flag set or in appropriate state
        if self._immediate or (
            self.state.is_connected() and
            (self._tx_blocks or self._tx_missing)
        ):
            self._send_blocks()
            self._immediate = False

            # Reset retry counter
            self._retry_counter = self.config.retry_time // self.config.loop_time

        # Update timeout counters
        if self._timeout_counter > 0:
            self._timeout_counter -= 1

            if self._timeout_counter == 0:
                self._handle_timeout()

        # Update retry counters
        if self._retry_counter > 0:
            self._retry_counter -= 1

            if self._retry_counter == 0:
                # Retry sending blocks
                if self.state.is_connected() and (self._tx_blocks or self._tx_missing):
                    self._send_blocks()
                    self._retry_counter = self.config.retry_time // self.config.loop_time
```

### Step 6: Update __init__() for New Attributes (10 minutes)

Add initialization for transmission queues.

Update the `__init__` method around line 88:

```python
        # Frame handler state
        self._immediate = False  # Flag for immediate transmission
        self._tx_pending: List[dict] = []  # Sent blocks pending acknowledgment
        self._rx_pending: List[dict] = []  # Received blocks (not consecutive)
        self._tx_missing: List[dict] = []  # Blocks needing retransmission
        self._tx_blocks: List[dict] = []   # NEW: Blocks queued for transmission
```

### Step 7: Create Tests (45 minutes)

Create comprehensive tests for text transmission.

Add to `tests/test_arq/test_protocol.py`:

```python
def test_send_text_single_block():
    """Test sending text that fits in one block."""
    protocol = ARQProtocol()
    protocol.config.my_call = "W1ABC"

    # Track sent frames
    sent_frames = []
    protocol.set_send_callback(lambda frame: sent_frames.append(frame))

    # Connect first
    protocol.connect("K6XYZ")
    sent_frames.clear()

    # Force connected state
    protocol.state.transition_to(LinkState.ARQ_CONNECTED)

    # Send short text
    protocol.send_text("Hello World")

    # Should have queued one block
    assert len(protocol._tx_blocks) == 1
    assert protocol._tx_blocks[0]['text'] == "Hello World"
    assert protocol._tx_blocks[0]['block_num'] == 0  # First block


def test_send_text_multiple_blocks():
    """Test sending text that requires multiple blocks."""
    protocol = ARQProtocol()
    protocol.config.my_call = "W1ABC"
    protocol.config.exponent = 5  # 32 byte buffers for testing
    protocol.state.transition_to(LinkState.ARQ_CONNECTED)

    # Send text longer than buffer
    long_text = "A" * 100  # 100 bytes, needs 4 blocks of 32 bytes
    protocol.send_text(long_text)

    # Should have queued 4 blocks
    assert len(protocol._tx_blocks) == 4
    assert protocol._tx_blocks[0]['text'] == "A" * 32
    assert protocol._tx_blocks[1]['text'] == "A" * 32
    assert protocol._tx_blocks[2]['text'] == "A" * 32
    assert protocol._tx_blocks[3]['text'] == "A" * 4

    # Block numbers should be sequential
    assert protocol._tx_blocks[0]['block_num'] == 0
    assert protocol._tx_blocks[1]['block_num'] == 1
    assert protocol._tx_blocks[2]['block_num'] == 2
    assert protocol._tx_blocks[3]['block_num'] == 3


def test_send_blocks():
    """Test _send_blocks() method."""
    protocol = ARQProtocol()
    protocol.config.my_call = "W1ABC"
    protocol.state.transition_to(LinkState.ARQ_CONNECTED)

    # Track sent frames
    sent_frames = []
    protocol.set_send_callback(lambda frame: sent_frames.append(frame))

    # Queue some blocks
    protocol.send_text("Block 1")
    protocol.send_text("Block 2")

    # Send blocks
    protocol._send_blocks()

    # Should have sent 2 DATA frames + 1 POLL frame
    assert len(sent_frames) == 3

    # Parse frames
    frame1 = ARQFrame.parse(sent_frames[0])
    frame2 = ARQFrame.parse(sent_frames[1])
    frame3 = ARQFrame.parse(sent_frames[2])

    # First two should be DATA frames
    assert frame1.block_type == 0  # Block 0
    assert frame1.payload == "Block 1"
    assert frame2.block_type == 1  # Block 1
    assert frame2.payload == "Block 2"

    # Last should be POLL
    assert frame3.block_type == POLL

    # Blocks should be in pending queue
    assert len(protocol._tx_pending) == 2
    assert len(protocol._tx_missing) == 2


def test_send_blocks_with_retransmission():
    """Test that missing blocks are sent first."""
    protocol = ARQProtocol()
    protocol.config.my_call = "W1ABC"
    protocol.state.transition_to(LinkState.ARQ_CONNECTED)

    sent_frames = []
    protocol.set_send_callback(lambda frame: sent_frames.append(frame))

    # Add a missing block (simulating retransmission request)
    protocol._tx_missing.append({
        'block_num': 5,
        'text': "Missing block"
    })

    # Add new blocks
    protocol.send_text("New block")

    # Send blocks
    protocol._send_blocks()

    # Should send missing block first
    frame1 = ARQFrame.parse(sent_frames[0])
    assert frame1.block_type == 5
    assert frame1.payload == "Missing block"

    # Then new block
    frame2 = ARQFrame.parse(sent_frames[1])
    assert frame2.block_type == 0
    assert frame2.payload == "New block"


def test_send_blocks_respects_window():
    """Test that send window is respected."""
    protocol = ARQProtocol()
    protocol.config.my_call = "W1ABC"
    protocol.state.transition_to(LinkState.ARQ_CONNECTED)

    # Set remote's good header to indicate limited window
    protocol._ur_good_header = 60  # Almost at block 0

    # Try to send block 62 (would be 2 ahead)
    protocol._tx_blocks.append({
        'block_num': 62,
        'text': "Block 62"
    })

    sent_frames = []
    protocol.set_send_callback(lambda frame: sent_frames.append(frame))

    # Send blocks
    protocol._send_blocks()

    # Block should not be sent (window full)
    data_frames = [f for f in sent_frames if ARQFrame.parse(f).block_type < 64]
    assert len(data_frames) == 0

    # Block should still be in queue
    assert len(protocol._tx_blocks) == 1


def test_send_text_not_connected():
    """Test that send_text() fails when not connected."""
    protocol = ARQProtocol()
    protocol.config.my_call = "W1ABC"

    # Try to send without connecting
    with pytest.raises(ARQConnectionError):
        protocol.send_text("Hello")


def test_process_sends_blocks():
    """Test that process() calls _send_blocks()."""
    protocol = ARQProtocol()
    protocol.config.my_call = "W1ABC"
    protocol.state.transition_to(LinkState.ARQ_CONNECTED)

    sent_frames = []
    protocol.set_send_callback(lambda frame: sent_frames.append(frame))

    # Queue text
    protocol.send_text("Test")

    # Call process
    protocol.process()

    # Should have sent block
    assert len(sent_frames) > 0
```

## Testing

Run the test suite:

```bash
# Run all ARQ tests
pytest tests/test_arq/ -v

# Run just transmission tests
pytest tests/test_arq/test_protocol.py::test_send_text_single_block -v
pytest tests/test_arq/test_protocol.py::test_send_text_multiple_blocks -v
pytest tests/test_arq/test_protocol.py::test_send_blocks -v
```

## Validation Checklist

- [ ] `send_text()` breaks text into correctly-sized blocks
- [ ] Block numbers are sequential with modulo-64 wrapping
- [ ] `_send_blocks()` sends missing blocks first
- [ ] Send window is respected (doesn't overflow receiver)
- [ ] POLL frame is sent after data blocks
- [ ] Blocks are added to pending/missing queues
- [ ] `process()` triggers block transmission
- [ ] All tests pass
- [ ] Test coverage > 80%

## Common Issues

1. **Block wrapping**: Block numbers wrap at 64, not 63
2. **Window check**: Must check `(block_num + 2) % 64` against `ur_good_header`
3. **Missing blocks**: TxMissing should be sent before new blocks
4. **POLL frame**: Always send POLL after data blocks to get acknowledgment
5. **State management**: Only send when in CONNECTED or WAITING state

## Next Session

**Session 8: Reception & Reassembly**
- Text reassembly from received blocks
- Out-of-order block handling
- Gap detection and repair
- End-to-end text transfer testing

## References

- fldigi source: `fldigi/src/flarq-src/arq.cxx`
  - `sendText()`: lines 1165-1180
  - `sendblocks()`: lines 1182-1221
  - `textFrame()`: lines 592-604
  - `transmitdata()`: lines 1273-1292
  - `arqloop()`: lines 1302-1492
- K9PS ARQ Specification: `fldigi/aux/ARQ2.pdf`
- IMPLEMENTATION_STATUS.md: Overall progress tracking
