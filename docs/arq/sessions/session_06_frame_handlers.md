# Session 6: Frame Handler Stubs

**Duration**: 2-3 hours
**Priority**: HIGH
**Status**: In Progress

## Goal

Implement the remaining frame handlers that were left as stubs in Session 5. These handlers process received frames for data transmission, status reporting, polling, and identification.

## Prerequisites

- Session 1-5 complete (CRC, Frames, Blocks, Config/State, Protocol)
- Python 3.8+
- pytest installed
- fldigi source code available for reference

## Deliverables

1. Updated `pydigi/arq/protocol.py` - Implement frame handlers
2. Updated `tests/test_arq/test_protocol.py` - Add handler tests
3. This session guide document

## Frame Handler Overview

### Handlers to Implement

| Handler | Purpose | Complexity | Priority |
|---------|---------|------------|----------|
| `_handle_ident` | Process IDENT frames (keepalive) | Low | Medium |
| `_handle_poll` | Process POLL frames (status request) | Low | High |
| `_handle_status` | Process STATUS frames (block tracking) | High | Critical |
| `_handle_data` | Process DATA frames (text blocks) | High | Critical |

### Frame Type Summary

**IDENT (0x69)**: Identification/keepalive frame
- Sent periodically when connected but idle
- Resets timeout counter
- Triggers STATUS response

**POLL (0x70)**: Poll for status
- Requests immediate STATUS response
- Used to check link health
- Triggers STATUS response

**STATUS (0x73)**: Status report
- Contains block tracking information
- Lists missing blocks for retransmission
- Updates transmit queue based on remote acknowledgments
- Payload format: `[LastHeader][GoodHeader][EndHeader][Missing...]`

**DATA (0x20-0x3F)**: Data block
- Contains text payload
- Block number encoded in frame type (0x20 + block_num)
- Must be reassembled in order
- Missing blocks detected and requested

## Implementation Steps

### Step 1: Add Helper Methods (20 minutes)

Add helper methods to send STATUS and IDENT frames.

**Reference**: `fldigi/src/flarq-src/arq.cxx` - lines 430-480 (statFrame, identFrame)

Add to `protocol.py` after existing helper methods:

```python
    def _send_status(self) -> None:
        """Send STATUS frame with current block tracking info."""
        # Build status payload
        # Format: [LastHeader][GoodHeader][EndHeader][Missing blocks...]
        payload = chr(0x20 + self._tx_tracker.last_sent)
        payload += chr(0x20 + self._tx_tracker.last_consecutive)
        payload += chr(0x20 + self._rx_tracker.last_received)

        # Add missing blocks to payload
        missing = self._rx_tracker.get_missing()
        for block_num in missing:
            payload += chr(0x20 + block_num)

        frame = ARQFrame(
            protocol_version='0',
            stream_id=self._my_stream_id,
            block_type=STATUS,
            payload=payload
        )

        self._send_frame(frame)

    def _send_ident(self) -> None:
        """Send IDENT frame."""
        frame = ARQFrame(
            protocol_version='0',
            stream_id=self._my_stream_id,
            block_type=IDENT,
            payload=''
        )

        self._send_frame(frame)
```

### Step 2: Implement IDENT Handler (15 minutes)

**Purpose**: Process IDENT frames to maintain connection.

**Reference**: `fldigi/src/flarq-src/arq.cxx` line 606

```python
    def _handle_ident(self, frame: ARQFrame) -> None:
        """Handle IDENT frame.

        IDENT frames are sent periodically when connected but idle.
        They serve as keepalives and request STATUS responses.

        Args:
            frame: Parsed IDENT frame
        """
        # Reset timeout counter
        self._timeout_counter = self.config.timeout // self.config.loop_time

        # Send STATUS response
        self._send_status()

        # Mark for immediate transmission
        self._immediate = True

        self._emit_status("IDENT received")
```

### Step 3: Implement POLL Handler (15 minutes)

**Purpose**: Process POLL frames to respond with STATUS.

**Reference**: `fldigi/src/flarq-src/arq.cxx` line 885

```python
    def _handle_poll(self, frame: ARQFrame) -> None:
        """Handle POLL frame.

        POLL frames request an immediate STATUS response.

        Args:
            frame: Parsed POLL frame
        """
        # Ignore if not in active state
        if self.state.state in {
            LinkState.DISCONNECTING,
            LinkState.DOWN,
            LinkState.TIMEDOUT,
            LinkState.ABORTING
        }:
            return

        # Send STATUS response
        self._send_status()

        # Mark for immediate transmission
        self._immediate = True

        # Ensure we're in CONNECTED state
        if self.state.can_transition_to(LinkState.ARQ_CONNECTED):
            self.state.transition_to(LinkState.ARQ_CONNECTED)

        self._emit_status("POLL received")
```

### Step 4: Implement STATUS Handler (45 minutes)

**Purpose**: Process STATUS frames to manage retransmissions and acknowledgments.

**Reference**: `fldigi/src/flarq-src/arq.cxx` line 800

```python
    def _handle_status(self, frame: ARQFrame) -> None:
        """Handle STATUS frame.

        STATUS frames contain the remote station's block tracking info:
        - LastHeader: Last block they sent
        - GoodHeader: Last consecutive block they received from us
        - EndHeader: Last block they received from us (may have gaps)
        - Missing: List of blocks they're missing from us

        Args:
            frame: Parsed STATUS frame
        """
        if not self.state.is_connected():
            return

        payload = frame.payload

        # Must have at least 3 bytes (LastHeader, GoodHeader, EndHeader)
        if len(payload) < 3:
            self._emit_status("Invalid STATUS payload")
            return

        # Parse remote station's block tracking info
        ur_last_sent = ord(payload[0]) - 0x20
        ur_good_header = ord(payload[1]) - 0x20
        ur_end_header = ord(payload[2]) - 0x20

        # Store remote station's info
        self._ur_last_sent = ur_last_sent
        self._ur_good_header = ur_good_header
        self._ur_end_header = ur_end_header

        # Parse missing blocks list from remote
        ur_missing = []
        for i in range(3, len(payload)):
            block_num = ord(payload[i]) - 0x20
            ur_missing.append(block_num)

        # Build complete missing list
        # Include explicitly reported missing blocks
        missing = list(ur_missing)

        # Also include blocks between EndHeader and our LastSent that weren't acknowledged
        if ur_end_header != self._tx_tracker.last_sent:
            m = ur_end_header + 1
            if m > 63:
                m -= 64

            while m != self._tx_tracker.last_sent:
                missing.append(m)
                m += 1
                if m > 63:
                    m -= 64

            # Add the last sent block too
            missing.append(self._tx_tracker.last_sent)

        # Update TxMissing queue - keep only blocks that are still missing
        if not missing:
            # All blocks acknowledged, clear missing queue
            self._tx_missing.clear()
        else:
            # Keep only blocks that are in the missing list
            self._tx_missing = [b for b in self._tx_missing if b['block_num'] in missing]

        # Process TxPending queue - remove blocks up to and including GoodHeader
        # These have been successfully received by remote station
        while self._tx_pending:
            block = self._tx_pending[0]
            if block['block_num'] <= ur_good_header or \
               (ur_good_header < 10 and block['block_num'] > 50):  # Handle wrap
                # Block acknowledged, remove from pending
                self._tx_pending.pop(0)

                # Call TX callback to show transmitted text
                if self._tx_text_callback:
                    self._tx_text_callback(block['text'])
            else:
                break
```

### Step 5: Implement DATA Handler (60 minutes)

**Purpose**: Process DATA frames containing text blocks.

**Reference**: `fldigi/src/flarq-src/arq.cxx` line 897

```python
    def _handle_data(self, frame: ARQFrame) -> None:
        """Handle DATA frame.

        DATA frames contain text blocks. Blocks must be reassembled in order.
        Block number is encoded in the block_type (0x20 + block_num).

        Args:
            frame: Parsed DATA frame
        """
        if not self.state.is_connected():
            return

        # Extract block number from block type
        block_num = ord(frame.block_type) - 0x20

        # Check for duplicate (already received)
        for pending in self._rx_pending:
            if pending['block_num'] == block_num:
                # Duplicate, ignore
                return

        self._emit_status(f"RX: data block {block_num}")

        # Add to pending queue
        self._rx_pending.append({
            'block_num': block_num,
            'text': frame.payload
        })

        # Sort pending blocks by block number (with modulo-64 handling)
        def sort_key(block):
            num = block['block_num']
            # Adjust for wrap boundary
            if num < self._rx_tracker.last_consecutive:
                num += 64
            return num

        self._rx_pending.sort(key=sort_key)

        # Update EndHeader (last received, possibly with gaps)
        if self._rx_pending:
            self._rx_tracker.last_received = self._rx_pending[-1]['block_num']
        else:
            self._rx_tracker.last_received = self._rx_tracker.last_consecutive

        # Process consecutive blocks from pending queue
        while self._rx_pending:
            block = self._rx_pending[0]
            next_expected = (self._rx_tracker.last_consecutive + 1) % 64

            if block['block_num'] != next_expected:
                # Gap in sequence, stop processing
                break

            # Block is next in sequence
            self._rx_pending.pop(0)

            # Add text to receive queue
            self._rx_queue.append(block['text'])

            # Update GoodHeader
            self._rx_tracker.last_consecutive = block['block_num']

            # Call RX callback
            if self._rx_text_callback:
                self._rx_text_callback(block['text'])

        # Update missing blocks list
        self._update_missing_blocks()

    def _update_missing_blocks(self) -> None:
        """Update list of missing received blocks.

        This is called after processing DATA frames to determine which
        blocks are missing between GoodHeader and EndHeader.
        """
        if not self._rx_pending:
            # No gaps, clear missing list
            self._rx_tracker.clear_missing()
            return

        # Find missing blocks between GoodHeader+1 and EndHeader
        start = (self._rx_tracker.last_consecutive + 1) % 64
        end = self._rx_tracker.last_received

        # Adjust for wrap
        if end < start:
            end += 64

        missing = []
        for i in range(start, end + 1):
            test_num = i % 64

            # Check if block is in pending queue
            found = False
            for pending in self._rx_pending:
                if pending['block_num'] == test_num:
                    found = True
                    break

            if not found:
                missing.append(test_num)

        # Update tracker
        for block_num in missing:
            self._rx_tracker.add_missing(block_num)
```

### Step 6: Add Instance Variables (10 minutes)

Add required instance variables to `__init__` method:

```python
        # Add to existing __init__ method
        self._immediate = False  # Flag for immediate transmission
        self._tx_pending: List[dict] = []  # Sent blocks pending acknowledgment
        self._rx_pending: List[dict] = []  # Received blocks (not consecutive)
        self._tx_missing: List[dict] = []  # Blocks needing retransmission

        # Remote station's block tracking
        self._ur_last_sent = 0
        self._ur_good_header = 0
        self._ur_end_header = 0
```

### Step 7: Update Tests (30 minutes)

Add tests for the new handlers to `tests/test_arq/test_protocol.py`:

```python
    def test_handle_ident(self):
        """Test IDENT frame handler."""
        config = ARQConfig(my_call="W1AW")
        protocol = ARQProtocol(config=config)

        sent_frames = []
        protocol.set_send_callback(lambda f: sent_frames.append(f))

        # Put in connected state
        protocol.state.transition_to(LinkState.ARQ_CONNECTING, force=True)
        protocol.state.transition_to(LinkState.ARQ_CONNECTED)

        # Receive IDENT frame
        frame = ARQFrame(
            protocol_version='0',
            stream_id='5',
            block_type=IDENT,
            payload=''
        )

        protocol._handle_ident(frame)

        # Should send STATUS
        assert len(sent_frames) == 1
        assert sent_frames[0].block_type == STATUS
        assert protocol._immediate == True

    def test_handle_poll(self):
        """Test POLL frame handler."""
        config = ARQConfig(my_call="W1AW")
        protocol = ARQProtocol(config=config)

        sent_frames = []
        protocol.set_send_callback(lambda f: sent_frames.append(f))

        # Put in connected state
        protocol.state.transition_to(LinkState.ARQ_CONNECTING, force=True)
        protocol.state.transition_to(LinkState.ARQ_CONNECTED)

        # Receive POLL frame
        frame = ARQFrame(
            protocol_version='0',
            stream_id='5',
            block_type=POLL,
            payload=''
        )

        protocol._handle_poll(frame)

        # Should send STATUS
        assert len(sent_frames) == 1
        assert sent_frames[0].block_type == STATUS
        assert protocol._immediate == True

    def test_handle_status(self):
        """Test STATUS frame handler."""
        config = ARQConfig(my_call="W1AW")
        protocol = ARQProtocol(config=config)

        # Put in connected state
        protocol.state.transition_to(LinkState.ARQ_CONNECTING, force=True)
        protocol.state.transition_to(LinkState.ARQ_CONNECTED)

        # Simulate having sent some blocks
        protocol._tx_tracker.last_sent = 5
        protocol._tx_pending = [
            {'block_num': 3, 'text': 'Block 3'},
            {'block_num': 4, 'text': 'Block 4'},
            {'block_num': 5, 'text': 'Block 5'},
        ]

        # Receive STATUS indicating remote received up to block 4
        payload = chr(0x20 + 5)  # UrLastSent
        payload += chr(0x20 + 4)  # UrGoodHeader (received 0-4 consecutively)
        payload += chr(0x20 + 4)  # UrEndHeader (last received is 4)

        frame = ARQFrame(
            protocol_version='0',
            stream_id='5',
            block_type=STATUS,
            payload=payload
        )

        protocol._handle_status(frame)

        # Blocks 3 and 4 should be removed from pending
        assert len(protocol._tx_pending) == 1
        assert protocol._tx_pending[0]['block_num'] == 5

    def test_handle_data(self):
        """Test DATA frame handler."""
        config = ARQConfig(my_call="W1AW")
        protocol = ARQProtocol(config=config)

        rx_text = []
        protocol.set_rx_text_callback(lambda t: rx_text.append(t))

        # Put in connected state
        protocol.state.transition_to(LinkState.ARQ_CONNECTING, force=True)
        protocol.state.transition_to(LinkState.ARQ_CONNECTED)

        # Receive block 1 (next expected)
        frame = ARQFrame(
            protocol_version='0',
            stream_id='5',
            block_type=chr(0x20 + 1),
            payload='Hello, '
        )

        protocol._handle_data(frame)

        # Should process immediately (consecutive)
        assert len(rx_text) == 1
        assert rx_text[0] == 'Hello, '
        assert protocol._rx_tracker.last_consecutive == 1
        assert len(protocol._rx_pending) == 0

    def test_handle_data_out_of_order(self):
        """Test DATA frame handler with out-of-order blocks."""
        config = ARQConfig(my_call="W1AW")
        protocol = ARQProtocol(config=config)

        rx_text = []
        protocol.set_rx_text_callback(lambda t: rx_text.append(t))

        # Put in connected state
        protocol.state.transition_to(LinkState.ARQ_CONNECTING, force=True)
        protocol.state.transition_to(LinkState.ARQ_CONNECTED)

        # Receive block 3 (out of order)
        frame = ARQFrame(
            protocol_version='0',
            stream_id='5',
            block_type=chr(0x20 + 3),
            payload='World!'
        )

        protocol._handle_data(frame)

        # Should be pending, not processed yet
        assert len(rx_text) == 0
        assert len(protocol._rx_pending) == 1

        # Now receive block 1
        frame = ARQFrame(
            protocol_version='0',
            stream_id='5',
            block_type=chr(0x20 + 1),
            payload='Hello '
        )

        protocol._handle_data(frame)

        # Block 1 processed, block 3 still pending
        assert len(rx_text) == 1
        assert rx_text[0] == 'Hello '
        assert len(protocol._rx_pending) == 1

        # Receive block 2
        frame = ARQFrame(
            protocol_version='0',
            stream_id='5',
            block_type=chr(0x20 + 2),
            payload='there, '
        )

        protocol._handle_data(frame)

        # All blocks should process in order
        assert len(rx_text) == 3
        assert rx_text == ['Hello ', 'there, ', 'World!']
        assert len(protocol._rx_pending) == 0
        assert protocol._rx_tracker.last_consecutive == 3
```

### Step 8: Run Tests (10 minutes)

```bash
# Test protocol handlers
pytest tests/test_arq/test_protocol.py::TestARQProtocol::test_handle_ident -v
pytest tests/test_arq/test_protocol.py::TestARQProtocol::test_handle_poll -v
pytest tests/test_arq/test_protocol.py::TestARQProtocol::test_handle_status -v
pytest tests/test_arq/test_protocol.py::TestARQProtocol::test_handle_data -v
pytest tests/test_arq/test_protocol.py::TestARQProtocol::test_handle_data_out_of_order -v

# Run all protocol tests
pytest tests/test_arq/test_protocol.py -v

# Check coverage
pytest tests/test_arq/test_protocol.py --cov=pydigi.arq.protocol --cov-report=term-missing
```

## Validation Checkpoint

### Frame Handlers
- ✅ `_handle_ident` implemented and sends STATUS
- ✅ `_handle_poll` implemented and sends STATUS
- ✅ `_handle_status` implemented and manages retransmissions
- ✅ `_handle_data` implemented and reassembles blocks
- ✅ Helper methods `_send_status` and `_send_ident` implemented
- ✅ Out-of-order block handling works correctly
- ✅ Missing block detection works
- ✅ Block acknowledgment works
- ✅ All new tests pass (8+ tests)

### Integration
- ✅ Handlers integrate with BlockTracker
- ✅ Handlers use callbacks appropriately
- ✅ State machine checked before processing
- ✅ Modulo-64 arithmetic handled correctly

### Overall
- ✅ All frame handler stubs now functional
- ✅ Ready for Session 7 (text transmission)
- ✅ Ready for Session 8 (full reception flow)

## Common Pitfalls

1. **Block Number Encoding**: Block numbers are encoded as ASCII (0x20 + block_num), not binary
2. **Modulo-64 Arithmetic**: Always use % 64 and check for wrap boundaries
3. **Sorting with Wrap**: When sorting blocks, adjust numbers < GoodHeader by adding 64
4. **Duplicate Detection**: Always check if block already in pending queue
5. **Consecutive Processing**: Only process blocks that are next in sequence
6. **Missing Block Detection**: Account for wrap boundary when finding gaps

## Reference Files

### fldigi Source
- `fldigi/src/flarq-src/arq.cxx` - Lines 606-970 for handler implementations
  - `parseIDENT()` - Line 606
  - `parsePOLL()` - Line 885
  - `parseSTATUS()` - Line 800
  - `parseDATA()` - Line 897

### Previous Sessions
- Session 1: CRC-16 implementation
- Session 2: Frame building/parsing
- Session 3: Block tracking
- Session 4: Config & State Machine
- Session 5: Protocol skeleton & connection

## Next Steps

After completing Session 6, proceed to:

**Session 7: Text Transmission** - Implement sending text data and managing transmit queue

**Session 8: Reception & Reassembly** - Complete the receive path with full text reassembly

## Estimated Time Breakdown

- Step 1 (Helper Methods): 20 minutes
- Step 2 (IDENT Handler): 15 minutes
- Step 3 (POLL Handler): 15 minutes
- Step 4 (STATUS Handler): 45 minutes
- Step 5 (DATA Handler): 60 minutes
- Step 6 (Instance Variables): 10 minutes
- Step 7 (Tests): 30 minutes
- Step 8 (Validation): 10 minutes

**Total**: ~3 hours
