"""
Convolutional encoder for FEC (Forward Error Correction).

Based on fldigi's encoder implementation (fldigi/src/filters/viterbi.cxx).
Used in QPSK and other PSK modes with FEC.
"""

import numpy as np


def parity(value: int) -> int:
    """
    Calculate parity (odd number of 1 bits).

    Args:
        value: Integer value to calculate parity for

    Returns:
        0 if even number of 1 bits, 1 if odd number of 1 bits
    """
    count = bin(value).count('1')
    return count & 1


class ConvolutionalEncoder:
    """
    Convolutional encoder for FEC.

    This implements a rate 1/2 convolutional encoder that takes 1 bit input
    and produces 2 bits output. The encoder uses two polynomials to generate
    the output bits through modulo-2 addition (XOR) of selected shift register
    positions.

    Used in QPSK modes for forward error correction.

    Attributes:
        k: Constraint length (number of shift register bits)
        poly1: First generator polynomial
        poly2: Second generator polynomial

    Example:
        >>> # Standard QPSK encoder (K=5)
        >>> encoder = ConvolutionalEncoder(k=5, poly1=0x17, poly2=0x19)
        >>> output = encoder.encode(1)  # Returns 2-bit value (0-3)
    """

    def __init__(self, k: int, poly1: int, poly2: int):
        """
        Initialize the convolutional encoder.

        Args:
            k: Constraint length (number of bits in shift register)
            poly1: First generator polynomial (binary)
            poly2: Second generator polynomial (binary)

        Common values for QPSK:
            k=5, poly1=0x17 (0b10111), poly2=0x19 (0b11001)
        """
        self.k = k
        self.poly1 = poly1
        self.poly2 = poly2

        # Shift register for encoder state
        self.shreg = 0

        # Size of output table (2^k entries)
        size = 1 << k
        self.shregmask = size - 1

        # Build output lookup table
        # output[i] contains the 2-bit output for shift register state i
        # Bit 0: parity of (poly1 & state)
        # Bit 1: parity of (poly2 & state)
        self.output_table = np.zeros(size, dtype=np.uint8)
        for i in range(size):
            bit0 = parity(poly1 & i)
            bit1 = parity(poly2 & i)
            self.output_table[i] = bit0 | (bit1 << 1)

    def encode(self, bit: int) -> int:
        """
        Encode a single bit and return the output symbol.

        Args:
            bit: Input bit (0 or 1)

        Returns:
            2-bit output symbol (0, 1, 2, or 3) for QPSK
        """
        # Shift new bit into register
        self.shreg = (self.shreg << 1) | (1 if bit else 0)

        # Look up output based on current state
        return self.output_table[self.shreg & self.shregmask]

    def reset(self):
        """Reset the encoder state to zero."""
        self.shreg = 0

    def flush(self, num_bits: int = 0) -> list:
        """
        Flush the encoder by sending zero bits.

        This is used at the end of transmission to clear the encoder state.

        Args:
            num_bits: Number of zero bits to send (default: k-1 for full flush)

        Returns:
            List of output symbols from flushing
        """
        if num_bits == 0:
            num_bits = self.k - 1

        outputs = []
        for _ in range(num_bits):
            outputs.append(self.encode(0))
        return outputs


# Standard encoder configurations
def create_qpsk_encoder() -> ConvolutionalEncoder:
    """
    Create a standard QPSK convolutional encoder.

    Uses K=5, POLY1=0x17, POLY2=0x19 (fldigi standard).

    Returns:
        ConvolutionalEncoder configured for QPSK
    """
    return ConvolutionalEncoder(k=5, poly1=0x17, poly2=0x19)


def create_mfsk_encoder() -> ConvolutionalEncoder:
    """
    Create a standard MFSK convolutional encoder (NASA coefficients).

    Uses K=7, POLY1=0x6d, POLY2=0x4f (NASA standard for MFSK).

    Returns:
        ConvolutionalEncoder configured for MFSK

    Reference:
        fldigi/src/include/mfsk.h lines 52-56
    """
    return ConvolutionalEncoder(k=7, poly1=0x6d, poly2=0x4f)
