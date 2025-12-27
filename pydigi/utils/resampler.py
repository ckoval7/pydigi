"""
Audio resampling utilities for pydigi.

Provides high-quality resampling for converting modem output between different sample rates.
Particularly useful for MT63 and SCAMP which require 8000 Hz but may need output at 48000 Hz
for use with SDR hardware or modern audio interfaces.
"""

import numpy as np
from scipy import signal
from typing import Union, Tuple, Optional, Any


def resample(
    audio: np.ndarray,
    original_rate: float,
    target_rate: float,
    method: str = 'polyphase'
) -> np.ndarray:
    """
    Resample audio from one sample rate to another.

    This function uses high-quality resampling algorithms to convert audio between
    different sample rates while minimizing artifacts and maintaining signal quality.

    Args:
        audio: Input audio samples (1D numpy array)
        original_rate: Original sample rate in Hz
        target_rate: Target sample rate in Hz
        method: Resampling method:
                - 'polyphase': Fast polyphase filtering (best for integer ratios)
                - 'fft': FFT-based resampling (best for arbitrary ratios)
                Default: 'polyphase'

    Returns:
        Resampled audio at target_rate

    Example:
        >>> # Resample MT63 output from 8000 Hz to 48000 Hz
        >>> mt63 = MT63(mode='MT63-2000L')
        >>> audio_8k = mt63.modulate("HELLO WORLD")
        >>> audio_48k = resample(audio_8k, 8000, 48000)
        >>>
        >>> # Resample arbitrary rate
        >>> audio_11k = resample(audio_8k, 8000, 11025, method='fft')
    """
    if original_rate == target_rate:
        return audio

    if method == 'polyphase':
        # Check if we have an integer ratio
        up, down = _compute_rational_ratio(original_rate, target_rate)

        # Use polyphase resampling for efficiency
        # scipy.signal.resample_poly is very fast for integer ratios
        return signal.resample_poly(audio, up, down)

    elif method == 'fft':
        # FFT-based resampling for arbitrary ratios
        num_samples = int(len(audio) * target_rate / original_rate)
        return signal.resample(audio, num_samples)

    else:
        raise ValueError(f"Unknown resampling method: {method}. Use 'polyphase' or 'fft'")


def resample_to_48k(audio: np.ndarray, original_rate: float = 8000) -> np.ndarray:
    """
    Convenience function to resample audio to 48000 Hz.

    This is a common operation for MT63 and SCAMP output which are fixed at 8000 Hz
    but need to be output to modern audio interfaces operating at 48000 Hz.

    Args:
        audio: Input audio samples
        original_rate: Original sample rate in Hz (default: 8000)

    Returns:
        Audio resampled to 48000 Hz

    Example:
        >>> mt63 = MT63(mode='MT63-2000L')
        >>> audio = mt63.modulate("CQ CQ DE W1ABC")
        >>> audio_48k = resample_to_48k(audio)  # 8000 -> 48000 Hz
    """
    return resample(audio, original_rate, 48000, method='polyphase')


def resample_from_modem(
    audio: np.ndarray,
    modem: Any,
    target_rate: float
) -> np.ndarray:
    """
    Resample audio from a modem's native sample rate to a target rate.

    Automatically detects the modem's sample rate and resamples accordingly.

    Args:
        audio: Audio output from modem.modulate()
        modem: Modem instance (must have .sample_rate attribute)
        target_rate: Target sample rate in Hz

    Returns:
        Resampled audio

    Example:
        >>> mt63 = MT63(mode='MT63-2000L')
        >>> audio = mt63.modulate("HELLO")
        >>> audio_48k = resample_from_modem(audio, mt63, 48000)
        >>>
        >>> psk31 = PSK(baud=31.25, sample_rate=8000)
        >>> audio = psk31.modulate("TEST")
        >>> audio_44k = resample_from_modem(audio, psk31, 44100)
    """
    if not hasattr(modem, 'sample_rate'):
        raise ValueError("Modem must have a 'sample_rate' attribute")

    return resample(audio, modem.sample_rate, target_rate)


def compute_resampled_length(
    original_length: int,
    original_rate: float,
    target_rate: float
) -> int:
    """
    Calculate the length of resampled audio without actually resampling.

    Useful for pre-allocating buffers or calculating timing.

    Args:
        original_length: Number of samples in original audio
        original_rate: Original sample rate in Hz
        target_rate: Target sample rate in Hz

    Returns:
        Number of samples after resampling

    Example:
        >>> # How many samples will we have after resampling?
        >>> new_len = compute_resampled_length(8000, 8000, 48000)
        >>> print(new_len)  # 48000
    """
    return int(original_length * target_rate / original_rate)


def _compute_rational_ratio(
    original_rate: float,
    target_rate: float,
    max_denominator: int = 1000
) -> Tuple[int, int]:
    """
    Compute rational approximation of sample rate ratio.

    Finds integers (up, down) such that target_rate/original_rate ≈ up/down.
    This is used for efficient polyphase resampling.

    Args:
        original_rate: Original sample rate
        target_rate: Target sample rate
        max_denominator: Maximum denominator to search (default: 1000)

    Returns:
        Tuple of (up, down) integers representing the ratio

    Example:
        >>> up, down = _compute_rational_ratio(8000, 48000)
        >>> print(up, down)  # 6, 1 (48000/8000 = 6/1)
        >>>
        >>> up, down = _compute_rational_ratio(8000, 44100)
        >>> print(up, down)  # 441, 80 (44100/8000 = 441/80)
    """
    from fractions import Fraction

    # Compute the ratio as a fraction
    ratio = Fraction(int(target_rate), int(original_rate)).limit_denominator(max_denominator)

    return ratio.numerator, ratio.denominator


def get_resampling_info(original_rate: float, target_rate: float) -> dict:
    """
    Get detailed information about a resampling operation.

    Returns ratio, method recommendation, and estimated quality.

    Args:
        original_rate: Original sample rate in Hz
        target_rate: Target sample rate in Hz

    Returns:
        Dictionary containing:
            - 'ratio': Exact ratio (float)
            - 'up': Upsampling factor (int)
            - 'down': Downsampling factor (int)
            - 'is_integer_ratio': Whether ratio is exactly an integer
            - 'recommended_method': 'polyphase' or 'fft'
            - 'quality': 'perfect', 'excellent', 'good', or 'approximate'

    Example:
        >>> info = get_resampling_info(8000, 48000)
        >>> print(info['ratio'])  # 6.0
        >>> print(info['recommended_method'])  # 'polyphase'
    """
    ratio = target_rate / original_rate
    up, down = _compute_rational_ratio(original_rate, target_rate)

    # Check if it's an exact integer ratio
    is_integer = (target_rate % original_rate == 0) or (original_rate % target_rate == 0)

    # Determine quality
    exact_ratio = up / down
    error = abs(exact_ratio - ratio) / ratio

    if error < 1e-10:
        quality = 'perfect'
    elif error < 1e-6:
        quality = 'excellent'
    elif error < 1e-3:
        quality = 'good'
    else:
        quality = 'approximate'

    # Recommend method
    if is_integer or (up * down < 1000):
        recommended_method = 'polyphase'
    else:
        recommended_method = 'fft'

    return {
        'ratio': ratio,
        'up': up,
        'down': down,
        'is_integer_ratio': is_integer,
        'recommended_method': recommended_method,
        'quality': quality,
        'original_rate': original_rate,
        'target_rate': target_rate
    }


# Common resampling presets
COMMON_CONVERSIONS = {
    '8k_to_48k': (8000, 48000),    # MT63/SCAMP to high-quality audio
    '8k_to_44k': (8000, 44100),    # MT63/SCAMP to CD quality
    '8k_to_16k': (8000, 16000),    # MT63/SCAMP to wideband
    '11k_to_48k': (11025, 48000),  # Common upsampling
    '44k_to_48k': (44100, 48000),  # CD to professional
    '48k_to_8k': (48000, 8000),    # High-quality to MT63/SCAMP
}


def resample_preset(audio: np.ndarray, preset: str) -> np.ndarray:
    """
    Resample using a common preset conversion.

    Args:
        audio: Input audio samples
        preset: Preset name (see COMMON_CONVERSIONS)

    Returns:
        Resampled audio

    Available presets:
        - '8k_to_48k': 8000 Hz → 48000 Hz (MT63/SCAMP to high-quality)
        - '8k_to_44k': 8000 Hz → 44100 Hz (MT63/SCAMP to CD quality)
        - '8k_to_16k': 8000 Hz → 16000 Hz (MT63/SCAMP to wideband)
        - '11k_to_48k': 11025 Hz → 48000 Hz
        - '44k_to_48k': 44100 Hz → 48000 Hz (CD to professional)
        - '48k_to_8k': 48000 Hz → 8000 Hz (high-quality to MT63/SCAMP)

    Example:
        >>> mt63 = MT63(mode='MT63-2000L')
        >>> audio = mt63.modulate("HELLO")
        >>> audio_48k = resample_preset(audio, '8k_to_48k')
    """
    if preset not in COMMON_CONVERSIONS:
        available = ', '.join(COMMON_CONVERSIONS.keys())
        raise ValueError(f"Unknown preset '{preset}'. Available: {available}")

    original_rate, target_rate = COMMON_CONVERSIONS[preset]
    return resample(audio, original_rate, target_rate)
