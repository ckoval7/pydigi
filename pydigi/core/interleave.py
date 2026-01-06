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


# Generic Block Deinterleaver (used by Olivia, Contestia, MT63, Thor)


class BlockDeinterleaver:
    """
    Generic block de-interleaver for burst error protection.

    Block interleaving spreads consecutive symbols across time by writing
    symbols row-by-row into a matrix and reading column-by-column (or vice versa).
    This converts burst errors into scattered errors that FEC can correct.

    Transmitter Operation:
        1. Write symbols row-by-row into rows×cols matrix
        2. Read symbols column-by-column for transmission
        3. Burst errors affect multiple columns, not consecutive rows

    Receiver Operation (this class):
        1. Receive symbols were sent column-by-column
        2. Write received symbols column-by-column into matrix
        3. Read symbols row-by-row to recover original order
        4. Scattered errors are now back in original positions

    Used by:
        - Olivia: 2×2, 4×4, 8×8 blocks depending on mode
        - Contestia: Similar to Olivia
        - MT63: 32×64 or 64×64 interleaver
        - Thor: Various sizes

    Example:
        >>> # For a 4×4 interleaver
        >>> deinterleaver = BlockDeinterleaver(rows=4, cols=4)
        >>>
        >>> # Feed symbols one at a time
        >>> for symbol in received_symbols:
        >>>     ready, block = deinterleaver.push_symbol(symbol)
        >>>     if ready:
        >>>         # Process de-interleaved block
        >>>         decode_block(block)

    Reference:
        - "Optimal Interleaving Schemes for Block and Convolutional Codes" - Ramsey (1970)
        - fldigi/src/olivia/olivia.cxx
        - fldigi/src/mt63/mt63.cxx
    """

    def __init__(self, rows: int, cols: int):
        """
        Initialize block de-interleaver.

        Args:
            rows: Number of rows in interleaver matrix
            cols: Number of columns in interleaver matrix
        """
        self.rows = rows
        self.cols = cols
        self.block_size = rows * cols

        # Storage matrix
        self.matrix = np.zeros((rows, cols), dtype=complex)

        # Current position (fill column-by-column)
        self.col_index = 0
        self.row_index = 0
        self.symbols_in = 0

    def push_symbol(self, symbol) -> tuple:
        """
        Add one symbol to de-interleaver.

        Args:
            symbol: Input symbol (can be complex, float, or int)

        Returns:
            (ready, deinterleaved_block) tuple:
                - ready: True if a complete block is available
                - deinterleaved_block: De-interleaved symbols (or None if not ready)
        """
        # Fill matrix column-by-column (reverse of transmitter)
        self.matrix[self.row_index, self.col_index] = symbol
        self.row_index += 1
        self.symbols_in += 1

        # Move to next column when current column is full
        if self.row_index >= self.rows:
            self.row_index = 0
            self.col_index += 1

        # Check if block is complete
        if self.col_index >= self.cols:
            # Read row-by-row (C-order = row-major)
            deinterleaved = self.matrix.flatten('C')

            # Reset for next block
            self.col_index = 0
            self.row_index = 0

            return True, deinterleaved

        return False, None

    def push_symbols(self, symbols: np.ndarray) -> list:
        """
        Push multiple symbols at once.

        Args:
            symbols: Array of input symbols

        Returns:
            List of de-interleaved blocks (may be empty or contain multiple blocks)
        """
        blocks = []
        for symbol in symbols:
            ready, block = self.push_symbol(symbol)
            if ready:
                blocks.append(block)
        return blocks

    def push_bits(self, bits: np.ndarray) -> list:
        """
        Push bits (alternative interface for bit-based modes).

        Args:
            bits: Array of input bits (0 or 1)

        Returns:
            List of de-interleaved bit blocks
        """
        return self.push_symbols(bits)

    def reset(self):
        """Reset the de-interleaver state."""
        self.matrix.fill(0)
        self.col_index = 0
        self.row_index = 0
        self.symbols_in = 0

    def get_fill_level(self) -> float:
        """
        Get current fill level as fraction of block size.

        Returns:
            Fill level (0.0 to 1.0)
        """
        return self.symbols_in / self.block_size if self.block_size > 0 else 0.0


class ConvolutionalDeinterleaver:
    """
    Convolutional de-interleaver.

    Convolutional interleaving uses delay lines of increasing length.
    Each symbol path has a different delay: 0, D, 2D, 3D, ...
    At the receiver, reverse delays reconstruct the original sequence.

    More complex than block interleaving but lower latency for same
    interleaving depth.

    Transmitter:
        Symbol → Branch 0 (delay 0) → Output
              → Branch 1 (delay D) → Output
              → Branch 2 (delay 2D) → Output
              ...

    Receiver (this class):
        Symbol → Branch 0 (delay (N-1)D) → Output
              → Branch 1 (delay (N-2)D) → Output
              → Branch 2 (delay (N-3)D) → Output
              ...

    Used by:
        - Some MFSK variants
        - Less common than block interleaving

    Example:
        >>> deinterleaver = ConvolutionalDeinterleaver(branches=4, delay=10)
        >>> for symbol in symbols:
        >>>     output = deinterleaver.push_symbol(symbol)
        >>>     if output is not None:
        >>>         process_symbol(output)

    Reference:
        - Ramsey, "Optimal Interleaving Schemes"
        - Forney, "Convolutional Codes I: Algebraic Structure"
    """

    def __init__(self, branches: int, delay: int):
        """
        Initialize convolutional de-interleaver.

        Args:
            branches: Number of parallel branches
            delay: Delay increment (in symbols)
                  Total delay for branch i = i × delay
        """
        self.branches = branches
        self.delay = delay

        # Create delay lines (FIFOs) for each branch
        # Branch i has delay (branches - 1 - i) × delay
        # This reverses the transmitter's interleaving
        self.fifos = []
        for i in range(branches):
            branch_delay = (branches - 1 - i) * delay
            # Use deque with maxlen for automatic size limiting
            if branch_delay > 0:
                fifo = []  # Start with empty list, will fill during operation
                self.fifos.append(fifo)
            else:
                self.fifos.append([])  # No delay for this branch

        self.branch_index = 0
        self.initialized = False
        self.init_counter = 0
        self.max_delay = (branches - 1) * delay

    def push_symbol(self, symbol):
        """
        De-interleave one symbol.

        Args:
            symbol: Input symbol

        Returns:
            De-interleaved symbol (or None during initialization)
        """
        fifo = self.fifos[self.branch_index]
        branch_delay = (self.branches - 1 - self.branch_index) * self.delay

        # Add symbol to delay line
        fifo.append(symbol)

        # Get output symbol
        if branch_delay == 0:
            # No delay - immediate output
            output = symbol
        elif len(fifo) > branch_delay:
            # Delay line full - output oldest symbol
            output = fifo.pop(0)
        else:
            # Still filling delay line - no valid output yet
            output = None

        # Move to next branch
        self.branch_index = (self.branch_index + 1) % self.branches

        # Track initialization
        if not self.initialized:
            self.init_counter += 1
            if self.init_counter >= self.max_delay:
                self.initialized = True

        return output

    def push_symbols(self, symbols: np.ndarray) -> list:
        """
        Push multiple symbols.

        Args:
            symbols: Array of input symbols

        Returns:
            List of de-interleaved symbols (may contain None during init)
        """
        outputs = []
        for symbol in symbols:
            output = self.push_symbol(symbol)
            if output is not None:
                outputs.append(output)
        return outputs

    def reset(self):
        """Reset the de-interleaver state."""
        for fifo in self.fifos:
            fifo.clear()
        self.branch_index = 0
        self.initialized = False
        self.init_counter = 0

    def is_initialized(self) -> bool:
        """Check if de-interleaver is initialized (delay lines filled)."""
        return self.initialized
