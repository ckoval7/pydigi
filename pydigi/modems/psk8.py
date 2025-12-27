"""
EightPSK (8-Phase Shift Keying) modem implementation.

Based on fldigi's 8PSK implementation (fldigi/src/psk/psk.cxx).
Supports 8PSK125, 8PSK250, 8PSK500, 8PSK1000, and other baud rates.

EightPSK transmits 3 bits per symbol using Gray-mapped constellation,
tripling the throughput compared to BPSK. This implementation supports
8PSK without FEC (for simplicity).

Note: Named "EightPSK" (not "PSK8") to match fldigi's "8PSK" convention
and avoid confusion with baud rates like "PSK31" (PSK at 31.25 baud).
"""

import numpy as np
from typing import Optional
from scipy import signal
from ..core.oscillator import NCO
from ..core.dsp_utils import (
    generate_raised_cosine_shape,
    apply_baseband_filter,
    modulate_to_carrier,
    normalize_audio
)
from ..modems.base import Modem
from ..varicode.mfsk_varicode import encode_char


class EightPSK(Modem):
    """
    EightPSK (8-Phase Shift Keying) modem.

    Generates 8PSK signals without FEC using varicode character encoding.
    Uses 8 phase states (0°, 45°, 90°, 135°, 180°, 225°, 270°, 315°)
    to transmit 3 bits per symbol.

    8PSK Modes (matching fldigi):
        - 8PSK125: 125 baud (375 bits/sec)
        - 8PSK250: 250 baud (750 bits/sec)
        - 8PSK500: 500 baud (1500 bits/sec)
        - 8PSK1000: 1000 baud (3000 bits/sec)

    Technical Details:
        - Modulation: 8PSK (8 phase states, 3 bits/symbol)
        - Encoding: Direct constellation mapping (sym * 2 to 16-PSK positions)
        - Character encoding: MFSK Varicode (variable-length bit patterns)
        - Pulse shaping: Raised cosine (alpha = 1.0)
        - Bit accumulation: Collects 3 bits LSB-first before transmitting symbol
        - NO character delimiters (unlike PSK varicode)

    Attributes:
        baud: Symbol rate in baud (symbols/second)
        sample_rate: Audio sample rate in Hz (default: 8000)
        frequency: Carrier frequency in Hz (default: 1000)

    Example:
        >>> # 8PSK125 mode (125 baud, 3 bits/symbol = 375 bits/sec)
        >>> modem = EightPSK(baud=125)
        >>> audio = modem.modulate("CQ CQ DE W1ABC", frequency=1000)
        >>>
        >>> # 8PSK250 mode (faster)
        >>> modem = EightPSK(baud=250)
        >>> audio = modem.modulate("8PSK250 TEST", frequency=1500)
    """

    # 8PSK constellation (from fldigi psk.cxx:2247-2248)
    # For 8PSK without FEC: sym *= 2 to map into 16-position constellation
    # Maps 3-bit symbol values to phase angles
    CONSTELLATION = {
        0: complex(-1.0, 0.0),              # 180° - sym*2=0
        1: complex(-0.7071, -0.7071),       # 225° - sym*2=2
        2: complex(0.0, -1.0),              # 270° - sym*2=4
        3: complex(0.7071, -0.7071),        # 315° - sym*2=6
        4: complex(1.0, 0.0),               # 0°   - sym*2=8
        5: complex(0.7071, 0.7071),         # 45°  - sym*2=10
        6: complex(0.0, 1.0),               # 90°  - sym*2=12
        7: complex(-0.7071, 0.7071),        # 135° - sym*2=14
    }

    def __init__(
        self,
        baud: float = 125,
        sample_rate: float = 8000.0,
        frequency: float = 1000.0,
        tx_amplitude: float = 0.8
    ):
        """
        Initialize the 8PSK modem.

        Args:
            baud: Symbol rate in baud. Common values:
                  - 125 (8PSK125, most common)
                  - 250 (8PSK250)
                  - 500 (8PSK500)
                  - 1000 (8PSK1000)
            sample_rate: Audio sample rate in Hz (default: 8000)
            frequency: Carrier frequency in Hz (default: 1000)
            tx_amplitude: Transmit amplitude scaling (0.0 to 1.0, default: 0.8)

        Raises:
            ValueError: If baud rate is <= 0 or > 2000
        """
        # Determine mode name based on baud rate
        baud_map = {
            125: "8PSK125",
            250: "8PSK250",
            500: "8PSK500",
            1000: "8PSK1000",
            1200: "8PSK1200"
        }
        mode_name = baud_map.get(baud, f"8PSK{int(baud)}")

        super().__init__(mode_name=mode_name, sample_rate=sample_rate, frequency=frequency)

        if baud <= 0 or baud > 2000:
            raise ValueError(f"Baud rate must be > 0 and <= 2000, got {baud}")

        self.baud = baud
        self.tx_amplitude = max(0.0, min(1.0, tx_amplitude))
        self._nco: Optional[NCO] = None
        self._prev_phase = 0.0
        self._symbol_samples = 0
        self._tx_shape = None
        self._bit_buffer = 0  # Accumulate 3 bits before transmission
        self._bit_count = 0   # Number of bits in buffer
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
        self._bit_buffer = 0
        self._bit_count = 0

    def _tx_preamble(self, num_symbols: int = None) -> tuple[list, list]:
        """
        Generate preamble for synchronization (returns baseband I/Q).

        8PSK without FEC sends symbol 0 (phase reversals) then NULL character.
        From fldigi psk.cxx:2589-2595

        Preamble length is baud-dependent (from fldigi dcdbits):
        - 8PSK125: 128 symbols
        - 8PSK250: 256 symbols
        - 8PSK500: 512 symbols
        - 8PSK1000: 1024 symbols

        Args:
            num_symbols: Number of preamble symbols (default: auto-calculated from baud)

        Returns:
            Tuple of (I samples list, Q samples list) at baseband
        """
        # Auto-calculate preamble length based on baud rate (dcdbits = baud * 1.024)
        if num_symbols is None:
            num_symbols = int(self.baud * 1.024)  # fldigi's dcdbits formula
        i_samples = []
        q_samples = []

        # Send symbol 0 (180° phase reversals) for preamble
        # fldigi: for (int i = 0; i < preamble; i++) tx_symbol(0);
        for _ in range(num_symbols):
            i_sym, q_sym = self._tx_symbol(0)
            i_samples.extend(i_sym)
            q_samples.extend(q_sym)

        # Send NULL character (0x00) after preamble for sync
        # fldigi: tx_char(0);
        i_null, q_null = self._tx_char(0)
        i_samples.extend(i_null)
        q_samples.extend(q_null)

        return i_samples, q_samples

    def _tx_postamble(self, num_symbols: int = None) -> tuple[list, list]:
        """
        Generate postamble for clean ending (returns baseband I/Q).

        8PSK postamble first sends NULL characters to clear bit accumulator,
        then sends symbol 4 (0°) for DCD window detection.
        From fldigi psk.cxx:2521-2533

        Postamble is typically ~3x preamble length for proper DCD detection.

        Args:
            num_symbols: Number of postamble symbols (default: auto-calculated from baud)

        Returns:
            Tuple of (I samples list, Q samples list) at baseband
        """
        # Auto-calculate postamble length (3x preamble for proper DCD)
        if num_symbols is None:
            num_symbols = int(self.baud * 1.024 * 3)  # ~3x preamble
        i_samples = []
        q_samples = []

        # First send symbits (3) NULL characters to clear bit accumulators
        # fldigi: for (int i=0; i<symbits; i++) tx_char(0);
        for _ in range(3):
            i_null, q_null = self._tx_char(0)
            i_samples.extend(i_null)
            q_samples.extend(q_null)

        # Send postamble: symbol 4 (0° in our constellation) repeated for DCD window
        # fldigi: for (int i = 0; i <= 96; i++) tx_symbol(symbol);
        for _ in range(num_symbols):
            i_sym, q_sym = self._tx_symbol(4)
            i_samples.extend(i_sym)
            q_samples.extend(q_sym)

        return i_samples, q_samples

    def _tx_symbol(self, symbol: int) -> tuple[np.ndarray, np.ndarray]:
        """
        Generate baseband I/Q samples for a single 8PSK symbol.

        8PSK symbols use differential encoding with 8 phase states.
        Uses direct constellation mapping (sym * 2 into 16-PSK positions).

        Args:
            symbol: Symbol value (0-7, representing 3 bits)

        Returns:
            Tuple of (I samples, Q samples) at baseband
        """
        # Map symbol to complex value using direct constellation
        symbol_complex = self.CONSTELLATION.get(symbol & 7, self.CONSTELLATION[0])

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

    def _tx_bit(self, bit: int) -> tuple[list, list]:
        """
        Transmit a single bit (accumulates 3 bits before transmitting symbol).

        8PSK transmits 3 bits per symbol, so we buffer bits until we have 3.
        From fldigi psk.cxx:2346-2353 (without FEC)
        Bits are accumulated LSB-first: xpsk_sym |= bit << bitcount++

        Args:
            bit: Bit value (0 or 1)

        Returns:
            Tuple of (I samples list, Q samples list) - empty unless symbol ready
        """
        i_samples = []
        q_samples = []

        # Accumulate bit in buffer - LSB first like fldigi
        # fldigi: xpsk_sym |= bit << bitcount++
        self._bit_buffer |= (bit & 1) << self._bit_count
        self._bit_count += 1

        # When we have 3 bits, transmit the symbol
        if self._bit_count == 3:
            symbol = self._bit_buffer & 7
            i_sym, q_sym = self._tx_symbol(symbol)
            i_samples.extend(i_sym)
            q_samples.extend(q_sym)

            # Reset buffer
            self._bit_buffer = 0
            self._bit_count = 0

        return i_samples, q_samples

    def _tx_char(self, char_code: int) -> tuple[list, list]:
        """
        Transmit a single character using MFSK varicode encoding.

        8PSK uses MFSK varicode, NOT PSK varicode!
        MFSK varicode does NOT use character delimiters.

        Args:
            char_code: ASCII character code (0-255)

        Returns:
            Tuple of (I samples list, Q samples list) at baseband
        """
        # Get MFSK varicode for this character
        code = encode_char(char_code)

        # Transmit each bit (no delimiters for MFSK varicode)
        i_samples = []
        q_samples = []

        for bit_char in code:
            bit = int(bit_char)
            i_bits, q_bits = self._tx_bit(bit)
            i_samples.extend(i_bits)
            q_samples.extend(q_bits)

        # NO character delimiter for MFSK varicode!
        # (Unlike PSK varicode which uses 00)

        return i_samples, q_samples

    # Removed _apply_baseband_filter - now using shared dsp_utils.apply_baseband_filter
    # Removed _modulate_to_carrier - now using shared dsp_utils.modulate_to_carrier

    def tx_process(self, text: str, preamble_symbols: int = None, postamble_symbols: int = None, apply_filter: bool = True) -> np.ndarray:
        """
        Process text for transmission.

        Args:
            text: Text to transmit
            preamble_symbols: Number of preamble symbols for sync (default: auto-calculated from baud)
            postamble_symbols: Number of postamble symbols for DCD (default: auto-calculated from baud)
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

        # Send postamble
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
        preamble_symbols: int = None,
        postamble_symbols: int = None,
        apply_filter: bool = True
    ) -> np.ndarray:
        """
        Modulate text into 8PSK audio signal.

        Args:
            text: Text string to modulate
            frequency: Carrier frequency in Hz (default: uses initialized value)
            sample_rate: Sample rate in Hz (default: uses initialized value)
            preamble_symbols: Number of preamble symbols (default: auto-calculated from baud)
            postamble_symbols: Number of postamble symbols (default: auto-calculated from baud)
            apply_filter: Apply baseband lowpass filtering (default: True)

        Returns:
            Audio samples as numpy array of float32 values (-1.0 to 1.0)

        Example:
            >>> modem = EightPSK(baud=125)  # 8PSK125
            >>> audio = modem.modulate("HELLO WORLD", frequency=1000)
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

    def estimate_duration(self, text: str, preamble_symbols: int = None, postamble_symbols: int = None) -> float:
        """
        Estimate transmission duration in seconds.

        Args:
            text: Text to transmit
            preamble_symbols: Number of preamble symbols (default: auto-calculated from baud)
            postamble_symbols: Number of postamble symbols (default: auto-calculated from baud)

        Returns:
            Estimated duration in seconds
        """
        # Auto-calculate if not provided
        if preamble_symbols is None:
            preamble_symbols = int(self.baud * 1.024)
        if postamble_symbols is None:
            postamble_symbols = int(self.baud * 1.024 * 3)
        from ..varicode.mfsk_varicode import encode_text

        # Get MFSK varicode bit stream (no delimiters)
        bit_stream = encode_text(text)
        num_bits = len(bit_stream)

        # 8PSK uses 3 bits per symbol
        data_symbols = (num_bits + 2) // 3  # Round up

        # Add preamble and postamble
        total_symbols = preamble_symbols + data_symbols + postamble_symbols

        # Duration = symbols / baud
        duration = total_symbols / self.baud

        return duration

    def __repr__(self) -> str:
        """String representation of the modem."""
        return (f"EightPSK(mode={self.mode_name}, baud={self.baud}, "
                f"freq={self.frequency}Hz, fs={self.sample_rate}Hz)")


# Convenience functions for common 8PSK modes

def EightPSK_125(sample_rate: float = 8000.0, frequency: float = 1000.0, tx_amplitude: float = 0.8) -> EightPSK:
    """Create an 8PSK125 modem (125 baud, 375 bits/sec)."""
    return EightPSK(baud=125, sample_rate=sample_rate, frequency=frequency, tx_amplitude=tx_amplitude)


def EightPSK_250(sample_rate: float = 8000.0, frequency: float = 1000.0, tx_amplitude: float = 0.8) -> EightPSK:
    """Create an 8PSK250 modem (250 baud, 750 bits/sec)."""
    return EightPSK(baud=250, sample_rate=sample_rate, frequency=frequency, tx_amplitude=tx_amplitude)


def EightPSK_500(sample_rate: float = 8000.0, frequency: float = 1000.0, tx_amplitude: float = 0.8) -> EightPSK:
    """Create an 8PSK500 modem (500 baud, 1500 bits/sec)."""
    return EightPSK(baud=500, sample_rate=sample_rate, frequency=frequency, tx_amplitude=tx_amplitude)


def EightPSK_1000(sample_rate: float = 8000.0, frequency: float = 1000.0, tx_amplitude: float = 0.8) -> EightPSK:
    """Create an 8PSK1000 modem (1000 baud, 3000 bits/sec)."""
    return EightPSK(baud=1000, sample_rate=sample_rate, frequency=frequency, tx_amplitude=tx_amplitude)
