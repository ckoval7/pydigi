"""
RTTY (Radioteletype) Modem Implementation.

RTTY uses FSK (Frequency Shift Keying) modulation with Baudot character encoding.
Common parameters:
- Baud rates: 45, 45.45, 50, 75, 100 baud
- Shifts: 170, 200, 425, 850 Hz
- Standard: 5 data bits, 1 start bit, 1.5 stop bits

References:
    - fldigi/src/rtty/rtty.cxx
    - ITU-R M.476 (RTTY standard)
"""

import numpy as np
from typing import Optional, List
from scipy import signal
from ..core.oscillator import NCO
from ..modems.base import Modem
from ..varicode.baudot import BaudotEncoder, LETTERS, FIGURES, BAUDOT_LTRS


class RTTY(Modem):
    """
    RTTY (Radioteletype) modem using FSK modulation.

    Uses Baudot character encoding and FSK modulation with mark/space
    frequencies. Supports standard RTTY configurations.

    Args:
        baud: Symbol rate in baud (default: 45.45)
        shift: Frequency shift in Hz (default: 170)
        bits: Number of data bits - 5, 7, or 8 (default: 5 for Baudot)
        stop_bits: Number of stop bits - 1.0, 1.5, or 2.0 (default: 1.5)
        use_ita2: Use ITA-2 encoding (True) or US-TTY (False)
        shaped: Use raised cosine shaping for smoother transitions
        shape_alpha: Raised cosine filter roll-off factor (0-1)

    Example:
        >>> rtty = RTTY(baud=45.45, shift=170)
        >>> audio = rtty.modulate("CQ CQ DE W1AW", frequency=1500, sample_rate=8000)
    """

    # Standard RTTY configurations (from fldigi)
    STANDARD_BAUDS = [45, 45.45, 50, 56, 75, 100, 110, 150, 200, 300]
    STANDARD_SHIFTS = [23, 85, 160, 170, 182, 200, 240, 350, 425, 850]

    def __init__(
        self,
        baud: float = 45.45,
        shift: float = 170.0,
        bits: int = 5,
        stop_bits: float = 1.5,
        use_ita2: bool = True,
        shaped: bool = True,
        shape_alpha: float = 0.5,
        tx_amplitude: float = 0.8,
        preamble_ltrs: int = 8,
        postamble_ltrs: int = 8
    ):
        """
        Initialize RTTY modem.

        Args:
            tx_amplitude: Transmit amplitude scaling (0.0 to 1.0, default: 0.8)
                         Lower values leave more headroom and match fldigi better
            preamble_ltrs: Number of LTRS characters to send before data (default: 8)
                          Helps receiver synchronize and detect start of transmission
            postamble_ltrs: Number of LTRS characters to send after data (default: 8)
                           Ensures last character decodes properly
        """
        super().__init__(mode_name="RTTY")

        self.baud = baud
        self.shift = shift
        self.bits = bits
        self.stop_bits = stop_bits
        self.use_ita2 = use_ita2
        self.shaped = shaped
        self.shape_alpha = shape_alpha
        self.tx_amplitude = max(0.0, min(1.0, tx_amplitude))  # Clamp to 0-1
        self.preamble_ltrs = max(0, min(20, preamble_ltrs))  # Clamp 0-20
        self.postamble_ltrs = max(0, min(20, postamble_ltrs))  # Clamp 0-20

        # Baudot encoder
        self.encoder = BaudotEncoder(use_ita2=use_ita2)

        # Oscillators and parameters (initialized in tx_init)
        self.mark_nco = None
        self.space_nco = None
        self.sample_rate = None
        self.samples_per_bit = None
        self.stop_samples = None

    def tx_init(self):
        """Initialize transmitter."""
        # Calculate timing
        self.samples_per_bit = int(self.sample_rate / self.baud)
        self.stop_samples = int(self.samples_per_bit * self.stop_bits)

        # Initialize oscillators
        self.mark_nco = NCO(self.sample_rate)
        self.space_nco = NCO(self.sample_rate)

        # Reset encoder
        self.encoder.reset()

    def _apply_bandpass_filter(self, samples: np.ndarray) -> np.ndarray:
        """
        Apply bandpass filter to limit signal bandwidth.

        For RTTY, we use a filter bandwidth based on the shift and baud rate.
        This implements a similar approach to fldigi's rtty_filter.

        Args:
            samples: Input audio samples

        Returns:
            Filtered audio samples
        """
        # Calculate required bandwidth: shift + 2*baud_rate
        # This ensures we capture the mark and space tones plus sidebands
        bandwidth = self.shift + (2.0 * self.baud)

        # Design bandpass filter centered on carrier frequency
        nyquist = self.sample_rate / 2.0

        # Bandpass edges
        low_edge = (self.frequency - bandwidth / 2.0) / nyquist
        high_edge = (self.frequency + bandwidth / 2.0) / nyquist

        # Ensure edges are valid
        low_edge = max(0.01, min(low_edge, 0.95))
        high_edge = max(low_edge + 0.05, min(high_edge, 0.99))

        # 5th order Butterworth bandpass filter
        b, a = signal.butter(5, [low_edge, high_edge], btype='band')

        # Apply zero-phase filtering
        filtered = signal.filtfilt(b, a, samples)

        return filtered.astype(np.float32)

    def _apply_baseband_filter(self, samples: np.ndarray) -> np.ndarray:
        """
        Apply lowpass filter to baseband signal.

        For RTTY/FSK, we filter at baseband before mixing to carrier frequency.
        This is cleaner than bandpass filtering the modulated signal.

        Args:
            samples: Baseband samples

        Returns:
            Filtered baseband samples
        """
        # Lowpass filter cutoff: shift + 2*baud gives good spectral containment
        # This captures the mark/space tones plus their sidebands
        cutoff_hz = (self.shift / 2.0) + (2.0 * self.baud)
        nyquist = self.sample_rate / 2.0
        cutoff_normalized = cutoff_hz / nyquist

        # Ensure cutoff is valid
        cutoff_normalized = min(cutoff_normalized, 0.95)

        # 5th order Butterworth lowpass filter
        b, a = signal.butter(5, cutoff_normalized, btype='low')

        # Apply zero-phase filtering
        filtered = signal.filtfilt(b, a, samples)

        return filtered.astype(np.float32)

    def _modulate_to_carrier(self, baseband: np.ndarray) -> np.ndarray:
        """
        Mix baseband FSK signal to carrier frequency.

        Args:
            baseband: Baseband FSK signal

        Returns:
            Modulated signal at carrier frequency
        """
        # Generate carrier and mix
        n_samples = len(baseband)
        t = np.arange(n_samples) / self.sample_rate
        carrier = np.cos(2.0 * np.pi * self.frequency * t)

        # FSK modulation: baseband signal modulates the carrier
        output = baseband * carrier

        return output.astype(np.float32)

    def tx_process(self, text: str, apply_filter: bool = False) -> np.ndarray:
        """
        Process text and generate RTTY signal.

        For FSK, we generate the signal directly at the carrier frequencies.
        The baseband approach used in PSK doesn't work cleanly for FSK.

        Args:
            text: Text to transmit
            apply_filter: Apply bandpass filtering (default: False)
                         For RTTY, the raised cosine shaping is usually sufficient

        Returns:
            Audio samples as numpy array
        """
        # Calculate mark and space frequencies at carrier
        # Mark = center + shift/2 (logic 1)
        # Space = center - shift/2 (logic 0)
        mark_freq = self.frequency + self.shift / 2.0
        space_freq = self.frequency - self.shift / 2.0

        # Encode text to Baudot codes
        baudot_codes = self.encoder.encode(text)

        if len(baudot_codes) == 0:
            # No valid characters - return silence
            return np.zeros(int(self.sample_rate * 0.1))

        # Pre-calculate symbol shaping if enabled
        if self.shaped:
            # Use raised cosine for smooth transitions
            # Shape over 1/4 of the symbol period
            shape_len = max(4, self.samples_per_bit // 4)
            # Create a raised cosine ramp from 0 to 1
            x = np.linspace(0, 1, shape_len)
            rise_shape = 0.5 * (1.0 - np.cos(np.pi * x))  # 0 to 1
            fall_shape = 1.0 - rise_shape  # 1 to 0
        else:
            rise_shape = None
            fall_shape = None

        # Generate audio samples directly at carrier
        samples = []

        # Send preamble (LTRS characters for synchronization)
        # LTRS is Baudot code 0x1F (all 1's = continuous mark)
        for _ in range(self.preamble_ltrs):
            char_samples = self._send_char(
                BAUDOT_LTRS, mark_freq, space_freq,
                rise_shape, fall_shape
            )
            samples.extend(char_samples)

        # Send data
        for code in baudot_codes:
            # Transmit one character
            char_samples = self._send_char(
                code, mark_freq, space_freq,
                rise_shape, fall_shape
            )
            samples.extend(char_samples)

        # Send postamble (LTRS characters to ensure clean ending)
        for _ in range(self.postamble_ltrs):
            char_samples = self._send_char(
                BAUDOT_LTRS, mark_freq, space_freq,
                rise_shape, fall_shape
            )
            samples.extend(char_samples)

        audio = np.array(samples, dtype=np.float32)

        # Optional bandpass filter (usually not needed with shaped FSK)
        if apply_filter and len(audio) > 0:
            audio = self._apply_bandpass_filter(audio)
            # Re-normalize after filtering
            max_amp = np.max(np.abs(audio))
            if max_amp > 0:
                audio = audio / max_amp * self.tx_amplitude
        else:
            # Just normalize with tx_amplitude
            max_amp = np.max(np.abs(audio))
            if max_amp > 0:
                audio = audio / max_amp * self.tx_amplitude

        return audio

    def _send_char_baseband(
        self,
        code: int,
        mark_freq: float,
        space_freq: float,
        rise_shape: Optional[np.ndarray],
        fall_shape: Optional[np.ndarray],
        mark_nco: NCO,
        space_nco: NCO
    ) -> List[float]:
        """
        Send one Baudot character at baseband.

        RTTY frame format:
        - 1 start bit (space/0)
        - 5 data bits (LSB first)
        - stop bits (mark/1)

        Args:
            code: 5-bit Baudot code (0-31)
            mark_freq: Mark frequency at baseband (logic 1)
            space_freq: Space frequency at baseband (logic 0)
            rise_shape: Rising edge shape filter
            fall_shape: Falling edge shape filter
            mark_nco: NCO for mark tone
            space_nco: NCO for space tone

        Returns:
            Baseband audio samples for this character
        """
        samples = []

        # Start bit (0 = space)
        samples.extend(
            self._send_bit_baseband(0, mark_freq, space_freq, rise_shape, fall_shape, mark_nco, space_nco)
        )

        # Data bits (LSB first)
        for i in range(self.bits):
            bit = (code >> i) & 1
            samples.extend(
                self._send_bit_baseband(bit, mark_freq, space_freq, rise_shape, fall_shape, mark_nco, space_nco)
            )

        # Stop bit(s) (1 = mark)
        samples.extend(
            self._send_stop_baseband(mark_freq, space_freq, rise_shape, fall_shape, mark_nco, space_nco)
        )

        return samples

    def _send_char(
        self,
        code: int,
        mark_freq: float,
        space_freq: float,
        rise_shape: Optional[np.ndarray],
        fall_shape: Optional[np.ndarray]
    ) -> List[float]:
        """
        Send one Baudot character (legacy method for compatibility).

        RTTY frame format:
        - 1 start bit (space/0)
        - 5 data bits (LSB first)
        - stop bits (mark/1)

        Args:
            code: 5-bit Baudot code (0-31)
            mark_freq: Mark frequency (logic 1)
            space_freq: Space frequency (logic 0)
            rise_shape: Rising edge shape filter
            fall_shape: Falling edge shape filter

        Returns:
            Audio samples for this character
        """
        samples = []

        # Start bit (0 = space)
        samples.extend(
            self._send_bit(0, mark_freq, space_freq, rise_shape, fall_shape)
        )

        # Data bits (LSB first)
        for i in range(self.bits):
            bit = (code >> i) & 1
            samples.extend(
                self._send_bit(bit, mark_freq, space_freq, rise_shape, fall_shape)
            )

        # Stop bit(s) (1 = mark)
        samples.extend(
            self._send_stop(mark_freq, space_freq, rise_shape, fall_shape)
        )

        return samples

    def _send_bit_baseband(
        self,
        bit: int,
        mark_freq: float,
        space_freq: float,
        rise_shape: Optional[np.ndarray],
        fall_shape: Optional[np.ndarray],
        mark_nco: NCO,
        space_nco: NCO
    ) -> np.ndarray:
        """
        Generate baseband samples for one bit period.

        Args:
            bit: Bit value (0 or 1)
            mark_freq: Mark frequency at baseband
            space_freq: Space frequency at baseband
            rise_shape: Rising edge shape
            fall_shape: Falling edge shape
            mark_nco: NCO for mark tone
            space_nco: NCO for space tone

        Returns:
            Baseband audio samples
        """
        if self.shaped and rise_shape is not None:
            # Generate shaped FSK at baseband
            return self._send_bit_shaped_baseband(
                bit, mark_freq, space_freq, rise_shape, fall_shape, mark_nco, space_nco
            )
        else:
            # Generate unshaped FSK at baseband (simple tone switching)
            freq = mark_freq if bit else space_freq

            if bit:
                mark_nco.frequency = freq
                return mark_nco.step_real(self.samples_per_bit)
            else:
                space_nco.frequency = freq
                return space_nco.step_real(self.samples_per_bit)

    def _send_bit_shaped_baseband(
        self,
        bit: int,
        mark_freq: float,
        space_freq: float,
        rise_shape: np.ndarray,
        fall_shape: np.ndarray,
        mark_nco: NCO,
        space_nco: NCO
    ) -> np.ndarray:
        """
        Generate shaped FSK at baseband for one bit.

        Uses two oscillators (mark and space) running continuously,
        shaped by rise/fall envelopes for smooth transitions.

        Args:
            bit: Bit value (0 or 1)
            mark_freq: Mark frequency at baseband
            space_freq: Space frequency at baseband
            rise_shape: Rising edge envelope
            fall_shape: Falling edge envelope
            mark_nco: NCO for mark tone
            space_nco: NCO for space tone

        Returns:
            Baseband audio samples
        """
        shape_len = len(rise_shape)
        samples = np.zeros(self.samples_per_bit)

        # Generate continuous tones at baseband
        mark_nco.frequency = mark_freq
        mark_tone = mark_nco.step_real(self.samples_per_bit)
        space_nco.frequency = space_freq
        space_tone = space_nco.step_real(self.samples_per_bit)

        if bit == 1:
            # Mark: fade out space, fade in mark
            for i in range(self.samples_per_bit):
                if i < shape_len:
                    # Transition region
                    mark_env = rise_shape[i]
                    space_env = fall_shape[i]
                else:
                    # Steady state
                    mark_env = 1.0
                    space_env = 0.0

                samples[i] = mark_env * mark_tone[i] + space_env * space_tone[i]
        else:
            # Space: fade out mark, fade in space
            for i in range(self.samples_per_bit):
                if i < shape_len:
                    # Transition region
                    mark_env = fall_shape[i]
                    space_env = rise_shape[i]
                else:
                    # Steady state
                    mark_env = 0.0
                    space_env = 1.0

                samples[i] = mark_env * mark_tone[i] + space_env * space_tone[i]

        return samples

    def _send_stop_baseband(
        self,
        mark_freq: float,
        space_freq: float,
        rise_shape: Optional[np.ndarray],
        fall_shape: Optional[np.ndarray],
        mark_nco: NCO,
        space_nco: NCO
    ) -> np.ndarray:
        """
        Generate stop bit(s) at baseband - always mark (1).

        Args:
            mark_freq: Mark frequency at baseband
            space_freq: Space frequency at baseband
            rise_shape: Rising edge shape
            fall_shape: Falling edge shape
            mark_nco: NCO for mark tone
            space_nco: NCO for space tone

        Returns:
            Baseband audio samples
        """
        if self.shaped and rise_shape is not None:
            # Generate shaped stop bit
            shape_len = len(rise_shape)
            samples = np.zeros(self.stop_samples)

            mark_nco.frequency = mark_freq
            mark_tone = mark_nco.step_real(self.stop_samples)
            space_nco.frequency = space_freq
            space_tone = space_nco.step_real(self.stop_samples)

            # Fade out space, fade in mark
            for i in range(self.stop_samples):
                if i < shape_len:
                    mark_env = rise_shape[i]
                    space_env = fall_shape[i]
                else:
                    mark_env = 1.0
                    space_env = 0.0

                samples[i] = mark_env * mark_tone[i] + space_env * space_tone[i]

            return samples
        else:
            # Simple mark tone
            mark_nco.frequency = mark_freq
            return mark_nco.step_real(self.stop_samples)

    def _send_bit(
        self,
        bit: int,
        mark_freq: float,
        space_freq: float,
        rise_shape: Optional[np.ndarray],
        fall_shape: Optional[np.ndarray]
    ) -> np.ndarray:
        """
        Generate samples for one bit period.

        Args:
            bit: Bit value (0 or 1)
            mark_freq: Mark frequency
            space_freq: Space frequency
            rise_shape: Rising edge shape
            fall_shape: Falling edge shape

        Returns:
            Audio samples
        """
        if self.shaped and rise_shape is not None:
            # Generate shaped FSK
            return self._send_bit_shaped(
                bit, mark_freq, space_freq, rise_shape, fall_shape
            )
        else:
            # Generate unshaped FSK (simple tone switching)
            freq = mark_freq if bit else space_freq

            if bit:
                self.mark_nco.frequency = freq
                return self.mark_nco.step_real(self.samples_per_bit)
            else:
                self.space_nco.frequency = freq
                return self.space_nco.step_real(self.samples_per_bit)

    def _send_bit_shaped(
        self,
        bit: int,
        mark_freq: float,
        space_freq: float,
        rise_shape: np.ndarray,
        fall_shape: np.ndarray
    ) -> np.ndarray:
        """
        Generate shaped FSK for one bit.

        Uses two oscillators (mark and space) running continuously,
        shaped by rise/fall envelopes for smooth transitions.

        Args:
            bit: Bit value (0 or 1)
            mark_freq: Mark frequency
            space_freq: Space frequency
            rise_shape: Rising edge envelope
            fall_shape: Falling edge envelope

        Returns:
            Audio samples
        """
        shape_len = len(rise_shape)
        samples = np.zeros(self.samples_per_bit)

        # Generate continuous tones
        self.mark_nco.frequency = mark_freq
        mark_tone = self.mark_nco.step_real(self.samples_per_bit)
        self.space_nco.frequency = space_freq
        space_tone = self.space_nco.step_real(self.samples_per_bit)

        if bit == 1:
            # Mark: fade out space, fade in mark
            for i in range(self.samples_per_bit):
                if i < shape_len:
                    # Transition region
                    mark_env = rise_shape[i]
                    space_env = fall_shape[i]
                else:
                    # Steady state
                    mark_env = 1.0
                    space_env = 0.0

                samples[i] = mark_env * mark_tone[i] + space_env * space_tone[i]
        else:
            # Space: fade out mark, fade in space
            for i in range(self.samples_per_bit):
                if i < shape_len:
                    # Transition region
                    mark_env = fall_shape[i]
                    space_env = rise_shape[i]
                else:
                    # Steady state
                    mark_env = 0.0
                    space_env = 1.0

                samples[i] = mark_env * mark_tone[i] + space_env * space_tone[i]

        return samples

    def _send_stop(
        self,
        mark_freq: float,
        space_freq: float,
        rise_shape: Optional[np.ndarray],
        fall_shape: Optional[np.ndarray]
    ) -> np.ndarray:
        """
        Generate stop bit(s) - always mark (1).

        Args:
            mark_freq: Mark frequency
            space_freq: Space frequency
            rise_shape: Rising edge shape
            fall_shape: Falling edge shape

        Returns:
            Audio samples
        """
        if self.shaped and rise_shape is not None:
            # Generate shaped stop bit
            shape_len = len(rise_shape)
            samples = np.zeros(self.stop_samples)

            self.mark_nco.frequency = mark_freq
            mark_tone = self.mark_nco.step_real(self.stop_samples)
            self.space_nco.frequency = space_freq
            space_tone = self.space_nco.step_real(self.stop_samples)

            # Fade out space, fade in mark
            for i in range(self.stop_samples):
                if i < shape_len:
                    mark_env = rise_shape[i]
                    space_env = fall_shape[i]
                else:
                    mark_env = 1.0
                    space_env = 0.0

                samples[i] = mark_env * mark_tone[i] + space_env * space_tone[i]

            return samples
        else:
            # Simple mark tone
            self.mark_nco.frequency = mark_freq
            return self.mark_nco.step_real(self.stop_samples)

    def modulate(
        self,
        text: str,
        frequency: Optional[float] = None,
        sample_rate: Optional[float] = None,
        apply_filter: bool = False
    ) -> np.ndarray:
        """
        Modulate text into RTTY audio signal.

        This is the main API for generating RTTY signals.

        Args:
            text: Text string to modulate
            frequency: Carrier frequency in Hz (default: uses initialized value)
            sample_rate: Sample rate in Hz (default: uses initialized value)
            apply_filter: Apply bandpass filtering (default: False)
                         The raised cosine shaping is usually sufficient for RTTY

        Returns:
            Audio samples as numpy array of float32 values (-1.0 to 1.0)

        Example:
            >>> rtty = RTTY(baud=45.45, shift=170)
            >>> audio = rtty.modulate("CQ CQ DE W1ABC", frequency=1500)
            >>> # audio is ready to save to WAV or use with GNU Radio
        """
        # Update parameters if provided
        if frequency is not None:
            self.frequency = frequency

        # Set sample_rate if not already set (for compatibility)
        if self.sample_rate is None:
            self.sample_rate = 8000.0

        if sample_rate is not None:
            self.sample_rate = sample_rate

        # Initialize transmitter
        self.tx_init()

        # Process text and generate audio
        audio = self.tx_process(text, apply_filter)

        return audio

    def estimate_duration(self, text: str, sample_rate: float = 8000) -> float:
        """
        Estimate transmission duration in seconds.

        Includes preamble and postamble in the estimate.

        Args:
            text: Text to transmit
            sample_rate: Audio sample rate

        Returns:
            Duration in seconds
        """
        # Encode to get actual number of codes
        encoder = BaudotEncoder(use_ita2=self.use_ita2)
        codes = encoder.encode(text)

        # Each character: 1 start + N data bits + stop bits
        bits_per_char = 1 + self.bits + self.stop_bits

        # Total characters = preamble + data + postamble
        total_chars = self.preamble_ltrs + len(codes) + self.postamble_ltrs
        total_bits = total_chars * bits_per_char

        # Duration = bits / baud rate
        return total_bits / self.baud

    def __str__(self) -> str:
        """String representation."""
        return (
            f"RTTY(baud={self.baud}, shift={self.shift}, "
            f"bits={self.bits}, stop={self.stop_bits}, "
            f"{'ITA-2' if self.use_ita2 else 'US-TTY'})"
        )
