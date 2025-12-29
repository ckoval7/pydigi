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
