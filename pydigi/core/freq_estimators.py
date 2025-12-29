"""
Advanced frequency estimation algorithms.

This module implements various sub-bin frequency estimation techniques
that provide better accuracy than simple parabolic interpolation.

References:
- Quinn, B.G. (1997) "Estimating Frequency by Interpolation Using Fourier Coefficients"
- Jacobsen, E. & Kootsookos, P. (2007) "Fast, Accurate Frequency Estimators"
- Gasior, M. & Gonzalez, J.L. (2004) "Improving FFT Frequency Measurement Resolution"
"""

import numpy as np
from typing import Tuple


def parabolic_interpolation(
    fft_mag: np.ndarray,
    peak_bin: int
) -> Tuple[float, float]:
    """
    Parabolic interpolation for frequency estimation.

    Uses three points around the peak to fit a parabola.

    Args:
        fft_mag: FFT magnitude array (linear scale)
        peak_bin: Index of peak bin

    Returns:
        Tuple of (bin_offset, magnitude_correction)
        bin_offset: Fractional bin offset from peak_bin (-0.5 to 0.5)
        magnitude_correction: Correction factor for true magnitude
    """
    if peak_bin <= 0 or peak_bin >= len(fft_mag) - 1:
        return 0.0, 1.0

    alpha = fft_mag[peak_bin - 1]
    beta = fft_mag[peak_bin]
    gamma = fft_mag[peak_bin + 1]

    # Parabolic interpolation formula
    denom = alpha - 2*beta + gamma
    if abs(denom) < 1e-10:
        return 0.0, 1.0

    p = 0.5 * (alpha - gamma) / denom

    # Clamp to reasonable range
    p = max(-0.5, min(0.5, p))

    # Magnitude correction (optional)
    mag_correction = beta - 0.25 * (alpha - gamma) * p

    return p, mag_correction


def quinn_tau(x: complex) -> float:
    """
    Helper function for Quinn's estimator.

    Args:
        x: Complex FFT bin value

    Returns:
        Tau value for Quinn's estimator
    """
    return 0.25 * np.log(3 * x.real**2 + x.imag**2) - \
           (np.sqrt(6) / 24) * np.log((x.real + np.sqrt(3) * x.imag) /
                                       (x.real - np.sqrt(3) * x.imag))


def quinn_estimator(
    fft_bins: np.ndarray,
    peak_bin: int
) -> float:
    """
    Quinn's first estimator for frequency estimation.

    This is one of the most accurate single-bin estimators.
    Uses phase information from complex FFT bins.

    Reference: Quinn, B.G. (1997) IEEE TSP 45(3)

    Args:
        fft_bins: Complex FFT array
        peak_bin: Index of peak bin

    Returns:
        Fractional bin offset from peak_bin
    """
    if peak_bin <= 0 or peak_bin >= len(fft_bins) - 1:
        return 0.0

    # Get three complex bins
    y_minus = fft_bins[peak_bin - 1]
    y_0 = fft_bins[peak_bin]
    y_plus = fft_bins[peak_bin + 1]

    # Avoid division by zero
    if abs(y_0) < 1e-10:
        return 0.0

    # Calculate ratios
    delta_minus = y_minus / y_0
    delta_plus = y_plus / y_0

    # Calculate tau values
    tau_minus = quinn_tau(delta_minus)
    tau_plus = quinn_tau(delta_plus)

    # Estimate offset
    delta = (tau_plus - tau_minus) / (1 + tau_plus + tau_minus)

    # Clamp to valid range
    delta = max(-0.5, min(0.5, delta))

    return delta


def jacobsen_estimator(
    fft_bins: np.ndarray,
    peak_bin: int
) -> float:
    """
    Jacobsen's estimator for frequency estimation.

    Very simple and nearly as accurate as Quinn's estimator.
    Uses the real part of the ratio of adjacent bins.

    Reference: Jacobsen & Kootsookos (2007) IEEE SPM

    Args:
        fft_bins: Complex FFT array
        peak_bin: Index of peak bin

    Returns:
        Fractional bin offset from peak_bin
    """
    if peak_bin <= 0 or peak_bin >= len(fft_bins) - 1:
        return 0.0

    y_0 = fft_bins[peak_bin]

    if abs(y_0) < 1e-10:
        return 0.0

    # Try both neighbors and pick the larger magnitude
    delta_minus = fft_bins[peak_bin - 1] / y_0
    delta_plus = fft_bins[peak_bin + 1] / y_0

    if abs(delta_plus) > abs(delta_minus):
        delta = delta_plus.real / (1 + delta_plus.real)
    else:
        delta = -delta_minus.real / (1 + delta_minus.real)

    # Clamp to valid range
    delta = max(-0.5, min(0.5, delta))

    return delta


def phase_vocoder_estimator(
    fft1: np.ndarray,
    fft2: np.ndarray,
    peak_bin: int,
    hop_size: int,
    sample_rate: float
) -> float:
    """
    Phase vocoder method for frequency estimation.

    Uses phase difference between two consecutive FFT frames
    to estimate the true frequency with high accuracy.

    Args:
        fft1: First complex FFT array
        fft2: Second complex FFT array (from later time)
        peak_bin: Index of peak bin
        hop_size: Number of samples between FFT frames
        sample_rate: Sample rate in Hz

    Returns:
        Fractional bin offset from peak_bin
    """
    if peak_bin <= 0 or peak_bin >= len(fft1) - 1:
        return 0.0

    # Get phases
    phase1 = np.angle(fft1[peak_bin])
    phase2 = np.angle(fft2[peak_bin])

    # Phase difference
    phase_diff = phase2 - phase1

    # Unwrap phase (handle 2π wrapping)
    while phase_diff > np.pi:
        phase_diff -= 2 * np.pi
    while phase_diff < -np.pi:
        phase_diff += 2 * np.pi

    # Expected phase advance for bin center frequency
    expected_phase = 2 * np.pi * peak_bin * hop_size / len(fft1)

    # Deviation from expected
    phase_deviation = phase_diff - expected_phase

    # Unwrap deviation
    while phase_deviation > np.pi:
        phase_deviation -= 2 * np.pi
    while phase_deviation < -np.pi:
        phase_deviation += 2 * np.pi

    # Convert to frequency offset in bins
    delta = phase_deviation * len(fft1) / (2 * np.pi * hop_size)

    # Clamp to valid range
    delta = max(-0.5, min(0.5, delta))

    return delta


def gaussian_interpolation(
    fft_mag: np.ndarray,
    peak_bin: int
) -> float:
    """
    Gaussian interpolation for frequency estimation.

    Fits a Gaussian (in log scale) to the peak, which often
    matches windowed sinusoids better than parabolic.

    Args:
        fft_mag: FFT magnitude array (linear scale)
        peak_bin: Index of peak bin

    Returns:
        Fractional bin offset from peak_bin
    """
    if peak_bin <= 0 or peak_bin >= len(fft_mag) - 1:
        return 0.0

    # Convert to log scale (dB)
    alpha = np.log(fft_mag[peak_bin - 1] + 1e-10)
    beta = np.log(fft_mag[peak_bin] + 1e-10)
    gamma = np.log(fft_mag[peak_bin + 1] + 1e-10)

    # Gaussian interpolation formula (same as parabolic in log domain)
    denom = alpha - 2*beta + gamma
    if abs(denom) < 1e-10:
        return 0.0

    delta = 0.5 * (alpha - gamma) / denom

    # Clamp to valid range
    delta = max(-0.5, min(0.5, delta))

    return delta


def multi_estimator_average(
    fft_bins: np.ndarray,
    fft_mag: np.ndarray,
    peak_bin: int,
    weights: dict = None
) -> float:
    """
    Combine multiple estimators with weighted averaging.

    This often provides better accuracy than any single method.

    Args:
        fft_bins: Complex FFT array
        fft_mag: Magnitude array (linear scale)
        peak_bin: Index of peak bin
        weights: Dictionary of weights for each estimator
                 Default: equal weights for all

    Returns:
        Fractional bin offset from peak_bin
    """
    if weights is None:
        weights = {
            'quinn': 3.0,      # Best overall, highest weight
            'jacobsen': 2.0,   # Nearly as good as Quinn
            'gaussian': 1.0,   # Good for windowed signals
            'parabolic': 0.5,  # Baseline, lower weight
        }

    estimates = []
    est_weights = []

    # Quinn's estimator
    if 'quinn' in weights and weights['quinn'] > 0:
        try:
            delta = quinn_estimator(fft_bins, peak_bin)
            estimates.append(delta)
            est_weights.append(weights['quinn'])
        except:
            pass

    # Jacobsen's estimator
    if 'jacobsen' in weights and weights['jacobsen'] > 0:
        try:
            delta = jacobsen_estimator(fft_bins, peak_bin)
            estimates.append(delta)
            est_weights.append(weights['jacobsen'])
        except:
            pass

    # Gaussian interpolation
    if 'gaussian' in weights and weights['gaussian'] > 0:
        try:
            delta = gaussian_interpolation(fft_mag, peak_bin)
            estimates.append(delta)
            est_weights.append(weights['gaussian'])
        except:
            pass

    # Parabolic interpolation
    if 'parabolic' in weights and weights['parabolic'] > 0:
        try:
            delta, _ = parabolic_interpolation(fft_mag, peak_bin)
            estimates.append(delta)
            est_weights.append(weights['parabolic'])
        except:
            pass

    if not estimates:
        return 0.0

    # Weighted average
    estimates = np.array(estimates)
    est_weights = np.array(est_weights)

    # Remove outliers (more than 0.1 bins from median)
    median = np.median(estimates)
    valid = np.abs(estimates - median) < 0.1

    if not np.any(valid):
        valid = np.ones_like(estimates, dtype=bool)

    weighted_avg = np.average(estimates[valid], weights=est_weights[valid])

    return weighted_avg


def zero_padded_fft_estimate(
    signal: np.ndarray,
    approx_bin: int,
    fft_size: int,
    zoom_factor: int = 4,
    sample_rate: float = 8000.0
) -> float:
    """
    Use zero-padding to increase FFT resolution around peak.

    This is a "zoom FFT" approach - we know the approximate location,
    so we can zero-pad heavily to get very fine resolution.

    Args:
        signal: Time-domain signal
        approx_bin: Approximate bin location
        fft_size: Original FFT size
        zoom_factor: How much to increase resolution (2, 4, 8, etc.)
        sample_rate: Sample rate in Hz

    Returns:
        Refined frequency estimate in Hz
    """
    # Zero-pad the signal
    padded_size = fft_size * zoom_factor
    padded_signal = np.zeros(padded_size)
    padded_signal[:len(signal)] = signal[:fft_size]

    # Apply window
    window = np.hanning(fft_size)
    padded_window = np.zeros(padded_size)
    padded_window[:fft_size] = window

    # Compute zero-padded FFT
    fft = np.fft.rfft(padded_signal * padded_window)
    mag = np.abs(fft)

    # Find peak in zoomed region
    # The original bin k maps to bin k*zoom_factor in padded FFT
    search_center = approx_bin * zoom_factor
    search_range = zoom_factor * 2  # Search ±2 original bins

    start = max(0, search_center - search_range)
    end = min(len(mag), search_center + search_range)

    search_region = mag[start:end]
    local_peak = np.argmax(search_region)
    peak_bin = start + local_peak

    # Convert bin to frequency
    freq = peak_bin * sample_rate / padded_size

    return freq


def czt_zoom(
    signal: np.ndarray,
    center_freq: float,
    bandwidth: float,
    num_points: int = 256,
    sample_rate: float = 8000.0
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Chirp Z-Transform for zooming into a specific frequency range.

    This is the ultimate "zoom FFT" - arbitrary frequency resolution
    in any frequency range. More computationally expensive than FFT.

    Args:
        signal: Time-domain signal
        center_freq: Center frequency of zoom region (Hz)
        bandwidth: Bandwidth of zoom region (Hz)
        num_points: Number of points in output spectrum
        sample_rate: Sample rate in Hz

    Returns:
        Tuple of (frequencies, magnitudes)
    """
    N = len(signal)

    # CZT parameters
    f_start = center_freq - bandwidth / 2
    f_end = center_freq + bandwidth / 2

    # Convert to normalized frequencies
    w_start = 2 * np.pi * f_start / sample_rate
    w_end = 2 * np.pi * f_end / sample_rate

    # CZT spiral parameters
    A = np.exp(1j * w_start)  # Starting point
    W = np.exp(-1j * (w_end - w_start) / (num_points - 1))  # Step

    # Compute CZT using FFT-based algorithm
    n = np.arange(N)
    k = np.arange(num_points)

    # Chirp signal
    chirp_n = W ** (-(n**2) / 2)
    chirp_k = W ** (-(k**2) / 2)

    # Convolution via FFT
    fft_size = 2 ** int(np.ceil(np.log2(N + num_points - 1)))

    y = signal * (A ** -n) * chirp_n
    Y = np.fft.fft(y, fft_size)

    chirp_padded = np.zeros(fft_size, dtype=complex)
    chirp_padded[:N] = chirp_n
    chirp_padded[-(num_points-1):] = np.conj(W ** (-((np.arange(1, num_points))**2) / 2))
    H = np.fft.fft(chirp_padded)

    Z = np.fft.ifft(Y * H)[:num_points]
    Z = Z * chirp_k

    # Generate frequency axis
    freqs = np.linspace(f_start, f_end, num_points)

    return freqs, np.abs(Z)
