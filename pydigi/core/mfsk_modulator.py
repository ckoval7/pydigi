"""
MFSK Modulator for Olivia and Contestia modes.

This module implements the MFSK modulator that generates multi-tone FSK signals
with raised cosine symbol shaping. Each symbol is transmitted as a specific
frequency tone selected from a bank of available tones.

Reference: fldigi/src/include/jalocha/pj_mfsk.h (MFSK_Modulator class)
"""

import numpy as np


class MFSKModulator:
    """
    MFSK modulator with raised cosine symbol shaping.

    Generates MFSK symbols as frequency tones with smooth transitions
    using raised cosine shaping to minimize spectral splatter.

    Reference: fldigi/src/include/jalocha/pj_mfsk.h lines 57-238
    """

    def __init__(self, symbol_len=512, first_carrier=32, bits_per_symbol=5,
                 sample_rate=8000.0, use_gray_code=True, reverse=False):
        """
        Initialize the MFSK modulator.

        Args:
            symbol_len: Length of each symbol in samples (must be power of 2)
            first_carrier: First carrier frequency bin
            bits_per_symbol: Number of bits per symbol (log2 of number of tones)
            sample_rate: Audio sample rate in Hz
            use_gray_code: Whether to use Gray coding
            reverse: Whether to reverse carrier order

        Reference:
            fldigi/src/include/jalocha/pj_mfsk.h lines 84-164
        """
        self.symbol_len = symbol_len
        self.first_carrier = first_carrier
        self.bits_per_symbol = bits_per_symbol
        self.sample_rate = sample_rate
        self.use_gray_code = use_gray_code
        self.reverse = reverse

        # Derived parameters
        self.carriers = 1 << bits_per_symbol  # 2^bits_per_symbol
        self.symbol_separ = symbol_len // 2  # Symbol separation
        self.carrier_separ = 2  # Carrier separation in FFT bins

        # Symbol phase tracking
        self.symbol_phase = 0
        self.wrap_mask = symbol_len - 1

        # Build cosine table for fast cos/sin calculation
        self.cosine_table = np.cos(2 * np.pi * np.arange(symbol_len) / symbol_len)

        # Build symbol shape (raised cosine in frequency domain)
        # Using simple {1.0, 1.0} for experimental raised cosine shape
        # Reference: fldigi/src/include/jalocha/pj_mfsk.h lines 35-36
        self.symbol_shape = self._build_symbol_shape()

        # Output tap buffer
        self.out_tap = np.zeros(symbol_len, dtype=np.float64)
        self.tap_ptr = 0

    def _build_symbol_shape(self):
        """
        Build the symbol shape in time domain.

        Converts the frequency-domain shape specification to time domain
        using inverse DFT.

        Reference:
            fldigi/src/include/jalocha/pj_mfsk.h lines 126-149
            Uses experimental raised cosine: {1.0, 1.0}
        """
        shape = np.ones(self.symbol_len, dtype=np.float64)
        freq_shape = [1.0, 1.0]  # Raised cosine shape

        # Apply each frequency component
        for freq, ampl in enumerate(freq_shape):
            if freq == 0:
                shape *= ampl
            else:
                # Alternate sign for odd frequencies
                if freq & 1:
                    ampl = -ampl

                phase = 0
                for time in range(self.symbol_len):
                    shape[time] += ampl * self.cosine_table[phase]
                    phase = (phase + freq) % self.symbol_len

        # Scale the shape
        shape *= 0.25
        return shape

    def _gray_code(self, value):
        """
        Convert binary value to Gray code.

        Args:
            value: Binary value to convert

        Returns:
            Gray-coded value

        Reference:
            fldigi/src/include/jalocha/pj_gray.h
        """
        return value ^ (value >> 1)

    def send(self, symbol):
        """
        Send a symbol by generating the corresponding tone.

        Args:
            symbol: Symbol value (0 to carriers-1)

        Reference:
            fldigi/src/include/jalocha/pj_mfsk.h lines 166-187
        """
        # Apply Gray code if enabled
        if self.use_gray_code:
            symbol = self._gray_code(symbol)

        # Calculate symbol frequency
        if self.reverse:
            rev_first_car = self.first_carrier - 2
            symbol_freq = rev_first_car - self.carrier_separ * symbol
        else:
            symbol_freq = self.first_carrier + self.carrier_separ * symbol

        # Calculate time shifts
        time_shift = self.symbol_separ // 2 - self.symbol_len // 2
        self.symbol_phase = (self.symbol_phase + symbol_freq * time_shift) & self.wrap_mask

        # Add symbol to output tap
        self._add_symbol(symbol_freq, self.symbol_phase)

        # Update phase for next symbol
        time_shift = self.symbol_separ // 2 + self.symbol_len // 2
        self.symbol_phase = (self.symbol_phase + symbol_freq * time_shift) & self.wrap_mask

        # Add random phase jitter (as in fldigi)
        phase_differ = self.symbol_len // 4
        if np.random.randint(2):
            phase_differ = -phase_differ
        self.symbol_phase = (self.symbol_phase + phase_differ) & self.wrap_mask

    def _add_symbol(self, freq, phase):
        """
        Add a symbol to the output tap buffer.

        Args:
            freq: Frequency bin of the symbol
            phase: Starting phase

        Reference:
            fldigi/src/include/jalocha/pj_mfsk.h lines 223-236
            Uses experimental raised cosine: shape = 1.0 - cos(phase)
        """
        for time in range(self.symbol_len):
            # Experimental raised cosine shaping
            shape = 1.0 - self.cosine_table[time]
            self.out_tap[self.tap_ptr] += self.cosine_table[phase] * shape

            phase = (phase + freq) & self.wrap_mask
            self.tap_ptr = (self.tap_ptr + 1) & self.wrap_mask

    def output(self):
        """
        Get the next block of modulator output samples.

        Returns:
            numpy array of audio samples (length = symbol_separ)

        Reference:
            fldigi/src/include/jalocha/pj_mfsk.h lines 209-219, 1839-1844
        """
        buffer = np.zeros(self.symbol_separ, dtype=np.float64)

        for idx in range(self.symbol_separ):
            buffer[idx] = self.out_tap[self.tap_ptr]
            self.out_tap[self.tap_ptr] = 0
            self.tap_ptr = (self.tap_ptr + 1) & self.wrap_mask

        # Normalize by maximum absolute value (like fldigi does)
        # Reference: fldigi/src/include/jalocha/pj_mfsk.h lines 1839-1844
        maxval = np.max(np.abs(buffer))
        if maxval > 0:
            buffer = buffer / maxval

        return buffer

    def reset(self):
        """Reset the modulator state."""
        self.symbol_phase = 0
        self.out_tap.fill(0)
        self.tap_ptr = 0
