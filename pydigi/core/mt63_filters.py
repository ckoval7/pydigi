"""
MT63 interpolation filters and windowing functions.

Based on fldigi dsp.cxx implementation.
"""

import numpy as np


def blackman3_window(phase):
    """
    Blackman3 window function (from Motorola).

    Args:
        phase: Phase angle in radians (typically -π to +π)

    Returns:
        Window value
    """
    return (0.35875 +
            0.48829 * np.cos(phase) +
            0.14128 * np.cos(2 * phase) +
            0.01168 * np.cos(3 * phase))


def design_windowed_fir(low_omega, high_omega, length, window_func=blackman3_window, shift=0.0):
    """
    Design windowed FIR filter for flat response from low_omega to high_omega.

    This implements the dspWinFirI function from fldigi.

    Args:
        low_omega: Lower cutoff frequency (normalized, 0 to π)
        high_omega: Upper cutoff frequency (normalized, 0 to π)
        length: Filter length
        window_func: Window function (takes phase as argument)
        shift: Time shift (default 0.0)

    Returns:
        FIR filter coefficients
    """
    shape = np.zeros(length)

    for i in range(length):
        # Match fldigi: time = i + (1.0 - shift) - (double)Len/2
        time = i + (1.0 - shift) - length / 2.0
        phase = 2.0 * np.pi * time / length

        # Sinc function for ideal bandpass
        if time == 0.0:
            freq_resp = high_omega - low_omega
        else:
            freq_resp = (np.sin(high_omega * time) - np.sin(low_omega * time)) / time

        # Apply window and normalize by PI (as in fldigi)
        shape[i] = freq_resp * window_func(phase) / np.pi

    return shape


def design_hilbert_fir(low_omega, high_omega, length, window_func=blackman3_window, shift=0.0):
    """
    Design windowed Hilbert transform FIR filter.

    This implements the WinFirQ function from fldigi (for quadrature).

    Args:
        low_omega: Lower cutoff frequency (normalized, 0 to π)
        high_omega: Upper cutoff frequency (normalized, 0 to π)
        length: Filter length
        window_func: Window function (takes phase as argument)
        shift: Time shift (default 0.0)

    Returns:
        Hilbert FIR filter coefficients
    """
    shape = np.zeros(length)

    for i in range(length):
        # Match fldigi: time = i + (1.0 - shift) - (double)Len/2
        time = i + (1.0 - shift) - length / 2.0
        phase = 2.0 * np.pi * time / length

        # Hilbert transform of sinc (for 90° phase shift)
        if time == 0.0:
            freq_resp = 0.0
        else:
            freq_resp = (-np.cos(high_omega * time) + np.cos(low_omega * time)) / time

        # Apply window and normalize by PI
        # NOTE: Negative sign applied as in fldigi (for reverse order indexing)
        shape[i] = (-freq_resp) * window_func(phase) / np.pi

    return shape


class PolyphaseInterpolator:
    """
    Polyphase interpolating FIR filter for I/Q to real conversion.

    This implements the dspQuadrComb functionality from fldigi.
    Takes complex baseband I/Q signal and:
    1. Interpolates by factor of `rate`
    2. Applies bandpass filtering
    3. Converts I/Q to real output
    """

    def __init__(self, filter_len, rate, low_omega, high_omega):
        """
        Initialize interpolator.

        Args:
            filter_len: Length of FIR filter
            rate: Interpolation ratio (2, 4, or 8 for MT63)
            low_omega: Lower cutoff (normalized angular frequency, 0 to π)
            high_omega: Upper cutoff (normalized angular frequency, 0 to π)
        """
        self.length = filter_len
        self.rate = rate

        # Design I and Q filters
        # NOTE: fldigi does NOT scale by rate - normalization happens in final output
        # See fldigi/src/mt63/mt63base.cxx lines 159-162
        self.shape_i = design_windowed_fir(low_omega, high_omega, filter_len)
        self.shape_q = design_hilbert_fir(low_omega, high_omega, filter_len)

        # Tap buffer for FIR filter state
        self.tap = np.zeros(filter_len)
        self.tap_ptr = 0

    def process(self, complex_input):
        """
        Process complex input through interpolating filter.

        Args:
            complex_input: Array of complex samples

        Returns:
            Real-valued output at interpolated rate
        """
        input_len = len(complex_input)
        output = np.zeros(input_len * self.rate)
        out_idx = 0

        for i in range(input_len):
            I = complex_input[i].real
            Q = complex_input[i].imag

            # Convolve input with filters and accumulate into tap buffer
            # This implements the polyphase filter structure
            # Matches fldigi: I*ShapeI + Q*ShapeQ
            # Note: ShapeQ is already negated in design_hilbert_fir()
            # so this effectively gives I*filter_I - Q*|filter_Q| (USB)
            r = 0
            for t in range(self.tap_ptr, self.length):
                self.tap[t] += I * self.shape_i[r] + Q * self.shape_q[r]
                r += 1

            for t in range(0, self.tap_ptr):
                self.tap[t] += I * self.shape_i[r] + Q * self.shape_q[r]
                r += 1

            # Output interpolated samples
            # Read from tap buffer and clear as we go
            remaining = self.length - self.tap_ptr

            if remaining < self.rate:
                # Output samples from current position to end of buffer
                for r in range(remaining):
                    output[out_idx] = self.tap[self.tap_ptr]
                    self.tap[self.tap_ptr] = 0.0
                    self.tap_ptr += 1
                    out_idx += 1

                # Wrap to beginning
                self.tap_ptr = 0

                # Output remaining samples
                for r in range(remaining, self.rate):
                    output[out_idx] = self.tap[self.tap_ptr]
                    self.tap[self.tap_ptr] = 0.0
                    self.tap_ptr += 1
                    out_idx += 1
            else:
                # Simple case: output rate samples
                for r in range(self.rate):
                    output[out_idx] = self.tap[self.tap_ptr]
                    self.tap[self.tap_ptr] = 0.0
                    self.tap_ptr += 1
                    out_idx += 1

        return output


class OverlapAddWindow:
    """
    Overlap-and-add windowing for OFDM symbols.

    Applies windowing and overlap-add to reduce inter-symbol interference.
    """

    def __init__(self, window_len, slide_dist, window_shape):
        """
        Initialize overlap-add processor.

        Args:
            window_len: Length of window (512 for MT63)
            slide_dist: Distance to slide window (100 for MT63)
            window_shape: Window shape coefficients (raised cosine for MT63)
        """
        self.window_len = window_len
        self.slide_dist = slide_dist
        self.window_shape = window_shape
        self.buffer = np.zeros(window_len, dtype=np.complex128)

    def process(self, input_samples):
        """
        Apply windowing and overlap-add.

        Args:
            input_samples: Complex input (can be window_len or multiple of window_len)

        Returns:
            Output samples (length = (len(input_samples)//window_len) * slide_dist)
        """
        # Process input in chunks of window_len
        num_windows = len(input_samples) // self.window_len
        output = np.zeros(num_windows * self.slide_dist, dtype=np.complex128)

        for w in range(num_windows):
            start = w * self.window_len
            end = start + self.window_len
            window_input = input_samples[start:end]

            # Apply window to input
            windowed = window_input * self.window_shape

            out_start = w * self.slide_dist

            # Overlap-add: output first slide_dist samples
            for i in range(self.slide_dist):
                output[out_start + i] = self.buffer[i] + windowed[i]

            # Shift buffer and add middle portion
            for i in range(self.slide_dist, self.window_len - self.slide_dist):
                self.buffer[i - self.slide_dist] = self.buffer[i] + windowed[i]

            # Store tail for next iteration
            for i in range(self.window_len - self.slide_dist, self.window_len):
                self.buffer[i - self.slide_dist] = windowed[i]

        return output
