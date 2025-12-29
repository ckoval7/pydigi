# FLARQ ARQ Protocol - Technical Reference

Based on K9PS ARQ Specification (Revision 0.2, December 2004)

## Frame Structure

### Basic Frame Format
```
<SOH> [Header(4)] [Payload(0-512)] [CRC(4)] <EOT|SOH>
```

**Control Characters**:
- `SOH` = 0x01 (Start of Header)
- `EOT` = 0x04 (End of Transmission)
- `STX` = 0x02 (Start of Text)
- `SUB` = 0x1A (Substitute)

**Terminator**:
- Data frames: terminated with SOH
- Control frames: terminated with EOT

### Header Structure (4 bytes)

| Byte | Field | Value | Description |
|------|-------|-------|-------------|
| 0 | Protocol Version | '0' | Current version identifier |
| 1 | Stream ID | '0'-'63' | Session identifier ('0' = unknown) |
| 2 | Block Type | See below | Frame type identifier |
| 3 | Block Number / Data | Varies | Depends on block type |

### Block Types

#### Control Frames (K9PS Standard)
| Char | Hex | Name | Description |
|------|-----|------|-------------|
| 'i' | 0x69 | IDENT | Identification/watchdog |
| 'c' | 0x63 | CONREQ | Connection Request |
| 'k' | 0x6B | CONACK | Connection Acknowledge |
| 'r' | 0x72 | REFUSED | Connection Refused |
| 'd' | 0x64 | DISREQ | Disconnection Request |
| 's' | 0x73 | STATUS | Status report with missing blocks |
| 'p' | 0x70 | POLL | Poll status request |

#### Extended Frames (FLARQ Extensions)
| Char | Hex | Name | Description |
|------|-----|------|-------------|
| 'a' | 0x61 | ABORT | Abort transfer |
| 'o' | 0x6F | ACKABORT | Acknowledge abort |
| 'b' | 0x62 | DISACK | Disconnect acknowledgment |
| 'u' | 0x75 | UNPROTO | Unprotocolled identification |
| 't' | 0x74 | TALK | Keyboard-to-keyboard text |

#### Data Frames
- Block numbers: 0-63 (wrapping)
- Encoding: `block_number + 0x20` → 0x20-0x3F (space to '?')
- Example: Block 0 → 0x20 (space), Block 63 → 0x3F ('?')

## CRC-16 Algorithm

**CRITICAL**: Must match fldigi exactly for interoperability!

### Parameters
- Algorithm: **CRC-16-MODBUS** (standard variant)
- Polynomial: `0xA001`
- Initial value: `0xFFFF`
- Coverage: From SOH through last payload byte (excludes CRC and terminator)
- Output: 4-character uppercase hexadecimal string

### Implementation

fldigi uses the standard CRC-16-MODBUS algorithm. We use the `crcmod` library:

```python
import crcmod

# Create CRC-16-MODBUS calculator (matches fldigi)
crc_func = crcmod.predefined.mkCrcFun('modbus')

# Calculate CRC
data = b"\x0100cW1ABC:1025 K6XYZ:24 0 7"
crc_value = crc_func(data)
crc_string = f"{crc_value:04X}"  # "13FF"
```

### Manual Algorithm (from fldigi arq.h:137-144)

If needed, the algorithm can be implemented manually:

```python
crcval = 0xFFFF
for byte in data:
    crcval ^= (byte & 0xFF)
    for i in range(8):
        if crcval & 1:
            crcval = (crcval >> 1) ^ 0xA001
        else:
            crcval = crcval >> 1

# Convert to 4-char hex string
crc_string = f"{crcval:04X}"  # e.g., "12EF"
```

### Test Vectors

```python
# Verified against fldigi algorithm:
test_vectors = [
    (b'', 'FFFF'),              # Empty = initial value
    (b'Hello', 'F377'),
    (b'Hello World', 'DAED'),
    (b'\x0100cW1ABC:1025 K6XYZ:24 0 7', '13FF'),  # CONREQ frame header
]
```

## Block Counting System

### Block Number Range
- **MAXCOUNT** = 64
- Block numbers: 0, 1, 2, ..., 63, 0, 1, ... (wraps)
- 6-bit counter

### Header Tracking Variables

Each station maintains three header counters:

| Variable | Description |
|----------|-------------|
| **LastHeader** | Last block number sent |
| **GoodHeader** | Last consecutive block received OK |
| **EndHeader** | Highest block number received (may have gaps) |

### Missing Block Detection

Missing blocks are those between GoodHeader and EndHeader that haven't been received:

```python
missing = []
current = (GoodHeader + 1) % 64
while current != EndHeader:
    if current not in received_blocks:
        missing.append(current)
    current = (current + 1) % 64
```

### Missing Block Encoding (STATUS Frame)

Missing blocks are encoded as ASCII characters by adding 0x20:
```python
missing_list = ''.join(chr(block_num + 0x20) for block_num in missing)
```

Example: Missing blocks [0, 5, 10] → "\x20\x25\x2A"

## Connection Process

### CONREQ Frame (Connection Request)

**Payload Format**:
```
"MYCALL:myport URCALL:urport StreamID BlockLengthChar [TxxxRxxxWxxx]"
```

**Example**:
```
"W1ABC:1025 K6XYZ:24 4 7 T60R5W10"
```

**Fields**:
- `MYCALL:myport` - Calling station's callsign and port
- `URCALL:urport` - Called station's callsign and port
- `StreamID` - '0' for new connection
- `BlockLengthChar` - '0'+exponent (e.g., '7' for 128 bytes = 2^7)
- `TxxxRxxxWxxx` - Optional timing parameters:
  - `Txxx` - Timeout in seconds
  - `Rxxx` - Number of retries
  - `Wxxx` - Wait time between retries

### CONACK Frame (Connection Acknowledge)

**Payload Format**:
```
"MYCALL:myport URCALL:urport StreamID BlockLengthChar"
```

Confirms connection and returns negotiated parameters.

### STATUS Frame

**Payload Format**:
```
[LastHeader][GoodHeader][EndHeader][MissingBlocks...]
```

**Example** (in hex for clarity):
```
Bytes:  [0x30][0x32][0x35][0x21][0x24]
Fields: Last=48 Good=50 End=53 Missing=[1,4]
```

Each field is a single byte (character):
- Headers: ASCII encoding of block number + 0x20
- Missing blocks: Each encoded as block_num + 0x20

### Data Frame

**Payload**: Raw text data (up to block_size bytes)

**Block Type Encoding**: `block_number + 0x20`

**Example**:
```
Block 5 → Block Type = 0x25 ('%')
Payload: "Hello World..."
```

## State Machine

### States

| State | Value | Description |
|-------|-------|-------------|
| DOWN | 0 | Not connected |
| TIMEDOUT | 1 | Connection timed out |
| ABORT | 2 | Transfer aborted |
| ARQ_CONNECTING | 3 | Connection in progress |
| ARQ_CONNECTED | 4 | Connected, ready for data |
| WAITING | 5 | Waiting for remote response |
| WAITFORACK | 6 | Waiting for acknowledgment |
| DISCONNECT | 7 | Disconnection initiated |
| DISCONNECTING | 8 | Disconnection in progress |
| ABORTING | 9 | Abort in progress |
| STOPPED | 10 | Stopped by user |

### State Transitions

```
DOWN --[send CONREQ]--> ARQ_CONNECTING
ARQ_CONNECTING --[receive CONACK]--> ARQ_CONNECTED
ARQ_CONNECTING --[receive REFUSED]--> DOWN
ARQ_CONNECTING --[timeout]--> TIMEDOUT --> DOWN

ARQ_CONNECTED --[send data]--> WAITFORACK
ARQ_CONNECTED --[receive data]--> ARQ_CONNECTED
WAITFORACK --[receive STATUS]--> ARQ_CONNECTED or WAITING

ARQ_CONNECTED --[send DISREQ]--> DISCONNECTING
DISCONNECTING --[receive DISACK]--> DOWN
DISCONNECTING --[timeout]--> DOWN
```

## Timing Parameters

All times in milliseconds unless noted.

### Default Values (from fldigi)

| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| **Block Size Exponent** | 7 | 4-8 | Block size = 2^N bytes |
| **Block Size** | 128 | 16-256 | Actual block size in bytes |
| **Retry Time** | 10000 | 1000-60000 | Time between retry attempts |
| **Retries** | 5 | 1-20 | Max retry attempts |
| **Timeout** | 60000 | 10000-300000 | Total timeout before link DOWN |
| **TX Delay** | 500 | 0-5000 | Delay from RX to TX turnaround |
| **Loop Time** | 100 | - | Main loop period (ARQLOOPTIME) |

### Timing Implementation

Counters are decremented each loop iteration (100ms):

```python
# Convert milliseconds to loop counts
retry_counter = retry_time_ms // 100
timeout_counter = timeout_ms // 100

# Each loop iteration (100ms)
if retry_counter > 0:
    retry_counter -= 1
if timeout_counter > 0:
    timeout_counter -= 1

# Check timeouts
if timeout_counter == 0:
    # Timeout occurred
    handle_timeout()
```

## Stream ID Management

### Stream ID Values
- `'0'` - Unknown/unassigned stream
- `'1'` - `'9'` - Session IDs 1-9
- `'A'` - `'Z'` - Session IDs 10-35
- `'a'` - `'z'` - Session IDs 36-61
- Total: 64 possible concurrent streams (0-63)

### Session Number Calculation

```python
SessionNumber = 1  # Start at 1

def newsession():
    global SessionNumber
    SessionNumber = (SessionNumber + 1) % 64
    if SessionNumber == 0:
        SessionNumber = 1  # Skip 0
    MyStreamID = chr(SessionNumber + ord('0'))
```

## Reference Source Files

From `fldigi/src/flarq-src/`:

- **include/arq.h** (lines 124-159) - CRC-16 class definition
- **arq.cxx** (lines 137-153) - Initialization, default values
- **arq.cxx** (lines 163-209) - Block tracking, wrapping logic
- **arq.cxx** (lines 240-300) - Frame building
- **arq.cxx** (lines 800-850) - Missing block calculation

## ARQ Specification Document

Full protocol specification: `fldigi/aux/ARQ2.pdf` (K9PS ARQ Specification, Revision 0.2)
