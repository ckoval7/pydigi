"""
PSK (Phase Shift Keying) modem implementation.

Based on fldigi's PSK implementation (fldigi/src/psk/psk.cxx).
Supports PSK31, PSK63, PSK125, PSK250, PSK500, and other baud rates.

This implementation currently supports BPSK (Binary Phase Shift Keying) with
differential encoding and varicode character encoding.
"""

import numpy as np
from typing import Optional, Tuple
from scipy import signal
from ..core.oscillator import NCO
from ..core.filters import raised_cosine
from ..core.dsp_utils import (
    generate_raised_cosine_shape,
    apply_baseband_filter,
    modulate_to_carrier,
    normalize_audio,
)
from ..modems.base import Modem
from ..varicode.psk_varicode import encode_text_to_bits


class PSK(Modem):
    """
    PSK (Phase Shift Keying) modem.

    Generates BPSK (Binary Phase Shift Keying) signals with differential encoding
    and varicode character encoding. The signal uses raised cosine pulse shaping
    to minimize spectral splatter.

    PSK Modes:
        - PSK31: 31.25 baud (most common)
        - PSK63: 62.5 baud
        - PSK125: 125 baud
        - PSK250: 250 baud
        - PSK500: 500 baud

    Technical Details:
        - Modulation: BPSK (Binary Phase Shift Keying)
        - Encoding: Differential (phase change relative to previous symbol)
        - Character encoding: Varicode (variable-length bit patterns)
        - Pulse shaping: Raised cosine (alpha = 1.0)
        - Symbol mapping: 0 = no phase change, 1 = 180° phase change
        - Character delimiter: Two consecutive zero bits (00)

    Attributes:
        baud: Symbol rate in baud (symbols/second)
        sample_rate: Audio sample rate in Hz (default: 8000)
        frequency: Carrier frequency in Hz (default: 1000)

    Example:
        >>> # PSK31 mode
        >>> psk31 = PSK(baud=31.25)
        >>> audio = psk31.modulate("CQ CQ DE W1ABC", frequency=1000)
        >>>
        >>> # PSK63 mode (faster)
        >>> psk63 = PSK(baud=62.5)
        >>> audio = psk63.modulate("PSK63 TEST", frequency=1500)
    """

    def __init__(
        self,
        baud: float = 31.25,
        sample_rate: float = 8000.0,
        frequency: float = 1000.0,
        tx_amplitude: float = 0.8,
        preamble_symbols: int = 32,
        postamble_symbols: int = 32,
        apply_filter: bool = True,
        leading_silence: float = 0.0,
        trailing_silence: float = 0.0,
    ):
        """
        Initialize the PSK modem.

        Args:
            baud: Symbol rate in baud. Common values:
                  - 31.25 (PSK31, most common)
                  - 62.5 (PSK63)
                  - 125 (PSK125)
                  - 250 (PSK250)
                  - 500 (PSK500)
            sample_rate: Audio sample rate in Hz (default: 8000)
            frequency: Carrier frequency in Hz (default: 1000)
            tx_amplitude: Transmit amplitude scaling (0.0 to 1.0, default: 0.8)
                         Lower values leave more headroom and match fldigi better
            preamble_symbols: Number of preamble symbols for sync (default: 32)
            postamble_symbols: Number of postamble symbols for clean ending (default: 32)
            apply_filter: Apply baseband lowpass filtering (default: True, recommended)
            leading_silence: Duration of silence in seconds to add before signal (default: 0.0)
            trailing_silence: Duration of silence in seconds to add after signal (default: 0.0)

        Raises:
            ValueError: If baud rate is <= 0 or > 1000
        """
        # Determine mode name based on baud rate
        baud_map = {
            31.25: "PSK31",
            62.5: "PSK63",
            125: "PSK125",
            250: "PSK250",
            500: "PSK500",
            1000: "PSK1000",
        }
        mode_name = baud_map.get(baud, f"PSK{int(baud)}")

        super().__init__(
            mode_name=mode_name,
            sample_rate=sample_rate,
            frequency=frequency,
            leading_silence=leading_silence,
            trailing_silence=trailing_silence,
        )

        if baud <= 0 or baud > 1000:
            raise ValueError(f"Baud rate must be > 0 and <= 1000, got {baud}")

        self.baud = baud
        self.tx_amplitude = max(0.0, min(1.0, tx_amplitude))  # Clamp to 0-1
        self.preamble_symbols = preamble_symbols
        self.postamble_symbols = postamble_symbols
        self.apply_filter = apply_filter
        self._nco: Optional[NCO] = None
        self._prev_phase = 0.0  # Track phase for differential encoding
        self._symbol_samples = 0  # Number of samples per symbol
        self._tx_shape = None  # Raised cosine pulse shape
        self._init_parameters()

    def _init_parameters(self):
        """Initialize internal parameters based on baud rate and sample rate."""
        # Calculate samples per symbol
        # symbollen in fldigi = (int)(samplerate / symbaud + 0.5)
        self._symbol_samples = int(self.sample_rate / self.baud + 0.5)

        # Generate raised cosine pulse shape for the symbol
        # This is the tx_shape from fldigi - implements smooth phase transitions
        # Formula from fldigi: (1.0 - cos(2*PI * n / symbollen)) / 2.0
        self._tx_shape = generate_raised_cosine_shape(self._symbol_samples)

    def tx_init(self):
        """Initialize transmitter state."""
        self._nco = NCO(self.sample_rate, self.frequency)
        self._prev_phase = 0.0  # Start with 0 phase
        self._preamble_sent = False

    def _tx_preamble(self, num_symbols: int = 32) -> tuple[list, list]:
        """
        Generate preamble for synchronization (returns baseband I/Q).

        The preamble consists of phase reversals (symbol value 0) which
        creates a two-tone pattern that helps the receiver lock onto the signal.

        Args:
            num_symbols: Number of preamble symbols (default: 32)

        Returns:
            Tuple of (I samples list, Q samples list) at baseband
        """
        i_samples = []
        q_samples = []

        for _ in range(num_symbols):
            # Symbol 0 = phase reversal (180 degrees)
            i_sym, q_sym = self._tx_symbol(0)
            i_samples.extend(i_sym)
            q_samples.extend(q_sym)

        return i_samples, q_samples

    def _tx_postamble(self, num_symbols: int = 32) -> tuple[list, list]:
        """
        Generate postamble for clean ending (returns baseband I/Q).

        The postamble consists of symbol 1 (no phase change, 0 degrees) which
        helps ensure the receiver properly decodes the last character and
        detects the end of transmission.

        Args:
            num_symbols: Number of postamble symbols (default: 32)

        Returns:
            Tuple of (I samples list, Q samples list) at baseband
        """
        i_samples = []
        q_samples = []

        for _ in range(num_symbols):
            # Symbol 1 = no phase change (0 degrees)
            # In fldigi this is tx_symbol(2) which maps to 0° (psk.cxx:2538)
            i_sym, q_sym = self._tx_symbol(1)
            i_samples.extend(i_sym)
            q_samples.extend(q_sym)

        return i_samples, q_samples

    def _tx_symbol(self, symbol: int) -> tuple[np.ndarray, np.ndarray]:
        """
        Generate baseband I/Q samples for a single BPSK symbol with differential encoding.

        In differential BPSK (matching fldigi):
        - Symbol 0: 180° phase change (phase reversal)
        - Symbol 1: No phase change (0°, maintain current phase)

        The symbol is shaped with a raised cosine to create smooth
        phase transitions.

        Args:
            symbol: Symbol value (0 or 1)

        Returns:
            Tuple of (I samples, Q samples) at baseband
        """
        # Map symbol to complex value using differential encoding
        # This matches fldigi's mapping after bit conversion
        # Symbol 0 -> 180° phase change (multiply by -1)
        # Symbol 1 -> no phase change (multiply by +1)
        if symbol == 0:
            symbol_complex = complex(-1.0, 0.0)  # 180° phase change
        else:
            symbol_complex = complex(1.0, 0.0)  # No phase change

        # Get previous symbol (stored as complex value)
        prev_symbol_complex = complex(np.cos(self._prev_phase), np.sin(self._prev_phase))

        # New symbol is differential: new = prev * symbol_change
        new_symbol_complex = prev_symbol_complex * symbol_complex

        # Generate baseband I/Q samples with smooth transition
        i_samples = np.zeros(self._symbol_samples, dtype=np.float32)
        q_samples = np.zeros(self._symbol_samples, dtype=np.float32)

        for i in range(self._symbol_samples):
            # Interpolate between previous and current symbol
            # using the raised cosine shape (matches fldigi exactly)
            shape_a = self._tx_shape[i]  # Weight for previous symbol (0->1)
            shape_b = 1.0 - shape_a  # Weight for new symbol (1->0)

            # Linear interpolation in complex plane (fldigi line 2270-2271)
            # This generates the baseband I/Q signal
            i_samples[i] = shape_a * prev_symbol_complex.real + shape_b * new_symbol_complex.real
            q_samples[i] = shape_a * prev_symbol_complex.imag + shape_b * new_symbol_complex.imag

        # Update previous phase for next symbol
        self._prev_phase = np.angle(new_symbol_complex)

        return i_samples, q_samples

    def _tx_bit(self, bit: int) -> tuple[np.ndarray, np.ndarray]:
        """
        Transmit a single bit as a BPSK symbol (returns baseband I/Q).

        Args:
            bit: Bit value (0 or 1)

        Returns:
            Tuple of (I samples, Q samples) at baseband
        """
        # Match fldigi's bit-to-symbol mapping (psk.cxx:2358)
        # In fldigi: sym = bit << 1, then sym*4 to index sym_vec_pos
        # Bit 0 -> sym 0 -> index 0 -> sym_vec_pos[0] = (-1,0) -> 180° phase change
        # Bit 1 -> sym 2 -> index 8 -> sym_vec_pos[8] = (1,0) -> 0° (no phase change)
        # We use: symbol 0 = 180° change, symbol 1 = no change
        symbol = bit  # Direct mapping: bit 0 -> symbol 0, bit 1 -> symbol 1
        return self._tx_symbol(symbol)

    def _tx_char(self, char_code: int) -> tuple[list, list]:
        """
        Transmit a single character using varicode encoding (returns baseband I/Q).

        Args:
            char_code: ASCII character code (0-255)

        Returns:
            Tuple of (I samples list, Q samples list) at baseband
        """
        from ..varicode.psk_varicode import encode_char

        # Get varicode for this character
        code = encode_char(char_code)

        # Transmit each bit and collect I/Q samples
        i_samples = []
        q_samples = []

        for bit_char in code:
            bit = int(bit_char)
            i_sym, q_sym = self._tx_bit(bit)
            i_samples.extend(i_sym)
            q_samples.extend(q_sym)

        # Add two zero bits as character delimiter (PSK varicode standard)
        i_sym, q_sym = self._tx_bit(0)
        i_samples.extend(i_sym)
        q_samples.extend(q_sym)

        i_sym, q_sym = self._tx_bit(0)
        i_samples.extend(i_sym)
        q_samples.extend(q_sym)

        return i_samples, q_samples

    # Removed _apply_baseband_filter - now using shared dsp_utils.apply_baseband_filter
    # Removed _modulate_to_carrier - now using shared dsp_utils.modulate_to_carrier

    def _apply_bandpass_filter(self, samples: np.ndarray) -> np.ndarray:
        """
        Apply bandpass filter to limit signal bandwidth.

        Uses a Butterworth bandpass filter centered on the carrier frequency
        to reduce spectral splatter while maintaining signal integrity.

        Args:
            samples: Input audio samples

        Returns:
            Filtered audio samples
        """
        # Calculate bandwidth: for PSK, we need about 2-3x the baud rate on each side
        # This gives us enough bandwidth for the sidebands while limiting splatter
        bandwidth_hz = self.baud * 3.0  # Total bandwidth

        nyquist = self.sample_rate / 2.0

        # Bandpass filter centered on carrier frequency
        low_edge = (self.frequency - bandwidth_hz / 2.0) / nyquist
        high_edge = (self.frequency + bandwidth_hz / 2.0) / nyquist

        # Ensure edges are valid
        low_edge = max(0.01, min(low_edge, 0.95))
        high_edge = max(low_edge + 0.05, min(high_edge, 0.99))

        # 4th order Butterworth bandpass filter (lower order to reduce ringing)
        b, a = signal.butter(4, [low_edge, high_edge], btype="band")

        # Apply zero-phase filtering (filtfilt) to avoid phase distortion
        filtered = signal.filtfilt(b, a, samples)

        return filtered.astype(np.float32)

    def tx_process(self, text: str) -> np.ndarray:
        """
        Process text for transmission.

        Args:
            text: Text to transmit

        Returns:
            Complete audio samples including preamble, text, and postamble

        Note:
            Preamble, postamble, and filtering are controlled by instance variables:
            - self.preamble_symbols
            - self.postamble_symbols
            - self.apply_filter
        """
        i_samples = []
        q_samples = []

        # Send preamble if not yet sent
        if not self._preamble_sent:
            i_preamble, q_preamble = self._tx_preamble(self.preamble_symbols)
            i_samples.extend(i_preamble)
            q_samples.extend(q_preamble)
            self._preamble_sent = True

        # Transmit each character
        for char in text:
            char_code = ord(char)
            i_char, q_char = self._tx_char(char_code)
            i_samples.extend(i_char)
            q_samples.extend(q_char)

        # Send postamble to ensure clean ending
        i_postamble, q_postamble = self._tx_postamble(self.postamble_symbols)
        i_samples.extend(i_postamble)
        q_samples.extend(q_postamble)

        # Convert to numpy arrays
        i_baseband = np.array(i_samples, dtype=np.float32)
        q_baseband = np.array(q_samples, dtype=np.float32)

        # Apply lowpass filter to baseband I/Q (recommended)
        if self.apply_filter and len(i_baseband) > 0:
            i_baseband, q_baseband = apply_baseband_filter(
                i_baseband, q_baseband, self.baud, self.sample_rate
            )

        # Mix to carrier frequency
        audio = modulate_to_carrier(i_baseband, q_baseband, self.frequency, self.sample_rate)

        # Normalize with tx_amplitude scaling
        audio = normalize_audio(audio, self.tx_amplitude)

        return audio

    def modulate(
        self,
        text: str,
        frequency: Optional[float] = None,
        sample_rate: Optional[float] = None,
        preamble_symbols: Optional[int] = None,
        postamble_symbols: Optional[int] = None,
        apply_filter: Optional[bool] = None,
        leading_silence: Optional[float] = None,
        trailing_silence: Optional[float] = None,
    ) -> np.ndarray:
        """
        Modulate text into PSK audio signal.

        This is the main API for generating PSK signals.

        Args:
            text: Text string to modulate
            frequency: Carrier frequency in Hz (default: uses initialized value)
            sample_rate: Sample rate in Hz (default: uses initialized value)
            preamble_symbols: Number of preamble symbols (default: uses initialized value)
            postamble_symbols: Number of postamble symbols (default: uses initialized value)
            apply_filter: Apply baseband lowpass filtering (default: uses initialized value)
            leading_silence: Duration of silence in seconds to add before signal (default: uses initialized value)
            trailing_silence: Duration of silence in seconds to add after signal (default: uses initialized value)

        Returns:
            Audio samples as numpy array of float32 values (-1.0 to 1.0)

        Example:
            >>> psk = PSK(baud=31.25)  # PSK31
            >>> audio = psk.modulate("HELLO WORLD", frequency=1000)
            >>> # audio is ready to save to WAV or use with GNU Radio
        """
        # Store original values for PSK-specific parameters
        original_preamble = self.preamble_symbols
        original_postamble = self.postamble_symbols
        original_filter = self.apply_filter
        original_sr = self.sample_rate

        # Apply overrides if provided
        if preamble_symbols is not None:
            self.preamble_symbols = preamble_symbols
        if postamble_symbols is not None:
            self.postamble_symbols = postamble_symbols
        if apply_filter is not None:
            self.apply_filter = apply_filter

        # Handle sample rate changes (PSK needs to call _init_parameters())
        if sample_rate is not None and sample_rate != self.sample_rate:
            self.sample_rate = sample_rate
            self._init_parameters()

        # Call base class modulate (handles frequency, sample_rate, and silence overrides)
        audio = super().modulate(text, frequency, sample_rate, leading_silence, trailing_silence)

        # Restore original values
        self.preamble_symbols = original_preamble
        self.postamble_symbols = original_postamble
        self.apply_filter = original_filter
        if sample_rate is not None and sample_rate != original_sr:
            self.sample_rate = original_sr
            self._init_parameters()

        return audio

    def estimate_duration(
        self,
        text: str,
        preamble_symbols: Optional[int] = None,
        postamble_symbols: Optional[int] = None,
    ) -> float:
        """
        Estimate transmission duration in seconds.

        Includes preamble and postamble in the estimate.

        Args:
            text: Text to transmit
            preamble_symbols: Number of preamble symbols (default: uses initialized value)
            postamble_symbols: Number of postamble symbols (default: uses initialized value)

        Returns:
            Estimated duration in seconds
        """
        from ..varicode.psk_varicode import encode_text

        # Use instance values if not specified
        if preamble_symbols is None:
            preamble_symbols = self.preamble_symbols
        if postamble_symbols is None:
            postamble_symbols = self.postamble_symbols

        # Get varicode bit stream (includes character delimiters)
        bit_stream = encode_text(text)
        num_bits = len(bit_stream)

        # Add preamble and postamble
        total_symbols = preamble_symbols + num_bits + postamble_symbols

        # Duration = symbols / baud
        duration = total_symbols / self.baud

        return duration

    def __repr__(self) -> str:
        """String representation of the modem."""
        return (
            f"PSK(mode={self.mode_name}, baud={self.baud}, "
            f"freq={self.frequency}Hz, fs={self.sample_rate}Hz)"
        )


# Convenience functions for common PSK modes


def PSK31(
    sample_rate: float = 8000.0,
    frequency: float = 1000.0,
    tx_amplitude: float = 0.8,
    leading_silence: float = 0.0,
    trailing_silence: float = 0.0,
) -> PSK:
    """Create a PSK31 modem (31.25 baud)."""
    return PSK(
        baud=31.25,
        sample_rate=sample_rate,
        frequency=frequency,
        tx_amplitude=tx_amplitude,
        leading_silence=leading_silence,
        trailing_silence=trailing_silence,
    )


def PSK63(
    sample_rate: float = 8000.0,
    frequency: float = 1000.0,
    tx_amplitude: float = 0.8,
    leading_silence: float = 0.0,
    trailing_silence: float = 0.0,
) -> PSK:
    """Create a PSK63 modem (62.5 baud)."""
    return PSK(
        baud=62.5,
        sample_rate=sample_rate,
        frequency=frequency,
        tx_amplitude=tx_amplitude,
        leading_silence=leading_silence,
        trailing_silence=trailing_silence,
    )


def PSK125(
    sample_rate: float = 8000.0,
    frequency: float = 1000.0,
    tx_amplitude: float = 0.8,
    leading_silence: float = 0.0,
    trailing_silence: float = 0.0,
) -> PSK:
    """Create a PSK125 modem (125 baud)."""
    return PSK(
        baud=125,
        sample_rate=sample_rate,
        frequency=frequency,
        tx_amplitude=tx_amplitude,
        leading_silence=leading_silence,
        trailing_silence=trailing_silence,
    )


def PSK250(
    sample_rate: float = 8000.0,
    frequency: float = 1000.0,
    tx_amplitude: float = 0.8,
    leading_silence: float = 0.0,
    trailing_silence: float = 0.0,
) -> PSK:
    """Create a PSK250 modem (250 baud)."""
    return PSK(
        baud=250,
        sample_rate=sample_rate,
        frequency=frequency,
        tx_amplitude=tx_amplitude,
        leading_silence=leading_silence,
        trailing_silence=trailing_silence,
    )


def PSK500(
    sample_rate: float = 8000.0,
    frequency: float = 1000.0,
    tx_amplitude: float = 0.8,
    leading_silence: float = 0.0,
    trailing_silence: float = 0.0,
) -> PSK:
    """Create a PSK500 modem (500 baud)."""
    return PSK(
        baud=500,
        sample_rate=sample_rate,
        frequency=frequency,
        tx_amplitude=tx_amplitude,
        leading_silence=leading_silence,
        trailing_silence=trailing_silence,
    )


def PSK1000(
    sample_rate: float = 8000.0,
    frequency: float = 1000.0,
    tx_amplitude: float = 0.8,
    leading_silence: float = 0.0,
    trailing_silence: float = 0.0,
) -> PSK:
    """Create a PSK1000 modem (1000 baud)."""
    return PSK(
        baud=1000,
        sample_rate=sample_rate,
        frequency=frequency,
        tx_amplitude=tx_amplitude,
        leading_silence=leading_silence,
        trailing_silence=trailing_silence,
    )
