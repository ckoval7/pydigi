"""
Data Carrier Detect (DCD) Components

This module provides signal detection algorithms for determining when
a carrier signal is present versus noise-only conditions.

DCD provides:
    - Signal presence detection
    - SNR (Signal-to-Noise Ratio) estimation
    - Squelch control
    - Signal quality metrics

Reference:
    - fldigi: Search for 'metric', 's2n', 'squelch' in mode implementations
    - Classic radar: Constant False Alarm Rate (CFAR) detectors
"""

import numpy as np
from typing import Tuple, Optional
from collections import deque


class EnergyDCD:
    """
    Energy-based Data Carrier Detect.

    Detects signal presence by comparing signal power to noise floor.
    Uses separate attack and decay time constants for stability.

    Algorithm:
        1. Measure average signal power over window
        2. Track noise floor with slow decay
        3. Compare power to threshold × noise_floor
        4. Use hysteresis to prevent flutter

    This is the simplest DCD method - suitable for most applications.

    Example:
        >>> dcd = EnergyDCD(threshold=6.0, attack=0.1, decay=0.01)
        >>> for samples in signal_blocks:
        >>>     active, snr = dcd.update(samples)
        >>>     if active:
        >>>         print(f"Signal detected! SNR: {snr:.1f} dB")
    """

    def __init__(
        self,
        threshold_db: float = 6.0,
        attack: float = 0.1,
        decay: float = 0.01,
        hysteresis_db: float = 2.0
    ):
        """
        Initialize energy-based DCD.

        Args:
            threshold_db: Threshold in dB above noise floor for detection
            attack: Attack time constant (0-1, higher = faster response to signals)
            decay: Decay time constant (0-1, higher = faster decay)
            hysteresis_db: Hysteresis for DCD state changes (prevents flutter)
        """
        self.threshold_db = threshold_db
        self.attack = attack
        self.decay = decay
        self.hysteresis_db = hysteresis_db

        # State variables
        self.noise_floor = 1e-6  # Initial noise floor estimate
        self.signal_power = 0.0  # Smoothed signal power
        self.dcd_active = False  # Current DCD state

    def update(self, samples: np.ndarray) -> Tuple[bool, float]:
        """
        Update DCD state from samples.

        Args:
            samples: Input sample array (complex or real)

        Returns:
            (dcd_active, snr_db) tuple:
                - dcd_active: True if carrier detected
                - snr_db: Estimated SNR in dB
        """
        # Calculate instantaneous power
        power = np.mean(np.abs(samples) ** 2)

        # Update noise floor (slow decay, no attack during strong signals)
        # Only update noise floor when power is low (not during signal)
        if power < self.noise_floor * 10:
            self.noise_floor = (1 - self.decay) * self.noise_floor + self.decay * power
        else:
            # Very slow decay even during signal (to handle changing noise conditions)
            self.noise_floor = (1 - self.decay * 0.01) * self.noise_floor + (self.decay * 0.01) * power

        # Ensure minimum noise floor
        self.noise_floor = max(self.noise_floor, 1e-10)

        # Update signal power estimate (fast attack, slow decay)
        if power > self.signal_power:
            # Fast attack
            self.signal_power = (1 - self.attack) * self.signal_power + self.attack * power
        else:
            # Slow decay
            self.signal_power = (1 - self.decay) * self.signal_power + self.decay * power

        # Calculate SNR
        snr_linear = self.signal_power / (self.noise_floor + 1e-10)
        snr_db = 10 * np.log10(snr_linear + 1e-10)

        # Apply hysteresis to DCD state
        if self.dcd_active:
            # Currently active - use lower threshold to turn off
            threshold = self.threshold_db - self.hysteresis_db
            self.dcd_active = snr_db > threshold
        else:
            # Currently inactive - use higher threshold to turn on
            threshold = self.threshold_db + self.hysteresis_db
            self.dcd_active = snr_db > threshold

        return self.dcd_active, snr_db

    def reset(self):
        """Reset the DCD state."""
        self.noise_floor = 1e-6
        self.signal_power = 0.0
        self.dcd_active = False

    def get_noise_floor(self) -> float:
        """Get current noise floor estimate (linear power)."""
        return self.noise_floor

    def get_signal_power(self) -> float:
        """Get current signal power estimate (linear power)."""
        return self.signal_power


class PreambleDetector:
    """
    Correlation-based preamble detection.

    Detects known synchronization patterns in the symbol stream using
    cross-correlation. More robust than energy detection for identifying
    specific signal types.

    Algorithm:
        1. Maintain sliding window buffer of symbols
        2. Correlate buffer with expected preamble pattern
        3. If correlation > threshold: preamble detected
        4. Can detect multiple preamble patterns

    Use for:
        - PSK31/63/125 phase reversal preambles
        - MFSK specific tone sequences
        - RTTY LTRS character preambles

    Example:
        >>> preamble = np.array([1, -1, 1, -1, 1, -1])  # PSK reversals
        >>> detector = PreambleDetector(preamble, threshold=0.8)
        >>> for symbol in symbols:
        >>>     if detector.update(symbol):
        >>>         print("Preamble detected!")
    """

    def __init__(self, preamble_symbols: np.ndarray, threshold: float = 0.8):
        """
        Initialize preamble detector.

        Args:
            preamble_symbols: Expected preamble pattern (array of symbols)
            threshold: Normalized correlation threshold (0-1)
                      0.5 = weak detection, 0.8 = moderate, 0.95 = strict
        """
        self.preamble = np.array(preamble_symbols)
        self.threshold = threshold
        self.length = len(self.preamble)

        # Sliding window buffer
        self.buffer = deque(maxlen=self.length)

        # Normalization factor for correlation
        self.preamble_energy = np.sum(np.abs(self.preamble) ** 2)

    def update(self, symbol: complex) -> bool:
        """
        Process one symbol and check for preamble.

        Args:
            symbol: Input symbol (complex or real)

        Returns:
            True if preamble detected, False otherwise
        """
        # Add symbol to buffer
        self.buffer.append(symbol)

        # Need full buffer for correlation
        if len(self.buffer) < self.length:
            return False

        # Calculate cross-correlation
        buffer_array = np.array(self.buffer)

        # For complex symbols: use conjugate multiplication
        if np.iscomplexobj(self.preamble):
            correlation = np.abs(np.sum(buffer_array * np.conj(self.preamble)))
        else:
            correlation = np.abs(np.sum(buffer_array * self.preamble))

        # Normalize by energies
        buffer_energy = np.sum(np.abs(buffer_array) ** 2)
        if buffer_energy < 1e-10:
            return False

        normalized_corr = correlation / np.sqrt(self.preamble_energy * buffer_energy + 1e-10)

        # Check threshold
        return normalized_corr > self.threshold

    def reset(self):
        """Clear the buffer and reset detector state."""
        self.buffer.clear()

    def get_buffer(self) -> np.ndarray:
        """Get current buffer contents."""
        return np.array(self.buffer)


class ToneDCD:
    """
    Tone-based data carrier detect for FSK modes.

    Detects presence of expected tones using Goertzel filters or FFT.
    Useful for RTTY, FSQ, MFSK, and other frequency-shift keying modes.

    Algorithm:
        1. Monitor expected tone frequencies
        2. Measure tone energy vs total energy
        3. If tone SNR > threshold: DCD active

    Example:
        >>> # For RTTY with mark=2125 Hz, space=2295 Hz
        >>> dcd = ToneDCD([2125, 2295], sample_rate=8000)
        >>> active, snr = dcd.update(samples)
    """

    def __init__(
        self,
        tone_freqs: list,
        sample_rate: float,
        threshold_db: float = 10.0,
        fft_size: int = 512
    ):
        """
        Initialize tone-based DCD.

        Args:
            tone_freqs: List of expected tone frequencies (Hz)
            sample_rate: Sample rate (Hz)
            threshold_db: Threshold in dB for tone detection
            fft_size: FFT size for spectral analysis
        """
        self.tone_freqs = np.array(tone_freqs)
        self.sample_rate = sample_rate
        self.threshold_db = threshold_db
        self.fft_size = fft_size

        # Convert frequencies to FFT bins
        self.tone_bins = np.round(self.tone_freqs * fft_size / sample_rate).astype(int)

        # State
        self.noise_floor = 1e-6
        self.dcd_active = False

    def update(self, samples: np.ndarray) -> Tuple[bool, float]:
        """
        Update DCD based on tone presence.

        Args:
            samples: Input sample array (must be at least fft_size)

        Returns:
            (dcd_active, tone_snr_db) tuple
        """
        if len(samples) < self.fft_size:
            # Not enough samples for FFT
            return self.dcd_active, 0.0

        # Take FFT of latest samples
        segment = samples[-self.fft_size:]
        spectrum = np.fft.fft(segment, n=self.fft_size)
        power_spectrum = np.abs(spectrum) ** 2

        # Measure tone energy
        tone_energy = 0.0
        for tone_bin in self.tone_bins:
            # Sum energy in tone bin and adjacent bins
            bin_range = slice(max(0, tone_bin - 2), min(self.fft_size, tone_bin + 3))
            tone_energy += np.sum(power_spectrum[bin_range])

        # Measure total energy
        total_energy = np.sum(power_spectrum)

        # Calculate SNR
        if total_energy > 1e-10:
            tone_ratio = tone_energy / total_energy
            snr_db = 10 * np.log10(tone_ratio + 1e-10)
        else:
            snr_db = -100.0

        # Update DCD state
        self.dcd_active = snr_db > self.threshold_db

        return self.dcd_active, snr_db

    def reset(self):
        """Reset the DCD state."""
        self.dcd_active = False
        self.noise_floor = 1e-6
