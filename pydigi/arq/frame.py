"""ARQ Frame building and parsing."""

from .crc import CRC16

# Control characters (from fldigi arq.h)
SOH = 0x01  # Start of Header
STX = 0x02  # Start of Text
EOT = 0x04  # End of Transmission
SUB = 0x1A  # Substitute

# Block types - Control frames (K9PS standard)
IDENT = ord('i')    # 0x69 - Identification
CONREQ = ord('c')   # 0x63 - Connection Request
CONACK = ord('k')   # 0x6B - Connection Acknowledge
REFUSED = ord('r')  # 0x72 - Connection Refused
DISREQ = ord('d')   # 0x64 - Disconnection Request
STATUS = ord('s')   # 0x73 - Status report
POLL = ord('p')     # 0x70 - Poll status

# Extended block types (FLARQ extensions)
ABORT = ord('a')     # 0x61 - Abort transfer
ACKABORT = ord('o')  # 0x6F - Acknowledge abort
DISACK = ord('b')    # 0x62 - Disconnect acknowledge
UNPROTO = ord('u')   # 0x75 - Unprotocolled
TALK = ord('t')      # 0x74 - Keyboard text

# Data block encoding
# Block numbers 0-63 are encoded as block_num + 0x20 (0x20-0x3F)
DATA_BLOCK_OFFSET = 0x20


class ARQFrame:
    """
    Represents a single ARQ frame.

    Frame structure: <SOH>[Header(4)][Payload(0-512)][CRC(4)]<EOT|SOH>
    """

    def __init__(
        self,
        protocol_version: str = '0',
        stream_id: str = '0',
        block_type: int = None,
        payload: str = ''
    ):
        """
        Initialize ARQ frame.

        Args:
            protocol_version: Protocol version character (default '0')
            stream_id: Stream ID character '0'-'9', 'A'-'Z' (default '0')
            block_type: Block type (int): CONREQ, STATUS, or block_num for data
            payload: Frame payload (0-512 chars)
        """
        self.protocol_version = protocol_version
        self.stream_id = stream_id
        self.block_type = block_type
        self.payload = payload

    def build(self) -> bytes:
        """
        Build complete frame with CRC.

        Returns:
            Complete frame as bytes, ready for modulation
        """
        # Build header: SOH + version + stream_id + block_type_char
        header = chr(SOH) + self.protocol_version + self.stream_id

        # Encode block type
        if isinstance(self.block_type, int):
            if self.block_type < 64:  # Data block (0-63)
                header += chr(self.block_type + DATA_BLOCK_OFFSET)
            else:  # Control block type
                header += chr(self.block_type)
        else:
            raise ValueError(f"Invalid block_type: {self.block_type}")

        # Build frame without CRC and terminator
        frame_without_crc = header + self.payload

        # Calculate CRC over SOH through last payload byte
        crc = CRC16()
        crc_value = crc.calculate(frame_without_crc)

        # Determine terminator (data blocks use SOH, control use EOT)
        if self.block_type < 64:  # Data block
            terminator = chr(SOH)
        else:  # Control block
            terminator = chr(EOT)

        # Complete frame
        complete_frame = frame_without_crc + crc_value + terminator

        return complete_frame.encode('latin-1')

    @staticmethod
    def parse(frame_bytes: bytes) -> 'ARQFrame':
        """
        Parse received frame and validate CRC.

        Args:
            frame_bytes: Complete frame as bytes

        Returns:
            Parsed ARQFrame object

        Raises:
            ValueError: If frame format invalid or CRC mismatch
        """
        # Decode from latin-1 (preserves all byte values)
        try:
            frame = frame_bytes.decode('latin-1')
        except UnicodeDecodeError as e:
            raise ValueError(f"Frame decode error: {e}")

        # Minimum frame: SOH + 3 header bytes + 4 CRC + terminator = 9 bytes
        if len(frame) < 9:
            raise ValueError(f"Frame too short: {len(frame)} bytes")

        # Verify SOH at start
        if ord(frame[0]) != SOH:
            raise ValueError(f"Missing SOH, got: 0x{ord(frame[0]):02X}")

        # Verify terminator (EOT or SOH)
        terminator = ord(frame[-1])
        if terminator not in (EOT, SOH):
            raise ValueError(f"Invalid terminator: 0x{terminator:02X}")

        # Extract header components
        protocol_version = frame[1]
        stream_id = frame[2]
        block_type_char = ord(frame[3])

        # Extract CRC (last 4 chars before terminator)
        received_crc = frame[-5:-1]

        # Frame data is everything except CRC and terminator
        frame_data = frame[:-5]

        # Calculate expected CRC
        crc = CRC16()
        calculated_crc = crc.calculate(frame_data)

        # Validate CRC
        if calculated_crc != received_crc:
            raise ValueError(
                f"CRC mismatch: received {received_crc}, "
                f"calculated {calculated_crc}"
            )

        # Decode block type
        if block_type_char >= DATA_BLOCK_OFFSET and block_type_char < DATA_BLOCK_OFFSET + 64:
            # Data block
            block_type = block_type_char - DATA_BLOCK_OFFSET
        else:
            # Control block
            block_type = block_type_char

        # Extract payload (everything after 4-byte header)
        payload = frame_data[4:]

        return ARQFrame(protocol_version, stream_id, block_type, payload)

    def __repr__(self):
        """String representation for debugging"""
        block_type_name = self._get_block_type_name()
        return (
            f"ARQFrame(v={self.protocol_version}, "
            f"stream={self.stream_id}, "
            f"type={block_type_name}, "
            f"payload_len={len(self.payload)})"
        )

    def _get_block_type_name(self) -> str:
        """Get human-readable block type name"""
        type_map = {
            CONREQ: 'CONREQ',
            CONACK: 'CONACK',
            STATUS: 'STATUS',
            DISREQ: 'DISREQ',
            DISACK: 'DISACK',
            IDENT: 'IDENT',
            POLL: 'POLL',
            ABORT: 'ABORT',
            ACKABORT: 'ACKABORT',
            UNPROTO: 'UNPROTO',
            TALK: 'TALK',
        }
        if self.block_type in type_map:
            return type_map[self.block_type]
        elif self.block_type < 64:
            return f'DATA[{self.block_type}]'
        else:
            return f'UNKNOWN[{self.block_type}]'
