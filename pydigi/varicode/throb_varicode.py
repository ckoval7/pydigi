"""
Throb Varicode Encoder

This module provides character encoding for Throb and ThrobX digital modes.
Throb uses dual-tone modulation where each character is represented by two
simultaneous tones selected from a set of 9 (Throb) or 11 (ThrobX) tones.

Reference: fldigi/src/throb/throb.cxx

Key Features:
- Throb: 45 characters using 9 tones (dual-tone pairs)
- ThrobX: 55 characters using 11 tones (dual-tone pairs)
- Regular Throb uses shift codes for special characters (?, @, -, \\n)
- ThrobX uses alternating idle/space symbols
"""

# Throb character set (45 characters)
# Reference: throb.cxx lines 835-881
THROB_CHARSET = [
    '\0',  # idle
    'A', 'B', 'C', 'D',
    '\0',  # shift
    'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O', 'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z',
    '1', '2', '3', '4', '5', '6', '7', '8', '9', '0',
    ',', '.', '\'', '/', ')', '(',
    'E',
    ' '
]

# ThrobX character set (55 characters)
# Reference: throb.cxx lines 883-939
THROBX_CHARSET = [
    '\0',  # idle (initially)
    ' ',   # space (initially)
    'A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O', 'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z',
    '1', '2', '3', '4', '5', '6', '7', '8', '9', '0',
    ',', '.', '\'', '/', ')', '(',
    '#', '"', '+', '-', ';', ':', '?', '!', '@', '=',
    '\n'
]

# Throb tone pairs (45 pairs for 9 tones)
# Each character is encoded as two tones (1-indexed in fldigi, 0-indexed here after -1)
# Reference: throb.cxx lines 729-775
THROB_TONE_PAIRS = [
    (4, 4),   # idle (tone 5, 5 in fldigi)
    (3, 4),   # A
    (0, 1),   # B
    (0, 2),   # C
    (0, 3),   # D
    (3, 5),   # SHIFT (was E)
    (0, 4),   # F
    (0, 5),   # G
    (0, 6),   # H
    (2, 6),   # I
    (0, 7),   # J
    (1, 2),   # K
    (1, 3),   # L
    (1, 7),   # M
    (1, 4),   # N
    (4, 5),   # O
    (1, 5),   # P
    (1, 8),   # Q
    (2, 3),   # R
    (2, 4),   # S
    (0, 8),   # T
    (2, 5),   # U
    (7, 8),   # V
    (2, 7),   # W
    (2, 2),   # X
    (1, 1),   # Y
    (0, 0),   # Z
    (2, 8),   # 1
    (3, 6),   # 2
    (3, 7),   # 3
    (3, 8),   # 4
    (4, 6),   # 5
    (4, 7),   # 6
    (4, 8),   # 7
    (5, 6),   # 8
    (5, 7),   # 9
    (5, 8),   # 0
    (6, 7),   # ,
    (6, 8),   # .
    (7, 7),   # '
    (6, 6),   # /
    (5, 5),   # )
    (3, 3),   # (
    (8, 8),   # E
    (1, 6),   # space
]

# ThrobX tone pairs (55 pairs for 11 tones)
# Reference: throb.cxx lines 777-833
THROBX_TONE_PAIRS = [
    (5, 10),   # idle (initially)
    (0, 5),    # space (initially)
    (1, 5),    # A
    (1, 4),    # B
    (1, 6),    # C
    (1, 7),    # D
    (4, 5),    # E
    (1, 8),    # F
    (1, 9),    # G
    (3, 7),    # H
    (3, 5),    # I
    (1, 10),   # J
    (2, 3),    # K
    (2, 4),    # L
    (2, 5),    # M
    (5, 8),    # N
    (5, 9),    # O
    (2, 6),    # P
    (2, 7),    # Q
    (2, 8),    # R
    (5, 7),    # S
    (5, 6),    # T
    (2, 9),    # U
    (2, 10),   # V
    (3, 4),    # W
    (3, 6),    # X
    (3, 8),    # Y
    (3, 9),    # Z
    (0, 1),    # 1
    (0, 2),    # 2
    (0, 3),    # 3
    (0, 4),    # 4
    (0, 6),    # 5
    (0, 7),    # 6
    (0, 8),    # 7
    (0, 9),    # 8
    (1, 2),    # 9
    (1, 3),    # 0
    (3, 10),   # ,
    (4, 6),    # .
    (4, 7),    # '
    (4, 8),    # /
    (4, 9),    # )
    (4, 10),   # (
    (6, 7),    # #
    (6, 8),    # "
    (6, 9),    # +
    (6, 10),   # -
    (7, 8),    # ;
    (7, 9),    # :
    (7, 10),   # ?
    (8, 9),    # !
    (8, 10),   # @
    (9, 10),   # =
    (0, 10),   # \\n (NONSTANDARD)
]


class ThrobEncoder:
    """
    Encoder for Throb varicode.

    Converts text characters to symbol indices for Throb transmission.
    Regular Throb uses shift codes for special characters (?, @, -, \\n).

    Reference: fldigi/src/throb/throb.cxx tx_process() lines 619-721
    """

    def __init__(self):
        # Build reverse lookup tables
        self.throb_lookup = {}
        for i, char in enumerate(THROB_CHARSET):
            if char != '\0':  # Don't map null characters
                self.throb_lookup[char] = i

        # Handle special shifted characters for Throb
        # Reference: throb.cxx lines 653-678
        self.throb_special = {
            '?': (5, 20),   # shift, then symbol 20 (tone pair 1,9)
            '@': (5, 13),   # shift, then symbol 13 (tone pair 2,8)
            '-': (5, 9),    # shift, then symbol 9 (tone pair 1,7)
            '\n': (5, 0),   # shift, then symbol 0 (tone pair 5,5)
        }

    def encode_throb(self, text):
        """
        Encode text for Throb transmission.

        Args:
            text: String to encode

        Returns:
            List of symbol indices

        Reference: fldigi/src/throb/throb.cxx tx_process()
        """
        symbols = []

        for char in text:
            # Skip carriage returns (line 672)
            if char == '\r':
                continue

            # Handle special shifted characters
            if char in self.throb_special:
                shift_sym, char_sym = self.throb_special[char]
                symbols.append(shift_sym)
                symbols.append(char_sym)
                continue

            # Convert to uppercase (line 690)
            if char.islower():
                char = char.upper()

            # Look up character in charset
            if char in self.throb_lookup:
                symbols.append(self.throb_lookup[char])
            else:
                # Unknown characters become spaces (line 710)
                symbols.append(44)  # space symbol

        return symbols


class ThrobXEncoder:
    """
    Encoder for ThrobX varicode.

    Converts text characters to symbol indices for ThrobX transmission.
    ThrobX has a larger character set and uses alternating idle/space symbols.

    Reference: fldigi/src/throb/throb.cxx tx_process() lines 619-721
    """

    def __init__(self):
        # Build reverse lookup table
        self.throbx_lookup = {}
        for i, char in enumerate(THROBX_CHARSET):
            if char != '\0':  # Don't map null characters (only idle at index 0)
                self.throbx_lookup[char] = i

    def encode_throbx(self, text):
        """
        Encode text for ThrobX transmission.

        Args:
            text: String to encode

        Returns:
            List of symbol indices

        Reference: fldigi/src/throb/throb.cxx tx_process()
        """
        symbols = []

        for char in text:
            # Skip carriage returns
            if char == '\r':
                continue

            # Convert to uppercase (line 690)
            if char.islower():
                char = char.upper()

            # Look up character in charset
            if char in self.throbx_lookup:
                symbols.append(self.throbx_lookup[char])
            else:
                # Unknown characters become spaces (line 710)
                symbols.append(1)  # space symbol (initially)

        return symbols


def encode_throb(text):
    """
    Convenience function to encode text for Throb.

    Args:
        text: String to encode

    Returns:
        List of symbol indices
    """
    encoder = ThrobEncoder()
    return encoder.encode_throb(text)


def encode_throbx(text):
    """
    Convenience function to encode text for ThrobX.

    Args:
        text: String to encode

    Returns:
        List of symbol indices
    """
    encoder = ThrobXEncoder()
    return encoder.encode_throbx(text)


# Export the tone pair and frequency information
def get_tone_pair(symbol, is_throbx=False):
    """
    Get the tone pair for a given symbol.

    Args:
        symbol: Symbol index (0-44 for Throb, 0-54 for ThrobX)
        is_throbx: True for ThrobX, False for Throb

    Returns:
        Tuple of (tone1, tone2) indices
    """
    if is_throbx:
        if 0 <= symbol < len(THROBX_TONE_PAIRS):
            return THROBX_TONE_PAIRS[symbol]
    else:
        if 0 <= symbol < len(THROB_TONE_PAIRS):
            return THROB_TONE_PAIRS[symbol]

    # Return idle symbol if out of range
    return (4, 4) if not is_throbx else (5, 10)
