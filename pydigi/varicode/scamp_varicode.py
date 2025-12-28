"""
SCAMP 6-bit character encoding.

SCAMP uses a 6-bit character encoding scheme that supports 60 characters
including uppercase letters, digits, and common punctuation. Characters can
be encoded as:
1. 6-bit codes (two per 12-bit codeword)
2. 8-bit raw data (one per 12-bit codeword, marked with 0xF00 prefix)

Based on fldigi implementation in scamp_protocol.cxx
"""

from typing import Optional, List, Tuple


# SCAMP 6-bit character table (60 characters, index 0-59)
# Matches fldigi's scamp_6bit_codesymbols array exactly
SCAMP_CHARSET = [
    "\x00",  # 0: NUL (reserved/unused)
    "\x08",  # 1: Backspace
    "\r",  # 2: Carriage return
    " ",  # 3: Space
    "!",  # 4
    '"',  # 5
    "'",  # 6: Apostrophe (can be interpreted as acute diacritical mark)
    "(",  # 7
    ")",  # 8
    "*",  # 9
    "+",  # 10
    ",",  # 11
    "-",  # 12
    ".",  # 13
    "/",  # 14
    "0",  # 15
    "1",  # 16
    "2",  # 17
    "3",  # 18
    "4",  # 19
    "5",  # 20
    "6",  # 21
    "7",  # 22
    "8",  # 23
    "9",  # 24
    ":",  # 25
    ";",  # 26
    "=",  # 27
    "?",  # 28
    "@",  # 29
    "A",  # 30
    "B",  # 31
    "C",  # 32
    "D",  # 33
    "E",  # 34
    "F",  # 35
    "G",  # 36
    "H",  # 37
    "I",  # 38
    "J",  # 39
    "K",  # 40
    "L",  # 41
    "M",  # 42
    "N",  # 43
    "O",  # 44
    "P",  # 45
    "Q",  # 46
    "R",  # 47
    "S",  # 48
    "T",  # 49
    "U",  # 50
    "V",  # 51
    "W",  # 52
    "X",  # 53
    "Y",  # 54
    "Z",  # 55
    "\\",  # 56: Backslash (can be interpreted as diaeresis/umlaut)
    "^",  # 57
    "`",  # 58
    "~",  # 59
]


def char_to_code(char: str) -> Optional[int]:
    """
    Convert a character to its 6-bit SCAMP code.

    Performs automatic conversions:
    - Lowercase letters -> uppercase
    - Newline (\\n) -> carriage return (\\r)
    - DEL (127) -> backspace (\\b)

    Args:
        char: Single character to encode

    Returns:
        6-bit code (1-59), or None if character is not in SCAMP charset

    Example:
        >>> char_to_code('A')
        31
        >>> char_to_code('a')  # Lowercase converted to uppercase
        31
        >>> char_to_code('0')
        16
        >>> char_to_code('\\x7f')  # Invalid character
        None
    """
    if not char or len(char) != 1:
        return None

    c = char

    # Automatic conversions (matching fldigi behavior)
    if "a" <= c <= "z":
        c = c.upper()
    elif c == "\n":
        c = "\r"
    elif c == "\x7f":  # DEL -> backspace
        c = "\x08"

    # Search for character in table (skip index 0 which is reserved)
    for i in range(1, len(SCAMP_CHARSET)):
        if SCAMP_CHARSET[i] == c:
            return i

    return None


def code_to_char(code: int) -> Optional[str]:
    """
    Convert a 6-bit SCAMP code to its character.

    Args:
        code: 6-bit code (0-59)

    Returns:
        Character, or None if code is invalid (0 or >= 60)

    Example:
        >>> code_to_char(31)
        'A'
        >>> code_to_char(16)
        '0'
        >>> code_to_char(0)  # Reserved/invalid
        None
    """
    if code == 0 or code >= len(SCAMP_CHARSET):
        return None
    return SCAMP_CHARSET[code]


def encode_char(char: str) -> int:
    """
    Encode a single character to a 12-bit codeword.

    Characters in the SCAMP charset are encoded as 6-bit codes in the lower
    6 bits of the codeword (bits 5-0), with upper 6 bits (bits 11-6) set to 0.
    This allows two characters to be packed into one codeword.

    Characters NOT in the SCAMP charset are encoded as 8-bit raw data with
    a 0xF00 prefix (bits 11-8 = 0xF, bits 7-0 = ASCII value).

    Args:
        char: Single character to encode

    Returns:
        12-bit codeword (0x000 to 0xFFF)

    Example:
        >>> hex(encode_char('A'))
        '0x1f'  # 6-bit code 31
        >>> hex(encode_char('\\x01'))  # Not in charset
        '0xf01'  # Raw 8-bit: 0xF00 | 0x01
    """
    if not char or len(char) != 1:
        return 0

    # Try to find in 6-bit charset
    code = char_to_code(char)
    if code is not None:
        return code & 0x3F

    # Fall back to 8-bit raw encoding
    return (0xF00 | ord(char)) & 0xFFF


def pack_two_chars(char1: str, char2: Optional[str] = None) -> int:
    """
    Pack one or two characters into a 12-bit codeword.

    If both characters are in the SCAMP charset (have 6-bit codes), they are
    packed together:
    - Bits 11-6: First character's 6-bit code
    - Bits 5-0:  Second character's 6-bit code

    If either character is not in the charset, they are encoded separately
    as 8-bit raw data (one codeword each).

    Args:
        char1: First character
        char2: Optional second character

    Returns:
        12-bit codeword, or list of codewords if raw encoding needed

    Example:
        >>> hex(pack_two_chars('A', 'B'))
        '0x7e0'  # (31 << 6) | 32 = 0x7E0
        >>> pack_two_chars('A')
        [0x1f]  # Just first character
        >>> pack_two_chars('\\x01', 'A')
        [0xf01, 0x1f]  # Raw + 6-bit
    """
    if not char1:
        return 0

    code1 = char_to_code(char1)

    # If no second character, just encode the first
    if char2 is None or len(char2) == 0:
        if code1 is not None:
            return code1 & 0x3F
        else:
            # Raw 8-bit encoding
            return 0xF00 | ord(char1)

    code2 = char_to_code(char2)

    # If both characters have 6-bit codes, pack them together
    # fldigi packing: first char in LOW bits, second char in HIGH bits
    if code1 is not None and code2 is not None:
        return ((code2 & 0x3F) << 6) | (code1 & 0x3F)

    # Otherwise, they need to be encoded separately as raw bytes
    # Return as a list
    codewords = []
    if code1 is not None:
        codewords.append(code1 & 0x3F)
    else:
        codewords.append(0xF00 | ord(char1))

    if code2 is not None:
        codewords.append(code2 & 0x3F)
    else:
        codewords.append(0xF00 | ord(char2))

    return codewords


def text_to_codewords(text: str) -> List[int]:
    """
    Encode text string to a list of 12-bit SCAMP codewords.

    Processes the text two characters at a time when possible, packing
    two 6-bit characters into single codewords for efficiency.

    Args:
        text: Text string to encode

    Returns:
        List of 12-bit codewords (0x000 to 0xFFF)

    Example:
        >>> codewords = text_to_codewords("HELLO")
        >>> [hex(c) for c in codewords]
        ['0x9d5', '0x3cf', '0x3c3']  # Packed pairs: HE, LL, O
    """
    if not text:
        return []

    codewords = []
    i = 0

    while i < len(text):
        char1 = text[i]
        char2 = text[i + 1] if i + 1 < len(text) else None

        code1 = char_to_code(char1)

        if char2 is not None:
            code2 = char_to_code(char2)

            # If both are 6-bit encodable, pack them together
            # fldigi packing: first char in LOW bits, second char in HIGH bits
            if code1 is not None and code2 is not None:
                codeword = ((code2 & 0x3F) << 6) | (code1 & 0x3F)
                codewords.append(codeword)
                i += 2  # Consumed both characters
                continue

        # Otherwise encode first character alone
        if code1 is not None:
            codewords.append(code1 & 0x3F)
        else:
            # Raw 8-bit encoding
            codewords.append(0xF00 | ord(char1))

        i += 1  # Consumed one character

    return codewords


def codeword_to_chars(codeword: int) -> List[str]:
    """
    Decode a 12-bit codeword to characters.

    Codewords can contain:
    - Raw 8-bit data (bits 11-8 = 0xF): Returns single 8-bit character
    - Two 6-bit characters: Returns two characters
    - One 6-bit character: Returns single character

    Args:
        codeword: 12-bit codeword (0x000 to 0xFFF)

    Returns:
        List of decoded characters (0, 1, or 2 characters)

    Example:
        >>> codeword_to_chars(0x7E0)  # Two 6-bit codes
        ['A', 'B']
        >>> codeword_to_chars(0xF41)  # Raw 8-bit
        ['A']
        >>> codeword_to_chars(0x1F)   # Single 6-bit
        ['A']
    """
    codeword = codeword & 0xFFF
    chars = []

    # Check if this is raw 8-bit data (bits 11-8 = 0xF)
    if (codeword & 0x0F00) == 0x0F00:
        byte_val = codeword & 0xFF
        chars.append(chr(byte_val))
        return chars

    # Extract lower 6-bit code (bits 5-0)
    code_low = codeword & 0x3F
    if code_low > 0:
        char = code_to_char(code_low)
        if char is not None:
            chars.append(char)

    # Extract upper 6-bit code (bits 11-6)
    code_high = (codeword >> 6) & 0x3F
    if code_high > 0:
        char = code_to_char(code_high)
        if char is not None:
            chars.append(char)

    return chars


def codewords_to_text(codewords: List[int]) -> str:
    """
    Decode a list of 12-bit codewords to text string.

    Args:
        codewords: List of 12-bit codewords

    Returns:
        Decoded text string

    Example:
        >>> codewords_to_text([0x9D5, 0x3CF, 0x3C3])
        'HELLO'
    """
    text = []

    for codeword in codewords:
        chars = codeword_to_chars(codeword)
        text.extend(chars)

    return "".join(text)


# Special codeword markers
def is_data_code(codeword: int) -> bool:
    """Check if codeword is raw 8-bit data (bits 11-8 = 0xF)."""
    return (codeword & 0x0F00) == 0x0F00


def is_reserved_code(codeword: int) -> bool:
    """Check if codeword is a reserved/special code."""
    return (codeword & 0x03C) == 0x03C and not is_data_code(codeword)
