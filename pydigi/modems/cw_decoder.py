"""
CW (Morse Code) Decoder Implementation

Based on fldigi's CW decoder (fldigi/src/cw/cw.cxx).
Decodes Morse code audio signals with automatic speed tracking and AGC.

Algorithm Overview:
    1. Bandpass filter centered on CW frequency
    2. Envelope detection (absolute value + smoothing)
    3. AGC (Automatic Gain Control) for normalization
    4. Hysteresis-based key up/down detection
    5. Adaptive speed tracking using dit-dah pairs
    6. Character/word spacing detection
    7. Morse pattern lookup and decoding

Reference:
    fldigi/src/cw/cw.cxx lines 673-1022 (decode_stream, handle_event)
"""

import numpy as np
from typing import Optional, Callable, Dict, Tuple
from scipy import signal
from collections import deque

from ..core.dcd import EnergyDCD


# Morse code lookup table (from cw.py)
MORSE_TABLE: Dict[str, str] = {
    # Letters
    "A": ".-", "B": "-...", "C": "-.-.", "D": "-..", "E": ".", "F": "..-.",
    "G": "--.", "H": "....", "I": "..", "J": ".---", "K": "-.-", "L": ".-..",
    "M": "--", "N": "-.", "O": "---", "P": ".--.", "Q": "--.-", "R": ".-.",
    "S": "...", "T": "-", "U": "..-", "V": "...-", "W": ".--", "X": "-..-",
    "Y": "-.--", "Z": "--..",
    # Numbers
    "0": "-----", "1": ".----", "2": "..---", "3": "...--", "4": "....-",
    "5": ".....", "6": "-....", "7": "--...", "8": "---..", "9": "----.",
    # Punctuation
    ".": ".-.-.-", ",": "--..--", "?": "..--..", "'": ".----.", "!": "-.-.--",
    "/": "-..-.", "(": "-.--.", ")": "-.--.-", "&": ".-...", ":": "---...",
    ";": "-.-.-.", "=": "-...-", "+": ".-.-.", "-": "-....-", "_": "..--.-..",
    '"': ".-..-.", "$": "...-..-", "@": ".--.-.",
    # Prosigns
    "<AR>": ".-.-.", "<SK>": "...-.-", "<BT>": "-...-", "<KN>": "-.--.",
    "<AS>": ".-...",
}

# Reverse lookup table (morse pattern -> character)
MORSE_REVERSE: Dict[str, str] = {v: k for k, v in MORSE_TABLE.items()}


class CWDecoder:
    """
    CW (Morse Code) Decoder

    Decodes CW audio signals with automatic speed tracking, AGC, and
    robust noise handling.

    Features:
        - Automatic speed tracking (WPM estimation)
        - AGC (Automatic Gain Control)
        - Hysteresis-based key detection
        - Character/word spacing detection
        - Noise spike rejection
        - Signal quality metrics

    Example:
        >>> decoder = CWDecoder(
        ...     wpm=20.0,
        ...     sample_rate=8000.0,
        ...     frequency=800.0,
        ...     text_callback=lambda text: print(text, end='')
        ... )
        >>> decoder.process(audio_samples)
    """

    # Decoder state constants
    RS_IDLE = 0
    RS_IN_TONE = 1
    RS_AFTER_TONE = 2

    def __init__(
        self,
        wpm: float = 20.0,
        sample_rate: float = 8000.0,
        frequency: float = 800.0,
        bandwidth: float = 100.0,
        use_dcd: bool = True,
        dcd_threshold: float = 6.0,
        squelch: Optional[float] = None,
        text_callback: Optional[Callable[[str], None]] = None,
        noise_char: str = '*'
    ):
        """
        Initialize CW decoder.

        Args:
            wpm: Expected speed in words per minute (5-200)
            sample_rate: Audio sample rate in Hz
            frequency: CW tone frequency in Hz
            bandwidth: Filter bandwidth in Hz
            use_dcd: Enable Data Carrier Detect
            dcd_threshold: DCD threshold in dB
            squelch: Squelch threshold (0-100), None to disable
            text_callback: Callback function for decoded text
            noise_char: Character to output for decode errors ('*', '_', or ' ')
        """
        self.sample_rate = sample_rate
        self.frequency = frequency
        self.bandwidth = bandwidth
        self.text_callback = text_callback
        self.noise_char = noise_char
        self.squelch = squelch

        # Timing parameters (calculated from WPM)
        self._wpm = wpm
        self._update_timing()

        # Create bandpass filter for CW tone extraction
        # Filter order and design based on fldigi
        filter_order = 64
        nyquist = sample_rate / 2
        low_freq = max(1.0, frequency - bandwidth / 2) / nyquist
        high_freq = min(nyquist - 1, frequency + bandwidth / 2) / nyquist

        self.filter_taps = signal.firwin(
            filter_order,
            [low_freq, high_freq],
            pass_zero=False,
            window='hamming'
        )
        self.filter_state = np.zeros(len(self.filter_taps) - 1)

        # Envelope detector - moving average filter
        # Based on fldigi's bitfilter
        self.envelope_window = int(sample_rate * 0.005)  # 5ms smoothing
        self.envelope_buffer = deque(maxlen=self.envelope_window)

        # AGC parameters (from fldigi decode_stream)
        self.agc_peak = 0.0
        self.noise_floor = 1e-6
        self.sig_avg = 0.5

        # AGC attack/decay time constants (samples)
        # Based on fldigi's cwrx_attack/cwrx_decay
        self.agc_attack = 200   # Fast attack (default setting)
        self.agc_decay = 1000   # Slow decay (default setting)

        # Decoder state machine
        self.state = self.RS_IDLE
        self.old_state = self.RS_IDLE

        # Timing tracking
        self.sample_counter = 0
        self.tone_start_sample = 0
        self.tone_end_sample = 0
        self.last_element_duration = 0

        # Morse pattern buffer
        self.morse_buffer = ""
        self.space_sent = True

        # Signal quality metrics
        self.metric = 0.0  # Signal quality (0-100)
        self.snr_db = 0.0

        # DCD (Data Carrier Detect)
        self.use_dcd = use_dcd
        if use_dcd:
            self.dcd = EnergyDCD(
                threshold_db=dcd_threshold,
                attack=0.1,
                decay=0.01
            )
            self.dcd_active = False

        # Statistics
        self.total_characters = 0
        self.decode_errors = 0

    def _update_timing(self):
        """Update timing parameters based on WPM."""
        # Standard word "PARIS" is 50 units
        # dit_time = 1.2 / WPM (in seconds)
        # This matches the encoder's timing calculation
        dit_time_seconds = 1.2 / self._wpm

        # Convert to samples
        self.dit_length_samples = int(dit_time_seconds * self.sample_rate)
        self.dah_length_samples = 3 * self.dit_length_samples
        self.two_dot_threshold = 2 * self.dit_length_samples

        # Noise spike threshold (from fldigi)
        # Ignore tones shorter than this (helps reject noise)
        self.noise_spike_threshold = self.two_dot_threshold // 4

    @property
    def wpm(self) -> float:
        """Get current WPM setting."""
        return self._wpm

    @wpm.setter
    def wpm(self, value: float):
        """Set WPM and update timing."""
        self._wpm = max(5.0, min(200.0, value))
        self._update_timing()

    def reset(self):
        """Reset decoder state."""
        self.state = self.RS_IDLE
        self.old_state = self.RS_IDLE
        self.sample_counter = 0
        self.tone_start_sample = 0
        self.tone_end_sample = 0
        self.last_element_duration = 0
        self.morse_buffer = ""
        self.space_sent = True
        self.filter_state = np.zeros(len(self.filter_taps) - 1)
        self.envelope_buffer.clear()
        self.total_characters = 0
        self.decode_errors = 0

    def _decayavg(self, avg: float, value: float, weight: int) -> float:
        """
        Exponential moving average with time constant.

        From fldigi: avg = (avg * weight + value) / (weight + 1)

        Args:
            avg: Current average
            value: New value
            weight: Time constant (higher = slower response)

        Returns:
            Updated average
        """
        if weight <= 0:
            return value
        return (avg * weight + value) / (weight + 1.0)

    def _update_agc(self, value: float) -> float:
        """
        Update AGC and normalize value.

        Based on fldigi's decode_stream AGC algorithm.

        Args:
            value: Input envelope value

        Returns:
            Normalized value (0-1 range)
        """
        # Update signal average (fast attack on rising, slow decay on falling)
        attack = self.agc_attack if value > self.sig_avg else self.agc_decay
        self.sig_avg = self._decayavg(self.sig_avg, 0.5 * value, attack)

        # Update noise floor (track minimum)
        if value < self.sig_avg:
            if value < self.noise_floor:
                self.noise_floor = self._decayavg(self.noise_floor, value, self.agc_attack)
            else:
                self.noise_floor = self._decayavg(self.noise_floor, value, self.agc_decay)

        # Update peak (track maximum)
        if value > self.sig_avg:
            if value > self.agc_peak:
                self.agc_peak = self._decayavg(self.agc_peak, value, self.agc_attack)
            else:
                self.agc_peak = self._decayavg(self.agc_peak, value, self.agc_decay)

        # Normalize to 0-1 range
        if self.agc_peak > 0:
            norm_value = value / self.agc_peak
            norm_noise = self.noise_floor / self.agc_peak
            norm_sig = self.sig_avg / self.agc_peak
        else:
            norm_value = self.noise_floor
            norm_noise = self.noise_floor
            norm_sig = self.noise_floor

        # Update signal quality metric (SNR-based)
        self.metric = 0.8 * self.metric
        if self.noise_floor > 1e-4 and self.noise_floor < self.sig_avg:
            snr_db = 20.0 * np.log10(norm_sig / norm_noise) if norm_noise > 0 else 0.0
            self.snr_db = snr_db
            # Clamp to 0-100 range with 2.5x scaling
            self.metric += 0.2 * np.clip(2.5 * snr_db, 0, 100)

        return norm_value

    def _update_speed_tracking(self, dit_duration: int, dah_duration: int):
        """
        Update speed tracking using dit-dah pair.

        From fldigi: When we see a dit-dah or dah-dit pair, we can estimate
        the actual speed by using the relationship: dah ≈ 3 × dit

        Args:
            dit_duration: Duration of dit in samples
            dah_duration: Duration of dah in samples
        """
        # Average the dit duration for more stable tracking
        estimated_dit = dit_duration

        # Calculate WPM from actual dit length
        # dit_time = 1.2 / WPM, so WPM = 1.2 / dit_time
        dit_seconds = estimated_dit / self.sample_rate
        estimated_wpm = 1.2 / dit_seconds

        # Clamp to reasonable range
        estimated_wpm = max(5.0, min(200.0, estimated_wpm))

        # Smooth tracking (slow adaptation)
        alpha = 0.1  # Smoothing factor
        self._wpm = alpha * estimated_wpm + (1 - alpha) * self._wpm

        # Update timing parameters
        self._update_timing()

    def _handle_keydown(self):
        """Handle tone start event."""
        if self.state == self.RS_IN_TONE:
            return

        # First tone in idle state - reset tracking
        if self.state == self.RS_IDLE:
            self.sample_counter = 0
            self.morse_buffer = ""

        # Save timestamp
        self.tone_start_sample = self.sample_counter

        # Update state
        self.old_state = self.state
        self.state = self.RS_IN_TONE

    def _handle_keyup(self):
        """Handle tone end event."""
        if self.state != self.RS_IN_TONE:
            return

        # Save timestamp
        self.tone_end_sample = self.sample_counter
        element_duration = self.tone_end_sample - self.tone_start_sample

        # Noise spike rejection
        if element_duration > 0 and element_duration < self.noise_spike_threshold:
            self.state = self.RS_IDLE
            return

        # Adaptive speed tracking using dit-dah pairs
        if self.last_element_duration > 0:
            # Check for dit-dah sequence (current should be ~3x last)
            if (element_duration > 2 * self.last_element_duration and
                element_duration < 4 * self.last_element_duration):
                self._update_speed_tracking(self.last_element_duration, element_duration)

            # Check for dah-dit sequence (last should be ~3x current)
            if (self.last_element_duration > 2 * element_duration and
                self.last_element_duration < 4 * element_duration):
                self._update_speed_tracking(element_duration, self.last_element_duration)

        self.last_element_duration = element_duration

        # Classify as dit or dah
        if element_duration <= self.two_dot_threshold:
            self.morse_buffer += "."
        else:
            self.morse_buffer += "-"

        # Limit buffer length (reject likely noise)
        if len(self.morse_buffer) > 8:  # Max morse elements for valid char
            self.state = self.RS_IDLE
            self.morse_buffer = ""
            self.sample_counter = 0
            return

        # Move to after-tone state
        self.state = self.RS_AFTER_TONE

    def _check_character_spacing(self):
        """Check for character/word spacing and decode."""
        if self.state == self.RS_IN_TONE:
            return

        # Compute silence duration since last keyup
        silence_duration = self.sample_counter - self.tone_end_sample

        # SHORT silence - still building character
        if silence_duration < (2 * self.dit_length_samples):
            return

        # MEDIUM silence (2-4 dit times) - character complete
        if (silence_duration >= (2 * self.dit_length_samples) and
            silence_duration <= (4 * self.dit_length_samples) and
            self.state == self.RS_AFTER_TONE):

            # Decode the morse pattern
            if self.morse_buffer:
                decoded = MORSE_REVERSE.get(self.morse_buffer, None)

                if decoded:
                    # Valid character
                    if self.text_callback:
                        self.text_callback(decoded)
                    self.total_characters += 1
                else:
                    # Invalid pattern - output noise character
                    if self.noise_char and self.text_callback:
                        self.text_callback(self.noise_char)
                    self.decode_errors += 1

                self.morse_buffer = ""
                self.state = self.RS_IDLE
                self.space_sent = False

        # LONG silence (>4 dit times) - word space
        if silence_duration > (4 * self.dit_length_samples) and not self.space_sent:
            if self.text_callback:
                self.text_callback(" ")
            self.space_sent = True

    def process(self, samples: np.ndarray):
        """
        Process audio samples (asynchronous callback-based API).

        Decoded text is sent to the text_callback function as it becomes available.

        Args:
            samples: Audio samples (mono, real-valued)
        """
        # Ensure samples are float
        samples = np.asarray(samples, dtype=np.float32)

        # Process each sample
        for sample in samples:
            # 1. Bandpass filter to extract CW tone
            filtered, self.filter_state = signal.lfilter(
                self.filter_taps, [1.0], [sample], zi=self.filter_state
            )
            filtered_value = filtered[0]

            # 2. Envelope detection (absolute value)
            envelope = abs(filtered_value)

            # 3. Smoothing filter (moving average)
            self.envelope_buffer.append(envelope)
            if len(self.envelope_buffer) > 0:
                smoothed = np.mean(self.envelope_buffer)
            else:
                smoothed = envelope

            # 4. AGC and normalization
            normalized = self._update_agc(smoothed)

            # 5. Check squelch
            if self.squelch is not None and self.metric < self.squelch:
                # Squelched - skip detection
                self.sample_counter += 1
                continue

            # 6. DCD update (optional)
            if self.use_dcd:
                self.dcd_active, _ = self.dcd.update(np.array([normalized]))
                if not self.dcd_active:
                    self.sample_counter += 1
                    continue

            # 7. Hysteresis-based key detection
            # Upper threshold: 1.05 × signal average (from fldigi)
            # Lower threshold: 0.95 × signal average
            upper_threshold = 1.05 * (self.sig_avg / self.agc_peak if self.agc_peak > 0 else 0.5)
            lower_threshold = 0.95 * (self.sig_avg / self.agc_peak if self.agc_peak > 0 else 0.5)

            # Detect key down (upward trend)
            if normalized > upper_threshold and self.state != self.RS_IN_TONE:
                self._handle_keydown()

            # Detect key up (downward trend)
            elif normalized < lower_threshold and self.state == self.RS_IN_TONE:
                self._handle_keyup()

            # 8. Check for character/word spacing
            self._check_character_spacing()

            # Increment sample counter
            self.sample_counter += 1

    def demodulate(self, samples: np.ndarray) -> str:
        """
        Demodulate audio samples and return decoded text (synchronous API).

        Args:
            samples: Audio samples (mono, real-valued)

        Returns:
            Decoded text string
        """
        # Create temporary buffer for decoded text
        decoded_text = []

        # Save original callback
        original_callback = self.text_callback

        # Set temporary callback to capture text
        self.text_callback = lambda text: decoded_text.append(text)

        # Process samples
        self.process(samples)

        # Restore original callback
        self.text_callback = original_callback

        # Return concatenated text
        return ''.join(decoded_text)

    def get_statistics(self) -> Dict[str, any]:
        """
        Get decoder statistics.

        Returns:
            Dictionary with decoder metrics:
                - wpm: Current estimated WPM
                - frequency: Center frequency
                - metric: Signal quality (0-100)
                - snr_db: Estimated SNR in dB
                - total_characters: Total characters decoded
                - decode_errors: Number of decode errors
                - error_rate: Decode error rate (0-1)
                - dcd_active: DCD state (if enabled)
        """
        error_rate = (self.decode_errors / self.total_characters
                     if self.total_characters > 0 else 0.0)

        stats = {
            'wpm': self.wpm,
            'frequency': self.frequency,
            'metric': self.metric,
            'snr_db': self.snr_db,
            'total_characters': self.total_characters,
            'decode_errors': self.decode_errors,
            'error_rate': error_rate,
        }

        if self.use_dcd:
            stats['dcd_active'] = self.dcd_active

        return stats
