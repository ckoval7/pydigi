"""Main ARQ protocol implementation for FLARQ."""

import time
from typing import Optional, Callable, List
from dataclasses import dataclass

from .config import ARQConfig
from .state_machine import ARQStateMachine, LinkState
from .frame import (
    ARQFrame,
    IDENT, CONREQ, CONACK, REFUSED, DISREQ, STATUS, POLL,
    ABORT, ACKABORT, DISACK, UNPROTO, TALK,
)
from .blocks import BlockTracker
from .exceptions import (
    ARQError,
    ARQConnectionError,
    ARQTimeoutError,
    ARQStateError,
)


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
        send_callback: Optional[Callable[[bytes], None]] = None,
    ):
        """Initialize ARQ protocol.

        Args:
            config: Protocol configuration (uses defaults if None)
            send_callback: Callback to send frames (takes frame bytes)
        """
        self.config = config or ARQConfig()
        self.state = ARQStateMachine()

        # Callbacks
        self._send_callback = send_callback
        self._rx_text_callback: Optional[Callable[[str], None]] = None
        self._tx_text_callback: Optional[Callable[[str], None]] = None
        self._status_callback: Optional[Callable[[str], None]] = None

        # Block tracking
        self._tx_tracker = BlockTracker()
        self._rx_tracker = BlockTracker()

        # Statistics
        self.stats = ARQStatistics()

        # Stream ID
        self._my_stream_id = self.config.my_stream_id
        self._ur_stream_id = '0'

        # Timing counters (in loop iterations)
        self._retry_counter = 0          # Block retry timer
        self._timeout_counter = 0        # Connection timeout timer
        self._id_timer = 0               # Keepalive ID timer
        self._tx_delay_counter = 0       # RX-to-TX delay
        self._connection_retries = 0     # Connection retry attempts

        # Queues
        self._tx_queue: List[str] = []  # Outgoing text
        self._rx_queue: List[str] = []  # Received text
        self._frame_queue: List[bytes] = []  # Received frames to process

        # Connection state
        self._ur_call = ""  # Remote callsign from connection
        self._ur_block_length_char = '7'  # Remote block length

        # Frame handler state
        self._immediate = False  # Flag for immediate transmission
        self._tx_pending: List[dict] = []  # Sent blocks pending acknowledgment
        self._rx_pending: List[dict] = []  # Received blocks (not consecutive)
        self._tx_missing: List[dict] = []  # Blocks needing retransmission
        self._tx_blocks: List[dict] = []   # Blocks queued for transmission

        # Remote station's block tracking
        self._ur_last_sent = 0
        self._ur_good_header = 0
        self._ur_end_header = 0

    def set_send_callback(self, callback: Callable[[bytes], None]) -> None:
        """Set callback for sending frames.

        Args:
            callback: Function that takes frame bytes and sends it
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

    def _set_id_timer(self, minutes: Optional[int] = None) -> None:
        """Set or reset the ID timer for keepalive frames.

        Args:
            minutes: Minutes until next ID frame (default: 10)
        """
        if minutes is None:
            minutes = 10  # Default 10 minutes

        # Convert to loop iterations: (minutes * 60 - 10) seconds * 1000ms / loop_time
        self._id_timer = ((minutes * 60 - 10) * 1000) // self.config.loop_time

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

        # Initialize connection retry counter
        self._connection_retries = self.config.retries - 1  # First attempt + retries

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
        frame = ARQFrame(
            protocol_version='0',
            stream_id=self._my_stream_id,
            block_type=CONREQ,
            payload=payload
        )

        self._send_frame(frame)
        self._emit_status(f"Connecting to {self._ur_call}...")

        # Start timeout counter
        self._timeout_counter = self.config.timeout // self.config.loop_time

        # Initialize ID timer
        self._set_id_timer()

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
        frame = ARQFrame(
            protocol_version='0',
            stream_id=self._my_stream_id,
            block_type=DISREQ,
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
        frame = ARQFrame(
            protocol_version='0',
            stream_id=self._my_stream_id,
            block_type=ABORT,
            payload=''
        )

        self._send_frame(frame)
        self._emit_status("Aborting transfer...")

    def _reset_tx(self) -> None:
        """Reset TX state (clear all transmit queues and counters)."""
        self._tx_blocks.clear()
        self._tx_missing.clear()
        self._tx_pending.clear()
        self._tx_tracker.reset_tx()

    def _reset_rx(self) -> None:
        """Reset RX state (clear all receive queues and counters)."""
        self._rx_pending.clear()
        self._rx_queue.clear()
        self._rx_tracker.reset_rx()

    def _reset(self) -> None:
        """Reset both TX and RX state (soft reset for ABORT)."""
        self._reset_tx()
        self._reset_rx()
        self._immediate = False

    # Frame Reception

    def receive_frame(self, frame_bytes: bytes) -> None:
        """Receive and queue a frame for processing.

        Args:
            frame_bytes: Complete frame bytes received
        """
        self._frame_queue.append(frame_bytes)
        self.stats.total_rx += 1

    def _process_frames(self) -> None:
        """Process all queued frames."""
        while self._frame_queue:
            frame_bytes = self._frame_queue.pop(0)
            self._process_frame(frame_bytes)

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

            if block_type == CONREQ:
                self._handle_conreq(frame)
            elif block_type == CONACK:
                self._handle_conack(frame)
            elif block_type == REFUSED:
                self._handle_refused(frame)
            elif block_type == DISREQ:
                self._handle_disreq(frame)
            elif block_type == DISACK:
                self._handle_disack(frame)
            elif block_type == ABORT:
                self._handle_abort(frame)
            elif block_type == ACKABORT:
                self._handle_ackabort(frame)
            elif block_type == STATUS:
                self._handle_status(frame)
            elif block_type == POLL:
                self._handle_poll(frame)
            elif block_type == IDENT:
                self._handle_ident(frame)
            elif block_type == UNPROTO:
                self._handle_unproto(frame)
            elif block_type == TALK:
                self._handle_talk(frame)
            else:
                # Data frame (block number 0-63)
                if 0 <= block_type < 64:
                    self._handle_data(frame)
                else:
                    # Unknown frame type
                    self._emit_status(f"Unknown frame type: {block_type}")

        except Exception as e:
            self.stats.bad_rx += 1
            self._emit_status(f"Frame processing error: {e}")

    # Frame Handlers (stubs for now, will be implemented in later sessions)

    def _handle_conreq(self, frame: ARQFrame) -> None:
        """Handle CONREQ frame.

        Args:
            frame: Parsed frame data
        """
        # Parse payload
        # Format: "MYCALL:port URCALL:port StreamID BlockLengthChar ..."
        payload = frame.payload
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

    def _handle_conack(self, frame: ARQFrame) -> None:
        """Handle CONACK frame.

        Args:
            frame: Parsed frame data
        """
        if self.state.state != LinkState.ARQ_CONNECTING:
            return

        # Parse payload to get remote parameters
        payload = frame.payload
        parts = payload.split()

        if len(parts) >= 4:
            self._ur_stream_id = parts[2]
            self._ur_block_length_char = parts[3]

        # Connection established
        self.state.transition_to(LinkState.ARQ_CONNECTED)
        self._emit_status(f"Connected to {self._ur_call}")

    def _handle_refused(self, frame: ARQFrame) -> None:
        """Handle REFUSED frame.

        Args:
            frame: Parsed frame data
        """
        if self.state.state == LinkState.ARQ_CONNECTING:
            self.state.transition_to(LinkState.DOWN)
            self._emit_status(f"Connection refused by {self._ur_call}")

    def _handle_disreq(self, frame: ARQFrame) -> None:
        """Handle DISREQ frame.

        Args:
            frame: Parsed frame data
        """
        if self.state.is_connected():
            # Send DISACK
            self._send_disack()

            # Disconnect
            self.state.reset()
            self._emit_status("Disconnected by remote")

    def _handle_disack(self, frame: ARQFrame) -> None:
        """Handle DISACK frame.

        Args:
            frame: Parsed frame data
        """
        if self.state.is_disconnecting():
            self.state.transition_to(LinkState.DOWN)
            self._emit_status("Disconnected")

    def _handle_abort(self, frame: ARQFrame) -> None:
        """Handle ABORT frame.

        ABORT is a "soft reset" that clears the current transfer
        but keeps the connection alive. Respond with ACKABORT.

        Args:
            frame: Parsed ABORT frame
        """
        # Reset transfer state
        self._reset()

        # Send ACKABORT response
        self._send_ackabort()

        # Set immediate flag to send ACKABORT right away
        self._immediate = True

        # Return to connected state if we were aborting
        if self.state.state == LinkState.ABORTING:
            self.state.transition_to(LinkState.ARQ_CONNECTED, force=True)

        self._emit_status("Abort received - transfer reset")

    def _handle_ackabort(self, frame: ARQFrame) -> None:
        """Handle ACKABORT frame.

        Acknowledgment of our ABORT request. Reset transfer state
        and return to connected.

        Args:
            frame: Parsed ACKABORT frame
        """
        # Reset transfer state
        self._reset()

        # Return to connected state
        if self.state.state == LinkState.ABORTING:
            self.state.transition_to(LinkState.ARQ_CONNECTED, force=True)

        self._emit_status("Abort acknowledged - transfer reset")

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

    def _handle_unproto(self, frame: ARQFrame) -> None:
        """Handle UNPROTO frame - stub for future."""
        pass

    def _handle_talk(self, frame: ARQFrame) -> None:
        """Handle TALK frame - stub for future."""
        pass

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
        # block_type is already decoded as int by ARQFrame.parse()
        if isinstance(frame.block_type, int):
            block_num = frame.block_type
        else:
            # For compatibility with tests that pass chr(0x20 + block_num)
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
            if num < self._rx_tracker.good_header:
                num += 64
            return num

        self._rx_pending.sort(key=sort_key)

        # Update EndHeader (last received, possibly with gaps)
        if self._rx_pending:
            self._rx_tracker.end_header = self._rx_pending[-1]['block_num']
        else:
            self._rx_tracker.end_header = self._rx_tracker.good_header

        # Process consecutive blocks from pending queue
        while self._rx_pending:
            block = self._rx_pending[0]
            next_expected = (self._rx_tracker.good_header + 1) % 64

            if block['block_num'] != next_expected:
                # Gap in sequence, stop processing
                break

            # Block is next in sequence
            self._rx_pending.pop(0)

            # Add text to receive queue
            self._rx_queue.append(block['text'])

            # Update GoodHeader
            self._rx_tracker.good_header = block['block_num']

            # Call RX callback
            if self._rx_text_callback:
                self._rx_text_callback(block['text'])

        # Update missing blocks list
        self._update_missing_blocks()

    def _update_missing_blocks(self) -> None:
        """Update list of missing received blocks.

        This is called after processing DATA frames to determine which
        blocks are missing between GoodHeader and EndHeader.

        Note: The BlockTracker.get_missing_blocks() method already handles
        this calculation, so we don't need to do anything here. The missing
        blocks will be calculated when we send a STATUS frame.
        """
        pass

    def _get_missing_blocks(self) -> list:
        """Get list of missing blocks between GoodHeader and EndHeader.

        Returns:
            List of missing block numbers (0-63)
        """
        if self._rx_tracker.good_header == self._rx_tracker.end_header:
            return []

        missing = []
        pending_nums = {b['block_num'] for b in self._rx_pending}

        # Range to check: (good_header + 1) to end_header (exclusive)
        start = (self._rx_tracker.good_header + 1) % 64
        end = self._rx_tracker.end_header

        # Handle wrapping
        if end < start:
            # Wraps around, check in two parts
            for i in range(start, 64):
                if i not in pending_nums:
                    missing.append(i)
            for i in range(0, end):
                if i not in pending_nums:
                    missing.append(i)
        else:
            # No wrap
            for i in range(start, end):
                if i not in pending_nums:
                    missing.append(i)

        return missing

    # Helper methods for sending control frames

    def _send_conack(self) -> None:
        """Send CONACK frame."""
        block_length_char = chr(ord('0') + self.config.exponent)
        payload = (
            f"{self.config.my_call}:0 {self._ur_call}:0 "
            f"{self._my_stream_id} {block_length_char}"
        )

        frame = ARQFrame(
            protocol_version='0',
            stream_id=self._my_stream_id,
            block_type=CONACK,
            payload=payload
        )

        self._send_frame(frame)

    def _send_refused(self) -> None:
        """Send REFUSED frame."""
        frame = ARQFrame(
            protocol_version='0',
            stream_id=self._my_stream_id,
            block_type=REFUSED,
            payload=''
        )

        self._send_frame(frame)

    def _send_disack(self) -> None:
        """Send DISACK frame."""
        frame = ARQFrame(
            protocol_version='0',
            stream_id=self._my_stream_id,
            block_type=DISACK,
            payload=''
        )

        self._send_frame(frame)

    def _send_status(self) -> None:
        """Send STATUS frame with current block tracking info."""
        # Build status payload
        # Format: [LastHeader][GoodHeader][EndHeader][Missing blocks...]
        payload = chr(0x20 + self._tx_tracker.last_sent)
        payload += chr(0x20 + self._rx_tracker.good_header)
        payload += chr(0x20 + self._rx_tracker.end_header)

        # Add missing blocks to payload
        missing = self._get_missing_blocks()
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

    def _send_poll(self) -> None:
        """Send POLL frame to request STATUS."""
        frame = ARQFrame(
            protocol_version='0',
            stream_id=self._my_stream_id,
            block_type=POLL,
            payload=''
        )

        self._send_frame(frame)

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

    def _send_ackabort(self) -> None:
        """Send ACKABORT frame with current block tracking info.

        ACKABORT includes status payload like STATUS frame.
        """
        # Build status payload (same as STATUS)
        # Format: [LastHeader][GoodHeader][EndHeader][Missing blocks...]
        payload = chr(0x20 + self._tx_tracker.last_sent)
        payload += chr(0x20 + self._rx_tracker.good_header)
        payload += chr(0x20 + self._rx_tracker.end_header)

        # Add missing blocks
        missing = self._get_missing_blocks()
        for block_num in missing[:self.config.max_headers]:
            payload += chr(0x20 + block_num)

        frame = ARQFrame(
            protocol_version='0',
            stream_id=self._my_stream_id,
            block_type=ACKABORT,
            payload=payload
        )

        self._send_frame(frame)

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

    # Text Transmission Methods

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

    # Main loop support

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
