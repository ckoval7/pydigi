"""
Viterbi decoder for FEC (Forward Error Correction).

Based on fldigi's Viterbi decoder implementation (fldigi/src/filters/viterbi.cxx).
Used in PSK modes with FEC for decoding convolutional codes.
"""

import numpy as np
from typing import Optional


def parity(value: int) -> int:
    """
    Calculate parity (odd number of 1 bits).

    Args:
        value: Integer value to calculate parity for

    Returns:
        0 if even number of 1 bits, 1 if odd number of 1 bits
    """
    count = bin(value).count("1")
    return count & 1


class ViterbiDecoder:
    """
    Viterbi decoder for convolutional codes.

    This implements a soft-decision Viterbi decoder that takes soft symbols
    (0-255 values) and produces decoded bits. The decoder uses path metrics
    and traceback to find the most likely sequence of transmitted bits.

    Used in PSK FEC modes for error correction.

    Attributes:
        k: Constraint length (number of shift register bits)
        poly1: First generator polynomial
        poly2: Second generator polynomial
        traceback: Number of steps to trace back (default: k * 12)
        chunksize: Number of bits to decode per traceback (default: 8)

    Example:
        >>> # Standard 8PSK FEC decoder (K=13)
        >>> decoder = ViterbiDecoder(k=13, poly1=0o16461, poly2=0o12767)
        >>> symbols = [128, 255, 0, 128]  # Soft symbols
        >>> bits, metric = decoder.decode(symbols)
    """

    PATHMEM = 256  # Path memory size (must match fldigi)

    def __init__(self, k: int, poly1: int, poly2: int, traceback: int = None, chunksize: int = 8):
        """
        Initialize the Viterbi decoder.

        Args:
            k: Constraint length (number of bits in shift register)
            poly1: First generator polynomial (octal or binary)
            poly2: Second generator polynomial (octal or binary)
            traceback: Number of steps to trace back (default: k * 12)
            chunksize: Number of bits to decode per traceback (default: 8)

        Common values:
            - K=13 (8PSK FEC): k=13, poly1=0o16461, poly2=0o12767
            - K=16 (8PSK FEC): k=16, poly1=0o152711, poly2=0o126723
            - K=5 (QPSK): k=5, poly1=0x17, poly2=0x19
        """
        self.k = k
        self.poly1 = poly1
        self.poly2 = poly2

        # State size parameters
        self.outsize = 1 << k  # 2^k
        self.nstates = 1 << (k - 1)  # 2^(k-1)

        # Traceback parameters
        self.traceback = traceback if traceback is not None else k * 12
        self.chunksize = chunksize

        # Build output lookup table
        # output[i] contains the 2-bit output for shift register state i
        self.output = np.zeros(self.outsize, dtype=np.uint8)
        for i in range(self.outsize):
            bit0 = parity(poly1 & i)
            bit1 = parity(poly2 & i)
            self.output[i] = bit0 | (bit1 << 1)

        # Build metric tables
        # mettab[0][i] = 128 - i (for bit = 0)
        # mettab[1][i] = i - 128 (for bit = 1)
        self.mettab = np.zeros((2, 256), dtype=np.int32)
        for i in range(256):
            self.mettab[0][i] = 128 - i
            self.mettab[1][i] = i - 128

        # Pre-compute state arrays for vectorized Viterbi (significant speedup)
        self._n_arr = np.arange(self.nstates, dtype=np.int32)
        self._s0_arr = self._n_arr  # State n with 0 input
        self._s1_arr = self._n_arr + self.nstates  # State n with 1 input
        self._p0_arr = self._s0_arr >> 1  # Previous state for s0
        self._p1_arr = self._s1_arr >> 1  # Previous state for s1
        self._output_s0 = self.output[self._s0_arr]
        self._output_s1 = self.output[self._s1_arr]

        # Path memory
        self.metrics = np.zeros((self.PATHMEM, self.nstates), dtype=np.int32)
        self.history = np.zeros((self.PATHMEM, self.nstates), dtype=np.int32)
        self.sequence = np.zeros(self.PATHMEM, dtype=np.int32)
        self.ptr = 0
        self.total_symbols = 0  # Track total symbols for limiting early tracebacks

    def reset(self):
        """Reset the decoder state to zero."""
        self.metrics.fill(0)
        self.history.fill(0)
        self.sequence.fill(0)
        self.ptr = 0
        self.total_symbols = 0

    def _traceback(self) -> tuple[int, int]:
        """
        Perform traceback to decode bits.

        Returns:
            Tuple of (decoded_bits, metric_delta)
        """
        # Find the state with the best metric
        p = (self.ptr - 1) % self.PATHMEM
        bestmetric = np.max(self.metrics[p])
        beststate = np.argmax(self.metrics[p])

        # Trace back 'traceback' steps, starting from the best state
        # Note: Early in the decode (before we have 'traceback' symbols), this will wrap
        # to uninitialized positions, making early bits unreliable. This is expected -
        # Viterbi decoders have inherent latency equal to the traceback depth.
        self.sequence[p] = beststate

        for i in range(self.traceback):
            prev = (p - 1) % self.PATHMEM
            self.sequence[prev] = self.history[p][self.sequence[p]]
            p = prev

        metric_start = self.metrics[p][self.sequence[p]]

        # Decode 'chunksize' bits
        c = 0
        for i in range(self.chunksize):
            # Low bit of state is the previous input bit
            c = (c << 1) | (self.sequence[p] & 1)
            p = (p + 1) % self.PATHMEM

        metric_end = self.metrics[p][self.sequence[p]]
        metric_delta = metric_end - metric_start

        return c, metric_delta

    def decode(self, symbols: list[int], metric_out: Optional[list] = None) -> Optional[int]:
        """
        Decode a pair of soft symbols.

        Args:
            symbols: List of 2 soft symbols (0-255 each)
                    symbols[0] = first bit
                    symbols[1] = second bit
            metric_out: Optional list to receive metric delta (pass a list to get value)

        Returns:
            Decoded bits (as integer), or None if not enough symbols accumulated

        Note:
            The decoder accumulates symbols and only returns decoded bits
            every 'chunksize' symbols (default: 8). This matches fldigi's behavior.
        """
        if len(symbols) < 2:
            return None

        currptr = self.ptr
        prevptr = (currptr - 1) % self.PATHMEM

        # Calculate branch metrics for all 4 possible symbol pairs
        # met[0] = both bits are 0 (00)
        # met[1] = first bit is 0, second is 1 (01)
        # met[2] = first bit is 1, second is 0 (10)
        # met[3] = both bits are 1 (11)
        met = np.zeros(4, dtype=np.int32)
        met[0] = self.mettab[0][symbols[1]] + self.mettab[0][symbols[0]]
        met[1] = self.mettab[0][symbols[1]] + self.mettab[1][symbols[0]]
        met[2] = self.mettab[1][symbols[1]] + self.mettab[0][symbols[0]]
        met[3] = self.mettab[1][symbols[1]] + self.mettab[1][symbols[0]]

        # Update all states (vectorized for performance)
        # m0[n] = metrics[prevptr][p0[n]] + met[output[s0[n]]]
        # m1[n] = metrics[prevptr][p1[n]] + met[output[s1[n]]]
        m0 = self.metrics[prevptr][self._p0_arr] + met[self._output_s0]
        m1 = self.metrics[prevptr][self._p1_arr] + met[self._output_s1]

        # Choose path with best metric (survivor)
        mask = m0 > m1
        self.metrics[currptr] = np.where(mask, m0, m1)
        self.history[currptr] = np.where(mask, self._p0_arr, self._p1_arr)

        # Advance pointer and symbol counter
        self.ptr = (self.ptr + 1) % self.PATHMEM
        self.total_symbols += 1

        # Perform traceback every 'chunksize' symbols
        if (self.ptr % self.chunksize) == 0:
            decoded_bits, metric_delta = self._traceback()
            if metric_out is not None and len(metric_out) > 0:
                metric_out[0] = metric_delta
            return decoded_bits

        # Normalize metrics to prevent overflow (matches fldigi lines 201-211)
        INT_MAX = 2147483647
        INT_MIN = -2147483648

        if self.metrics[currptr][0] > INT_MAX // 2:
            self.metrics -= INT_MAX // 2

        if self.metrics[currptr][0] < INT_MIN // 2:
            self.metrics += INT_MIN // 2

        return None

    def set_traceback(self, traceback: int) -> bool:
        """
        Set the traceback length.

        Args:
            traceback: Number of steps to trace back (1 to PATHMEM-1)

        Returns:
            True if successful, False if invalid
        """
        if traceback < 1 or traceback >= self.PATHMEM:
            return False
        self.traceback = traceback
        return True

    def set_chunksize(self, chunksize: int) -> bool:
        """
        Set the chunk size for decoding.

        Args:
            chunksize: Number of bits to decode per traceback (1 to traceback)

        Returns:
            True if successful, False if invalid
        """
        if chunksize < 1 or chunksize > self.traceback:
            return False
        self.chunksize = chunksize
        return True


# Standard decoder configurations
def create_8psk_k13_decoder() -> ViterbiDecoder:
    """
    Create a Viterbi decoder for 8PSK FEC modes with K=13.

    Used in 8PSK125FL, 8PSK250FL, 8PSK500F, 8PSK1000F, 8PSK1200F.

    Returns:
        ViterbiDecoder configured for K=13 8PSK FEC
    """
    return ViterbiDecoder(k=13, poly1=0o16461, poly2=0o12767)


def create_8psk_k16_decoder() -> ViterbiDecoder:
    """
    Create a Viterbi decoder for 8PSK FEC modes with K=16.

    Used in 8PSK125F, 8PSK250F (non-FL modes).

    Returns:
        ViterbiDecoder configured for K=16 8PSK FEC
    """
    return ViterbiDecoder(k=16, poly1=0o152711, poly2=0o126723)


def create_qpsk_decoder() -> ViterbiDecoder:
    """
    Create a Viterbi decoder for QPSK modes.

    Returns:
        ViterbiDecoder configured for QPSK
    """
    return ViterbiDecoder(k=5, poly1=0x17, poly2=0x19)
