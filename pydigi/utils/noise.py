"""
Noise Generation and Channel Impairments

This module provides tools for adding realistic channel impairments
to signals for testing decoder performance.

Includes:
    - AWGN (Additive White Gaussian Noise)
    - Frequency offset simulation
    - Phase noise
    - Multipath fading
    - Timing jitter

Use these for:
    - Testing decoder performance at various SNR levels
    - Validating AFC and timing recovery
    - Characterizing BER vs Eb/N0
"""

import numpy as np
from typing import Optional


def add_awgn(signal: np.ndarray, snr_db: float, signal_power: Optional[float] = None) -> np.ndarray:
    """
    Add Additive White Gaussian Noise to achieve target SNR.

    AWGN is the standard channel noise model used for testing
    digital communication systems. This function adds zero-mean
    Gaussian noise with variance calculated to achieve the specified SNR.

    SNR Definition:
        SNR (dB) = 10 * log10(P_signal / P_noise)

    Args:
        signal: Input signal (complex or real numpy array)
        snr_db: Desired signal-to-noise ratio in dB
               Higher SNR = less noise (cleaner signal)
               Typical values:
                 - 30 dB: Very strong signal
                 - 20 dB: Strong signal
                 - 10 dB: Moderate signal
                 - 0 dB: Weak signal (signal power = noise power)
                 - -3 dB: Very weak signal
        signal_power: Optional pre-calculated signal power (linear).
                     If None, will be calculated from signal.
                     Useful when adding noise to multiple blocks.

    Returns:
        Noisy signal with same dtype as input

    Example:
        >>> # Clean PSK signal
        >>> signal = psk_modulate("Hello")
        >>>
        >>> # Add noise for 10 dB SNR
        >>> noisy = add_awgn(signal, snr_db=10.0)
        >>>
        >>> # Test decoder at various SNR levels
        >>> for snr in [0, 5, 10, 15, 20]:
        >>>     noisy = add_awgn(signal, snr)
        >>>     decoded = decoder.decode(noisy)
        >>>     print(f"SNR {snr} dB: {decoded}")
    """
    # Calculate signal power if not provided
    if signal_power is None:
        signal_power = np.mean(np.abs(signal) ** 2)

    # Convert SNR from dB to linear
    snr_linear = 10 ** (snr_db / 10)

    # Calculate required noise power
    noise_power = signal_power / snr_linear

    # Generate noise with appropriate statistics
    if np.iscomplexobj(signal):
        # For complex signals: split power equally between I and Q
        # E[|n|²] = E[|n_I|²] + E[|n_Q|²] = 2σ²
        # Therefore σ² = noise_power / 2
        sigma = np.sqrt(noise_power / 2)
        noise = sigma * (np.random.randn(len(signal)) + 1j * np.random.randn(len(signal)))
    else:
        # For real signals: all power in one dimension
        sigma = np.sqrt(noise_power)
        noise = sigma * np.random.randn(len(signal))

    return signal + noise


def add_frequency_offset(signal: np.ndarray, offset_hz: float, sample_rate: float) -> np.ndarray:
    """
    Add frequency offset to simulate radio mistuning.

    Multiplies signal by exp(j*2*pi*offset*t) to shift frequency.
    This simulates:
        - Radio oscillator drift
        - Doppler shift
        - User tuning error

    Args:
        signal: Input signal (complex)
        offset_hz: Frequency offset in Hz
                  Positive = shift up
                  Negative = shift down
        sample_rate: Sample rate in Hz

    Returns:
        Frequency-shifted signal

    Example:
        >>> # Simulate 50 Hz tuning error
        >>> signal_offset = add_frequency_offset(signal, 50.0, 8000)
        >>>
        >>> # Test AFC
        >>> decoded = decoder.decode(signal_offset)
    """
    t = np.arange(len(signal)) / sample_rate
    offset_carrier = np.exp(2j * np.pi * offset_hz * t)
    return signal * offset_carrier


def add_phase_noise(
    signal: np.ndarray,
    phase_noise_std: float,
    sample_rate: float,
    corner_freq: float = 100.0
) -> np.ndarray:
    """
    Add phase noise to simulate oscillator jitter.

    Phase noise is modeled as filtered Gaussian noise integrated
    to produce random walk in phase. This simulates:
        - VCO/PLL jitter
        - Crystal oscillator noise
        - Thermal noise in RF frontend

    Args:
        signal: Input signal (complex)
        phase_noise_std: Standard deviation of phase noise (radians)
                        Typical values: 0.01 to 0.1 radians
        sample_rate: Sample rate in Hz
        corner_freq: Corner frequency for 1/f noise shaping (Hz)

    Returns:
        Signal with phase noise

    Example:
        >>> # Add 0.05 radian RMS phase noise
        >>> noisy = add_phase_noise(signal, 0.05, 8000)
    """
    # Generate white Gaussian phase noise
    phase_noise = np.random.randn(len(signal)) * phase_noise_std

    # Optional: shape with 1/f filter for more realistic PLL noise
    # For now, use white phase noise

    # Integrate phase noise (random walk)
    phase = np.cumsum(phase_noise)

    # Apply phase rotation
    rotation = np.exp(1j * phase)
    return signal * rotation


def add_timing_jitter(
    signal: np.ndarray,
    jitter_std: float,
    samples_per_symbol: int
) -> np.ndarray:
    """
    Add timing jitter to symbol clock.

    Resamples signal with random timing offsets to simulate:
        - Clock jitter
        - Sample rate offset
        - Timing noise

    Args:
        signal: Input signal
        jitter_std: Standard deviation of timing jitter (samples)
                   Typical values: 0.01 to 0.1 samples
        samples_per_symbol: Samples per symbol

    Returns:
        Signal with timing jitter

    Note:
        This is a simplified model. For production testing,
        use proper resampling with fractional delays.
    """
    # Generate jitter sequence
    jitter = np.random.randn(len(signal) // samples_per_symbol) * jitter_std

    # Interpolate jitter to sample rate
    jitter_upsampled = np.repeat(jitter, samples_per_symbol)[:len(signal)]

    # Create time indices with jitter
    t_ideal = np.arange(len(signal))
    t_jittered = t_ideal + jitter_upsampled

    # Clip to valid range
    t_jittered = np.clip(t_jittered, 0, len(signal) - 1)

    # Interpolate signal at jittered times
    # Simple nearest-neighbor for now
    indices = np.round(t_jittered).astype(int)
    return signal[indices]


def add_multipath_fading(
    signal: np.ndarray,
    delays_samples: list,
    gains: list,
    sample_rate: float
) -> np.ndarray:
    """
    Add multipath fading (multiple delayed copies of signal).

    Simulates propagation through multiple paths with different
    delays and gains. Common in:
        - HF ionospheric propagation
        - Urban VHF/UHF with reflections
        - NVIS (Near Vertical Incidence Skywave)

    Args:
        signal: Input signal
        delays_samples: List of delays for each path (in samples)
        gains: List of gains for each path (linear, not dB)
               Should sum to approximately 1.0
        sample_rate: Sample rate in Hz

    Returns:
        Signal with multipath fading

    Example:
        >>> # Two-path fading: direct + delayed echo at 50% strength
        >>> faded = add_multipath_fading(
        >>>     signal,
        >>>     delays_samples=[0, 100],  # 0 ms and 12.5 ms @ 8 kHz
        >>>     gains=[1.0, 0.5]
        >>> )
    """
    output = np.zeros(len(signal), dtype=signal.dtype)

    for delay, gain in zip(delays_samples, gains):
        # Create delayed copy
        delayed = np.zeros(len(signal), dtype=signal.dtype)
        if delay < len(signal):
            delayed[delay:] = signal[:-delay] if delay > 0 else signal
            output += gain * delayed

    return output


def calculate_signal_power(signal: np.ndarray) -> float:
    """
    Calculate average power of signal.

    Args:
        signal: Input signal (complex or real)

    Returns:
        Average power (linear, not dB)

    Example:
        >>> power = calculate_signal_power(signal)
        >>> power_dbw = 10 * np.log10(power)
    """
    return np.mean(np.abs(signal) ** 2)


def db_to_linear(db: float) -> float:
    """Convert dB to linear scale."""
    return 10 ** (db / 10)


def linear_to_db(linear: float) -> float:
    """Convert linear to dB scale."""
    return 10 * np.log10(linear + 1e-10)


def estimate_snr(
    signal_with_noise: np.ndarray,
    noise_only: Optional[np.ndarray] = None
) -> float:
    """
    Estimate SNR of a noisy signal.

    Args:
        signal_with_noise: Received signal with noise
        noise_only: Optional noise-only samples for direct measurement
                   If None, uses signal variance estimation

    Returns:
        Estimated SNR in dB

    Example:
        >>> # Method 1: With known noise reference
        >>> snr = estimate_snr(noisy_signal, noise_samples)
        >>>
        >>> # Method 2: From signal alone (less accurate)
        >>> snr = estimate_snr(noisy_signal)
    """
    if noise_only is not None:
        # Direct measurement
        noise_power = np.mean(np.abs(noise_only) ** 2)
        signal_power = np.mean(np.abs(signal_with_noise) ** 2)
        snr_linear = (signal_power - noise_power) / noise_power
    else:
        # Estimate from signal statistics
        # This is approximate and assumes signal variance > noise variance
        signal_power = np.mean(np.abs(signal_with_noise) ** 2)
        # Use minimum as rough noise estimate
        noise_power = np.min(np.abs(signal_with_noise) ** 2)
        snr_linear = signal_power / (noise_power + 1e-10)

    return linear_to_db(snr_linear)
