"""
8PSK FEC (8-Phase Shift Keying with Forward Error Correction) Decoder Implementation

Based on fldigi's 8PSK FEC decoder (fldigi/src/psk/psk.cxx).
Supports decoding 8PSK125F, 8PSK125FL, 8PSK250F, 8PSK250FL, 8PSK500F, 8PSK1000F, 8PSK1200F.

Decoder Architecture:
1. Baseband conversion - Mix with NCO to downconvert to baseband
2. Matched filtering - Two-stage FIR filters with decimation
3. Symbol timing recovery - Syncbuf-based timing loop
4. Phase detection - Compute phase of each symbol
5. Soft symbol generation - Map phase to soft bits using Gray mapping
6. Deinterleaving - Reverse bit interleaving
7. Viterbi decoding - Decode convolutional code
8. Varicode decoding - Convert bit stream to text (MFSK varicode)

Reference: fldigi/src/psk/psk.cxx (rx_process, rx_symbol, rx_pskr)
"""

import numpy as np
from typing import Optional, Callable
from ..core.viterbi import ViterbiDecoder, create_8psk_k13_decoder, create_8psk_k16_decoder
from ..core.interleave import Interleave, INTERLEAVE_REV
from ..varicode.mfsk_varicode import MFSKVaricodeDecoder


class EightPSKFECDecoder:
    """
    8PSK FEC decoder for all 8PSK FEC modes.

    This decoder handles 8-phase shift keying with FEC, including:
    - Gray-mapped constellation for optimal soft decoding
    - Convolutional decoding with Viterbi algorithm
    - Bit deinterleaving for burst error protection
    - Puncturing for higher-rate modes (500F, 1000F, 1200F)

    Args:
        baud: Symbol rate in baud (125, 250, 500, 1000, 1200)
        sample_rate: Audio sample rate in Hz (default: 8000)
        frequency: Carrier frequency in Hz (default: 1000)
        long_interleave: Use long interleave (FL modes)
        use_k16: Force K=16 encoder (auto-select if None)
        afc_enabled: Enable automatic frequency correction (default: True)
        squelch_enabled: Enable squelch/DCD (default: True)

    Example:
        >>> decoder = EightPSKFECDecoder(baud=250, sample_rate=8000, frequency=1000)
        >>> decoder.set_text_callback(lambda text: print(text, end=''))
        >>> decoder.process(audio_samples)
    """

    # Gray-mapped 8PSK soft bits table
    # Indexed by phase position (0-7 = 0°, 45°, 90°, ..., 315°)
    # Each row contains soft bits [bit0, bit1, bit2] for the Gray-coded symbol at that phase
    # Values: 25 = likely 0, 230 = likely 1, 128 = uncertain
    # Phase to symbol mapping (Gray constellation):
    #   0° -> symbol 0 (000), 45° -> symbol 1 (001), 90° -> symbol 3 (011),
    #   135° -> symbol 2 (010), 180° -> symbol 6 (110), 225° -> symbol 7 (111),
    #   270° -> symbol 5 (101), 315° -> symbol 4 (100)
    GRAYMAPPED_8PSK_SOFTBITS = np.array(
        [
            [25, 25, 25],    # Phase 0° = symbol 0 (bits 000)
            [230, 25, 25],   # Phase 45° = symbol 1 (bits 001)
            [230, 230, 25],  # Phase 90° = symbol 3 (bits 011)
            [25, 230, 25],   # Phase 135° = symbol 2 (bits 010)
            [25, 230, 230],  # Phase 180° = symbol 6 (bits 110)
            [230, 230, 230], # Phase 225° = symbol 7 (bits 111)
            [230, 25, 230],  # Phase 270° = symbol 5 (bits 101)
            [25, 25, 230],   # Phase 315° = symbol 4 (bits 100)
        ],
        dtype=np.uint8,
    )

    def __init__(
        self,
        baud: float = 125,
        sample_rate: float = 8000.0,
        frequency: float = 1000.0,
        long_interleave: bool = False,
        use_k16: bool = None,
        afc_enabled: bool = True,
        squelch_enabled: bool = True,
    ):
        """Initialize 8PSK FEC decoder."""
        self.baud = baud
        self.sample_rate = sample_rate
        self.frequency = frequency
        self.afc_enabled = afc_enabled
        self.squelch_enabled = squelch_enabled

        # Determine mode configuration
        if baud == 125:
            self.mode_name = "8PSK125FL" if long_interleave else "8PSK125F"
            self._idepth = 384
            self._dcdbits = 128
            self._use_k16 = (
                False if long_interleave else (use_k16 if use_k16 is not None else True)
            )
        elif baud == 250:
            self.mode_name = "8PSK250FL" if long_interleave else "8PSK250F"
            self._idepth = 512
            self._dcdbits = 256
            self._use_k16 = (
                False if long_interleave else (use_k16 if use_k16 is not None else True)
            )
        elif baud == 500:
            self.mode_name = "8PSK500F"
            self._idepth = 640
            self._dcdbits = 512
            self._use_k16 = False
            self._puncturing = True
        elif baud == 1000:
            self.mode_name = "8PSK1000F"
            self._idepth = 512
            self._dcdbits = 1024
            self._use_k16 = False
            self._puncturing = True
        elif baud == 1200:
            self.mode_name = "8PSK1200F"
            self._idepth = 512
            self._dcdbits = 2048
            self._use_k16 = False
            self._puncturing = True
        else:
            raise ValueError(f"Unsupported baud rate: {baud}")

        if not hasattr(self, "_puncturing"):
            self._puncturing = False

        # Calculate symbol parameters
        self.samples_per_symbol = sample_rate / baud
        self.symbollen = int(self.samples_per_symbol)

        # Determine decimation factor
        if baud <= 128:
            self.decimate1 = 4
        elif baud <= 256:
            self.decimate1 = 2
        else:
            self.decimate1 = 1
        self.decimate2 = 1

        # NCO for carrier mixing
        self.phase_acc = 0.0
        self.delta = 2.0 * np.pi * frequency / sample_rate

        # FIR filters
        self.fir1_index = 0
        self._init_filters()

        # Symbol timing recovery
        self.bitclk = 0.0
        self.syncbuf_size = 16 if self.symbollen >= 16 else self.symbollen
        self.syncbuf = np.zeros(self.syncbuf_size)

        # Phase tracking
        self.prevsymbol = complex(1.0, 0.0)
        self.phase = 0.0

        # Symbol accumulation for better phase estimation
        self.symbol_accum = complex(0.0, 0.0)
        self.symbol_count = 0

        # Quality and DCD
        self.quality_real = 0.0
        self.quality_imag = 0.0
        self.metric = 0.0
        self.dcd = False
        self.dcd_threshold = 0.5

        # Sample-level signal detection - gates processing before filter corruption
        # This is critical for handling noise during leading silence
        self._sample_signal_detected = False
        self._sample_power_window = int(self.samples_per_symbol * 2)  # ~2 symbol periods
        self._sample_power_buffer = np.zeros(self._sample_power_window)
        self._sample_power_idx = 0
        self._sample_power_sum = 0.0
        self._noise_floor = 0.0
        self._noise_floor_samples = 0
        self._noise_floor_window = int(self.sample_rate * 0.1)  # 100ms for noise estimation
        self._signal_threshold_db = 10.0  # Signal must be 10dB above noise floor
        self._signal_onset_count = 0  # Consecutive high-power samples
        self._signal_onset_required = int(self.samples_per_symbol)  # Require 1 symbol period of signal

        # Symbol-level signal detection state (kept for soft puncturing)
        self._signal_detected = False
        self._signal_threshold = 0.05  # Minimum amplitude to consider as signal
        self._signal_history = []  # Track recent amplitudes
        self._signal_history_len = 16  # Number of symbols to track
        self._amplitude_avg = 0.0
        self._amplitude_peak = 0.0
        self._seen_low_amplitude = False  # Track if we've ever seen silence

        # AFC
        self.freqerr = 0.0
        self.afcmetric = 0.0
        self.afc_decay = 50

        # Create Viterbi decoder
        if self._use_k16:
            self.viterbi_decoder = create_8psk_k16_decoder()
        else:
            self.viterbi_decoder = create_8psk_k13_decoder()

        # Create deinterleaver
        self.deinterleaver = Interleave(size=2, depth=self._idepth, direction=INTERLEAVE_REV)

        # Soft symbol pair buffer
        self.symbolpair = [128, 128]  # Neutral soft symbols
        self.rxbitstate = 0

        # FEC metrics
        self.fecmet = 0.0
        self.fecmet2 = -9999.0  # Second decoder (for bit sync voting)

        # Second Viterbi decoder for bit sync voting (not used for punctured modes)
        if not self._puncturing:
            if self._use_k16:
                self.viterbi_decoder2 = create_8psk_k16_decoder()
            else:
                self.viterbi_decoder2 = create_8psk_k13_decoder()
            self.deinterleaver2 = Interleave(size=2, depth=self._idepth, direction=INTERLEAVE_REV)
        else:
            self.viterbi_decoder2 = None
            self.deinterleaver2 = None

        # Varicode decoder state
        self.varicode_decoder = MFSKVaricodeDecoder()

        # Callbacks
        self.text_callback: Optional[Callable[[str], None]] = None

        # Statistics
        self.symbols_received = 0
        self.chars_decoded = 0

        # Phase quality for soft decoding
        self.last_phase_quality = 0.0

    def _init_filters(self):
        """Initialize matched filters."""
        # Use shorter filters to reduce group delay (matching non-FEC decoder)
        # Longer filters cause phase smoothing across symbol transitions
        filter_len = max(3, int(self.samples_per_symbol / (self.decimate1 * 4)))

        self.fir1_coeffs = np.ones(filter_len) / filter_len
        self.fir1_buffer = np.zeros(len(self.fir1_coeffs), dtype=complex)

        self.fir2_coeffs = np.ones(filter_len) / filter_len
        self.fir2_buffer = np.zeros(len(self.fir2_coeffs), dtype=complex)

    def _reset_fec_pipeline(self) -> None:
        """Reset FEC decoder pipeline when signal is first detected.

        This clears any garbage that may have accumulated in the deinterleaver
        and Viterbi decoder during silence periods.

        Note: We do NOT reset filters or prevsymbol here:
        - Filters: Resetting would lose the current symbol being processed
        - prevsymbol: Should be set explicitly by the caller for clean differential detection
        """
        # Reset Viterbi decoder
        self.viterbi_decoder.reset()
        if self.viterbi_decoder2:
            self.viterbi_decoder2.reset()

        # Flush deinterleaver
        self.deinterleaver.flush()
        if self.deinterleaver2:
            self.deinterleaver2.flush()

        # Reset symbol pair buffer
        self.symbolpair = [128, 128]
        self.rxbitstate = 0

        # Reset FEC metrics
        self.fecmet = 0.0
        self.fecmet2 = -9999.0

        # Reset varicode decoder
        self.varicode_decoder.reset()

        # Reset quality tracking
        self.last_phase_quality = 0.0

    def _reset_sample_level_state(self) -> None:
        """Reset filter and timing state when signal is first detected.

        This clears any garbage that accumulated in the filters during noisy
        silence periods, ensuring clean processing starts with the actual signal.
        """
        # Reset FIR filter buffers
        self.fir1_buffer = np.zeros(len(self.fir1_coeffs), dtype=complex)
        self.fir2_buffer = np.zeros(len(self.fir2_coeffs), dtype=complex)
        self.fir1_index = 0

        # Reset symbol timing
        self.bitclk = 0.0
        self.syncbuf = np.zeros(self.syncbuf_size)
        self.symbol_accum = complex(0.0, 0.0)
        self.symbol_count = 0

        # Reset phase tracking
        self.prevsymbol = complex(1.0, 0.0)
        self.phase = 0.0

        # Reset symbol-level signal detection (will re-detect from clean state)
        self._signal_detected = False
        self._signal_history = []
        self._amplitude_avg = 0.0
        self._amplitude_peak = 0.0
        self._seen_low_amplitude = False

        # Also reset FEC pipeline
        self._reset_fec_pipeline()

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
        # Sample-level signal detection (before any filtering)
        # This prevents noise during silence from corrupting filter state
        sample_power = sample * sample

        # Update sliding window power estimate
        old_power = self._sample_power_buffer[self._sample_power_idx]
        self._sample_power_buffer[self._sample_power_idx] = sample_power
        self._sample_power_sum = self._sample_power_sum - old_power + sample_power
        self._sample_power_idx = (self._sample_power_idx + 1) % self._sample_power_window

        current_power = self._sample_power_sum / self._sample_power_window

        if not self._sample_signal_detected:
            # Thresholds for sample-level signal detection
            # Low noise threshold: below this, treat as silence and process through filters
            # (amplitude ~0.02 -> power ~0.0004)
            low_noise_threshold = 0.0004

            # Minimum absolute signal power (amplitude ~0.1 -> power ~0.01)
            # Signal must be at least this strong to be considered signal
            min_absolute_signal = 0.01

            # Relative threshold: signal must be X dB above noise floor
            relative_threshold_db = 10.0  # 10 dB above noise
            relative_threshold_linear = 10.0 ** (relative_threshold_db / 10.0)  # ~10x

            # Calculate dynamic signal threshold
            if self._noise_floor > low_noise_threshold:
                # Have significant noise - require signal to be well above it
                signal_threshold = max(min_absolute_signal, self._noise_floor * relative_threshold_linear)
            else:
                # Low/no noise - use minimum absolute threshold
                signal_threshold = min_absolute_signal

            if current_power < low_noise_threshold:
                # Very low power (essentially silence) - safe to process through filters
                self._noise_floor_samples += 1
                # Slowly decay noise floor toward current (low) level
                alpha = 0.1 if self._noise_floor_samples > 10 else 1.0 / self._noise_floor_samples
                self._noise_floor = (1 - alpha) * self._noise_floor + alpha * current_power
                self._signal_onset_count = 0
                # Fall through to normal processing

            elif current_power > signal_threshold:
                # Power significantly above noise floor - likely signal
                self._signal_onset_count += 1

                # Check if we should confirm signal detection
                if self._noise_floor_samples < self._sample_power_window:
                    # Haven't seen much silence, assume signal from start
                    if self._signal_onset_count >= min(8, self._sample_power_window):
                        self._sample_signal_detected = True
                elif self._signal_onset_count >= self._signal_onset_required:
                    # Seen silence/noise, now signal is sustained - start processing
                    self._sample_signal_detected = True
                    # Reset FEC pipeline but NOT filters
                    self._reset_fec_pipeline()
                    # Reset symbol-level detection state
                    self._signal_detected = False
                    self._signal_history = []
                    self._seen_low_amplitude = False

                # Fall through to normal processing (always process signal samples)

            else:
                # Moderate power (noise) - skip processing to avoid corrupting filters
                self._signal_onset_count = 0
                self._noise_floor_samples += 1
                # Update noise floor estimate
                alpha = 0.1 if self._noise_floor_samples > 10 else 1.0 / self._noise_floor_samples
                self._noise_floor = (1 - alpha) * self._noise_floor + alpha * current_power

                # Skip filter processing during noisy silence
                self.phase_acc += self.delta
                if self.phase_acc > 2.0 * np.pi:
                    self.phase_acc -= 2.0 * np.pi
                return

        # Mix with NCO to downconvert to baseband
        z = complex(sample * np.cos(self.phase_acc), sample * np.sin(self.phase_acc))

        # Update NCO phase
        self.phase_acc += self.delta
        if self.phase_acc > 2.0 * np.pi:
            self.phase_acc -= 2.0 * np.pi

        # First FIR filter with decimation
        self.fir1_buffer = np.roll(self.fir1_buffer, 1)
        self.fir1_buffer[0] = z
        self.fir1_index += 1

        if self.fir1_index >= self.decimate1:
            self.fir1_index = 0
            z_fir1 = np.sum(self.fir1_buffer * self.fir1_coeffs)

            # Second FIR filter
            self.fir2_buffer = np.roll(self.fir2_buffer, 1)
            self.fir2_buffer[0] = z_fir1
            z_fir2 = np.sum(self.fir2_buffer * self.fir2_coeffs)

            # Symbol timing recovery
            self._symbol_timing_recovery(z_fir2)

    def _symbol_timing_recovery(self, z: complex) -> None:
        """Symbol timing recovery using syncbuf with sample accumulation."""
        idx = int(self.bitclk)
        if idx < 0 or idx >= len(self.syncbuf):
            idx = 0

        self.syncbuf[idx] = 0.8 * self.syncbuf[idx] + 0.2 * abs(z)

        bitsteps = self.syncbuf_size
        symsteps = bitsteps // 2

        # Accumulate samples from the last quarter of the symbol period
        # for better phase estimation (matching non-FEC decoder fix)
        quarter_start = (bitsteps * 3) // 4
        if idx >= quarter_start:
            self.symbol_accum += z
            self.symbol_count += 1

        sum_diff = 0.0
        sum_amp = 0.0
        for i in range(symsteps):
            sum_diff += self.syncbuf[i] - self.syncbuf[i + symsteps]
            sum_amp += self.syncbuf[i] + self.syncbuf[i + symsteps]

        if sum_amp > 1e-10:
            timing_error = sum_diff / sum_amp
        else:
            timing_error = 0.0

        # Reduced timing loop gain for stability
        self.bitclk -= timing_error / (8.0 * 16 / bitsteps)
        self.bitclk += 1.0

        if self.bitclk < 0:
            self.bitclk += bitsteps

        if self.bitclk >= bitsteps:
            self.bitclk -= bitsteps
            # Use accumulated symbol if we have samples
            if self.symbol_count > 0:
                symbol = self.symbol_accum / self.symbol_count
            else:
                symbol = z
            self._rx_symbol(symbol)
            # Reset accumulator for next symbol
            self.symbol_accum = complex(0.0, 0.0)
            self.symbol_count = 0

    def _rx_symbol(self, symbol: complex) -> None:
        """Process received symbol."""
        self.symbols_received += 1

        # Calculate signal amplitude
        amplitude = abs(symbol)

        # Track peak amplitude with slow decay
        if amplitude > self._amplitude_peak:
            self._amplitude_peak = amplitude
        else:
            self._amplitude_peak = 0.99 * self._amplitude_peak + 0.01 * amplitude

        # Track average amplitude
        self._amplitude_avg = 0.95 * self._amplitude_avg + 0.05 * amplitude

        # Signal detection: track recent symbol amplitudes
        self._signal_history.append(amplitude)
        if len(self._signal_history) > self._signal_history_len:
            self._signal_history.pop(0)

        # Track if we've ever seen low amplitude (silence)
        if amplitude < self._signal_threshold * 0.5:
            self._seen_low_amplitude = True

        # Simple signal gating: skip FEC processing during silence
        # This prevents garbage from going into the deinterleaver during silent periods
        if not self._signal_detected:
            # If we've never seen low amplitude, signal was present from the start
            if not self._seen_low_amplitude:
                self._signal_detected = True
            elif amplitude > self._signal_threshold:
                # Signal started - begin processing
                self._signal_detected = True
                # Don't return - process this symbol
            else:
                # Still in silence - skip processing entirely
                return

        # Differential phase detection
        phase_sample = np.conj(self.prevsymbol) * symbol
        self.phase = np.angle(phase_sample)
        # Only update prevsymbol if current symbol has meaningful amplitude
        # Use a low threshold (0.01) to:
        # - Prevent near-zero symbols during pure silence from corrupting phase
        # - Allow noise dithering during noisy silence (helps with sync)
        if amplitude > 0.01:
            self.prevsymbol = symbol

        # Ensure phase is in [0, 2π)
        if self.phase < 0:
            self.phase += 2.0 * np.pi

        # 8PSK: map phase to 3-bit symbol (0-7)
        n = 8
        bits = int((self.phase / (np.pi / 4.0)) + 0.5) & 7

        # Update quality metric
        cval = np.cos(n * self.phase)
        sval = np.sin(n * self.phase)

        decay = 50 * 4  # 8PSK uses 4x decay
        attack = 50 * 2  # 8PSK uses 2x attack

        if cval > self.quality_real:
            self.quality_real = (self.quality_real * (attack - 1.0) + cval) / attack
        else:
            self.quality_real = (self.quality_real * (decay - 1.0) + cval) / decay

        if sval > self.quality_imag:
            self.quality_imag = (self.quality_imag * (attack - 1.0) + sval) / attack
        else:
            self.quality_imag = (self.quality_imag * (decay - 1.0) + sval) / decay

        self.metric = 100.0 * (self.quality_real**2 + self.quality_imag**2)

        # DCD
        if self.squelch_enabled:
            self.dcd = self.metric > self.dcd_threshold
        else:
            self.dcd = True

        # AFC
        if self.afc_enabled and self.dcd:
            self._update_afc(bits, n)

        # Soft-decode 8PSK symbol to 3 soft bits
        # Calculate phase quality for soft decoding
        phase_quality = abs(np.cos((n / 2) * self.phase))
        phase_quality = (phase_quality + self.last_phase_quality) / 2.0
        self.last_phase_quality = phase_quality

        soft_quality_error = int(128 - (128 * phase_quality))

        # Check if we should puncture (signal too weak or noisy)
        soft_puncture = False

        # Puncture if amplitude is very low (silence or weak signal)
        # Compare against a fraction of peak to detect signal presence
        min_amplitude = 0.02  # Absolute minimum amplitude
        if self._amplitude_peak > 0.1:
            # Dynamic threshold: require at least 20% of peak
            amplitude_threshold = max(min_amplitude, 0.2 * self._amplitude_peak)
        else:
            amplitude_threshold = min_amplitude

        if amplitude < amplitude_threshold:
            soft_puncture = True
        elif soft_quality_error > 255 - 25:
            soft_puncture = True
        elif soft_quality_error < 128 // 3:
            # Keep minimum uncertainty to avoid edge cases in Viterbi decoder
            # when soft bits are too confident (prevents numerical issues)
            soft_quality_error = max(5, soft_quality_error)
        elif soft_quality_error > 128 - (128 // 8):
            soft_puncture = True
        else:
            soft_quality_error //= 2

        if soft_puncture:
            # Send neutral symbols (128 = don't know)
            for i in range(3):
                self._rx_pskr(128)
        else:
            # Use Gray-mapped soft bits
            bitindex = int(bits) & 7
            softbits = self.GRAYMAPPED_8PSK_SOFTBITS[bitindex]

            # Send 3 soft bits (LSB first to match encoder packing)
            # Encoder packs: bit0=a0, bit1=a1, bit2=b0 from FEC pairs (a0a1), (b0b1)
            for i in range(3):
                if softbits[i] > 128:  # Soft-one
                    self._rx_pskr(softbits[i] - soft_quality_error)
                else:  # Soft-zero
                    self._rx_pskr(softbits[i] + soft_quality_error)

        # Handle puncturing for high-rate modes
        if self._puncturing:
            self._rx_pskr(128)  # Recover punctured high bit

    def _rx_pskr(self, soft_symbol: int) -> None:
        """Process soft symbol through deinterleaver and Viterbi decoder."""
        # Accumulate symbol pair
        self.symbolpair[1] = self.symbolpair[0]
        self.symbolpair[0] = soft_symbol

        if self.rxbitstate == 0:
            self.rxbitstate += 1
            # Skip the odd offset - only process even offsets with primary decoder
            # TODO: Implement proper bit sync voting that compares metrics
            # and only outputs from the better decoder
            return

        else:
            # Primary decoder
            self.rxbitstate = 0
            twosym = np.array([self.symbolpair[0], self.symbolpair[1]], dtype=np.uint8)

            # Deinterleave
            if self.mode_name != "PSK63F":
                self.deinterleaver.symbols(twosym)

            # Reverse symbols
            twosym = [twosym[1], twosym[0]]

            # Viterbi decode
            metric = [0]
            decoded = self.viterbi_decoder.decode(twosym, metric)

            if decoded is not None:
                # Update metric
                self.fecmet = (self.fecmet * 19.0 + metric[0]) / 20.0

                # Decode 8 bits (chunksize=8)
                for i in range(7, -1, -1):
                    bit = (decoded >> i) & 1
                    self._rx_bit(bit)

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

    def _update_afc(self, bits: int, n: int) -> None:
        """Update automatic frequency control."""
        quality_norm = self.quality_real**2 + self.quality_imag**2
        self.afcmetric = (self.afcmetric * (self.afc_decay - 1.0) + quality_norm) / self.afc_decay

        if self.afcmetric < 0.05:
            return

        target_phase = bits * np.pi / 4.0
        error = self.phase - target_phase

        while error > np.pi / 2.0:
            error -= 2.0 * np.pi
        while error < -np.pi / 2.0:
            error += 2.0 * np.pi

        if abs(error) > np.pi / 2.0:
            return

        error_hz = error * self.sample_rate / (2.0 * np.pi * self.symbollen)
        sc_bw = self.baud * 2

        if abs(error_hz) < sc_bw:
            self.freqerr = error_hz / self._dcdbits
            new_freq = self.frequency - self.freqerr
            self.set_frequency(new_freq)

    def get_stats(self) -> dict:
        """Get decoder statistics."""
        return {
            'symbols_received': self.symbols_received,
            'chars_decoded': self.chars_decoded,
            'metric': self.metric,
            'dcd': self.dcd,
            'frequency': self.frequency,
            'freqerr': self.freqerr,
            'fecmet': self.fecmet,
            'fecmet2': self.fecmet2,
        }

    def reset(self) -> None:
        """Reset decoder state."""
        self.phase_acc = 0.0
        self.bitclk = 0.0
        self.syncbuf = np.zeros(self.syncbuf_size)
        self.prevsymbol = complex(1.0, 0.0)
        self.phase = 0.0
        self.symbol_accum = complex(0.0, 0.0)
        self.symbol_count = 0
        self.quality_real = 0.0
        self.quality_imag = 0.0
        self.metric = 0.0
        self.dcd = False
        self.freqerr = 0.0
        self.afcmetric = 0.0
        self.varicode_decoder.reset()
        self.fir1_buffer = np.zeros(len(self.fir1_coeffs), dtype=complex)
        self.fir2_buffer = np.zeros(len(self.fir2_coeffs), dtype=complex)
        self.symbols_received = 0
        self.chars_decoded = 0
        self.viterbi_decoder.reset()
        if self.viterbi_decoder2:
            self.viterbi_decoder2.reset()
        self.deinterleaver.flush()
        if self.deinterleaver2:
            self.deinterleaver2.flush()
        self.symbolpair = [128, 128]
        self.rxbitstate = 0
        self.fecmet = 0.0
        self.fecmet2 = -9999.0
        self.last_phase_quality = 0.0
        # Reset sample-level signal detection state
        self._sample_signal_detected = False
        self._sample_power_buffer = np.zeros(self._sample_power_window)
        self._sample_power_idx = 0
        self._sample_power_sum = 0.0
        self._noise_floor = 0.0
        self._noise_floor_samples = 0
        self._signal_onset_count = 0
        # Reset symbol-level signal detection state
        self._signal_detected = False
        self._signal_history = []
        self._amplitude_avg = 0.0
        self._amplitude_peak = 0.0
        self._seen_low_amplitude = False


# Convenience functions for common 8PSK FEC modes


def EightPSK_125F_Decoder(
    sample_rate: float = 8000.0,
    frequency: float = 1000.0,
    afc_enabled: bool = True,
    squelch_enabled: bool = True,
) -> EightPSKFECDecoder:
    """Create an 8PSK125F decoder (125 baud, K=16 FEC)."""
    return EightPSKFECDecoder(
        baud=125,
        sample_rate=sample_rate,
        frequency=frequency,
        long_interleave=False,
        afc_enabled=afc_enabled,
        squelch_enabled=squelch_enabled,
    )


def EightPSK_125FL_Decoder(
    sample_rate: float = 8000.0,
    frequency: float = 1000.0,
    afc_enabled: bool = True,
    squelch_enabled: bool = True,
) -> EightPSKFECDecoder:
    """Create an 8PSK125FL decoder (125 baud, K=13 FEC, long interleave)."""
    return EightPSKFECDecoder(
        baud=125,
        sample_rate=sample_rate,
        frequency=frequency,
        long_interleave=True,
        afc_enabled=afc_enabled,
        squelch_enabled=squelch_enabled,
    )


def EightPSK_250F_Decoder(
    sample_rate: float = 8000.0,
    frequency: float = 1000.0,
    afc_enabled: bool = True,
    squelch_enabled: bool = True,
) -> EightPSKFECDecoder:
    """Create an 8PSK250F decoder (250 baud, K=16 FEC)."""
    return EightPSKFECDecoder(
        baud=250,
        sample_rate=sample_rate,
        frequency=frequency,
        long_interleave=False,
        afc_enabled=afc_enabled,
        squelch_enabled=squelch_enabled,
    )


def EightPSK_250FL_Decoder(
    sample_rate: float = 8000.0,
    frequency: float = 1000.0,
    afc_enabled: bool = True,
    squelch_enabled: bool = True,
) -> EightPSKFECDecoder:
    """Create an 8PSK250FL decoder (250 baud, K=13 FEC, long interleave)."""
    return EightPSKFECDecoder(
        baud=250,
        sample_rate=sample_rate,
        frequency=frequency,
        long_interleave=True,
        afc_enabled=afc_enabled,
        squelch_enabled=squelch_enabled,
    )


def EightPSK_500F_Decoder(
    sample_rate: float = 8000.0,
    frequency: float = 1000.0,
    afc_enabled: bool = True,
    squelch_enabled: bool = True,
) -> EightPSKFECDecoder:
    """Create an 8PSK500F decoder (500 baud, K=13 FEC, 2/3 rate punctured)."""
    return EightPSKFECDecoder(
        baud=500,
        sample_rate=sample_rate,
        frequency=frequency,
        afc_enabled=afc_enabled,
        squelch_enabled=squelch_enabled,
    )


def EightPSK_1000F_Decoder(
    sample_rate: float = 8000.0,
    frequency: float = 1000.0,
    afc_enabled: bool = True,
    squelch_enabled: bool = True,
) -> EightPSKFECDecoder:
    """Create an 8PSK1000F decoder (1000 baud, K=13 FEC, 2/3 rate punctured)."""
    return EightPSKFECDecoder(
        baud=1000,
        sample_rate=sample_rate,
        frequency=frequency,
        afc_enabled=afc_enabled,
        squelch_enabled=squelch_enabled,
    )


def EightPSK_1200F_Decoder(
    sample_rate: float = 8000.0,
    frequency: float = 1000.0,
    afc_enabled: bool = True,
    squelch_enabled: bool = True,
) -> EightPSKFECDecoder:
    """Create an 8PSK1200F decoder (1200 baud, K=13 FEC, 2/3 rate punctured)."""
    return EightPSKFECDecoder(
        baud=1200,
        sample_rate=sample_rate,
        frequency=frequency,
        afc_enabled=afc_enabled,
        squelch_enabled=squelch_enabled,
    )
