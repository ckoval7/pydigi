"""
FSQ (Fast Simple QSO) Modem

This module implements the FSQ digital mode, a robust MFSK mode designed
for keyboard-to-keyboard QSO and automated operations.

FSQ uses 33-tone MFSK with incremental frequency keying (IFK), similar to
DominoEX. The mode is highly resistant to frequency drift and provides
good performance on weak HF signals.

Key Features:
- 33 tones with 3 Hz spacing
- Variable baud rates: 1.5, 2.0, 3.0, 4.5, 6.0 (default 3.0)
- Incremental frequency keying (no absolute frequency reference needed)
- Two-symbol varicode encoding
- Sample rate: 12000 Hz

Reference: fldigi/src/fsq/fsq.cxx
Author: PyDigi Project
Date: 2025-12-15
"""

import numpy as np
from typing import Optional, Tuple
from pydigi.modems.base import Modem
from pydigi.varicode.fsq_varicode import encode_fsq_varicode, count_symbols


class FSQ(Modem):
    """
    FSQ (Fast Simple QSO) modem implementation.

    FSQ uses 33-tone MFSK with incremental frequency keying. Each symbol is
    transmitted as a tone that is relative to the previous tone, making it
    highly resistant to frequency drift.

    The tone calculation is: tone = (prev_tone + symbol + 1) % 33
    The frequency is: freq = (basetone + tone * spacing) * SR / symlen

    Attributes:
        baud_rate: Symbol rate in baud (1.5, 2.0, 3.0, 4.5, or 6.0)
        num_tones: Number of tones (always 33 for FSQ)
        tone_spacing: Spacing between tones in Hz (always 3.0 for FSQ)
        basetone: Base tone index (333 by default, relative to center frequency)
        sample_rate: Audio sample rate (12000 Hz for FSQ)
        symlen: Symbol length in samples
    """

    # FSQ constants
    FSQ_SAMPLE_RATE = 12000  # Fixed sample rate for FSQ
    FSQ_NUM_TONES = 33  # Number of tones
    FSQ_TONE_SPACING = 3.0  # Tone spacing in Hz
    FSQ_SYMLEN = 4096  # Symbol length constant for frequency calculation (not variable symlen!)

    # Valid baud rates for FSQ and their corresponding symbol lengths
    # Reference: fldigi/src/fsq/fsq.cxx lines 326-336
    VALID_BAUD_RATES = [1.5, 2.0, 3.0, 4.5, 6.0]
    SYMLEN_TABLE = {
        1.5: 8192,  # 12000 / 8192 = 1.46 baud
        2.0: 6144,  # 12000 / 6144 = 1.95 baud
        3.0: 4096,  # 12000 / 4096 = 2.93 baud
        4.5: 3072,  # 12000 / 3072 = 3.91 baud
        6.0: 2048,  # 12000 / 2048 = 5.86 baud
    }

    # Special sequences (reference: fldigi/src/fsq/fsq.cxx lines 72-78)
    FSQBOL = " \n"  # Beginning of line
    FSQEOL = "\n "  # End of line
    FSQEOT = "  \b  "  # End of transmission

    def __init__(self, baud_rate: float = 3.0, callsign: str = "PYDIGI"):
        """
        Initialize FSQ modem.

        Args:
            baud_rate: Symbol rate in baud (1.5, 2.0, 3.0, 4.5, or 6.0)
                      Default is 3.0 baud.
            callsign: Station callsign for preamble (default: "PYDIGI")

        Raises:
            ValueError: If baud_rate is not in VALID_BAUD_RATES
        """
        if baud_rate not in self.VALID_BAUD_RATES:
            raise ValueError(
                f"Invalid baud rate {baud_rate}. " f"Must be one of {self.VALID_BAUD_RATES}"
            )

        # Initialize base class with FSQ-specific parameters
        super().__init__(
            mode_name=f"FSQ-{baud_rate}", sample_rate=self.FSQ_SAMPLE_RATE, frequency=1500.0
        )

        self.baud_rate = baud_rate
        self.num_tones = self.FSQ_NUM_TONES
        self.tone_spacing = self.FSQ_TONE_SPACING
        self.callsign = callsign.upper()

        # Get symbol length from lookup table
        # FSQ uses fixed symlen values, not calculated from baud rate
        # Reference: fldigi/src/fsq/fsq.cxx lines 326-336
        self.symlen = self.SYMLEN_TABLE[self.baud_rate]

        # Set bandwidth (33 tones * 3 Hz spacing)
        self._bandwidth = self.num_tones * self.tone_spacing

        # Calculate basetone from frequency
        # NOTE: Uses FSQ_SYMLEN constant (4096), NOT variable symlen!
        # This ensures tone frequencies stay constant across all baud rates
        # Reference: fldigi/src/fsq/fsq.cxx lines 301-305
        import math

        basetone = math.ceil(
            1.0 * (self.frequency - self._bandwidth / 2) * self.FSQ_SYMLEN / self.sample_rate
        )
        incr = basetone % int(self.tone_spacing)
        self.basetone = basetone - incr

        # Transmit state
        self.txphase = 0.0  # Transmit phase accumulator
        self.prevtone = 0  # Previous tone (for incremental keying)

    def _send_tone(self, tone: int, output: np.ndarray, offset: int) -> int:
        """
        Generate audio for a single tone.

        Reference: fldigi/src/fsq/fsq.cxx lines 1342-1365

        The tone frequency is calculated as:
        freq = (basetone + tone * spacing) * sample_rate / FSQ_SYMLEN

        IMPORTANT: Uses FSQ_SYMLEN constant (4096), NOT variable symlen!
        This ensures tones stay at the same frequencies for all baud rates.

        Args:
            tone: Tone index (0-32)
            output: Output buffer to write samples to
            offset: Starting offset in output buffer

        Returns:
            New offset after writing samples
        """
        # Calculate frequency (reference: fldigi line 1349)
        # CRITICAL: Uses FSQ_SYMLEN (constant), not self.symlen (variable)!
        # freq = (tx_basetone + tone * spacing) * samplerate / FSQ_SYMLEN
        freq = (self.basetone + tone * self.tone_spacing) * self.sample_rate / self.FSQ_SYMLEN

        # Generate tone samples
        phaseincr = 2.0 * np.pi * freq / self.sample_rate

        for i in range(self.symlen):
            if offset + i < len(output):
                output[offset + i] = np.cos(self.txphase)
                self.txphase -= phaseincr
                if self.txphase < 0:
                    self.txphase += 2.0 * np.pi

        return offset + self.symlen

    def _send_symbol(self, symbol: int, output: np.ndarray, offset: int) -> int:
        """
        Send a symbol using incremental frequency keying.

        Reference: fldigi/src/fsq/fsq.cxx lines 1367-1372

        FSQ uses incremental frequency keying where the tone is calculated as:
        tone = (prev_tone + symbol + 1) mod 33

        This makes FSQ resistant to frequency drift since only the relative
        tone changes matter, not the absolute frequencies.

        Args:
            symbol: Symbol value (0-31)
            output: Output buffer
            offset: Current offset in buffer

        Returns:
            New offset after writing samples
        """
        # Incremental frequency keying (reference: fldigi line 1370)
        # tone = (prevtone + sym + 1) % 33
        tone = (self.prevtone + symbol + 1) % self.num_tones

        offset = self._send_tone(tone, output, offset)
        self.prevtone = tone

        return offset

    def _send_idle(self, output: np.ndarray, offset: int) -> int:
        """
        Send idle pattern (two symbols: 28 and 30).

        Reference: fldigi/src/fsq/fsq.cxx lines 1374-1378

        Args:
            output: Output buffer
            offset: Current offset in buffer

        Returns:
            New offset after writing samples
        """
        offset = self._send_symbol(28, output, offset)
        offset = self._send_symbol(30, output, offset)
        return offset

    def _send_char(self, ch: str, output: np.ndarray, offset: int) -> int:
        """
        Send a single character using FSQ varicode.

        Reference: fldigi/src/fsq/fsq.cxx lines 1382-1397

        Each character is encoded as one or two symbols:
        - If sym2 < 29: Only sym1 is transmitted
        - If sym2 >= 29: Both sym1 and sym2 are transmitted

        Args:
            ch: Character to send
            output: Output buffer
            offset: Current offset in buffer

        Returns:
            New offset after writing samples
        """
        if not ch:  # Null character = idle
            return self._send_idle(output, offset)

        # Get varicode for character
        ascii_val = ord(ch)
        symbols = encode_fsq_varicode(ch)

        if len(symbols) > 0:
            sym1, sym2 = symbols[0]

            # Always send first symbol
            offset = self._send_symbol(sym1, output, offset)

            # Send second symbol only if >= 29
            if sym2 >= 29:
                offset = self._send_symbol(sym2, output, offset)

        return offset

    def _send_string(self, text: str, output: np.ndarray, offset: int) -> int:
        """
        Send a text string.

        Args:
            text: Text to transmit
            output: Output buffer
            offset: Current offset in buffer

        Returns:
            New offset after writing samples
        """
        for ch in text:
            offset = self._send_char(ch, output, offset)
        return offset

    def tx_init(self) -> None:
        """
        Initialize transmitter state.

        This method initializes the phase accumulator and tone state
        before transmission begins.
        """
        self.txphase = 0.0
        self.prevtone = 0
        self._tx_initialized = True

    def _tx_process_internal(
        self, text: str, add_preamble: bool = True, add_postamble: bool = True
    ) -> np.ndarray:
        """
        Generate FSQ transmission for the given text.

        Reference: fldigi/src/fsq/fsq.cxx lines 1497-1536

        The transmission sequence is:
        1. Preamble: " \n" + callsign + ":" (if enabled)
        2. Text data
        3. Postamble: "\n " (FSQEOL) (if enabled)

        Args:
            text: Text to transmit
            add_preamble: Add preamble sequence (default: True)
            add_postamble: Add postamble sequence (default: True)

        Returns:
            Audio samples as numpy array
        """
        # Initialize transmit state
        self.txphase = 0.0
        self.prevtone = 0

        # Estimate buffer size needed
        preamble_text = ""
        postamble_text = ""

        if add_preamble:
            # Preamble: " \n" + callsign + ":" (reference: fldigi lines 1502-1506)
            preamble_text = " " + self.FSQBOL + self.callsign + ":"

        if add_postamble:
            # Postamble: "\n " (FSQEOL) (reference: fldigi lines 1514-1516)
            postamble_text = self.FSQEOL

        full_text = preamble_text + text + postamble_text
        estimated_symbols = count_symbols(full_text) + 4  # +4 for safety margin
        buffer_size = int(estimated_symbols * self.symlen * 1.2)  # 20% extra

        # Allocate output buffer
        output = np.zeros(buffer_size, dtype=np.float32)
        offset = 0

        # Send preamble
        if add_preamble:
            offset = self._send_string(preamble_text, output, offset)

        # Send data
        offset = self._send_string(text, output, offset)

        # Send postamble
        if add_postamble:
            offset = self._send_string(postamble_text, output, offset)

        # Trim to actual length
        return output[:offset]

    def tx_process(self, text: str) -> np.ndarray:
        """
        Process text and generate modulated audio samples.

        This is the main interface required by the base Modem class.

        Args:
            text: Text to transmit

        Returns:
            Audio samples as numpy array
        """
        return self._tx_process_internal(text, add_preamble=True, add_postamble=True)

    def modulate(
        self,
        text: str,
        frequency: float = 1500.0,
        sample_rate: Optional[int] = None,
        add_preamble: bool = True,
        add_postamble: bool = True,
    ) -> np.ndarray:
        """
        Modulate text to FSQ audio signal.

        Note: FSQ requires 12000 Hz sample rate. If a different sample_rate is
        specified, the output will be resampled.

        Args:
            text: Text to transmit
            frequency: Center frequency in Hz (default: 1500 Hz)
            sample_rate: Desired output sample rate (if None, uses 12000 Hz)
            add_preamble: Add preamble with callsign (default: True)
            add_postamble: Add postamble (default: True)

        Returns:
            Modulated audio samples

        Example:
            >>> fsq = FSQ(baud_rate=3.0, callsign="W1ABC")
            >>> audio = fsq.modulate("CQ CQ CQ DE W1ABC")
            >>> save_wav("fsq_output.wav", audio, 12000)
        """
        # Update frequency and recalculate basetone if frequency changed
        if frequency != self.frequency:
            self.frequency = frequency

            # Recalculate basetone for new frequency
            # Reference: fldigi/src/fsq/fsq.cxx lines 301-305
            import math

            basetone = math.ceil(
                1.0 * (self.frequency - self._bandwidth / 2) * self.FSQ_SYMLEN / self.sample_rate
            )
            incr = basetone % int(self.tone_spacing)
            self.basetone = basetone - incr

        # Initialize transmitter
        self.tx_init()

        # Generate baseband signal at FSQ sample rate (12000 Hz)
        baseband = self._tx_process_internal(text, add_preamble, add_postamble)

        # FSQ tones are already centered at the desired frequency
        # The basetone calculation includes the center frequency offset
        # So we don't need frequency shifting like other modes

        # Resample if needed
        if sample_rate is not None and sample_rate != self.FSQ_SAMPLE_RATE:
            # Simple resampling using linear interpolation
            old_length = len(baseband)
            new_length = int(old_length * sample_rate / self.FSQ_SAMPLE_RATE)
            old_indices = np.linspace(0, old_length - 1, old_length)
            new_indices = np.linspace(0, old_length - 1, new_length)
            output = np.interp(new_indices, old_indices, baseband)
        else:
            output = baseband

        return output

    def estimate_duration(
        self, text: str, add_preamble: bool = True, add_postamble: bool = True
    ) -> float:
        """
        Estimate transmission duration in seconds.

        Args:
            text: Text to transmit
            add_preamble: Include preamble in estimate
            add_postamble: Include postamble in estimate

        Returns:
            Estimated duration in seconds
        """
        preamble_text = ""
        postamble_text = ""

        if add_preamble:
            preamble_text = " " + self.FSQBOL + self.callsign + ":"

        if add_postamble:
            postamble_text = self.FSQEOL

        full_text = preamble_text + text + postamble_text
        num_symbols = count_symbols(full_text)

        # Duration = symbols * symlen / sample_rate
        # (Use actual symlen for accurate timing)
        return num_symbols * self.symlen / self.sample_rate


# Convenience functions for different FSQ speeds


def FSQ_2() -> FSQ:
    """Create FSQ modem at 2.0 baud."""
    return FSQ(baud_rate=2.0)


def FSQ_3() -> FSQ:
    """Create FSQ modem at 3.0 baud (standard speed)."""
    return FSQ(baud_rate=3.0)


def FSQ_6() -> FSQ:
    """Create FSQ modem at 6.0 baud (fast speed)."""
    return FSQ(baud_rate=6.0)
