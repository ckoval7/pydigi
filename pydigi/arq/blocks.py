"""
Block tracking and management for ARQ protocol.

Handles modulo-64 block numbering, missing block detection,
and out-of-order block queuing.
"""

from typing import List, Optional, Tuple
from dataclasses import dataclass


# Constants
MAXCOUNT = 64  # Block numbers wrap at 64


@dataclass
class Block:
    """Represents a data block with number and payload."""
    number: int  # Block number (0-63)
    payload: str  # Block payload content

    def __post_init__(self):
        """Validate block number is in valid range."""
        if not (0 <= self.number < MAXCOUNT):
            raise ValueError(f"Block number must be 0-{MAXCOUNT-1}, got {self.number}")


class BlockTracker:
    """
    Tracks block transmission and reception with modulo-64 arithmetic.

    This class manages:
    - Sequential block numbering with wrapping
    - Missing block detection across wrap boundary
    - Out-of-order block queuing and sorting
    - Consecutive block detection
    """

    def __init__(self):
        """Initialize block tracker."""
        self.good_header: int = MAXCOUNT - 1  # Last consecutive block received
        self.end_header: int = MAXCOUNT - 1   # Last block received (any order)
        self.last_sent: int = MAXCOUNT - 1    # Last block sent
        self.last_queued: int = MAXCOUNT - 1  # Last block queued for sending

        # Pending blocks (received out of order)
        self.rx_pending: List[Block] = []

    def next_block_number(self) -> int:
        """
        Get next block number for transmission.

        Returns:
            Next block number (0-63)
        """
        self.last_queued = (self.last_queued + 1) % MAXCOUNT
        return self.last_queued

    def receive_block(self, block_number: int, payload: str) -> Tuple[List[str], bool]:
        """
        Process a received block.

        Args:
            block_number: Block number (0-63)
            payload: Block payload

        Returns:
            Tuple of (consecutive_payloads, is_consecutive)
            - consecutive_payloads: List of payloads now consecutive from good_header
            - is_consecutive: True if this block was immediately consecutive
        """
        if not (0 <= block_number < MAXCOUNT):
            raise ValueError(f"Block number must be 0-{MAXCOUNT-1}, got {block_number}")

        # Update end_header to highest block seen
        self.end_header = block_number

        # Check if this block is consecutive
        expected_next = (self.good_header + 1) % MAXCOUNT

        if block_number == expected_next:
            # Consecutive block - can process immediately
            self.good_header = block_number
            consecutive_payloads = [payload]

            # Check if any pending blocks are now consecutive
            consecutive_payloads.extend(self._process_pending())

            return consecutive_payloads, True
        else:
            # Out of order - add to pending
            block = Block(number=block_number, payload=payload)
            self.rx_pending.append(block)

            # Sort pending blocks
            self._sort_pending()

            return [], False

    def _sort_pending(self):
        """Sort pending blocks accounting for modulo-64 wrapping."""
        if not self.rx_pending:
            return

        # Sort using comparison that accounts for wrapping
        # Blocks are sorted relative to good_header
        def block_key(block: Block) -> int:
            n = block.number
            # Adjust blocks below good_header (they wrapped around)
            if n < self.good_header:
                n += MAXCOUNT
            return n

        self.rx_pending.sort(key=block_key)

    def _process_pending(self) -> List[str]:
        """
        Process pending blocks that are now consecutive.

        Returns:
            List of consecutive payloads from pending queue
        """
        consecutive = []

        while self.rx_pending:
            expected_next = (self.good_header + 1) % MAXCOUNT

            # Check if first pending block is consecutive
            if self.rx_pending[0].number == expected_next:
                block = self.rx_pending.pop(0)
                self.good_header = block.number
                consecutive.append(block.payload)
            else:
                # No more consecutive blocks
                break

        return consecutive

    def get_missing_blocks(self) -> List[int]:
        """
        Get list of missing block numbers between good_header and end_header.

        Returns:
            List of missing block numbers
        """
        if self.good_header == self.end_header:
            return []

        missing = []

        # Range to check: (good_header + 1) to end_header (inclusive)
        start = (self.good_header + 1) % MAXCOUNT
        end = self.end_header

        # Handle wrapping
        if end < start:
            end += MAXCOUNT

        # Check each block in range
        current = start
        while current != (end % MAXCOUNT):
            test_block = current % MAXCOUNT

            # Check if this block is in pending
            is_pending = any(b.number == test_block for b in self.rx_pending)

            if not is_pending:
                missing.append(test_block)

            current += 1

        # Check end block itself
        test_block = end % MAXCOUNT
        is_pending = any(b.number == test_block for b in self.rx_pending)
        if not is_pending and test_block != self.good_header:
            missing.append(test_block)

        return missing

    def reset(self):
        """Reset tracker to initial state."""
        self.good_header = MAXCOUNT - 1
        self.end_header = MAXCOUNT - 1
        self.last_sent = MAXCOUNT - 1
        self.last_queued = MAXCOUNT - 1
        self.rx_pending.clear()

    def reset_rx(self):
        """Reset only receive-side tracking."""
        self.good_header = MAXCOUNT - 1
        self.end_header = MAXCOUNT - 1
        self.rx_pending.clear()

    def reset_tx(self):
        """Reset only transmit-side tracking."""
        self.last_sent = MAXCOUNT - 1
        self.last_queued = MAXCOUNT - 1
