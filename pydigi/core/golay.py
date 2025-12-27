"""
Golay(24,12) Forward Error Correction Encoder/Decoder.

This module implements the Golay(24,12) extended binary error-correcting code
used in SCAMP modem protocol. The code can correct up to 3 bit errors in a
24-bit codeword.

Based on fldigi implementation in scamp_protocol.cxx
"""

import numpy as np
from typing import Tuple


# Golay generator matrix - converts 12 data bits to 12 parity bits
GOLAY_MATRIX = np.array([
    0xdc5,  # 0b 1101 1100 0101
    0xb8b,  # 0b 1011 1000 1011
    0x717,  # 0b 0111 0001 0111
    0xe2d,  # 0b 1110 0010 1101
    0xc5b,  # 0b 1100 0101 1011
    0x8b7,  # 0b 1000 1011 0111
    0x16f,  # 0b 0001 0110 1111
    0x2dd,  # 0b 0010 1101 1101
    0x5d9,  # 0b 0101 1011 1001
    0xb71,  # 0b 1011 0111 0001
    0x6e3,  # 0b 0110 1110 0011
    0xffe   # 0b 1111 1111 1110
], dtype=np.uint16)


def hamming_weight_16(n: int) -> int:
    """
    Calculate the Hamming weight (number of 1 bits) of a 16-bit number.

    Args:
        n: 16-bit integer

    Returns:
        Number of 1 bits in the integer
    """
    count = 0
    n = n & 0xFFFF
    while n:
        n &= (n - 1)
        count += 1
    return count


def hamming_weight_30(n: int) -> int:
    """
    Calculate the Hamming weight (number of 1 bits) of a 30-bit number.

    Args:
        n: 30-bit integer

    Returns:
        Number of 1 bits in the integer
    """
    count = 0
    n = n & 0x3FFFFFFF
    while n:
        n &= (n - 1)
        count += 1
    return count


def golay_mult(data: int) -> int:
    """
    Multiply a 12-bit data word by the Golay generator matrix.

    This performs the matrix multiplication to generate the 12 parity bits
    from the 12 data bits.

    Args:
        data: 12-bit data word (0x000 to 0xFFF)

    Returns:
        12-bit parity word
    """
    parity = 0
    data = data & 0xFFF

    for i in range(11, -1, -1):
        if data & 1:
            parity ^= int(GOLAY_MATRIX[i])
        data >>= 1

    return parity & 0xFFF


def golay_encode(data: int) -> int:
    """
    Encode a 12-bit data word into a 24-bit Golay codeword.

    The codeword format is:
    - Bits 23-12: 12 parity bits (generated from data)
    - Bits 11-0:  12 data bits (original input)

    Args:
        data: 12-bit data word (0x000 to 0xFFF)

    Returns:
        24-bit Golay codeword (0x000000 to 0xFFFFFF)

    Example:
        >>> hex(golay_encode(0xABC))
        '0x...'  # 24-bit codeword with parity in upper 12 bits
    """
    data = data & 0xFFF
    parity = golay_mult(data)
    codeword = (parity << 12) | data
    return codeword & 0xFFFFFF


def golay_decode(codeword: int) -> Tuple[int, int]:
    """
    Decode a 24-bit Golay codeword, correcting up to 3 bit errors.

    Args:
        codeword: 24-bit Golay codeword

    Returns:
        Tuple of (decoded_data, bit_errors):
        - decoded_data: 12-bit corrected data word, or 0xFFFF if uncorrectable
        - bit_errors: Number of bit errors corrected (0-3), or >3 if uncorrectable

    Example:
        >>> data, errors = golay_decode(encoded_word)
        >>> if data != 0xFFFF:
        ...     print(f"Decoded {hex(data)} with {errors} bit errors")
    """
    codeword = codeword & 0xFFFFFF
    data = codeword & 0xFFF
    parity = (codeword >> 12) & 0xFFF

    # Calculate syndrome (difference between received and expected parity)
    syndrome = golay_mult(data) ^ parity
    bit_errors = hamming_weight_16(syndrome)

    # Case 1: 3 or fewer errors in parity bits only
    # Assume data is correct
    if bit_errors <= 3:
        return data, bit_errors

    # Case 2: Check if parity bits have no errors
    # (errors are in data bits)
    parity_syndrome = golay_mult(parity) ^ data
    bit_errors = hamming_weight_16(parity_syndrome)
    if bit_errors <= 3:
        corrected_data = data ^ parity_syndrome
        return corrected_data & 0xFFF, bit_errors

    # Case 3: Try flipping each data bit to see if we have 2 or fewer errors
    for i in range(11, -1, -1):
        test_syndrome = syndrome ^ int(GOLAY_MATRIX[i])
        bit_errors = hamming_weight_16(test_syndrome)
        if bit_errors <= 2:
            corrected_data = data ^ (0x800 >> i)
            return corrected_data & 0xFFF, bit_errors + 1

    # Case 4: Try flipping each parity bit to see if we have 2 or fewer errors
    for i in range(11, -1, -1):
        par_bit_synd = parity_syndrome ^ int(GOLAY_MATRIX[i])
        bit_errors = hamming_weight_16(par_bit_synd)
        if bit_errors <= 2:
            corrected_data = data ^ par_bit_synd
            return corrected_data & 0xFFF, bit_errors + 1

    # Uncorrectable error
    return 0xFFFF, 99


def add_reversal_bits(codeword: int) -> int:
    """
    Add reversal bits to a 24-bit Golay codeword to create a 30-bit SCAMP frame.

    The reversal bits are inserted at positions 1, 5, 9, 13, 17, 21 (counting from MSB).
    Each reversal bit is the complement of the following data bit.

    The process groups the 24 bits into 6 groups of 4 bits, then inserts a
    reversal bit (complement of bit 3 in each group) before bit 3.

    Input format (24 bits):  [b23 b22 b21 b20][b19 b18 b17 b16]...[b3 b2 b1 b0]
    Output format (30 bits): [b23 b22 b21 ~b20 b20][b19 b18 b17 ~b16 b16]...[b3 b2 b1 ~b0 b0]

    Args:
        codeword: 24-bit Golay codeword

    Returns:
        30-bit SCAMP frame with reversal bits inserted

    Example:
        >>> frame = add_reversal_bits(0xABCDEF)
        >>> bin(frame)  # 30-bit frame
    """
    codeword = codeword & 0xFFFFFF
    outword = 0

    for i in range(6):
        if i > 0:
            outword <<= 5
        codeword <<= 4

        # Extract the top 4 bits
        temp = (codeword >> 24) & 0x0F

        # Insert reversal bit (complement of bit 3)
        # temp format: [b3 b2 b1 b0]
        # output format: [b3 b2 b1 ~b3 b0]
        reversal_bit = ((temp & 0x08) ^ 0x08) << 1
        outword |= (temp | reversal_bit)

    return outword & 0x3FFFFFFF


def remove_reversal_bits(frame: int) -> int:
    """
    Remove reversal bits from a 30-bit SCAMP frame to recover a 24-bit Golay codeword.

    This is the inverse of add_reversal_bits(). It extracts the original 24 bits
    by removing the inserted reversal bits.

    Input format (30 bits):  [b23 b22 b21 ~b20 b20][b19 b18 b17 ~b16 b16]...
    Output format (24 bits): [b23 b22 b21 b20][b19 b18 b17 b16]...

    Args:
        frame: 30-bit SCAMP frame

    Returns:
        24-bit Golay codeword

    Example:
        >>> codeword = remove_reversal_bits(frame)
        >>> hex(codeword)  # 24-bit codeword
    """
    frame = frame & 0x3FFFFFFF
    codeword = 0

    for i in range(6):
        if i > 0:
            frame <<= 5
            codeword <<= 4

        # Extract the top 5 bits and keep only the data bits
        # Input: [b3 b2 b1 ~b3 b0]
        # Output: [b3 b2 b1 b0]
        temp = (frame >> 25) & 0x0F
        codeword |= temp

    return codeword & 0xFFFFFF


# SCAMP special frame codewords (30-bit values with reversal bits)
SCAMP_SOLID_CODEWORD = 0x3FFFFFFF          # All 1s - FSK preamble
SCAMP_DOTTED_CODEWORD = 0x2AAAAAAA        # Alternating pattern - OOK preamble
SCAMP_INIT_CODEWORD = 0x3FFFFFD5          # Initialize codeword
SCAMP_SYNC_CODEWORD = 0x3ED19D1E          # Synchronization codeword
SCAMP_BLANK_CODEWORD = 0x00000000         # Blank/null codeword

# Special codes (12-bit values before Golay encoding)
SCAMP_RES_CODE_END_TRANSMISSION = 0x03C   # End of transmission marker

# End of transmission frame
# NOTE: Must use fldigi's exact value even though it has different parity.
# fldigi's frame decodes with 2 bit errors but is still recognized.
# Our mathematically correct frame (0x1B15426C) is not recognized by fldigi.
SCAMP_RES_CODE_END_TRANSMISSION_FRAME = 0x1B75426C
