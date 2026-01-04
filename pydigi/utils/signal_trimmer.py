"""
Signal Detection and Trimming Utility

Generic signal detection and trimming for removing leading/trailing silence from audio signals.
Provides two modes:
1. Deep search (hybrid FFT + energy) - For pre-recorded signals
2. Real-time (fast energy) - For streaming audio

Not tied to any specific modem - works with any audio signal.
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Optional, Union, Tuple, Dict
from collections import deque

from ..core.signal_detector import SignalDetector


# Default configuration
DEFAULT_CONFIG = {
    # Common parameters
    'sample_rate': 8000.0,
    'snr_threshold_db': 10.0,          # 10 dB above noise floor
    'noise_window_duration': 0.1,      # 100ms for noise estimation
    'min_signal_duration': 0.05,       # 50ms sustained signal required
    'edge_margin_duration': 0.02,      # 20ms safety margin at edges

    # Deep search specific
    'fft_window_size': 2048,           # ~256ms @ 8kHz
    'fft_hop_size': 512,               # 75% overlap
    'energy_window_duration': 0.032,   # 32ms (~1 PSK31 symbol)

    # Real-time specific
    'rt_power_window_samples': 100,    # ~12.5ms @ 8kHz
    'rt_onset_duration': 0.05,         # 50ms sustained onset
    'rt_offset_duration': 0.1,         # 100ms sustained offset

    # Threshold constants
    'low_noise_threshold': 0.0004,     # Power threshold for "very quiet" (amplitude ~0.02)
    'min_signal_threshold': 0.01,      # Minimum power for signal (amplitude ~0.1)
}

# Preset configurations for common use cases
PRESET_CONFIGS = {
    'psk31': {
        'snr_threshold_db': 6.0,
        'energy_window_duration': 0.032,  # 1 symbol @ 31.25 baud
    },
    'psk63': {
        'snr_threshold_db': 6.0,
        'energy_window_duration': 0.016,  # 1 symbol @ 62.5 baud
    },
    'psk125': {
        'snr_threshold_db': 8.0,
        'energy_window_duration': 0.008,  # 1 symbol @ 125 baud
    },
    'psk250': {
        'snr_threshold_db': 8.0,
        'energy_window_duration': 0.004,  # 1 symbol @ 250 baud
    },
    'weak_signals': {
        'snr_threshold_db': 3.0,          # More sensitive
        'min_signal_duration': 0.1,       # Require longer sustained signal
    },
    'noisy_environment': {
        'snr_threshold_db': 15.0,         # Higher threshold
        'min_signal_duration': 0.1,       # Longer confirmation
    },
}


@dataclass
class TrimResult:
    """Result of signal trimming operation."""
    trimmed_audio: np.ndarray           # Audio with silence removed
    signal_start: int                   # Sample index where signal starts
    signal_end: int                     # Sample index where signal ends
    leading_samples_removed: int        # Number of leading samples trimmed
    trailing_samples_removed: int       # Number of trailing samples trimmed
    noise_floor: float                  # Estimated noise floor power
    peak_snr_db: float                  # Peak SNR in dB
    detection_method: str               # 'deep_search' or 'real_time'
    metadata: Dict = field(default_factory=dict)  # Additional detection metadata


class SignalTrimmer:
    """
    Generic signal detection and trimming utility.

    Provides two modes:
    1. Deep search (hybrid FFT + energy) - For pre-recorded signals
    2. Real-time (fast energy) - For streaming audio

    This is a standalone utility not tied to any specific modem.
    Returns trimmed audio with leading/trailing silence removed.

    Example usage:
        # Pre-recorded signal (deep search)
        trimmer = SignalTrimmer(preset='psk31')
        result = trimmer.trim_deep_search(audio, return_metadata=True)
        print(f"Removed {result.leading_samples_removed} leading samples")

        # Real-time streaming
        trimmer = SignalTrimmer(preset='psk125')
        for chunk in audio_stream:
            trimmed, is_active = trimmer.trim_real_time(chunk)
            if len(trimmed) > 0:
                process(trimmed)
    """

    def __init__(
        self,
        sample_rate: float = 8000.0,
        snr_threshold_db: float = 10.0,
        noise_window_duration: float = 0.1,
        min_signal_duration: float = 0.05,
        edge_margin_duration: float = 0.02,
        preset: Optional[str] = None,
    ):
        """
        Initialize signal trimmer.

        Args:
            sample_rate: Audio sample rate in Hz
            snr_threshold_db: SNR threshold in dB above noise floor
            noise_window_duration: Duration for noise floor estimation (seconds)
            min_signal_duration: Minimum sustained signal duration (seconds)
            edge_margin_duration: Safety margin to add at signal edges (seconds)
            preset: Apply preset configuration ('psk31', 'psk63', 'psk125',
                   'weak_signals', 'noisy_environment', etc.)
        """
        # Start with default config
        config = DEFAULT_CONFIG.copy()

        # Apply preset if specified
        if preset and preset in PRESET_CONFIGS:
            config.update(PRESET_CONFIGS[preset])

        # Override with explicit arguments (if not default)
        if sample_rate != DEFAULT_CONFIG['sample_rate']:
            config['sample_rate'] = sample_rate
        if snr_threshold_db != DEFAULT_CONFIG['snr_threshold_db']:
            config['snr_threshold_db'] = snr_threshold_db
        if noise_window_duration != DEFAULT_CONFIG['noise_window_duration']:
            config['noise_window_duration'] = noise_window_duration
        if min_signal_duration != DEFAULT_CONFIG['min_signal_duration']:
            config['min_signal_duration'] = min_signal_duration
        if edge_margin_duration != DEFAULT_CONFIG['edge_margin_duration']:
            config['edge_margin_duration'] = edge_margin_duration

        # Store configuration
        self.sample_rate = config['sample_rate']
        self.snr_threshold_db = config['snr_threshold_db']
        self.noise_window_duration = config['noise_window_duration']
        self.min_signal_duration = config['min_signal_duration']
        self.edge_margin_duration = config['edge_margin_duration']

        # Deep search parameters
        self.fft_window_size = config['fft_window_size']
        self.fft_hop_size = config['fft_hop_size']
        self.energy_window_duration = config['energy_window_duration']

        # Real-time parameters
        self.rt_power_window_samples = config['rt_power_window_samples']
        self.rt_onset_duration = config['rt_onset_duration']
        self.rt_offset_duration = config['rt_offset_duration']

        # Threshold constants
        self.low_noise_threshold = config['low_noise_threshold']
        self.min_signal_threshold = config['min_signal_threshold']

        # Computed parameters
        self.noise_window_samples = int(self.noise_window_duration * self.sample_rate)
        self.min_signal_samples = int(self.min_signal_duration * self.sample_rate)
        self.edge_margin_samples = int(self.edge_margin_duration * self.sample_rate)
        self.energy_window_samples = int(self.energy_window_duration * self.sample_rate)

        # Initialize SignalDetector for FFT-based coarse detection
        # Use higher threshold for coarse detection to avoid false detections from noise
        coarse_threshold_db = max(self.snr_threshold_db, 12.0)  # Minimum 12 dB for coarse detection
        self._signal_detector = SignalDetector(
            sample_rate=self.sample_rate,
            threshold_db=coarse_threshold_db,
        )

        # Real-time state
        self._rt_noise_floor = 0.001  # Initial estimate
        self._rt_noise_samples = 0
        self._rt_signal_active = False
        self._rt_onset_counter = 0
        self._rt_offset_counter = 0
        self._rt_power_buffer = deque(maxlen=self.rt_power_window_samples)
        self._rt_onset_buffer = []  # Buffer samples during onset detection

    def trim_deep_search(
        self,
        audio: np.ndarray,
        return_metadata: bool = False,
    ) -> Union[np.ndarray, TrimResult]:
        """
        Deep search signal trimming (hybrid FFT + energy approach).

        Best for pre-recorded signals where we can analyze the entire
        waveform. Uses both frequency and time-domain analysis.

        Algorithm:
        1. Coarse detection: FFT-based carrier detection
        2. Noise floor estimation: Percentile-based from pre-signal region
        3. Fine detection: Energy-based edge refinement
        4. Edge trimming: Precise boundaries with safety margin

        Args:
            audio: Input audio samples (float32, -1.0 to 1.0)
            return_metadata: If True, return TrimResult with metadata.
                           If False, return just the trimmed audio array.

        Returns:
            Trimmed audio array, or TrimResult if return_metadata=True
        """
        if len(audio) == 0:
            return self._empty_result() if return_metadata else np.array([], dtype=np.float32)

        # Phase 1: Coarse Detection (FFT-based)
        coarse_start, coarse_end, carrier_windows = self._fft_coarse_detection(audio)

        if coarse_start is None or coarse_end is None:
            # No signal detected
            return self._empty_result() if return_metadata else np.array([], dtype=np.float32)

        # Fallback: If FFT detects signal very early, it may be noise
        # Use energy-based coarse detection as fallback
        early_detection_threshold = int(0.1 * self.sample_rate)  # 100ms
        if coarse_start < early_detection_threshold:
            # Try energy-based coarse detection as alternative
            energy_start, energy_end = self._energy_coarse_detection(audio)
            if energy_start is not None and energy_start > early_detection_threshold:
                # Energy detection found signal later - more reliable
                coarse_start = energy_start
                coarse_end = energy_end if energy_end is not None else coarse_end

        # Phase 2: Noise Floor Estimation
        noise_floor = self._estimate_noise_floor(audio, coarse_start)

        # Phase 3: Fine Edge Detection (Energy-based)
        signal_threshold_power = self._calculate_signal_threshold(noise_floor)

        signal_start = self._find_signal_onset(
            audio, coarse_start, coarse_end,
            noise_floor, signal_threshold_power
        )

        signal_end = self._find_signal_offset(
            audio, coarse_start, coarse_end,
            noise_floor, signal_threshold_power
        )

        # Phase 4: Edge Refinement (add safety margin)
        signal_start = max(0, signal_start - self.edge_margin_samples)
        signal_end = min(len(audio), signal_end + self.edge_margin_samples)

        # Extract trimmed audio
        trimmed_audio = audio[signal_start:signal_end]

        # Calculate statistics
        if len(trimmed_audio) > 0:
            peak_power = np.max(trimmed_audio ** 2)
            peak_snr_db = 10 * np.log10((peak_power / (noise_floor + 1e-10)))
        else:
            peak_snr_db = 0.0

        if return_metadata:
            return TrimResult(
                trimmed_audio=trimmed_audio,
                signal_start=signal_start,
                signal_end=signal_end,
                leading_samples_removed=signal_start,
                trailing_samples_removed=len(audio) - signal_end,
                noise_floor=noise_floor,
                peak_snr_db=peak_snr_db,
                detection_method='deep_search',
                metadata={
                    'coarse_start': coarse_start,
                    'coarse_end': coarse_end,
                    'carrier_windows_detected': carrier_windows,
                    'energy_window_size': self.energy_window_samples,
                    'signal_threshold_power': signal_threshold_power,
                }
            )
        else:
            return trimmed_audio

    def trim_real_time(
        self,
        audio_chunk: np.ndarray,
    ) -> Tuple[np.ndarray, bool]:
        """
        Real-time signal trimming (fast energy-based approach).

        Designed for streaming audio where we can't look ahead.
        Maintains internal state across chunks.

        State machine:
        - IDLE: Waiting for signal, estimating noise floor
        - ONSET: Detecting signal onset, require sustained signal
        - ACTIVE: Signal active, passing through audio
        - OFFSET: Detecting signal offset, require sustained silence

        Args:
            audio_chunk: Input audio chunk (float32, -1.0 to 1.0)

        Returns:
            (trimmed_chunk, is_signal_active)
            - trimmed_chunk: Audio with silence removed
            - is_signal_active: True if currently detecting signal
        """
        output_samples = []

        for sample in audio_chunk:
            sample_power = sample * sample

            # Update power buffer (sliding window)
            self._rt_power_buffer.append(sample_power)
            if len(self._rt_power_buffer) > 0:
                current_power = np.mean(self._rt_power_buffer)
            else:
                current_power = sample_power

            # Calculate dynamic threshold
            if self._rt_noise_floor > self.low_noise_threshold:
                signal_threshold = max(
                    self.min_signal_threshold,
                    self._rt_noise_floor * (10 ** (self.snr_threshold_db / 10))
                )
            else:
                signal_threshold = self.min_signal_threshold

            # State machine
            if not self._rt_signal_active:
                # IDLE or ONSET state

                if current_power < self.low_noise_threshold:
                    # Very low power - update noise floor
                    self._rt_noise_samples += 1
                    alpha = min(0.1, 1.0 / max(1, self._rt_noise_samples))
                    self._rt_noise_floor = (1 - alpha) * self._rt_noise_floor + alpha * current_power
                    self._rt_onset_counter = 0
                    self._rt_onset_buffer = []
                    # Don't output (trimming silence)

                elif current_power > signal_threshold:
                    # Above signal threshold - onset detection
                    self._rt_onset_counter += 1
                    self._rt_onset_buffer.append(sample)

                    # Require sustained signal before activation
                    onset_required = int(self.rt_onset_duration * self.sample_rate)
                    if self._rt_onset_counter >= onset_required:
                        self._rt_signal_active = True
                        # Output buffered onset samples
                        output_samples.extend(self._rt_onset_buffer)
                        self._rt_onset_buffer = []
                    # Don't output yet (still in onset phase)

                else:
                    # Moderate power (noise) - update noise floor but don't process
                    self._rt_noise_samples += 1
                    alpha = min(0.1, 1.0 / max(1, self._rt_noise_samples))
                    self._rt_noise_floor = (1 - alpha) * self._rt_noise_floor + alpha * current_power
                    self._rt_onset_counter = 0
                    self._rt_onset_buffer = []
                    # Don't output

            else:
                # ACTIVE or OFFSET state

                if current_power > signal_threshold:
                    # Still above signal threshold
                    self._rt_offset_counter = 0
                    output_samples.append(sample)

                else:
                    # Below threshold - offset detection
                    self._rt_offset_counter += 1

                    # Require sustained silence before deactivation
                    offset_required = int(self.rt_offset_duration * self.sample_rate)
                    if self._rt_offset_counter >= offset_required:
                        # Signal ended
                        self._rt_signal_active = False
                        self._rt_onset_counter = 0
                        self._rt_offset_counter = 0
                        # Don't output (trailing silence)
                    else:
                        # Still in offset grace period - output sample
                        output_samples.append(sample)

        # Convert to numpy array
        trimmed_chunk = np.array(output_samples, dtype=np.float32)

        return trimmed_chunk, self._rt_signal_active

    def reset(self):
        """Reset internal state for real-time trimming (call between transmissions)."""
        self._rt_noise_floor = 0.001
        self._rt_noise_samples = 0
        self._rt_signal_active = False
        self._rt_onset_counter = 0
        self._rt_offset_counter = 0
        self._rt_power_buffer.clear()
        self._rt_onset_buffer = []

    def configure(
        self,
        snr_threshold_db: Optional[float] = None,
        noise_window_duration: Optional[float] = None,
        min_signal_duration: Optional[float] = None,
        edge_margin_duration: Optional[float] = None,
    ):
        """
        Update configuration parameters.

        Args:
            snr_threshold_db: New SNR threshold in dB
            noise_window_duration: New noise window duration in seconds
            min_signal_duration: New minimum signal duration in seconds
            edge_margin_duration: New edge margin duration in seconds
        """
        if snr_threshold_db is not None:
            self.snr_threshold_db = snr_threshold_db
            # Use higher threshold for coarse detection
            coarse_threshold_db = max(self.snr_threshold_db, 12.0)
            self._signal_detector = SignalDetector(
                sample_rate=self.sample_rate,
                threshold_db=coarse_threshold_db,
            )

        if noise_window_duration is not None:
            self.noise_window_duration = noise_window_duration
            self.noise_window_samples = int(self.noise_window_duration * self.sample_rate)

        if min_signal_duration is not None:
            self.min_signal_duration = min_signal_duration
            self.min_signal_samples = int(self.min_signal_duration * self.sample_rate)

        if edge_margin_duration is not None:
            self.edge_margin_duration = edge_margin_duration
            self.edge_margin_samples = int(self.edge_margin_duration * self.sample_rate)

    # Helper methods for deep search

    def _energy_coarse_detection(self, audio: np.ndarray) -> Tuple[Optional[int], Optional[int]]:
        """
        Energy-based coarse detection (fallback when FFT fails).

        Uses sliding window energy to find approximate signal boundaries.
        More robust to noise than FFT-based detection.

        Returns:
            (coarse_start, coarse_end) or (None, None) if no signal found
        """
        # Use larger window for coarse detection
        window_size = self.fft_window_size  # Same as FFT window
        hop_size = self.fft_hop_size

        # Estimate initial noise floor from first window
        if len(audio) > window_size:
            first_window = audio[:window_size]
            noise_floor = np.percentile(first_window ** 2, 25)
        else:
            noise_floor = np.percentile(audio ** 2, 5)

        # Calculate threshold (higher than fine detection for robustness)
        signal_threshold = max(
            self.min_signal_threshold,
            noise_floor * (10 ** ((self.snr_threshold_db + 6) / 10))  # +6 dB stricter
        )

        # Scan for signal regions
        signal_regions = []
        for i in range(0, len(audio) - window_size, hop_size):
            window = audio[i:i + window_size]
            window_power = np.mean(window ** 2)

            if window_power > signal_threshold:
                signal_regions.append(i)

        if not signal_regions:
            return None, None

        # Find start and end of signal region
        coarse_start = signal_regions[0]
        coarse_end = signal_regions[-1] + window_size

        return coarse_start, coarse_end

    def _fft_coarse_detection(self, audio: np.ndarray) -> Tuple[Optional[int], Optional[int], int]:
        """
        Phase 1: FFT-based coarse detection.

        Scans audio in overlapping windows to find carrier presence.
        Returns approximate signal boundaries.

        Returns:
            (coarse_start, coarse_end, num_carrier_windows)
        """
        carrier_presence = []

        # Scan with overlapping windows
        for window_start in range(0, len(audio) - self.fft_window_size, self.fft_hop_size):
            window = audio[window_start:window_start + self.fft_window_size]
            peaks = self._signal_detector.detect(window, num_peaks=1)

            # Record presence and SNR
            if peaks and len(peaks) > 0:
                carrier_presence.append({
                    'sample': window_start,
                    'snr': peaks[0].snr,
                    'present': True
                })
            else:
                carrier_presence.append({
                    'sample': window_start,
                    'snr': 0.0,
                    'present': False
                })

        # Find coarse signal region (first and last carrier detections)
        signal_windows = [w for w in carrier_presence if w['present']]

        if not signal_windows:
            # No signal detected
            return None, None, 0

        coarse_start = signal_windows[0]['sample']
        coarse_end = signal_windows[-1]['sample'] + self.fft_window_size

        return coarse_start, coarse_end, len(signal_windows)

    def _estimate_noise_floor(self, audio: np.ndarray, coarse_start: int) -> float:
        """
        Phase 2: Noise floor estimation using percentile method.

        Uses ONLY pre-signal region to avoid "noise floor grows with signal" bug.

        Args:
            audio: Full audio array
            coarse_start: Start of coarse signal region

        Returns:
            Noise floor power (not dB)
        """
        # Extract pre-signal region for noise estimation
        noise_samples = min(self.noise_window_samples, coarse_start)

        if noise_samples > 100:
            # Enough pre-signal data - use it exclusively
            pre_signal_audio = audio[max(0, coarse_start - noise_samples):coarse_start]

            # Compute power for each sample
            power = pre_signal_audio ** 2

            # Use 25th percentile (robust to outliers and signal ramp-up)
            # This prevents the noise floor from "growing" to match signal
            noise_floor = np.percentile(power, 25)
        else:
            # Not enough pre-signal data
            # If coarse_start is very early (< noise_window), use the first noise_window samples
            # This handles the case where FFT detects noise as weak signal
            if len(audio) > self.noise_window_samples:
                pre_signal_audio = audio[:self.noise_window_samples]
                power = pre_signal_audio ** 2
                noise_floor = np.percentile(power, 25)
            else:
                # Very short audio - estimate from entire audio
                power = audio ** 2
                # Use very low percentile to avoid including signal
                noise_floor = np.percentile(power, 5)

        return noise_floor

    def _calculate_signal_threshold(self, noise_floor: float) -> float:
        """
        Calculate signal detection threshold.

        Uses dynamic threshold: absolute minimum + relative to noise floor.

        Args:
            noise_floor: Estimated noise floor power

        Returns:
            Signal threshold power
        """
        # SNR-based threshold
        relative_threshold = noise_floor * (10 ** (self.snr_threshold_db / 10))

        # Use higher of absolute minimum or relative threshold
        signal_threshold = max(self.min_signal_threshold, relative_threshold)

        return signal_threshold

    def _find_signal_onset(
        self,
        audio: np.ndarray,
        coarse_start: int,
        coarse_end: int,
        noise_floor: float,
        signal_threshold: float,
    ) -> int:
        """
        Phase 3: Find precise signal onset (start boundary).

        Handles signal ramp-up by requiring sustained signal above threshold.
        This prevents false triggers from noise spikes or initial ramp-up.

        Args:
            audio: Full audio array
            coarse_start: Coarse signal start from FFT detection
            coarse_end: Coarse signal end from FFT detection
            noise_floor: Estimated noise floor power
            signal_threshold: Power threshold for signal detection

        Returns:
            Precise signal start index
        """
        # Search region: expand coarse boundary for safety
        search_margin = int(0.1 * self.sample_rate)  # 100ms margin
        search_start = max(0, coarse_start - search_margin)
        search_end = min(len(audio), coarse_start + search_margin)
        search_audio = audio[search_start:search_end]

        # Sliding window power
        consecutive_signal = 0
        onset_samples_required = int(self.min_signal_duration * self.sample_rate)

        for i in range(len(search_audio) - self.energy_window_samples):
            window = search_audio[i:i + self.energy_window_samples]
            window_power = np.mean(window ** 2)

            if window_power > signal_threshold:
                consecutive_signal += 1

                # Sustained signal detected
                if consecutive_signal >= onset_samples_required:
                    # Back up to find true start (before sustained region)
                    # Search backward for first sample above 2x noise floor
                    for j in range(i, max(0, i - onset_samples_required), -1):
                        if search_audio[j] ** 2 < noise_floor * 2:
                            return search_start + j + 1
                    # Fallback: return midpoint of onset region
                    return search_start + max(0, i - onset_samples_required // 2)
            else:
                consecutive_signal = 0

        # No onset found, return coarse start
        return coarse_start

    def _find_signal_offset(
        self,
        audio: np.ndarray,
        coarse_start: int,
        coarse_end: int,
        noise_floor: float,
        signal_threshold: float,
    ) -> int:
        """
        Phase 3: Find precise signal offset (end boundary).

        Searches backward from coarse end to find last sustained signal.

        Args:
            audio: Full audio array
            coarse_start: Coarse signal start from FFT detection
            coarse_end: Coarse signal end from FFT detection
            noise_floor: Estimated noise floor power
            signal_threshold: Power threshold for signal detection

        Returns:
            Precise signal end index
        """
        # Search region: expand coarse boundary for safety
        search_margin = int(0.1 * self.sample_rate)  # 100ms margin
        search_start = max(0, coarse_end - search_margin)
        search_end = min(len(audio), coarse_end + search_margin)
        search_audio = audio[search_start:search_end]

        # Search backward
        consecutive_silence = 0
        offset_samples_required = int(self.min_signal_duration * self.sample_rate)

        for i in range(len(search_audio) - self.energy_window_samples, -1, -1):
            if i < 0:
                break
            window = search_audio[i:i + self.energy_window_samples]
            window_power = np.mean(window ** 2)

            if window_power < signal_threshold:
                consecutive_silence += 1

                # Sustained silence detected
                if consecutive_silence >= offset_samples_required:
                    # Search forward to find precise end (first sample below noise)
                    for j in range(i, min(len(search_audio), i + offset_samples_required)):
                        if search_audio[j] ** 2 < noise_floor * 2:
                            return search_start + j
                    # Fallback: return midpoint of offset region
                    return search_start + i + offset_samples_required // 2
            else:
                consecutive_silence = 0

        # No offset found, return coarse end
        return coarse_end

    def _empty_result(self) -> TrimResult:
        """Return empty TrimResult for when no signal is detected."""
        return TrimResult(
            trimmed_audio=np.array([], dtype=np.float32),
            signal_start=0,
            signal_end=0,
            leading_samples_removed=0,
            trailing_samples_removed=0,
            noise_floor=0.0,
            peak_snr_db=0.0,
            detection_method='deep_search',
            metadata={'no_signal_detected': True}
        )
