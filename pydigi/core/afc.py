"""
Automatic Frequency Control (AFC)

This module provides frequency tracking and correction for digital receivers.
AFC compensates for frequency offset between transmitter and receiver due to:
    - Radio oscillator drift (temperature, aging)
    - Doppler shift (moving stations)
    - Operator tuning error

Reference:
    - fldigi: Search for 'afcmetric', 'freqerr', 'set_freq()' in mode implementations
    - Gardner, "Phaselock Techniques" 3rd ed.
    - Lyons, "Understanding Digital Signal Processing"
"""

import numpy as np
from typing import Optional, Tuple


class PhaseAFC:
    """
    AFC for phase-based modulations (PSK, QPSK, 8PSK).

    Tracks frequency offset by measuring phase drift over time.
    Since frequency is the derivative of phase:
        freq_error = phase_drift / (2π × time)

    The AFC integrates phase error measurements to estimate
    the frequency offset, then adjusts the receiver NCO.

    Algorithm:
        1. Measure phase error from demodulator
        2. Low-pass filter to get phase drift rate
        3. Convert phase drift to frequency offset
        4. Update NCO to compensate

    Example:
        >>> afc = PhaseAFC(alpha=0.01, max_offset=100.0)
        >>> nco = NCO(frequency=1000.0, sample_rate=8000)
        >>>
        >>> for sample in samples:
        >>>     # Mix down to baseband
        >>>     baseband = sample * nco.mix_down()
        >>>
        >>>     # Demodulate and get phase error
        >>>     phase_error = demodulate(baseband)
        >>>
        >>>     # Update AFC
        >>>     freq_offset = afc.update(phase_error)
        >>>     nco.set_frequency(1000.0 + freq_offset)
    """

    def __init__(
        self,
        alpha: float = 0.01,
        max_offset: float = 100.0,
        damping: float = 1.0
    ):
        """
        Initialize phase-based AFC.

        Args:
            alpha: Tracking rate (0-1)
                  Lower = slower tracking, more stable
                  Higher = faster tracking, less stable
                  Typical values: 0.001 to 0.1
            max_offset: Maximum frequency offset (Hz)
                       Clamps correction to prevent runaway
            damping: Damping factor for 2nd-order loop
                    1.0 = critically damped (default)
                    < 1.0 = underdamped (faster, may oscillate)
                    > 1.0 = overdamped (slower, very stable)
        """
        self.alpha = alpha
        self.max_offset = max_offset
        self.damping = damping

        # State variables
        self.freq_offset = 0.0  # Current frequency offset estimate (Hz)
        self.phase_accum = 0.0  # Accumulated phase for 2nd-order loop

        # For bandwidth calculation
        self.omega_n = alpha  # Natural frequency
        self.zeta = damping   # Damping factor

    def update(self, phase_error: float, symbol_rate: Optional[float] = None) -> float:
        """
        Update frequency offset estimate from phase error.

        Args:
            phase_error: Phase error in radians
                        Positive = signal phase leading
                        Negative = signal phase lagging
            symbol_rate: Optional symbol rate (Hz) for scaling
                        If provided, converts phase error per symbol
                        to frequency error

        Returns:
            Current frequency offset estimate (Hz)

        Note:
            For PSK demodulators, phase_error typically comes from:
                phase_error = angle(received_symbol * conj(expected_symbol))
        """
        # Simple first-order loop
        # Frequency is derivative of phase, so integrate phase error
        self.freq_offset += self.alpha * phase_error

        # Clamp to max offset
        self.freq_offset = np.clip(
            self.freq_offset,
            -self.max_offset,
            self.max_offset
        )

        return self.freq_offset

    def update_2nd_order(
        self,
        phase_error: float,
        loop_gain: float = 1.0
    ) -> float:
        """
        Update using 2nd-order loop for better tracking.

        A 2nd-order loop has both proportional and integral paths,
        providing better steady-state tracking of constant frequency offsets.

        Args:
            phase_error: Phase error in radians
            loop_gain: Overall loop gain multiplier

        Returns:
            Current frequency offset estimate (Hz)
        """
        # Proportional + Integral loop filter
        # Gains from natural frequency and damping
        K_p = 2 * self.zeta * self.omega_n * loop_gain
        K_i = (self.omega_n ** 2) * loop_gain

        # Proportional path (immediate correction)
        freq_correction = K_p * phase_error

        # Integral path (accumulated correction)
        self.phase_accum += K_i * phase_error
        self.phase_accum = np.clip(self.phase_accum, -self.max_offset, self.max_offset)

        # Total frequency offset
        self.freq_offset = freq_correction + self.phase_accum
        self.freq_offset = np.clip(self.freq_offset, -self.max_offset, self.max_offset)

        return self.freq_offset

    def reset(self):
        """Reset AFC state."""
        self.freq_offset = 0.0
        self.phase_accum = 0.0

    def get_offset(self) -> float:
        """Get current frequency offset estimate."""
        return self.freq_offset


class ToneAFC:
    """
    AFC for tone-based modulations (MFSK, FSQ, RTTY).

    Detects actual tone frequencies and compares to expected
    frequencies to estimate offset. Adjusts receiver center
    frequency to lock onto the signal.

    Algorithm:
        1. Detect strongest tone in FFT or Goertzel output
        2. Compare to expected tone center frequency
        3. Error = detected_freq - expected_freq
        4. Low-pass filter the error
        5. Adjust receiver center frequency

    Example:
        >>> # For MFSK16 centered at 1500 Hz
        >>> afc = ToneAFC(center_freq=1500.0, alpha=0.05)
        >>>
        >>> # Detect tone from FFT
        >>> detected_tone_freq = find_peak_frequency(fft_output)
        >>>
        >>> # Update AFC
        >>> freq_offset = afc.update(detected_tone_freq)
        >>> actual_center = 1500.0 + freq_offset
    """

    def __init__(
        self,
        center_freq: float,
        alpha: float = 0.05,
        max_offset: float = 50.0,
        enable: bool = True
    ):
        """
        Initialize tone-based AFC.

        Args:
            center_freq: Expected center frequency (Hz)
            alpha: Tracking rate (0-1)
                  Typical values: 0.01 to 0.1
                  Higher for MFSK (faster tones)
                  Lower for RTTY (slower symbols)
            max_offset: Maximum frequency offset (Hz)
            enable: Enable/disable AFC (useful for testing)
        """
        self.center_freq = center_freq
        self.alpha = alpha
        self.max_offset = max_offset
        self.enable = enable

        # State
        self.freq_offset = 0.0

        # Statistics for adaptive AFC
        self.tone_history = []
        self.max_history = 10

    def update(self, detected_freq: float) -> float:
        """
        Update offset from detected tone frequency.

        Args:
            detected_freq: Detected tone frequency (Hz)

        Returns:
            Current frequency offset estimate (Hz)
        """
        if not self.enable:
            return 0.0

        # Calculate error
        error = detected_freq - self.center_freq

        # Update offset with low-pass filter
        self.freq_offset += self.alpha * error

        # Clamp
        self.freq_offset = np.clip(
            self.freq_offset,
            -self.max_offset,
            self.max_offset
        )

        # Update history for statistics
        self.tone_history.append(detected_freq)
        if len(self.tone_history) > self.max_history:
            self.tone_history.pop(0)

        return self.freq_offset

    def update_from_bins(
        self,
        tone_bins: np.ndarray,
        bin_frequencies: np.ndarray,
        threshold: float = 0.1
    ) -> float:
        """
        Update AFC from multiple tone bins.

        For MFSK modes, we often have multiple tone bins.
        This method finds the strongest tone and uses it for AFC.

        Args:
            tone_bins: Array of tone magnitudes
            bin_frequencies: Corresponding frequencies for each bin
            threshold: Minimum magnitude threshold (relative to max)

        Returns:
            Current frequency offset estimate (Hz)
        """
        if not self.enable:
            return 0.0

        # Find strongest tone
        max_magnitude = np.max(tone_bins)
        if max_magnitude < 1e-10:
            return self.freq_offset  # No signal

        # Only use tones above threshold
        strong_tones = tone_bins > (max_magnitude * threshold)
        if not np.any(strong_tones):
            return self.freq_offset

        # Use frequency of strongest tone
        strongest_idx = np.argmax(tone_bins)
        detected_freq = bin_frequencies[strongest_idx]

        return self.update(detected_freq)

    def reset(self):
        """Reset AFC state."""
        self.freq_offset = 0.0
        self.tone_history = []

    def get_offset(self) -> float:
        """Get current frequency offset estimate."""
        return self.freq_offset

    def get_statistics(self) -> dict:
        """
        Get AFC statistics.

        Returns:
            Dictionary with:
                - mean_freq: Mean detected frequency
                - std_freq: Standard deviation of frequency
                - offset: Current offset estimate
        """
        if len(self.tone_history) < 2:
            return {
                'mean_freq': self.center_freq,
                'std_freq': 0.0,
                'offset': self.freq_offset
            }

        history = np.array(self.tone_history)
        return {
            'mean_freq': np.mean(history),
            'std_freq': np.std(history),
            'offset': self.freq_offset
        }


class PLL:
    """
    Phase-Locked Loop for carrier tracking.

    A PLL is a feedback control system that locks onto the phase
    and frequency of an input signal. It's more sophisticated than
    simple AFC and provides better tracking under difficult conditions.

    Components:
        1. Phase Detector: Measures phase error
        2. Loop Filter: Smooths error signal (proportional + integral)
        3. NCO: Adjusts frequency/phase based on filtered error

    This is a digital 2nd-order PLL implementation.

    Reference:
        Gardner, F. "Phaselock Techniques" 3rd ed.
        Best, R. "Phase-Locked Loops: Design, Simulation, and Applications"

    Example:
        >>> pll = PLL(bandwidth=0.01, damping=0.707)
        >>>
        >>> for sample in samples:
        >>>     # Get PLL output (tracking carrier)
        >>>     carrier = pll.step(sample)
        >>>
        >>>     # Baseband signal
        >>>     baseband = sample * np.conj(carrier)
    """

    def __init__(
        self,
        bandwidth: float = 0.01,
        damping: float = 0.707,
        max_freq_offset: float = 100.0
    ):
        """
        Initialize PLL.

        Args:
            bandwidth: Loop bandwidth (normalized frequency, 0-0.5)
                      Lower = narrower tracking, more filtering
                      Higher = wider tracking, faster response
                      Typical: 0.001 to 0.1
            damping: Damping factor (zeta)
                    0.707 = critically damped (Butterworth response)
                    1.0 = overdamped (no overshoot)
                    < 0.707 = underdamped (may oscillate)
            max_freq_offset: Maximum frequency offset (Hz)
        """
        self.bandwidth = bandwidth
        self.damping = damping
        self.max_freq_offset = max_freq_offset

        # Calculate loop filter gains
        # Using natural frequency formulation
        omega_n = bandwidth * 2 * np.pi
        self.K_p = 2 * damping * omega_n  # Proportional gain
        self.K_i = omega_n ** 2            # Integral gain

        # PLL state
        self.phase = 0.0  # Current phase estimate (radians)
        self.freq = 0.0   # Current frequency estimate (rad/sample)
        self.freq_accum = 0.0  # Accumulated frequency (for integral path)

    def step(self, sample: complex) -> complex:
        """
        Process one sample through PLL.

        Args:
            sample: Input complex sample

        Returns:
            PLL output (tracking carrier)
        """
        # Generate current carrier estimate
        carrier = np.exp(1j * self.phase)

        # Phase detector: multiply input by conjugate of carrier
        # Phase error = angle of result
        error_signal = sample * np.conj(carrier)
        phase_error = np.angle(error_signal)

        # Loop filter (proportional + integral)
        # Proportional path
        freq_correction = self.K_p * phase_error

        # Integral path
        self.freq_accum += self.K_i * phase_error

        # Total frequency
        self.freq = freq_correction + self.freq_accum

        # Clamp frequency to prevent runaway
        max_freq_rad = self.max_freq_offset * 2 * np.pi
        self.freq = np.clip(self.freq, -max_freq_rad, max_freq_rad)

        # Update phase
        self.phase += self.freq
        # Wrap phase to [-π, π]
        self.phase = np.angle(np.exp(1j * self.phase))

        return carrier

    def process(self, samples: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Process block of samples.

        Args:
            samples: Input complex samples

        Returns:
            (tracked_carriers, phase_errors) tuple
        """
        carriers = np.zeros(len(samples), dtype=complex)
        phase_errors = np.zeros(len(samples))

        for i, sample in enumerate(samples):
            carriers[i] = self.step(sample)
            # Calculate phase error for monitoring
            error_signal = sample * np.conj(carriers[i])
            phase_errors[i] = np.angle(error_signal)

        return carriers, phase_errors

    def reset(self):
        """Reset PLL state."""
        self.phase = 0.0
        self.freq = 0.0
        self.freq_accum = 0.0

    def get_frequency(self) -> float:
        """Get current frequency estimate (radians/sample)."""
        return self.freq

    def get_phase(self) -> float:
        """Get current phase estimate (radians)."""
        return self.phase

    def set_bandwidth(self, bandwidth: float):
        """
        Adjust loop bandwidth dynamically.

        Useful for acquisition (wide bandwidth) vs tracking (narrow bandwidth).

        Args:
            bandwidth: New loop bandwidth (normalized, 0-0.5)
        """
        self.bandwidth = bandwidth
        omega_n = bandwidth * 2 * np.pi
        self.K_p = 2 * self.damping * omega_n
        self.K_i = omega_n ** 2
