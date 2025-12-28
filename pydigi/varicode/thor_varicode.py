"""
Thor Varicode Encoder/Decoder

Thor varicode is an extended set of the IZ8BLY MFSK varicode that uses
12-bit codes for a secondary character set (ASCII 32-122).

Primary character set uses standard MFSK varicode (same as used in MFSK and 8PSK modes).
Secondary character set uses 12-bit extended codes for printable ASCII characters.

Reference: fldigi/src/thor/thorvaricode.cxx
"""

from pydigi.varicode.mfsk_varicode import encode_text as mfsk_encode_text

# Thor varicode table for secondary characters (ASCII 32-122: space through 'z')
# These are 12-bit codes that extend the MFSK varicode
_THOR_SECONDARY_VARICODE = {
    ord(" "): "101110000000",  # 032 - <SPC>
    ord("!"): "101110100000",  # 033 - !
    ord('"'): "101110101000",  # 034 - "
    ord("#"): "101110101100",  # 035 - #
    ord("$"): "101110110000",  # 036 - $
    ord("%"): "101110110100",  # 037 - %
    ord("&"): "101110111000",  # 038 - &
    ord("'"): "101110111100",  # 039 - '
    ord("("): "101111000000",  # 040 - (
    ord(")"): "101111010000",  # 041 - )
    ord("*"): "101111010100",  # 042 - *
    ord("+"): "101111011000",  # 043 - +
    ord(","): "101111011100",  # 044 - ,
    ord("-"): "101111100000",  # 045 - -
    ord("."): "101111101000",  # 046 - .
    ord("/"): "101111101100",  # 047 - /
    ord("0"): "101111110000",  # 048 - 0
    ord("1"): "101111110100",  # 049 - 1
    ord("2"): "101111111000",  # 050 - 2
    ord("3"): "101111111100",  # 051 - 3
    ord("4"): "110000000000",  # 052 - 4
    ord("5"): "110100000000",  # 053 - 5
    ord("6"): "110101000000",  # 054 - 6
    ord("7"): "110101010100",  # 055 - 7
    ord("8"): "110101011000",  # 056 - 8
    ord("9"): "110101011100",  # 057 - 9
    ord(":"): "110101100000",  # 058 - :
    ord(";"): "110101101000",  # 059 - ;
    ord("<"): "110101101100",  # 060 - <
    ord("="): "110101110000",  # 061 - =
    ord(">"): "110101110100",  # 062 - >
    ord("?"): "110101111000",  # 063 - ?
    ord("@"): "110101111100",  # 064 - @
    ord("A"): "110110000000",  # 065 - A
    ord("B"): "110110100000",  # 066 - B
    ord("C"): "110110101000",  # 067 - C
    ord("D"): "110110101100",  # 068 - D
    ord("E"): "110110110000",  # 069 - E
    ord("F"): "110110110100",  # 070 - F
    ord("G"): "110110111000",  # 071 - G
    ord("H"): "110110111100",  # 072 - H
    ord("I"): "110111000000",  # 073 - I
    ord("J"): "110111010000",  # 074 - J
    ord("K"): "110111010100",  # 075 - K
    ord("L"): "110111011000",  # 076 - L
    ord("M"): "110111011100",  # 077 - M
    ord("N"): "110111100000",  # 078 - N
    ord("O"): "110111101000",  # 079 - O
    ord("P"): "110111101100",  # 080 - P
    ord("Q"): "110111110000",  # 081 - Q
    ord("R"): "110111110100",  # 082 - R
    ord("S"): "110111111000",  # 083 - S
    ord("T"): "110111111100",  # 084 - T
    ord("U"): "111000000000",  # 085 - U
    ord("V"): "111010000000",  # 086 - V
    ord("W"): "111010100000",  # 087 - W
    ord("X"): "111010101100",  # 088 - X
    ord("Y"): "111010110000",  # 089 - Y
    ord("Z"): "111010110100",  # 090 - Z
    ord("["): "111010111000",  # 091 - [
    ord("\\"): "111010111100",  # 092 - \
    ord("]"): "111011000000",  # 093 - ]
    ord("^"): "111011010000",  # 094 - ^
    ord("_"): "111011010100",  # 095 - _
    ord("`"): "111011011000",  # 096 - `
    ord("a"): "111011011100",  # 097 - a
    ord("b"): "111011100000",  # 098 - b
    ord("c"): "111011101000",  # 099 - c
    ord("d"): "111011101100",  # 100 - d
    ord("e"): "111011110000",  # 101 - e
    ord("f"): "111011110100",  # 102 - f
    ord("g"): "111011111000",  # 103 - g
    ord("h"): "111011111100",  # 104 - h
    ord("i"): "111100000000",  # 105 - i
    ord("j"): "111101000000",  # 106 - j
    ord("k"): "111101010000",  # 107 - k
    ord("l"): "111101010100",  # 108 - l
    ord("m"): "111101011000",  # 109 - m
    ord("n"): "111101011100",  # 110 - n
    ord("o"): "111101100000",  # 111 - o
    ord("p"): "111101101000",  # 112 - p
    ord("q"): "111101101100",  # 113 - q
    ord("r"): "111101110000",  # 114 - r
    ord("s"): "111101110100",  # 115 - s
    ord("t"): "111101111000",  # 116 - t
    ord("u"): "111101111100",  # 117 - u
    ord("v"): "111110000000",  # 118 - v
    ord("w"): "111110100000",  # 119 - w
    ord("x"): "111110101000",  # 120 - x
    ord("y"): "111110101100",  # 121 - y
    ord("z"): "111110110000",  # 122 - z
}


def thor_varicode_encode(text: str, secondary: bool = False) -> str:
    """
    Encode text using Thor varicode.

    Thor uses two character sets:
    - Primary: Standard MFSK varicode (for most characters)
    - Secondary: Extended 12-bit codes (for printable ASCII)

    Args:
        text: String to encode
        secondary: If True, use secondary character set (12-bit codes)
                  If False, use primary character set (MFSK varicode)

    Returns:
        String of '0' and '1' characters representing the encoded bits

    Reference: fldigi/src/thor/thorvaricode.cxx - thorvarienc()
    """
    if not isinstance(text, str):
        text = str(text)

    bits = ""

    for char in text:
        code = ord(char)

        if secondary:
            # Use secondary character set (12-bit codes)
            if code in _THOR_SECONDARY_VARICODE:
                bits += _THOR_SECONDARY_VARICODE[code]
            else:
                # Character not in secondary set, fall back to NUL (primary)
                bits += mfsk_encode_text("\x00")
        else:
            # Use primary character set (MFSK varicode)
            bits += mfsk_encode_text(char)

    return bits


def thor_encode_char(char: str, secondary: bool = False) -> str:
    """
    Encode a single character using Thor varicode.

    Args:
        char: Single character to encode
        secondary: If True, use secondary character set

    Returns:
        String of '0' and '1' characters

    Reference: fldigi/src/thor/thor.cxx - sendchar()
    """
    if isinstance(char, int):
        char = chr(char)

    return thor_varicode_encode(char, secondary)
