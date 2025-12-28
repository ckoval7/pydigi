"""
Hellschreiber (FeldHell) Modem Implementation

Hellschreiber is a facsimile mode that "paints" characters on the screen
rather than decoding them as text. Each character is a 14-row bitmap
transmitted column-by-column.

Supported modes:
- FeldHell (original): 17.5 columns/sec, AM
- SlowHell: 2.1875 columns/sec, AM
- HellX5: 87.5 columns/sec, AM (5x faster)
- HellX9: 157.5 columns/sec, AM (9x faster)
- FSKHell245: 17.5 columns/sec, FSK, 245 baud
- FSKHell105: 17.5 columns/sec, FSK, 105 baud
- Hell80: 35 columns/sec, FSK, 80 columns/sec

Reference: fldigi/src/feld/feld.cxx
"""

import numpy as np
import math
from typing import Optional
from ..core.oscillator import NCO
from ..varicode.feld_font import get_column_bits, FELD_7X7_14
from .base import Modem


class Hell(Modem):
    """
    Hellschreiber modem with support for all 7 Hell modes.

    This modem transmits characters as 14-row bitmaps, column-by-column.
    Each pixel (bit) in the bitmap is represented by either amplitude
    modulation (ON/OFF keying) or frequency shift keying.
    """

    # Mode definitions: (column_rate, modulation_type, fsk_bandwidth)
    MODE_PARAMS = {
        "FELDHELL": (17.5, "AM", None),
        "SLOWHELL": (2.1875, "AM", None),
        "HELLX5": (87.5, "AM", None),
        "HELLX9": (157.5, "AM", None),
        "FSKH245": (17.5, "FSK", 122.5),
        "FSKH105": (17.5, "FSK", 55.0),
        "HELL80": (35.0, "FSK", 300.0),
    }

    def __init__(
        self,
        mode: str = "FELDHELL",
        sample_rate: float = 8000.0,
        frequency: float = 1000.0,
        tx_amplitude: float = 0.8,
        pulse_shaping: int = 0,
        column_width: int = 1,
    ):
        """
        Initialize Hell modem.

        Args:
            mode: Hell mode name (FELDHELL, SLOWHELL, HELLX5, HELLX9, FSKH245, FSKH105, HELL80)
            sample_rate: Sample rate in Hz (default: 8000)
            frequency: Center frequency in Hz (default: 1000)
            tx_amplitude: Transmit amplitude 0.0-1.0 (default: 0.8)
            pulse_shaping: Pulse rise time in samples (0=slow/4ms, 1=medium/2ms, 2=fast/1ms, 3=square)
            column_width: Number of times to repeat each column (1-4, default: 1)
        """
        mode = mode.upper()
        if mode not in self.MODE_PARAMS:
            raise ValueError(
                f"Unknown Hell mode: {mode}. Valid modes: {list(self.MODE_PARAMS.keys())}"
            )

        super().__init__(mode_name=mode, sample_rate=sample_rate, frequency=frequency)

        self.tx_amplitude = tx_amplitude
        self.pulse_shaping = pulse_shaping
        self.column_width = column_width

        # Get mode parameters
        self.column_rate, self.modulation_type, self.fsk_bandwidth = self.MODE_PARAMS[mode]

        # Calculate timing
        self.column_len = 14  # Each column has 14 rows
        self.pixel_rate = self.column_len * self.column_rate
        self.samples_per_pixel = int(sample_rate / self.pixel_rate)
        # Calculate upsample increment once (critical for timing accuracy)
        self.upsample_inc = self.pixel_rate / sample_rate

        # Calculate bandwidth
        if self.modulation_type == "AM":
            self._bandwidth = self.pixel_rate
        else:  # FSK
            self._bandwidth = self.fsk_bandwidth

        # TX state
        self.nco = None
        self.txphacc = 0.0
        self.txcounter = 0.0  # Persistent timing counter (prevents slant)
        self.prev_symbol = 0
        self.on_shape = None
        self.off_shape = None

    def tx_init(self) -> None:
        """Initialize transmitter state."""
        # Initialize NCO
        self.nco = NCO(frequency=self.frequency, sample_rate=self.sample_rate)
        self.txphacc = 0.0
        self.txcounter = 0.0  # Reset timing counter
        self.prev_symbol = 0

        # Initialize pulse shaping waveforms for AM modes
        if self.modulation_type == "AM":
            self._init_key_waveform()

    def _init_key_waveform(self) -> None:
        """
        Initialize ON/OFF key shaping waveforms.

        Uses raised cosine shaping to prevent spectral splatter on
        transitions between ON and OFF states.

        Reference: fldigi feld.cxx initKeyWaveform()
        """
        max_len = 512
        self.on_shape = np.ones(max_len, dtype=np.float64)
        self.off_shape = np.zeros(max_len, dtype=np.float64)

        # Apply raised cosine shaping based on pulse_shaping parameter
        if self.pulse_shaping == 0:
            # Slow rise: 4ms (33 samples at 8kHz)
            rise_samples = 33
            for i in range(min(rise_samples, max_len)):
                self.on_shape[i] = 0.5 * (1.0 - math.cos(math.pi * i / rise_samples))
                self.off_shape[rise_samples - 1 - i] = self.on_shape[i]
        elif self.pulse_shaping == 1:
            # Medium rise: 2ms (16 samples at 8kHz)
            rise_samples = 16
            for i in range(min(rise_samples, max_len)):
                self.on_shape[i] = 0.5 * (1.0 - math.cos(math.pi * i / rise_samples))
                self.off_shape[rise_samples - 1 - i] = self.on_shape[i]
        elif self.pulse_shaping == 2:
            # Fast rise: 1ms (8 samples at 8kHz)
            rise_samples = 8
            for i in range(min(rise_samples, max_len)):
                self.on_shape[i] = 0.5 * (1.0 - math.cos(math.pi * i / rise_samples))
                self.off_shape[rise_samples - 1 - i] = self.on_shape[i]
        # else: pulse_shaping == 3 means square wave (default arrays already set)

    def _nco(self, freq: float) -> float:
        """
        Simple NCO (Numerically Controlled Oscillator) for generating sine wave.

        Args:
            freq: Frequency in Hz

        Returns:
            Sine wave sample
        """
        sample = math.sin(self.txphacc)
        self.txphacc += 2.0 * math.pi * freq / self.sample_rate
        if self.txphacc > 2.0 * math.pi:
            self.txphacc -= 2.0 * math.pi
        return sample

    def _send_symbol(self, curr_symbol: int, next_symbol: int) -> np.ndarray:
        """
        Generate audio samples for one pixel (row bit).

        Args:
            curr_symbol: Current pixel state (0 or 1)
            next_symbol: Next pixel state (0 or 1, used for AM shaping)

        Returns:
            Audio samples for this pixel

        Reference: fldigi feld.cxx send_symbol()
        """
        samples = []
        tone = self.frequency
        out_idx = 0

        # For FSK modes, shift frequency based on symbol
        if self.modulation_type == "FSK":
            shift = self._bandwidth / 2.0
            if curr_symbol:
                tone -= shift
            else:
                tone += shift

        # Generate samples for this pixel
        # NOTE: txcounter is persistent across all symbol calls to maintain timing accuracy
        while True:
            # Determine amplitude
            if self.modulation_type == "FSK":
                # FSK: constant amplitude, frequency carries data
                amp = 1.0
            elif self.modulation_type == "AM" and (self.pulse_shaping in [0, 1, 2]):
                # AM with shaping: apply shaped transitions
                if self.prev_symbol == 0 and curr_symbol == 1:
                    # Rising edge
                    amp = self.on_shape[min(out_idx, len(self.on_shape) - 1)]
                elif curr_symbol == 1 and next_symbol == 0:
                    # Falling edge
                    amp = self.off_shape[min(out_idx, len(self.off_shape) - 1)]
                else:
                    # Steady state
                    amp = float(curr_symbol)
            else:
                # AM modes (HellX5, HellX9) or square wave: direct amplitude
                amp = float(curr_symbol)

            # Generate sample
            samples.append(amp * self._nco(tone))
            out_idx += 1

            # Check if we've generated enough samples for this pixel
            # Use persistent counter to avoid timing drift (slant)
            self.txcounter += self.upsample_inc
            if self.txcounter >= 1.0:
                self.txcounter -= 1.0
                break

            # Safety check to prevent infinite loop
            if out_idx >= 10000:
                break

        self.prev_symbol = curr_symbol
        return np.array(samples, dtype=np.float64)

    def _send_null_column(self) -> np.ndarray:
        """
        Send a column of all zeros (blank column).

        Returns:
            Audio samples for null column
        """
        audio = np.array([], dtype=np.float64)
        for _ in range(self.column_len):
            audio = np.append(audio, self._send_symbol(0, 0))
        return audio

    def _tx_char(self, char: str) -> np.ndarray:
        """
        Transmit a single character.

        Args:
            char: Character to transmit

        Returns:
            Audio samples for this character

        Reference: fldigi feld.cxx tx_char()
        """
        audio = np.array([], dtype=np.float64)

        # Send leading null column
        audio = np.append(audio, self._send_null_column())

        # Handle space specially: send 3 null columns
        if char == " ":
            audio = np.append(audio, self._send_null_column())
            audio = np.append(audio, self._send_null_column())
            audio = np.append(audio, self._send_null_column())
        else:
            # Send character column by column
            column = 0
            while True:
                col_bits = get_column_bits(char, column)
                if col_bits == -1:
                    break

                # Repeat column based on column_width setting
                for _ in range(self.column_width):
                    # Send each row of this column
                    for row in range(self.column_len):
                        curr_bit = (col_bits >> row) & 1
                        # Look ahead to next bit for shaping
                        if row < self.column_len - 1:
                            next_bit = (col_bits >> (row + 1)) & 1
                        else:
                            next_bit = 0
                        audio = np.append(audio, self._send_symbol(curr_bit, next_bit))

                column += 1

        # Send trailing null column
        audio = np.append(audio, self._send_null_column())

        return audio

    def tx_process(self, text: str) -> np.ndarray:
        """
        Process text and generate Hellschreiber audio.

        Args:
            text: Text to transmit

        Returns:
            Audio samples

        Reference: fldigi feld.cxx tx_process()
        """
        audio = np.array([], dtype=np.float64)

        # Send preamble: 3 dots
        for _ in range(3):
            audio = np.append(audio, self._tx_char("."))

        # Send each character
        for char in text:
            # Convert newlines and carriage returns to spaces
            if char in "\r\n":
                char = " "

            # Only send characters we have in the font
            if char in FELD_7X7_14:
                audio = np.append(audio, self._tx_char(char))

        # Send postamble: 3 dots + space
        for _ in range(3):
            audio = np.append(audio, self._tx_char("."))
        audio = np.append(audio, self._tx_char(" "))

        # Scale by tx_amplitude
        audio = audio * self.tx_amplitude

        return audio


# Convenience functions for creating specific Hell modes


def FeldHell(sample_rate: float = 8000.0, frequency: float = 1000.0, **kwargs) -> Hell:
    """Create FeldHell modem (original Hellschreiber, 17.5 col/sec, AM)."""
    return Hell("FELDHELL", sample_rate, frequency, **kwargs)


def SlowHell(sample_rate: float = 8000.0, frequency: float = 1000.0, **kwargs) -> Hell:
    """Create SlowHell modem (slow version, 2.1875 col/sec, AM)."""
    return Hell("SLOWHELL", sample_rate, frequency, **kwargs)


def HellX5(sample_rate: float = 8000.0, frequency: float = 1000.0, **kwargs) -> Hell:
    """Create HellX5 modem (5x faster, 87.5 col/sec, AM)."""
    return Hell("HELLX5", sample_rate, frequency, **kwargs)


def HellX9(sample_rate: float = 8000.0, frequency: float = 1000.0, **kwargs) -> Hell:
    """Create HellX9 modem (9x faster, 157.5 col/sec, AM)."""
    return Hell("HELLX9", sample_rate, frequency, **kwargs)


def FSKHell245(sample_rate: float = 8000.0, frequency: float = 1000.0, **kwargs) -> Hell:
    """Create FSKHell245 modem (245 baud FSK, 17.5 col/sec)."""
    return Hell("FSKH245", sample_rate, frequency, **kwargs)


def FSKHell105(sample_rate: float = 8000.0, frequency: float = 1000.0, **kwargs) -> Hell:
    """Create FSKHell105 modem (105 baud FSK, 17.5 col/sec)."""
    return Hell("FSKH105", sample_rate, frequency, **kwargs)


def Hell80(sample_rate: float = 8000.0, frequency: float = 1000.0, **kwargs) -> Hell:
    """Create Hell80 modem (80 column mode, 35 col/sec, FSK)."""
    return Hell("HELL80", sample_rate, frequency, **kwargs)
