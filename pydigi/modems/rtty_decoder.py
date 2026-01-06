"""
RTTY (Radioteletype) Decoder Implementation.

Decodes RTTY signals using FSK demodulation and Baudot character decoding.

The decoder uses:
- Dual Goertzel filters for mark/space tone detection
- Symbol timing recovery (SymbolSlicer or EarlyLateGate)
- ToneDCD for signal detection
- ToneAFC for frequency tracking
- Baudot decoder for character recovery

References:
    - fldigi/src/rtty/rtty.cxx
    - pydigi/modems/rtty.py (transmitter)
"""

import numpy as np
from typing import Optional, Callable, List
from ..core.filters import GoertzelFilter
from ..core.timing_recovery import SymbolSlicer, EarlyLateGate
from ..core.dcd import EnergyDCD
from ..core.afc import ToneAFC
from ..varicode.baudot import decode_baudot, BAUDOT_LTRS, BAUDOT_FIGS, LETTERS, FIGURES
from collections import deque


class RTTYDecoder:
    """
    RTTY (Radioteletype) decoder using FSK demodulation.

    Decodes RTTY signals by detecting mark and space tones, recovering
    bit timing, and decoding Baudot characters.

    Args:
        baud: Symbol rate in baud (default: 45.45)
        shift: Frequency shift in Hz (default: 170)
        bits: Number of data bits - 5, 7, or 8 (default: 5 for Baudot)
        stop_bits: Number of stop bits - 1.0, 1.5, or 2.0 (default: 1.5)
        sample_rate: Audio sample rate in Hz (default: 8000)
        frequency: Center frequency in Hz (default: 1000)
        use_ita2: Use ITA-2 encoding (True) or US-TTY (False)
        use_afc: Enable automatic frequency control (default: True)
        use_dcd: Enable data carrier detect (default: True)
        text_callback: Optional callback for decoded characters

    Example:
        >>> decoder = RTTYDecoder(baud=45.45, shift=170)
        >>> decoder.text_callback = lambda c: print(c, end='')
        >>> decoder.process(audio_samples)
    """

    def __init__(
        self,
        baud: float = 45.45,
        shift: float = 170.0,
        bits: int = 5,
        stop_bits: float = 1.5,
        sample_rate: float = 8000.0,
        frequency: float = 1000.0,
        use_ita2: bool = True,
        use_afc: bool = True,
        use_dcd: bool = True,
        text_callback: Optional[Callable[[str], None]] = None,
    ):
        """Initialize RTTY decoder."""
        self.baud = baud
        self.shift = shift
        self.bits = bits
        self.stop_bits = stop_bits
        self.sample_rate = sample_rate
        self.frequency = frequency
        self.use_ita2 = use_ita2
        self.use_afc = use_afc
        self.use_dcd = use_dcd
        self.text_callback = text_callback

        # Calculate mark and space frequencies
        # Mark = center + shift/2 (logic 1)
        # Space = center - shift/2 (logic 0)
        self.mark_freq = frequency + shift / 2.0
        self.space_freq = frequency - shift / 2.0

        # Calculate timing parameters
        self.samples_per_bit = int(sample_rate / baud)
        self.stop_samples = int(self.samples_per_bit * stop_bits)

        # Initialize Goertzel filters for tone detection
        # Use one symbol period for Goertzel block size
        self.mark_filter = GoertzelFilter(self.mark_freq, sample_rate, self.samples_per_bit)
        self.space_filter = GoertzelFilter(self.space_freq, sample_rate, self.samples_per_bit)

        # Initialize timing recovery (simple slicer for now)
        self.timing = SymbolSlicer(samples_per_symbol=self.samples_per_bit)

        # Initialize DCD (data carrier detect)
        if self.use_dcd:
            # EnergyDCD requires batch processing, so we buffer samples
            self.dcd = EnergyDCD(
                threshold_db=6.0,   # 6 dB SNR threshold
                attack=0.1,         # Fast attack
                decay=0.01,         # Slow decay
                hysteresis_db=2.0   # 2 dB hysteresis
            )
            self.dcd_buffer = deque(maxlen=self.samples_per_bit)
            self.dcd_active = False
            self.snr_db = 0.0
        else:
            self.dcd = None
            self.dcd_buffer = None
            self.dcd_active = True  # Always active if DCD disabled
            self.snr_db = 0.0

        # AFC not yet implemented (would require tracking tone frequencies)
        # TODO: Add AFC support for frequency offset tracking
        self.afc = None
        self.freq_offset = 0.0

        # Bit decoding state
        self.bit_buffer = []  # Collected bits for current character
        self.bit_state = "IDLE"  # IDLE, START, DATA, STOP
        self.data_bit_count = 0
        self.stop_bit_count = 0

        # Baudot decoding state
        self.baudot_mode = LETTERS
        self.decoded_codes = []  # For testing/analysis

        # Statistics
        self.total_chars = 0
        self.errors = 0

    def reset(self):
        """Reset decoder state."""
        self.mark_filter.reset()
        self.space_filter.reset()
        self.timing.reset()

        if self.dcd:
            self.dcd.reset()
            self.dcd_buffer.clear()
            self.dcd_active = False
            self.snr_db = 0.0

        if self.afc:
            self.afc.reset()
            self.freq_offset = 0.0

        self.bit_buffer = []
        self.bit_state = "IDLE"
        self.data_bit_count = 0
        self.stop_bit_count = 0
        self.baudot_mode = LETTERS
        self.decoded_codes = []
        self.total_chars = 0
        self.errors = 0

    def _process_sample(self, sample: float) -> None:
        """
        Process a single audio sample.

        Args:
            sample: Audio sample value
        """
        # Update DCD (if enabled)
        if self.dcd:
            # Buffer samples for DCD batch processing
            self.dcd_buffer.append(sample)

            # Update DCD every symbol period
            if len(self.dcd_buffer) >= self.samples_per_bit:
                # Convert buffer to numpy array and update DCD
                buffer_array = np.array(self.dcd_buffer)
                self.dcd_active, self.snr_db = self.dcd.update(buffer_array)

                # Clear buffer for next period
                self.dcd_buffer.clear()

            # If no signal detected, reset to IDLE and skip processing
            if not self.dcd_active:
                if self.bit_state != "IDLE":
                    self.bit_state = "IDLE"
                    self.bit_buffer = []
                return

        # Process through Goertzel filters
        mark_mag = self.mark_filter.filter(sample)
        space_mag = self.space_filter.filter(sample)

        # Only process when Goertzel produces output (every samples_per_bit)
        if mark_mag is None or space_mag is None:
            return

        # Make bit decision: 1 if mark > space, else 0
        bit = 1 if mark_mag > space_mag else 0

        # Decode the bit
        self._decode_bit(bit)

    def _decode_bit(self, bit: int) -> None:
        """
        Decode a single bit and manage frame state machine.

        RTTY frame format:
        - 1 start bit (space/0)
        - 5 data bits (LSB first)
        - stop bits (mark/1)

        Args:
            bit: Received bit (0 or 1)
        """
        if self.bit_state == "IDLE":
            # Look for start bit (0)
            if bit == 0:
                self.bit_state = "START"
                self.bit_buffer = []
                self.data_bit_count = 0
                self.stop_bit_count = 0

        elif self.bit_state == "START":
            # Start bit received, now collect data bits
            self.bit_state = "DATA"
            self.bit_buffer.append(bit)
            self.data_bit_count = 1

        elif self.bit_state == "DATA":
            # Collect data bits (LSB first)
            self.bit_buffer.append(bit)
            self.data_bit_count += 1

            if self.data_bit_count >= self.bits:
                # All data bits received, expect stop bit(s)
                self.bit_state = "STOP"
                self.stop_bit_count = 0

        elif self.bit_state == "STOP":
            # Stop bit(s) should be mark (1)
            self.stop_bit_count += 1

            # Check for framing error
            if bit != 1:
                # Framing error - stop bit should be mark
                self.errors += 1
                self.bit_state = "IDLE"
                return

            # Determine how many stop bits to expect
            # For 1.5 stop bits at 45.45 baud, we check after 1 bit
            # For 2.0 stop bits, we check after 2 bits
            expected_stop_bits = 1 if self.stop_bits < 2.0 else 2

            if self.stop_bit_count >= expected_stop_bits:
                # Complete character received
                self._decode_character()
                self.bit_state = "IDLE"

    def _decode_character(self) -> None:
        """
        Decode the collected bits into a Baudot character.

        Converts the 5-bit code to ASCII using Baudot tables,
        handling LTRS/FIGS shift states.
        """
        if len(self.bit_buffer) != self.bits:
            return

        # Convert bits to Baudot code (LSB first)
        code = 0
        for i, bit in enumerate(self.bit_buffer):
            code |= bit << i

        # Store for analysis
        self.decoded_codes.append(code)

        # Decode using Baudot tables
        char = self._baudot_to_char(code)

        if char is not None:
            self.total_chars += 1
            if self.text_callback:
                self.text_callback(char)

    def _baudot_to_char(self, code: int) -> Optional[str]:
        """
        Convert Baudot code to ASCII character.

        Handles LTRS/FIGS shift codes and mode switching.

        Args:
            code: 5-bit Baudot code (0-31)

        Returns:
            ASCII character, or None if it's a shift code
        """
        # Handle shift codes
        if code == BAUDOT_LTRS:
            self.baudot_mode = LETTERS
            return None
        elif code == BAUDOT_FIGS:
            self.baudot_mode = FIGURES
            return None

        # Decode using current mode
        # Use the decode_baudot function with a single code
        try:
            text = decode_baudot([code], use_ita2=self.use_ita2)
            if self.baudot_mode == LETTERS:
                # Already decoded in letters mode by default
                return text
            else:
                # Need to manually decode in figures mode
                from ..varicode.baudot import ITA2_FIGURES, USTTY_FIGURES

                figures_table = ITA2_FIGURES if self.use_ita2 else USTTY_FIGURES
                char = figures_table[code & 0x1F]
                if char and char not in ["\0"]:
                    return char
                return None
        except:
            return None

    def process(self, samples: np.ndarray) -> None:
        """
        Process audio samples through the decoder.

        Args:
            samples: Array of audio samples
        """
        for sample in samples:
            self._process_sample(sample)

    def demodulate(self, samples: np.ndarray) -> str:
        """
        Synchronous API: Decode audio samples and return text.

        This is a blocking call that processes all samples and returns
        the decoded text.

        Args:
            samples: Array of audio samples

        Returns:
            Decoded text string

        Example:
            >>> decoder = RTTYDecoder(baud=45.45, shift=170)
            >>> text = decoder.demodulate(audio_samples)
            >>> print(text)
        """
        decoded_chars = []

        def capture_char(c):
            decoded_chars.append(c)

        # Temporarily override callback
        original_callback = self.text_callback
        self.text_callback = capture_char

        # Process samples
        self.process(samples)

        # Restore callback
        self.text_callback = original_callback

        return "".join(decoded_chars)

    def get_statistics(self) -> dict:
        """
        Get decoder statistics.

        Returns:
            Dictionary with decoder stats
        """
        return {
            "total_chars": self.total_chars,
            "errors": self.errors,
            "error_rate": self.errors / max(1, self.total_chars),
            "dcd_active": self.dcd_active,
            "snr_db": self.snr_db,
            "freq_offset": self.freq_offset,
            "mode": "ITA-2" if self.use_ita2 else "US-TTY",
        }

    def __str__(self) -> str:
        """String representation."""
        return (
            f"RTTYDecoder(baud={self.baud}, shift={self.shift}, "
            f"bits={self.bits}, stop={self.stop_bits}, "
            f"{'ITA-2' if self.use_ita2 else 'US-TTY'})"
        )
