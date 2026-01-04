"""Frame extraction from character stream.

This module provides the FrameExtractor class which bridges between
PSK decoder output (individual characters) and ARQ protocol input
(complete frames).
"""

from typing import Callable, Optional
from collections import deque

from .frame import ARQFrame, SOH, EOT


class FrameExtractor:
    """Extract ARQ frames from decoded character stream.

    The PSK decoder outputs individual characters via callback. The ARQ
    protocol needs complete frames. This class accumulates characters,
    detects frame boundaries (SOH/EOT markers), and validates CRC before
    forwarding frames to the ARQ protocol.

    Example:
        >>> def on_frame(frame_bytes):
        ...     print(f"Received frame: {len(frame_bytes)} bytes")
        >>>
        >>> extractor = FrameExtractor(on_frame)
        >>> # Connect to decoder
        >>> decoder.set_text_callback(extractor.process_char)
    """

    def __init__(
        self,
        frame_callback: Callable[[bytes], None],
        max_buffer_size: int = 1024,
        debug: bool = False,
    ):
        """Initialize frame extractor.

        Args:
            frame_callback: Called with complete valid frame bytes
            max_buffer_size: Maximum characters to buffer (default 1024)
            debug: Enable debug output (default False)
        """
        self._frame_callback = frame_callback
        self._max_buffer_size = max_buffer_size
        self._debug = debug

        # Character accumulation buffer
        self._buffer = deque(maxlen=max_buffer_size)

        # Statistics
        self.frames_extracted = 0
        self.crc_errors = 0
        self.format_errors = 0

    def process_char(self, char: str) -> None:
        """Process single character from decoder.

        Accumulates characters and extracts complete frames.
        Calls frame_callback when valid frame detected.

        Args:
            char: Single character from PSK decoder
        """
        # Add character to buffer
        self._buffer.append(char)

        # Try to extract frames from buffer
        self._extract_frames()

    def _extract_frames(self) -> None:
        """Scan buffer for complete frames and extract them.

        This method:
        1. Scans buffer for SOH start markers
        2. When SOH found, scans ahead for terminator (EOT or SOH)
        3. Extracts candidate frame and validates CRC
        4. If valid, calls frame_callback
        5. If invalid, discards and continues scanning
        """
        # Convert buffer to string for easier scanning
        buffer_str = ''.join(self._buffer)

        # Track where we are in processing
        search_start = 0

        while True:
            # Find next SOH marker
            soh_pos = buffer_str.find(chr(SOH), search_start)

            if soh_pos == -1:
                # No more SOH markers, done scanning
                # Keep only unprocessed portion of buffer
                if search_start > 0:
                    # Remove processed characters
                    for _ in range(search_start):
                        self._buffer.popleft()
                break

            # Found SOH, now look for terminator
            # Minimum frame: SOH + 3 header + 4 CRC + terminator = 9 bytes
            min_frame_end = soh_pos + 9
            if min_frame_end > len(buffer_str):
                # Not enough data yet for complete frame
                # Keep buffer starting from this SOH
                chars_to_remove = soh_pos
                for _ in range(chars_to_remove):
                    self._buffer.popleft()
                break

            # Scan for terminator after minimum frame size
            # Maximum frame: SOH (1) + 3 header + 512 payload + 4 CRC + terminator (1) = 521
            max_frame_end = min(soh_pos + 521, len(buffer_str))

            terminator_pos = None
            for pos in range(min_frame_end - 1, max_frame_end):
                if buffer_str[pos] in (chr(EOT), chr(SOH)):
                    # Found potential terminator (but not if it's SOH at start of next frame)
                    # Check if this could be EOT or SOH terminator
                    if buffer_str[pos] == chr(EOT):
                        # EOT is always a terminator
                        terminator_pos = pos
                        break
                    elif buffer_str[pos] == chr(SOH) and pos > soh_pos:
                        # SOH can be terminator for data blocks
                        # But need to verify this isn't start of next frame
                        # If we're at the right position for a data block terminator, use it
                        # Data block: SOH + 3 header + variable payload + 4 CRC + SOH
                        # The terminator should be at least 8 chars after SOH
                        if pos >= soh_pos + 8:
                            terminator_pos = pos
                            break

            if terminator_pos is None:
                # No terminator found yet
                # If we've scanned to max frame size, discard this SOH as invalid
                if max_frame_end >= soh_pos + 521:
                    # Frame too long, skip this SOH
                    if self._debug:
                        print(f"Frame too long, skipping SOH at {soh_pos}")
                    self.format_errors += 1
                    search_start = soh_pos + 1
                    continue
                else:
                    # Not enough data yet, keep buffer from SOH onwards
                    chars_to_remove = soh_pos
                    for _ in range(chars_to_remove):
                        self._buffer.popleft()
                    break

            # Found complete frame candidate
            frame_str = buffer_str[soh_pos:terminator_pos + 1]

            # Try to parse and validate frame
            try:
                frame_bytes = frame_str.encode('latin-1')
                # This validates CRC
                ARQFrame.parse(frame_bytes)

                # Valid frame - deliver to callback
                if self._debug:
                    print(f"Extracted frame: {len(frame_bytes)} bytes, type={ord(frame_str[3]):02X}")

                self._frame_callback(frame_bytes)
                self.frames_extracted += 1

                # Remove frame from buffer and continue scanning after it
                search_start = terminator_pos + 1

            except ValueError as e:
                # Invalid frame (CRC error or format error)
                if self._debug:
                    print(f"Invalid frame at {soh_pos}: {e}")

                # Check if this was a CRC error vs format error
                if "CRC mismatch" in str(e):
                    self.crc_errors += 1
                else:
                    self.format_errors += 1

                # Skip this SOH and continue scanning
                search_start = soh_pos + 1

        # If we processed anything, remove those characters from buffer
        if search_start > 0:
            for _ in range(search_start):
                if self._buffer:
                    self._buffer.popleft()

    def reset(self) -> None:
        """Clear internal buffer and state.

        This is useful when resyncing after signal loss or when
        starting a new session.
        """
        self._buffer.clear()

    def get_buffer_size(self) -> int:
        """Get current buffer size in characters.

        Returns:
            Number of characters in buffer
        """
        return len(self._buffer)

    def get_stats(self) -> dict:
        """Get extraction statistics.

        Returns:
            Dictionary with keys:
            - frames_extracted: Number of valid frames extracted
            - crc_errors: Number of CRC validation failures
            - format_errors: Number of format errors
            - buffer_size: Current buffer size
        """
        return {
            'frames_extracted': self.frames_extracted,
            'crc_errors': self.crc_errors,
            'format_errors': self.format_errors,
            'buffer_size': len(self._buffer),
        }
