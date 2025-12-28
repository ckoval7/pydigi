"""MFSK (Multiple Frequency Shift Keying) modem implementation.

This module implements MFSK modems with various symbol rates and number of tones.
MFSK uses multiple frequency tones to transmit data, with forward error correction
via Viterbi encoding and time diversity through interleaving for improved reliability.

The MFSK family includes modes from MFSK4 (ultra-slow, 3.90625 baud) to MFSK128
(fast, 125 baud), offering a range of speed/robustness tradeoffs.

Key Features:
    - Multiple frequency shift keying with 16 or 32 tones
    - Viterbi FEC (K=7, rate 1/2)
    - Time diversity through interleaving
    - Varicode encoding for efficient text transmission
    - Configurable symbol lengths and interleave depths

Common Modes:
    - MFSK16: 16 tones, 15.625 baud (~1000 Hz center)
    - MFSK32: 16 tones, 31.25 baud
    - MFSK64: 16 tones, 62.5 baud
    - MFSK128: 16 tones, 125 baud

Example:
    Generate MFSK16 signal::

        from pydigi.modems.mfsk import MFSK16
        from pydigi.utils.audio import save_wav

        modem = MFSK16()
        audio = modem.modulate("CQ CQ DE W1ABC")
        save_wav("mfsk16_test.wav", audio, 8000)

Reference:
    fldigi/src/mfsk/mfsk.cxx

Attributes:
    gray_encode: Function to apply Gray coding to symbol values
"""

import numpy as np
from ..core.oscillator import NCO
from ..core.encoder import create_mfsk_encoder
from ..core.interleave import Interleave, INTERLEAVE_FWD
from ..varicode.mfsk_varicode import encode_char as mfsk_varicode_encode
from .base import Modem


def gray_encode(value: int) -> int:
    """Encode a value using Gray code algorithm.

    Gray code ensures adjacent symbols differ by only one bit,
    reducing error probability when noise causes a symbol to be
    received as an adjacent symbol. This implementation works for
    any number of bits (unlike a lookup table).

    The Gray code is computed using XOR shift algorithm:
        result = value XOR (value >> 1) XOR (value >> 2) ...

    Args:
        value: Integer value to encode (0-255)

    Returns:
        int: Gray-coded value

    Example:
        >>> gray_encode(5)  # Binary 101
        7  # Gray code 111
        >>> gray_encode(6)  # Binary 110
        5  # Gray code 101

    Reference:
        fldigi/src/misc/misc.cxx grayencode()
    """
    # Compute Gray code using XOR shift algorithm
    bits = value
    bits ^= value >> 1
    bits ^= value >> 2
    bits ^= value >> 3
    bits ^= value >> 4
    bits ^= value >> 5
    bits ^= value >> 6
    bits ^= value >> 7
    return bits


class MFSK(Modem):
    """
    MFSK (Multiple Frequency Shift Keying) Modem.

    MFSK transmits data using multiple frequency tones, with forward error
    correction via Viterbi encoding and time diversity via interleaving.

    Common modes:
    - MFSK16: 16 tones, 15.625 baud, ~1000 Hz center frequency
    - MFSK32: 16 tones, 31.25 baud
    - MFSK64: 16 tones, 62.5 baud

    Reference: fldigi/src/mfsk/mfsk.cxx
    """

    def __init__(
        self,
        symlen: int = 512,
        symbits: int = 4,
        depth: int = 10,
        basetone: int = 64,
        sample_rate: int = 8000,
        frequency: float = 1000,
        tx_amplitude: float = 0.8,
        reverse: bool = False,
    ):
        """
        Initialize MFSK modem.

        Args:
            symlen: Symbol length in samples (default: 512 for MFSK16)
            symbits: Bits per symbol (default: 4 for 16 tones)
            depth: Interleave depth (default: 10)
            basetone: Base tone FFT bin (default: 64)
            sample_rate: Audio sample rate in Hz (default: 8000)
            frequency: Center frequency in Hz (default: 1000)
            tx_amplitude: Transmit amplitude 0.0-1.0 (default: 0.8)
            reverse: Reverse tone order if True (default: False)

        Reference:
            fldigi/src/mfsk/mfsk.cxx lines 177-359
        """
        # Determine mode name from parameters
        mode_name = f"MFSK{symbits}_{symlen}"
        super().__init__(mode_name=mode_name, sample_rate=sample_rate, frequency=frequency)

        self.symlen = symlen
        self.symbits = symbits
        self.depth = depth
        self.basetone = basetone
        self.tx_amplitude = tx_amplitude
        self.reverse = reverse

        # Derived parameters
        self.numtones = 1 << symbits  # 2^symbits (e.g., 16 for 4 bits)
        self.tonespacing = sample_rate / symlen  # Hz per tone
        self.basefreq = sample_rate * basetone / symlen  # Base frequency in Hz
        self._bandwidth = (
            self.numtones - 1
        ) * self.tonespacing  # Use _bandwidth (base class property)
        self.baud_rate = sample_rate / symlen

        # FEC encoder (NASA K=7, POLY1=0x6d, POLY2=0x4f)
        self.enc = create_mfsk_encoder()

        # Interleaver for time diversity
        self.txinlv = Interleave(symbits, depth, INTERLEAVE_FWD)

        # TX state
        self.bitshreg = 0  # Bit shift register
        self.bitstate = 0  # Number of bits accumulated
        self.phaseacc = 0  # Phase accumulator
        self.default_preamble = 107  # Default preamble length

    def _gray_encode(self, value):
        """Gray encode a symbol value."""
        return gray_encode(value & (self.numtones - 1))

    def _sendsymbol(self, sym):
        """
        Generate audio samples for a single symbol.

        Args:
            sym: Symbol value (0 to numtones-1)

        Returns:
            Array of audio samples

        Reference:
            fldigi/src/mfsk/mfsk.cxx lines 941-959
        """
        # Apply Gray coding
        sym = self._gray_encode(sym)

        # Reverse tone order if requested
        if self.reverse:
            sym = (self.numtones - 1) - sym

        # Calculate tone frequency
        # Start from lower edge of bandwidth, then add spacing
        f_base = self.frequency - self.bandwidth / 2
        tone_freq = f_base + sym * self.tonespacing

        # Generate symbol using phase accumulation
        phaseincr = 2 * np.pi * tone_freq / self.sample_rate
        samples = np.zeros(self.symlen, dtype=np.float64)

        for i in range(self.symlen):
            samples[i] = np.cos(self.phaseacc)
            self.phaseacc -= phaseincr
            if self.phaseacc < 0:
                self.phaseacc += 2 * np.pi

        return samples

    def _sendbit(self, bit):
        """
        Send a single bit through the encoder and interleaver.

        Each bit is encoded into 2 bits (rate 1/2), then accumulated
        until we have enough bits for a symbol.

        Args:
            bit: Input bit (0 or 1)

        Returns:
            Audio samples if a symbol was generated, None otherwise

        Reference:
            fldigi/src/mfsk/mfsk.cxx lines 961-975
        """
        # Encode bit (1 bit in, 2 bits out)
        data = self.enc.encode(bit)

        samples = []

        # Process both output bits
        for i in range(2):
            # Extract bit i from encoded data
            bit_val = (data >> i) & 1

            # Accumulate bit
            self.bitshreg = (self.bitshreg << 1) | bit_val
            self.bitstate += 1

            # When we have enough bits for a symbol, send it
            if self.bitstate == self.symbits:
                # Interleave the bits
                sym = self.txinlv.bits(self.bitshreg)

                # Generate symbol audio
                sym_samples = self._sendsymbol(sym)
                samples.extend(sym_samples)

                # Reset bit accumulator
                self.bitstate = 0
                self.bitshreg = 0  # Critical: clear shift register!

        return np.array(samples) if samples else None

    def _sendchar(self, c):
        """
        Send a character using MFSK varicode.

        Args:
            c: Character to send (integer or char)

        Returns:
            Array of audio samples

        Reference:
            fldigi/src/mfsk/mfsk.cxx lines 977-983
        """
        # Convert to integer if needed
        if isinstance(c, str):
            c = ord(c)

        # Encode character to varicode
        code = mfsk_varicode_encode(c)

        # Send each bit in the varicode
        samples = []
        for bit_char in code:
            bit = int(bit_char)
            bit_samples = self._sendbit(bit)
            if bit_samples is not None:
                samples.extend(bit_samples)

        return np.array(samples) if samples else np.array([], dtype=np.float64)

    def _send_preamble(self, preamble_bits):
        """
        Send preamble for synchronization.

        Args:
            preamble_bits: Number of preamble bits to send

        Returns:
            Array of audio samples

        Reference:
            fldigi/src/mfsk/mfsk.cxx lines 1105-1112
        """
        samples = []

        # Send preamble/3 zero bits
        for _ in range(preamble_bits // 3):
            bit_samples = self._sendbit(0)
            if bit_samples is not None:
                samples.extend(bit_samples)

        return np.array(samples) if samples else np.array([], dtype=np.float64)

    def _send_start_sequence(self):
        """
        Send start sequence (CR, STX, CR).

        Reference:
            fldigi/src/mfsk/mfsk.cxx lines 1114-1118
        """
        samples = []
        for char in [ord("\r"), 2, ord("\r")]:  # CR, STX, CR
            char_samples = self._sendchar(char)
            if len(char_samples) > 0:
                samples.extend(char_samples)
        return np.array(samples) if samples else np.array([], dtype=np.float64)

    def _send_end_sequence(self):
        """
        Send end sequence (CR, EOT, CR).

        Reference:
            fldigi/src/mfsk/mfsk.cxx lines 1150-1153
        """
        samples = []
        for char in [ord("\r"), 4, ord("\r")]:  # CR, EOT, CR
            char_samples = self._sendchar(char)
            if len(char_samples) > 0:
                samples.extend(char_samples)
        return np.array(samples) if samples else np.array([], dtype=np.float64)

    def _flush_encoder(self, flush_bits):
        """
        Flush the encoder by sending zero bits.

        Reference:
            fldigi/src/mfsk/mfsk.cxx lines 995-1011
        """
        samples = []

        # Send flush_bits zero bits to clear the encoder
        for _ in range(flush_bits):
            bit_samples = self._sendbit(0)
            if bit_samples is not None:
                samples.extend(bit_samples)

        return np.array(samples) if samples else np.array([], dtype=np.float64)

    def tx_init(self) -> None:
        """
        Initialize transmitter state.

        Reference:
            fldigi/src/mfsk/mfsk.cxx lines 1079-1092
        """
        # Reset encoder and interleaver
        self.enc.reset()
        self.txinlv.flush()

        # Reset bit accumulator
        self.bitshreg = 0
        self.bitstate = 0

        # Reset phase accumulator
        self.phaseacc = 0

    def tx_process(self, text: str) -> np.ndarray:
        """
        Process text and generate MFSK signal.

        Args:
            text: Text string to transmit

        Returns:
            Array of audio samples normalized to [-1.0, 1.0]

        Reference:
            fldigi/src/mfsk/mfsk.cxx lines 1093-1165
        """
        output = []

        # 1. Send preamble
        preamble_samples = self._send_preamble(self.default_preamble)
        if len(preamble_samples) > 0:
            output.extend(preamble_samples)

        # 2. Send start sequence
        start_samples = self._send_start_sequence()
        if len(start_samples) > 0:
            output.extend(start_samples)

        # 3. Send data
        for char in text:
            char_samples = self._sendchar(char)
            if len(char_samples) > 0:
                output.extend(char_samples)

        # 4. Send end sequence
        end_samples = self._send_end_sequence()
        if len(end_samples) > 0:
            output.extend(end_samples)

        # 5. Flush encoder
        flush_samples = self._flush_encoder(self.default_preamble)
        if len(flush_samples) > 0:
            output.extend(flush_samples)

        # Convert to array
        signal = np.array(output, dtype=np.float64)

        # Apply amplitude scaling
        signal = signal * self.tx_amplitude

        # Normalize to [-1.0, 1.0]
        max_val = np.max(np.abs(signal))
        if max_val > 1.0:
            signal = signal / max_val

        return signal.astype(np.float32)

    def modulate(
        self,
        text: str,
        frequency: float = None,
        sample_rate: float = None,
        preamble: int = None,
        reverse: bool = None,
    ) -> np.ndarray:
        """
        Modulate text into MFSK audio signal.

        Args:
            text: Text to transmit
            frequency: Center frequency in Hz (default: use instance value)
            sample_rate: Sample rate in Hz (default: use instance value)
            preamble: Number of preamble symbols (default: mode-specific)
            reverse: Reverse tone order if True (default: use instance value)

        Returns:
            Numpy array of audio samples normalized to [-1.0, 1.0]

        Reference:
            fldigi/src/mfsk/mfsk.cxx lines 1079-1165
        """
        # Store original values for custom parameters
        original_preamble = self.default_preamble
        original_reverse = self.reverse

        # Apply overrides if provided
        if preamble is not None:
            self.default_preamble = preamble
        if reverse is not None:
            self.reverse = reverse

        # Call base class modulate (handles frequency and sample_rate overrides)
        signal = super().modulate(text, frequency, sample_rate)

        # Restore original values
        self.default_preamble = original_preamble
        self.reverse = original_reverse

        return signal


# Convenience functions for common MFSK modes


def MFSK4(sample_rate: int = 8000) -> "MFSK":
    """
    Create MFSK4 modem (32 tones, 3.90625 baud).

    Very slow MFSK mode for extreme weak-signal conditions.

    Args:
        sample_rate: Audio sample rate in Hz (default: 8000)

    Returns:
        MFSK modem configured for MFSK4

    Reference:
        fldigi/src/mfsk/mfsk.cxx lines 188-196
    """
    modem = MFSK(symlen=2048, symbits=5, depth=5, basetone=256, sample_rate=sample_rate)
    modem.default_preamble = 107  # Standard preamble
    return modem


def MFSK8(sample_rate: int = 8000) -> "MFSK":
    """
    Create MFSK8 modem (32 tones, 7.8125 baud).

    Slower MFSK mode with more tones for better weak-signal performance.

    Args:
        sample_rate: Audio sample rate in Hz (default: 8000)

    Returns:
        MFSK modem configured for MFSK8

    Reference:
        fldigi/src/mfsk/mfsk.cxx lines 197-205
    """
    modem = MFSK(symlen=1024, symbits=5, depth=5, basetone=128, sample_rate=sample_rate)
    modem.default_preamble = 107  # Standard preamble
    return modem


def MFSK11(sample_rate: int = 11025) -> "MFSK":
    """
    Create MFSK11 modem (16 tones, 10.77 baud).

    MFSK mode using 11025 Hz sample rate for compatibility with sound cards.

    Args:
        sample_rate: Audio sample rate in Hz (default: 11025)

    Returns:
        MFSK modem configured for MFSK11

    Reference:
        fldigi/src/mfsk/mfsk.cxx lines 265-273
    """
    modem = MFSK(symlen=1024, symbits=4, depth=10, basetone=93, sample_rate=sample_rate)
    modem.default_preamble = 107  # Standard preamble
    return modem


def MFSK16(sample_rate: int = 8000) -> "MFSK":
    """
    Create MFSK16 modem (16 tones, 15.625 baud).

    Standard MFSK mode with good balance of speed and reliability.

    Args:
        sample_rate: Audio sample rate in Hz (default: 8000)

    Returns:
        MFSK modem configured for MFSK16

    Reference:
        fldigi/src/mfsk/mfsk.cxx lines 284-294
    """
    modem = MFSK(symlen=512, symbits=4, depth=10, basetone=64, sample_rate=sample_rate)
    modem.default_preamble = 107  # Standard preamble
    return modem


def MFSK32(sample_rate: int = 8000) -> "MFSK":
    """
    Create MFSK32 modem (16 tones, 31.25 baud).

    Faster MFSK mode, half the symbol time of MFSK16.

    Args:
        sample_rate: Audio sample rate in Hz (default: 8000)

    Returns:
        MFSK modem configured for MFSK32

    Reference:
        fldigi/src/mfsk/mfsk.cxx lines 215-224
    """
    modem = MFSK(symlen=256, symbits=4, depth=10, basetone=32, sample_rate=sample_rate)
    modem.default_preamble = 107  # Standard preamble
    return modem


def MFSK64(sample_rate: int = 8000) -> "MFSK":
    """
    Create MFSK64 modem (16 tones, 62.5 baud).

    Fast MFSK mode with higher throughput.

    Args:
        sample_rate: Audio sample rate in Hz (default: 8000)

    Returns:
        MFSK modem configured for MFSK64

    Reference:
        fldigi/src/mfsk/mfsk.cxx lines 225-234
    """
    modem = MFSK(symlen=128, symbits=4, depth=10, basetone=16, sample_rate=sample_rate)
    modem.default_preamble = 180  # Longer preamble for faster mode
    return modem


def MFSK22(sample_rate: int = 11025) -> "MFSK":
    """
    Create MFSK22 modem (16 tones, 21.53 baud).

    Faster MFSK mode using 11025 Hz sample rate.

    Args:
        sample_rate: Audio sample rate in Hz (default: 11025)

    Returns:
        MFSK modem configured for MFSK22

    Reference:
        fldigi/src/mfsk/mfsk.cxx lines 274-282
    """
    modem = MFSK(symlen=512, symbits=4, depth=10, basetone=46, sample_rate=sample_rate)
    modem.default_preamble = 107  # Standard preamble
    return modem


def MFSK31(sample_rate: int = 8000) -> "MFSK":
    """
    Create MFSK31 modem (8 tones, 31.25 baud).

    MFSK mode with only 8 tones for narrower bandwidth.

    Args:
        sample_rate: Audio sample rate in Hz (default: 8000)

    Returns:
        MFSK modem configured for MFSK31

    Reference:
        fldigi/src/mfsk/mfsk.cxx lines 206-214
    """
    modem = MFSK(symlen=256, symbits=3, depth=10, basetone=32, sample_rate=sample_rate)
    modem.default_preamble = 107  # Standard preamble
    return modem


def MFSK128(sample_rate: int = 8000) -> "MFSK":
    """
    Create MFSK128 modem (16 tones, 125 baud).

    Very fast MFSK mode for good conditions.

    Args:
        sample_rate: Audio sample rate in Hz (default: 8000)

    Returns:
        MFSK modem configured for MFSK128

    Reference:
        fldigi/src/mfsk/mfsk.cxx lines 235-244
    """
    modem = MFSK(symlen=64, symbits=4, depth=20, basetone=8, sample_rate=sample_rate)
    modem.default_preamble = 214  # Even longer preamble
    return modem


def MFSK64L(sample_rate: int = 8000) -> "MFSK":
    """
    Create MFSK64L modem (16 tones, 62.5 baud, long interleave).

    MFSK64 with long interleaver (depth=400) for extreme multipath conditions.
    Uses much longer preamble (2500 symbols) for synchronization.

    Args:
        sample_rate: Audio sample rate in Hz (default: 8000)

    Returns:
        MFSK modem configured for MFSK64L

    Reference:
        fldigi/src/mfsk/mfsk.cxx lines 246-253
    """
    modem = MFSK(symlen=128, symbits=4, depth=400, basetone=16, sample_rate=sample_rate)
    modem.default_preamble = 2500  # Very long preamble for sync
    return modem


def MFSK128L(sample_rate: int = 8000) -> "MFSK":
    """
    Create MFSK128L modem (16 tones, 125 baud, long interleave).

    MFSK128 with very long interleaver (depth=800) for extreme multipath.
    Uses very long preamble (5000 symbols) for synchronization.

    Args:
        sample_rate: Audio sample rate in Hz (default: 8000)

    Returns:
        MFSK modem configured for MFSK128L

    Reference:
        fldigi/src/mfsk/mfsk.cxx lines 255-263
    """
    modem = MFSK(symlen=64, symbits=4, depth=800, basetone=8, sample_rate=sample_rate)
    modem.default_preamble = 5000  # Extremely long preamble for sync
    return modem
