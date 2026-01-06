"""
THROB Decoder Implementation.

Decodes THROB signals using dual-tone correlation and amplitude detection.

THROB is a dual-tone amplitude-modulated digital mode where each character
is represented by two simultaneous tones. The mode is highly resistant to
propagation-induced phase shifts and requires no carrier tracking.

The decoder uses:
- Hilbert transform for analytic signal creation
- Complex mixer for frequency translation to baseband
- FFT bandpass filtering
- Downsampling (32x)
- Correlation against pre-computed tone templates
- Dual-tone detection for symbol decoding
- Sync tracking for symbol timing alignment
- Optional AFC for frequency tracking

References:
    - fldigi/src/throb/throb.cxx
    - pydigi/modems/throb.py (transmitter)
"""

import numpy as np
from typing import Optional, Callable, Tuple
from scipy.signal import firwin, hilbert
from ..varicode.throb_varicode import (
    THROB_CHARSET,
    THROBX_CHARSET,
    THROB_TONE_PAIRS,
    THROBX_TONE_PAIRS,
)


class ThrobDecoder:
    """
    THROB decoder using dual-tone correlation and amplitude detection.

    Decodes THROB signals by correlating received symbols against pre-computed
    tone templates and detecting the two strongest tones.

    Args:
        mode: Throb mode ('throb1', 'throb2', 'throb4', 'throbx1', 'throbx2', 'throbx4')
        sample_rate: Audio sample rate in Hz (default: 8000, fixed for Throb)
        frequency: Center frequency in Hz (default: 1500)
        use_afc: Enable automatic frequency control (default: True)
        squelch: Squelch threshold in dB (default: 3.0)
        squelch_enabled: Enable squelch (default: True)
        text_callback: Optional callback for decoded characters

    Example:
        >>> decoder = ThrobDecoder(mode='throb1')
        >>> decoder.text_callback = lambda c: print(c, end='')
        >>> decoder.process(audio_samples)
    """

    # Tone frequencies (Hz relative to center frequency)
    # Reference: throb.cxx lines 941-944, throb.h lines 52-55
    THROB_TONE_FREQS_NAR = np.array([-32, -24, -16, -8, 0, 8, 16, 24, 32])
    THROB_TONE_FREQS_WID = np.array([-64, -48, -32, -16, 0, 16, 32, 48, 64])
    THROBX_TONE_FREQS_NAR = np.array(
        [-39.0625, -31.25, -23.4375, -15.625, -7.8125, 0, 7.8125, 15.625, 23.4375, 31.25, 39.0625]
    )
    THROBX_TONE_FREQS_WID = np.array(
        [-78.125, -62.5, -46.875, -31.25, -15.625, 0, 15.625, 31.25, 46.875, 62.5, 78.125]
    )

    # Symbol lengths at 8000 Hz sample rate
    # Reference: throb.h lines 42-44
    SYMLEN_1 = 8192  # ~1.024 seconds per symbol
    SYMLEN_2 = 4096  # ~0.512 seconds per symbol
    SYMLEN_4 = 2048  # ~0.256 seconds per symbol

    # Downsampling factor
    # Reference: throb.h line 40
    DOWN_SAMPLE = 32

    # Sample rate (fixed for Throb)
    # Reference: throb.h line 34
    THROB_SAMPLE_RATE = 8000

    def __init__(
        self,
        mode: str = "throb1",
        sample_rate: float = 8000.0,
        frequency: float = 1500.0,
        use_afc: bool = True,
        squelch: float = 3.0,
        squelch_enabled: bool = True,
        text_callback: Optional[Callable[[str], None]] = None,
    ):
        """Initialize THROB decoder."""
        self.mode = mode.lower()
        self.frequency = frequency
        self.use_afc = use_afc
        self.squelch = squelch
        self.squelch_enabled = squelch_enabled
        self.text_callback = text_callback

        # Warn if sample rate is not 8000 Hz
        if sample_rate != self.THROB_SAMPLE_RATE:
            print(
                f"Warning: Throb requires {self.THROB_SAMPLE_RATE} Hz sample rate. "
                f"Overriding to {self.THROB_SAMPLE_RATE} Hz."
            )
        self.sample_rate = self.THROB_SAMPLE_RATE

        # Determine mode parameters
        # Reference: throb.cxx lines 141-219
        self._setup_mode_params()

        # Create Hilbert filter for analytic signal
        # Reference: throb.cxx line 226-227
        # 37-tap Hilbert transformer
        self.hilbert_filter = self._create_hilbert_filter(37)

        # Create bandpass filter
        # Reference: throb.cxx line 229
        self.bandpass_filter = self._create_bandpass_filter()

        # Create sync filter (matched filter)
        # Reference: throb.cxx lines 231-233
        self.sync_filter = self._create_sync_filter()

        # Create pre-computed receive tone templates
        # Reference: throb.cxx lines 237-238, 264-279
        self.rxtones = self._create_rxtone_templates()

        # Decoder state
        self.phase_acc = 0.0  # Mixer phase accumulator
        self.rxcntr = float(self.rxsymlen)  # Symbol timing counter
        self.waitsync = 1  # Waiting for sync flag
        self.symptr = 0  # Symbol buffer pointer
        self.deccntr = 0  # Decimation counter

        # Symbol buffer (circular buffer of downsampled symbols)
        # Reference: throb.h line 83
        self.symbol_buffer = np.zeros(self.rxsymlen, dtype=complex)

        # Sync buffer for timing recovery
        # Reference: throb.h line 85
        self.sync_buffer = np.zeros(self.rxsymlen)

        # Character decoding state
        self.shift = False  # Shift state for Throb special characters
        self.lastchar = '\0'  # Last character decoded (for ThrobX)
        self._reset_syms()  # Initialize idle/space symbols

        # SNR tracking
        # Reference: throb.cxx line 235
        self.snr_filter = MovingAverage(16)
        self.signal = 0.0
        self.noise = 0.0
        self.metric = 0.0
        self.s2n = 0.0

        # Statistics
        self.total_chars = 0
        self.decoded_symbols = []  # For testing/analysis

    def _setup_mode_params(self):
        """Set up mode-specific parameters based on mode name."""
        # Reference: throb.cxx lines 141-219
        self.is_throbx = 'x' in self.mode

        if '1' in self.mode:
            self.symlen = self.SYMLEN_1
            self.use_full_pulse = False
        elif '2' in self.mode:
            self.symlen = self.SYMLEN_2
            self.use_full_pulse = False
        elif '4' in self.mode:
            self.symlen = self.SYMLEN_4
            self.use_full_pulse = True
        else:
            self.symlen = self.SYMLEN_4
            self.use_full_pulse = True

        # Downsampled symbol length
        self.rxsymlen = self.symlen // self.DOWN_SAMPLE

        # Set tone frequencies and character set
        if self.is_throbx:
            if '4' in self.mode:
                self.tone_freqs = self.THROBX_TONE_FREQS_WID
            else:
                self.tone_freqs = self.THROBX_TONE_FREQS_NAR
            self.num_tones = 11
            self.num_chars = 55
            self.charset = THROBX_CHARSET
            self.tone_pairs = THROBX_TONE_PAIRS
        else:
            if '4' in self.mode:
                self.tone_freqs = self.THROB_TONE_FREQS_WID
            else:
                self.tone_freqs = self.THROB_TONE_FREQS_NAR
            self.num_tones = 9
            self.num_chars = 45
            self.charset = THROB_CHARSET
            self.tone_pairs = THROB_TONE_PAIRS

    def _create_hilbert_filter(self, taps: int) -> np.ndarray:
        """
        Create Hilbert transform filter.

        Reference: throb.cxx lines 226-227 (C_FIR_filter with hilbert type)
        """
        # Create Hilbert filter coefficients
        # This is a simple approximation - fldigi uses a more complex FIR filter
        n = np.arange(taps)
        h = np.zeros(taps)
        mid = taps // 2

        for i in range(taps):
            if i == mid:
                h[i] = 0.0
            else:
                n_val = i - mid
                if n_val % 2 == 1:  # Odd indices
                    h[i] = 2.0 / (np.pi * n_val)
                else:
                    h[i] = 0.0

        # Normalize
        h = h / np.sum(np.abs(h))
        return h

    def _create_bandpass_filter(self) -> dict:
        """
        Create FFT-based bandpass filter.

        Reference: throb.cxx line 229
        We'll use a simpler time-domain FIR filter instead of FFT filter
        for initial implementation.
        """
        # Calculate bandwidth based on mode
        # Reference: throb.cxx lines 152, 165, 179, 192, 205, 218
        if self.is_throbx:
            if '4' in self.mode:
                bw = 94.0  # Hz
            else:
                bw = 47.0  # Hz
        else:
            if '4' in self.mode:
                bw = 72.0  # Hz
            else:
                bw = 36.0  # Hz

        # Create bandpass filter
        # Low and high cutoff frequencies
        low_freq = -bw
        high_freq = bw

        # Store filter parameters for FFT filtering
        return {
            'bw': bw,
            'low': low_freq,
            'high': high_freq,
            'buffer': []
        }

    def _create_sync_filter(self) -> np.ndarray:
        """
        Create sync filter (matched filter using pulse shape).

        Reference: throb.cxx lines 231-233
        """
        # Create pulse shape for matched filtering
        if self.use_full_pulse:
            pulse = self._make_full_pulse(self.rxsymlen)
        else:
            pulse = self._make_semi_pulse(self.rxsymlen)

        return pulse

    def _make_semi_pulse(self, length: int) -> np.ndarray:
        """
        Generate semi-pulse shape (20% rise, 60% flat, 20% fall).

        Reference: throb.cxx lines 542-566
        """
        pulse = np.zeros(length)

        # Rising edge (0% to 20%)
        rise_len = length // 5
        for i in range(rise_len):
            x = np.pi * i / rise_len
            pulse[i] = 0.5 * (1 - np.cos(x))

        # Flat portion (20% to 80%)
        pulse[rise_len : length * 4 // 5] = 1.0

        # Falling edge (80% to 100%)
        fall_start = length * 4 // 5
        fall_len = length - fall_start
        for i in range(fall_len):
            x = np.pi * i / fall_len
            pulse[fall_start + i] = 0.5 * (1 + np.cos(x))

        return pulse

    def _make_full_pulse(self, length: int) -> np.ndarray:
        """
        Generate full-pulse shape (full cosine wave).

        Reference: throb.cxx lines 568-579
        """
        pulse = np.zeros(length)
        for i in range(length):
            pulse[i] = 0.5 * (1 - np.cos(2 * np.pi * i / length))
        return pulse

    def _create_rxtone_templates(self) -> list:
        """
        Create pre-computed complex tone templates for correlation.

        Reference: throb.cxx lines 237-238, 264-279
        """
        # Generate full-rate pulse shape for tone templates
        if self.use_full_pulse:
            txpulse = self._make_full_pulse(self.symlen)
        else:
            txpulse = self._make_semi_pulse(self.symlen)

        rxtones = []
        for freq in self.tone_freqs:
            # Create complex tone template
            # Reference: throb.cxx mk_rxtone() lines 264-279
            tone = np.zeros(self.rxsymlen, dtype=complex)

            for i in range(0, self.symlen, self.DOWN_SAMPLE):
                # Complex exponential with negative frequency (for correlation)
                x = -2.0 * np.pi * freq * i / self.THROB_SAMPLE_RATE
                idx = i // self.DOWN_SAMPLE
                if idx < self.rxsymlen:
                    tone[idx] = txpulse[i] * complex(np.cos(x), np.sin(x))

            rxtones.append(tone)

        return rxtones

    def _reset_syms(self):
        """
        Reset idle and space symbols.

        Reference: throb.cxx lines 116-130
        """
        if self.is_throbx:
            self.idlesym = 0
            self.spacesym = 1
        else:
            self.idlesym = 0
            self.spacesym = 44

    def _flip_syms(self):
        """
        Flip idle and space symbols (ThrobX only).

        Reference: throb.cxx lines 96-114
        """
        if self.is_throbx:
            if self.idlesym == 0:
                self.idlesym = 1
                self.spacesym = 0
            else:
                self.idlesym = 0
                self.spacesym = 1

    def reset(self):
        """Reset decoder state."""
        self.phase_acc = 0.0
        self.rxcntr = float(self.rxsymlen)
        self.waitsync = 1
        self.symptr = 0
        self.deccntr = 0
        self.symbol_buffer.fill(0)
        self.sync_buffer.fill(0)
        self.shift = False
        self.lastchar = '\0'
        self._reset_syms()
        self.snr_filter.reset()
        self.signal = 0.0
        self.noise = 0.0
        self.metric = 0.0
        self.s2n = 0.0
        self.total_chars = 0
        self.decoded_symbols = []

    def _mixer(self, sample_complex: complex) -> complex:
        """
        Mix signal down to baseband.

        Reference: throb.cxx lines 281-295
        """
        # Complex mixer
        z = complex(np.cos(self.phase_acc), np.sin(self.phase_acc))
        result = z * sample_complex

        # Update phase accumulator
        self.phase_acc -= 2.0 * np.pi * self.frequency / self.THROB_SAMPLE_RATE

        # Keep phase in range [0, 2π)
        if self.phase_acc < 0:
            self.phase_acc += 2.0 * np.pi

        return result

    def _cmac(self, a: np.ndarray, b: np.ndarray, ptr: int, length: int) -> complex:
        """
        Complex multiply-accumulate (correlation).

        Reference: fldigi/src/include/complex.h lines 33-41
        """
        z = 0j
        ptr = ptr % length
        for i in range(length):
            z += a[i] * b[ptr]
            ptr = (ptr + 1) % length
        return z

    def _findtones(self, rxword: np.ndarray) -> Tuple[int, int, int]:
        """
        Find the two strongest tones in the received symbol.

        Reference: throb.cxx lines 297-350

        Returns:
            Tuple of (tone1, tone2, maxtone) where tone1 <= tone2
        """
        # Find strongest tone
        max1 = 0.0
        tone1 = 0
        for i in range(self.num_tones):
            mag = abs(rxword[i])
            if mag > max1:
                max1 = mag
                tone1 = i

        maxtone = tone1

        # Find second strongest tone
        max2 = 0.0
        tone2 = 0
        for i in range(self.num_tones):
            if i == tone1:
                continue
            mag = abs(rxword[i])
            if mag > max2:
                max2 = mag
                tone2 = i

        # Handle single-tone symbols (Throb only)
        # Reference: throb.cxx lines 324-329
        if not self.is_throbx:
            if max1 > max2 * 2:
                tone2 = tone1

        # Sort tones (tone1 < tone2)
        if tone1 > tone2:
            tone1, tone2 = tone2, tone1

        # Calculate signal and noise for SNR
        # Reference: throb.cxx lines 337-343
        signal = 0.0
        noise = 0.0
        for i in range(self.num_tones):
            if i == tone1 or i == tone2:
                signal += abs(rxword[i]) / 2.0
            else:
                noise += abs(rxword[i]) / (self.num_tones - 2.0)

        self.signal = signal
        self.noise = noise
        self.metric = self.snr_filter.update(signal / (noise + 1e-6))
        self.s2n = max(0.0, min(100.0, 10.0 * np.log10(self.metric) - 3.0))

        return tone1, tone2, maxtone

    def _decodechar(self, tone1: int, tone2: int):
        """
        Decode a character from tone pair.

        Reference: throb.cxx lines 357-417
        """
        # Check squelch
        if self.squelch_enabled and self.metric < self.squelch:
            return

        if self.is_throbx:
            # ThrobX mode
            # Reference: throb.cxx lines 396-414
            for i in range(self.num_chars):
                # Note: tone_pairs are already 0-indexed in Python
                if (self.tone_pairs[i][0] == tone1 and
                    self.tone_pairs[i][1] == tone2):
                    if i == self.spacesym or i == self.idlesym:
                        # Space or idle symbol
                        if self.lastchar != '\0' and self.lastchar != ' ':
                            self._show_char(' ')
                            self.lastchar = ' '
                        else:
                            self.lastchar = '\0'
                        self._flip_syms()
                    else:
                        char = self.charset[i]
                        self._show_char(char)
                        self.lastchar = char
                    break
        else:
            # Regular Throb mode
            # Reference: throb.cxx lines 364-394
            if self.shift:
                # Process shifted character
                # Reference: throb.cxx lines 365-379
                if tone1 == 0 and tone2 == 8:
                    self._show_char('?')
                elif tone1 == 1 and tone2 == 7:
                    self._show_char('@')
                elif tone1 == 2 and tone2 == 6:
                    self._show_char('=')
                elif tone1 == 4 and tone2 == 4:
                    self._show_char('\n')
                self.shift = False
                return

            # Check for shift symbol
            # Reference: throb.cxx lines 382-385
            if tone1 == 3 and tone2 == 5:
                self.shift = True
                return

            # Look up character in tone pairs table
            # Reference: throb.cxx lines 387-393
            for i in range(self.num_chars):
                # Note: tone_pairs are already 0-indexed in Python
                if (self.tone_pairs[i][0] == tone1 and
                    self.tone_pairs[i][1] == tone2):
                    char = self.charset[i]
                    self._show_char(char)
                    break

    def _show_char(self, char: str):
        """
        Output decoded character.

        Reference: throb.cxx lines 352-355
        """
        if char and char != '\0':
            self.total_chars += 1
            if self.text_callback:
                self.text_callback(char)

    def _sync(self, sample_complex: complex):
        """
        Symbol synchronization.

        Reference: throb.cxx lines 466-503
        """
        # Rectify and filter for sync detection
        mag = abs(sample_complex)

        # Matched filter
        # Simple convolution approximation
        filtered = mag  # Simplified - full implementation would convolve with sync_filter

        # Store in sync buffer
        self.sync_buffer[self.symptr] = filtered

        # Check if we need to resync
        # Reference: throb.cxx lines 477-479
        if self.waitsync == 0 or self.rxcntr > (self.rxsymlen / 2.0):
            return

        # Find peak in sync buffer
        # Reference: throb.cxx lines 481-491
        maxval = 0.0
        maxpos = 0
        for i in range(self.rxsymlen):
            idx = (i + self.symptr + 1) % self.rxsymlen
            if self.sync_buffer[idx] > maxval:
                maxval = self.sync_buffer[idx]
                maxpos = i

        # Correct sync
        # Reference: throb.cxx line 494
        self.rxcntr += (maxpos - self.rxsymlen / 2) / (self.num_tones - 1)
        self.waitsync = 0

    def _rx(self, sample_complex: complex):
        """
        Receive and decode symbol.

        Reference: throb.cxx lines 419-464
        """
        # Store sample in symbol buffer
        self.symbol_buffer[self.symptr] = sample_complex

        # Check if symbol is complete
        # Reference: throb.cxx lines 426-427
        if self.rxcntr > 0.0:
            return

        # Correlate against all tone templates
        # Reference: throb.cxx lines 429-431
        rxword = np.zeros(self.num_tones, dtype=complex)
        for i in range(self.num_tones):
            rxword[i] = self._cmac(
                self.rxtones[i],
                self.symbol_buffer,
                self.symptr + 1,
                self.rxsymlen
            )

        # Find strongest tones
        # Reference: throb.cxx line 434
        tone1, tone2, maxtone = self._findtones(rxword)

        # Store for analysis
        self.decoded_symbols.append((tone1, tone2))

        # Decode character
        # Reference: throb.cxx lines 437-440
        self._decodechar(tone1, tone2)

        # AFC (Automatic Frequency Control)
        # Reference: throb.cxx lines 442-454
        if self.use_afc and (not self.squelch_enabled or self.metric >= self.squelch):
            # Calculate frequency error
            z1 = rxword[maxtone]
            z2 = self._cmac(
                self.rxtones[maxtone],
                self.symbol_buffer,
                self.symptr + 2,
                self.rxsymlen
            )

            # Calculate frequency offset
            phase_diff = np.angle(np.conj(z1) * z2)
            f = phase_diff / (2 * self.DOWN_SAMPLE * np.pi / self.THROB_SAMPLE_RATE)
            f -= self.tone_freqs[maxtone]

            # Update frequency
            self.frequency += f / (self.num_tones - 1)

        # Reset for next symbol
        # Reference: throb.cxx lines 457-458
        self.rxcntr = self.rxsymlen
        self.waitsync = 1

    def process(self, samples: np.ndarray) -> str:
        """
        Process audio samples and decode THROB signals.

        Args:
            samples: Array of audio samples (real-valued)

        Returns:
            Decoded text string

        Reference: throb.cxx lines 505-536 (rx_process)
        """
        decoded_text = []

        # Set up callback to capture decoded characters
        # Also call user callback if one is set
        original_callback = self.text_callback

        def internal_callback(c):
            decoded_text.append(c)
            if original_callback:
                original_callback(c)

        self.text_callback = internal_callback

        # Convert real signal to analytic signal using Hilbert transform
        # Reference: throb.cxx line 514 (hilbert->run())
        # scipy.signal.hilbert returns the analytic signal directly
        from scipy.signal import hilbert as scipy_hilbert
        analytic_signal = scipy_hilbert(samples)

        # Process each sample
        # Reference: throb.cxx lines 510-533
        for z in analytic_signal:
            # Mix down to baseband
            # Reference: throb.cxx line 515
            z = self._mixer(z)

            # Bandpass filter (simplified - fldigi uses FFT filter)
            # Reference: throb.cxx line 516
            # For now, skip complex filtering and just use the mixed signal
            # TODO: Add proper FFT-based bandpass filtering

            # Downsample by 32
            # Reference: throb.cxx lines 519-531
            self.deccntr += 1
            if self.deccntr >= self.DOWN_SAMPLE:
                self.rxcntr -= 1.0

                # Do symbol sync
                # Reference: throb.cxx line 524
                self._sync(z)

                # Decode
                # Reference: throb.cxx line 527
                self._rx(z)

                # Update symbol pointer
                # Reference: throb.cxx line 529
                self.symptr = (self.symptr + 1) % self.rxsymlen
                self.deccntr = 0

        # Restore original callback
        self.text_callback = original_callback

        return ''.join(decoded_text)

    def get_snr(self) -> float:
        """Get current SNR estimate in dB."""
        return self.s2n

    def get_metric(self) -> float:
        """Get current signal quality metric."""
        return self.metric


class MovingAverage:
    """
    Simple moving average filter.

    Reference: throb.cxx line 235 (Cmovavg)
    """

    def __init__(self, length: int):
        """Initialize moving average filter."""
        self.length = length
        self.buffer = []

    def update(self, value: float) -> float:
        """Update filter with new value."""
        self.buffer.append(value)
        if len(self.buffer) > self.length:
            self.buffer.pop(0)
        return sum(self.buffer) / len(self.buffer) if self.buffer else 0.0

    def reset(self):
        """Reset filter state."""
        self.buffer = []


# Convenience functions for each mode
def Throb1Decoder(
    frequency: float = 1500.0,
    use_afc: bool = True,
    text_callback: Optional[Callable[[str], None]] = None,
) -> ThrobDecoder:
    """Create Throb1 decoder instance."""
    return ThrobDecoder(
        mode='throb1',
        frequency=frequency,
        use_afc=use_afc,
        text_callback=text_callback
    )


def Throb2Decoder(
    frequency: float = 1500.0,
    use_afc: bool = True,
    text_callback: Optional[Callable[[str], None]] = None,
) -> ThrobDecoder:
    """Create Throb2 decoder instance."""
    return ThrobDecoder(
        mode='throb2',
        frequency=frequency,
        use_afc=use_afc,
        text_callback=text_callback
    )


def Throb4Decoder(
    frequency: float = 1500.0,
    use_afc: bool = True,
    text_callback: Optional[Callable[[str], None]] = None,
) -> ThrobDecoder:
    """Create Throb4 decoder instance."""
    return ThrobDecoder(
        mode='throb4',
        frequency=frequency,
        use_afc=use_afc,
        text_callback=text_callback
    )


def ThrobX1Decoder(
    frequency: float = 1500.0,
    use_afc: bool = True,
    text_callback: Optional[Callable[[str], None]] = None,
) -> ThrobDecoder:
    """Create ThrobX1 decoder instance."""
    return ThrobDecoder(
        mode='throbx1',
        frequency=frequency,
        use_afc=use_afc,
        text_callback=text_callback
    )


def ThrobX2Decoder(
    frequency: float = 1500.0,
    use_afc: bool = True,
    text_callback: Optional[Callable[[str], None]] = None,
) -> ThrobDecoder:
    """Create ThrobX2 decoder instance."""
    return ThrobDecoder(
        mode='throbx2',
        frequency=frequency,
        use_afc=use_afc,
        text_callback=text_callback
    )


def ThrobX4Decoder(
    frequency: float = 1500.0,
    use_afc: bool = True,
    text_callback: Optional[Callable[[str], None]] = None,
) -> ThrobDecoder:
    """Create ThrobX4 decoder instance."""
    return ThrobDecoder(
        mode='throbx4',
        frequency=frequency,
        use_afc=use_afc,
        text_callback=text_callback
    )
