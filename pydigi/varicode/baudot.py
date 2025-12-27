"""
Baudot (ITA-2 and US-TTY) character encoding for RTTY.

This module provides character encoding tables and conversion functions
for the Baudot/Murray code used in RTTY transmissions.

Baudot is a 5-bit character encoding with two shift states:
- LETTERS mode: Standard alphabet characters
- FIGURES mode: Numbers and punctuation

References:
    - fldigi/src/rtty/rtty.cxx
    - ITA-2 (International Telegraph Alphabet No. 2)
    - US-TTY variant
"""

import numpy as np
from typing import List, Tuple

# Shift state constants (match fldigi's convention)
LETTERS = 0x100  # Bit flag indicating letters mode
FIGURES = 0x200  # Bit flag indicating figures mode

# Letters table (shared by both ITA-2 and US-TTY)
# Index 0-31 maps to Baudot code 0x00-0x1F
BAUDOT_LETTERS = [
    '\0', 'E', '\n', 'A', ' ', 'S', 'I', 'U',
    '\r', 'D', 'R', 'J', 'N', 'F', 'C', 'K',
    'T', 'Z', 'L', 'W', 'H', 'Y', 'P', 'Q',
    'O', 'B', 'G', ' ', 'M', 'X', 'V', ' '
]

# US-TTY figures table
USTTY_FIGURES = [
    '\0', '3', '\n', '-', ' ', '\a', '8', '7',
    '\r', '$', '4', '\'', ',', '!', ':', '(',
    '5', '"', ')', '2', '#', '6', '0', '1',
    '9', '?', '&', ' ', '.', '/', ';', ' '
]

# ITA-2 figures table
ITA2_FIGURES = [
    '\0', '3', '\n', '-', ' ', '\'', '8', '7',
    '\r', ' ', '4', '\a', ',', '!', ':', '(',
    '5', '+', ')', '2', '#', '6', '0', '1',
    '9', '?', '&', ' ', '.', '/', '=', ' '
]

# Special Baudot codes
BAUDOT_LTRS = 0x1F  # Letters shift (code 31)
BAUDOT_FIGS = 0x1B  # Figures shift (code 27)


class BaudotEncoder:
    """
    Encodes ASCII text to Baudot codes.

    Handles automatic shift between LETTERS and FIGURES modes.

    Args:
        use_ita2: If True, use ITA-2 figures table; if False, use US-TTY
    """

    def __init__(self, use_ita2: bool = True):
        """Initialize the Baudot encoder."""
        self.use_ita2 = use_ita2
        self.figures_table = ITA2_FIGURES if use_ita2 else USTTY_FIGURES
        self.current_mode = LETTERS

        # Build reverse lookup tables for efficient encoding
        self._build_lookup_tables()

    def _build_lookup_tables(self):
        """Build reverse lookup tables: char -> (mode, code)."""
        self.char_to_baudot = {}

        # Map letters
        for i, char in enumerate(BAUDOT_LETTERS):
            if char and char not in ['\0', ' ']:
                self.char_to_baudot[char] = (LETTERS, i)

        # Map figures
        for i, char in enumerate(self.figures_table):
            if char and char not in ['\0', ' ', '\n', '\r']:
                # Only map if not already in letters or if it's unique to figures
                if char not in self.char_to_baudot:
                    self.char_to_baudot[char] = (FIGURES, i)

        # Special handling for space (available in both modes)
        self.char_to_baudot[' '] = (LETTERS | FIGURES, 4)

        # Newline and carriage return (available in both modes)
        self.char_to_baudot['\n'] = (LETTERS | FIGURES, 2)
        self.char_to_baudot['\r'] = (LETTERS | FIGURES, 8)

    def encode_char(self, char: str) -> List[Tuple[int, int]]:
        """
        Encode a single character to Baudot code(s).

        May return multiple codes if a shift is needed.

        Args:
            char: Single ASCII character

        Returns:
            List of (mode, code) tuples. Mode is LETTERS or FIGURES,
            code is the 5-bit Baudot code (0-31).

        Example:
            >>> enc = BaudotEncoder()
            >>> enc.encode_char('A')
            [(256, 3)]  # LETTERS mode, code 3
            >>> enc.encode_char('3')
            [(512, 27), (512, 1)]  # Shift to FIGURES, then code 1
        """
        # Convert to uppercase (Baudot is case-insensitive)
        char = char.upper()

        if char not in self.char_to_baudot:
            # Unknown character - skip it
            return []

        mode, code = self.char_to_baudot[char]
        result = []

        # Check if we need to shift modes
        if mode & (LETTERS | FIGURES) == (LETTERS | FIGURES):
            # Character available in both modes - no shift needed
            result.append((self.current_mode, code))
        elif mode != self.current_mode:
            # Need to shift modes
            if mode == LETTERS:
                result.append((LETTERS, BAUDOT_LTRS))
                self.current_mode = LETTERS
            else:
                result.append((FIGURES, BAUDOT_FIGS))
                self.current_mode = FIGURES
            result.append((mode, code))
        else:
            # Already in correct mode
            result.append((mode, code))

        return result

    def encode(self, text: str) -> List[int]:
        """
        Encode text string to list of Baudot codes.

        Args:
            text: ASCII text to encode

        Returns:
            List of 5-bit Baudot codes (0-31), including shift codes

        Example:
            >>> enc = BaudotEncoder()
            >>> enc.encode("CQ")
            [14, 23]  # C=14, Q=23
        """
        codes = []

        for char in text:
            char_codes = self.encode_char(char)
            for mode, code in char_codes:
                codes.append(code)

        return codes

    def reset(self):
        """Reset encoder to LETTERS mode."""
        self.current_mode = LETTERS


def encode_baudot(text: str, use_ita2: bool = True) -> List[int]:
    """
    Convenience function to encode text to Baudot.

    Args:
        text: ASCII text to encode
        use_ita2: If True, use ITA-2; if False, use US-TTY

    Returns:
        List of 5-bit Baudot codes

    Example:
        >>> encode_baudot("HELLO")
        [20, 1, 18, 18, 24]
    """
    encoder = BaudotEncoder(use_ita2=use_ita2)
    return encoder.encode(text)


def decode_baudot(codes: List[int], use_ita2: bool = True) -> str:
    """
    Decode Baudot codes to ASCII text.

    Args:
        codes: List of 5-bit Baudot codes
        use_ita2: If True, use ITA-2; if False, use US-TTY

    Returns:
        Decoded ASCII text

    Example:
        >>> decode_baudot([20, 1, 18, 18, 24])
        'HELLO'
    """
    figures_table = ITA2_FIGURES if use_ita2 else USTTY_FIGURES
    mode = LETTERS
    text = []

    for code in codes:
        if code == BAUDOT_LTRS:
            mode = LETTERS
        elif code == BAUDOT_FIGS:
            mode = FIGURES
        else:
            if mode == LETTERS:
                char = BAUDOT_LETTERS[code & 0x1F]
            else:
                char = figures_table[code & 0x1F]

            if char and char not in ['\0']:
                text.append(char)

    return ''.join(text)
