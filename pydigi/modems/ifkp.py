"""
IFKP (Incremental Frequency Keying Plus) Modem Implementation.

IFKP is an MFSK mode with an offset of +1, designed for very high coding efficiency.
It uses 33 tones (32 differences), a mildly Varicoded Alphabet, with a rotating
difference frequency.

Reference: fldigi/src/ifkp/ifkp.cxx
"""

import numpy as np
from .base import Modem


# IFKP parameters from ifkp.h
IFKP_FFTSIZE = 4096
IFKP_SYMLEN = 4096
IFKP_SPACING = 3  # Tone spacing in bins
IFKP_OFFSET = 1  # Offset added to symbols
IFKP_NUMBINS = 151
IFKP_SR = 16000  # Sample rate


# IFKP Varicode table - maps ASCII characters to [symbol1, symbol2]
# If symbol2 == 0, it's a single-symbol character
# Reference: fldigi/src/ifkp/ifkp_varicode.cxx
IFKP_VARICODE = [
    [0, 0],
    [0, 0],
    [0, 0],
    [0, 0],
    [0, 0],
    [0, 0],
    [0, 0],
    [0, 0],
    [27, 31],
    [0, 0],
    [28, 30],
    [0, 0],
    [0, 0],
    [0, 0],
    [0, 0],
    [0, 0],
    [0, 0],
    [0, 0],
    [0, 0],
    [0, 0],
    [0, 0],
    [0, 0],
    [0, 0],
    [0, 0],
    [0, 0],
    [0, 0],
    [0, 0],
    [0, 0],
    [0, 0],
    [0, 0],
    [0, 0],
    [0, 0],
    [28, 0],
    [11, 30],
    [12, 30],
    [13, 30],
    [14, 30],
    [15, 30],
    [16, 30],
    [17, 30],  # ' '!-'
    [18, 30],
    [19, 30],
    [20, 30],
    [21, 30],
    [27, 29],
    [22, 30],
    [27, 0],
    [23, 30],
    [10, 30],
    [1, 30],
    [2, 30],
    [3, 30],
    [4, 30],
    [5, 30],
    [6, 30],
    [7, 30],  # 0 - 7
    [8, 30],
    [9, 30],
    [24, 30],
    [25, 30],
    [26, 30],
    [0, 31],
    [27, 30],
    [28, 29],  # 8, 9
    [0, 29],
    [1, 29],
    [2, 29],
    [3, 29],
    [4, 29],
    [5, 29],
    [6, 29],
    [7, 29],
    [8, 29],
    [9, 29],
    [10, 29],
    [11, 29],
    [12, 29],
    [13, 29],
    [14, 29],
    [15, 29],
    [16, 29],
    [17, 29],
    [18, 29],
    [19, 29],
    [20, 29],
    [21, 29],
    [22, 29],
    [23, 29],  # ... :
    [24, 29],
    [25, 29],
    [26, 29],
    [1, 31],
    [2, 31],
    [3, 31],
    [4, 31],
    [5, 31],
    [9, 31],
    [1, 0],
    [2, 0],
    [3, 0],
    [4, 0],
    [5, 0],
    [6, 0],
    [7, 0],  # @ - g
    [8, 0],
    [9, 0],
    [10, 0],
    [11, 0],
    [12, 0],
    [13, 0],
    [14, 0],
    [15, 0],  # h - o
    [16, 0],
    [17, 0],
    [18, 0],
    [19, 0],
    [20, 0],
    [21, 0],
    [22, 0],
    [23, 0],  # p - w
    [24, 0],
    [25, 0],
    [26, 0],
    [6, 31],
    [7, 31],
    [8, 31],
    [0, 30],
    [28, 31],  # x - 127
    [0, 0],
    [0, 0],
    [0, 0],
    [0, 0],
    [0, 0],
    [0, 0],
    [0, 0],
    [0, 0],  # 135
    [0, 0],
    [0, 0],
    [0, 0],
    [0, 0],
    [0, 0],
    [0, 0],
    [0, 0],
    [0, 0],  # 143
    [0, 0],
    [0, 0],
    [0, 0],
    [0, 0],
    [0, 0],
    [0, 0],
    [0, 0],
    [0, 0],  # 151
    [0, 0],
    [0, 0],
    [0, 0],
    [0, 0],
    [0, 0],
    [0, 0],
    [0, 0],
    [0, 0],  # 159
    [0, 0],
    [0, 0],
    [0, 0],
    [14, 31],
    [0, 0],
    [0, 0],
    [0, 0],
    [0, 0],  # 167
    [0, 0],
    [0, 0],
    [0, 0],
    [0, 0],
    [0, 0],
    [0, 0],
    [0, 0],
    [0, 0],  # 175
    [12, 31],
    [10, 31],
    [0, 0],
    [0, 0],
    [0, 0],
    [0, 0],
    [0, 0],
    [0, 0],  # 183
    [0, 0],
    [0, 0],
    [0, 0],
    [0, 0],
    [0, 0],
    [0, 0],
    [0, 0],
    [0, 0],  # 191
    [0, 0],
    [0, 0],
    [0, 0],
    [0, 0],
    [0, 0],
    [0, 0],
    [0, 0],
    [0, 0],  # 199
    [0, 0],
    [0, 0],
    [0, 0],
    [0, 0],
    [0, 0],
    [0, 0],
    [0, 0],
    [0, 0],  # 207
    [0, 0],
    [0, 0],
    [0, 0],
    [0, 0],
    [0, 0],
    [0, 0],
    [0, 0],
    [13, 31],  # 215
    [0, 0],
    [0, 0],
    [0, 0],
    [0, 0],
    [0, 0],
    [0, 0],
    [0, 0],
    [0, 0],  # 223
    [0, 0],
    [0, 0],
    [0, 0],
    [0, 0],
    [0, 0],
    [0, 0],
    [0, 0],
    [0, 0],  # 231
    [0, 0],
    [0, 0],
    [0, 0],
    [0, 0],
    [0, 0],
    [0, 0],
    [0, 0],
    [0, 0],  # 239
    [0, 0],
    [0, 0],
    [0, 0],
    [0, 0],
    [0, 0],
    [0, 0],
    [0, 0],
    [11, 31],  # 247
    [12, 31],
    [0, 0],
    [0, 0],
    [0, 0],
    [0, 0],
    [0, 0],
    [0, 0],
    [0, 0],  # 255
]


class IFKP(Modem):
    """
    IFKP (Incremental Frequency Keying Plus) Modem.

    IFKP is an MFSK mode with 33 tones and incremental frequency keying.
    It uses a varicode alphabet optimized for ham radio communications.

    Specifications:
        Sample rate: 16000 Hz
        Symbol length: 4096 samples
        Tone spacing: 3 bins
        Number of tones: 33 (for 32 differences)
        Bandwidth: ~386 Hz
        Baud rate: ~3.9 baud (varies by baud_rate setting)

    Supports three baud rates:
        - IFKP-0.5: 2.0x symbol length (slower)
        - IFKP-1.0: 1.0x symbol length (standard)
        - IFKP-2.0: 0.5x symbol length (faster)

    Reference: fldigi/src/ifkp/ifkp.cxx
    """

    def __init__(self, frequency: float = 1500, baud_rate: float = 1.0):
        """
        Initialize IFKP modem.

        Args:
            frequency: Center frequency in Hz (default: 1500)
            baud_rate: Baud rate multiplier - 0.5, 1.0, or 2.0 (default: 1.0)

        Reference:
            fldigi/src/ifkp/ifkp.cxx lines 114-177
        """
        super().__init__(mode_name=f"IFKP-{baud_rate}", sample_rate=IFKP_SR, frequency=frequency)

        self.symlen = IFKP_SYMLEN
        self.baud_rate = baud_rate

        # Calculate basetone (center frequency bin)
        # basetone = ceil((frequency - bandwidth / 2.0) * symlen / samplerate)
        # From ifkp.cxx line 272
        self._bandwidth = 33 * IFKP_SPACING * self.sample_rate / self.symlen
        self.basetone = int(
            np.ceil((frequency - self._bandwidth / 2.0) * self.symlen / self.sample_rate)
        )

        # TX state
        self.tone = 0
        self.prevtone = 0
        self.txphase = 0.0
        self.send_bot = True  # Send beginning-of-transmission preamble

    def tx_init(self) -> None:
        """
        Initialize the transmitter.

        Reference:
            fldigi/src/ifkp/ifkp.cxx lines 196-205
        """
        self.tone = 0
        self.prevtone = 0
        self.txphase = 0.0
        self.send_bot = True
        self._tx_initialized = True

    def _send_tone(self, tone: int) -> np.ndarray:
        """
        Generate audio samples for a single tone.

        Args:
            tone: Tone number (0-32)

        Returns:
            Array of audio samples

        Reference:
            fldigi/src/ifkp/ifkp.cxx lines 687-709
        """
        # Calculate the actual frequency for this tone
        # frequency = (basetone + tone * IFKP_SPACING) * samplerate / symlen
        frequency = (self.basetone + tone * IFKP_SPACING) * self.sample_rate / self.symlen

        phaseincr = 2.0 * np.pi * frequency / self.sample_rate

        # Symbol length varies by baud rate
        # 0.5 -> 2.0x, 1.0 -> 1.0x, 2.0 -> 0.5x
        if self.baud_rate == 0.5:
            send_symlen = int(self.symlen * 2.0)
        elif self.baud_rate == 2.0:
            send_symlen = int(self.symlen * 0.5)
        else:  # 1.0
            send_symlen = self.symlen

        outbuf = np.zeros(send_symlen, dtype=np.float64)

        for i in range(send_symlen):
            outbuf[i] = np.cos(self.txphase)
            self.txphase -= phaseincr
            if self.txphase < 0:
                self.txphase += 2.0 * np.pi

        self.prevtone = tone
        return outbuf

    def _send_symbol(self, sym: int) -> np.ndarray:
        """
        Send a symbol using incremental frequency keying.

        Args:
            sym: Symbol value (0-32)

        Returns:
            Array of audio samples

        Reference:
            fldigi/src/ifkp/ifkp.cxx lines 711-715
        """
        # Incremental frequency keying: add symbol to previous tone with offset
        self.tone = (self.prevtone + sym + IFKP_OFFSET) % 33
        return self._send_tone(self.tone)

    def _send_idle(self) -> np.ndarray:
        """
        Send an idle symbol (symbol 0).

        Returns:
            Array of audio samples

        Reference:
            fldigi/src/ifkp/ifkp.cxx lines 717-720
        """
        return self._send_symbol(0)

    def _send_char(self, ch: int) -> np.ndarray:
        """
        Send a character using varicode encoding.

        Args:
            ch: ASCII character code

        Returns:
            Array of audio samples (concatenated symbols)

        Reference:
            fldigi/src/ifkp/ifkp.cxx lines 722-733
        """
        if ch <= 0:
            return self._send_idle()

        # Ensure character is in valid range
        if ch >= len(IFKP_VARICODE):
            return self._send_idle()

        sym1, sym2 = IFKP_VARICODE[ch]

        # Send first symbol
        samples = self._send_symbol(sym1)

        # Send second symbol if needed (sym2 > 28)
        if sym2 > 28:
            samples = np.concatenate([samples, self._send_symbol(sym2)])

        return samples

    def tx_process(self, text: str) -> np.ndarray:
        """
        Process text and generate modulated audio samples.

        Args:
            text: Text string to transmit

        Returns:
            Array of audio samples

        Reference:
            fldigi/src/ifkp/ifkp.cxx lines 1056-1104
        """
        if not self._tx_initialized:
            self.tx_init()

        all_samples = []

        # Send preamble (two idle symbols) at beginning of transmission
        # Reference: ifkp.cxx lines 1060-1064
        if self.send_bot:
            self.send_bot = False
            all_samples.append(self._send_char(0))
            all_samples.append(self._send_char(0))

        # Send each character
        for ch in text:
            samples = self._send_char(ord(ch))
            all_samples.append(samples)

        # Send postamble (one idle symbol)
        # Reference: ifkp.cxx line 1096
        all_samples.append(self._send_char(0))

        # Concatenate all samples
        if all_samples:
            return np.concatenate(all_samples)
        else:
            return np.array([], dtype=np.float64)


def create_ifkp_modem(frequency: float = 1500, baud_rate: float = 1.0) -> IFKP:
    """
    Create an IFKP modem instance.

    Args:
        frequency: Center frequency in Hz (default: 1500)
        baud_rate: Baud rate multiplier - 0.5, 1.0, or 2.0 (default: 1.0)
            0.5 -> IFKP-0.5 (slowest, most robust)
            1.0 -> IFKP-1.0 (standard)
            2.0 -> IFKP-2.0 (fastest)

    Returns:
        IFKP modem instance
    """
    return IFKP(frequency=frequency, baud_rate=baud_rate)
