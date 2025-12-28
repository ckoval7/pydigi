"""
Digital Signal Processing Utilities for PyDigi.

This module provides common DSP functions used across multiple modem implementations,
reducing code duplication and ensuring consistent signal processing.
"""

import numpy as np
from scipy import signal
from typing import Tuple


def generate_raised_cosine_shape(length: int) -> np.ndarray:
    """
    Generate raised cosine pulse shape for symbol transitions.

    This implements the same shape as fldigi's tx_shape,
    which creates smooth transitions between symbols to prevent spectral splatter.

    Args:
        length: Number of samples in the shape (symbol length)

    Returns:
        Array of shape coefficients (1.0 to 0.0)

    Reference:
        fldigi/psk/psk.cxx:1052
        Formula: 0.5 * cos(i * PI / symbollen) + 0.5
    """
    n = np.arange(length)
    shape = 0.5 * np.cos(n * np.pi / length) + 0.5
    return shape


def apply_baseband_filter(
    i_samples: np.ndarray, q_samples: np.ndarray, baud: float, sample_rate: float
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Apply lowpass filter to baseband I/Q signals.

    This is the proper way to filter - apply lowpass to the baseband
    before mixing to carrier frequency.

    Args:
        i_samples: I (in-phase) baseband samples
        q_samples: Q (quadrature) baseband samples
        baud: Symbol rate in baud
        sample_rate: Audio sample rate in Hz

    Returns:
        Tuple of (filtered I, filtered Q)

    Reference:
        Common implementation across PSK, QPSK, PSK8 modems
    """
    # Lowpass filter cutoff: 2-3x the baud rate gives good spectral containment
    # while preserving the signal
    cutoff_hz = baud * 2.5
    nyquist = sample_rate / 2.0
    cutoff_normalized = cutoff_hz / nyquist

    # Ensure cutoff is valid
    cutoff_normalized = min(cutoff_normalized, 0.95)

    # 5th order Butterworth lowpass filter
    b, a = signal.butter(5, cutoff_normalized, btype="low")

    # Apply zero-phase filtering to both I and Q
    i_filtered = signal.filtfilt(b, a, i_samples)
    q_filtered = signal.filtfilt(b, a, q_samples)

    return i_filtered.astype(np.float32), q_filtered.astype(np.float32)


def modulate_to_carrier(
    i_samples: np.ndarray, q_samples: np.ndarray, frequency: float, sample_rate: float
) -> np.ndarray:
    """
    Mix baseband I/Q signal to carrier frequency.

    Uses quadrature modulation: output = I*cos(wt) + Q*sin(wt)

    Args:
        i_samples: I (in-phase) baseband samples
        q_samples: Q (quadrature) baseband samples
        frequency: Carrier frequency in Hz
        sample_rate: Audio sample rate in Hz

    Returns:
        Modulated signal at carrier frequency

    Reference:
        Common implementation across PSK, QPSK, PSK8 modems
    """
    # Generate carrier
    n_samples = len(i_samples)
    t = np.arange(n_samples) / sample_rate
    carrier_i = np.cos(2.0 * np.pi * frequency * t)
    carrier_q = np.sin(2.0 * np.pi * frequency * t)

    # Quadrature modulation
    output = i_samples * carrier_i + q_samples * carrier_q

    return output.astype(np.float32)


def normalize_audio(audio: np.ndarray, target_amplitude: float = 0.8) -> np.ndarray:
    """
    Normalize audio to target amplitude.

    Args:
        audio: Audio samples
        target_amplitude: Target peak amplitude (0.0 to 1.0)

    Returns:
        Normalized audio samples
    """
    max_amp = np.max(np.abs(audio))
    if max_amp > 0:
        audio = audio / max_amp * target_amplitude
    return audio.astype(np.float32)
