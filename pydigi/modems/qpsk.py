"""
QPSK (Quadrature Phase Shift Keying) modem implementation.

Based on fldigi's QPSK implementation (fldigi/src/psk/psk.cxx).
Supports QPSK31, QPSK63, QPSK125, QPSK250, QPSK500, and other baud rates.

QPSK transmits 2 bits per symbol using a rate 1/2 convolutional encoder (FEC),
effectively doubling the throughput compared to BPSK while maintaining robustness.
"""

import numpy as np
from typing import Optional
from scipy import signal
from ..core.oscillator import NCO
from ..core.encoder import create_qpsk_encoder
from ..core.dsp_utils import (
    generate_raised_cosine_shape,
    apply_baseband_filter,
    modulate_to_carrier,
    normalize_audio,
)
from ..modems.base import Modem
from ..varicode.psk_varicode import encode_text_to_bits


class QPSK(Modem):
    """
    QPSK (Quadrature Phase Shift Keying) modem.

    Generates QPSK signals with convolutional FEC encoding and varicode
    character encoding. Uses 4 phase states (0°, 90°, 180°, 270°) to
    transmit 2 bits per symbol.

    QPSK Modes:
        - QPSK31: 31.25 baud (62.5 bits/sec effective)
        - QPSK63: 62.5 baud (125 bits/sec effective)
        - QPSK125: 125 baud (250 bits/sec effective)
        - QPSK250: 250 baud (500 bits/sec effective)
        - QPSK500: 500 baud (1000 bits/sec effective)

    Technical Details:
        - Modulation: QPSK (4 phase states)
        - FEC: Rate 1/2 convolutional encoder (K=5, POLY1=0x17, POLY2=0x19)
        - Character encoding: Varicode (variable-length bit patterns)
        - Pulse shaping: Raised cosine (alpha = 1.0)
        - Symbol mapping: 0→180°, 1→270°, 2→0°, 3→90°
        - Character delimiter: Two consecutive zero bits (00)

    Attributes:
        baud: Symbol rate in baud (symbols/second)
        sample_rate: Audio sample rate in Hz (default: 8000)
        frequency: Carrier frequency in Hz (default: 1000)

    Example:
        >>> # QPSK31 mode
        >>> qpsk31 = QPSK(baud=31.25)
        >>> audio = qpsk31.modulate("CQ CQ DE W1ABC", frequency=1000)
        >>>
        >>> # QPSK63 mode (faster)
        >>> qpsk63 = QPSK(baud=62.5)
        >>> audio = qpsk63.modulate("QPSK63 TEST", frequency=1500)
    """

    # QPSK constellation points (differential encoding)
    # Maps symbol values 0-3 to complex phase changes
    # After reversal operation: sym = (4 - sym) & 3 (from fldigi psk.cxx:2250-2251)
    # Then multiply by 4 to index into sym_vec_pos[]
    CONSTELLATION = {
        0: complex(-1.0, 0.0),  # 180° - encoder 0 -> rev 0 -> index 0
        1: complex(0.0, 1.0),  # 90°  - encoder 1 -> rev 3 -> index 12
        2: complex(1.0, 0.0),  # 0°   - encoder 2 -> rev 2 -> index 8
        3: complex(0.0, -1.0),  # 270° - encoder 3 -> rev 1 -> index 4
    }

    def __init__(
        self,
        baud: float = 31.25,
        sample_rate: float = 8000.0,
        frequency: float = 1000.0,
        tx_amplitude: float = 0.8,
    ):
        """
        Initialize the QPSK modem.

        Args:
            baud: Symbol rate in baud. Common values:
                  - 31.25 (QPSK31)
                  - 62.5 (QPSK63)
                  - 125 (QPSK125)
                  - 250 (QPSK250)
                  - 500 (QPSK500)
            sample_rate: Audio sample rate in Hz (default: 8000)
            frequency: Carrier frequency in Hz (default: 1000)
            tx_amplitude: Transmit amplitude scaling (0.0 to 1.0, default: 0.8)

        Raises:
            ValueError: If baud rate is <= 0 or > 1000
        """
        # Determine mode name based on baud rate
        baud_map = {
            31.25: "QPSK31",
            62.5: "QPSK63",
            125: "QPSK125",
            250: "QPSK250",
            500: "QPSK500",
            1000: "QPSK1000",
        }
        mode_name = baud_map.get(baud, f"QPSK{int(baud)}")

        super().__init__(mode_name=mode_name, sample_rate=sample_rate, frequency=frequency)

        if baud <= 0 or baud > 1000:
            raise ValueError(f"Baud rate must be > 0 and <= 1000, got {baud}")

        self.baud = baud
        self.tx_amplitude = max(0.0, min(1.0, tx_amplitude))
        self._nco: Optional[NCO] = None
        self._prev_phase = 0.0
        self._symbol_samples = 0
        self._tx_shape = None
        self._encoder = None
        self._init_parameters()

    def _init_parameters(self):
        """Initialize internal parameters based on baud rate and sample rate."""
        self._symbol_samples = int(self.sample_rate / self.baud + 0.5)
        self._tx_shape = generate_raised_cosine_shape(self._symbol_samples)

    def tx_init(self):
        """Initialize transmitter state."""
        self._nco = NCO(self.sample_rate, self.frequency)
        self._prev_phase = 0.0
        self._preamble_sent = False
        # Create convolutional encoder for QPSK FEC
        self._encoder = create_qpsk_encoder()

    def _tx_preamble(self, num_symbols: int = 32) -> tuple[list, list]:
        """
        Generate preamble for synchronization (returns baseband I/Q).

        QPSK preamble sends symbol 0 (180° phase reversals) for sync.

        Args:
            num_symbols: Number of preamble symbols (default: 32)

        Returns:
            Tuple of (I samples list, Q samples list) at baseband
        """
        i_samples = []
        q_samples = []

        for _ in range(num_symbols):
            # Symbol 0 = 180° phase reversal
            i_sym, q_sym = self._tx_symbol(0)
            i_samples.extend(i_sym)
            q_samples.extend(q_sym)

        return i_samples, q_samples

    def _tx_postamble(self, num_symbols: int = 32) -> tuple[list, list]:
        """
        Generate postamble for clean ending (returns baseband I/Q).

        QPSK postamble flushes the encoder by sending zero bits.
        From fldigi psk.cxx:2509-2512

        Args:
            num_symbols: Number of symbols worth of flush bits (default: 32)

        Returns:
            Tuple of (I samples list, Q samples list) at baseband
        """
        i_samples = []
        q_samples = []

        # Flush the convolutional encoder with zero bits
        # This ensures the encoder state is cleared and receiver can finish decoding
        for _ in range(num_symbols):
            i_sym, q_sym = self._tx_bit(0)
            i_samples.extend(i_sym)
            q_samples.extend(q_sym)

        return i_samples, q_samples

    def _tx_symbol(self, symbol: int) -> tuple[np.ndarray, np.ndarray]:
        """
        Generate baseband I/Q samples for a single QPSK symbol.

        QPSK symbols use differential encoding with 4 phase states:
        - Symbol 0: 180° phase change
        - Symbol 1: 270° phase change (90° CCW from 0°)
        - Symbol 2: 0° (no phase change)
        - Symbol 3: 90° phase change

        Args:
            symbol: Symbol value (0, 1, 2, or 3)

        Returns:
            Tuple of (I samples, Q samples) at baseband
        """
        # Map symbol to complex value
        symbol_complex = self.CONSTELLATION.get(symbol & 3, self.CONSTELLATION[0])

        # Get previous symbol (stored as complex value)
        prev_symbol_complex = complex(np.cos(self._prev_phase), np.sin(self._prev_phase))

        # New symbol is differential: new = prev * symbol_change
        new_symbol_complex = prev_symbol_complex * symbol_complex

        # Generate baseband I/Q samples with smooth transition
        i_samples = np.zeros(self._symbol_samples, dtype=np.float32)
        q_samples = np.zeros(self._symbol_samples, dtype=np.float32)

        for i in range(self._symbol_samples):
            # Interpolate between previous and current symbol
            shape_a = self._tx_shape[i]
            shape_b = 1.0 - shape_a

            # Linear interpolation in complex plane
            i_samples[i] = shape_a * prev_symbol_complex.real + shape_b * new_symbol_complex.real
            q_samples[i] = shape_a * prev_symbol_complex.imag + shape_b * new_symbol_complex.imag

        # Update previous phase for next symbol
        self._prev_phase = np.angle(new_symbol_complex)

        return i_samples, q_samples

    def _tx_bit(self, bit: int) -> tuple[np.ndarray, np.ndarray]:
        """
        Transmit a single bit through the convolutional encoder as a QPSK symbol.

        The encoder converts 1 bit into 2 bits (rate 1/2), which form a QPSK symbol.

        Args:
            bit: Bit value (0 or 1)

        Returns:
            Tuple of (I samples, Q samples) at baseband
        """
        # Encode bit through convolutional encoder (1 bit in, 2 bits out)
        # This returns a symbol value 0-3
        symbol = self._encoder.encode(bit)

        # Transmit the encoded symbol
        return self._tx_symbol(symbol & 3)

    def _tx_char(self, char_code: int) -> tuple[list, list]:
        """
        Transmit a single character using varicode encoding.

        Args:
            char_code: ASCII character code (0-255)

        Returns:
            Tuple of (I samples list, Q samples list) at baseband
        """
        from ..varicode.psk_varicode import encode_char

        # Get varicode for this character
        code = encode_char(char_code)

        # Transmit each bit through the encoder
        i_samples = []
        q_samples = []

        for bit_char in code:
            bit = int(bit_char)
            i_sym, q_sym = self._tx_bit(bit)
            i_samples.extend(i_sym)
            q_samples.extend(q_sym)

        # Add two zero bits as character delimiter
        i_sym, q_sym = self._tx_bit(0)
        i_samples.extend(i_sym)
        q_samples.extend(q_sym)

        i_sym, q_sym = self._tx_bit(0)
        i_samples.extend(i_sym)
        q_samples.extend(q_sym)

        return i_samples, q_samples

    # Removed _apply_baseband_filter - now using shared dsp_utils.apply_baseband_filter
    # Removed _modulate_to_carrier - now using shared dsp_utils.modulate_to_carrier

    def tx_process(
        self,
        text: str,
        preamble_symbols: int = 32,
        postamble_symbols: int = 32,
        apply_filter: bool = True,
    ) -> np.ndarray:
        """
        Process text for transmission.

        Args:
            text: Text to transmit
            preamble_symbols: Number of preamble symbols for sync (default: 32)
            postamble_symbols: Number of postamble symbols for encoder flush (default: 32)
            apply_filter: Apply baseband lowpass filtering (default: True)

        Returns:
            Complete audio samples including preamble, text, and postamble
        """
        i_samples = []
        q_samples = []

        # Send preamble
        if not self._preamble_sent:
            i_preamble, q_preamble = self._tx_preamble(preamble_symbols)
            i_samples.extend(i_preamble)
            q_samples.extend(q_preamble)
            self._preamble_sent = True

        # Transmit each character
        for char in text:
            char_code = ord(char)
            i_char, q_char = self._tx_char(char_code)
            i_samples.extend(i_char)
            q_samples.extend(q_char)

        # Send postamble (flushes encoder)
        i_postamble, q_postamble = self._tx_postamble(postamble_symbols)
        i_samples.extend(i_postamble)
        q_samples.extend(q_postamble)

        # Convert to numpy arrays
        i_baseband = np.array(i_samples, dtype=np.float32)
        q_baseband = np.array(q_samples, dtype=np.float32)

        # Apply lowpass filter to baseband I/Q
        if apply_filter and len(i_baseband) > 0:
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
        preamble_symbols: int = 32,
        postamble_symbols: int = 32,
        apply_filter: bool = True,
    ) -> np.ndarray:
        """
        Modulate text into QPSK audio signal.

        Args:
            text: Text string to modulate
            frequency: Carrier frequency in Hz (default: uses initialized value)
            sample_rate: Sample rate in Hz (default: uses initialized value)
            preamble_symbols: Number of preamble symbols (default: 32)
            postamble_symbols: Number of postamble symbols (default: 32)
            apply_filter: Apply baseband lowpass filtering (default: True)

        Returns:
            Audio samples as numpy array of float32 values (-1.0 to 1.0)

        Example:
            >>> qpsk = QPSK(baud=31.25)  # QPSK31
            >>> audio = qpsk.modulate("HELLO WORLD", frequency=1000)
        """
        # Update parameters if provided
        if frequency is not None:
            self.frequency = frequency
        if sample_rate is not None:
            if sample_rate != self.sample_rate:
                self.sample_rate = sample_rate
                self._init_parameters()

        # Initialize transmitter
        self.tx_init()

        # Process text and generate audio
        audio = self.tx_process(text, preamble_symbols, postamble_symbols, apply_filter)

        return audio

    def estimate_duration(
        self, text: str, preamble_symbols: int = 32, postamble_symbols: int = 32
    ) -> float:
        """
        Estimate transmission duration in seconds.

        Args:
            text: Text to transmit
            preamble_symbols: Number of preamble symbols
            postamble_symbols: Number of postamble symbols

        Returns:
            Estimated duration in seconds
        """
        from ..varicode.psk_varicode import encode_text

        # Get varicode bit stream
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
            f"QPSK(mode={self.mode_name}, baud={self.baud}, "
            f"freq={self.frequency}Hz, fs={self.sample_rate}Hz)"
        )


# Convenience functions for common QPSK modes


def QPSK31(
    sample_rate: float = 8000.0, frequency: float = 1000.0, tx_amplitude: float = 0.8
) -> QPSK:
    """Create a QPSK31 modem (31.25 baud)."""
    return QPSK(baud=31.25, sample_rate=sample_rate, frequency=frequency, tx_amplitude=tx_amplitude)


def QPSK63(
    sample_rate: float = 8000.0, frequency: float = 1000.0, tx_amplitude: float = 0.8
) -> QPSK:
    """Create a QPSK63 modem (62.5 baud)."""
    return QPSK(baud=62.5, sample_rate=sample_rate, frequency=frequency, tx_amplitude=tx_amplitude)


def QPSK125(
    sample_rate: float = 8000.0, frequency: float = 1000.0, tx_amplitude: float = 0.8
) -> QPSK:
    """Create a QPSK125 modem (125 baud)."""
    return QPSK(baud=125, sample_rate=sample_rate, frequency=frequency, tx_amplitude=tx_amplitude)


def QPSK250(
    sample_rate: float = 8000.0, frequency: float = 1000.0, tx_amplitude: float = 0.8
) -> QPSK:
    """Create a QPSK250 modem (250 baud)."""
    return QPSK(baud=250, sample_rate=sample_rate, frequency=frequency, tx_amplitude=tx_amplitude)


def QPSK500(
    sample_rate: float = 8000.0, frequency: float = 1000.0, tx_amplitude: float = 0.8
) -> QPSK:
    """Create a QPSK500 modem (500 baud)."""
    return QPSK(baud=500, sample_rate=sample_rate, frequency=frequency, tx_amplitude=tx_amplitude)
