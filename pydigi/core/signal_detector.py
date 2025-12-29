"""
Signal detection and frequency estimation.

Provides automatic carrier frequency detection for PSK and other modes
using FFT-based peak detection.
"""

import numpy as np
from typing import List, Tuple, Optional
from dataclasses import dataclass
from .freq_estimators import (
    parabolic_interpolation,
    quinn_estimator,
    jacobsen_estimator,
    gaussian_interpolation,
    multi_estimator_average,
    zero_padded_fft_estimate,
)


@dataclass
class SignalPeak:
    """Detected signal peak."""
    frequency: float  # Hz
    magnitude: float  # Relative magnitude
    snr: float  # Approximate SNR in dB


class SignalDetector:
    """
    Automatic signal detector using FFT-based peak detection.

    This detector finds strong carrier signals in the audio spectrum,
    useful for automatically tuning decoders to the correct frequency.

    Args:
        sample_rate: Audio sample rate in Hz
        fft_size: FFT window size (larger = better frequency resolution)
        min_freq: Minimum frequency to search (Hz)
        max_freq: Maximum frequency to search (Hz)
        threshold_db: Minimum SNR threshold in dB (default: 6 dB)

    Example:
        >>> detector = SignalDetector(sample_rate=8000)
        >>> peaks = detector.detect(audio_samples, num_peaks=3)
        >>> for peak in peaks:
        ...     print(f"Signal at {peak.frequency:.1f} Hz, SNR={peak.snr:.1f} dB")
    """

    def __init__(
        self,
        sample_rate: float = 8000.0,
        fft_size: int = 2048,
        min_freq: float = 500.0,
        max_freq: float = 2500.0,
        threshold_db: float = 6.0,
        estimator: str = 'multi',
    ):
        """Initialize signal detector.

        Args:
            estimator: Frequency estimation method:
                'parabolic' - Simple parabolic interpolation (fast, ±0.5-1 Hz)
                'gaussian' - Gaussian interpolation (fast, ±0.3-0.5 Hz)
                'jacobsen' - Jacobsen's estimator (fast, ±0.2-0.4 Hz)
                'quinn' - Quinn's estimator (slower, ±0.1-0.2 Hz)
                'multi' - Multi-estimator average (best, ±0.05-0.15 Hz)
                'zero_pad' - Zero-padded FFT (slow, very accurate)
        """
        self.sample_rate = sample_rate
        self.fft_size = fft_size
        self.min_freq = min_freq
        self.max_freq = max_freq
        self.threshold_db = threshold_db
        self.estimator = estimator

        # Calculate frequency resolution
        self.freq_resolution = sample_rate / fft_size

        # Calculate bin indices for search range
        self.min_bin = int(min_freq / self.freq_resolution)
        self.max_bin = int(max_freq / self.freq_resolution)

        # Window function for FFT (reduces spectral leakage)
        self.window = np.hanning(fft_size)

        # Running average for noise floor estimation
        self.noise_floor = None
        self.noise_alpha = 0.9  # Smoothing factor

    def detect(
        self,
        samples: np.ndarray,
        num_peaks: int = 1,
        min_spacing_hz: float = 100.0,
    ) -> List[SignalPeak]:
        """
        Detect signal peaks in audio samples.

        Args:
            samples: Audio samples (numpy array)
            num_peaks: Number of peaks to return (default: 1)
            min_spacing_hz: Minimum spacing between peaks in Hz (default: 100)

        Returns:
            List of SignalPeak objects, sorted by magnitude (strongest first)
        """
        # Need at least one FFT window of data
        if len(samples) < self.fft_size:
            return []

        # Take last FFT window of samples
        window_samples = samples[-self.fft_size:]

        # Apply window and compute FFT
        windowed = window_samples * self.window
        fft = np.fft.rfft(windowed)
        magnitude = np.abs(fft)

        # Convert to dB
        magnitude_db = 20 * np.log10(magnitude + 1e-10)

        # Estimate noise floor (average of lower magnitudes in search range)
        search_mags = magnitude_db[self.min_bin:self.max_bin]
        current_noise = np.percentile(search_mags, 25)  # 25th percentile

        # Update running average of noise floor
        if self.noise_floor is None:
            self.noise_floor = current_noise
        else:
            self.noise_floor = (
                self.noise_alpha * self.noise_floor +
                (1 - self.noise_alpha) * current_noise
            )

        # Find peaks in search range
        peaks = []
        min_spacing_bins = int(min_spacing_hz / self.freq_resolution)

        # Copy magnitude array for peak finding
        mag_search = magnitude_db[self.min_bin:self.max_bin].copy()

        for _ in range(num_peaks):
            # Find maximum in search range
            max_idx = np.argmax(mag_search)
            max_mag = mag_search[max_idx]

            # Calculate SNR
            snr = max_mag - self.noise_floor

            # Check if above threshold
            if snr < self.threshold_db:
                break

            # Convert bin index to frequency with sub-bin estimation
            bin_idx = self.min_bin + max_idx

            # Apply selected frequency estimator
            if 0 < max_idx < len(mag_search) - 1:
                if self.estimator == 'parabolic':
                    p, _ = parabolic_interpolation(magnitude, bin_idx)
                elif self.estimator == 'gaussian':
                    p = gaussian_interpolation(magnitude, bin_idx)
                elif self.estimator == 'jacobsen':
                    p = jacobsen_estimator(fft, bin_idx)
                elif self.estimator == 'quinn':
                    p = quinn_estimator(fft, bin_idx)
                elif self.estimator == 'multi':
                    p = multi_estimator_average(fft, magnitude, bin_idx)
                elif self.estimator == 'zero_pad':
                    # For zero-pad, we need the original signal
                    # This requires storing windowed samples - skip for now
                    # Fall back to multi-estimator
                    p = multi_estimator_average(fft, magnitude, bin_idx)
                else:
                    # Unknown estimator, use parabolic
                    p, _ = parabolic_interpolation(magnitude, bin_idx)

                # Refined frequency estimate
                frequency = (bin_idx + p) * self.freq_resolution
            else:
                # Can't interpolate at edges
                frequency = bin_idx * self.freq_resolution

            # Add peak
            peaks.append(SignalPeak(
                frequency=frequency,
                magnitude=magnitude[bin_idx],
                snr=snr
            ))

            # Zero out region around this peak to find next peak
            start = max(0, max_idx - min_spacing_bins)
            end = min(len(mag_search), max_idx + min_spacing_bins)
            mag_search[start:end] = -100.0  # Very low value

        return peaks

    def get_strongest_signal(self, samples: np.ndarray) -> Optional[float]:
        """
        Get frequency of strongest signal.

        Args:
            samples: Audio samples

        Returns:
            Frequency in Hz, or None if no signal detected
        """
        peaks = self.detect(samples, num_peaks=1)
        if peaks:
            return peaks[0].frequency
        return None

    def get_spectrum(self, samples: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Get power spectrum for visualization.

        Args:
            samples: Audio samples

        Returns:
            Tuple of (frequencies, magnitudes_db)
        """
        if len(samples) < self.fft_size:
            # Return empty spectrum
            freqs = np.fft.rfftfreq(self.fft_size, 1/self.sample_rate)
            mags = np.zeros_like(freqs)
            return freqs, mags

        # Take last FFT window
        window_samples = samples[-self.fft_size:]

        # Apply window and compute FFT
        windowed = window_samples * self.window
        fft = np.fft.rfft(windowed)
        magnitude = np.abs(fft)

        # Convert to dB
        magnitude_db = 20 * np.log10(magnitude + 1e-10)

        # Frequency bins
        freqs = np.fft.rfftfreq(self.fft_size, 1/self.sample_rate)

        return freqs, magnitude_db


class MultiSignalDetector:
    """
    Tracks multiple signals over time.

    This class maintains a list of active signals and tracks their
    frequency changes over time.

    Args:
        sample_rate: Audio sample rate in Hz
        max_signals: Maximum number of simultaneous signals to track
        update_interval: Samples between updates (default: 4000 = 0.5s at 8kHz)

    Example:
        >>> tracker = MultiSignalDetector(sample_rate=8000, max_signals=5)
        >>> # Feed audio continuously
        >>> tracker.update(audio_chunk)
        >>> active_signals = tracker.get_active_signals()
        >>> for freq in active_signals:
        ...     print(f"Active signal at {freq:.1f} Hz")
    """

    def __init__(
        self,
        sample_rate: float = 8000.0,
        max_signals: int = 5,
        update_interval: int = 4000,
    ):
        """Initialize multi-signal tracker."""
        self.sample_rate = sample_rate
        self.max_signals = max_signals
        self.update_interval = update_interval

        # Signal detector
        self.detector = SignalDetector(sample_rate=sample_rate)

        # Buffer for accumulating samples
        self.buffer = np.array([], dtype=np.float32)
        self.samples_since_update = 0

        # Tracked signals (frequency -> last_seen_time)
        self.active_signals: List[float] = []
        self.signal_history: List[List[float]] = []  # Frequency history for each signal

    def update(self, samples: np.ndarray) -> None:
        """
        Update with new audio samples.

        Args:
            samples: Audio samples to process
        """
        # Add to buffer
        self.buffer = np.append(self.buffer, samples)
        self.samples_since_update += len(samples)

        # Limit buffer size
        max_buffer = self.detector.fft_size * 4
        if len(self.buffer) > max_buffer:
            self.buffer = self.buffer[-max_buffer:]

        # Check if time to update
        if self.samples_since_update >= self.update_interval:
            self._detect_signals()
            self.samples_since_update = 0

    def _detect_signals(self) -> None:
        """Detect and update active signals."""
        # Detect peaks
        peaks = self.detector.detect(
            self.buffer,
            num_peaks=self.max_signals,
            min_spacing_hz=150.0  # Minimum spacing between PSK signals
        )

        # Update active signals list
        new_signals = [peak.frequency for peak in peaks]

        # Simple replacement strategy (could be improved with tracking)
        self.active_signals = new_signals

    def get_active_signals(self) -> List[float]:
        """
        Get list of currently active signal frequencies.

        Returns:
            List of frequencies in Hz, sorted by strength
        """
        return self.active_signals.copy()

    def reset(self) -> None:
        """Reset tracker state."""
        self.buffer = np.array([], dtype=np.float32)
        self.samples_since_update = 0
        self.active_signals = []
        self.signal_history = []
