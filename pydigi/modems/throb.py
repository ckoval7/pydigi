"""Throb modem implementation.

Throb is a dual-tone amplitude-modulated digital mode where each character
is represented by two simultaneous tones. The mode is highly resistant to
propagation-induced phase shifts and requires no carrier tracking.

The Throb family includes six modes with varying speed and robustness:
    - Throb1, Throb2, Throb4 (9 tones, 45 characters)
    - ThrobX1, ThrobX2, ThrobX4 (11 tones, 55 characters)

Key Features:
    - Dual-tone modulation (two simultaneous tones per symbol)
    - Amplitude modulation with pulse shaping
    - Fixed 8000 Hz sample rate
    - Symbol lengths: 8192 (mode 1), 4096 (mode 2), 2048 (mode 4) samples
    - Baud rates: ~1 baud (mode 1), ~2 baud (mode 2), ~4 baud (mode 4)

Mode Details:
    - Throb: 9 tones, 45 characters, shift codes for special chars
    - ThrobX: 11 tones, 55 characters, no shift codes
    - Modes 1 & 2: Semi-pulse shaping (20% rise, 60% flat, 20% fall)
    - Mode 4: Full-pulse shaping (full cosine wave)

Example:
    Generate Throb1 signal::

        from pydigi.modems.throb import Throb1
        from pydigi.utils.audio import save_wav

        modem = Throb1()
        audio = modem.modulate("CQ CQ DE W1ABC")
        save_wav("throb1_test.wav", audio, 8000)

Reference:
    fldigi/src/throb/throb.cxx
"""

import numpy as np
from ..modems.base import Modem
from ..varicode.throb_varicode import (
    encode_throb,
    encode_throbx,
    get_tone_pair,
    THROB_CHARSET,
    THROBX_CHARSET
)


class Throb(Modem):
    """
    Throb modem implementation.

    Generates dual-tone amplitude-modulated signals for Throb and ThrobX modes.

    Reference: fldigi/src/throb/throb.cxx
    """

    # Tone frequencies relative to center frequency (Hz)
    # Reference: throb.cxx lines 941-944
    THROB_TONE_FREQS_NAR = np.array([-32, -24, -16, -8, 0, 8, 16, 24, 32])
    THROB_TONE_FREQS_WID = np.array([-64, -48, -32, -16, 0, 16, 32, 48, 64])
    THROBX_TONE_FREQS_NAR = np.array([-39.0625, -31.25, -23.4375, -15.625, -7.8125,
                                       0, 7.8125, 15.625, 23.4375, 31.25, 39.0625])
    THROBX_TONE_FREQS_WID = np.array([-78.125, -62.5, -46.875, -31.25, -15.625,
                                       0, 15.625, 31.25, 46.875, 62.5, 78.125])

    # Symbol lengths (samples at 8000 Hz)
    # Reference: throb.h lines 42-44
    SYMLEN_1 = 8192   # ~1.024 seconds per symbol (~1 baud)
    SYMLEN_2 = 4096   # ~0.512 seconds per symbol (~2 baud)
    SYMLEN_4 = 2048   # ~0.256 seconds per symbol (~4 baud)

    # Sample rate (fixed for Throb)
    # Reference: throb.h line 34
    THROB_SAMPLE_RATE = 8000

    def __init__(self, mode: str = 'throb1', symlen: int = None, tone_freqs: np.ndarray = None, num_tones: int = 9,
                 num_chars: int = 45, is_throbx: bool = False, use_full_pulse: bool = False,
                 sample_rate: int = 8000, frequency: float = 1500, tx_amplitude: float = 0.8):
        """
        Initialize Throb modem.

        Args:
            mode: Mode name ('throb1', 'throb2', 'throb4', 'throbx1', 'throbx2', 'throbx4')
            symlen: Symbol length in samples (overrides mode default)
            tone_freqs: Array of tone frequencies in Hz (overrides mode default)
            num_tones: Number of tones (9 for Throb, 11 for ThrobX)
            num_chars: Number of characters (45 for Throb, 55 for ThrobX)
            is_throbx: True for ThrobX modes
            use_full_pulse: True to use full-pulse shaping (mode 4 style)
            sample_rate: Sample rate in Hz (default: 8000, fixed for Throb)
            frequency: Center frequency in Hz (default: 1500)
            tx_amplitude: Transmit amplitude 0.0-1.0 (default: 0.8)

        Reference: fldigi/src/throb/throb.cxx constructor lines 132-256
        """
        super().__init__(mode_name=mode, sample_rate=sample_rate, frequency=frequency)

        self.mode_name = mode.lower()
        self.is_throbx = is_throbx
        self.num_tones = num_tones
        self.num_chars = num_chars
        self.use_full_pulse = use_full_pulse
        self.tx_amplitude = tx_amplitude

        # Warn if sample rate is not 8000 Hz
        if sample_rate != self.THROB_SAMPLE_RATE:
            print(f"Warning: Throb requires {self.THROB_SAMPLE_RATE} Hz sample rate. "
                  f"Overriding to {self.THROB_SAMPLE_RATE} Hz.")
            self.sample_rate = self.THROB_SAMPLE_RATE

        # Set symbol length
        if symlen is not None:
            self.symlen = symlen
        else:
            self.symlen = self._get_default_symlen()

        # Set tone frequencies
        if tone_freqs is not None:
            self.tone_freqs = np.array(tone_freqs)
        else:
            self.tone_freqs = self._get_default_tone_freqs()

        # Idle and space symbols
        # Reference: throb.cxx lines 102-129
        if is_throbx:
            self.idlesym = 0      # Initially
            self.spacesym = 1     # Initially
            self.idle_alternates = True  # ThrobX alternates idle/space
        else:
            self.idlesym = 0
            self.spacesym = 44
            self.idle_alternates = False

        # Generate pulse shape for this mode
        self.txpulse = self._make_pulse_shape()

        # Preamble length (number of idle symbols)
        # Reference: throb.cxx line 49
        self.preamble_symbols = 4

    def _get_default_symlen(self):
        """Get default symbol length based on mode."""
        if '1' in self.mode_name:
            return self.SYMLEN_1
        elif '2' in self.mode_name:
            return self.SYMLEN_2
        elif '4' in self.mode_name:
            return self.SYMLEN_4
        else:
            return self.SYMLEN_4  # Default

    def _get_default_tone_freqs(self):
        """Get default tone frequencies based on mode."""
        if self.is_throbx:
            if '4' in self.mode_name:
                return self.THROBX_TONE_FREQS_WID
            else:
                return self.THROBX_TONE_FREQS_NAR
        else:
            if '4' in self.mode_name:
                return self.THROB_TONE_FREQS_WID
            else:
                return self.THROB_TONE_FREQS_NAR

    def _make_semi_pulse(self, length):
        """
        Generate semi-pulse shape (20% rise, 60% flat, 20% fall).

        Reference: fldigi/src/throb/throb.cxx mk_semi_pulse() lines 542-566
        """
        pulse = np.zeros(length)

        # Rising edge (0% to 20%)
        rise_len = length // 5
        for i in range(rise_len):
            x = np.pi * i / rise_len
            pulse[i] = 0.5 * (1 - np.cos(x))

        # Flat portion (20% to 80%)
        pulse[rise_len:length * 4 // 5] = 1.0

        # Falling edge (80% to 100%)
        fall_start = length * 4 // 5
        fall_len = length - fall_start
        for i in range(fall_len):
            x = np.pi * i / fall_len
            pulse[fall_start + i] = 0.5 * (1 + np.cos(x))

        return pulse

    def _make_full_pulse(self, length):
        """
        Generate full-pulse shape (full cosine wave).

        Reference: fldigi/src/throb/throb.cxx mk_full_pulse() lines 568-579
        """
        pulse = np.zeros(length)

        for i in range(length):
            pulse[i] = 0.5 * (1 - np.cos(2 * np.pi * i / length))

        return pulse

    def _make_pulse_shape(self):
        """Generate pulse shape based on mode settings."""
        if self.use_full_pulse or '4' in self.mode_name:
            return self._make_full_pulse(self.symlen)
        else:
            return self._make_semi_pulse(self.symlen)

    def _flip_syms(self):
        """
        Flip idle and space symbols (ThrobX only).

        In ThrobX, idle and space symbols alternate to help with synchronization.

        Reference: fldigi/src/throb/throb.cxx flip_syms() lines 96-114
        """
        if self.is_throbx:
            if self.idlesym == 0:
                self.idlesym = 1
                self.spacesym = 0
            else:
                self.idlesym = 0
                self.spacesym = 1

    def _send_symbol(self, symbol):
        """
        Generate dual-tone symbol.

        Args:
            symbol: Symbol index (0 to num_chars-1)

        Returns:
            Array of audio samples for this symbol

        Reference: fldigi/src/throb/throb.cxx send() lines 582-617
        """
        # Get tone pair for this symbol
        tone1, tone2 = get_tone_pair(symbol, self.is_throbx)

        # Calculate actual frequencies
        freq1 = self.frequency + self.tone_freqs[tone1]
        freq2 = self.frequency + self.tone_freqs[tone2]

        # Generate phase increments
        w1 = 2.0 * np.pi * freq1 / self.sample_rate
        w2 = 2.0 * np.pi * freq2 / self.sample_rate

        # Generate time indices
        t = np.arange(self.symlen)

        # Generate dual-tone signal with pulse shaping
        # Reference: throb.cxx lines 612-614
        outbuf = self.txpulse * (np.sin(w1 * t) + np.sin(w2 * t)) / 2.0

        return outbuf

    def tx_init(self):
        """
        Initialize transmitter.

        Reference: fldigi/src/throb/throb.cxx tx_init() lines 47-52
        """
        pass

    def tx_process(self, text: str) -> np.ndarray:
        """
        Process text and generate Throb signal.

        Args:
            text: Text string to transmit

        Returns:
            Array of audio samples normalized to [-1.0, 1.0]

        Reference: fldigi/src/throb/throb.cxx tx_process() lines 619-721
        """
        # Encode text to symbols
        if self.is_throbx:
            symbols = encode_throbx(text)
        else:
            symbols = encode_throb(text)

        # Initialize output buffer
        output = []

        # Send preamble (idle symbols)
        # Reference: throb.cxx lines 625-630
        for _ in range(self.preamble_symbols):
            symbol_audio = self._send_symbol(self.idlesym)
            output.append(symbol_audio)
            self._flip_syms()

        # Send data symbols
        for symbol in symbols:
            # Handle space symbols (need to flip for ThrobX)
            # Reference: throb.cxx lines 712-715
            if symbol == self.spacesym:
                symbol_audio = self._send_symbol(symbol)
                output.append(symbol_audio)
                self._flip_syms()
            else:
                symbol_audio = self._send_symbol(symbol)
                output.append(symbol_audio)

        # Send postamble (one idle symbol)
        # Reference: throb.cxx lines 635-639
        symbol_audio = self._send_symbol(self.idlesym)
        output.append(symbol_audio)

        # Concatenate all symbols
        signal = np.concatenate(output)

        # Apply amplitude scaling
        signal = signal * self.tx_amplitude

        # Normalize to [-1.0, 1.0]
        max_val = np.max(np.abs(signal))
        if max_val > 1.0:
            signal = signal / max_val

        return signal.astype(np.float32)

    def estimate_duration(self, text: str) -> float:
        """Estimate transmission duration in seconds.

        Calculates the approximate time required to transmit the given text,
        including preamble, data, and postamble.

        Args:
            text: Text to transmit

        Returns:
            float: Estimated duration in seconds

        Example:
            >>> modem = Throb1()
            >>> duration = modem.estimate_duration("HELLO")
            >>> print(f"Transmission will take {duration:.1f} seconds")
        """
        # Encode text to get symbol count
        if self.is_throbx:
            symbols = encode_throbx(text)
        else:
            symbols = encode_throb(text)

        # Total symbols = preamble + data + postamble
        total_symbols = self.preamble_symbols + len(symbols) + 1

        # Duration = symbols * symbol_length / sample_rate
        duration = total_symbols * self.symlen / self.THROB_SAMPLE_RATE

        return duration


# Convenience functions for each Throb mode
# Reference: fldigi/src/throb/throb.cxx constructor lines 141-219

def Throb1() -> 'Throb':
    """Create Throb1 modem instance.

    Throb1 is the slowest Throb mode, optimized for weak signal conditions.

    Mode Parameters:
        - Symbol length: 8192 samples (~1.024 seconds)
        - Baud rate: ~1 baud
        - Tone spacing: 8 Hz
        - Bandwidth: 64 Hz (approx)
        - Pulse shaping: Semi-pulse
        - Character set: 45 characters (9 tones)

    Returns:
        Throb: Configured Throb1 modem instance

    Example:
        >>> modem = Throb1()
        >>> audio = modem.modulate("CQ CQ DE W1ABC")

    Reference:
        fldigi/src/throb/throb.cxx lines 142-153
    """
    return Throb(mode='throb1', symlen=Throb.SYMLEN_1,
                 tone_freqs=Throb.THROB_TONE_FREQS_NAR,
                 num_tones=9, num_chars=45, is_throbx=False,
                 use_full_pulse=False)


def Throb2() -> 'Throb':
    """
    Throb2 mode: 2 baud, 9 tones, narrow spacing (8 Hz).

    - Symbol length: 4096 samples (~0.512 seconds)
    - Baud rate: ~2 baud
    - Tone spacing: 8 Hz
    - Bandwidth: 64 Hz (approx)
    - Pulse shaping: Semi-pulse

    Reference: fldigi/src/throb/throb.cxx lines 155-166
    """
    return Throb(mode='throb2', symlen=Throb.SYMLEN_2,
                 tone_freqs=Throb.THROB_TONE_FREQS_NAR,
                 num_tones=9, num_chars=45, is_throbx=False,
                 use_full_pulse=False)


def Throb4() -> 'Throb':
    """
    Throb4 mode: 4 baud, 9 tones, wide spacing (16 Hz).

    - Symbol length: 2048 samples (~0.256 seconds)
    - Baud rate: ~4 baud
    - Tone spacing: 16 Hz
    - Bandwidth: 128 Hz (approx)
    - Pulse shaping: Full-pulse

    Reference: fldigi/src/throb/throb.cxx lines 168-180
    """
    return Throb(mode='throb4', symlen=Throb.SYMLEN_4,
                 tone_freqs=Throb.THROB_TONE_FREQS_WID,
                 num_tones=9, num_chars=45, is_throbx=False,
                 use_full_pulse=True)


def ThrobX1() -> 'Throb':
    """
    ThrobX1 mode: 1 baud, 11 tones, narrow spacing (7.8125 Hz).

    - Symbol length: 8192 samples (~1.024 seconds)
    - Baud rate: ~1 baud
    - Tone spacing: 7.8125 Hz
    - Bandwidth: 78.125 Hz (approx)
    - Pulse shaping: Semi-pulse
    - Extended character set (55 characters)

    Reference: fldigi/src/throb/throb.cxx lines 182-193
    """
    return Throb(mode='throbx1', symlen=Throb.SYMLEN_1,
                 tone_freqs=Throb.THROBX_TONE_FREQS_NAR,
                 num_tones=11, num_chars=55, is_throbx=True,
                 use_full_pulse=False)


def ThrobX2() -> 'Throb':
    """
    ThrobX2 mode: 2 baud, 11 tones, narrow spacing (7.8125 Hz).

    - Symbol length: 4096 samples (~0.512 seconds)
    - Baud rate: ~2 baud
    - Tone spacing: 7.8125 Hz
    - Bandwidth: 78.125 Hz (approx)
    - Pulse shaping: Semi-pulse
    - Extended character set (55 characters)

    Reference: fldigi/src/throb/throb.cxx lines 195-206
    """
    return Throb(mode='throbx2', symlen=Throb.SYMLEN_2,
                 tone_freqs=Throb.THROBX_TONE_FREQS_NAR,
                 num_tones=11, num_chars=55, is_throbx=True,
                 use_full_pulse=False)


def ThrobX4() -> 'Throb':
    """
    ThrobX4 mode: 4 baud, 11 tones, wide spacing (15.625 Hz).

    - Symbol length: 2048 samples (~0.256 seconds)
    - Baud rate: ~4 baud
    - Tone spacing: 15.625 Hz
    - Bandwidth: 156.25 Hz (approx)
    - Pulse shaping: Full-pulse
    - Extended character set (55 characters)
    - NONSTANDARD mode

    Reference: fldigi/src/throb/throb.cxx lines 208-219
    """
    return Throb(mode='throbx4', symlen=Throb.SYMLEN_4,
                 tone_freqs=Throb.THROBX_TONE_FREQS_WID,
                 num_tones=11, num_chars=55, is_throbx=True,
                 use_full_pulse=True)
