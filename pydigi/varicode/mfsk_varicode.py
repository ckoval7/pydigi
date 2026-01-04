"""
MFSK Varicode encoding and decoding.

Based on fldigi's MFSK varicode implementation (fldigi/src/mfsk/mfskvaricode.cxx).
Used by 8PSK, xPSK, and MFSK modes.

The IZ8BLY MFSK Varicode as defined in http://www.qsl.net/zl1bpu/MFSK/Varicode.html

For decoding, this module provides two approaches:
1. Simple string-based decoder: decode_mfsk_varicode()
2. Shift register decoder (matches fldigi): MFSKVaricodeDecoder class
"""

import numpy as np

# MFSK Varicode table (256 entries, indexed by ASCII value 0-255)
# Generated from fldigi/src/mfsk/mfskvaricode.cxx
MFSK_VARICODE = [
    "11101011100",  #   0 - <NUL>
    "11101100000",  #   1 - <SOH>
    "11101101000",  #   2 - <STX>
    "11101101100",  #   3 - <ETX>
    "11101110000",  #   4 - <EOT>
    "11101110100",  #   5 - <ENQ>
    "11101111000",  #   6 - <ACK>
    "11101111100",  #   7 - <BEL>
    "10101000",  #   8 - <BS>
    "11110000000",  #   9 - <TAB>
    "11110100000",  #  10 - <LF>
    "11110101000",  #  11 - <VT>
    "11110101100",  #  12 - <FF>
    "10101100",  #  13 - <CR>
    "11110110000",  #  14 - <SO>
    "11110110100",  #  15 - <SI>
    "11110111000",  #  16 - <DLE>
    "11110111100",  #  17 - <DC1>
    "11111000000",  #  18 - <DC2>
    "11111010000",  #  19 - <DC3>
    "11111010100",  #  20 - <DC4>
    "11111011000",  #  21 - <NAK>
    "11111011100",  #  22 - <SYN>
    "11111100000",  #  23 - <ETB>
    "11111101000",  #  24 - <CAN>
    "11111101100",  #  25 - <EM>
    "11111110000",  #  26 - <SUB>
    "11111110100",  #  27 - <ESC>
    "11111111000",  #  28 - <FS>
    "11111111100",  #  29 - <GS>
    "100000000000",  #  30 - <RS>
    "101000000000",  #  31 - <US>
    "100",  #  32 - <SPC>
    "111000000",  #  33 - !
    "111111100",  #  34 - "
    "1011011000",  #  35 - #
    "1010101000",  #  36 - $
    "1010100000",  #  37 - %
    "1000000000",  #  38 - &
    "110111100",  #  39 - '
    "111110100",  #  40 - (
    "111110000",  #  41 - )
    "1010110100",  #  42 - *
    "111100000",  #  43 - +
    "10100000",  #  44 - ,
    "111011000",  #  45 - -
    "111010100",  #  46 - .
    "111101000",  #  47 - /
    "11100000",  #  48 - 0
    "11110000",  #  49 - 1
    "101000000",  #  50 - 2
    "101010100",  #  51 - 3
    "101110100",  #  52 - 4
    "101100000",  #  53 - 5
    "101101100",  #  54 - 6
    "110100000",  #  55 - 7
    "110000000",  #  56 - 8
    "110101100",  #  57 - 9
    "111101100",  #  58 - :
    "111111000",  #  59 - ;
    "1011000000",  #  60 - <
    "111011100",  #  61 - =
    "1010111100",  #  62 - >
    "111010000",  #  63 - ?
    "1010000000",  #  64 - @
    "10111100",  #  65 - A
    "100000000",  #  66 - B
    "11010100",  #  67 - C
    "11011100",  #  68 - D
    "10111000",  #  69 - E
    "11111000",  #  70 - F
    "101010000",  #  71 - G
    "101011000",  #  72 - H
    "11000000",  #  73 - I
    "110110100",  #  74 - J
    "101111100",  #  75 - K
    "11110100",  #  76 - L
    "11101000",  #  77 - M
    "11111100",  #  78 - N
    "11010000",  #  79 - O
    "11101100",  #  80 - P
    "110110000",  #  81 - Q
    "11011000",  #  82 - R
    "10110100",  #  83 - S
    "10110000",  #  84 - T
    "101011100",  #  85 - U
    "110101000",  #  86 - V
    "101101000",  #  87 - W
    "101110000",  #  88 - X
    "101111000",  #  89 - Y
    "110111000",  #  90 - Z
    "1011101000",  #  91 - [
    "1011010000",  #  92 - \
    "1011101100",  #  93 - ]
    "1011010100",  #  94 - ^
    "1010110000",  #  95 - _
    "1010101100",  #  96 - `
    "10100",  #  97 - a
    "1100000",  #  98 - b
    "111000",  #  99 - c
    "110100",  # 100 - d
    "1000",  # 101 - e
    "1010000",  # 102 - f
    "1011000",  # 103 - g
    "110000",  # 104 - h
    "11000",  # 105 - i
    "10000000",  # 106 - j
    "1110000",  # 107 - k
    "101100",  # 108 - l
    "1000000",  # 109 - m
    "11100",  # 110 - n
    "10000",  # 111 - o
    "1010100",  # 112 - p
    "1111000",  # 113 - q
    "100000",  # 114 - r
    "101000",  # 115 - s
    "1100",  # 116 - t
    "111100",  # 117 - u
    "1101100",  # 118 - v
    "1101000",  # 119 - w
    "1110100",  # 120 - x
    "1011100",  # 121 - y
    "1111100",  # 122 - z
    "1011011100",  # 123 - {
    "1010111000",  # 124 - |
    "1011100000",  # 125 - }
    "1011110000",  # 126 - ~
    "101010000000",  # 127 - <DEL>
    "101010100000",  # 128 - 0x80
    "101010101000",  # 129 - 0x81
    "101010101100",  # 130 - 0x82
    "101010110000",  # 131 - 0x83
    "101010110100",  # 132 - 0x84
    "101010111000",  # 133 - 0x85
    "101010111100",  # 134 - 0x86
    "101011000000",  # 135 - 0x87
    "101011010000",  # 136 - 0x88
    "101011010100",  # 137 - 0x89
    "101011011000",  # 138 - 0x8A
    "101011011100",  # 139 - 0x8B
    "101011100000",  # 140 - 0x8C
    "101011101000",  # 141 - 0x8D
    "101011101100",  # 142 - 0x8E
    "101011110000",  # 143 - 0x8F
    "101011110100",  # 144 - 0x90
    "101011111000",  # 145 - 0x91
    "101011111100",  # 146 - 0x92
    "101100000000",  # 147 - 0x93
    "101101000000",  # 148 - 0x94
    "101101010000",  # 149 - 0x95
    "101101010100",  # 150 - 0x96
    "101101011000",  # 151 - 0x97
    "101101011100",  # 152 - 0x98
    "101101100000",  # 153 - 0x99
    "101101101000",  # 154 - 0x9A
    "101101101100",  # 155 - 0x9B
    "101101110000",  # 156 - 0x9C
    "101101110100",  # 157 - 0x9D
    "101101111000",  # 158 - 0x9E
    "101101111100",  # 159 - 0x9F
    "1011110100",  # 160 - 0xA0
    "1011111000",  # 161 - 0xA1
    "1011111100",  # 162 - 0xA2
    "1100000000",  # 163 - 0xA3
    "1101000000",  # 164 - 0xA4
    "1101010000",  # 165 - 0xA5
    "1101010100",  # 166 - 0xA6
    "1101011000",  # 167 - 0xA7
    "1101011100",  # 168 - 0xA8
    "1101100000",  # 169 - 0xA9
    "1101101000",  # 170 - 0xAA
    "1101101100",  # 171 - 0xAB
    "1101110000",  # 172 - 0xAC
    "1101110100",  # 173 - 0xAD
    "1101111000",  # 174 - 0xAE
    "1101111100",  # 175 - 0xAF
    "1110000000",  # 176 - 0xB0
    "1110100000",  # 177 - 0xB1
    "1110101000",  # 178 - 0xB2
    "1110101100",  # 179 - 0xB3
    "1110110000",  # 180 - 0xB4
    "1110110100",  # 181 - 0xB5
    "1110111000",  # 182 - 0xB6
    "1110111100",  # 183 - 0xB7
    "1111000000",  # 184 - 0xB8
    "1111010000",  # 185 - 0xB9
    "1111010100",  # 186 - 0xBA
    "1111011000",  # 187 - 0xBB
    "1111011100",  # 188 - 0xBC
    "1111100000",  # 189 - 0xBD
    "1111101000",  # 190 - 0xBE
    "1111101100",  # 191 - 0xBF
    "1111110000",  # 192 - 0xC0
    "1111110100",  # 193 - 0xC1
    "1111111000",  # 194 - 0xC2
    "1111111100",  # 195 - 0xC3
    "10000000000",  # 196 - 0xC4
    "10100000000",  # 197 - 0xC5
    "10101000000",  # 198 - 0xC6
    "10101010000",  # 199 - 0xC7
    "10101010100",  # 200 - 0xC8
    "10101011000",  # 201 - 0xC9
    "10101011100",  # 202 - 0xCA
    "10101100000",  # 203 - 0xCB
    "10101101000",  # 204 - 0xCC
    "10101101100",  # 205 - 0xCD
    "10101110000",  # 206 - 0xCE
    "10101110100",  # 207 - 0xCF
    "10101111000",  # 208 - 0xD0
    "10101111100",  # 209 - 0xD1
    "10110000000",  # 210 - 0xD2
    "10110100000",  # 211 - 0xD3
    "10110101000",  # 212 - 0xD4
    "10110101100",  # 213 - 0xD5
    "10110110000",  # 214 - 0xD6
    "10110110100",  # 215 - 0xD7
    "10110111000",  # 216 - 0xD8
    "10110111100",  # 217 - 0xD9
    "10111000000",  # 218 - 0xDA
    "10111010000",  # 219 - 0xDB
    "10111010100",  # 220 - 0xDC
    "10111011000",  # 221 - 0xDD
    "10111011100",  # 222 - 0xDE
    "10111100000",  # 223 - 0xDF
    "10111101000",  # 224 - 0xE0
    "10111101100",  # 225 - 0xE1
    "10111110000",  # 226 - 0xE2
    "10111110100",  # 227 - 0xE3
    "10111111000",  # 228 - 0xE4
    "10111111100",  # 229 - 0xE5
    "11000000000",  # 230 - 0xE6
    "11010000000",  # 231 - 0xE7
    "11010100000",  # 232 - 0xE8
    "11010101000",  # 233 - 0xE9
    "11010101100",  # 234 - 0xEA
    "11010110000",  # 235 - 0xEB
    "11010110100",  # 236 - 0xEC
    "11010111000",  # 237 - 0xED
    "11010111100",  # 238 - 0xEE
    "11011000000",  # 239 - 0xEF
    "11011010000",  # 240 - 0xF0
    "11011010100",  # 241 - 0xF1
    "11011011000",  # 242 - 0xF2
    "11011011100",  # 243 - 0xF3
    "11011100000",  # 244 - 0xF4
    "11011101000",  # 245 - 0xF5
    "11011101100",  # 246 - 0xF6
    "11011110000",  # 247 - 0xF7
    "11011110100",  # 248 - 0xF8
    "11011111000",  # 249 - 0xF9
    "11011111100",  # 250 - 0xFA
    "11100000000",  # 251 - 0xFB
    "11101000000",  # 252 - 0xFC
    "11101010000",  # 253 - 0xFD
    "11101010100",  # 254 - 0xFE
    "11101011000",  # 255 - 0xFF
]


def encode_char(char_code: int) -> str:
    """
    Encode a single character using MFSK varicode.

    Args:
        char_code: ASCII character code (0-255)

    Returns:
        Varicode bit string (e.g., "10111100" for 'A')

    Example:
        >>> encode_char(ord('A'))
        '10111100'
        >>> encode_char(ord('e'))
        '1000'
    """
    if char_code < 0 or char_code > 255:
        char_code = 0  # Return NULL varicode for invalid codes
    return MFSK_VARICODE[char_code]


def encode_text(text: str) -> str:
    """
    Encode text string using MFSK varicode.

    Note: MFSK varicode does NOT use character delimiters like PSK varicode.
    Characters are sent back-to-back.

    Args:
        text: Text string to encode

    Returns:
        Concatenated varicode bit string

    Example:
        >>> encode_text("HI")
        '10101100011000'  # H='101011000' + I='11000'
    """
    result = ""
    for char in text:
        result += encode_char(ord(char))
    return result


def encode_text_to_bits(text: str) -> list:
    """
    Encode text to list of integer bits.

    Args:
        text: Text string to encode

    Returns:
        List of integer bits [0, 1, 0, 1, ...]

    Example:
        >>> encode_text_to_bits("A")
        [1, 0, 1, 1, 1, 1, 0, 0]
    """
    bit_string = encode_text(text)
    return [int(b) for b in bit_string]


def decode_mfsk_varicode(bit_string: str) -> tuple:
    """
    Decode MFSK varicode from bit string.

    Checks if the bit_string starts with a valid varicode.
    Returns (char_code, remaining_bits) if match found, or (None, bit_string) if no match.

    Args:
        bit_string: Bit string to decode (e.g., "10111100100")

    Returns:
        Tuple of (char_code, remaining_bits) where:
        - char_code: ASCII code (0-255) if match found, None otherwise
        - remaining_bits: Remaining bits after removing the matched varicode

    Example:
        >>> decode_mfsk_varicode("10111100100")
        (65, '100')  # Decoded 'A' (10111100), leaving '100'
        >>> decode_mfsk_varicode("100")
        (32, '')  # Decoded ' ' (space), no bits left
    """
    # Try to find a varicode that matches the start of bit_string
    for char_code, varicode in enumerate(MFSK_VARICODE):
        if bit_string.startswith(varicode):
            # Found a match - return character and remaining bits
            remaining = bit_string[len(varicode):]
            return (char_code, remaining)

    # No match found - return None and unchanged bit_string
    return (None, bit_string)


# MFSK Varicode decode table from fldigi (fldigi/src/mfsk/mfskvaricode.cxx)
# Index is character code (0-255), value is the bit pattern as an integer
# This is used by the shift register decoder (MFSKVaricodeDecoder class)
MFSK_VARIDECODE = [
    0x75C, 0x760, 0x768, 0x76C, 0x770, 0x774, 0x778, 0x77C,
    0x0A8, 0x780, 0x7A0, 0x7A8, 0x7AC, 0x0AC, 0x7B0, 0x7B4,
    0x7B8, 0x7BC, 0x7C0, 0x7D0, 0x7D4, 0x7D8, 0x7DC, 0x7E0,
    0x7E8, 0x7EC, 0x7F0, 0x7F4, 0x7F8, 0x7FC, 0x800, 0xA00,
    0x004, 0x1C0, 0x1FC, 0x2D8, 0x2A8, 0x2A0, 0x200, 0x1BC,
    0x1F4, 0x1F0, 0x2B4, 0x1E0, 0x0A0, 0x1D8, 0x1D4, 0x1E8,
    0x0E0, 0x0F0, 0x140, 0x154, 0x174, 0x160, 0x16C, 0x1A0,
    0x180, 0x1AC, 0x1EC, 0x1F8, 0x2C0, 0x1DC, 0x2BC, 0x1D0,
    0x280, 0x0BC, 0x100, 0x0D4, 0x0DC, 0x0B8, 0x0F8, 0x150,
    0x158, 0x0C0, 0x1B4, 0x17C, 0x0F4, 0x0E8, 0x0FC, 0x0D0,
    0x0EC, 0x1B0, 0x0D8, 0x0B4, 0x0B0, 0x15C, 0x1A8, 0x168,
    0x170, 0x178, 0x1B8, 0x2E8, 0x2D0, 0x2EC, 0x2D4, 0x2B0,
    0x2AC, 0x014, 0x060, 0x038, 0x034, 0x008, 0x050, 0x058,
    0x030, 0x018, 0x080, 0x070, 0x02C, 0x040, 0x01C, 0x010,
    0x054, 0x078, 0x020, 0x028, 0x00C, 0x03C, 0x06C, 0x068,
    0x074, 0x05C, 0x07C, 0x2DC, 0x2B8, 0x2E0, 0x2F0, 0xA80,
    0xAA0, 0xAA8, 0xAAC, 0xAB0, 0xAB4, 0xAB8, 0xABC, 0xAC0,
    0xAD0, 0xAD4, 0xAD8, 0xADC, 0xAE0, 0xAE8, 0xAEC, 0xAF0,
    0xAF4, 0xAF8, 0xAFC, 0xB00, 0xB40, 0xB50, 0xB54, 0xB58,
    0xB5C, 0xB60, 0xB68, 0xB6C, 0xB70, 0xB74, 0xB78, 0xB7C,
    0x2F4, 0x2F8, 0x2FC, 0x300, 0x340, 0x350, 0x354, 0x358,
    0x35C, 0x360, 0x368, 0x36C, 0x370, 0x374, 0x378, 0x37C,
    0x380, 0x3A0, 0x3A8, 0x3AC, 0x3B0, 0x3B4, 0x3B8, 0x3BC,
    0x3C0, 0x3D0, 0x3D4, 0x3D8, 0x3DC, 0x3E0, 0x3E8, 0x3EC,
    0x3F0, 0x3F4, 0x3F8, 0x3FC, 0x400, 0x500, 0x540, 0x550,
    0x554, 0x558, 0x55C, 0x560, 0x568, 0x56C, 0x570, 0x574,
    0x578, 0x57C, 0x580, 0x5A0, 0x5A8, 0x5AC, 0x5B0, 0x5B4,
    0x5B8, 0x5BC, 0x5C0, 0x5D0, 0x5D4, 0x5D8, 0x5DC, 0x5E0,
    0x5E8, 0x5EC, 0x5F0, 0x5F4, 0x5F8, 0x5FC, 0x600, 0x680,
    0x6A0, 0x6A8, 0x6AC, 0x6B0, 0x6B4, 0x6B8, 0x6BC, 0x6C0,
    0x6D0, 0x6D4, 0x6D8, 0x6DC, 0x6E0, 0x6E8, 0x6EC, 0x6F0,
    0x6F4, 0x6F8, 0x6FC, 0x700, 0x740, 0x750, 0x754, 0x758,
]


def _strip_leading_bit(value: int) -> int:
    """
    Remove the highest set bit (the marker bit) from a value.

    The shift register starts with value 1 (the marker). As bits are shifted in,
    this marker gets pushed to the MSB. When we decode, we need to strip it.

    Args:
        value: Integer with a leading marker bit

    Returns:
        Integer with the leading bit removed

    Example:
        >>> _strip_leading_bit(12)  # 0b1100 -> 0b100 = 4
        4
        >>> _strip_leading_bit(432)  # 0b110110000 -> 0b10110000 = 176
        176
    """
    if value <= 0:
        return 0
    # Find the highest power of 2 that's <= value
    highest_bit = 1
    while highest_bit * 2 <= value:
        highest_bit *= 2
    return value - highest_bit


def mfsk_varidec(symbol: int) -> int:
    """
    Decode MFSK varicode symbol to character code (fldigi-compatible).

    Args:
        symbol: Integer bit pattern (from shreg >> 1, WITH marker stripped)

    Returns:
        Character code (0-255) if found, -1 otherwise

    Example:
        >>> mfsk_varidec(0x004)  # Space
        32
        >>> mfsk_varidec(0x008)  # 'e'
        101
    """
    for i in range(256):
        if symbol == MFSK_VARIDECODE[i]:
            return i
    return -1


class MFSKVaricodeDecoder:
    """
    MFSK Varicode decoder matching fldigi's implementation.

    This decoder uses a shift register approach that matches fldigi's exact
    implementation. It properly handles the marker bit and "001" trigger pattern.

    Key insights from fldigi/src/psk/psk.cxx and mfskvaricode.cxx:
    1. Bits are shifted into shreg: shreg = (shreg << 1) | bit
    2. After init or each decode, shreg is set to 1 (marker bit)
    3. Decode triggers when (shreg & 7) == 1 (pattern ends with "001")
    4. Character is decoded from (shreg >> 1) with leading marker bit stripped
    5. Varicode patterns always start with "1" and end with "00"
    6. The "001" trigger pattern = end of char "00" + start of next char "1"

    Usage:
        decoder = MFSKVaricodeDecoder()
        for bit in bit_stream:
            char_code = decoder.rx_bit(bit)
            if char_code is not None and char_code > 0:
                print(chr(char_code), end='')
    """

    def __init__(self):
        """Initialize decoder."""
        self.shreg = 1  # Start at 1 (marker bit) per fldigi

    def rx_bit(self, bit: int) -> int:
        """
        Process a single bit and return character code if decoded.

        Args:
            bit: Bit value (0 or 1)

        Returns:
            Character code (0-255) if character decoded, None otherwise

        Note: Character code 0 (NUL) should typically be ignored
        """
        # Shift bit into register (from fldigi)
        self.shreg = (self.shreg << 1) | (1 if bit else 0)

        # Limit shreg size to prevent overflow (keep reasonable number of bits)
        if self.shreg > 0xFFFF:
            self.shreg &= 0xFFFF

        # Check if last 3 bits are "001"
        if (self.shreg & 7) == 1:
            # Decode: strip leading marker bit before lookup
            lookup_value = _strip_leading_bit(self.shreg >> 1)
            c = mfsk_varidec(lookup_value)

            # Reset shift register to 3 (0b11)
            # The trigger bit "1" is also the first bit of the next character
            # Setting shreg = 3 preserves this as: marker(bit 1) + first_data(bit 0)
            self.shreg = 3

            # Return character code (-1 means no match, 0 is NUL)
            if c != -1:
                return c

        return None

    def reset(self):
        """Reset decoder state."""
        self.shreg = 1  # Reset to 1 (marker bit) per fldigi
