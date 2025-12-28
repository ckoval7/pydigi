"""
NAVTEX and SITOR-B Modem Implementation.

NAVTEX (Navigational Telex) is a maritime safety broadcast system using
SITOR-B (AMTOR-B) modulation with Forward Error Correction.

Technical specifications:
- Modulation: FSK (Frequency Shift Keying)
- Baud rate: 100 baud
- Shift: 170 Hz (±85 Hz deviation)
- Character encoding: CCIR-476 (7-bit with 4 bits set for error detection)
- FEC: Each character transmitted twice with interleaving
- Standard frequencies: 490, 518, 4209.5 kHz

Message format:
- Phasing signal (carrier): 10 seconds (first message) or 5 seconds
- Header: "ZCZC " + origin + subject + number (2 digits) + CR + LF
- Message text
- Trailer: CR + LF + "NNNN" + CR + LF + LF
- End phasing: 2 seconds (alpha signal)

References:
    - fldigi/src/navtex/navtex.cxx
    - ITU-R M.540-2 (NAVTEX technical characteristics)
    - CCIR Recommendation 476-4
"""

import numpy as np
from typing import Optional, List
from scipy import signal
from ..core.oscillator import NCO
from ..modems.base import Modem
from ..varicode.navtex_varicode import (
    CCIR476Encoder,
    create_fec_interleaved,
)


class NAVTEX(Modem):
    """
    NAVTEX modem using SITOR-B modulation with FEC.

    Implements the NAVTEX maritime safety broadcast system using FSK
    modulation with CCIR-476 encoding and forward error correction.

    Args:
        use_ita2: Use ITA-2 encoding (True) or US-TTY (False)
        sitor_b_only: If True, transmit raw SITOR-B without NAVTEX headers
        tx_amplitude: Transmit amplitude scaling (0.0 to 1.0, default: 0.9)

    Example:
        >>> navtex = NAVTEX()
        >>> audio = navtex.modulate("WEATHER WARNING", frequency=1000, sample_rate=11025)
    """

    # Fixed NAVTEX parameters
    BAUD_RATE = 100.0  # 100 baud
    SHIFT = 170.0  # 170 Hz shift
    DEVIATION = 85.0  # ±85 Hz deviation (shift/2)
    BITS_PER_CHAR = 7  # CCIR-476 uses 7 bits
    DEFAULT_SAMPLE_RATE = 11025  # Standard sample rate for NAVTEX

    def __init__(
        self,
        use_ita2: bool = True,
        sitor_b_only: bool = False,
        tx_amplitude: float = 0.9,
        use_filtering: bool = True,
    ):
        """Initialize NAVTEX modem.

        Args:
            use_ita2: Use ITA-2 encoding (True) or US-TTY (False)
            sitor_b_only: If True, transmit raw SITOR-B without NAVTEX headers
            tx_amplitude: Transmit amplitude scaling (0.0 to 1.0, default: 0.9)
            use_filtering: Apply baseband lowpass filtering to reduce spectral splatter
        """
        super().__init__(mode_name="NAVTEX" if not sitor_b_only else "SITOR-B")

        self.use_ita2 = use_ita2
        self.sitor_b_only = sitor_b_only
        self.tx_amplitude = max(0.0, min(1.0, tx_amplitude))
        self.use_filtering = use_filtering

        # CCIR-476 encoder
        self.encoder = CCIR476Encoder(use_ita2=use_ita2)

        # Message counter for NAVTEX headers
        self.message_counter = 1

        # Oscillators and parameters (initialized in tx_init)
        self.mark_nco = None
        self.space_nco = None
        self.center_nco = None
        self.sample_rate = None
        self.samples_per_bit = None

    def tx_init(self):
        """Initialize transmitter."""
        # Use NAVTEX standard sample rate if not set
        if self.sample_rate is None:
            self.sample_rate = self.DEFAULT_SAMPLE_RATE

        # Calculate timing
        # NAVTEX uses exactly 110.25 samples per bit at 11025 Hz
        self.samples_per_bit = self.sample_rate / self.BAUD_RATE

        # Initialize oscillators for mark, space, and center frequencies
        self.mark_nco = NCO(self.sample_rate)
        self.space_nco = NCO(self.sample_rate)
        self.center_nco = NCO(self.sample_rate)

        # Reset encoder
        self.encoder.reset()

    def _generate_baseband_bit(self, bit_value: int, duration: float = 1.0) -> np.ndarray:
        """
        Generate baseband representation for a single bit.

        Instead of generating the modulated tone directly, this creates a
        baseband signal that will be filtered before modulation.

        Args:
            bit_value: 0 for space, 1 for mark
            duration: Duration multiplier (default: 1.0 for one bit period)

        Returns:
            Baseband samples (1.0 for mark, -1.0 for space)
        """
        num_samples = int(self.samples_per_bit * duration)

        # Baseband: +1 for mark (binary 1), -1 for space (binary 0)
        baseband_value = 1.0 if bit_value else -1.0

        return np.full(num_samples, baseband_value, dtype=np.float32)

    def _generate_phasing(self, duration: float) -> np.ndarray:
        """
        Generate phasing signal (carrier at center frequency).

        The phasing signal is transmitted before each message to allow
        receivers to synchronize.

        Args:
            duration: Duration in seconds

        Returns:
            Audio samples for phasing signal
        """
        num_samples = int(self.sample_rate * duration)
        self.center_nco.frequency = self.frequency
        samples = self.center_nco.step_real(num_samples)
        return samples * self.tx_amplitude

    def _generate_baseband_char(self, code: int) -> np.ndarray:
        """
        Generate baseband representation for a 7-bit CCIR-476 character.

        Each character consists of 7 bits transmitted LSB first.

        Args:
            code: 7-bit CCIR-476 code

        Returns:
            Baseband samples for the character (±1.0)
        """
        samples = []

        # Transmit 7 bits, LSB first
        for i in range(7):
            bit = (code >> i) & 1
            bit_samples = self._generate_baseband_bit(bit)
            samples.append(bit_samples)

        return np.concatenate(samples)

    def _generate_message_with_header(
        self, text: str, is_first: bool = True, is_last: bool = True
    ) -> np.ndarray:
        """
        Generate complete NAVTEX message with header and trailer.

        Args:
            text: Message text to transmit
            is_first: If True, send 10s phasing; if False, send 5s
            is_last: If True, send 2s end phasing

        Returns:
            Audio samples for complete message
        """
        samples = []

        # 1. Phasing signal (already at audio frequency)
        phasing_duration = 10.0 if is_first else 5.0
        samples.append(self._generate_phasing(phasing_duration))

        # 2. NAVTEX header: "ZCZC " + origin + subject + number + CR + LF
        origin = "Z"  # Z for testing/unknown
        subject = "I"  # I for "Not used"
        header = f"ZCZC {origin}{subject}{self.message_counter:02d}\r\n"
        self.message_counter = (self.message_counter + 1) % 100

        # 3. Full message with trailer
        full_text = header + text + "\r\nNNNN\r\n\n"

        # 4. Encode to CCIR-476 codes
        codes = self.encoder.encode(full_text)

        # 5. Apply FEC interleaving
        fec_codes = create_fec_interleaved(codes)

        # 6. Generate BASEBAND for all codes
        baseband_samples = []
        for code in fec_codes:
            char_baseband = self._generate_baseband_char(code)
            baseband_samples.append(char_baseband)

        baseband = np.concatenate(baseband_samples)

        # 7. Filter baseband BEFORE modulation
        filtered_baseband = self._apply_baseband_filter(baseband)

        # 8. Modulate filtered baseband to FSK
        fsk_audio = self._modulate_baseband_to_fsk(filtered_baseband)
        samples.append(fsk_audio)

        # 9. End phasing (alpha signal)
        if is_last:
            samples.append(self._generate_phasing(2.0))

        return np.concatenate(samples)

    def _generate_sitor_b(self, text: str) -> np.ndarray:
        """
        Generate raw SITOR-B transmission without NAVTEX headers.

        Includes 1 second of silence before and after the message to help
        with decoder synchronization and clean start/stop.

        Args:
            text: Message text to transmit

        Returns:
            Audio samples for SITOR-B message with leading/trailing silence
        """
        samples = []

        # 1. Add 1 second of silence at the start
        silence_samples = int(self.sample_rate * 1.0)
        samples.append(np.zeros(silence_samples, dtype=np.float32))

        # 2. Encode to CCIR-476 codes
        codes = self.encoder.encode(text)

        # 3. Apply FEC interleaving
        fec_codes = create_fec_interleaved(codes)

        # 4. Generate BASEBAND for all codes
        baseband_samples = []
        for code in fec_codes:
            char_baseband = self._generate_baseband_char(code)
            baseband_samples.append(char_baseband)

        baseband = np.concatenate(baseband_samples)

        # 5. Filter baseband BEFORE modulation
        filtered_baseband = self._apply_baseband_filter(baseband)

        # 6. Modulate filtered baseband to FSK
        fsk_audio = self._modulate_baseband_to_fsk(filtered_baseband)
        samples.append(fsk_audio)

        # 7. Add 1 second of silence at the end
        samples.append(np.zeros(silence_samples, dtype=np.float32))

        return np.concatenate(samples)

    def _apply_baseband_filter(self, baseband: np.ndarray) -> np.ndarray:
        """
        Apply lowpass filter to baseband signal to reduce spectral splatter.

        This smooths the transitions between mark and space in the baseband
        BEFORE modulation, which is the correct approach for FSK.

        Args:
            baseband: Input baseband samples (±1.0)

        Returns:
            Filtered baseband samples
        """
        if not self.use_filtering:
            return baseband

        # For baseband filtering, we want to limit bandwidth to
        # approximately the baud rate. This smooths transitions
        # between bits without losing the signal.
        # Using ~1.2x baud rate gives good balance
        cutoff = self.BAUD_RATE * 1.2

        # Design lowpass filter
        nyquist = self.sample_rate / 2.0
        normalized_cutoff = cutoff / nyquist

        # Ensure cutoff is valid
        normalized_cutoff = max(0.01, min(normalized_cutoff, 0.95))

        # 5th order Butterworth lowpass filter
        b, a = signal.butter(5, normalized_cutoff, btype="low")

        # Apply zero-phase filtering to avoid group delay
        filtered = signal.filtfilt(b, a, baseband)

        return filtered.astype(np.float32)

    def _modulate_baseband_to_fsk(self, baseband: np.ndarray) -> np.ndarray:
        """
        Modulate filtered baseband signal to FSK audio.

        Takes a baseband signal (±1.0) and generates FSK by varying
        the frequency between mark and space based on the baseband value.

        Args:
            baseband: Filtered baseband samples (approximately ±1.0)

        Returns:
            FSK modulated audio samples
        """
        # Pre-allocate output array
        output = np.zeros(len(baseband), dtype=np.float32)

        # Generate FSK: frequency varies based on baseband value
        # baseband = +1 -> mark frequency (center + deviation)
        # baseband = -1 -> space frequency (center - deviation)
        # baseband = 0 -> center frequency
        # Filtered baseband will have intermediate values during transitions

        # Initialize phase accumulator
        phase = 0.0
        phase_increment_center = 2.0 * np.pi * self.frequency / self.sample_rate

        for i in range(len(baseband)):
            # Instantaneous frequency based on baseband value
            # Normalize baseband to ±1 range and scale by deviation
            freq_offset = baseband[i] * self.DEVIATION
            instantaneous_freq = self.frequency + freq_offset

            # Phase increment for this sample
            phase_increment = 2.0 * np.pi * instantaneous_freq / self.sample_rate

            # Generate sample
            output[i] = np.sin(phase) * self.tx_amplitude

            # Update phase
            phase += phase_increment

            # Wrap phase to avoid accumulation
            if phase > 2.0 * np.pi:
                phase -= 2.0 * np.pi
            elif phase < 0:
                phase += 2.0 * np.pi

        return output

    def tx_process(self, text: str) -> np.ndarray:
        """
        Process text and generate modulated NAVTEX/SITOR-B audio.

        The signal flow is:
        1. Generate baseband bit stream (±1.0)
        2. Apply lowpass filter to baseband (smooths transitions)
        3. Modulate filtered baseband to FSK (varies frequency)

        Args:
            text: Message text to transmit

        Returns:
            Audio samples as float32 array

        Example:
            >>> navtex = NAVTEX()
            >>> navtex.frequency = 1000
            >>> navtex.sample_rate = 11025
            >>> navtex.tx_init()
            >>> audio = navtex.tx_process("TEST MESSAGE")
        """
        # Generate message (filtering happens at baseband before modulation)
        if self.sitor_b_only:
            audio = self._generate_sitor_b(text)
        else:
            audio = self._generate_message_with_header(text)

        return audio.astype(np.float32)


class SITORB(NAVTEX):
    """
    SITOR-B modem (NAVTEX without headers).

    This is a convenience class for transmitting raw SITOR-B without
    the NAVTEX message structure (headers, trailers, phasing).

    Example:
        >>> sitor = SITORB()
        >>> audio = sitor.modulate("TEST", frequency=1000, sample_rate=11025)
    """

    def __init__(
        self,
        use_ita2: bool = True,
        tx_amplitude: float = 0.9,
        use_filtering: bool = True,
    ):
        """Initialize SITOR-B modem.

        Args:
            use_ita2: Use ITA-2 encoding (True) or US-TTY (False)
            tx_amplitude: Transmit amplitude scaling (0.0 to 1.0, default: 0.9)
            use_filtering: Apply baseband lowpass filtering to reduce spectral splatter
        """
        super().__init__(
            use_ita2=use_ita2,
            sitor_b_only=True,
            tx_amplitude=tx_amplitude,
            use_filtering=use_filtering,
        )
