"""
Fast Hadamard Transform (FHT) implementation for MFSK FEC encoding.

This module provides forward and inverse Fast Hadamard Transform functions
used in Olivia and Contestia modems for forward error correction.

Reference: fldigi/src/include/jalocha/pj_fht.h
Original implementation by Pawel Jalocha, December 2004
"""

import numpy as np


def fht(data: np.ndarray) -> np.ndarray:
    """
    Forward Fast Hadamard Transform.

    The FHT is used to spread the signal energy across multiple time slots,
    providing forward error correction capability.

    Args:
        data: numpy array of data to transform (length must be power of 2)

    Returns:
        numpy array containing the transformed data

    Reference:
        fldigi/src/include/jalocha/pj_fht.h lines 8-27
    """
    result = data.copy()
    length = len(result)

    step = 1
    while step < length:
        ptr = 0
        while ptr < length:
            for ptr2 in range(ptr, ptr + step):
                bit1 = result[ptr2]
                bit2 = result[ptr2 + step]
                result[ptr2] = bit2 + bit1
                result[ptr2 + step] = bit2 - bit1
            ptr += 2 * step
        step *= 2

    return result


def ifht(data: np.ndarray) -> np.ndarray:
    """
    Inverse Fast Hadamard Transform.

    The IFHT is used during encoding to convert character data into
    time-domain symbols suitable for transmission.

    Args:
        data: numpy array of data to transform (length must be power of 2)

    Returns:
        numpy array containing the inverse transformed data

    Reference:
        fldigi/src/include/jalocha/pj_fht.h lines 29-49
    """
    result = data.copy()
    length = len(result)

    step = length // 2
    while step > 0:
        ptr = 0
        while ptr < length:
            for ptr2 in range(ptr, ptr + step):
                bit1 = result[ptr2]
                bit2 = result[ptr2 + step]
                result[ptr2] = bit1 - bit2
                result[ptr2 + step] = bit1 + bit2
            ptr += 2 * step
        step //= 2

    return result
