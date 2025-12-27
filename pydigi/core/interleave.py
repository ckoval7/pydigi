"""
Interleaver for MFSK modes.

Based on fldigi's interleaver implementation (fldigi/src/mfsk/interleave.cxx).
The interleaver provides time diversity by spreading symbols across multiple
time slots, improving resistance to burst errors.

Reference: fldigi/src/mfsk/interleave.cxx
"""

import numpy as np

# Direction constants
INTERLEAVE_FWD = 0  # Forward (transmit)
INTERLEAVE_REV = 1  # Reverse (receive)
PUNCTURE = 128  # Puncture value for RX interleaver


class Interleave:
    """
    MFSK interleaver/deinterleaver.

    The interleaver uses a 3D table (depth x size x size) to shuffle bits
    or symbols, providing time diversity for error correction.

    Reference: fldigi/src/mfsk/interleave.cxx
    """

    def __init__(self, size: int, depth: int, direction: int = INTERLEAVE_FWD):
        """
        Initialize the interleaver.

        Args:
            size: Number of bits per symbol (e.g., 4 for MFSK16)
            depth: Interleave depth (e.g., 10 for MFSK16)
            direction: INTERLEAVE_FWD for TX, INTERLEAVE_REV for RX

        Reference:
            fldigi/src/mfsk/interleave.cxx lines 34-42
        """
        self.size = size
        self.depth = depth
        self.direction = direction
        self.len = size * size * depth

        # Create 3D table as a flat array
        self.table = np.zeros(self.len, dtype=np.uint8)
        self.flush()

    def _tab(self, i, j, k):
        """
        Access the 3D table at position (i, j, k).

        Args:
            i: Depth index (0 to depth-1)
            j: Row index (0 to size-1)
            k: Column index (0 to size-1)

        Returns:
            Index into flat table array

        Reference:
            fldigi/src/include/interleave.h lines 41-43
        """
        return (self.size * self.size * i) + (self.size * j) + k

    def symbols(self, psyms: np.ndarray) -> None:
        """
        Interleave or deinterleave an array of symbols.

        Args:
            psyms: Array of symbols (modified in-place)

        Reference:
            fldigi/src/mfsk/interleave.cxx lines 57-76
        """
        for k in range(self.depth):
            # Shift columns left
            for i in range(self.size):
                for j in range(self.size - 1):
                    idx_src = self._tab(k, i, j + 1)
                    idx_dst = self._tab(k, i, j)
                    self.table[idx_dst] = self.table[idx_src]

            # Insert new symbols at rightmost column
            for i in range(self.size):
                idx = self._tab(k, i, self.size - 1)
                self.table[idx] = psyms[i]

            # Extract symbols diagonally
            for i in range(self.size):
                if self.direction == INTERLEAVE_FWD:
                    idx = self._tab(k, i, self.size - i - 1)
                else:
                    idx = self._tab(k, i, i)
                psyms[i] = self.table[idx]

    def bits(self, pbits: int) -> int:
        """
        Interleave or deinterleave a bit pattern.

        Args:
            pbits: Integer containing bits to interleave (modified)

        Returns:
            Interleaved bit pattern

        Reference:
            fldigi/src/mfsk/interleave.cxx lines 78-90
        """
        # Extract bits into symbol array
        syms = np.zeros(self.size, dtype=np.uint8)
        for i in range(self.size):
            syms[i] = (pbits >> (self.size - i - 1)) & 1

        # Interleave symbols
        self.symbols(syms)

        # Pack bits back into integer
        result = 0
        for i in range(self.size):
            result = (result << 1) | syms[i]

        return result

    def flush(self):
        """
        Reset the interleaver table.

        For TX (FWD), fill with zeros.
        For RX (REV), fill with puncture markers.

        Reference:
            fldigi/src/mfsk/interleave.cxx lines 92-100
        """
        if self.direction == INTERLEAVE_REV:
            self.table.fill(PUNCTURE)
        else:
            self.table.fill(0)

    def init(self):
        """
        Re-initialize the interleaver.

        Reference:
            fldigi/src/mfsk/interleave.cxx lines 49-55
        """
        self.flush()
