# Session 5: Protocol Skeleton & Connection

**Duration**: 3-4 hours
**Priority**: HIGH
**Status**: In Progress

## Goal

Create the main ARQ protocol class with connection/disconnection logic. This is the core class that ties together all the components built in Sessions 1-4.

## Prerequisites

- Session 1 complete (CRC-16)
- Session 2 complete (Frame Builder/Parser)
- Session 3 complete (Block Tracking)
- Session 4 complete (Config & State Machine)
- Python 3.8+
- pytest installed

## Deliverables

1. `pydigi/arq/protocol.py` - Main ARQ protocol class
2. `tests/test_arq/test_protocol.py` - Protocol tests
3. Updated `pydigi/arq/__init__.py` - Export protocol class

## Implementation Steps

### Step 1: Create Protocol Class Skeleton (30 minutes)

Create `pydigi/arq/protocol.py` with the main protocol class structure.

**Reference**: `fldigi/src/flarq-src/include/arq.h` lines 180-399

```python
"""Main ARQ protocol implementation for FLARQ."""

import time
from typing import Optional, Callable, List
from dataclasses import dataclass

from .config import ARQConfig
from .state_machine import ARQStateMachine, LinkState
from .frame import FrameBuilder, FrameParser
from .blocks import BlockTracker
from .crc import calculate_crc16
from .exceptions import (
    ARQError,
    ARQConnectionError,
    ARQTimeoutError,
    ARQStateError,
)


# Frame type constants (from K9PS ARQ spec)
IDENT = 'i'
CONREQ = 'c'
CONACK = 'k'
REFUSED = 'r'
DISREQ = 'd'
STATUS = 's'
POLL = 'p'
FMTFAIL = 'f'
# FLARQ extensions
ABORT = 'a'
ACKABORT = 'o'
DISACK = 'b'
UNPROTO = 'u'
TALK = 't'


@dataclass
class ARQStatistics:
    """Statistics for ARQ link."""
    total_tx: int = 0
    total_rx: int = 0
    bad_rx: int = 0  # CRC errors
    bad_tx: int = 0  # Retransmissions
    avg_payload_length: int = 0


class ARQProtocol:
    """Main ARQ protocol implementation.

    This class implements the FLARQ ARQ protocol for reliable data transfer
    over unreliable radio links.

    Reference: fldigi/src/flarq-src/arq.cxx
    """

    def __init__(
        self,
        config: Optional[ARQConfig] = None,
        send_callback: Optional[Callable[[str], None]] = None,
    ):
        """Initialize ARQ protocol.

        Args:
            config: Protocol configuration (uses defaults if None)
            send_callback: Callback to send frames (takes frame string)
        """
        self.config = config or ARQConfig()
        self.state = ARQStateMachine()

        # Callbacks
        self._send_callback = send_callback
        self._rx_text_callback: Optional[Callable[[str], None]] = None
        self._tx_text_callback: Optional[Callable[[str], None]] = None
        self._status_callback: Optional[Callable[[str], None]] = None

        # Frame builder/parser
        self._frame_builder = FrameBuilder()
        self._frame_parser = FrameParser()

        # Block tracking
        self._tx_tracker = BlockTracker()
        self._rx_tracker = BlockTracker()

        # Statistics
        self.stats = ARQStatistics()

        # Stream ID
        self._my_stream_id = self.config.my_stream_id
        self._ur_stream_id = '0'

        # Timing counters (in loop iterations)
        self._retry_counter = 0
        self._timeout_counter = 0

        # Queues
        self._tx_queue: List[str] = []  # Outgoing text
        self._rx_queue: List[str] = []  # Received text
        self._frame_queue: List[str] = []  # Received frames to process

        # Connection state
        self._ur_call = ""  # Remote callsign from connection
        self._ur_block_length_char = '7'  # Remote block length

    def set_send_callback(self, callback: Callable[[str], None]) -> None:
        """Set callback for sending frames.

        Args:
            callback: Function that takes frame string and sends it
        """
        self._send_callback = callback

    def set_rx_text_callback(self, callback: Callable[[str], None]) -> None:
        """Set callback for received text.

        Args:
            callback: Function that receives decoded text
        """
        self._rx_text_callback = callback

    def set_tx_text_callback(self, callback: Callable[[str], None]) -> None:
        """Set callback for transmitted text.

        Args:
            callback: Function that receives transmitted text
        """
        self._tx_text_callback = callback

    def set_status_callback(self, callback: Callable[[str], None]) -> None:
        """Set callback for status messages.

        Args:
            callback: Function that receives status messages
        """
        self._status_callback = callback

    def _send_frame(self, frame: str) -> None:
        """Send a frame via callback.

        Args:
            frame: Complete frame to send
        """
        if self._send_callback:
            self._send_callback(frame)
            self.stats.total_tx += 1

            # Call TX callback if set
            if self._tx_text_callback:
                self._tx_text_callback(f"TX: {frame}")

    def _emit_status(self, message: str) -> None:
        """Emit status message via callback.

        Args:
            message: Status message
        """
        if self._status_callback:
            self._status_callback(message)

    # Connection Methods

    def connect(self, remote_call: str) -> None:
        """Initiate connection to remote station.

        Args:
            remote_call: Remote station callsign

        Raises:
            ARQStateError: If not in DOWN state
            ARQConnectionError: If my_call not configured
        """
        if not self.state.can_transition_to(LinkState.ARQ_CONNECTING):
            raise ARQStateError("Cannot connect: not in DOWN state")

        if not self.config.my_call:
            raise ARQConnectionError("my_call must be configured before connecting")

        # Update state
        self.state.transition_to(LinkState.ARQ_CONNECTING)
        self._ur_call = remote_call.upper()

        # Build CONREQ payload
        # Format: "MYCALL:port URCALL:port StreamID BlockLengthChar T60R5W10"
        block_length_char = chr(ord('0') + self.config.exponent)
        timeout_sec = self.config.timeout // 1000
        retry_sec = self.config.retry_time // 1000

        payload = (
            f"{self.config.my_call}:0 {self._ur_call}:0 "
            f"{self._my_stream_id} {block_length_char} "
            f"T{timeout_sec}R{self.config.retries}W{retry_sec}"
        )

        # Build and send CONREQ frame
        frame = self._frame_builder.build_control_frame(
            protocol_version='0',
            stream_id=self._my_stream_id,
            block_type=CONREQ,
            data='',
            payload=payload
        )

        self._send_frame(frame)
        self._emit_status(f"Connecting to {self._ur_call}...")

        # Start timeout counter
        self._timeout_counter = self.config.timeout // self.config.loop_time

    def disconnect(self) -> None:
        """Initiate disconnection from remote station.

        Raises:
            ARQStateError: If not in connected state
        """
        if not self.state.is_connected():
            raise ARQStateError("Cannot disconnect: not connected")

        # Update state
        self.state.transition_to(LinkState.DISCONNECT)

        # Build and send DISREQ frame
        frame = self._frame_builder.build_control_frame(
            protocol_version='0',
            stream_id=self._my_stream_id,
            block_type=DISREQ,
            data='',
            payload=''
        )

        self._send_frame(frame)
        self._emit_status("Disconnecting...")

        # Transition to disconnecting
        self.state.transition_to(LinkState.DISCONNECTING)

        # Start timeout counter
        self._timeout_counter = self.config.timeout // self.config.loop_time

    def abort(self) -> None:
        """Abort current transfer.

        Can be called from any state.
        """
        # Transition to aborting
        if self.state.can_transition_to(LinkState.ABORTING):
            self.state.transition_to(LinkState.ABORTING)
        else:
            self.state.transition_to(LinkState.ABORTING, force=True)

        # Build and send ABORT frame
        frame = self._frame_builder.build_control_frame(
            protocol_version='0',
            stream_id=self._my_stream_id,
            block_type=ABORT,
            data='',
            payload=''
        )

        self._send_frame(frame)
        self._emit_status("Aborting transfer...")

    # Frame Reception

    def receive_frame(self, frame: str) -> None:
        """Receive and queue a frame for processing.

        Args:
            frame: Complete frame received
        """
        self._frame_queue.append(frame)
        self.stats.total_rx += 1

    def _process_frames(self) -> None:
        """Process all queued frames."""
        while self._frame_queue:
            frame = self._frame_queue.pop(0)
            self._process_frame(frame)

    def _process_frame(self, frame: str) -> None:
        """Process a single received frame.

        Args:
            frame: Complete frame to process
        """
        try:
            # Parse frame
            parsed = self._frame_parser.parse(frame)

            # Route to appropriate handler based on block type
            block_type = parsed['block_type']

            if block_type == CONREQ:
                self._handle_conreq(parsed)
            elif block_type == CONACK:
                self._handle_conack(parsed)
            elif block_type == REFUSED:
                self._handle_refused(parsed)
            elif block_type == DISREQ:
                self._handle_disreq(parsed)
            elif block_type == DISACK:
                self._handle_disack(parsed)
            elif block_type == ABORT:
                self._handle_abort(parsed)
            elif block_type == ACKABORT:
                self._handle_ackabort(parsed)
            elif block_type == STATUS:
                self._handle_status(parsed)
            elif block_type == POLL:
                self._handle_poll(parsed)
            elif block_type == IDENT:
                self._handle_ident(parsed)
            elif block_type == UNPROTO:
                self._handle_unproto(parsed)
            elif block_type == TALK:
                self._handle_talk(parsed)
            else:
                # Data frame (block number 0x20-0x3F)
                if 0x20 <= ord(block_type) <= 0x3F:
                    self._handle_data(parsed)
                else:
                    # Unknown frame type
                    self._emit_status(f"Unknown frame type: {block_type}")

        except Exception as e:
            self.stats.bad_rx += 1
            self._emit_status(f"Frame processing error: {e}")

    # Frame Handlers (stubs for now, will be implemented in later sessions)

    def _handle_conreq(self, parsed: dict) -> None:
        """Handle CONREQ frame.

        Args:
            parsed: Parsed frame data
        """
        # Parse payload
        # Format: "MYCALL:port URCALL:port StreamID BlockLengthChar ..."
        payload = parsed['payload']
        parts = payload.split()

        if len(parts) < 4:
            self._emit_status("Invalid CONREQ payload")
            return

        # Extract remote info
        remote_call = parts[0].split(':')[0]
        self._ur_call = remote_call
        self._ur_stream_id = parts[2]
        self._ur_block_length_char = parts[3]

        # Check if we're available
        if self.state.state != LinkState.DOWN:
            # Already connected or connecting, refuse
            self._send_refused()
            return

        # Accept connection
        self.state.transition_to(LinkState.ARQ_CONNECTING)
        self._send_conack()
        self.state.transition_to(LinkState.ARQ_CONNECTED)

        self._emit_status(f"Connected to {self._ur_call}")

    def _handle_conack(self, parsed: dict) -> None:
        """Handle CONACK frame.

        Args:
            parsed: Parsed frame data
        """
        if self.state.state != LinkState.ARQ_CONNECTING:
            return

        # Parse payload to get remote parameters
        payload = parsed['payload']
        parts = payload.split()

        if len(parts) >= 4:
            self._ur_stream_id = parts[2]
            self._ur_block_length_char = parts[3]

        # Connection established
        self.state.transition_to(LinkState.ARQ_CONNECTED)
        self._emit_status(f"Connected to {self._ur_call}")

    def _handle_refused(self, parsed: dict) -> None:
        """Handle REFUSED frame.

        Args:
            parsed: Parsed frame data
        """
        if self.state.state == LinkState.ARQ_CONNECTING:
            self.state.transition_to(LinkState.DOWN)
            self._emit_status(f"Connection refused by {self._ur_call}")

    def _handle_disreq(self, parsed: dict) -> None:
        """Handle DISREQ frame.

        Args:
            parsed: Parsed frame data
        """
        if self.state.is_connected():
            # Send DISACK
            self._send_disack()

            # Disconnect
            self.state.reset()
            self._emit_status("Disconnected by remote")

    def _handle_disack(self, parsed: dict) -> None:
        """Handle DISACK frame.

        Args:
            parsed: Parsed frame data
        """
        if self.state.is_disconnecting():
            self.state.transition_to(LinkState.DOWN)
            self._emit_status("Disconnected")

    def _handle_abort(self, parsed: dict) -> None:
        """Handle ABORT frame - stub for Session 9."""
        self._emit_status("Abort received")

    def _handle_ackabort(self, parsed: dict) -> None:
        """Handle ACKABORT frame - stub for Session 9."""
        self._emit_status("Abort acknowledged")

    def _handle_status(self, parsed: dict) -> None:
        """Handle STATUS frame - stub for Session 8."""
        pass

    def _handle_poll(self, parsed: dict) -> None:
        """Handle POLL frame - stub for Session 8."""
        pass

    def _handle_ident(self, parsed: dict) -> None:
        """Handle IDENT frame - stub for Session 7."""
        pass

    def _handle_unproto(self, parsed: dict) -> None:
        """Handle UNPROTO frame - stub for future."""
        pass

    def _handle_talk(self, parsed: dict) -> None:
        """Handle TALK frame - stub for future."""
        pass

    def _handle_data(self, parsed: dict) -> None:
        """Handle DATA frame - stub for Session 7."""
        pass

    # Helper methods for sending control frames

    def _send_conack(self) -> None:
        """Send CONACK frame."""
        block_length_char = chr(ord('0') + self.config.exponent)
        payload = (
            f"{self.config.my_call}:0 {self._ur_call}:0 "
            f"{self._my_stream_id} {block_length_char}"
        )

        frame = self._frame_builder.build_control_frame(
            protocol_version='0',
            stream_id=self._my_stream_id,
            block_type=CONACK,
            data='',
            payload=payload
        )

        self._send_frame(frame)

    def _send_refused(self) -> None:
        """Send REFUSED frame."""
        frame = self._frame_builder.build_control_frame(
            protocol_version='0',
            stream_id=self._my_stream_id,
            block_type=REFUSED,
            data='',
            payload=''
        )

        self._send_frame(frame)

    def _send_disack(self) -> None:
        """Send DISACK frame."""
        frame = self._frame_builder.build_control_frame(
            protocol_version='0',
            stream_id=self._my_stream_id,
            block_type=DISACK,
            data='',
            payload=''
        )

        self._send_frame(frame)

    # Main loop support

    def process(self) -> None:
        """Process one iteration of the ARQ protocol.

        This should be called regularly (every 100ms recommended).
        Processes received frames and handles timeouts.
        """
        # Process received frames
        self._process_frames()

        # Update timeout counters
        if self._timeout_counter > 0:
            self._timeout_counter -= 1

            if self._timeout_counter == 0:
                self._handle_timeout()

        # Update retry counters
        if self._retry_counter > 0:
            self._retry_counter -= 1

    def _handle_timeout(self) -> None:
        """Handle timeout event."""
        if self.state.state in {LinkState.ARQ_CONNECTING, LinkState.DISCONNECTING}:
            self.state.transition_to(LinkState.TIMEDOUT)
            self.state.transition_to(LinkState.DOWN)
            self._emit_status("Connection timed out")

    # State queries

    def is_connected(self) -> bool:
        """Check if connected.

        Returns:
            True if in connected state
        """
        return self.state.is_connected()

    def is_connecting(self) -> bool:
        """Check if connection in progress.

        Returns:
            True if connecting
        """
        return self.state.is_connecting()

    def get_state(self) -> LinkState:
        """Get current link state.

        Returns:
            Current link state
        """
        return self.state.state
```

### Step 2: Create Protocol Tests (30 minutes)

Create `tests/test_arq/test_protocol.py`:

```python
"""Tests for ARQ protocol."""

import pytest
from pydigi.arq.protocol import (
    ARQProtocol,
    CONREQ,
    CONACK,
    REFUSED,
    DISREQ,
    DISACK,
    ABORT,
)
from pydigi.arq.config import ARQConfig
from pydigi.arq.state_machine import LinkState
from pydigi.arq.exceptions import ARQStateError, ARQConnectionError


class TestARQProtocol:
    """Test ARQ protocol class."""

    def test_initialization(self):
        """Test protocol initialization."""
        protocol = ARQProtocol()

        assert protocol.state.state == LinkState.DOWN
        assert protocol.stats.total_tx == 0
        assert protocol.stats.total_rx == 0

    def test_initialization_with_config(self):
        """Test initialization with custom config."""
        config = ARQConfig(
            my_call="W1AW",
            my_stream_id="5"
        )
        protocol = ARQProtocol(config=config)

        assert protocol.config.my_call == "W1AW"
        assert protocol._my_stream_id == "5"

    def test_set_callbacks(self):
        """Test setting callbacks."""
        protocol = ARQProtocol()

        sent_frames = []
        rx_text = []
        status_msgs = []

        protocol.set_send_callback(lambda f: sent_frames.append(f))
        protocol.set_rx_text_callback(lambda t: rx_text.append(t))
        protocol.set_status_callback(lambda m: status_msgs.append(m))

        assert protocol._send_callback is not None
        assert protocol._rx_text_callback is not None
        assert protocol._status_callback is not None

    def test_connect_without_mycall(self):
        """Test connect fails without my_call configured."""
        protocol = ARQProtocol()

        with pytest.raises(ARQConnectionError, match="my_call must be configured"):
            protocol.connect("K6XYZ")

    def test_connect_from_down_state(self):
        """Test successful connection initiation."""
        config = ARQConfig(my_call="W1AW")
        protocol = ARQProtocol(config=config)

        sent_frames = []
        status_msgs = []
        protocol.set_send_callback(lambda f: sent_frames.append(f))
        protocol.set_status_callback(lambda m: status_msgs.append(m))

        protocol.connect("K6XYZ")

        assert protocol.state.state == LinkState.ARQ_CONNECTING
        assert protocol._ur_call == "K6XYZ"
        assert len(sent_frames) == 1
        assert CONREQ in sent_frames[0]
        assert "W1AW" in sent_frames[0]
        assert "K6XYZ" in sent_frames[0]
        assert any("Connecting" in msg for msg in status_msgs)

    def test_connect_from_wrong_state(self):
        """Test connect fails from non-DOWN state."""
        config = ARQConfig(my_call="W1AW")
        protocol = ARQProtocol(config=config)

        # Force into CONNECTED state
        protocol.state.transition_to(LinkState.ARQ_CONNECTING, force=True)
        protocol.state.transition_to(LinkState.ARQ_CONNECTED, force=True)

        with pytest.raises(ARQStateError, match="Cannot connect"):
            protocol.connect("K6XYZ")

    def test_disconnect_from_connected_state(self):
        """Test disconnection from connected state."""
        config = ARQConfig(my_call="W1AW")
        protocol = ARQProtocol(config=config)

        sent_frames = []
        protocol.set_send_callback(lambda f: sent_frames.append(f))

        # Force into connected state
        protocol.state.transition_to(LinkState.ARQ_CONNECTING, force=True)
        protocol.state.transition_to(LinkState.ARQ_CONNECTED)

        protocol.disconnect()

        assert protocol.state.state == LinkState.DISCONNECTING
        assert len(sent_frames) == 1
        assert DISREQ in sent_frames[0]

    def test_disconnect_from_wrong_state(self):
        """Test disconnect fails from non-connected state."""
        protocol = ARQProtocol()

        with pytest.raises(ARQStateError, match="Cannot disconnect"):
            protocol.disconnect()

    def test_abort_from_any_state(self):
        """Test abort can be called from any state."""
        config = ARQConfig(my_call="W1AW")
        protocol = ARQProtocol(config=config)

        sent_frames = []
        protocol.set_send_callback(lambda f: sent_frames.append(f))

        protocol.abort()

        assert protocol.state.state == LinkState.ABORTING
        assert len(sent_frames) == 1
        assert ABORT in sent_frames[0]

    def test_receive_frame(self):
        """Test receiving a frame."""
        protocol = ARQProtocol()

        protocol.receive_frame("test_frame")

        assert len(protocol._frame_queue) == 1
        assert protocol.stats.total_rx == 1

    def test_handle_conack(self):
        """Test handling CONACK frame."""
        config = ARQConfig(my_call="W1AW")
        protocol = ARQProtocol(config=config)

        status_msgs = []
        protocol.set_status_callback(lambda m: status_msgs.append(m))

        # Put in CONNECTING state
        protocol.state.transition_to(LinkState.ARQ_CONNECTING, force=True)
        protocol._ur_call = "K6XYZ"

        # Simulate receiving CONACK
        parsed = {
            'protocol_version': '0',
            'stream_id': '5',
            'block_type': CONACK,
            'data': '',
            'payload': 'K6XYZ:0 W1AW:0 5 7'
        }

        protocol._handle_conack(parsed)

        assert protocol.state.state == LinkState.ARQ_CONNECTED
        assert protocol._ur_stream_id == '5'
        assert any("Connected" in msg for msg in status_msgs)

    def test_handle_refused(self):
        """Test handling REFUSED frame."""
        config = ARQConfig(my_call="W1AW")
        protocol = ARQProtocol(config=config)

        status_msgs = []
        protocol.set_status_callback(lambda m: status_msgs.append(m))

        # Put in CONNECTING state
        protocol.state.transition_to(LinkState.ARQ_CONNECTING, force=True)
        protocol._ur_call = "K6XYZ"

        # Simulate receiving REFUSED
        parsed = {
            'protocol_version': '0',
            'stream_id': '5',
            'block_type': REFUSED,
            'data': '',
            'payload': ''
        }

        protocol._handle_refused(parsed)

        assert protocol.state.state == LinkState.DOWN
        assert any("refused" in msg.lower() for msg in status_msgs)

    def test_handle_disreq(self):
        """Test handling DISREQ frame."""
        config = ARQConfig(my_call="W1AW")
        protocol = ARQProtocol(config=config)

        sent_frames = []
        protocol.set_send_callback(lambda f: sent_frames.append(f))

        # Put in CONNECTED state
        protocol.state.transition_to(LinkState.ARQ_CONNECTING, force=True)
        protocol.state.transition_to(LinkState.ARQ_CONNECTED)

        # Simulate receiving DISREQ
        parsed = {
            'protocol_version': '0',
            'stream_id': '5',
            'block_type': DISREQ,
            'data': '',
            'payload': ''
        }

        protocol._handle_disreq(parsed)

        assert protocol.state.state == LinkState.DOWN
        assert len(sent_frames) == 1
        assert DISACK in sent_frames[0]

    def test_handle_disack(self):
        """Test handling DISACK frame."""
        config = ARQConfig(my_call="W1AW")
        protocol = ARQProtocol(config=config)

        # Put in DISCONNECTING state
        protocol.state.transition_to(LinkState.ARQ_CONNECTING, force=True)
        protocol.state.transition_to(LinkState.ARQ_CONNECTED)
        protocol.state.transition_to(LinkState.DISCONNECT)
        protocol.state.transition_to(LinkState.DISCONNECTING)

        # Simulate receiving DISACK
        parsed = {
            'protocol_version': '0',
            'stream_id': '5',
            'block_type': DISACK,
            'data': '',
            'payload': ''
        }

        protocol._handle_disack(parsed)

        assert protocol.state.state == LinkState.DOWN

    def test_process_loop(self):
        """Test main process loop."""
        protocol = ARQProtocol()

        # Add frame to queue
        protocol._frame_queue.append("test")

        # Process should not crash
        protocol.process()

    def test_timeout_handling(self):
        """Test timeout handling."""
        config = ARQConfig(my_call="W1AW", timeout=1000, loop_time=100)
        protocol = ARQProtocol(config=config)

        status_msgs = []
        protocol.set_status_callback(lambda m: status_msgs.append(m))

        # Put in CONNECTING state with timeout
        protocol.state.transition_to(LinkState.ARQ_CONNECTING, force=True)
        protocol._timeout_counter = 1

        # Process should trigger timeout
        protocol.process()

        assert protocol.state.state == LinkState.DOWN
        assert any("timed out" in msg.lower() for msg in status_msgs)

    def test_is_connected(self):
        """Test is_connected query."""
        protocol = ARQProtocol()

        assert not protocol.is_connected()

        protocol.state.transition_to(LinkState.ARQ_CONNECTING, force=True)
        assert not protocol.is_connected()

        protocol.state.transition_to(LinkState.ARQ_CONNECTED)
        assert protocol.is_connected()

    def test_statistics(self):
        """Test statistics tracking."""
        config = ARQConfig(my_call="W1AW")
        protocol = ARQProtocol(config=config)

        sent_frames = []
        protocol.set_send_callback(lambda f: sent_frames.append(f))

        # Send a frame
        protocol.connect("K6XYZ")
        assert protocol.stats.total_tx == 1

        # Receive a frame
        protocol.receive_frame("test")
        assert protocol.stats.total_rx == 1
```

### Step 3: Update __init__.py (5 minutes)

Update `pydigi/arq/__init__.py` to export the protocol class:

```python
"""FLARQ ARQ Protocol implementation for pydigi."""

from .crc import calculate_crc16
from .frame import FrameBuilder, FrameParser
from .blocks import BlockTracker
from .config import ARQConfig
from .state_machine import ARQStateMachine, LinkState
from .protocol import ARQProtocol
from .exceptions import (
    ARQError,
    ARQFrameError,
    ARQCRCError,
    ARQTimeoutError,
    ARQConnectionError,
    ARQStateError,
    ARQAbortError,
)

__all__ = [
    'calculate_crc16',
    'FrameBuilder',
    'FrameParser',
    'BlockTracker',
    'ARQConfig',
    'ARQStateMachine',
    'LinkState',
    'ARQProtocol',
    'ARQError',
    'ARQFrameError',
    'ARQCRCError',
    'ARQTimeoutError',
    'ARQConnectionError',
    'ARQStateError',
    'ARQAbortError',
]
```

### Step 4: Run Tests (10 minutes)

Run the test suite to validate implementation:

```bash
# Test protocol
pytest tests/test_arq/test_protocol.py -v

# Test all ARQ components
pytest tests/test_arq/ -v

# Check coverage
pytest tests/test_arq/test_protocol.py --cov=pydigi.arq.protocol --cov-report=term-missing
```

## Validation Checkpoint

### Protocol Class
- ✅ ARQProtocol class created with initialization
- ✅ Callbacks for send/receive/status implemented
- ✅ Connection logic (connect, CONREQ, CONACK) works
- ✅ Disconnection logic (disconnect, DISREQ, DISACK) works
- ✅ Abort logic implemented
- ✅ Frame reception and routing works
- ✅ State machine integration works
- ✅ Timeout handling works
- ✅ All tests pass (20+ tests)

### Integration
- ✅ Uses ARQConfig for configuration
- ✅ Uses ARQStateMachine for state management
- ✅ Uses FrameBuilder/Parser for frames
- ✅ Uses BlockTracker for block management
- ✅ Proper exception handling

### Overall
- ✅ Protocol skeleton complete
- ✅ Connection/disconnection working
- ✅ Ready for Session 6 (frame handler stubs) and Session 7 (text transmission)

## Common Pitfalls

1. **State Management**: Always check state before transitioning
2. **Callbacks**: Check if callback is set before calling
3. **Frame Format**: CONREQ payload format must match fldigi exactly
4. **Timeout Counters**: Convert milliseconds to loop iterations correctly
5. **Stream ID**: Must be single character, not integer

## Reference Files

### fldigi Source
- `fldigi/src/flarq-src/include/arq.h` - Lines 180-399 for class structure
- `fldigi/src/flarq-src/arq.cxx` - Implementation reference

### Previous Sessions
- Session 1: CRC-16 implementation
- Session 2: Frame building/parsing
- Session 3: Block tracking
- Session 4: Config & State Machine

## Next Steps

After completing Session 5, proceed to:

**Session 6: Frame Handler Stubs** - Implement remaining frame handlers (STATUS, POLL, IDENT, DATA)

**Session 7: Text Transmission** - Implement text data transmission and block management

## Estimated Time Breakdown

- Step 1 (Protocol Skeleton): 30 minutes
- Step 2 (Tests): 30 minutes
- Step 3 (Update __init__): 5 minutes
- Step 4 (Validation): 10 minutes

**Total**: ~75 minutes (1.5 hours, could extend to 2-3 hours with debugging)
