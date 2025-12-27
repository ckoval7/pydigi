"""
MFSK FEC Encoder using Fast Hadamard Transform.

This module implements the FEC encoder used by Olivia and Contestia modems.
The encoder uses Fast Hadamard Transform to provide forward error correction
by spreading the signal energy across multiple time slots.

Reference: fldigi/src/include/jalocha/pj_mfsk.h (MFSK_Encoder class)
"""

import numpy as np
from .fht import ifht


class MFSKEncoder:
    """
    MFSK FEC encoder using Fast Hadamard Transform.

    This encoder takes input characters and produces symbol blocks with
    forward error correction. It uses FHT to spread the data across multiple
    symbols for improved reliability.

    Reference: fldigi/src/include/jalocha/pj_mfsk.h lines 1060-1217
    """

    # Scrambling codes for different modes
    SCRAMBLING_CODE_OLIVIA = 0xE257E6D0291574EC
    SCRAMBLING_CODE_CONTESTIA = 0xEDB88320

    def __init__(self, bits_per_symbol=5, mode='olivia'):
        """
        Initialize the MFSK encoder.

        Args:
            bits_per_symbol: Number of bits per symbol (determines number of tones)
            mode: 'olivia' or 'contestia' (affects character encoding and scrambling)

        Reference:
            fldigi/src/include/jalocha/pj_mfsk.h lines 1089-1131
        """
        self.bits_per_symbol = bits_per_symbol
        self.mode = mode.lower()

        # Set mode-specific parameters
        if self.mode == 'contestia':
            self.scrambling_code = self.SCRAMBLING_CODE_CONTESTIA
            self.bits_per_character = 6
            self.n_shift = 5
        else:  # olivia
            self.scrambling_code = self.SCRAMBLING_CODE_OLIVIA
            self.bits_per_character = 7
            self.n_shift = 13

        # Calculate derived parameters
        self.symbols = 1 << bits_per_symbol  # 2^bits_per_symbol
        self.symbols_per_block = 1 << (self.bits_per_character - 1)  # 2^(bits_per_char - 1)

        # Buffers
        self.fht_buffer = np.zeros(self.symbols_per_block, dtype=np.int8)
        self.output_block = np.zeros(self.symbols_per_block, dtype=np.uint8)

    def _encode_character(self, char):
        """
        Encode a single character using FHT.

        Args:
            char: Character code (0-127 for Olivia, 0-63 for Contestia)

        Reference:
            fldigi/src/include/jalocha/pj_mfsk.h lines 1133-1166
        """
        mask = (self.symbols_per_block << 1) - 1

        # Apply mode-specific character mapping
        if self.mode == 'contestia':
            # Contestia character mapping
            if ord('a') <= char <= ord('z'):
                char = char - ord('a') + ord('A')  # Convert to uppercase
            if char == ord(' '):
                char = 59
            elif char == ord('\r'):
                char = 60
            elif char == ord('\n'):
                char = 0
            elif 33 <= char <= 90:
                char -= 32
            elif char == 8:  # Backspace
                char = 61
            elif char == 0:
                char = 0
            else:
                char = ord('?') - 32
        else:
            # Olivia just masks to valid range
            char &= mask

        # Initialize FHT buffer
        self.fht_buffer.fill(0)

        # Set the character bit
        if char < self.symbols_per_block:
            self.fht_buffer[char] = 1
        else:
            self.fht_buffer[char - self.symbols_per_block] = -1

        # Apply inverse FHT
        self.fht_buffer = ifht(self.fht_buffer).astype(np.int8)

    def _scramble_fht(self, code_offset=0):
        """
        Apply scrambling to the FHT buffer using the scrambling code.

        Args:
            code_offset: Offset into the scrambling code

        Reference:
            fldigi/src/include/jalocha/pj_mfsk.h lines 1168-1177
        """
        code_wrap = self.symbols_per_block - 1
        code_bit = code_offset & code_wrap

        for time_bit in range(self.symbols_per_block):
            code_mask = 1 << code_bit
            if self.scrambling_code & code_mask:
                self.fht_buffer[time_bit] = -self.fht_buffer[time_bit]
            code_bit = (code_bit + 1) & code_wrap

    def encode_block(self, input_block):
        """
        Encode a block of characters into symbols.

        Takes a block of characters (one per frequency bit) and produces
        a block of symbols ready for transmission.

        Args:
            input_block: Array of character codes (length = bits_per_symbol)

        Returns:
            numpy array of symbols (length = symbols_per_block)

        Reference:
            fldigi/src/include/jalocha/pj_mfsk.h lines 1179-1207
        """
        # Initialize output block
        self.output_block.fill(0)

        # Process each frequency bit
        for freq_bit in range(self.bits_per_symbol):
            # Encode the character for this frequency bit
            self._encode_character(input_block[freq_bit])

            # Scramble the FHT output
            self._scramble_fht(freq_bit * self.n_shift)

            # Build output symbols
            rotate = 0
            for time_bit in range(self.symbols_per_block):
                if self.fht_buffer[time_bit] < 0:
                    bit = freq_bit + rotate
                    if bit >= self.bits_per_symbol:
                        bit -= self.bits_per_symbol
                    mask = 1 << bit
                    self.output_block[time_bit] |= mask

                rotate += 1
                if rotate >= self.bits_per_symbol:
                    rotate -= self.bits_per_symbol

        return self.output_block.copy()
