"""DominoEX modem implementation.

DominoEX is an Incremental Frequency Keying (IFK) mode that uses relative tone shifts
to encode data. Each symbol shifts the current tone by a fixed amount, making it
exceptionally robust to frequency drift and multi-path propagation.

Unlike traditional FSK where each symbol represents an absolute frequency, DominoEX
uses differential encoding where each symbol represents a frequency shift from the
previous symbol. This eliminates the need for precise frequency calibration and makes
the mode highly resistant to Doppler shift and propagation effects.

Key Features:
    - 18 tones with incremental frequency keying (IFK)
    - Variable-length varicode (1-3 nibbles per character)
    - Multiple speed variants (Micro, 4, 5, 8, 11, 16, 22, 44, 88 baud)
    - Excellent weak-signal and multi-path performance
    - No absolute frequency reference needed
    - Resistant to frequency drift and Doppler shift

Common Modes:
    - DominoEX Micro: ~2 baud (ultra-slow, extreme weak signal)
    - DominoEX 4: ~3.9 baud (very slow, weak signal)
    - DominoEX 8: ~7.8 baud (moderate speed)
    - DominoEX 11: ~10.8 baud (good balance)
    - DominoEX 16: ~15.6 baud (faster, still robust)
    - DominoEX 22: ~21.5 baud (fast mode)

Example:
    Generate DominoEX 11 signal::

        from pydigi.modems.dominoex import DominoEX_11
        from pydigi.utils.audio import save_wav

        modem = DominoEX_11()
        audio = modem.modulate("CQ CQ DE W1ABC")
        save_wav("dominoex11_test.wav", audio, 8000)

Note:
    Tone calculation uses IFK formula:
        tone = (prev_tone + 2 + symbol) % 18
    This creates a differential encoding that is self-correcting.

Reference:
    - fldigi/src/dominoex/dominoex.cxx
    - fldigi/src/dominoex/dominovar.cxx
    - fldigi/src/include/dominoex.h

Attributes:
    NUMTONES (int): Number of tones (18)
    BASEFREQ (float): Base frequency offset in Hz (1000.0)
"""

import numpy as np
from ..core.oscillator import NCO
from ..varicode import dominoex_varicode
from .base import Modem


# DominoEX constants from fldigi
NUMTONES = 18  # Number of tones in DominoEX
BASEFREQ = 1000.0  # Base frequency offset (unused in our implementation, we use 'frequency' parameter instead)


class DominoEX(Modem):
    """
    DominoEX modem implementation.

    DominoEX uses Incremental Frequency Keying (IFK) where each symbol represents
    a relative tone shift from the previous tone, not an absolute frequency.
    This makes it very robust to frequency drift and multi-path propagation.

    Tone calculation:
        tone = (prev_tone + 2 + symbol) % NUMTONES
        freq = (tone + 0.5) * tone_spacing + center_freq - bandwidth/2

    Symbol encoding:
        - Uses DominoEX varicode (1-3 nibbles per character)
        - Each nibble is a 4-bit symbol (0-15, but only 0-15 within NUMTONES constraints)
        - Continuation nibbles have MSB set (value >= 8)

    Args:
        symlen: Symbol length in samples
        doublespaced: Tone spacing multiplier (1 or 2)
        sample_rate: Sample rate in Hz (8000 or 11025)
        fec: Enable FEC mode (not yet implemented)

    Example:
        >>> modem = DominoEX(symlen=1024, doublespaced=2, sample_rate=8000)
        >>> audio = modem.modulate("CQ CQ CQ", frequency=1500, sample_rate=8000)
    """

    def __init__(self, symlen: int = 1024, doublespaced: int = 2, sample_rate: int = 8000,
                 frequency: float = 1500.0, tx_amplitude: float = 0.8,
                 fec: bool = False, mode_micro: bool = False, mode_name: str = "DominoEX"):
        """
        Initialize DominoEX modem with specified parameters.

        Args:
            symlen: Symbol length in samples (determines baud rate)
            doublespaced: Tone spacing multiplier (1 = normal, 2 = double spacing)
            sample_rate: Audio sample rate (8000 or 11025 Hz, default: 8000)
            frequency: Center frequency in Hz (default: 1500)
            tx_amplitude: Transmit amplitude 0.0-1.0 (default: 0.8)
            fec: Enable FEC mode (not yet implemented in TX, default: False)
            mode_micro: True for DominoEX Micro mode (default: False)
            mode_name: Name of the mode (for display purposes, default: "DominoEX")
        """
        super().__init__(mode_name=mode_name, sample_rate=sample_rate, frequency=frequency)
        self.symlen = symlen
        self.doublespaced = doublespaced
        self.tx_amplitude = tx_amplitude
        self.fec = fec  # FEC not yet implemented
        self.mode_micro = mode_micro

        # Calculate tone spacing and bandwidth
        self.tonespacing = (sample_rate * doublespaced) / symlen
        self._bandwidth = NUMTONES * self.tonespacing

        # TX state
        self.txphase = 0.0
        self.txprevtone = 0

    def tx_init(self) -> None:
        """Initialize transmitter state."""
        self.txphase = 0.0
        self.txprevtone = 0

    def tx_process(self, text: str) -> np.ndarray:
        """
        Process text and generate DominoEX signal.

        Args:
            text: Text to transmit

        Returns:
            numpy array of audio samples normalized to [-1.0, 1.0]
        """
        audio = []

        # Send preamble
        audio.append(self._send_preamble(self.frequency, self.mode_micro))

        # Send data
        for char in text:
            audio.append(self._send_char(char, False, self.frequency))

        # Send postamble
        audio.append(self._send_postamble(self.frequency, self.mode_micro))

        # Concatenate all audio
        signal = np.concatenate(audio) if audio else np.array([], dtype=np.float32)

        # Apply amplitude scaling
        signal = signal * self.tx_amplitude

        # Normalize to [-1.0, 1.0]
        max_val = np.max(np.abs(signal))
        if max_val > 1.0:
            signal = signal / max_val

        return signal.astype(np.float32)

    def _send_tone(self, tone, duration, frequency):
        """
        Generate audio for a specific tone.

        Args:
            tone: Tone index (0-17)
            duration: Number of symbols to send
            frequency: Center frequency in Hz

        Returns:
            numpy array of audio samples
        """
        # Calculate tone frequency
        # f = (tone + 0.5) * tonespacing + frequency - bandwidth / 2.0
        f = (tone + 0.5) * self.tonespacing + frequency - self._bandwidth / 2.0

        # Generate audio samples
        samples = []
        phaseincr = 2.0 * np.pi * f / self.sample_rate

        for _ in range(duration):
            for _ in range(self.symlen):
                samples.append(np.cos(self.txphase))
                self.txphase -= phaseincr
                if self.txphase < 0:
                    self.txphase += 2.0 * np.pi

        return np.array(samples, dtype=np.float32)

    def _send_symbol(self, sym, frequency):
        """
        Send a single symbol using IFK (Incremental Frequency Keying).

        The tone is calculated relative to the previous tone:
        tone = (prev_tone + 2 + symbol) % NUMTONES

        Args:
            sym: Symbol value (0-15, a 4-bit nibble)
            frequency: Center frequency in Hz

        Returns:
            numpy array of audio samples for this symbol
        """
        # IFK: each symbol is relative to the previous tone
        tone = (self.txprevtone + 2 + sym) % NUMTONES
        self.txprevtone = tone

        return self._send_tone(tone, 1, frequency)

    def _send_char(self, c, secondary, frequency):
        """
        Send a single character using varicode encoding.

        Args:
            c: Character to send (int ASCII value or single-char string)
            secondary: True if secondary channel
            frequency: Center frequency in Hz

        Returns:
            numpy array of audio samples
        """
        if isinstance(c, str):
            c = ord(c[0])

        # Get varicode for this character
        code = dominoex_varicode.encode_char(c, secondary)

        # Send each nibble as a symbol
        audio = []
        for nibble in code:
            audio.append(self._send_symbol(nibble, frequency))

        return np.concatenate(audio) if audio else np.array([], dtype=np.float32)

    def _send_idle(self, frequency):
        """
        Send an idle character (NUL on secondary channel).

        Args:
            frequency: Center frequency in Hz

        Returns:
            numpy array of audio samples
        """
        return self._send_char(0, True, frequency)  # NUL on secondary channel

    def _send_preamble(self, frequency, mode_micro=False):
        """
        Send preamble sequence.

        Preamble:
        - 1 idle character (NUL on secondary)
        - CR + STX + CR (for non-Micro modes)

        Args:
            frequency: Center frequency in Hz
            mode_micro: True if DominoEX Micro mode (skips STX)

        Returns:
            numpy array of audio samples
        """
        audio = []

        # Send idle character
        audio.append(self._send_idle(frequency))

        # Send CR
        audio.append(self._send_char(ord('\r'), False, frequency))

        if not mode_micro:
            # Send STX (0x02)
            audio.append(self._send_char(2, False, frequency))
            # Send CR
            audio.append(self._send_char(ord('\r'), False, frequency))

        return np.concatenate(audio) if audio else np.array([], dtype=np.float32)

    def _send_postamble(self, frequency, mode_micro=False):
        """
        Send postamble sequence.

        Postamble:
        - CR + EOT + CR (for non-Micro modes)
        - 4 idle characters to flush varicode decoder

        Args:
            frequency: Center frequency in Hz
            mode_micro: True if DominoEX Micro mode (skips EOT)

        Returns:
            numpy array of audio samples
        """
        audio = []

        # Send CR
        audio.append(self._send_char(ord('\r'), False, frequency))

        if not mode_micro:
            # Send EOT (0x04)
            audio.append(self._send_char(4, False, frequency))
            # Send CR
            audio.append(self._send_char(ord('\r'), False, frequency))

        # Flush varicode decoder with 4 idle characters
        for _ in range(4):
            audio.append(self._send_idle(frequency))

        return np.concatenate(audio) if audio else np.array([], dtype=np.float32)

    def modulate(self, text: str, frequency: float = None,
                 sample_rate: float = None, mode_micro: bool = None) -> np.ndarray:
        """
        Modulate text into DominoEX audio signal.

        Args:
            text: Text string to transmit
            frequency: Center frequency in Hz (default: use instance value)
            sample_rate: Audio sample rate in Hz (default: use instance value)
            mode_micro: True if DominoEX Micro mode (default: use instance value)

        Returns:
            numpy array of float32 audio samples in range [-1.0, 1.0]

        Example:
            >>> modem = DominoEX(symlen=1024, doublespaced=2, sample_rate=8000)
            >>> audio = modem.modulate("HELLO WORLD", frequency=1500)
            >>> from pydigi.utils.audio import save_wav
            >>> save_wav("dominoex8.wav", audio, 8000)
        """
        # Store original mode_micro value
        original_mode_micro = self.mode_micro

        # Apply override if provided
        if mode_micro is not None:
            self.mode_micro = mode_micro

        # Call base class modulate (handles frequency and sample_rate overrides)
        signal = super().modulate(text, frequency, sample_rate)

        # Restore original value
        self.mode_micro = original_mode_micro

        return signal

    def estimate_duration(self, text: str, mode_micro: bool = False) -> float:
        """
        Estimate transmission duration in seconds.

        Args:
            text: Text to transmit
            mode_micro: True if DominoEX Micro mode

        Returns:
            Estimated duration in seconds
        """
        # Count nibbles for preamble
        preamble_nibbles = len(dominoex_varicode.encode_char(0, True))  # idle
        preamble_nibbles += len(dominoex_varicode.encode_char(ord('\r'), False))  # CR

        if not mode_micro:
            preamble_nibbles += len(dominoex_varicode.encode_char(2, False))  # STX
            preamble_nibbles += len(dominoex_varicode.encode_char(ord('\r'), False))  # CR

        # Count nibbles for data
        data_nibbles = len(dominoex_varicode.encode(text, False))

        # Count nibbles for postamble
        postamble_nibbles = len(dominoex_varicode.encode_char(ord('\r'), False))  # CR

        if not mode_micro:
            postamble_nibbles += len(dominoex_varicode.encode_char(4, False))  # EOT
            postamble_nibbles += len(dominoex_varicode.encode_char(ord('\r'), False))  # CR

        # 4 idle characters for flush
        postamble_nibbles += 4 * len(dominoex_varicode.encode_char(0, True))

        # Total symbols
        total_symbols = preamble_nibbles + data_nibbles + postamble_nibbles

        # Calculate duration
        symbol_rate = self.sample_rate / self.symlen  # symbols per second
        duration = total_symbols / symbol_rate

        return duration


#
# Convenience functions for standard DominoEX modes
#

def DominoEX_Micro(text, frequency=1500.0, sample_rate=8000):
    """DominoEX Micro - Ultra-slow weak signal mode (2.0 baud)."""
    modem = DominoEX(symlen=4000, doublespaced=1, sample_rate=8000)
    return modem.modulate(text, frequency, sample_rate, mode_micro=True)


def DominoEX_4(text, frequency=1500.0, sample_rate=8000):
    """DominoEX 4 - Very slow mode (3.90625 baud)."""
    modem = DominoEX(symlen=2048, doublespaced=2, sample_rate=8000)
    return modem.modulate(text, frequency, sample_rate)


def DominoEX_5(text, frequency=1500.0, sample_rate=11025):
    """DominoEX 5 - Slow mode (5.3833 baud)."""
    modem = DominoEX(symlen=2048, doublespaced=2, sample_rate=11025)
    return modem.modulate(text, frequency, sample_rate)


def DominoEX_8(text, frequency=1500.0, sample_rate=8000):
    """DominoEX 8 - Standard slow mode (7.8125 baud)."""
    modem = DominoEX(symlen=1024, doublespaced=2, sample_rate=8000)
    return modem.modulate(text, frequency, sample_rate)


def DominoEX_11(text, frequency=1500.0, sample_rate=11025):
    """DominoEX 11 - Medium-slow mode (10.766 baud)."""
    modem = DominoEX(symlen=1024, doublespaced=1, sample_rate=11025)
    return modem.modulate(text, frequency, sample_rate)


def DominoEX_16(text, frequency=1500.0, sample_rate=8000):
    """DominoEX 16 - Standard mode (15.625 baud)."""
    modem = DominoEX(symlen=512, doublespaced=1, sample_rate=8000)
    return modem.modulate(text, frequency, sample_rate)


def DominoEX_22(text, frequency=1500.0, sample_rate=11025):
    """DominoEX 22 - Medium-fast mode (21.533 baud)."""
    modem = DominoEX(symlen=512, doublespaced=1, sample_rate=11025)
    return modem.modulate(text, frequency, sample_rate)


def DominoEX_44(text, frequency=1500.0, sample_rate=11025):
    """DominoEX 44 - Fast mode (43.066 baud, experimental)."""
    modem = DominoEX(symlen=256, doublespaced=2, sample_rate=11025)
    return modem.modulate(text, frequency, sample_rate)


def DominoEX_88(text, frequency=1500.0, sample_rate=11025):
    """DominoEX 88 - Very fast mode (86.132 baud, experimental)."""
    modem = DominoEX(symlen=128, doublespaced=1, sample_rate=11025)
    return modem.modulate(text, frequency, sample_rate)
