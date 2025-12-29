"""CRC-16 calculator for ARQ frames.

Uses standard CRC-16-MODBUS algorithm (polynomial 0xA001, init 0xFFFF)
which matches fldigi's implementation exactly.
"""
import crcmod


class CRC16:
    """
    CRC-16-MODBUS calculator matching fldigi's implementation.

    fldigi uses CRC-16 with polynomial 0xA001 and init 0xFFFF,
    which is the standard CRC-16-MODBUS algorithm.

    Reference: fldigi/src/flarq-src/include/arq.h lines 124-159
    """

    def __init__(self):
        """Initialize CRC calculator."""
        self._crc_func = crcmod.predefined.mkCrcFun('modbus')
        self._buffer = bytearray()

    def reset(self):
        """Reset CRC calculation."""
        self._buffer = bytearray()

    def update(self, byte: int):
        """
        Update CRC with a single byte.

        Args:
            byte: Integer 0-255 to process
        """
        self._buffer.append(byte & 0xFF)

    def value(self) -> int:
        """
        Return current CRC value as integer.

        Returns:
            CRC value as 16-bit integer
        """
        return self._crc_func(bytes(self._buffer))

    def hex_string(self) -> str:
        """
        Return CRC as 4-character uppercase hex string.

        Returns:
            String like "A3F1", "12EF", etc.
        """
        return f"{self.value():04X}"

    def calculate(self, data: str | bytes) -> str:
        """
        Calculate CRC for data and return hex string.

        Args:
            data: String or bytes to calculate CRC for

        Returns:
            4-character uppercase hex string
        """
        if isinstance(data, str):
            data = data.encode('latin-1')
        return f"{self._crc_func(data):04X}"
