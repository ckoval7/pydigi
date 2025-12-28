"""
CCIR-476 character encoding for NAVTEX and SITOR-B.

This module provides character encoding tables and conversion functions
for the CCIR-476 code used in NAVTEX (navigational telex) and SITOR-B
maritime transmissions.

CCIR-476 is a 7-bit character encoding with built-in error detection:
- Each valid code has exactly 4 bits set to 1 (out of 7 bits)
- This allows detection of single and double bit errors
- Two shift states: LETTERS mode and FIGURES mode
- Forward Error Correction (FEC) with character repetition

References:
    - fldigi/src/navtex/navtex.cxx
    - CCIR Recommendation 476-4
    - ITU-R M.540-2 (NAVTEX technical characteristics)
"""

import numpy as np
from typing import List, Tuple, Optional

# Shift state constants
LETTERS = 0  # Letters mode
FIGURES = 1  # Figures mode

# Special CCIR-476 codes (7-bit values with 4 bits set)
CODE_LTRS = 0x5A  # Letters shift (binary: 1011010)
CODE_FIGS = 0x36  # Figures shift (binary: 0110110)
CODE_ALPHA = 0x0F  # Alpha character marker (binary: 0001111)
CODE_BETA = 0x33  # Beta character marker (binary: 0110011)
CODE_REP = 0x66  # Repeat/redundancy marker (binary: 1100110)
CODE_CHAR32 = 0x6A  # Space character code (binary: 1101010)

# Letters table - CCIR-476 code to letter character
# Only codes with exactly 4 bits set are valid
CODE_TO_LTRS = {
    # Code  Char  Binary
    0x47: "A",  # 1000111
    0x72: "B",  # 1110010
    0x1D: "C",  # 0011101
    0x53: "D",  # 1010011
    0x56: "E",  # 1010110
    0x1B: "F",  # 0011011
    0x35: "G",  # 0110101
    0x69: "H",  # 1101001
    0x4D: "I",  # 1001101
    0x17: "J",  # 0010111
    0x1E: "K",  # 0011110
    0x65: "L",  # 1100101
    0x39: "M",  # 0111001
    0x59: "N",  # 1011001
    0x71: "O",  # 1110001
    0x2D: "P",  # 0101101
    0x2E: "Q",  # 0101110
    0x55: "R",  # 1010101
    0x4B: "S",  # 1001011
    0x74: "T",  # 1110100
    0x4E: "U",  # 1001110
    0x3C: "V",  # 0111100
    0x27: "W",  # 0100111
    0x3A: "X",  # 0111010
    0x2B: "Y",  # 0101011
    0x63: "Z",  # 1100011
    0x6C: "\n",  # Line feed (binary: 1101100)
    0x78: "\r",  # Carriage return (binary: 1111000)
    0x5C: " ",  # Space (binary: 1011100)
}

# US-TTY figures table
USTTY_CODE_TO_FIGS = {
    0x2E: "1",  # Q in letters
    0x27: "2",  # W in letters
    0x56: "3",  # E in letters
    0x55: "4",  # R in letters
    0x74: "5",  # T in letters
    0x2B: "6",  # Y in letters
    0x4E: "7",  # U in letters
    0x4D: "8",  # I in letters
    0x71: "9",  # O in letters
    0x2D: "0",  # P in letters
    0x17: "'",  # J in letters (apostrophe)
    0x1B: "!",  # F in letters (exclamation)
    0x1D: ":",  # C in letters (colon)
    0x1E: "(",  # K in letters (open paren)
    0x47: "-",  # A in letters (dash/minus)
    0x4B: "\a",  # S in letters (bell)
    0x63: '"',  # Z in letters (quote)
    0x65: ")",  # L in letters (close paren)
    0x69: "#",  # H in letters (hash/pound)
    0x39: ".",  # M in letters (period)
    0x3A: "/",  # X in letters (slash)
    0x3C: ";",  # V in letters (semicolon)
    0x35: "&",  # G in letters (ampersand)
    0x59: ",",  # N in letters (comma)
    0x6C: "\n",  # Line feed (same in both)
    0x78: "\r",  # Carriage return (same in both)
    0x5C: " ",  # Space (same in both)
}

# ITA-2 figures table (different from US-TTY)
ITA2_CODE_TO_FIGS = {
    0x2E: "1",  # Q in letters
    0x27: "2",  # W in letters
    0x56: "3",  # E in letters
    0x55: "4",  # R in letters
    0x74: "5",  # T in letters
    0x2B: "6",  # Y in letters
    0x4E: "7",  # U in letters
    0x4D: "8",  # I in letters
    0x71: "9",  # O in letters
    0x2D: "0",  # P in letters
    0x17: "'",  # J in letters (apostrophe)
    0x1B: "!",  # F in letters (exclamation)
    0x1D: ":",  # C in letters (colon)
    0x1E: "(",  # K in letters (open paren)
    0x47: "-",  # A in letters (dash/minus)
    0x4B: "'",  # S in letters (apostrophe in ITA-2)
    0x63: "+",  # Z in letters (plus in ITA-2)
    0x65: ")",  # L in letters (close paren)
    0x69: "#",  # H in letters (hash/pound)
    0x39: ".",  # M in letters (period)
    0x3A: "/",  # X in letters (slash)
    0x3C: "=",  # V in letters (equals in ITA-2)
    0x35: "&",  # G in letters (ampersand)
    0x59: ",",  # N in letters (comma)
    0x6C: "\n",  # Line feed (same in both)
    0x78: "\r",  # Carriage return (same in both)
    0x5C: " ",  # Space (same in both)
}


def check_valid_code(code: int) -> bool:
    """
    Check if a 7-bit code is valid (has exactly 4 bits set).

    Valid CCIR-476 codes have exactly 4 bits set to 1 out of 7 bits.
    This provides error detection capability.

    Args:
        code: 7-bit code value (0-127)

    Returns:
        True if code has exactly 4 bits set, False otherwise

    Example:
        >>> check_valid_code(0x47)  # A = 1000111
        True
        >>> check_valid_code(0x42)  # Invalid
        False
    """
    count = 0
    v = code & 0x7F
    while v != 0:
        count += 1
        v &= v - 1  # Clear least significant bit
    return count == 4


class CCIR476Encoder:
    """
    Encodes ASCII text to CCIR-476 codes for NAVTEX/SITOR-B.

    Handles automatic shift between LETTERS and FIGURES modes.

    Args:
        use_ita2: If True, use ITA-2 figures table; if False, use US-TTY
    """

    def __init__(self, use_ita2: bool = True):
        """Initialize the CCIR-476 encoder."""
        self.use_ita2 = use_ita2
        self.code_to_figs = ITA2_CODE_TO_FIGS if use_ita2 else USTTY_CODE_TO_FIGS
        self.current_mode = LETTERS

        # Build reverse lookup tables for efficient encoding
        self._build_lookup_tables()

    def _build_lookup_tables(self):
        """Build reverse lookup tables: char -> code."""
        self.ltrs_to_code = {}
        self.figs_to_code = {}

        # Map letters
        for code, char in CODE_TO_LTRS.items():
            if char and char not in ["\0", "_"]:
                self.ltrs_to_code[char] = code

        # Map figures
        for code, char in self.code_to_figs.items():
            if char and char not in ["\0", "_"]:
                self.figs_to_code[char] = code

    def encode_char(self, char: str) -> List[int]:
        """
        Encode a single character to CCIR-476 code(s).

        May return multiple codes if a shift is needed.

        Args:
            char: Single ASCII character

        Returns:
            List of 7-bit CCIR-476 codes, including shift codes if needed

        Example:
            >>> enc = CCIR476Encoder()
            >>> enc.encode_char('A')
            [71]  # 0x47
            >>> enc.encode_char('3')
            [54, 86]  # CODE_FIGS, then E code (3 in figures)
        """
        # Convert to uppercase (CCIR-476 is case-insensitive)
        char = char.upper()

        result = []

        # Check if character exists in current mode
        if self.current_mode == LETTERS:
            if char in self.ltrs_to_code:
                # Available in letters mode
                result.append(self.ltrs_to_code[char])
            elif char in self.figs_to_code:
                # Need to shift to figures
                result.append(CODE_FIGS)
                result.append(self.figs_to_code[char])
                self.current_mode = FIGURES
            # else: unknown character, skip
        else:  # FIGURES mode
            if char in self.figs_to_code:
                # Available in figures mode
                result.append(self.figs_to_code[char])
            elif char in self.ltrs_to_code:
                # Need to shift to letters
                result.append(CODE_LTRS)
                result.append(self.ltrs_to_code[char])
                self.current_mode = LETTERS
            # else: unknown character, skip

        return result

    def encode(self, text: str) -> List[int]:
        """
        Encode text string to list of CCIR-476 codes.

        Args:
            text: ASCII text to encode

        Returns:
            List of 7-bit CCIR-476 codes, including shift codes

        Example:
            >>> enc = CCIR476Encoder()
            >>> enc.encode("CQ")
            [29, 46]  # C=0x1D, Q=0x2E
        """
        codes = []

        for char in text:
            char_codes = self.encode_char(char)
            codes.extend(char_codes)

        return codes

    def reset(self):
        """Reset encoder to LETTERS mode."""
        self.current_mode = LETTERS


def encode_ccir476(text: str, use_ita2: bool = True) -> List[int]:
    """
    Convenience function to encode text to CCIR-476.

    Args:
        text: ASCII text to encode
        use_ita2: If True, use ITA-2; if False, use US-TTY

    Returns:
        List of 7-bit CCIR-476 codes

    Example:
        >>> encode_ccir476("HELLO")
        [105, 86, 101, 101, 113]
    """
    encoder = CCIR476Encoder(use_ita2=use_ita2)
    return encoder.encode(text)


def decode_ccir476(codes: List[int], use_ita2: bool = True) -> str:
    """
    Decode CCIR-476 codes to ASCII text.

    Args:
        codes: List of 7-bit CCIR-476 codes
        use_ita2: If True, use ITA-2; if False, use US-TTY

    Returns:
        Decoded ASCII text

    Example:
        >>> decode_ccir476([105, 86, 101, 101, 113])
        'HELLO'
    """
    code_to_figs = ITA2_CODE_TO_FIGS if use_ita2 else USTTY_CODE_TO_FIGS
    mode = LETTERS
    text = []

    for code in codes:
        code = code & 0x7F  # Ensure 7-bit

        if code == CODE_LTRS:
            mode = LETTERS
        elif code == CODE_FIGS:
            mode = FIGURES
        elif code == CODE_ALPHA or code == CODE_BETA or code == CODE_REP:
            # Skip control codes
            continue
        else:
            if mode == LETTERS:
                char = CODE_TO_LTRS.get(code, None)
            else:
                char = code_to_figs.get(code, None)

            if char and char not in ["\0", "_"]:
                text.append(char)

    return "".join(text)


def create_fec_interleaved(codes: List[int]) -> List[int]:
    """
    Create FEC (Forward Error Correction) interleaved code sequence.

    In NAVTEX, each character is transmitted twice for error correction:
    - First transmission (alpha) followed by second transmission (rep)
    - Pattern: rep alpha rep alpha char1 alpha char2 char1 char3 char2 ...
    - Each character is repeated 5 characters (35 bits) later

    This implements the FEC pattern used in SITOR-B.

    Args:
        codes: List of 7-bit CCIR-476 codes to transmit

    Returns:
        FEC-interleaved code sequence with rep/alpha markers

    Example:
        >>> create_fec_interleaved([0x59, 0x47])  # "NA"
        [0x66, 0x0F, 0x66, 0x0F, 0x59, 0x0F, 0x47, 0x59, ...]
    """
    result = []
    offset = 2  # Offset for interleaving (2 characters ahead)

    # Add initial rep/alpha sequence
    for _ in range(offset):
        result.append(CODE_REP)
        result.append(CODE_ALPHA)

    # Interleave characters
    for i, code in enumerate(codes):
        result.append(code)
        if i >= offset:
            result.append(codes[i - offset])
        else:
            result.append(CODE_ALPHA)

    # Add trailing characters
    sz = len(codes)
    for i in range(offset):
        result.append(CODE_CHAR32)  # Space character
        result.append(codes[sz - offset + i])

    return result
