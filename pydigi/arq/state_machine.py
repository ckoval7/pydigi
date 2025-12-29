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
        prev = self._previous_state.name if self._previous_state is not None else "None"
        return f"ARQStateMachine(state={self._state.name}, previous={prev})"
