"""
Audio utilities for pydigi.

Functions for saving and loading audio files, and audio-related operations.
"""

import numpy as np
from typing import Optional
import wave
import struct


def save_wav(
    filename: str,
    audio: np.ndarray,
    sample_rate: int = 8000,
    bit_depth: int = 16
) -> None:
    """
    Save audio samples to a WAV file.

    Args:
        filename: Output filename (should end in .wav)
        audio: Audio samples (float array in range [-1.0, 1.0])
        sample_rate: Sample rate in Hz (default: 8000)
        bit_depth: Bit depth (8 or 16, default: 16)

    Raises:
        ValueError: If bit_depth is not 8 or 16

    Example:
        >>> audio = np.sin(2 * np.pi * 440 * np.arange(8000) / 8000)
        >>> save_wav("tone.wav", audio, sample_rate=8000)
    """
    if bit_depth not in [8, 16]:
        raise ValueError("bit_depth must be 8 or 16")

    # Ensure audio is in [-1.0, 1.0] range
    audio = np.clip(audio, -1.0, 1.0)

    # Convert to integer samples
    if bit_depth == 16:
        # 16-bit signed
        max_val = 32767
        audio_int = (audio * max_val).astype(np.int16)
        sample_width = 2
    else:
        # 8-bit unsigned
        max_val = 127
        audio_int = ((audio + 1.0) * max_val).astype(np.uint8)
        sample_width = 1

    # Write WAV file
    with wave.open(filename, 'wb') as wav_file:
        wav_file.setnchannels(1)  # Mono
        wav_file.setsampwidth(sample_width)
        wav_file.setframerate(sample_rate)

        # Convert to bytes and write
        if bit_depth == 16:
            wav_data = audio_int.tobytes()
        else:
            wav_data = audio_int.tobytes()

        wav_file.writeframes(wav_data)


def load_wav(filename: str) -> tuple:
    """
    Load audio samples from a WAV file.

    Args:
        filename: Input WAV filename

    Returns:
        Tuple of (audio_samples, sample_rate) where audio_samples
        is a float numpy array in range [-1.0, 1.0]

    Example:
        >>> audio, sr = load_wav("input.wav")
        >>> print(f"Loaded {len(audio)} samples at {sr} Hz")
    """
    with wave.open(filename, 'rb') as wav_file:
        # Get WAV parameters
        n_channels = wav_file.getnchannels()
        sample_width = wav_file.getsampwidth()
        sample_rate = wav_file.getframerate()
        n_frames = wav_file.getnframes()

        # Read all frames
        frames = wav_file.readframes(n_frames)

    # Convert bytes to numpy array
    if sample_width == 1:
        # 8-bit unsigned
        audio_int = np.frombuffer(frames, dtype=np.uint8)
        audio = (audio_int.astype(np.float32) / 127.0) - 1.0
    elif sample_width == 2:
        # 16-bit signed
        audio_int = np.frombuffer(frames, dtype=np.int16)
        audio = audio_int.astype(np.float32) / 32767.0
    else:
        raise ValueError(f"Unsupported sample width: {sample_width}")

    # Handle stereo by taking first channel
    if n_channels == 2:
        audio = audio[::2]

    return audio, sample_rate


def save_wav_soundfile(
    filename: str,
    audio: np.ndarray,
    sample_rate: int = 8000
) -> None:
    """
    Save audio using soundfile library (if available).

    This provides better quality and more format options than the
    built-in wave module.

    Args:
        filename: Output filename
        audio: Audio samples (float array in range [-1.0, 1.0])
        sample_rate: Sample rate in Hz (default: 8000)

    Raises:
        ImportError: If soundfile is not installed

    Example:
        >>> audio = np.sin(2 * np.pi * 440 * np.arange(8000) / 8000)
        >>> save_wav_soundfile("tone.wav", audio, sample_rate=8000)
    """
    try:
        import soundfile as sf
        sf.write(filename, audio, sample_rate)
    except ImportError:
        raise ImportError(
            "soundfile library not installed. "
            "Install with: pip install soundfile"
        )


def load_wav_soundfile(filename: str) -> tuple:
    """
    Load audio using soundfile library (if available).

    Args:
        filename: Input filename

    Returns:
        Tuple of (audio_samples, sample_rate)

    Raises:
        ImportError: If soundfile is not installed

    Example:
        >>> audio, sr = load_wav_soundfile("input.wav")
    """
    try:
        import soundfile as sf
        audio, sample_rate = sf.read(filename)
        return audio, sample_rate
    except ImportError:
        raise ImportError(
            "soundfile library not installed. "
            "Install with: pip install soundfile"
        )


def db_to_linear(db: float) -> float:
    """
    Convert decibels to linear amplitude.

    Args:
        db: Level in decibels

    Returns:
        Linear amplitude
    """
    return 10.0 ** (db / 20.0)


def linear_to_db(amplitude: float) -> float:
    """
    Convert linear amplitude to decibels.

    Args:
        amplitude: Linear amplitude

    Returns:
        Level in decibels
    """
    return 20.0 * np.log10(np.abs(amplitude) + 1e-20)


def rms(audio: np.ndarray) -> float:
    """
    Calculate RMS (root mean square) of audio signal.

    Args:
        audio: Audio samples

    Returns:
        RMS value
    """
    return np.sqrt(np.mean(audio ** 2))


def peak(audio: np.ndarray) -> float:
    """
    Calculate peak amplitude of audio signal.

    Args:
        audio: Audio samples

    Returns:
        Peak amplitude (absolute value)
    """
    return np.max(np.abs(audio))


def normalize(audio: np.ndarray, target_peak: float = 1.0) -> np.ndarray:
    """
    Normalize audio to target peak level.

    Args:
        audio: Audio samples
        target_peak: Target peak level (default: 1.0)

    Returns:
        Normalized audio samples
    """
    current_peak = peak(audio)
    if current_peak > 0:
        return audio * (target_peak / current_peak)
    return audio
