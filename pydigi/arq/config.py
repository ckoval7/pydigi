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
