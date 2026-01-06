"""
QPSK (Quadrature Phase Shift Keying) Decoder Implementation

Based on fldigi's QPSK decoder (fldigi/src/psk/psk.cxx).
Supports decoding QPSK31, QPSK63, QPSK125, QPSK250, QPSK500 and other baud rates.

Decoder Architecture (from fldigi):
1. Baseband conversion - Mix with NCO to downconvert to baseband
2. Matched filtering - Two-stage FIR filters with decimation
3. Symbol timing recovery - Syncbuf-based timing loop
4. Phase detection - Compute phase of each symbol (4-state QPSK)
5. Viterbi decoding - Rate 1/2 convolutional FEC decoder
6. Varicode decoding - Convert bit stream to text

QPSK uses a rate 1/2 convolutional encoder, where 1 data bit produces 2 coded bits
(forming a QPSK symbol). The Viterbi decoder reverses this process.

Reference: fldigi/src/psk/psk.cxx (rx_process, rx_symbol, rx_qpsk)
"""

import numpy as np
from typing import Optional, Callable
from ..varicode.psk_varicode import decode_varicode
from ..core.viterbi import create_qpsk_decoder
from ..core.oscillator import NCO
from ..core.afc import PhaseAFC
from ..core.dcd import EnergyDCD


class QPSKDecoder:
    """
    QPSK decoder for all QPSK modes (QPSK31, QPSK63, QPSK125, QPSK250, QPSK500).

    This decoder uses Viterbi FEC decoding for error correction. Each QPSK symbol
    carries 2 coded bits, which the Viterbi decoder converts back to 1 data bit.

    Args:
        baud: Symbol rate in baud (31.25, 62.5, 125, 250, 500)
        sample_rate: Audio sample rate in Hz (default: 8000)
        frequency: Carrier frequency in Hz (default: 1000)
        afc_enabled: Enable automatic frequency correction (default: True)
        squelch_enabled: Enable squelch/DCD (default: True)

    Attributes:
        text_callback: Optional callback for decoded text (set via set_text_callback)

    Example:
        >>> decoder = QPSKDecoder(baud=125, sample_rate=8000, frequency=1000)
        >>> decoder.set_text_callback(lambda text: print(text, end=''))
        >>> decoder.process(audio_samples)
    """

    def __init__(
        self,
        baud: float = 31.25,
        sample_rate: float = 8000.0,
        frequency: float = 1000.0,
        afc_enabled: bool = True,
        squelch_enabled: bool = True,
    ):
        """Initialize QPSK decoder."""
        self.baud = baud
        self.sample_rate = sample_rate
        self.frequency = frequency
        self.afc_enabled = afc_enabled
        self.squelch_enabled = squelch_enabled

        # Calculate symbol parameters
        self.samples_per_symbol = sample_rate / baud
        self.symbollen = int(self.samples_per_symbol)

        # Determine decimation factor based on baud rate
        # QPSK31: decimate by 16, QPSK63: by 8, QPSK125: by 4, QPSK250: by 2, QPSK500: by 1
        if baud <= 32:
            self.decimate1 = 16
            self.decimate2 = 1
        elif baud <= 64:
            self.decimate1 = 8
            self.decimate2 = 1
        elif baud <= 128:
            self.decimate1 = 4
            self.decimate2 = 1
        elif baud <= 256:
            self.decimate1 = 2
            self.decimate2 = 1
        else:
            self.decimate1 = 1
            self.decimate2 = 1

        # NCO (Numerically Controlled Oscillator) for carrier mixing
        self.nco = NCO(sample_rate=sample_rate, frequency=frequency)

        # FIR filters (will be initialized later)
        self.fir1 = None  # First decimating matched filter
        self.fir2 = None  # Second matched filter
        self.fir1_index = 0

        # Symbol timing recovery
        self.bitclk = 0.0
        self.syncbuf_size = 16 if self.symbollen >= 16 else self.symbollen
        self.syncbuf = np.zeros(self.syncbuf_size)

        # Phase tracking and differential decoding
        self.prevsymbol = complex(1.0, 0.0)
        self.phase = 0.0

        # Quality metrics (for monitoring)
        self.quality_real = 0.0
        self.quality_imag = 0.0
        self.metric = 0.0

        # DCD (Data Carrier Detect) - using framework component
        self.dcd = EnergyDCD(threshold_db=6.0, attack=0.1, decay=0.01)
        self.dcd_active = False

        # AFC (Automatic Frequency Control) - using framework component
        self.afc = PhaseAFC(alpha=0.01, max_offset=self.baud * 2)
        self.afcmetric = 0.0
        self.afc_decay = 50  # Decay constant for AFC metric

        # Viterbi decoder for FEC
        self.viterbi = create_qpsk_decoder()

        # Varicode decoder state
        self.shreg = 0  # Shift register for varicode decoding

        # Callbacks
        self.text_callback: Optional[Callable[[str], None]] = None

        # Initialize filters
        self._init_filters()

        # Statistics
        self.symbols_received = 0
        self.chars_decoded = 0

    def _init_filters(self):
        """Initialize matched filters.

        fldigi uses raised cosine matched filters. For now we'll use
        simple lowpass filters and improve later.
        """
        # TODO: Implement proper raised cosine matched filters
        # For now, use simple moving average as placeholder
        filter_len = int(self.samples_per_symbol / self.decimate1)
        if filter_len < 3:
            filter_len = 3
        self.fir1_coeffs = np.ones(filter_len) / filter_len
        self.fir1_buffer = np.zeros(len(self.fir1_coeffs), dtype=complex)

        self.fir2_coeffs = np.ones(filter_len) / filter_len
        self.fir2_buffer = np.zeros(len(self.fir2_coeffs), dtype=complex)

    def set_text_callback(self, callback: Callable[[str], None]) -> None:
        """Set callback for decoded text output.

        Args:
            callback: Function that receives decoded text strings
        """
        self.text_callback = callback

    def set_frequency(self, frequency: float) -> None:
        """Update carrier frequency (e.g., for AFC).

        Args:
            frequency: New carrier frequency in Hz
        """
        self.frequency = frequency
        self.nco.frequency = frequency

    def process(self, samples: np.ndarray) -> None:
        """Process incoming audio samples.

        This is the main entry point. Feed audio samples here and
        decoded text will be output via the text_callback.

        Args:
            samples: Audio samples as numpy array (mono, float)
        """
        for sample in samples:
            self._process_sample(sample)

    def demodulate(self, samples: np.ndarray) -> str:
        """Demodulate audio samples to text (synchronous API).

        This provides a simple synchronous API that mirrors the
        QPSK.modulate() encoder API.

        Args:
            samples: Audio samples as numpy array (mono, float)

        Returns:
            Decoded text string

        Example:
            >>> decoder = QPSKDecoder(baud=125, frequency=1000)
            >>> text = decoder.demodulate(audio_samples)
            >>> print(text)
            'Hello World!'
        """
        # Collect decoded text
        decoded_chars = []

        # Temporarily override callback
        old_callback = self.text_callback
        self.text_callback = lambda char: decoded_chars.append(char)

        # Process samples
        self.process(samples)

        # Restore callback
        self.text_callback = old_callback

        return ''.join(decoded_chars)

    def _process_sample(self, sample: float) -> None:
        """Process a single audio sample.

        This implements the rx_process logic from fldigi.

        Args:
            sample: Single audio sample (float)
        """
        # Step 1: Mix with NCO to downconvert to baseband
        # Get one sample from NCO and mix with input
        nco_sample = self.nco.step(1)[0]
        z = sample * np.conj(nco_sample)  # Mix down: multiply by conj to shift down

        # Step 2: First FIR filter with decimation
        # Shift sample into buffer
        self.fir1_buffer = np.roll(self.fir1_buffer, 1)
        self.fir1_buffer[0] = z

        # Increment decimation counter
        self.fir1_index += 1

        # Only process every Nth sample (decimation)
        if self.fir1_index >= self.decimate1:
            self.fir1_index = 0

            # Apply FIR1 filter
            z_fir1 = np.sum(self.fir1_buffer * self.fir1_coeffs)

            # Step 3: Second FIR filter (no decimation)
            self.fir2_buffer = np.roll(self.fir2_buffer, 1)
            self.fir2_buffer[0] = z_fir1
            z_fir2 = np.sum(self.fir2_buffer * self.fir2_coeffs)

            # Step 4: Symbol timing recovery
            self._symbol_timing_recovery(z_fir2)

    def _symbol_timing_recovery(self, z: complex) -> None:
        """Symbol timing recovery using syncbuf.

        This implements the symbol timing logic from fldigi/src/psk/psk.cxx
        lines 2056-2149.

        Args:
            z: Filtered complex sample
        """
        # Fill syncbuf with rectified signal magnitude
        idx = int(self.bitclk)
        if idx < 0 or idx >= len(self.syncbuf):
            idx = 0

        # Update syncbuf with exponential averaging
        self.syncbuf[idx] = 0.8 * self.syncbuf[idx] + 0.2 * abs(z)

        # Calculate timing error
        bitsteps = self.syncbuf_size
        symsteps = bitsteps // 2

        sum_diff = 0.0
        sum_amp = 0.0

        for i in range(symsteps):
            sum_diff += (self.syncbuf[i] - self.syncbuf[i + symsteps])
            sum_amp += (self.syncbuf[i] + self.syncbuf[i + symsteps])

        # Normalize by amplitude to avoid signal level dependency
        if sum_amp > 1e-10:
            timing_error = sum_diff / sum_amp
        else:
            timing_error = 0.0

        # Adjust bit clock based on timing error
        self.bitclk -= timing_error / (5.0 * 16 / bitsteps)
        self.bitclk += 1.0

        # Wrap bit clock
        if self.bitclk < 0:
            self.bitclk += bitsteps

        # When bitclk wraps around, we have a complete symbol
        if self.bitclk >= bitsteps:
            self.bitclk -= bitsteps
            self._rx_symbol(z)

    def _rx_symbol(self, symbol: complex) -> None:
        """Process received symbol.

        This implements the rx_symbol logic from fldigi/src/psk/psk.cxx
        with QPSK-specific modifications.

        Args:
            symbol: Complex symbol value
        """
        self.symbols_received += 1

        # Calculate signal amplitude for quality metric
        sigamp = abs(symbol) ** 2

        # Differential phase detection
        # phase = arg(conj(prev) * current)
        phase_sample = np.conj(self.prevsymbol) * symbol
        self.phase = np.angle(phase_sample)

        # Update previous symbol
        self.prevsymbol = symbol

        # Ensure phase is in [0, 2π)
        if self.phase < 0:
            self.phase += 2.0 * np.pi

        # QPSK: decide which of 4 phase states (0°, 90°, 180°, 270°)
        # bits = 0: 0° (0), bits = 1: 90° (π/2), bits = 2: 180° (π), bits = 3: 270° (3π/2)
        # From fldigi psk.cxx line 1500: bits = ((int) (phase / M_PI_2 + 0.5)) & 3
        bits = int(self.phase / (np.pi / 2.0) + 0.5) & 3

        # Update quality metric
        # Quality tracks how well phase aligns with ideal constellation
        # For QPSK, n=4 (4 phase states)
        n = 4
        cval = np.cos(n * self.phase)
        sval = np.sin(n * self.phase)

        decay = 50  # SQLDECAY from fldigi
        self.quality_real = self._decayavg(self.quality_real, cval, decay)
        self.quality_imag = self._decayavg(self.quality_imag, sval, decay)

        # Metric is norm of quality vector (0-100 scale)
        self.metric = 100.0 * (self.quality_real**2 + self.quality_imag**2)

        # Update AFC metric (for AFC logic)
        quality_norm = self.quality_real**2 + self.quality_imag**2
        self.afcmetric = self._decayavg(self.afcmetric, quality_norm, self.afc_decay)

        # DCD (Data Carrier Detect) - using framework component
        if self.squelch_enabled:
            # Update DCD with symbol power
            symbol_array = np.array([symbol])
            self.dcd_active, snr_db = self.dcd.update(symbol_array)
        else:
            self.dcd_active = True

        # AFC (Automatic Frequency Control) - using framework component
        if self.afc_enabled and self.afcmetric > 0.05:
            # Calculate phase error for AFC
            # For QPSK: ideal phase is bits * π/2
            ideal_phase = bits * np.pi / 2.0
            phase_error = self.phase - ideal_phase

            # Wrap phase error to [-π, π]
            while phase_error > np.pi:
                phase_error -= 2.0 * np.pi
            while phase_error < -np.pi:
                phase_error += 2.0 * np.pi

            # Update AFC and adjust frequency
            freq_offset = self.afc.update(phase_error, self.baud)
            new_freq = self.frequency - freq_offset
            self.set_frequency(new_freq)

        # Send symbol to QPSK decoder (Viterbi)
        self._rx_qpsk(bits)

    def _rx_qpsk(self, bits: int) -> None:
        """Process QPSK symbol through Viterbi decoder.

        This implements the rx_qpsk logic from fldigi/src/psk/psk.cxx
        lines 1191-1206.

        From fldigi:
        - If QPSK and not reversed: bits = (4 - bits) & 3
        - Convert 2-bit symbol to soft symbols for Viterbi:
          sym[0] = (bits & 1) ? 255 : 0
          sym[1] = (bits & 2) ? 0 : 255  (top bit is flipped)

        Args:
            bits: QPSK symbol value (0-3)
        """
        # Apply reversal if not in reverse mode (from fldigi line 1196-1197)
        # For normal QPSK operation: bits = (4 - bits) & 3
        bits = (4 - bits) & 3

        # Convert symbol to soft symbols for Viterbi decoder
        # sym[0] = first bit (0 or 255)
        # sym[1] = second bit (0 or 255, inverted)
        sym = [0, 0]
        sym[0] = 255 if (bits & 1) else 0
        sym[1] = 0 if (bits & 2) else 255  # Top bit is flipped

        # Decode through Viterbi decoder
        metric_out = [0]
        decoded_bits = self.viterbi.decode(sym, metric_out)

        # Viterbi decoder returns decoded bits every chunksize symbols
        if decoded_bits is not None:
            # Process each decoded bit
            # Note: Bits need to be inverted for fldigi compatibility
            for i in range(8):  # chunksize = 8 by default
                bit = (decoded_bits >> (7 - i)) & 1
                bit = 1 - bit  # Invert bit for fldigi compatibility
                self._rx_bit(bit)

    def _rx_bit(self, bit: bool) -> None:
        """Process received bit through varicode decoder.

        This implements the rx_bit logic from fldigi/src/psk/psk.cxx
        lines 1116-1156.

        Args:
            bit: Received bit value (True/False or 1/0)
        """
        # Shift bit into shift register
        self.shreg = (self.shreg << 1) | (1 if bit else 0)

        # PSK varicode: look for two consecutive zeros
        # When (shreg & 3) == 0, we have "...XX00" pattern
        if (self.shreg & 3) == 0:
            # Extract the varicode (everything before the two zeros)
            code_bits = self.shreg >> 2

            # Decode varicode
            char_code = self._decode_varicode(code_bits)

            # Output character if valid and DCD active
            if char_code is not None and self.dcd_active:
                char = chr(char_code)
                if self.text_callback:
                    self.text_callback(char)
                self.chars_decoded += 1

            # Reset shift register
            self.shreg = 0

    def _decode_varicode(self, code_bits: int) -> Optional[int]:
        """Decode varicode bit pattern to ASCII.

        Args:
            code_bits: Integer with varicode bits

        Returns:
            ASCII character code, or None if invalid
        """
        # Convert integer to bit string
        if code_bits == 0:
            return None

        # Convert to binary string
        bit_str = bin(code_bits)[2:]  # Remove '0b' prefix

        # Use existing varicode decoder
        return decode_varicode(bit_str)

    @staticmethod
    def _decayavg(avg: float, value: float, decay: float) -> float:
        """Exponential moving average (decay filter).

        Args:
            avg: Current average value
            value: New value
            decay: Decay constant (larger = slower response)

        Returns:
            Updated average
        """
        return (avg * (decay - 1.0) + value) / decay

    def get_stats(self) -> dict:
        """Get decoder statistics.

        Returns:
            Dictionary with statistics
        """
        return {
            'symbols_received': self.symbols_received,
            'chars_decoded': self.chars_decoded,
            'metric': self.metric,
            'dcd': self.dcd_active,
            'frequency': self.frequency,
            'freq_offset': self.afc.freq_offset,
        }

    def reset(self) -> None:
        """Reset decoder state."""
        # Reset NCO
        self.nco.phase = 0.0

        # Reset timing recovery
        self.bitclk = 0.0
        self.syncbuf = np.zeros(self.syncbuf_size)

        # Reset phase tracking
        self.prevsymbol = complex(1.0, 0.0)
        self.phase = 0.0

        # Reset quality metrics
        self.quality_real = 0.0
        self.quality_imag = 0.0
        self.metric = 0.0

        # Reset DCD
        self.dcd_active = False

        # Reset AFC
        self.afc = PhaseAFC(alpha=0.01, max_offset=self.baud * 2)
        self.afcmetric = 0.0

        # Reset varicode decoder
        self.shreg = 0

        # Reset Viterbi decoder
        self.viterbi.reset()

        # Reset filters
        self.fir1_buffer = np.zeros(len(self.fir1_coeffs), dtype=complex)
        self.fir2_buffer = np.zeros(len(self.fir2_coeffs), dtype=complex)

        # Reset statistics
        self.symbols_received = 0
        self.chars_decoded = 0


# Convenience functions for common QPSK modes


def QPSK_31_Decoder(
    sample_rate: float = 8000.0,
    frequency: float = 1000.0,
    afc_enabled: bool = True,
    squelch_enabled: bool = True,
) -> QPSKDecoder:
    """Create a QPSK31 decoder (31.25 baud)."""
    return QPSKDecoder(
        baud=31.25,
        sample_rate=sample_rate,
        frequency=frequency,
        afc_enabled=afc_enabled,
        squelch_enabled=squelch_enabled,
    )


def QPSK_63_Decoder(
    sample_rate: float = 8000.0,
    frequency: float = 1000.0,
    afc_enabled: bool = True,
    squelch_enabled: bool = True,
) -> QPSKDecoder:
    """Create a QPSK63 decoder (62.5 baud)."""
    return QPSKDecoder(
        baud=62.5,
        sample_rate=sample_rate,
        frequency=frequency,
        afc_enabled=afc_enabled,
        squelch_enabled=squelch_enabled,
    )


def QPSK_125_Decoder(
    sample_rate: float = 8000.0,
    frequency: float = 1000.0,
    afc_enabled: bool = True,
    squelch_enabled: bool = True,
) -> QPSKDecoder:
    """Create a QPSK125 decoder (125 baud)."""
    return QPSKDecoder(
        baud=125,
        sample_rate=sample_rate,
        frequency=frequency,
        afc_enabled=afc_enabled,
        squelch_enabled=squelch_enabled,
    )


def QPSK_250_Decoder(
    sample_rate: float = 8000.0,
    frequency: float = 1000.0,
    afc_enabled: bool = True,
    squelch_enabled: bool = True,
) -> QPSKDecoder:
    """Create a QPSK250 decoder (250 baud)."""
    return QPSKDecoder(
        baud=250,
        sample_rate=sample_rate,
        frequency=frequency,
        afc_enabled=afc_enabled,
        squelch_enabled=squelch_enabled,
    )


def QPSK_500_Decoder(
    sample_rate: float = 8000.0,
    frequency: float = 1000.0,
    afc_enabled: bool = True,
    squelch_enabled: bool = True,
) -> QPSKDecoder:
    """Create a QPSK500 decoder (500 baud)."""
    return QPSKDecoder(
        baud=500,
        sample_rate=sample_rate,
        frequency=frequency,
        afc_enabled=afc_enabled,
        squelch_enabled=squelch_enabled,
    )
