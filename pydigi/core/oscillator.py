"""
Numerically Controlled Oscillator (NCO) implementation.

The NCO is a fundamental building block for digital modems, generating
complex exponentials at a specified frequency.
"""

import numpy as np
from typing import Union


class NCO:
    """
    Numerically Controlled Oscillator for generating complex exponentials.

    This class implements a phase accumulator that generates complex
    exponential signals (cos + j*sin) at a specified frequency.

    The NCO maintains phase continuity across calls, making it suitable
    for continuous signal generation.

    Attributes:
        sample_rate: Sample rate in Hz
        frequency: Current oscillator frequency in Hz
        phase: Current phase in radians (0 to 2π)

    Example:
        >>> nco = NCO(sample_rate=8000, frequency=1000)
        >>> samples = nco.step(100)  # Generate 100 samples
        >>> # samples is complex array with 1000 Hz tone
    """

    def __init__(self, sample_rate: float = 8000.0, frequency: float = 0.0, phase: float = 0.0):
        """
        Initialize the NCO.

        Args:
            sample_rate: Sample rate in Hz (default: 8000)
            frequency: Initial frequency in Hz (default: 0)
            phase: Initial phase in radians (default: 0)
        """
        self.sample_rate = sample_rate
        self._frequency = frequency
        self._phase = phase % (2.0 * np.pi)  # Keep phase in [0, 2π)
        self._phase_increment = 2.0 * np.pi * frequency / sample_rate

    @property
    def frequency(self) -> float:
        """Get the current frequency in Hz."""
        return self._frequency

    @frequency.setter
    def frequency(self, freq: float) -> None:
        """
        Set the oscillator frequency.

        Args:
            freq: Frequency in Hz
        """
        self._frequency = freq
        self._phase_increment = 2.0 * np.pi * freq / self.sample_rate

    @property
    def phase(self) -> float:
        """Get the current phase in radians."""
        return self._phase

    @phase.setter
    def phase(self, ph: float) -> None:
        """
        Set the oscillator phase.

        Args:
            ph: Phase in radians
        """
        self._phase = ph % (2.0 * np.pi)

    def step(self, n_samples: int) -> np.ndarray:
        """
        Generate n_samples of the complex exponential.

        Generates exp(j*2*pi*f*t) where f is the frequency and t is time.
        Phase is maintained between calls for continuous generation.

        Args:
            n_samples: Number of samples to generate

        Returns:
            Complex numpy array of shape (n_samples,) containing the
            generated complex exponential
        """
        # Generate phase values for each sample
        phases = self._phase + np.arange(n_samples) * self._phase_increment

        # Generate complex exponential: exp(j*phase) = cos(phase) + j*sin(phase)
        samples = np.exp(1j * phases)

        # Update phase for next call, keeping it in [0, 2π)
        self._phase = (self._phase + n_samples * self._phase_increment) % (2.0 * np.pi)

        return samples

    def step_real(self, n_samples: int) -> np.ndarray:
        """
        Generate n_samples of the real part (cosine) only.

        This is useful when only a real-valued sinusoid is needed.

        Args:
            n_samples: Number of samples to generate

        Returns:
            Real numpy array of shape (n_samples,) containing cos(2*pi*f*t)
        """
        return np.real(self.step(n_samples))

    def reset(self, phase: float = 0.0) -> None:
        """
        Reset the oscillator phase.

        Args:
            phase: Phase to reset to in radians (default: 0)
        """
        self._phase = phase % (2.0 * np.pi)


def generate_tone(
    frequency: float,
    duration: float,
    sample_rate: float = 8000.0,
    amplitude: float = 1.0,
    phase: float = 0.0,
) -> np.ndarray:
    """
    Generate a real sinusoidal tone.

    Convenience function for generating a simple tone without managing an NCO instance.

    Args:
        frequency: Frequency in Hz
        duration: Duration in seconds
        sample_rate: Sample rate in Hz (default: 8000)
        amplitude: Amplitude (default: 1.0)
        phase: Initial phase in radians (default: 0)

    Returns:
        Real numpy array containing the generated tone

    Example:
        >>> tone = generate_tone(1000, 0.1, 8000)  # 100ms of 1000 Hz
        >>> len(tone)
        800
    """
    n_samples = int(duration * sample_rate)
    nco = NCO(sample_rate=sample_rate, frequency=frequency, phase=phase)
    return amplitude * nco.step_real(n_samples)


def generate_complex_tone(
    frequency: float,
    duration: float,
    sample_rate: float = 8000.0,
    amplitude: float = 1.0,
    phase: float = 0.0,
) -> np.ndarray:
    """
    Generate a complex exponential tone.

    Convenience function for generating a complex tone without managing an NCO instance.

    Args:
        frequency: Frequency in Hz
        duration: Duration in seconds
        sample_rate: Sample rate in Hz (default: 8000)
        amplitude: Amplitude (default: 1.0)
        phase: Initial phase in radians (default: 0)

    Returns:
        Complex numpy array containing the generated tone

    Example:
        >>> tone = generate_complex_tone(1000, 0.1, 8000)  # 100ms of 1000 Hz
        >>> len(tone)
        800
    """
    n_samples = int(duration * sample_rate)
    nco = NCO(sample_rate=sample_rate, frequency=frequency, phase=phase)
    return amplitude * nco.step(n_samples)
