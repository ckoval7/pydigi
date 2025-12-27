"""
EightPSKFEC (8-Phase Shift Keying with Forward Error Correction) modem implementation.

Based on fldigi's 8PSK implementation with FEC (fldigi/src/psk/psk.cxx).
Supports 8PSK125F, 8PSK125FL, 8PSK250F, 8PSK250FL, 8PSK500F, 8PSK1000F, 8PSK1200F.

EightPSKFEC modes use:
- Gray-mapped constellation (different from non-FEC 8PSK)
- Convolutional encoding (K=13 or K=16)
- Bit interleaving
- Puncturing for higher-rate modes (500F, 1000F, 1200F)

FEC Mode Variants:
- F: Standard FEC with shorter interleave
- FL: FEC with Long interleave (better burst error protection)

Note: Named "EightPSKFEC" (not "PSK8FEC") to match fldigi's "8PSK" convention
and avoid confusion with baud rates like "PSK31" (PSK at 31.25 baud).
"""

import numpy as np
from typing import Optional
from scipy import signal
from ..core.oscillator import NCO
from ..core.encoder import ConvolutionalEncoder
from ..core.interleave import Interleave, INTERLEAVE_FWD
from ..core.dsp_utils import (
    generate_raised_cosine_shape,
    apply_baseband_filter,
    modulate_to_carrier,
    normalize_audio
)
from ..modems.base import Modem
from ..varicode.mfsk_varicode import encode_text_to_bits


class EightPSKFEC(Modem):
    """
    EightPSKFEC modem - 8PSK with Forward Error Correction.

    8PSK FEC modes transmit 3 bits per symbol using a Gray-mapped constellation,
    with convolutional encoding and bit interleaving for error correction.

    Modes supported:
        - 8PSK125FL: 125 baud, K=13, long interleave (idepth=384, 2048ms)
        - 8PSK250FL: 250 baud, K=13, long interleave (idepth=512, 1365ms)
        - 8PSK125F: 125 baud, K=16, standard interleave (idepth=384, 2048ms)
        - 8PSK250F: 250 baud, K=16, standard interleave (idepth=512, 1365ms)
        - 8PSK500F: 500 baud, K=13, 2/3 rate (punctured, idepth=640, 426ms)
        - 8PSK1000F: 1000 baud, K=13, 2/3 rate (punctured, idepth=512, 170ms)
        - 8PSK1200F: 1200 baud, K=13, 2/3 rate (punctured, idepth=512, 142ms)

    Technical Details:
        - Modulation: 8PSK (8 phase states, 3 bits/symbol)
        - Encoding: Convolutional (K=13 or K=16, rate 1/2 or 2/3)
        - Character encoding: MFSK/ARQ varicode
        - Pulse shaping: Raised cosine
        - Constellation: Gray-mapped for optimal error resilience
        - Interleaving: Bit-level interleaving for burst error protection

    Attributes:
        baud: Symbol rate in baud (symbols/second)
        sample_rate: Audio sample rate in Hz (default: 8000)
        frequency: Carrier frequency in Hz (default: 1000)

    Example:
        >>> # 8PSK250F mode
        >>> modem = EightPSKFEC(baud=250)
        >>> audio = modem.modulate("TEST 8PSK250F", frequency=1000)
        >>>
        >>> # 8PSK125FL mode (long interleave)
        >>> modem = EightPSKFEC(baud=125, long_interleave=True)
        >>> audio = modem.modulate("8PSK125FL", frequency=1500)
    """

    # Gray-mapped 8PSK constellation (from fldigi psk.cxx:100-110)
    # Optimized for minimal bit errors when phase is off by ±1 position
    # Maps 3-bit symbol values to phase angles
    GRAY_CONSTELLATION = {
        0b000: complex(1.0, 0.0),              # 0°
        0b001: complex(0.7071, 0.7071),        # 45°
        0b010: complex(-0.7071, 0.7071),       # 135°
        0b011: complex(0.0, 1.0),              # 90°
        0b100: complex(0.7071, -0.7071),       # 315°
        0b101: complex(0.0, -1.0),             # 270°
        0b110: complex(-1.0, 0.0),             # 180°
        0b111: complex(-0.7071, -0.7071),      # 225°
    }

    def __init__(
        self,
        baud: float = 125,
        sample_rate: float = 8000.0,
        frequency: float = 1000.0,
        tx_amplitude: float = 0.8,
        long_interleave: bool = False,
        use_k16: bool = None
    ):
        """
        Initialize the 8PSK FEC modem.

        Args:
            baud: Symbol rate in baud. Common values:
                  - 125 (8PSK125F/FL)
                  - 250 (8PSK250F/FL)
                  - 500 (8PSK500F)
                  - 1000 (8PSK1000F)
                  - 1200 (8PSK1200F)
            sample_rate: Audio sample rate in Hz (default: 8000)
            frequency: Carrier frequency in Hz (default: 1000)
            tx_amplitude: Transmit amplitude scaling (0.0 to 1.0, default: 0.8)
            long_interleave: Use long interleave (FL modes) for better burst protection
            use_k16: Force K=16 encoder. If None, auto-select based on mode:
                    - K=16 for 125F and 250F (when not FL)
                    - K=13 for all FL modes and all punctured modes

        Raises:
            ValueError: If baud rate is invalid
        """
        # Determine mode name and configuration
        if baud == 125:
            mode_name = "8PSK125FL" if long_interleave else "8PSK125F"
            self._idepth = 384
            self._dcdbits = 128
            self._flushlength = 55
            self._use_k16 = False if long_interleave else (use_k16 if use_k16 is not None else True)
        elif baud == 250:
            mode_name = "8PSK250FL" if long_interleave else "8PSK250F"
            self._idepth = 512
            self._dcdbits = 256
            self._flushlength = 65
            self._use_k16 = False if long_interleave else (use_k16 if use_k16 is not None else True)
        elif baud == 500:
            mode_name = "8PSK500F"
            self._idepth = 640
            self._dcdbits = 512
            self._flushlength = 80
            self._use_k16 = False
            self._puncturing = True
        elif baud == 1000:
            mode_name = "8PSK1000F"
            self._idepth = 512
            self._dcdbits = 1024
            self._flushlength = 120
            self._use_k16 = False
            self._puncturing = True
        elif baud == 1200:
            mode_name = "8PSK1200F"
            self._idepth = 512
            self._dcdbits = 2048
            self._flushlength = 175
            self._use_k16 = False
            self._puncturing = True
        else:
            raise ValueError(f"Unsupported baud rate: {baud}. Supported: 125, 250, 500, 1000, 1200")

        super().__init__(mode_name=mode_name, sample_rate=sample_rate, frequency=frequency)

        self.baud = baud
        self.tx_amplitude = max(0.0, min(1.0, tx_amplitude))
        self._nco: Optional[NCO] = None
        self._prev_phase = 0.0
        self._symbol_samples = 0
        self._tx_shape = None
        self._encoder: Optional[ConvolutionalEncoder] = None
        self._interleaver: Optional[Interleave] = None
        self._preamble_sent = False

        # Bit accumulation state for tx_xpsk
        self._bitcount = 0
        self._xpsk_sym = 0

        # Check if puncturing is used (for 500F, 1000F, 1200F)
        if not hasattr(self, '_puncturing'):
            self._puncturing = False

        self._init_parameters()

    def _init_parameters(self):
        """Initialize internal parameters based on baud rate and sample rate."""
        self._symbol_samples = int(self.sample_rate / self.baud + 0.5)
        self._tx_shape = generate_raised_cosine_shape(self._symbol_samples)

        # Create convolutional encoder
        if self._use_k16:
            # K=16 encoder for 8PSK125F and 8PSK250F (non-FL)
            # From fldigi psk.cxx:93-94
            k = 16
            poly1 = 0o152711  # octal 152711 = 0x6BC9 = 54729 decimal
            poly2 = 0o126723  # octal 126723 = 0x57D3 = 44499 decimal
        else:
            # K=13 encoder for FL modes and all punctured modes
            # From fldigi psk.cxx:83-85
            k = 13
            poly1 = 0o16461  # octal 16461 = 0x1D31 = 7473 decimal
            poly2 = 0o12767  # octal 12767 = 0x15F7 = 5623 decimal

        self._encoder = ConvolutionalEncoder(k=k, poly1=poly1, poly2=poly2)

        # Create bit interleaver
        # Interleaver uses size=2 (2 bits from FEC encoder), depth=idepth
        self._interleaver = Interleave(size=2, depth=self._idepth, direction=INTERLEAVE_FWD)

    # Removed _generate_raised_cosine_shape - now using shared dsp_utils.generate_raised_cosine_shape

    def tx_init(self):
        """Initialize transmitter state."""
        self._nco = NCO(self.sample_rate, self.frequency)
        self._prev_phase = 0.0
        self._preamble_sent = False
        self._encoder.reset()
        self._interleaver.flush()
        self._bitcount = 0
        self._xpsk_sym = 0

    def _tx_preamble(self, num_symbols: int = None) -> tuple[list, list]:
        """
        Generate preamble for synchronization (returns baseband I/Q).

        8PSK FEC sends symbol 0 (phase reversals) for preamble.
        From fldigi psk.cxx

        Args:
            num_symbols: Number of preamble symbols (default: dcdbits value)

        Returns:
            Tuple of (I samples list, Q samples list) at baseband
        """
        if num_symbols is None:
            num_symbols = self._dcdbits

        i_samples = []
        q_samples = []

        # Send symbol 0 for preamble
        for _ in range(num_symbols):
            i_sym, q_sym = self._tx_symbol(0)
            i_samples.extend(i_sym)
            q_samples.extend(q_sym)

        # Send NULL character (0x00) after preamble for sync
        i_null, q_null = self._tx_char(0)
        i_samples.extend(i_null)
        q_samples.extend(q_null)

        return i_samples, q_samples

    def _tx_postamble(self, num_symbols: int = None) -> tuple[list, list]:
        """
        Generate postamble for clean ending (returns baseband I/Q).

        8PSK FEC postamble flushes encoder and sends symbol 4 (0°) for DCD.
        From fldigi psk.cxx

        Args:
            num_symbols: Number of postamble symbols (default: 3x dcdbits)

        Returns:
            Tuple of (I samples list, Q samples list) at baseband
        """
        if num_symbols is None:
            num_symbols = self._dcdbits * 3

        i_samples = []
        q_samples = []

        # Flush any remaining bits in the accumulator
        # Send flushlength zero bits to clear the FEC encoder
        for _ in range(self._flushlength):
            i_bits, q_bits = self._tx_bit(0)
            i_samples.extend(i_bits)
            q_samples.extend(q_bits)

        # Send postamble: symbol 4 (0° in Gray constellation)
        for _ in range(num_symbols):
            i_sym, q_sym = self._tx_symbol(4)
            i_samples.extend(i_sym)
            q_samples.extend(q_sym)

        return i_samples, q_samples

    def _tx_symbol(self, symbol: int) -> tuple[np.ndarray, np.ndarray]:
        """
        Generate baseband I/Q samples for a single 8PSK symbol.

        Uses Gray-mapped constellation for FEC modes.

        Args:
            symbol: Symbol value (0-7, representing 3 bits)

        Returns:
            Tuple of (I samples, Q samples) at baseband
        """
        # Map symbol to complex value using Gray constellation
        symbol_complex = self.GRAY_CONSTELLATION.get(symbol & 7, self.GRAY_CONSTELLATION[0])

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
        Transmit a single bit using FEC encoding and interleaving.

        This implements the tx_xpsk() function from fldigi psk.cxx:2363-2425

        For non-punctured 8PSK FEC (125F/FL, 250F/FL):
        - Each input bit is encoded to 2 FEC bits (rate 1/2)
        - FEC bits are interleaved
        - Accumulate until we have 3 bits, then transmit as 8PSK symbol

        For punctured 8PSK FEC (500F, 1000F, 1200F):
        - Rate 2/3: Every 2 input bits -> 4 FEC bits -> puncture 1 -> 3 bits transmitted

        Args:
            bit: Bit value (0 or 1)

        Returns:
            Tuple of (I samples list, Q samples list)
        """
        i_samples = []
        q_samples = []

        # Encode bit through convolutional encoder (1 bit -> 2 bits)
        fecbits = self._encoder.encode(bit & 1)

        # Interleave the 2 FEC bits
        fecbits = self._interleaver.bits(fecbits)

        # Now handle accumulation based on puncturing mode
        if self._puncturing:
            # Punctured mode: 2/3 rate
            # Pattern: collect 2 FEC bits, then add 1 more (drop the 2nd), transmit 3 bits
            if self._bitcount == 0:
                # Add 2 bits
                self._xpsk_sym = fecbits & 3
                self._bitcount = 2
            elif self._bitcount == 2:
                # Add only the low bit (puncture the high bit)
                self._xpsk_sym |= (fecbits & 1) << 2
                # Transmit symbol
                i_sym, q_sym = self._tx_symbol(self._xpsk_sym & 7)
                i_samples.extend(i_sym)
                q_samples.extend(q_sym)
                # Reset
                self._xpsk_sym = 0
                self._bitcount = 0
        else:
            # Non-punctured mode: 1/2 rate
            # Pattern: accumulate 2-bit chunks until we have 3 bits total
            if self._bitcount == 0:
                # Add 2 bits
                self._xpsk_sym = fecbits & 3
                self._bitcount = 2
            elif self._bitcount == 1:
                # Add 2 bits (now have 3), transmit
                self._xpsk_sym |= (fecbits & 1) << 1
                self._xpsk_sym |= (fecbits & 2) << 1
                i_sym, q_sym = self._tx_symbol(self._xpsk_sym & 7)
                i_samples.extend(i_sym)
                q_samples.extend(q_sym)
                # Reset
                self._xpsk_sym = 0
                self._bitcount = 0
            elif self._bitcount == 2:
                # Add 1 bit (now have 3), transmit, save remaining bit
                self._xpsk_sym |= (fecbits & 1) << 2
                i_sym, q_sym = self._tx_symbol(self._xpsk_sym & 7)
                i_samples.extend(i_sym)
                q_samples.extend(q_sym)
                # Save the second bit for next symbol
                self._xpsk_sym = (fecbits & 2) >> 1
                self._bitcount = 1

        return i_samples, q_samples

    def _tx_char(self, char_code: int) -> tuple[list, list]:
        """
        Transmit a single character using MFSK/ARQ varicode encoding.

        8PSK FEC uses MFSK/ARQ varicode, NOT PSK varicode.

        Args:
            char_code: ASCII character code (0-255)

        Returns:
            Tuple of (I samples list, Q samples list) at baseband
        """
        # Get MFSK varicode bits for this character
        bits = encode_text_to_bits(chr(char_code))

        i_samples = []
        q_samples = []

        # Transmit each bit through FEC encoder
        for bit in bits:
            i_bits, q_bits = self._tx_bit(bit)
            i_samples.extend(i_bits)
            q_samples.extend(q_bits)

        return i_samples, q_samples

    # Removed _apply_baseband_filter - now using shared dsp_utils.apply_baseband_filter
    # Removed _modulate_to_carrier - now using shared dsp_utils.modulate_to_carrier

    def tx_process(self, text: str, preamble_symbols: int = None, postamble_symbols: int = None, apply_filter: bool = True) -> np.ndarray:
        """
        Process text for transmission.

        Args:
            text: Text to transmit
            preamble_symbols: Number of preamble symbols (default: dcdbits value)
            postamble_symbols: Number of postamble symbols (default: 3x dcdbits)
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
        Modulate text into 8PSK FEC audio signal.

        Args:
            text: Text string to modulate
            frequency: Carrier frequency in Hz (default: uses initialized value)
            sample_rate: Sample rate in Hz (default: uses initialized value)
            preamble_symbols: Number of preamble symbols (default: dcdbits value)
            postamble_symbols: Number of postamble symbols (default: 3x dcdbits)
            apply_filter: Apply baseband lowpass filtering (default: True)

        Returns:
            Audio samples as numpy array of float32 values (-1.0 to 1.0)

        Example:
            >>> modem = EightPSKFEC(baud=250)  # 8PSK250F
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

    def __repr__(self) -> str:
        """String representation of the modem."""
        encoder_type = "K16" if self._use_k16 else "K13"
        punct_mode = "2/3" if self._puncturing else "1/2"
        return (f"EightPSKFEC(mode={self.mode_name}, baud={self.baud}, "
                f"encoder={encoder_type}, rate={punct_mode}, "
                f"freq={self.frequency}Hz, fs={self.sample_rate}Hz)")


# Convenience functions for common 8PSK FEC modes
# Named to match fldigi's convention: 8PSK125F, 8PSK125FL, etc.

def EightPSK_125F(sample_rate: float = 8000.0, frequency: float = 1000.0, tx_amplitude: float = 0.8) -> EightPSKFEC:
    """Create an 8PSK125F modem (125 baud, K=16 FEC)."""
    return EightPSKFEC(baud=125, sample_rate=sample_rate, frequency=frequency,
                       tx_amplitude=tx_amplitude, long_interleave=False)


def EightPSK_125FL(sample_rate: float = 8000.0, frequency: float = 1000.0, tx_amplitude: float = 0.8) -> EightPSKFEC:
    """Create an 8PSK125FL modem (125 baud, K=13 FEC, long interleave)."""
    return EightPSKFEC(baud=125, sample_rate=sample_rate, frequency=frequency,
                       tx_amplitude=tx_amplitude, long_interleave=True)


def EightPSK_250F(sample_rate: float = 8000.0, frequency: float = 1000.0, tx_amplitude: float = 0.8) -> EightPSKFEC:
    """Create an 8PSK250F modem (250 baud, K=16 FEC)."""
    return EightPSKFEC(baud=250, sample_rate=sample_rate, frequency=frequency,
                       tx_amplitude=tx_amplitude, long_interleave=False)


def EightPSK_250FL(sample_rate: float = 8000.0, frequency: float = 1000.0, tx_amplitude: float = 0.8) -> EightPSKFEC:
    """Create an 8PSK250FL modem (250 baud, K=13 FEC, long interleave)."""
    return EightPSKFEC(baud=250, sample_rate=sample_rate, frequency=frequency,
                       tx_amplitude=tx_amplitude, long_interleave=True)


def EightPSK_500F(sample_rate: float = 8000.0, frequency: float = 1000.0, tx_amplitude: float = 0.8) -> EightPSKFEC:
    """Create an 8PSK500F modem (500 baud, K=13 FEC, 2/3 rate punctured)."""
    return EightPSKFEC(baud=500, sample_rate=sample_rate, frequency=frequency, tx_amplitude=tx_amplitude)


def EightPSK_1000F(sample_rate: float = 8000.0, frequency: float = 1000.0, tx_amplitude: float = 0.8) -> EightPSKFEC:
    """Create an 8PSK1000F modem (1000 baud, K=13 FEC, 2/3 rate punctured)."""
    return EightPSKFEC(baud=1000, sample_rate=sample_rate, frequency=frequency, tx_amplitude=tx_amplitude)


def EightPSK_1200F(sample_rate: float = 8000.0, frequency: float = 1000.0, tx_amplitude: float = 0.8) -> EightPSKFEC:
    """Create an 8PSK1200F modem (1200 baud, K=13 FEC, 2/3 rate punctured)."""
    return EightPSKFEC(baud=1200, sample_rate=sample_rate, frequency=frequency, tx_amplitude=tx_amplitude)
