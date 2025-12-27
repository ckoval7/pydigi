"""
Digital filter implementations for pydigi.

Includes FIR, IIR, and specialized filters used in digital modems.
Based on fldigi's filter implementations.

References:
    - fldigi/src/filters/filters.cxx
    - fldigi/src/filters/fftfilt.cxx
    - "Digital Signal Processing: A Practical Guide for Engineers and Scientists"
      by Steven W. Smith
"""

import numpy as np
from typing import Optional, Union


def sinc(x: Union[float, np.ndarray]) -> Union[float, np.ndarray]:
    """
    Compute the sinc function: sin(pi*x) / (pi*x).

    Args:
        x: Input value or array

    Returns:
        sinc(x)
    """
    # Handle x=0 case to avoid division by zero
    x = np.asarray(x)
    result = np.ones_like(x, dtype=float)
    mask = x != 0
    result[mask] = np.sin(np.pi * x[mask]) / (np.pi * x[mask])
    return result if result.shape else float(result)


def cosc(x: Union[float, np.ndarray]) -> Union[float, np.ndarray]:
    """
    Compute the cosc function: cos(pi*x) / (pi*x).

    Used in Hilbert transform filters.

    Args:
        x: Input value or array

    Returns:
        cosc(x)
    """
    x = np.asarray(x)
    result = np.ones_like(x, dtype=float)
    mask = x != 0
    result[mask] = np.cos(np.pi * x[mask]) / (np.pi * x[mask])
    return result if result.shape else float(result)


def hamming(x: Union[float, np.ndarray]) -> Union[float, np.ndarray]:
    """
    Hamming window function.

    Args:
        x: Input value or array, range [0, 1]

    Returns:
        Hamming window value
    """
    return 0.54 - 0.46 * np.cos(2.0 * np.pi * x)


def blackman(x: Union[float, np.ndarray]) -> Union[float, np.ndarray]:
    """
    Blackman window function.

    Args:
        x: Input value or array, range [0, 1]

    Returns:
        Blackman window value
    """
    return 0.42 - 0.5 * np.cos(2.0 * np.pi * x) + 0.08 * np.cos(4.0 * np.pi * x)


def raised_cosine(t: np.ndarray, symbol_rate: float, alpha: float = 0.5) -> np.ndarray:
    """
    Raised cosine filter impulse response.

    Used for pulse shaping in PSK and other modems.

    Args:
        t: Time array
        symbol_rate: Symbol rate in symbols/second
        alpha: Roll-off factor (0 to 1, typically 0.5)

    Returns:
        Filter impulse response
    """
    T = 1.0 / symbol_rate  # Symbol period

    # Avoid division by zero at specific points
    eps = 1e-10
    t_norm = t / T + eps

    # Raised cosine formula
    numerator = np.sin(np.pi * t_norm) * np.cos(np.pi * alpha * t_norm)
    denominator = np.pi * t_norm * (1.0 - (2.0 * alpha * t_norm) ** 2)

    # Handle singularities
    result = numerator / (denominator + eps)

    return result


class FIRFilter:
    """
    Finite Impulse Response (FIR) filter with decimation support.

    Based on fldigi's C_FIR_filter class.

    The filter operates on complex samples by maintaining separate
    I and Q buffers and filter taps.

    Attributes:
        length: Filter length (number of taps)
        decimation: Decimation ratio (output every Nth sample)
        taps: Filter coefficients
    """

    def __init__(
        self,
        taps: np.ndarray,
        decimation: int = 1
    ):
        """
        Initialize the FIR filter.

        Args:
            taps: Filter coefficients (impulse response)
            decimation: Decimation ratio (default: 1, no decimation)
        """
        self.length = len(taps)
        self.decimation = decimation
        self.taps = np.asarray(taps, dtype=np.float64)

        # Circular buffers for I and Q
        self.buffer_i = np.zeros(self.length, dtype=np.float64)
        self.buffer_q = np.zeros(self.length, dtype=np.float64)

        # Buffer pointer and decimation counter
        self.pointer = 0
        self.counter = 0

    def reset(self) -> None:
        """Reset the filter state."""
        self.buffer_i.fill(0.0)
        self.buffer_q.fill(0.0)
        self.pointer = 0
        self.counter = 0

    def filter(self, sample: complex) -> Optional[complex]:
        """
        Process one sample through the filter.

        Args:
            sample: Complex input sample

        Returns:
            Filtered complex sample, or None if decimated
        """
        # Store sample in circular buffer
        self.buffer_i[self.pointer] = sample.real
        self.buffer_q[self.pointer] = sample.imag
        self.pointer = (self.pointer + 1) % self.length

        # Decimation counter
        self.counter += 1
        if self.counter < self.decimation:
            return None
        self.counter = 0

        # Convolve with filter taps
        out_i = 0.0
        out_q = 0.0
        idx = self.pointer
        for i in range(self.length):
            idx = (idx - 1) % self.length
            out_i += self.buffer_i[idx] * self.taps[i]
            out_q += self.buffer_q[idx] * self.taps[i]

        return complex(out_i, out_q)

    def filter_array(self, samples: np.ndarray) -> np.ndarray:
        """
        Process an array of samples.

        Args:
            samples: Array of complex samples

        Returns:
            Array of filtered samples (length may be reduced by decimation)
        """
        output = []
        for sample in samples:
            result = self.filter(sample)
            if result is not None:
                output.append(result)
        return np.array(output, dtype=np.complex128)

    @staticmethod
    def design_lowpass(
        length: int,
        cutoff: float,
        window: str = 'hamming'
    ) -> 'FIRFilter':
        """
        Design a lowpass FIR filter.

        Args:
            length: Filter length (number of taps)
            cutoff: Cutoff frequency (normalized, 0 to 0.5)
            window: Window function ('hamming' or 'blackman')

        Returns:
            FIRFilter instance
        """
        taps = np.zeros(length)

        for i in range(length):
            t = i - (length - 1.0) / 2.0
            h = i / (length - 1.0)

            # Windowed sinc lowpass
            x = 2.0 * cutoff * sinc(2.0 * cutoff * t)

            if window == 'hamming':
                x *= hamming(h)
            elif window == 'blackman':
                x *= blackman(h)

            taps[i] = x

        return FIRFilter(taps)

    @staticmethod
    def design_bandpass(
        length: int,
        f_low: float,
        f_high: float,
        window: str = 'hamming'
    ) -> 'FIRFilter':
        """
        Design a bandpass FIR filter.

        Args:
            length: Filter length (number of taps)
            f_low: Lower cutoff frequency (normalized, 0 to 0.5)
            f_high: Upper cutoff frequency (normalized, 0 to 0.5)
            window: Window function ('hamming' or 'blackman')

        Returns:
            FIRFilter instance
        """
        taps = np.zeros(length)

        for i in range(length):
            t = i - (length - 1.0) / 2.0
            h = i / (length - 1.0)

            # Windowed sinc bandpass (difference of two lowpass filters)
            x = (2.0 * f_high * sinc(2.0 * f_high * t) -
                 2.0 * f_low * sinc(2.0 * f_low * t))

            if window == 'hamming':
                x *= hamming(h)
            elif window == 'blackman':
                x *= blackman(h)

            taps[i] = x

        return FIRFilter(taps)

    @staticmethod
    def design_hilbert(
        length: int,
        f_low: float,
        f_high: float,
        window: str = 'hamming'
    ) -> 'FIRFilter':
        """
        Design a Hilbert transform filter.

        Used for creating analytic signals (complex from real).

        Args:
            length: Filter length (number of taps, should be odd)
            f_low: Lower cutoff frequency (normalized, 0 to 0.5)
            f_high: Upper cutoff frequency (normalized, 0 to 0.5)
            window: Window function ('hamming' or 'blackman')

        Returns:
            FIRFilter instance
        """
        taps = np.zeros(length)

        for i in range(length):
            t = i - (length - 1.0) / 2.0
            h = i / (length - 1.0)

            # Windowed cosc for Hilbert transform
            x = (2.0 * f_high * cosc(2.0 * f_high * t) -
                 2.0 * f_low * cosc(2.0 * f_low * t))

            # Time reversal for actual filter
            x = -x

            if window == 'hamming':
                x *= hamming(h)
            elif window == 'blackman':
                x *= blackman(h)

            taps[i] = x

        return FIRFilter(taps)


class MovingAverageFilter:
    """
    Moving average filter (boxcar filter).

    Simple and efficient filter for smoothing signals.
    """

    def __init__(self, length: int):
        """
        Initialize the moving average filter.

        Args:
            length: Number of samples to average
        """
        self.length = length
        self.buffer = np.zeros(length, dtype=np.complex128)
        self.pointer = 0
        self.sum = 0.0 + 0.0j

    def reset(self) -> None:
        """Reset the filter state."""
        self.buffer.fill(0.0)
        self.pointer = 0
        self.sum = 0.0 + 0.0j

    def filter(self, sample: complex) -> complex:
        """
        Process one sample.

        Args:
            sample: Complex input sample

        Returns:
            Filtered output (average of last N samples)
        """
        # Remove oldest sample from sum
        self.sum -= self.buffer[self.pointer]

        # Add new sample
        self.buffer[self.pointer] = sample
        self.sum += sample

        self.pointer = (self.pointer + 1) % self.length

        return self.sum / self.length

    def filter_array(self, samples: np.ndarray) -> np.ndarray:
        """
        Process an array of samples.

        Args:
            samples: Array of complex samples

        Returns:
            Array of filtered samples
        """
        output = np.zeros(len(samples), dtype=np.complex128)
        for i, sample in enumerate(samples):
            output[i] = self.filter(sample)
        return output


class GoertzelFilter:
    """
    Goertzel algorithm for tone detection.

    More efficient than FFT for detecting a single frequency.
    Used in RTTY and other FSK modes for tone detection.
    """

    def __init__(self, target_freq: float, sample_rate: float, n_samples: int):
        """
        Initialize the Goertzel filter.

        Args:
            target_freq: Frequency to detect (Hz)
            sample_rate: Sample rate (Hz)
            n_samples: Number of samples per DFT block
        """
        self.target_freq = target_freq
        self.sample_rate = sample_rate
        self.n_samples = n_samples

        # Precompute coefficient
        k = int(0.5 + n_samples * target_freq / sample_rate)
        w = 2.0 * np.pi * k / n_samples
        self.coeff = 2.0 * np.cos(w)
        self.w = w

        self.reset()

    def reset(self) -> None:
        """Reset the filter state."""
        self.s1 = 0.0
        self.s2 = 0.0
        self.count = 0

    def filter(self, sample: float) -> Optional[float]:
        """
        Process one sample.

        Args:
            sample: Real input sample

        Returns:
            Magnitude squared at target frequency after n_samples,
            or None if still collecting samples
        """
        # Goertzel recursion
        s0 = sample + self.coeff * self.s1 - self.s2
        self.s2 = self.s1
        self.s1 = s0

        self.count += 1

        if self.count >= self.n_samples:
            # Compute magnitude squared
            real = self.s1 - self.s2 * np.cos(self.w)
            imag = self.s2 * np.sin(self.w)
            magnitude_sq = real * real + imag * imag

            # Reset for next block
            self.reset()

            return magnitude_sq

        return None
