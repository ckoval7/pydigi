# Session 3: Block Tracking & Wrapping

**Duration**: 2-3 hours
**Priority**: HIGH
**Prerequisites**: Sessions 1-2 complete

## Goal

Implement block number tracking with modulo-64 arithmetic and missing block detection. This is critical for ARQ protocol operation as blocks wrap at 64 and must be tracked across the wrap boundary.

## Overview

The ARQ protocol uses block numbers 0-63 that wrap around. This session implements:

1. **Modulo-64 arithmetic** - Block numbers wrap at 64
2. **Missing block detection** - Identify gaps in received blocks
3. **Out-of-order handling** - Queue blocks received out of sequence
4. **Wrap boundary handling** - Correctly handle missing blocks across the wrap point (e.g., blocks 62, 63, 0, 1)

## Deliverables

1. `pydigi/arq/blocks.py` - Block tracking implementation
2. `tests/test_arq/test_blocks.py` - Comprehensive test suite (8+ tests)

## Key Concepts from fldigi

### Block Number Wrapping

```python
# Block numbers: 0-63 (MAXCOUNT = 64)
# Increment with wrap:
last_block = (last_block + 1) % 64

# Example sequence:
# 61, 62, 63, 0, 1, 2, 3...
```

### Critical Variables (from fldigi arq.h)

- **GoodHeader**: Last block received consecutively (no gaps)
- **EndHeader**: Last block received (may have gaps before it)
- **LastHeader**: Last block we sent
- **Lastqueued**: Last block added to send queue
- **RxPending**: Out-of-order blocks waiting to be processed

### Missing Block Detection Algorithm

fldigi checks the range from `(GoodHeader + 1) % 64` to `(EndHeader + 1) % 64`:

```cpp
// From arq.cxx:948-964
int start = (GoodHeader + 1) % MAXCOUNT;
int end = (EndHeader + 1) % MAXCOUNT;
int test;
bool ok;
if (end < start) end += MAXCOUNT;  // Handle wrap
for (int i = start; i < end; i++) {
    test = (i % MAXCOUNT);
    ok = false;
    // Check if 'test' block is in RxPending
    // If not, it's missing
}
```

## Implementation Steps

### Step 1: Create `pydigi/arq/blocks.py`

```python
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
```

### Step 2: Create `tests/test_arq/test_blocks.py`

```python
"""
Tests for ARQ block tracking.

Tests modulo-64 arithmetic, missing block detection, and out-of-order handling.
"""

import pytest
from pydigi.arq.blocks import BlockTracker, Block, MAXCOUNT


class TestBlock:
    """Test Block dataclass."""

    def test_block_creation(self):
        """Test creating a valid block."""
        block = Block(number=5, payload="test")
        assert block.number == 5
        assert block.payload == "test"

    def test_block_invalid_number_low(self):
        """Test block rejects negative numbers."""
        with pytest.raises(ValueError, match="Block number must be 0-63"):
            Block(number=-1, payload="test")

    def test_block_invalid_number_high(self):
        """Test block rejects numbers >= 64."""
        with pytest.raises(ValueError, match="Block number must be 0-63"):
            Block(number=64, payload="test")


class TestBlockTracker:
    """Test BlockTracker class."""

    def test_initialization(self):
        """Test tracker initializes to correct state."""
        tracker = BlockTracker()
        assert tracker.good_header == MAXCOUNT - 1
        assert tracker.end_header == MAXCOUNT - 1
        assert tracker.last_sent == MAXCOUNT - 1
        assert tracker.last_queued == MAXCOUNT - 1
        assert tracker.rx_pending == []

    def test_next_block_number(self):
        """Test block number generation wraps correctly."""
        tracker = BlockTracker()

        # First block should be 0
        assert tracker.next_block_number() == 0
        assert tracker.next_block_number() == 1
        assert tracker.next_block_number() == 2

    def test_next_block_number_wrapping(self):
        """Test block number wraps at 64."""
        tracker = BlockTracker()
        tracker.last_queued = 62

        assert tracker.next_block_number() == 63
        assert tracker.next_block_number() == 0  # Wraps
        assert tracker.next_block_number() == 1

    def test_receive_consecutive_blocks(self):
        """Test receiving blocks in order."""
        tracker = BlockTracker()

        # Receive blocks 0, 1, 2 in order
        payloads, is_consecutive = tracker.receive_block(0, "block0")
        assert is_consecutive is True
        assert payloads == ["block0"]
        assert tracker.good_header == 0

        payloads, is_consecutive = tracker.receive_block(1, "block1")
        assert is_consecutive is True
        assert payloads == ["block1"]
        assert tracker.good_header == 1

        payloads, is_consecutive = tracker.receive_block(2, "block2")
        assert is_consecutive is True
        assert payloads == ["block2"]
        assert tracker.good_header == 2

    def test_receive_out_of_order(self):
        """Test receiving blocks out of order."""
        tracker = BlockTracker()

        # Receive block 0
        payloads, is_consecutive = tracker.receive_block(0, "block0")
        assert is_consecutive is True
        assert payloads == ["block0"]

        # Receive block 2 (skipping 1)
        payloads, is_consecutive = tracker.receive_block(2, "block2")
        assert is_consecutive is False
        assert payloads == []
        assert tracker.good_header == 0  # Still at 0
        assert len(tracker.rx_pending) == 1

        # Receive block 1 (fills gap)
        payloads, is_consecutive = tracker.receive_block(1, "block1")
        assert is_consecutive is True
        assert payloads == ["block1", "block2"]  # Both become consecutive
        assert tracker.good_header == 2
        assert len(tracker.rx_pending) == 0

    def test_receive_multiple_out_of_order(self):
        """Test receiving multiple blocks out of order."""
        tracker = BlockTracker()

        # Receive blocks: 0, 3, 2, 1
        tracker.receive_block(0, "block0")
        tracker.receive_block(3, "block3")
        tracker.receive_block(2, "block2")

        # Now receive block 1 - should get 1, 2, 3
        payloads, _ = tracker.receive_block(1, "block1")
        assert payloads == ["block1", "block2", "block3"]
        assert tracker.good_header == 3

    def test_get_missing_blocks_simple(self):
        """Test missing block detection."""
        tracker = BlockTracker()

        # Receive blocks 0, 2, 3 (missing 1)
        tracker.receive_block(0, "block0")
        tracker.receive_block(2, "block2")
        tracker.receive_block(3, "block3")

        # Should detect block 1 is missing
        missing = tracker.get_missing_blocks()
        assert missing == [1]

    def test_get_missing_blocks_multiple(self):
        """Test detecting multiple missing blocks."""
        tracker = BlockTracker()

        # Receive blocks 0, 5 (missing 1, 2, 3, 4)
        tracker.receive_block(0, "block0")
        tracker.receive_block(5, "block5")

        missing = tracker.get_missing_blocks()
        assert sorted(missing) == [1, 2, 3, 4]

    def test_get_missing_blocks_wrap_boundary(self):
        """Test missing block detection across wrap boundary."""
        tracker = BlockTracker()

        # Set up scenario: good_header=62, received blocks 63, 1
        # Missing block 0
        tracker.good_header = 62
        tracker.receive_block(63, "block63")
        tracker.receive_block(1, "block1")

        missing = tracker.get_missing_blocks()
        assert 0 in missing

    def test_consecutive_blocks_wrap_boundary(self):
        """Test consecutive blocks across wrap boundary."""
        tracker = BlockTracker()

        # Set up: good_header=62
        tracker.good_header = 62

        # Receive 63, 0, 1 in order
        payloads, _ = tracker.receive_block(63, "block63")
        assert payloads == ["block63"]
        assert tracker.good_header == 63

        payloads, _ = tracker.receive_block(0, "block0")
        assert payloads == ["block0"]
        assert tracker.good_header == 0

        payloads, _ = tracker.receive_block(1, "block1")
        assert payloads == ["block1"]
        assert tracker.good_header == 1

    def test_reset(self):
        """Test reset clears all state."""
        tracker = BlockTracker()

        # Receive some blocks
        tracker.receive_block(0, "block0")
        tracker.receive_block(2, "block2")
        tracker.next_block_number()

        # Reset
        tracker.reset()

        assert tracker.good_header == MAXCOUNT - 1
        assert tracker.end_header == MAXCOUNT - 1
        assert tracker.last_sent == MAXCOUNT - 1
        assert tracker.last_queued == MAXCOUNT - 1
        assert tracker.rx_pending == []

    def test_reset_rx_only(self):
        """Test reset_rx clears only receive state."""
        tracker = BlockTracker()

        tracker.receive_block(0, "block0")
        tracker.next_block_number()
        tracker.next_block_number()

        tracker.reset_rx()

        # RX state reset
        assert tracker.good_header == MAXCOUNT - 1
        assert tracker.end_header == MAXCOUNT - 1
        assert tracker.rx_pending == []

        # TX state preserved
        assert tracker.last_queued == 1

    def test_reset_tx_only(self):
        """Test reset_tx clears only transmit state."""
        tracker = BlockTracker()

        tracker.receive_block(0, "block0")
        tracker.next_block_number()
        tracker.next_block_number()

        tracker.reset_tx()

        # TX state reset
        assert tracker.last_sent == MAXCOUNT - 1
        assert tracker.last_queued == MAXCOUNT - 1

        # RX state preserved
        assert tracker.good_header == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
```

## Validation Checkpoint

### Must Pass

1. ✅ All 18+ tests pass
2. ✅ Block numbers wrap correctly at 64
3. ✅ Missing blocks detected correctly
4. ✅ Out-of-order blocks queued and processed when gap fills
5. ✅ Wrap boundary handling works (blocks 62→63→0→1)

### Run Tests

```bash
cd /home/corey/pydigi
pytest tests/test_arq/test_blocks.py -v
```

Expected output:
```
test_blocks.py::TestBlock::test_block_creation PASSED
test_blocks.py::TestBlock::test_block_invalid_number_low PASSED
test_blocks.py::TestBlock::test_block_invalid_number_high PASSED
test_blocks.py::TestBlockTracker::test_initialization PASSED
test_blocks.py::TestBlockTracker::test_next_block_number PASSED
test_blocks.py::TestBlockTracker::test_next_block_number_wrapping PASSED
test_blocks.py::TestBlockTracker::test_receive_consecutive_blocks PASSED
test_blocks.py::TestBlockTracker::test_receive_out_of_order PASSED
test_blocks.py::TestBlockTracker::test_receive_multiple_out_of_order PASSED
test_blocks.py::TestBlockTracker::test_get_missing_blocks_simple PASSED
test_blocks.py::TestBlockTracker::test_get_missing_blocks_multiple PASSED
test_blocks.py::TestBlockTracker::test_get_missing_blocks_wrap_boundary PASSED
test_blocks.py::TestBlockTracker::test_consecutive_blocks_wrap_boundary PASSED
test_blocks.py::TestBlockTracker::test_reset PASSED
test_blocks.py::TestBlockTracker::test_reset_rx_only PASSED
test_blocks.py::TestBlockTracker::test_reset_tx_only PASSED

=================== 16 passed ===================
```

## Common Pitfalls

### 1. Modulo Arithmetic Errors
**Problem**: Forgetting to apply `% MAXCOUNT` when incrementing
**Solution**: Always use `(value + 1) % MAXCOUNT`

### 2. Wrap Boundary in Ranges
**Problem**: Missing blocks at wrap boundary (e.g., 62, 63, 0, 1)
**Solution**: Adjust end value: `if end < start: end += MAXCOUNT`

### 3. Sorting Out-of-Order Blocks
**Problem**: Standard sort fails across wrap boundary
**Solution**: Adjust block numbers relative to `good_header` before sorting

### 4. Off-by-One Errors
**Problem**: Including or excluding boundary blocks incorrectly
**Solution**: Carefully check inclusive/exclusive ranges in loops

## Reference Files

### fldigi Source
- `fldigi/src/flarq-src/include/arq.h` (lines 162-177, 248-269)
  - Block data structure
  - Tracker variables

- `fldigi/src/flarq-src/arq.cxx` (lines 913-969)
  - `parseDATA()` - Receiving blocks
  - Missing block detection algorithm
  - Pending block sorting

### Key Code Sections

**Block increment (arq.cxx:205-209)**:
```cpp
void arq::newblocknumber()
{
    Lastqueued++;
    Lastqueued %= MAXCOUNT;
}
```

**Missing block detection (arq.cxx:948-964)**:
```cpp
int start = (GoodHeader + 1)%MAXCOUNT;
int end = (EndHeader + 1)%MAXCOUNT;
if (end < start) end += MAXCOUNT;  // Handle wrap!
```

**Pending block sort (arq.cxx:918-921)**:
```cpp
n1 = p1->nbr();
if (n1 < GoodHeader) n1 += MAXCOUNT;  // Adjust for wrap
```

## Next Steps

After completing Session 3:
- ✅ Block tracking foundation complete
- ➡️ Ready for **Session 4: Config & State Machine**
- ➡️ Can also work on **Session 4** in parallel (independent)

## Notes

- This is the last critical foundation piece before protocol implementation
- Correct modulo-64 arithmetic is essential for interoperability
- The wrap boundary is the most common source of bugs - test thoroughly!
- Once this passes, Sessions 1-3 provide the core building blocks for ARQ
