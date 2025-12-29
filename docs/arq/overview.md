# FLARQ ARQ Protocol - Architecture Overview

## Module Structure

```
pydigi/arq/
├── __init__.py          # Public API exports
├── crc.py               # CRC-16 calculator (CRITICAL for interop)
├── frame.py             # Frame builder and parser
├── blocks.py            # Block tracking with wrapping logic
├── state_machine.py     # ARQ state machine
├── protocol.py          # Main ARQProtocol class
├── config.py            # Configuration parameters
├── base64_codec.py      # Base64 for binary files
└── exceptions.py        # ARQ-specific exceptions
```

## Component Responsibilities

### CRC-16 Calculator (`crc.py`)
**Status**: Not Implemented
**Priority**: CRITICAL - Must match fldigi exactly!

- Algorithm: CRC-16-MODBUS (standard variant)
- Polynomial: `0xA001`
- Initial value: `0xFFFF`
- Output: 4-character uppercase hex string
- Implementation: Uses `crcmod` library (well-tested, standard)
- Used for all frame integrity checking

**Good News**: fldigi uses standard CRC-16-MODBUS, so we can use the proven `crcmod` library instead of manual implementation.

### Frame Builder/Parser (`frame.py`)
**Status**: Not Implemented
**Priority**: CRITICAL

Handles ARQ frame structure:
```
<SOH>[Header(4)][Payload(0-512)][CRC(4)]<EOT|SOH>
```

**Header (4 bytes)**:
- Byte 0: Protocol version ('0')
- Byte 1: Stream ID ('0'-'9', 'A'-'Z')
- Byte 2: Block type (CONREQ, STATUS, data, etc.)
- Byte 3: Block number or payload start

### Block Tracker (`blocks.py`)
**Status**: Not Implemented
**Priority**: HIGH

Manages block numbering with wrapping at 64:
- Tracks tx/rx blocks
- Calculates missing blocks
- Handles wrap-around arithmetic
- Manages retransmission queues

### State Machine (`state_machine.py`)
**Status**: Not Implemented
**Priority**: MEDIUM

ARQ connection states:
```
DOWN → ARQ_CONNECTING → ARQ_CONNECTED → WAITING/WAITFORACK
  ↑           ↓                  ↓
  └── TIMEDOUT      DISCONNECTING → DOWN
```

### Main Protocol Class (`protocol.py`)
**Status**: Not Implemented
**Priority**: HIGH

The main ARQProtocol class that:
- Wraps any pydigi modem
- Manages connection/disconnection
- Handles text/file transmission
- Implements automatic retransmission
- Runs async main loop

### Configuration (`config.py`)
**Status**: Not Implemented
**Priority**: MEDIUM

Default configuration matching fldigi:
- Block size: 128 bytes (2^7)
- Retry time: 10 seconds
- Retries: 5
- Timeout: 60 seconds
- TX delay: 500 ms
- Loop time: 100 ms

### Base64 Codec (`base64_codec.py`)
**Status**: Not Implemented
**Priority**: MEDIUM

Standard Base64 encoding for binary file transfer.

### Exceptions (`exceptions.py`)
**Status**: Not Implemented
**Priority**: MEDIUM

Custom exceptions:
- ARQError
- ARQTimeout
- ARQRefused
- ARQAbort

## Integration with Modems

ARQ protocol is **transport-agnostic** and wraps any pydigi modem:

```python
# Works with any modem
modem = PSK31()  # or QPSK(), MFSK16(), MT63(), etc.
arq = ARQProtocol(modem, my_call="W1ABC")
```

The ARQ layer:
1. Builds frames with payload text
2. Calls `modem.modulate(frame_text)` to generate audio
3. Returns audio samples to user
4. User feeds decoded bytes back via `arq.receive_bytes()`

## Data Flow

### Transmission Path
```
User Text/File
    ↓
ARQProtocol.send_text() / send_file()
    ↓
Break into blocks (128 bytes each)
    ↓
Build ARQ frames with CRC
    ↓
modem.modulate(frame_text)
    ↓
Audio samples → Sound card / file / GNU Radio
```

### Reception Path
```
Audio → Sound card / file / GNU Radio
    ↓
modem.demodulate() (user's responsibility)
    ↓
Decoded bytes → arq.receive_bytes()
    ↓
Parse frames, validate CRC
    ↓
Track blocks, detect missing
    ↓
Reassemble consecutive blocks
    ↓
Deliver to user via on_receive_text callback
```

## Protocol Operation

### Connection Establishment
1. Station A sends **CONREQ** with callsigns, parameters
2. Station B responds with **CONACK**
3. Both transition to ARQ_CONNECTED state
4. Data transfer can begin

### Data Transfer
1. Sender breaks data into blocks (0-63, wrapping)
2. Sends blocks as data frames
3. Receiver sends **STATUS** frames reporting:
   - Last consecutive block received (GoodHeader)
   - Highest block received (EndHeader)
   - Missing block list
4. Sender retransmits only missing blocks
5. Repeat until all blocks acknowledged

### Disconnection
1. Initiator sends **DISREQ**
2. Remote responds with **DISACK**
3. Both return to DOWN state

## Compatibility Requirements

For interoperability with real FLARQ/fldigi:

✓ **CRC-16**: Must be byte-for-byte identical
✓ **Frame Format**: Exact SOH/EOT structure
✓ **Block Wrapping**: Correct modulo-64 arithmetic
✓ **Timing**: 100ms loop, proper retry timing
✓ **Stream IDs**: '0' for unknown, '1'-'63' for sessions

## Reference Implementation

The fldigi FLARQ source code is available in `fldigi/src/flarq-src/` for reference:

- `include/arq.h` - Class definitions, CRC-16 algorithm
- `arq.cxx` - Core protocol implementation
- `b64.cxx` - Base64 encoding

## Testing Strategy

Each component has unit tests:
- `tests/test_arq/test_crc.py` - CRC validation
- `tests/test_arq/test_frame.py` - Frame building/parsing
- `tests/test_arq/test_blocks.py` - Block tracking
- `tests/test_arq/test_protocol.py` - Integration tests

Integration tests validate complete protocol operation.

Optional: Interoperability tests with real fldigi via audio loopback.
