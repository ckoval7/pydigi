"""
8PSK (8-Phase Shift Keying) Decoder Implementation (Non-FEC)

Based on fldigi's 8PSK decoder (fldigi/src/psk/psk.cxx).
Supports decoding 8PSK125, 8PSK250, 8PSK500, 8PSK1000 (non-FEC modes).

Decoder Architecture:
1. Baseband conversion - Mix with NCO to downconvert to baseband
2. Matched filtering - Two-stage FIR filters with decimation
3. Symbol timing recovery - Syncbuf-based timing loop
4. Phase detection - Compute phase of each symbol
5. Constellation decoding - Map phase to 3-bit symbols (8PSK)
6. Bit accumulation - Collect 3 bits per symbol
7. Varicode decoding - Convert bit stream to text (MFSK varicode)

Reference: fldigi/src/psk/psk.cxx (rx_process, rx_symbol, rx_bit)
"""

import numpy as np
from typing import Optional, Callable
from ..varicode.mfsk_varicode_fixed import MFSKVaricodeDecoder


class EightPSKDecoder:
    """
    8PSK decoder for non-FEC modes (8PSK125, 8PSK250, 8PSK500, 8PSK1000).

    This decoder handles 8-phase shift keying with MFSK varicode encoding.
    Each symbol carries 3 bits of information.

    Args:
        baud: Symbol rate in baud (125, 250, 500, 1000)
        sample_rate: Audio sample rate in Hz (default: 8000)
        frequency: Carrier frequency in Hz (default: 1000)
        afc_enabled: Enable automatic frequency correction (default: True)
        squelch_enabled: Enable squelch/DCD (default: True)

    Attributes:
        text_callback: Optional callback for decoded text (set via set_text_callback)

    Example:
        >>> decoder = EightPSKDecoder(baud=125, sample_rate=8000, frequency=1000)
        >>> decoder.set_text_callback(lambda text: print(text, end=''))
        >>> decoder.process(audio_samples)
    """

    # 8PSK constellation for non-FEC (from fldigi)
    # Symbol value to phase mapping
    # Maps to sym*2 positions in 16-PSK constellation
    CONSTELLATION_PHASES = [
        np.pi,  # 0: 180°
        5 * np.pi / 4,  # 1: 225°
        3 * np.pi / 2,  # 2: 270°
        7 * np.pi / 4,  # 3: 315°
        0.0,  # 4: 0°
        np.pi / 4,  # 5: 45°
        np.pi / 2,  # 6: 90°
        3 * np.pi / 4,  # 7: 135°
    ]

    def __init__(
        self,
        baud: float = 125,
        sample_rate: float = 8000.0,
        frequency: float = 1000.0,
        afc_enabled: bool = True,
        squelch_enabled: bool = True,
    ):
        """Initialize 8PSK decoder."""
        self.baud = baud
        self.sample_rate = sample_rate
        self.frequency = frequency
        self.afc_enabled = afc_enabled
        self.squelch_enabled = squelch_enabled

        # Calculate symbol parameters
        self.samples_per_symbol = sample_rate / baud
        self.symbollen = int(self.samples_per_symbol)

        # Determine decimation factor based on baud rate
        # 8PSK125: decimate by 4, 8PSK250: by 2, 8PSK500+: by 1
        if baud <= 128:
            self.decimate1 = 4
            self.decimate2 = 1
        elif baud <= 256:
            self.decimate1 = 2
            self.decimate2 = 1
        else:
            self.decimate1 = 1
            self.decimate2 = 1

        # NCO (Numerically Controlled Oscillator) for carrier mixing
        self.phase_acc = 0.0
        self.delta = 2.0 * np.pi * frequency / sample_rate

        # FIR filters
        self.fir1_index = 0
        self._init_filters()

        # Symbol timing recovery
        self.syncbuf_size = 16 if self.symbollen >= 16 else self.symbollen
        self.bitclk = 0.0
        self.syncbuf = np.zeros(self.syncbuf_size)

        # Symbol accumulator - collect I/Q samples over each symbol period
        self.symbol_accum = complex(0.0, 0.0)
        self.symbol_count = 0

        # Phase tracking and differential decoding
        self.prevsymbol = complex(1.0, 0.0)
        self.phase = 0.0

        # Quality and DCD (Data Carrier Detect)
        self.quality_real = 0.0
        self.quality_imag = 0.0
        self.metric = 0.0
        self.dcd = False
        self.dcd_threshold = 0.5

        # DCD pattern detection (from fldigi)
        # dcdshreg tracks recent symbols for sync detection
        # For 8PSK: shift by 4 (symbits + 1) and OR with bits
        self.dcdshreg = 0
        self.symbits = 3  # 8PSK = 3 bits per symbol

        # Postamble detection - symbol 4 repeated produces 0x44444444
        # Use shorter patterns for faster detection
        self.DCD_ON_PATTERN = 0x00000000   # Preamble: all zeros from symbol 0
        self.DCD_OFF_PATTERNS = [
            0x44444444,  # 8 consecutive symbol 4s
            0x04444444,  # 7 consecutive (with leading 0)
            0x00444444,  # 6 consecutive
        ]
        # Track consecutive symbol 4s for alternative postamble detection
        self.consecutive_sym4 = 0

        # AFC (Automatic Frequency Control)
        self.freqerr = 0.0
        self.afcmetric = 0.0
        self.afc_decay = 50

        # Varicode decoder state
        self.varicode_decoder = MFSKVaricodeDecoder()

        # Callbacks
        self.text_callback: Optional[Callable[[str], None]] = None

        # Statistics
        self.symbols_received = 0
        self.chars_decoded = 0

    def _init_filters(self):
        """Initialize matched filters."""
        # Use shorter filters to reduce group delay
        # Original filter length was symbol_samples, which causes ~half-symbol delay
        # Reduce to quarter of symbol to minimize delay while still filtering
        filter_len = max(3, int(self.samples_per_symbol / (self.decimate1 * 4)))

        self.fir1_coeffs = np.ones(filter_len) / filter_len
        self.fir1_buffer = np.zeros(len(self.fir1_coeffs), dtype=complex)

        self.fir2_coeffs = np.ones(filter_len) / filter_len
        self.fir2_buffer = np.zeros(len(self.fir2_coeffs), dtype=complex)

    def set_text_callback(self, callback: Callable[[str], None]) -> None:
        """Set callback for decoded text output."""
        self.text_callback = callback

    def set_frequency(self, frequency: float) -> None:
        """Update carrier frequency (e.g., for AFC)."""
        self.frequency = frequency
        self.delta = 2.0 * np.pi * frequency / self.sample_rate

    def process(self, samples: np.ndarray) -> None:
        """Process incoming audio samples."""
        for sample in samples:
            self._process_sample(sample)

    def demodulate(self, samples: np.ndarray) -> str:
        """Demodulate audio samples to text (synchronous API)."""
        decoded_chars = []
        old_callback = self.text_callback
        self.text_callback = lambda char: decoded_chars.append(char)
        self.process(samples)
        self.text_callback = old_callback
        return ''.join(decoded_chars)

    def _process_sample(self, sample: float) -> None:
        """Process a single audio sample."""
        # Step 1: Mix with NCO to downconvert to baseband
        # Standard quadrature demodulation: multiply by cos and sin references
        # After lowpass filtering: Re{z} = I, Im{z} = Q
        z = complex(sample * np.cos(self.phase_acc), sample * np.sin(self.phase_acc))

        # Update NCO phase
        self.phase_acc += self.delta
        if self.phase_acc > 2.0 * np.pi:
            self.phase_acc -= 2.0 * np.pi

        # Step 2: First FIR filter with decimation
        self.fir1_buffer = np.roll(self.fir1_buffer, 1)
        self.fir1_buffer[0] = z

        self.fir1_index += 1

        # Only process every Nth sample (decimation)
        if self.fir1_index >= self.decimate1:
            self.fir1_index = 0

            # Apply FIR1 filter
            z_fir1 = np.sum(self.fir1_buffer * self.fir1_coeffs)

            # Step 3: Second FIR filter
            self.fir2_buffer = np.roll(self.fir2_buffer, 1)
            self.fir2_buffer[0] = z_fir1
            z_fir2 = np.sum(self.fir2_buffer * self.fir2_coeffs)

            # Step 4: Symbol timing recovery
            self._symbol_timing_recovery(z_fir2)

    def _symbol_timing_recovery(self, z: complex) -> None:
        """Symbol timing recovery using syncbuf."""
        # Fill syncbuf with rectified signal magnitude
        idx = int(self.bitclk)
        if idx < 0 or idx >= len(self.syncbuf):
            idx = 0

        # Accumulate samples from the last quarter of the symbol period
        # (around 75-100% of symbol) - this is where the raised cosine
        # transition is most complete and the phase is most stable
        bitsteps = self.syncbuf_size
        quarter_start = (bitsteps * 3) // 4  # Start at 75%
        if idx >= quarter_start:
            self.symbol_accum += z
            self.symbol_count += 1

        # Update syncbuf with exponential averaging
        self.syncbuf[idx] = 0.8 * self.syncbuf[idx] + 0.2 * abs(z)

        # Calculate timing error from early vs late halves
        symsteps = bitsteps // 2

        sum_diff = 0.0
        sum_amp = 0.0

        for i in range(symsteps):
            sum_diff += self.syncbuf[i] - self.syncbuf[i + symsteps]
            sum_amp += self.syncbuf[i] + self.syncbuf[i + symsteps]

        # Normalize by amplitude
        if sum_amp > 1e-10:
            timing_error = sum_diff / sum_amp
        else:
            timing_error = 0.0

        # Adjust bit clock based on timing error (reduced gain for stability)
        self.bitclk -= timing_error / (8.0 * 16 / bitsteps)
        self.bitclk += 1.0

        # Wrap bit clock
        if self.bitclk < 0:
            self.bitclk += bitsteps

        # When bitclk wraps around, we have a complete symbol
        if self.bitclk >= bitsteps:
            self.bitclk -= bitsteps

            # Use accumulated symbol value (average over symbol period)
            if self.symbol_count > 0:
                symbol_value = self.symbol_accum / self.symbol_count
                self._rx_symbol(symbol_value)

            # Reset accumulator for next symbol
            self.symbol_accum = complex(0.0, 0.0)
            self.symbol_count = 0

    def _rx_symbol(self, symbol: complex) -> None:
        """Process received symbol."""
        self.symbols_received += 1

        # Differential phase detection
        phase_sample = np.conj(self.prevsymbol) * symbol
        self.phase = np.angle(phase_sample)

        # Update previous symbol
        self.prevsymbol = symbol

        # Align RX constellation to TX constellation (non-FEC 8PSK)
        # From fldigi: phase -= M_PI for non-FEC 8PSK
        self.phase -= np.pi

        # Ensure phase is in [0, 2π)
        if self.phase < 0:
            self.phase += 2.0 * np.pi

        # 8PSK: map phase to 3-bit symbol (0-7)
        # Divide circle into 8 equal sectors
        bits = int((self.phase / (np.pi / 4.0)) + 0.5) & 7

        # Update quality metric
        n = 8  # Number of constellation points
        cval = np.cos(n * self.phase)
        sval = np.sin(n * self.phase)

        decay = 50 * 4  # 8PSK uses 4x decay
        attack = 50 * 2  # 8PSK uses 2x attack
        self.quality_real = self._decayavg(
            self.quality_real, cval, cval > self.quality_real, attack, decay
        )
        self.quality_imag = self._decayavg(
            self.quality_imag, sval, sval > self.quality_real, attack, decay
        )

        self.metric = 100.0 * (self.quality_real**2 + self.quality_imag**2)

        # Update DCD pattern register (from fldigi)
        # dcdshreg = (dcdshreg << (symbits + 1)) | bits
        self.dcdshreg = ((self.dcdshreg << (self.symbits + 1)) | bits) & 0xFFFFFFFF

        # DCD (Data Carrier Detect) - pattern-based detection
        self._update_dcd(bits)

        # AFC (Automatic Frequency Control)
        if self.afc_enabled:
            self._update_afc(bits, n)

        # Decode 3 bits per symbol (LSB first, like fldigi)
        for i in range(3):
            bit = (bits >> i) & 1
            self._rx_bit(bit)

    def _decayavg(
        self, avg: float, value: float, attack_mode: bool, attack: float, decay: float
    ) -> float:
        """Exponential moving average with attack/decay."""
        if attack_mode:
            return (avg * (attack - 1.0) + value) / attack
        else:
            return (avg * (decay - 1.0) + value) / decay

    def _update_dcd(self, bits: int) -> None:
        """
        Update DCD (Data Carrier Detect) based on symbol patterns.

        From fldigi psk.cxx:
        - 8PSK DCD ON: dcdshreg == 0x00000000 (preamble zeros from symbol 0)
        - 8PSK DCD OFF: dcdshreg matches postamble pattern (symbol 4 repeated)
        - Also use metric/squelch as fallback

        When DCD transitions to ON, reset the varicode decoder to clear
        any garbage bits accumulated during preamble.
        """
        new_dcd = self.dcd

        # Track consecutive symbol 4s for postamble detection
        if bits == 4:
            self.consecutive_sym4 += 1
        else:
            self.consecutive_sym4 = 0

        # Check for DCD ON pattern (preamble zeros)
        if self.dcdshreg == self.DCD_ON_PATTERN:
            new_dcd = True
            self.consecutive_sym4 = 0  # Reset counter

        # Check for DCD OFF patterns (postamble)
        elif self.dcdshreg in self.DCD_OFF_PATTERNS:
            new_dcd = False

        # Alternative: detect 2+ consecutive symbol 4s (postamble starts)
        elif self.consecutive_sym4 >= 2:
            new_dcd = False

        # Fallback to metric-based DCD if squelch enabled
        elif self.squelch_enabled:
            new_dcd = self.metric > self.dcd_threshold

        # If squelch disabled, just stay with current state after initial sync
        # (don't set dcd=True unconditionally to avoid preamble garbage)

        # Handle DCD transitions - check against current self.dcd
        if new_dcd and not self.dcd:
            # DCD just turned ON - reset varicode decoder to clear preamble garbage
            self.varicode_decoder.reset()
            self.consecutive_sym4 = 0

        self.dcd = new_dcd

    def _update_afc(self, bits: int, n: int) -> None:
        """Update automatic frequency control."""
        # Calculate quality metric for AFC
        quality_norm = self.quality_real**2 + self.quality_imag**2
        self.afcmetric = (self.afcmetric * (self.afc_decay - 1.0) + quality_norm) / self.afc_decay

        # Only do AFC if we have good signal
        if self.afcmetric < 0.05:
            return

        # Calculate frequency error from phase
        # For 8PSK, target phase is bits * pi/4
        target_phase = bits * np.pi / 4.0
        error = self.phase - target_phase

        # Wrap error to [-pi/2, pi/2]
        while error > np.pi / 2.0:
            error -= 2.0 * np.pi
        while error < -np.pi / 2.0:
            error += 2.0 * np.pi

        # Limit error range
        if abs(error) > np.pi / 2.0:
            return

        # Convert phase error to frequency error
        error_hz = error * self.sample_rate / (2.0 * np.pi * self.symbollen)

        # Bandwidth limit
        sc_bw = self.baud * 2
        dcdbits = int(self.baud * 1.024)  # From 8PSK encoder
        if abs(error_hz) < sc_bw:
            self.freqerr = error_hz / dcdbits
            new_freq = self.frequency - self.freqerr
            self.set_frequency(new_freq)

    def _rx_bit(self, bit: int) -> None:
        """Process received bit through MFSK varicode decoder."""
        # Process bit through fldigi-compatible varicode decoder
        char_code = self.varicode_decoder.rx_bit(bit)

        if char_code is not None and char_code != 0:
            # Successfully decoded a character (ignore NUL)
            if self.dcd and self.text_callback:
                char = chr(char_code)
                self.text_callback(char)
                self.chars_decoded += 1

    def get_stats(self) -> dict:
        """Get decoder statistics."""
        return {
            'symbols_received': self.symbols_received,
            'chars_decoded': self.chars_decoded,
            'metric': self.metric,
            'dcd': self.dcd,
            'frequency': self.frequency,
            'freqerr': self.freqerr,
        }

    def reset(self) -> None:
        """Reset decoder state."""
        self.phase_acc = 0.0
        self.bitclk = 0.0
        self.syncbuf = np.zeros(self.syncbuf_size)
        self.prevsymbol = complex(1.0, 0.0)
        self.phase = 0.0
        self.quality_real = 0.0
        self.quality_imag = 0.0
        self.metric = 0.0
        self.dcd = False
        self.dcdshreg = 0
        self.consecutive_sym4 = 0
        self.freqerr = 0.0
        self.afcmetric = 0.0
        self.varicode_decoder.reset()
        self.fir1_buffer = np.zeros(len(self.fir1_coeffs), dtype=complex)
        self.fir2_buffer = np.zeros(len(self.fir2_coeffs), dtype=complex)
        self.symbols_received = 0
        self.chars_decoded = 0


# Convenience functions for common 8PSK modes


def EightPSK_125_Decoder(
    sample_rate: float = 8000.0,
    frequency: float = 1000.0,
    afc_enabled: bool = True,
    squelch_enabled: bool = True,
) -> EightPSKDecoder:
    """Create an 8PSK125 decoder (125 baud, non-FEC)."""
    return EightPSKDecoder(
        baud=125,
        sample_rate=sample_rate,
        frequency=frequency,
        afc_enabled=afc_enabled,
        squelch_enabled=squelch_enabled,
    )


def EightPSK_250_Decoder(
    sample_rate: float = 8000.0,
    frequency: float = 1000.0,
    afc_enabled: bool = True,
    squelch_enabled: bool = True,
) -> EightPSKDecoder:
    """Create an 8PSK250 decoder (250 baud, non-FEC)."""
    return EightPSKDecoder(
        baud=250,
        sample_rate=sample_rate,
        frequency=frequency,
        afc_enabled=afc_enabled,
        squelch_enabled=squelch_enabled,
    )


def EightPSK_500_Decoder(
    sample_rate: float = 8000.0,
    frequency: float = 1000.0,
    afc_enabled: bool = True,
    squelch_enabled: bool = True,
) -> EightPSKDecoder:
    """Create an 8PSK500 decoder (500 baud, non-FEC)."""
    return EightPSKDecoder(
        baud=500,
        sample_rate=sample_rate,
        frequency=frequency,
        afc_enabled=afc_enabled,
        squelch_enabled=squelch_enabled,
    )


def EightPSK_1000_Decoder(
    sample_rate: float = 8000.0,
    frequency: float = 1000.0,
    afc_enabled: bool = True,
    squelch_enabled: bool = True,
) -> EightPSKDecoder:
    """Create an 8PSK1000 decoder (1000 baud, non-FEC)."""
    return EightPSKDecoder(
        baud=1000,
        sample_rate=sample_rate,
        frequency=frequency,
        afc_enabled=afc_enabled,
        squelch_enabled=squelch_enabled,
    )
