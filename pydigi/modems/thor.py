"""Thor MFSK modem implementation.

Thor is a robust MFSK mode combining Incremental Frequency Keying (IFK) with
powerful Viterbi forward error correction and interleaving. It offers excellent
performance under difficult propagation conditions while maintaining good throughput.

Like DominoEX, Thor uses differential frequency encoding (IFK) which makes it
highly resistant to frequency drift and Doppler shift. The addition of Viterbi
FEC and configurable interleaving provides superior error correction compared
to DominoEX, at the cost of slightly reduced speed.

Key Features:
    - 18 tones with incremental frequency keying (IFK)
    - Viterbi FEC with K=7 (NASA) or K=15 (IEEE) constraint length
    - Variable interleaving depths (4, 10, 25, 50) for time diversity
    - Thor varicode encoding for efficient text transmission
    - 15 different modes with varying speed/robustness tradeoffs
    - Continuous phase modulation for spectral efficiency

Common Modes:
    - Thor Micro: ~2 baud (K=7, depth=4, ultra-slow)
    - Thor 4: ~3.9 baud (K=7, depth=10)
    - Thor 8: ~7.8 baud (K=7, depth=10)
    - Thor 11: ~10.8 baud (K=7, depth=10)
    - Thor 16: ~15.6 baud (K=7, depth=25)
    - Thor 22: ~21.5 baud (K=7, depth=25)

Example:
    Generate Thor 16 signal::

        from pydigi.modems.thor import Thor16
        from pydigi.utils.audio import save_wav

        modem = Thor16()
        audio = modem.modulate("CQ CQ DE W1ABC")
        save_wav("thor16_test.wav", audio, 8000)

Note:
    Thor uses IFK modulation like DominoEX:
        tone = (prev_tone + 2 + symbol) % 18
    Combined with rate 1/2 Viterbi FEC for excellent error correction.

Reference:
    fldigi/src/thor/thor.cxx

Attributes:
    NUMTONES (int): Number of MFSK tones (18)
    BASEFREQ (float): Base frequency in Hz (1500.0)
    INTERLEAVE_SIZE (int): Interleaver block size (4 bits)
    K7_CONSTRAINT (int): NASA Voyager constraint length (7)
    K7_POLY1 (int): NASA polynomial 1 (0x6d)
    K7_POLY2 (int): NASA polynomial 2 (0x4f)
    K15_CONSTRAINT (int): IEEE constraint length (15)
    K15_POLY1 (int): IEEE polynomial 1 (0o44735)
    K15_POLY2 (int): IEEE polynomial 2 (0o63057)
"""

import numpy as np
from pydigi.modems.base import Modem
from pydigi.varicode.thor_varicode import thor_varicode_encode
from pydigi.core.encoder import ConvolutionalEncoder
from pydigi.core.interleave import Interleave, INTERLEAVE_FWD


class Thor(Modem):
    """
    Thor MFSK modem with incremental frequency keying.

    Thor uses 18-tone MFSK with IFK (Incremental Frequency Keying), where each symbol
    is transmitted as a relative tone shift from the previous tone, making it highly
    resistant to frequency drift.

    Modulation:
        tone = (prev_tone + 2 + symbol) % 18

    The mode uses Viterbi FEC (K=7 or K=15) and interleaving for error correction.

    Args:
        symlen: Symbol length in samples
        sample_rate: Sample rate in Hz (8000, 11025, or 16000)
        doublespaced: Tone spacing multiplier (1, 2, or 4)
        interleave_depth: Interleaver depth (4, 10, 25, or 50)
        flushlength: Number of idle characters for postamble
        use_k15: If True, use K=15 encoder (IEEE), else K=7 (NASA Voyager)
        secondary_text: Optional secondary text string for idle periods

    Reference: fldigi/src/thor/thor.cxx - constructor (lines 217-426)
    """

    # Thor constants
    NUMTONES = 18  # Number of MFSK tones (fldigi: THORNUMTONES)
    BASEFREQ = 1500.0  # Base frequency in Hz (fldigi: THORBASEFREQ)
    INTERLEAVE_SIZE = 4  # Interleaver block size (4 bits per symbol)

    # NASA Voyager codes (K=7) - used for most Thor modes
    K7_CONSTRAINT = 7
    K7_POLY1 = 0x6D  # 109
    K7_POLY2 = 0x4F  # 79

    # IEEE codes (K=15) - used for high-speed modes
    K15_CONSTRAINT = 15
    K15_POLY1 = 0o44735  # 18909 decimal
    K15_POLY2 = 0o63057  # 26139 decimal

    def __init__(
        self,
        symlen: int,
        sample_rate: int = 8000,
        frequency: float = 1500.0,
        tx_amplitude: float = 0.8,
        doublespaced: int = 1,
        interleave_depth: int = 10,
        flushlength: int = 4,
        use_k15: bool = False,
        secondary_text: str = "fldigi pydigi",
        mode_name: str = "Thor",
    ):
        super().__init__(mode_name=mode_name, sample_rate=sample_rate, frequency=frequency)

        self.symlen = symlen
        self.tx_amplitude = tx_amplitude
        self.doublespaced = doublespaced
        self.interleave_depth = interleave_depth
        self.flushlength = flushlength
        self.use_k15 = use_k15
        self.secondary_text = secondary_text
        self.secondary_ptr = 0

        # Calculate tone spacing and bandwidth
        # Reference: fldigi/src/thor/thor.cxx line 351
        self.tonespacing = 1.0 * sample_rate * doublespaced / symlen
        self._bandwidth = self.NUMTONES * self.tonespacing

        # Calculate symbol rate (baud)
        self.baud_rate = sample_rate / symlen

        # Initialize Viterbi encoder
        # Reference: fldigi/src/thor/thor.cxx lines 398-407
        if use_k15:
            self.encoder = ConvolutionalEncoder(self.K15_CONSTRAINT, self.K15_POLY1, self.K15_POLY2)
        else:
            self.encoder = ConvolutionalEncoder(self.K7_CONSTRAINT, self.K7_POLY1, self.K7_POLY2)

        # Initialize interleaver
        # Reference: fldigi/src/thor/thor.cxx line 408
        self.interleaver = Interleave(self.INTERLEAVE_SIZE, interleave_depth, INTERLEAVE_FWD)

        # TX state variables
        self.prev_tone = 0
        self.bit_accumulator = 0
        self.bit_count = 0
        self.txphase = 0.0  # Phase accumulator for continuous phase

    def tx_init(self) -> None:
        """
        Initialize transmitter state.

        Resets all TX state variables for a fresh transmission.
        Required by base Modem class.
        """
        self.prev_tone = 0
        self.bit_accumulator = 0
        self.bit_count = 0
        self.secondary_ptr = 0
        self.txphase = 0.0  # Reset phase accumulator
        self.encoder.reset()
        self.interleaver.init()

    def tx_process(self, text: str) -> np.ndarray:
        """
        Process text and generate Thor signal.

        Args:
            text: Text to transmit

        Returns:
            numpy array of audio samples normalized to [-1.0, 1.0]
        """
        output = []

        # Determine if this is Thor Micro mode (symlen == 4000)
        is_micro = self.symlen == 4000

        # Send preamble
        self._send_preamble(self.frequency, output, is_micro)

        # Send start sequence
        self._send_start_sequence(self.frequency, output, is_micro)

        # Send data characters
        for char in text:
            self._send_char(char, self.frequency, output, secondary=False)

        # Send end sequence
        self._send_end_sequence(self.frequency, output, is_micro)

        # Send postamble (includes padding any partial bits)
        self._send_postamble(self.frequency, output)

        # Add silence at the end to allow receiver to finish decoding
        silence_symbols = 20
        silence_duration = (silence_symbols * self.symlen) / self.sample_rate
        silence_duration = max(silence_duration, 0.5)  # At least 500ms
        silence_samples = int(self.sample_rate * silence_duration)
        for _ in range(silence_samples):
            output.append(0.0)

        # Convert to numpy array
        signal = np.array(output, dtype=np.float32)

        # Apply amplitude scaling
        signal = signal * self.tx_amplitude

        # Normalize to [-1.0, 1.0]
        max_val = np.max(np.abs(signal))
        if max_val > 1.0:
            signal = signal / max_val

        return signal.astype(np.float32)

    def _send_tone(self, tone, duration, frequency, output):
        """
        Generate tone at specified frequency for given duration.

        IMPORTANT: Maintains phase continuity across symbols using self.txphase.
        This is critical for proper decoding!

        Args:
            tone: Tone number (0-17)
            duration: Duration in symbols
            frequency: Center frequency in Hz
            output: List to append samples to

        Reference: fldigi/src/thor/thor.cxx - sendtone() lines 1206-1231
        """
        # Calculate tone frequency
        # Reference: fldigi/src/thor/thor.cxx line 1209
        f = (tone + 0.5) * self.tonespacing + frequency - self.bandwidth / 2.0

        # Phase increment per sample
        # Note: fldigi uses txphase -= phaseincr (decrements), we use += (increments)
        # Both are equivalent, just different directions
        phase_incr = 2.0 * np.pi * f / self.sample_rate

        total_samples = duration * self.symlen

        for i in range(total_samples):
            # Use continuous phase (member variable, not local)
            sample = np.cos(self.txphase)
            output.append(sample)

            # Update phase and wrap
            self.txphase += phase_incr
            if self.txphase > 2.0 * np.pi:
                self.txphase -= 2.0 * np.pi

    def _send_symbol(self, symbol, frequency, output):
        """
        Send symbol using incremental frequency keying.

        IFK formula: tone = (prev_tone + 2 + symbol) % NUMTONES

        Args:
            symbol: Symbol value (0-15, 4 bits)
            frequency: Center frequency in Hz
            output: List to append samples to

        Reference: fldigi/src/thor/thor.cxx - sendsymbol() lines 1233-1243
        """
        # Calculate next tone using IFK
        tone = (self.prev_tone + 2 + symbol) % self.NUMTONES
        self.prev_tone = tone

        # Send the tone for 1 symbol duration
        self._send_tone(tone, 1, frequency, output)

    def _send_char(self, char, frequency, output, secondary=False):
        """
        Send a character using Thor varicode encoding.

        Process:
        1. Encode character to varicode bit string
        2. Pass each bit through Viterbi encoder (outputs 2 FEC bits per input bit)
        3. Accumulate 4 bits
        4. Interleave the 4 bits
        5. Send as a symbol (0-15)

        Args:
            char: Character to send
            frequency: Center frequency in Hz
            output: List to append samples to
            secondary: Use secondary character set

        Reference: fldigi/src/thor/thor.cxx - sendchar() lines 1247-1268
        """
        # Get varicode for character
        varicode_bits = thor_varicode_encode(char, secondary)

        # Encode each bit through Viterbi encoder
        for bit_char in varicode_bits:
            bit = int(bit_char)

            # Viterbi encoder outputs 2 bits for each input bit
            # Reference: fldigi/src/thor/thor.cxx line 1254
            fec_bits = self.encoder.encode(bit)

            # Process both FEC output bits
            for i in range(2):
                fec_bit = (fec_bits >> i) & 1

                # Accumulate bits
                self.bit_accumulator = (self.bit_accumulator << 1) | fec_bit
                self.bit_count += 1

                # When we have 4 bits, interleave and send as symbol
                if self.bit_count == 4:
                    # Interleave the 4 bits
                    # Reference: fldigi/src/thor/thor.cxx line 1259
                    interleaved = self.interleaver.bits(self.bit_accumulator)

                    # Send the symbol
                    self._send_symbol(interleaved, frequency, output)

                    # Reset accumulator
                    self.bit_accumulator = 0
                    self.bit_count = 0

    def _send_idle(self, frequency, output):
        """
        Send idle character (NUL).

        Reference: fldigi/src/thor/thor.cxx - sendidle() lines 1270-1273
        """
        self._send_char("\x00", frequency, output, secondary=False)

    def _get_secondary_char(self):
        """
        Get next character from secondary text string.

        Reference: fldigi/src/thor/thor.cxx - get_secondary_char() lines 1197-1204
        """
        if len(self.secondary_text) == 0:
            return " "

        if self.secondary_ptr >= len(self.secondary_text):
            self.secondary_ptr = 0

        char = self.secondary_text[self.secondary_ptr]
        self.secondary_ptr += 1
        return char

    def _clear_bits(self, frequency, output):
        """
        Flush the encoder and interleaver with zeros.

        IMPORTANT: Encode ONE zero bit, then use that FEC output repeatedly
        for 1400 iterations. This is how fldigi does it.

        Reference: fldigi/src/thor/thor.cxx - Clearbits() lines 1281-1295
        """
        # Encode ONE zero bit (with zero-initialized encoder state)
        # Reference: fldigi line 1283
        fec_bits = self.encoder.encode(0)

        # Use this same FEC output for 1400 iterations
        for _ in range(1400):
            # Process both FEC output bits
            for i in range(2):
                fec_bit = (fec_bits >> i) & 1

                self.bit_accumulator = (self.bit_accumulator << 1) | fec_bit
                self.bit_count += 1

                if self.bit_count == 4:
                    # Interleave but don't send (just clearing TX state)
                    self.interleaver.bits(self.bit_accumulator)
                    self.bit_accumulator = 0
                    self.bit_count = 0

    def _send_preamble(self, frequency, output, is_micro=False):
        """
        Send Thor preamble sequence.

        Preamble:
        1. Clearbits() - flush encoder with zeros
        2. 16 symbols of 0 (for synchronization)
        3. 1 idle character (NUL)

        Reference: fldigi/src/thor/thor.cxx - tx_process() lines 1320-1327
        """
        # Clear encoder and interleaver state
        self._clear_bits(frequency, output)

        # Send 16 symbols of 0 for synchronization
        for _ in range(16):
            self._send_symbol(0, frequency, output)

        # Send idle character
        self._send_idle(frequency, output)

    def _send_start_sequence(self, frequency, output, is_micro=False):
        """
        Send start sequence.

        Start sequence:
        - Thor Micro: CR only
        - Other modes: CR + STX + CR

        Reference: fldigi/src/thor/thor.cxx - tx_process() lines 1329-1335
        """
        self._send_char("\r", frequency, output, secondary=False)

        if not is_micro:
            self._send_char("\x02", frequency, output, secondary=False)  # STX
            self._send_char("\r", frequency, output, secondary=False)

    def _send_end_sequence(self, frequency, output, is_micro=False):
        """
        Send end sequence.

        End sequence:
        - Thor Micro: CR only
        - Other modes: CR + EOT + CR

        Reference: fldigi/src/thor/thor.cxx - tx_process() lines 1358-1364
        """
        self._send_char("\r", frequency, output, secondary=False)

        if not is_micro:
            self._send_char("\x04", frequency, output, secondary=False)  # EOT
            self._send_char("\r", frequency, output, secondary=False)

    def _send_postamble(self, frequency, output):
        """
        Send postamble sequence.

        Postamble: Send flushlength idle characters to flush decoder

        Reference: fldigi/src/thor/thor.cxx - flushtx() lines 1297-1309
        """
        for _ in range(self.flushlength):
            self._send_idle(frequency, output)

        # Discard any remaining partial bits (fldigi sets bitstate = 0)
        # Reference: fldigi/src/thor/thor.cxx line 1308
        self.bit_accumulator = 0
        self.bit_count = 0

    def estimate_duration(self, text: str, use_secondary: bool = False) -> float:
        """
        Estimate transmission duration in seconds.

        This is an approximation based on average character length in varicode.

        Args:
            text: Text to transmit
            use_secondary: Using secondary character set

        Returns:
            Estimated duration in seconds
        """
        # Preamble: Clearbits + 16 symbols + 1 idle (~700 symbols for Clearbits)
        preamble_symbols = 700 + 16 + 50  # Approx 50 symbols for idle char

        # Start sequence: ~150 symbols
        start_symbols = 150

        # Data: Estimate based on character count
        # Average ~12 bits per character in varicode
        # Each bit → 2 FEC bits → accumulated to 4 bits → 1 symbol
        # So ~6 symbols per character on average
        data_symbols = len(text) * 6

        # End sequence: ~150 symbols
        end_symbols = 150

        # Postamble: flushlength idle characters (~50 symbols each)
        postamble_symbols = self.flushlength * 50

        total_symbols = (
            preamble_symbols + start_symbols + data_symbols + end_symbols + postamble_symbols
        )

        # Convert symbols to time
        symbol_duration = self.symlen / self.sample_rate
        return total_symbols * symbol_duration


# ============================================================================
# Thor Mode Factory Functions
# ============================================================================


def ThorMicro():
    """
    Thor Micro - Ultra-slow weak signal mode.

    - Baud rate: 2.0 symbols/sec
    - Sample rate: 8000 Hz
    - Bandwidth: 18 Hz
    - Use case: Extremely weak signal conditions

    Reference: fldigi/src/thor/thor.cxx lines 260-265
    """
    return Thor(
        symlen=4000,
        sample_rate=8000,
        doublespaced=1,
        interleave_depth=4,
        flushlength=4,
        use_k15=False,
    )


def Thor4():
    """
    Thor 4 - Very slow mode with good weak-signal performance.

    - Baud rate: 3.90625 symbols/sec
    - Sample rate: 8000 Hz
    - Bandwidth: 36 Hz
    - Tone spacing: 2 Hz

    Reference: fldigi/src/thor/thor.cxx lines 267-271
    """
    return Thor(
        symlen=2048,
        sample_rate=8000,
        doublespaced=2,
        interleave_depth=10,
        flushlength=4,
        use_k15=False,
    )


def Thor5():
    """
    Thor 5 - Slow mode for weak signals.

    - Baud rate: 5.38 symbols/sec
    - Sample rate: 11025 Hz
    - Bandwidth: 36 Hz
    - Tone spacing: 2 Hz

    Reference: fldigi/src/thor/thor.cxx lines 229-234
    """
    return Thor(
        symlen=2048,
        sample_rate=11025,
        doublespaced=2,
        interleave_depth=10,
        flushlength=4,
        use_k15=False,
    )


def Thor8():
    """
    Thor 8 - Slow mode for weak signals.

    - Baud rate: 7.8125 symbols/sec
    - Sample rate: 8000 Hz
    - Bandwidth: 36 Hz
    - Tone spacing: 2 Hz

    Reference: fldigi/src/thor/thor.cxx lines 273-277
    """
    return Thor(
        symlen=1024,
        sample_rate=8000,
        doublespaced=2,
        interleave_depth=10,
        flushlength=4,
        use_k15=False,
    )


def Thor11():
    """
    Thor 11 - Medium-slow mode.

    - Baud rate: 10.76 symbols/sec
    - Sample rate: 11025 Hz
    - Bandwidth: 18 Hz
    - Tone spacing: 1 Hz

    Reference: fldigi/src/thor/thor.cxx lines 236-242
    """
    return Thor(
        symlen=1024,
        sample_rate=11025,
        doublespaced=1,
        interleave_depth=10,
        flushlength=8,
        use_k15=False,
    )


def Thor16():
    """
    Thor 16 - Standard mode (most popular).

    - Baud rate: 15.625 symbols/sec
    - Sample rate: 8000 Hz
    - Bandwidth: 18 Hz
    - Tone spacing: 1 Hz
    - Use case: General purpose HF digital mode

    Reference: fldigi/src/thor/thor.cxx lines 280-286
    """
    return Thor(
        symlen=512,
        sample_rate=8000,
        doublespaced=1,
        interleave_depth=10,
        flushlength=8,
        use_k15=False,
    )


def Thor22():
    """
    Thor 22 - Medium-fast mode.

    - Baud rate: 21.53 symbols/sec
    - Sample rate: 11025 Hz
    - Bandwidth: 18 Hz
    - Tone spacing: 1 Hz

    Reference: fldigi/src/thor/thor.cxx lines 244-250
    """
    return Thor(
        symlen=512,
        sample_rate=11025,
        doublespaced=1,
        interleave_depth=10,
        flushlength=16,
        use_k15=False,
    )


def Thor25():
    """
    Thor 25 - Fast mode with 1-second interleave.

    - Baud rate: 25.0 symbols/sec
    - Sample rate: 8000 Hz
    - Bandwidth: 18 Hz
    - Interleave: 1 second
    - Uses K=15 encoder (IEEE codes)

    Reference: fldigi/src/thor/thor.cxx lines 288-295
    """
    return Thor(
        symlen=320,
        sample_rate=8000,
        doublespaced=1,
        interleave_depth=25,
        flushlength=20,
        use_k15=True,
    )


def Thor32():
    """
    Thor 32 - Fast mode.

    - Baud rate: 31.25 symbols/sec
    - Sample rate: 8000 Hz
    - Bandwidth: 18 Hz

    Reference: fldigi/src/thor/thor.cxx lines 297-303
    """
    return Thor(
        symlen=256,
        sample_rate=8000,
        doublespaced=1,
        interleave_depth=10,
        flushlength=20,
        use_k15=False,
    )


def Thor44():
    """
    Thor 44 - Very fast mode.

    - Baud rate: 43.07 symbols/sec
    - Sample rate: 11025 Hz
    - Bandwidth: 18 Hz

    Reference: fldigi/src/thor/thor.cxx lines 252-257
    """
    return Thor(
        symlen=256,
        sample_rate=11025,
        doublespaced=1,
        interleave_depth=10,
        flushlength=16,
        use_k15=False,
    )


def Thor56():
    """
    Thor 56 - High-speed mode.

    - Baud rate: 55.17 symbols/sec
    - Sample rate: 16000 Hz
    - Bandwidth: 18 Hz

    Reference: fldigi/src/thor/thor.cxx lines 339-345
    """
    return Thor(
        symlen=290,
        sample_rate=16000,
        doublespaced=1,
        interleave_depth=10,
        flushlength=20,
        use_k15=False,
    )


def Thor25x4():
    """
    Thor 25x4 - 4-carrier mode with 2-second interleave.

    - Baud rate: 25.0 symbols/sec
    - Sample rate: 8000 Hz
    - Bandwidth: 72 Hz (4x tone spacing)
    - Interleave: 2 seconds
    - Uses K=15 encoder (IEEE codes)

    Reference: fldigi/src/thor/thor.cxx lines 305-311
    """
    return Thor(
        symlen=320,
        sample_rate=8000,
        doublespaced=4,
        interleave_depth=50,
        flushlength=40,
        use_k15=True,
    )


def Thor50x1():
    """
    Thor 50x1 - High-speed mode with 1-second interleave.

    - Baud rate: 50.0 symbols/sec
    - Sample rate: 8000 Hz
    - Bandwidth: 18 Hz
    - Interleave: 1 second
    - Uses K=15 encoder (IEEE codes)

    Reference: fldigi/src/thor/thor.cxx lines 313-319
    """
    return Thor(
        symlen=160,
        sample_rate=8000,
        doublespaced=1,
        interleave_depth=50,
        flushlength=40,
        use_k15=True,
    )


def Thor50x2():
    """
    Thor 50x2 - 2-carrier high-speed mode with 1-second interleave.

    - Baud rate: 50.0 symbols/sec
    - Sample rate: 8000 Hz
    - Bandwidth: 36 Hz (2x tone spacing)
    - Interleave: 1 second
    - Uses K=15 encoder (IEEE codes)

    Reference: fldigi/src/thor/thor.cxx lines 321-327
    """
    return Thor(
        symlen=160,
        sample_rate=8000,
        doublespaced=2,
        interleave_depth=50,
        flushlength=40,
        use_k15=True,
    )


def Thor100():
    """
    Thor 100 - Very high-speed mode with 0.5-second interleave.

    - Baud rate: 100.0 symbols/sec
    - Sample rate: 8000 Hz
    - Bandwidth: 18 Hz
    - Interleave: 0.5 seconds
    - Uses K=15 encoder (IEEE codes)

    Reference: fldigi/src/thor/thor.cxx lines 329-335
    """
    return Thor(
        symlen=80,
        sample_rate=8000,
        doublespaced=1,
        interleave_depth=50,
        flushlength=40,
        use_k15=True,
    )
