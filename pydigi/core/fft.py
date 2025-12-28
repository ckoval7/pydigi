"""
FFT utilities for pydigi.

Wrapper functions and classes for FFT operations.
Uses numpy.fft as the underlying FFT implementation.
"""

import numpy as np
from typing import Optional


def fft(x: np.ndarray) -> np.ndarray:
    """
    Compute the FFT of a complex signal.

    Args:
        x: Complex input array

    Returns:
        Complex FFT output
    """
    return np.fft.fft(x)


def ifft(x: np.ndarray) -> np.ndarray:
    """
    Compute the inverse FFT of a complex signal.

    Args:
        x: Complex input array

    Returns:
        Complex IFFT output
    """
    return np.fft.ifft(x)


def rfft(x: np.ndarray) -> np.ndarray:
    """
    Compute the FFT of a real signal.

    More efficient than regular FFT for real-valued inputs.

    Args:
        x: Real input array

    Returns:
        Complex FFT output (length n//2 + 1)
    """
    return np.fft.rfft(x)


def irfft(x: np.ndarray, n: Optional[int] = None) -> np.ndarray:
    """
    Compute the inverse FFT of a real signal's FFT.

    Args:
        x: Complex input array (from rfft)
        n: Output length (optional)

    Returns:
        Real IFFT output
    """
    return np.fft.irfft(x, n=n)


def fftshift(x: np.ndarray) -> np.ndarray:
    """
    Shift zero-frequency component to center of spectrum.

    Args:
        x: FFT output

    Returns:
        Shifted FFT
    """
    return np.fft.fftshift(x)


def ifftshift(x: np.ndarray) -> np.ndarray:
    """
    Inverse of fftshift.

    Args:
        x: Shifted FFT

    Returns:
        Unshifted FFT
    """
    return np.fft.ifftshift(x)


def magnitude_spectrum(x: np.ndarray) -> np.ndarray:
    """
    Compute the magnitude spectrum of a signal.

    Args:
        x: Time-domain signal (real or complex)

    Returns:
        Magnitude spectrum
    """
    return np.abs(fft(x))


def power_spectrum(x: np.ndarray) -> np.ndarray:
    """
    Compute the power spectrum of a signal.

    Args:
        x: Time-domain signal (real or complex)

    Returns:
        Power spectrum (magnitude squared)
    """
    spectrum = fft(x)
    return np.abs(spectrum) ** 2


def power_spectrum_db(x: np.ndarray, ref: float = 1.0) -> np.ndarray:
    """
    Compute the power spectrum in dB.

    Args:
        x: Time-domain signal (real or complex)
        ref: Reference value for dB calculation (default: 1.0)

    Returns:
        Power spectrum in dB
    """
    power = power_spectrum(x)
    return 10.0 * np.log10(power / ref + 1e-20)  # Add epsilon to avoid log(0)


class SlidingFFT:
    """
    Sliding FFT for real-time spectral analysis.

    Maintains a circular buffer and computes FFT on overlapping windows.
    Useful for waterfall displays and frequency tracking.
    """

    def __init__(self, fft_size: int, hop_size: Optional[int] = None):
        """
        Initialize the sliding FFT.

        Args:
            fft_size: FFT size (number of samples)
            hop_size: Hop size between FFTs (default: fft_size // 2)
        """
        self.fft_size = fft_size
        self.hop_size = hop_size if hop_size is not None else fft_size // 2

        # Circular buffer for samples
        self.buffer = np.zeros(fft_size, dtype=np.complex128)
        self.pointer = 0
        self.count = 0

        # Window function (Hann window)
        self.window = np.hanning(fft_size)

    def reset(self) -> None:
        """Reset the buffer."""
        self.buffer.fill(0.0)
        self.pointer = 0
        self.count = 0

    def process(self, sample: complex) -> Optional[np.ndarray]:
        """
        Process one sample.

        Args:
            sample: Complex input sample

        Returns:
            FFT output when hop_size samples have been collected,
            None otherwise
        """
        # Add sample to buffer
        self.buffer[self.pointer] = sample
        self.pointer = (self.pointer + 1) % self.fft_size
        self.count += 1

        # Compute FFT every hop_size samples
        if self.count >= self.hop_size:
            self.count = 0

            # Rearrange buffer to proper order
            ordered = np.roll(self.buffer, -self.pointer)

            # Apply window and compute FFT
            windowed = ordered * self.window
            return fft(windowed)

        return None

    def process_array(self, samples: np.ndarray) -> list:
        """
        Process an array of samples.

        Args:
            samples: Array of complex samples

        Returns:
            List of FFT outputs
        """
        outputs = []
        for sample in samples:
            result = self.process(sample)
            if result is not None:
                outputs.append(result)
        return outputs


class OverlapAddFFT:
    """
    Overlap-add FFT filtering.

    Fast convolution using FFT for long filters.
    Based on fldigi's fftfilt implementation.
    """

    def __init__(self, impulse_response: np.ndarray, fft_size: Optional[int] = None):
        """
        Initialize the overlap-add filter.

        Args:
            impulse_response: Filter impulse response
            fft_size: FFT size (default: next power of 2 >= 2 * len(impulse_response))
        """
        self.ir_len = len(impulse_response)

        # Determine FFT size
        if fft_size is None:
            fft_size = 2 ** int(np.ceil(np.log2(2 * self.ir_len)))
        self.fft_size = fft_size

        # Half the FFT size (block processing size)
        self.block_size = fft_size // 2

        # Zero-pad impulse response and compute FFT
        ir_padded = np.zeros(fft_size, dtype=np.complex128)
        ir_padded[: self.ir_len] = impulse_response
        self.h_fft = fft(ir_padded)

        # Buffers
        self.input_buffer = np.zeros(fft_size, dtype=np.complex128)
        self.overlap_buffer = np.zeros(self.block_size, dtype=np.complex128)
        self.output_buffer = np.zeros(self.block_size, dtype=np.complex128)

        self.input_ptr = 0
        self.pass_count = 0  # Skip first pass for stability

    def reset(self) -> None:
        """Reset the filter state."""
        self.input_buffer.fill(0.0)
        self.overlap_buffer.fill(0.0)
        self.output_buffer.fill(0.0)
        self.input_ptr = 0
        self.pass_count = 0

    def process(self, sample: complex) -> Optional[complex]:
        """
        Process one sample.

        Args:
            sample: Complex input sample

        Returns:
            Filtered sample when a block is ready, None otherwise
        """
        # Collect samples until we have a half-block
        self.input_buffer[self.input_ptr] = sample
        self.input_ptr += 1

        if self.input_ptr < self.block_size:
            return None

        # Process block
        if self.pass_count > 0:
            self.pass_count -= 1

        # FFT of input
        x_fft = fft(self.input_buffer)

        # Multiply with filter in frequency domain
        y_fft = x_fft * self.h_fft

        # IFFT back to time domain
        y = ifft(y_fft)

        # Overlap and add
        for i in range(self.block_size):
            self.output_buffer[i] = self.overlap_buffer[i] + y[i]
            self.overlap_buffer[i] = y[i + self.block_size]

        # Reset input pointer
        self.input_ptr = 0

        # Return first output sample (user should call process multiple times)
        # For simplicity, we'll return None here and provide process_array method
        return None

    def process_array(self, samples: np.ndarray) -> np.ndarray:
        """
        Process an array of samples.

        This is the recommended method for using overlap-add filtering.

        Args:
            samples: Array of complex samples

        Returns:
            Filtered array (may be shorter due to overlap-add processing)
        """
        n_samples = len(samples)
        output = []

        for i in range(0, n_samples, self.block_size):
            # Get next block
            block = samples[i : i + self.block_size]

            # Pad if necessary
            if len(block) < self.block_size:
                block = np.pad(block, (0, self.block_size - len(block)), mode="constant")

            # Copy to input buffer
            self.input_buffer[: self.block_size] = block

            # FFT of input
            x_fft = fft(self.input_buffer)

            # Multiply with filter in frequency domain
            y_fft = x_fft * self.h_fft

            # IFFT back to time domain
            y = ifft(y_fft)

            # Overlap and add
            result_block = self.overlap_buffer + y[: self.block_size]
            self.overlap_buffer = y[self.block_size :].copy()

            # Skip first block for stability
            if self.pass_count > 0:
                self.pass_count -= 1
            else:
                output.extend(result_block)

        return np.array(output, dtype=np.complex128)
