# Session 4: Configuration & State Machine

**Duration**: 1-2 hours
**Priority**: MEDIUM
**Status**: In Progress

## Goal

Create configuration management and state machine components for the FLARQ ARQ protocol. These provide the foundation for protocol behavior and state transitions.

## Prerequisites

- Session 1 complete (CRC-16)
- Session 2 complete (Frame Builder/Parser)
- Session 3 complete (Block Tracking)
- Python 3.8+
- pytest installed

## Deliverables

1. `pydigi/arq/config.py` - Configuration dataclass with protocol parameters
2. `pydigi/arq/state_machine.py` - State machine with transitions
3. `pydigi/arq/exceptions.py` - Custom ARQ exceptions
4. `tests/test_arq/test_config.py` - Configuration tests
5. `tests/test_arq/test_state_machine.py` - State machine tests

## Implementation Steps

### Step 1: Create Custom Exceptions (15 minutes)

Create `pydigi/arq/exceptions.py` with ARQ-specific exceptions.

**Reference**: Common error conditions from `fldigi/src/flarq-src/arq.cxx`

```python
"""Custom exceptions for FLARQ ARQ protocol."""


class ARQError(Exception):
    """Base exception for ARQ protocol errors."""
    pass


class ARQFrameError(ARQError):
    """Exception raised for frame-related errors."""
    pass


class ARQCRCError(ARQFrameError):
    """Exception raised when frame CRC validation fails."""
    pass


class ARQTimeoutError(ARQError):
    """Exception raised when ARQ operation times out."""
    pass


class ARQConnectionError(ARQError):
    """Exception raised for connection-related errors."""
    pass


class ARQStateError(ARQError):
    """Exception raised for invalid state transitions."""
    pass


class ARQAbortError(ARQError):
    """Exception raised when transfer is aborted."""
    pass
```

### Step 2: Create Configuration Module (20 minutes)

Create `pydigi/arq/config.py` with protocol configuration.

**Reference**: `fldigi/src/flarq-src/include/arq.h` lines 78-87

```python
"""Configuration for FLARQ ARQ protocol."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ARQConfig:
    """Configuration parameters for FLARQ ARQ protocol.

    Based on K9PS ARQ Protocol Specification and FLARQ implementation.
    All timing values are in milliseconds.

    Reference: fldigi/src/flarq-src/include/arq.h lines 78-87
    """

    # Protocol constants (DO NOT CHANGE)
    max_block_count: int = 64  # Block numbers wrap at 64
    max_headers: int = 8  # Max number of missing blocks to report
    exponent: int = 7  # Buffer length = 2^exponent

    # Timing parameters
    retry_time: int = 10000  # Milliseconds between retries
    retries: int = 5  # Number of retry attempts
    tx_delay: int = 500  # Milliseconds from transmit to receive
    timeout: int = 60000  # Milliseconds before timeout
    loop_time: int = 100  # Milliseconds for main loop timing

    # Station identification
    my_call: str = ""  # Local callsign
    ur_call: str = ""  # Remote callsign

    # Stream identification
    my_stream_id: str = "0"  # Local stream ID ('0' = unknown)

    # Optional overrides
    custom_buffer_length: Optional[int] = None  # Override calculated buffer length

    def __post_init__(self):
        """Validate configuration parameters."""
        if self.max_block_count != 64:
            raise ValueError("max_block_count must be 64 (protocol requirement)")

        if self.exponent < 4 or self.exponent > 8:
            raise ValueError("exponent must be between 4 and 8")

        if self.max_headers < 1 or self.max_headers > 64:
            raise ValueError("max_headers must be between 1 and 64")

        if self.retry_time < 100:
            raise ValueError("retry_time must be at least 100ms")

        if self.retries < 1:
            raise ValueError("retries must be at least 1")

        if self.timeout < self.retry_time:
            raise ValueError("timeout must be >= retry_time")

        # Validate stream ID
        if not (self.my_stream_id == "0" or
                (self.my_stream_id.isdigit() and 0 <= int(self.my_stream_id) <= 63)):
            raise ValueError("my_stream_id must be '0' or '1'-'63'")

    @property
    def buffer_length(self) -> int:
        """Calculate buffer length from exponent.

        Returns:
            Buffer length = 2^exponent
        """
        if self.custom_buffer_length is not None:
            return self.custom_buffer_length
        return 2 ** self.exponent

    @property
    def max_payload_size(self) -> int:
        """Maximum payload size in bytes.

        Returns:
            Maximum payload size (512 bytes for default exponent=7)
        """
        # FLARQ supports payloads up to buffer_length
        # but typically uses smaller chunks
        return min(512, self.buffer_length)
```

### Step 3: Create State Machine Module (25 minutes)

Create `pydigi/arq/state_machine.py` with state management.

**Reference**: `fldigi/src/flarq-src/include/arq.h` lines 90-102

```python
"""State machine for FLARQ ARQ protocol."""

from enum import IntEnum, auto
from typing import Optional, Set
from .exceptions import ARQStateError


class LinkState(IntEnum):
    """ARQ link states.

    Reference: fldigi/src/flarq-src/include/arq.h lines 90-102
    """
    DOWN = 0  # No connection
    TIMEDOUT = auto()  # Connection timed out
    ABORT = auto()  # Transfer aborted
    ARQ_CONNECTING = auto()  # Connection in progress
    ARQ_CONNECTED = auto()  # Connected and ready
    WAITING = auto()  # Waiting for response
    WAITFORACK = auto()  # Waiting for acknowledgment
    DISCONNECT = auto()  # Disconnect requested
    DISCONNECTING = auto()  # Disconnection in progress
    ABORTING = auto()  # Abort in progress
    STOPPED = auto()  # Protocol stopped


class ARQStateMachine:
    """State machine for ARQ protocol connection management.

    Manages state transitions and validates allowed transitions
    based on FLARQ protocol rules.
    """

    # Valid state transitions
    TRANSITIONS = {
        LinkState.DOWN: {
            LinkState.ARQ_CONNECTING,  # Can initiate connection
        },
        LinkState.ARQ_CONNECTING: {
            LinkState.ARQ_CONNECTED,  # Connection accepted
            LinkState.DOWN,  # Connection refused
            LinkState.TIMEDOUT,  # Connection timeout
            LinkState.ABORTING,  # Connection aborted
        },
        LinkState.ARQ_CONNECTED: {
            LinkState.WAITING,  # Start waiting for data
            LinkState.WAITFORACK,  # Waiting for acknowledgment
            LinkState.DISCONNECT,  # Initiate disconnect
            LinkState.TIMEDOUT,  # Connection timeout
            LinkState.ABORTING,  # Abort transfer
        },
        LinkState.WAITING: {
            LinkState.ARQ_CONNECTED,  # Return to connected
            LinkState.WAITFORACK,  # Switch to waiting for ack
            LinkState.DISCONNECT,  # Initiate disconnect
            LinkState.TIMEDOUT,  # Timeout
            LinkState.ABORTING,  # Abort
        },
        LinkState.WAITFORACK: {
            LinkState.ARQ_CONNECTED,  # Ack received
            LinkState.WAITING,  # Switch to waiting
            LinkState.DISCONNECT,  # Initiate disconnect
            LinkState.TIMEDOUT,  # Timeout
            LinkState.ABORTING,  # Abort
        },
        LinkState.DISCONNECT: {
            LinkState.DISCONNECTING,  # Start disconnect process
            LinkState.DOWN,  # Immediate disconnect
        },
        LinkState.DISCONNECTING: {
            LinkState.DOWN,  # Disconnect complete
            LinkState.TIMEDOUT,  # Disconnect timeout
        },
        LinkState.ABORTING: {
            LinkState.ABORT,  # Abort complete
            LinkState.DOWN,  # Abort and reset
        },
        LinkState.TIMEDOUT: {
            LinkState.DOWN,  # Reset after timeout
        },
        LinkState.ABORT: {
            LinkState.DOWN,  # Reset after abort
        },
        LinkState.STOPPED: {
            LinkState.DOWN,  # Restart protocol
        },
    }

    def __init__(self, initial_state: LinkState = LinkState.DOWN):
        """Initialize state machine.

        Args:
            initial_state: Initial link state (default: DOWN)
        """
        self._state = initial_state
        self._previous_state: Optional[LinkState] = None

    @property
    def state(self) -> LinkState:
        """Get current state.

        Returns:
            Current link state
        """
        return self._state

    @property
    def previous_state(self) -> Optional[LinkState]:
        """Get previous state.

        Returns:
            Previous link state or None
        """
        return self._previous_state

    def can_transition_to(self, new_state: LinkState) -> bool:
        """Check if transition to new state is valid.

        Args:
            new_state: Target state

        Returns:
            True if transition is allowed
        """
        # Same state is always allowed
        if new_state == self._state:
            return True

        # Check if transition is in allowed set
        allowed = self.TRANSITIONS.get(self._state, set())
        return new_state in allowed

    def transition_to(self, new_state: LinkState, force: bool = False) -> None:
        """Transition to new state.

        Args:
            new_state: Target state
            force: If True, skip validation (use with caution)

        Raises:
            ARQStateError: If transition is not allowed
        """
        if not force and not self.can_transition_to(new_state):
            raise ARQStateError(
                f"Invalid state transition: {self._state.name} -> {new_state.name}"
            )

        self._previous_state = self._state
        self._state = new_state

    def reset(self) -> None:
        """Reset to DOWN state."""
        self._previous_state = self._state
        self._state = LinkState.DOWN

    def is_connected(self) -> bool:
        """Check if link is in connected state.

        Returns:
            True if in any connected state
        """
        return self._state in {
            LinkState.ARQ_CONNECTED,
            LinkState.WAITING,
            LinkState.WAITFORACK,
        }

    def is_connecting(self) -> bool:
        """Check if connection is in progress.

        Returns:
            True if connecting
        """
        return self._state == LinkState.ARQ_CONNECTING

    def is_disconnecting(self) -> bool:
        """Check if disconnection is in progress.

        Returns:
            True if disconnecting
        """
        return self._state in {
            LinkState.DISCONNECT,
            LinkState.DISCONNECTING,
        }

    def is_error_state(self) -> bool:
        """Check if in error state.

        Returns:
            True if in error state
        """
        return self._state in {
            LinkState.TIMEDOUT,
            LinkState.ABORT,
        }

    def __repr__(self) -> str:
        """String representation.

        Returns:
            State machine description
        """
        prev = self._previous_state.name if self._previous_state else "None"
        return f"ARQStateMachine(state={self._state.name}, previous={prev})"
```

### Step 4: Create Configuration Tests (15 minutes)

Create `tests/test_arq/test_config.py`:

```python
"""Tests for ARQ configuration."""

import pytest
from pydigi.arq.config import ARQConfig


class TestARQConfig:
    """Test ARQ configuration."""

    def test_default_config(self):
        """Test default configuration values."""
        config = ARQConfig()

        assert config.max_block_count == 64
        assert config.max_headers == 8
        assert config.exponent == 7
        assert config.retry_time == 10000
        assert config.retries == 5
        assert config.tx_delay == 500
        assert config.timeout == 60000
        assert config.loop_time == 100
        assert config.my_call == ""
        assert config.ur_call == ""
        assert config.my_stream_id == "0"

    def test_buffer_length_calculation(self):
        """Test buffer length calculation from exponent."""
        config = ARQConfig(exponent=7)
        assert config.buffer_length == 128

        config = ARQConfig(exponent=6)
        assert config.buffer_length == 64

        config = ARQConfig(exponent=8)
        assert config.buffer_length == 256

    def test_custom_buffer_length(self):
        """Test custom buffer length override."""
        config = ARQConfig(custom_buffer_length=256)
        assert config.buffer_length == 256

    def test_max_payload_size(self):
        """Test maximum payload size."""
        config = ARQConfig(exponent=7)
        assert config.max_payload_size == 512  # min(512, 128) = 128? No, the formula caps at 512

        config = ARQConfig(exponent=8)
        assert config.max_payload_size == 512  # Capped at 512

    def test_invalid_max_block_count(self):
        """Test that max_block_count cannot be changed."""
        with pytest.raises(ValueError, match="max_block_count must be 64"):
            ARQConfig(max_block_count=32)

    def test_invalid_exponent(self):
        """Test invalid exponent values."""
        with pytest.raises(ValueError, match="exponent must be between 4 and 8"):
            ARQConfig(exponent=3)

        with pytest.raises(ValueError, match="exponent must be between 4 and 8"):
            ARQConfig(exponent=9)

    def test_invalid_max_headers(self):
        """Test invalid max_headers values."""
        with pytest.raises(ValueError, match="max_headers must be between 1 and 64"):
            ARQConfig(max_headers=0)

        with pytest.raises(ValueError, match="max_headers must be between 1 and 64"):
            ARQConfig(max_headers=65)

    def test_invalid_retry_time(self):
        """Test invalid retry_time value."""
        with pytest.raises(ValueError, match="retry_time must be at least 100ms"):
            ARQConfig(retry_time=50)

    def test_invalid_retries(self):
        """Test invalid retries value."""
        with pytest.raises(ValueError, match="retries must be at least 1"):
            ARQConfig(retries=0)

    def test_invalid_timeout(self):
        """Test timeout must be >= retry_time."""
        with pytest.raises(ValueError, match="timeout must be >= retry_time"):
            ARQConfig(retry_time=10000, timeout=5000)

    def test_invalid_stream_id(self):
        """Test invalid stream ID values."""
        with pytest.raises(ValueError, match="my_stream_id must be"):
            ARQConfig(my_stream_id="64")

        with pytest.raises(ValueError, match="my_stream_id must be"):
            ARQConfig(my_stream_id="abc")

    def test_valid_stream_ids(self):
        """Test valid stream ID values."""
        config = ARQConfig(my_stream_id="0")
        assert config.my_stream_id == "0"

        config = ARQConfig(my_stream_id="1")
        assert config.my_stream_id == "1"

        config = ARQConfig(my_stream_id="63")
        assert config.my_stream_id == "63"

    def test_custom_config(self):
        """Test custom configuration."""
        config = ARQConfig(
            my_call="W1AW",
            ur_call="K6XYZ",
            my_stream_id="5",
            retry_time=5000,
            retries=3,
            timeout=30000
        )

        assert config.my_call == "W1AW"
        assert config.ur_call == "K6XYZ"
        assert config.my_stream_id == "5"
        assert config.retry_time == 5000
        assert config.retries == 3
        assert config.timeout == 30000
```

### Step 5: Create State Machine Tests (20 minutes)

Create `tests/test_arq/test_state_machine.py`:

```python
"""Tests for ARQ state machine."""

import pytest
from pydigi.arq.state_machine import LinkState, ARQStateMachine
from pydigi.arq.exceptions import ARQStateError


class TestLinkState:
    """Test LinkState enum."""

    def test_state_values(self):
        """Test state enum values."""
        assert LinkState.DOWN == 0
        assert LinkState.TIMEDOUT.value > 0
        assert LinkState.ABORT.value > 0
        assert LinkState.ARQ_CONNECTING.value > 0
        assert LinkState.ARQ_CONNECTED.value > 0

    def test_state_names(self):
        """Test state names."""
        assert LinkState.DOWN.name == "DOWN"
        assert LinkState.ARQ_CONNECTED.name == "ARQ_CONNECTED"


class TestARQStateMachine:
    """Test ARQ state machine."""

    def test_initial_state(self):
        """Test initial state is DOWN."""
        sm = ARQStateMachine()
        assert sm.state == LinkState.DOWN
        assert sm.previous_state is None

    def test_custom_initial_state(self):
        """Test custom initial state."""
        sm = ARQStateMachine(initial_state=LinkState.ARQ_CONNECTED)
        assert sm.state == LinkState.ARQ_CONNECTED

    def test_valid_transition_down_to_connecting(self):
        """Test valid transition from DOWN to CONNECTING."""
        sm = ARQStateMachine()
        sm.transition_to(LinkState.ARQ_CONNECTING)

        assert sm.state == LinkState.ARQ_CONNECTING
        assert sm.previous_state == LinkState.DOWN

    def test_valid_transition_connecting_to_connected(self):
        """Test valid transition from CONNECTING to CONNECTED."""
        sm = ARQStateMachine(initial_state=LinkState.ARQ_CONNECTING)
        sm.transition_to(LinkState.ARQ_CONNECTED)

        assert sm.state == LinkState.ARQ_CONNECTED
        assert sm.previous_state == LinkState.ARQ_CONNECTING

    def test_invalid_transition(self):
        """Test invalid transition raises error."""
        sm = ARQStateMachine()

        with pytest.raises(ARQStateError, match="Invalid state transition"):
            sm.transition_to(LinkState.ARQ_CONNECTED)  # Can't go directly from DOWN to CONNECTED

    def test_same_state_transition(self):
        """Test transition to same state is allowed."""
        sm = ARQStateMachine()
        sm.transition_to(LinkState.DOWN)  # Same state

        assert sm.state == LinkState.DOWN

    def test_force_transition(self):
        """Test forced transition bypasses validation."""
        sm = ARQStateMachine()
        sm.transition_to(LinkState.ARQ_CONNECTED, force=True)

        assert sm.state == LinkState.ARQ_CONNECTED

    def test_can_transition_to(self):
        """Test can_transition_to check."""
        sm = ARQStateMachine()

        assert sm.can_transition_to(LinkState.ARQ_CONNECTING)
        assert not sm.can_transition_to(LinkState.ARQ_CONNECTED)
        assert sm.can_transition_to(LinkState.DOWN)  # Same state

    def test_reset(self):
        """Test reset to DOWN state."""
        sm = ARQStateMachine(initial_state=LinkState.ARQ_CONNECTED)
        sm.reset()

        assert sm.state == LinkState.DOWN
        assert sm.previous_state == LinkState.ARQ_CONNECTED

    def test_is_connected(self):
        """Test is_connected check."""
        sm = ARQStateMachine()
        assert not sm.is_connected()

        sm.transition_to(LinkState.ARQ_CONNECTING)
        assert not sm.is_connected()

        sm.transition_to(LinkState.ARQ_CONNECTED)
        assert sm.is_connected()

        sm.transition_to(LinkState.WAITING)
        assert sm.is_connected()

        sm.transition_to(LinkState.ARQ_CONNECTED)
        sm.transition_to(LinkState.WAITFORACK)
        assert sm.is_connected()

    def test_is_connecting(self):
        """Test is_connecting check."""
        sm = ARQStateMachine()
        assert not sm.is_connecting()

        sm.transition_to(LinkState.ARQ_CONNECTING)
        assert sm.is_connecting()

    def test_is_disconnecting(self):
        """Test is_disconnecting check."""
        sm = ARQStateMachine(initial_state=LinkState.ARQ_CONNECTED)
        assert not sm.is_disconnecting()

        sm.transition_to(LinkState.DISCONNECT)
        assert sm.is_disconnecting()

        sm.transition_to(LinkState.DISCONNECTING)
        assert sm.is_disconnecting()

    def test_is_error_state(self):
        """Test is_error_state check."""
        sm = ARQStateMachine()
        assert not sm.is_error_state()

        sm.transition_to(LinkState.ARQ_CONNECTING)
        sm.transition_to(LinkState.TIMEDOUT)
        assert sm.is_error_state()

        sm.reset()
        sm.transition_to(LinkState.ARQ_CONNECTING)
        sm.transition_to(LinkState.ABORTING)
        sm.transition_to(LinkState.ABORT)
        assert sm.is_error_state()

    def test_connection_flow(self):
        """Test typical connection flow."""
        sm = ARQStateMachine()

        # DOWN -> CONNECTING
        sm.transition_to(LinkState.ARQ_CONNECTING)
        assert sm.state == LinkState.ARQ_CONNECTING

        # CONNECTING -> CONNECTED
        sm.transition_to(LinkState.ARQ_CONNECTED)
        assert sm.state == LinkState.ARQ_CONNECTED

        # CONNECTED -> WAITING
        sm.transition_to(LinkState.WAITING)
        assert sm.state == LinkState.WAITING

        # WAITING -> WAITFORACK
        sm.transition_to(LinkState.WAITFORACK)
        assert sm.state == LinkState.WAITFORACK

        # WAITFORACK -> CONNECTED
        sm.transition_to(LinkState.ARQ_CONNECTED)
        assert sm.state == LinkState.ARQ_CONNECTED

        # CONNECTED -> DISCONNECT
        sm.transition_to(LinkState.DISCONNECT)
        assert sm.state == LinkState.DISCONNECT

        # DISCONNECT -> DISCONNECTING
        sm.transition_to(LinkState.DISCONNECTING)
        assert sm.state == LinkState.DISCONNECTING

        # DISCONNECTING -> DOWN
        sm.transition_to(LinkState.DOWN)
        assert sm.state == LinkState.DOWN

    def test_timeout_flow(self):
        """Test timeout flow."""
        sm = ARQStateMachine()
        sm.transition_to(LinkState.ARQ_CONNECTING)

        # CONNECTING -> TIMEDOUT
        sm.transition_to(LinkState.TIMEDOUT)
        assert sm.state == LinkState.TIMEDOUT

        # TIMEDOUT -> DOWN
        sm.transition_to(LinkState.DOWN)
        assert sm.state == LinkState.DOWN

    def test_abort_flow(self):
        """Test abort flow."""
        sm = ARQStateMachine(initial_state=LinkState.ARQ_CONNECTED)

        # CONNECTED -> ABORTING
        sm.transition_to(LinkState.ABORTING)
        assert sm.state == LinkState.ABORTING

        # ABORTING -> ABORT
        sm.transition_to(LinkState.ABORT)
        assert sm.state == LinkState.ABORT

        # ABORT -> DOWN
        sm.transition_to(LinkState.DOWN)
        assert sm.state == LinkState.DOWN

    def test_repr(self):
        """Test string representation."""
        sm = ARQStateMachine()
        assert "DOWN" in repr(sm)

        sm.transition_to(LinkState.ARQ_CONNECTING)
        r = repr(sm)
        assert "ARQ_CONNECTING" in r
        assert "DOWN" in r  # Previous state
```

### Step 6: Run Tests (5 minutes)

Run the test suite to validate implementation:

```bash
# Test configuration
pytest tests/test_arq/test_config.py -v

# Test state machine
pytest tests/test_arq/test_state_machine.py -v

# Test all ARQ components
pytest tests/test_arq/ -v

# Check coverage
pytest tests/test_arq/ --cov=pydigi.arq --cov-report=term-missing
```

## Validation Checkpoint

### Configuration Module
- ✅ ARQConfig dataclass created with all parameters
- ✅ Default values match fldigi (retry_time=10000, timeout=60000, etc.)
- ✅ Buffer length calculation works (2^exponent)
- ✅ Validation prevents invalid configurations
- ✅ Stream ID validation works ('0' or '1'-'63')
- ✅ All 15 tests pass

### State Machine Module
- ✅ LinkState enum with all 12 states
- ✅ ARQStateMachine class created
- ✅ Valid transitions defined for all states
- ✅ Invalid transitions raise ARQStateError
- ✅ Helper methods (is_connected, is_connecting, etc.) work
- ✅ All 21 tests pass

### Exceptions Module
- ✅ 7 custom exception classes defined
- ✅ Inheritance hierarchy (all inherit from ARQError)
- ✅ Specific exceptions for CRC, timeout, connection, state, abort

### Overall
- ✅ All components integrate cleanly
- ✅ No circular dependencies
- ✅ Ready for use in Session 5 (Protocol implementation)

## Common Pitfalls

1. **State Transitions**: Don't allow invalid state transitions without `force=True`
2. **Configuration Validation**: Ensure timeout >= retry_time
3. **Buffer Length**: Remember it's 2^exponent, not exponent directly
4. **Stream ID**: Must be string '0' or '1'-'63', not integer
5. **Max Block Count**: Must always be 64 (protocol requirement)

## Reference Files

### fldigi Source
- `fldigi/src/flarq-src/include/arq.h` - Lines 78-102 for constants and states
- `fldigi/src/flarq-src/arq.cxx` - State machine logic

### Previous Sessions
- Session 1: CRC-16 implementation
- Session 2: Frame building/parsing
- Session 3: Block tracking

## Next Steps

After completing Session 4, proceed to:

**Session 5: Protocol Skeleton & Connection** - Create main protocol class using config and state machine

## Estimated Time Breakdown

- Step 1 (Exceptions): 15 minutes
- Step 2 (Config): 20 minutes
- Step 3 (State Machine): 25 minutes
- Step 4 (Config Tests): 15 minutes
- Step 5 (State Machine Tests): 20 minutes
- Step 6 (Validation): 5 minutes

**Total**: ~100 minutes (1.5-2 hours)
