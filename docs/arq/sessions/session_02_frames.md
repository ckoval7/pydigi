# Session 2: Frame Builder/Parser

**Duration**: 2-3 hours
**Priority**: ⭐ CRITICAL - Frame format must be exact
**Prerequisites**: Session 1 (CRC-16) complete
**Status**: ✅ Complete (2025-12-28)

## Goal

Implement ARQ frame building and parsing with CRC validation. Frames must match fldigi's format byte-for-byte for interoperability.

## Frame Structure Review

```
<SOH>[Header(4)][Payload(0-512)][CRC(4)]<EOT|SOH>
```

**Components**:
- `SOH` = 0x01 (Start of Header)
- Header = 4 bytes (version, stream_id, block_type, data)
- Payload = 0-512 bytes (variable)
- CRC = 4 uppercase hex chars (calculated over SOH through last payload byte)
- Terminator = EOT (0x04) for control frames, SOH for data frames

## Deliverables

### 1. Create `pydigi/arq/frame.py`

#### Frame Constants

```python
"""ARQ Frame building and parsing."""

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
```

#### ARQFrame Class

```python
from .crc import CRC16


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

        # Minimum frame: SOH + 4 header + 4 CRC + terminator = 10 bytes
        if len(frame) < 10:
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
```

### 2. Create `tests/test_arq/test_frame.py`

```python
import pytest
from pydigi.arq.frame import (
    ARQFrame, SOH, EOT,
    CONREQ, CONACK, STATUS, DISREQ, DISACK,
    DATA_BLOCK_OFFSET
)


def test_frame_build_conreq():
    """Test building CONREQ frame"""
    payload = "W1ABC:1025 K6XYZ:24 0 7"
    frame = ARQFrame('0', '0', CONREQ, payload)

    frame_bytes = frame.build()

    # Verify starts with SOH
    assert frame_bytes[0] == SOH

    # Verify header
    assert chr(frame_bytes[1]) == '0'  # version
    assert chr(frame_bytes[2]) == '0'  # stream_id
    assert frame_bytes[3] == CONREQ    # block_type

    # Verify ends with EOT (control frame)
    assert frame_bytes[-1] == EOT

    # Verify CRC is 4 chars before terminator
    crc_str = frame_bytes[-5:-1].decode('latin-1')
    assert len(crc_str) == 4
    assert crc_str.isupper()


def test_frame_build_data_block():
    """Test building data block frame"""
    payload = "Hello World"
    block_num = 5
    frame = ARQFrame('0', '1', block_num, payload)

    frame_bytes = frame.build()

    # Verify block type encoding
    assert frame_bytes[3] == block_num + DATA_BLOCK_OFFSET

    # Verify ends with SOH (data frame)
    assert frame_bytes[-1] == SOH


def test_frame_parse_conreq():
    """Test parsing CONREQ frame"""
    # Build a frame first
    payload = "W1ABC:1025 K6XYZ:24 0 7"
    original = ARQFrame('0', '0', CONREQ, payload)
    frame_bytes = original.build()

    # Parse it back
    parsed = ARQFrame.parse(frame_bytes)

    assert parsed.protocol_version == '0'
    assert parsed.stream_id == '0'
    assert parsed.block_type == CONREQ
    assert parsed.payload == payload


def test_frame_parse_data_block():
    """Test parsing data block frame"""
    payload = "Test data"
    block_num = 10
    original = ARQFrame('0', '2', block_num, payload)
    frame_bytes = original.build()

    parsed = ARQFrame.parse(frame_bytes)

    assert parsed.protocol_version == '0'
    assert parsed.stream_id == '2'
    assert parsed.block_type == block_num
    assert parsed.payload == payload


def test_frame_roundtrip():
    """Test build -> parse roundtrip for various frame types"""
    test_frames = [
        ('0', '0', CONREQ, "W1ABC:1025 K6XYZ:24 0 7"),
        ('0', '1', CONACK, "W1ABC:1025 K6XYZ:24 1 7"),
        ('0', '2', STATUS, "\x30\x32\x35"),  # Example STATUS
        ('0', '3', DISREQ, ""),
        ('0', '4', 0, "First block"),
        ('0', '5', 63, "Last block"),
        ('0', '6', 32, "Middle block"),
    ]

    for version, stream, btype, payload in test_frames:
        original = ARQFrame(version, stream, btype, payload)
        frame_bytes = original.build()
        parsed = ARQFrame.parse(frame_bytes)

        assert parsed.protocol_version == version
        assert parsed.stream_id == stream
        assert parsed.block_type == btype
        assert parsed.payload == payload


def test_frame_parse_invalid_crc():
    """Test parsing frame with corrupted CRC"""
    # Build valid frame
    frame = ARQFrame('0', '0', CONREQ, "test")
    frame_bytes = bytearray(frame.build())

    # Corrupt CRC (last 4 chars before terminator)
    frame_bytes[-5] = ord('X')

    # Should raise ValueError
    with pytest.raises(ValueError, match="CRC mismatch"):
        ARQFrame.parse(bytes(frame_bytes))


def test_frame_parse_too_short():
    """Test parsing frame that's too short"""
    short_frame = b"\x01000"  # Only 4 bytes

    with pytest.raises(ValueError, match="too short"):
        ARQFrame.parse(short_frame)


def test_frame_parse_missing_soh():
    """Test parsing frame without SOH"""
    bad_frame = b"X00ctest1234\x04"  # Wrong start char

    with pytest.raises(ValueError, match="Missing SOH"):
        ARQFrame.parse(bad_frame)


def test_frame_empty_payload():
    """Test frame with empty payload"""
    frame = ARQFrame('0', '0', DISREQ, "")
    frame_bytes = frame.build()

    parsed = ARQFrame.parse(frame_bytes)
    assert parsed.payload == ""


def test_frame_max_payload():
    """Test frame with maximum payload size"""
    payload = "X" * 512  # Max size
    frame = ARQFrame('0', '0', 5, payload)
    frame_bytes = frame.build()

    parsed = ARQFrame.parse(frame_bytes)
    assert parsed.payload == payload
    assert len(parsed.payload) == 512


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
```

## Implementation Steps

1. Create `pydigi/arq/frame.py` with constants and `ARQFrame` class
2. Implement `build()` method with proper CRC and terminator
3. Implement `parse()` method with CRC validation
4. Create `tests/test_arq/test_frame.py`
5. Run tests: `pytest tests/test_arq/test_frame.py -v`
6. Test with example CONREQ frame format

## Example Test Frame

**CONREQ Frame**:
```
Input: "W1ABC:1025 K6XYZ:24 0 7"
Frame: SOH + '0' + '0' + 'c' + payload + CRC + EOT
```

Build this frame and verify it can be parsed back correctly.

## Validation Checkpoint

✅ **Session Complete When**:
- [ ] `frame.py` created with all constants
- [ ] `ARQFrame` class implemented
- [ ] `build()` method works for all frame types
- [ ] `parse()` method works with CRC validation
- [ ] All tests pass
- [ ] CONREQ, STATUS, and data frames build/parse correctly
- [ ] CRC validation catches corrupted frames
- [ ] Empty and max-size payloads work

## Common Pitfalls

❌ **Wrong terminator**: Data blocks use SOH, control use EOT
❌ **CRC coverage**: Must include SOH through last payload byte only
❌ **Block type encoding**: Data blocks are `block_num + 0x20`, not raw block_num
❌ **String encoding**: Use `latin-1` to preserve all byte values

## Reference Files

- `fldigi/src/flarq-src/arq.cxx` lines 240-300 (frame building)
- `fldigi/src/flarq-src/arq.cxx` lines 350-450 (frame parsing)

## Next Session

Once complete, proceed to **Session 3: Block Tracking**

See [session_03_blocks.md](session_03_blocks.md)
