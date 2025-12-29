# FLARQ ARQ Protocol - Testing Guide

## Testing Philosophy

For FLARQ to work with real fldigi stations, our implementation must be **byte-for-byte compatible**. Testing strategy focuses on:

1. **Unit tests** - Individual component correctness
2. **Integration tests** - Component interaction
3. **Validation tests** - Compare against fldigi output
4. **Interoperability tests** - Real communication with fldigi

## Test Structure

```
tests/test_arq/
├── __init__.py
├── test_crc.py           # CRC-16 validation
├── test_frame.py         # Frame building/parsing
├── test_blocks.py        # Block tracking
├── test_state_machine.py # State transitions
├── test_protocol.py      # Protocol integration
└── test_interop.py       # fldigi compatibility (optional)
```

## Unit Tests by Component

### CRC-16 Tests (`test_crc.py`)

**Critical**: CRC must match fldigi exactly!

```python
def test_crc_known_values():
    """Test against values from fldigi"""
    # Get these from fldigi source or live testing
    test_vectors = [
        ("", "FFFF"),  # Empty string = initial value
        ("\x01", "????"),  # Get from fldigi
        ("\x01" + "00c", "????"),  # Frame header
    ]
```

**How to Generate Test Vectors**:

1. **From fldigi source**:
   ```bash
   cd fldigi/src/flarq-src
   # Look for test cases in arq.cxx
   grep -n "crc" arq.cxx
   ```

2. **Create simple C++ test program**:
   ```cpp
   #include "arq.h"
   int main() {
       Ccrc16 crc;
       std::string test = "Hello";
       crc.crc16(test);
       std::cout << crc.sval() << std::endl;
   }
   ```

3. **Capture from real FLARQ** (if available):
   - Generate frames with fldigi
   - Capture audio
   - Demodulate and extract CRC values

### Frame Tests (`test_frame.py`)

**Test Coverage**:
- ✅ Build all frame types (CONREQ, STATUS, data)
- ✅ Parse frames correctly
- ✅ CRC validation catches errors
- ✅ Proper terminator selection
- ✅ Empty and max-size payloads
- ✅ Roundtrip (build → parse → verify)

**Example Frame Test**:
```python
def test_conreq_frame_format():
    """Verify CONREQ frame matches fldigi format"""
    payload = "W1ABC:1025 K6XYZ:24 0 7"
    frame = ARQFrame('0', '0', CONREQ, payload)

    frame_bytes = frame.build()

    # Verify structure
    assert frame_bytes[0] == SOH
    assert chr(frame_bytes[1]) == '0'  # version
    assert chr(frame_bytes[2]) == '0'  # stream_id
    assert frame_bytes[3] == ord('c')  # CONREQ
    # Payload starts at byte 4
    # CRC is 4 chars before terminator
    # Terminator is EOT for control frames
```

### Block Tracking Tests (`test_blocks.py`)

**Critical Tests**:
- ✅ Block wrapping at 64
- ✅ Missing block detection
- ✅ Wrap-around arithmetic
- ✅ Missing blocks across wrap boundary

**Example Wrap Test**:
```python
def test_block_wrapping():
    """Test block numbers wrap at 64"""
    tracker = BlockTracker()

    # Get blocks 62, 63, 0, 1
    for expected in [62, 63, 0, 1]:
        block_num = tracker.get_next_block_number()
        assert block_num == expected
```

**Example Missing Blocks Across Wrap**:
```python
def test_missing_blocks_wrap_boundary():
    """Test missing block detection across wrap"""
    tracker = BlockTracker()

    # Received blocks: 61, 62, 64 (wrapped to 0), 2
    # Missing: 63, 1
    tracker.good_header = 60
    tracker.end_header = 2

    # Mark blocks as received
    tracker.rx_pending = [
        TextBlock(61, "data"),
        TextBlock(62, "data"),
        TextBlock(0, "data"),
        TextBlock(2, "data"),
    ]

    missing = tracker.calculate_missing_blocks()
    assert 63 in missing
    assert 1 in missing
    assert len(missing) == 2
```

## Integration Tests

### Protocol Tests (`test_protocol.py`)

Test complete protocol interactions:

```python
async def test_connection_handshake():
    """Test CONREQ → CONACK handshake"""
    # Create two ARQProtocol instances
    station_a = ARQProtocol(PSK31(), "W1ABC")
    station_b = ARQProtocol(PSK31(), "K6XYZ")

    # A sends CONREQ
    audio = await station_a.connect("K6XYZ")

    # Demodulate and feed to B (simulated)
    # B should respond with CONACK
    # Verify both in CONNECTED state
```

### Loopback Tests

Test by feeding output back as input:

```python
def test_frame_loopback():
    """Build frame, parse it back"""
    original = ARQFrame('0', '0', CONREQ, "test")
    frame_bytes = original.build()

    # Parse the same frame
    parsed = ARQFrame.parse(frame_bytes)

    # Verify identical
    assert parsed.protocol_version == original.protocol_version
    assert parsed.stream_id == original.stream_id
    assert parsed.block_type == original.block_type
    assert parsed.payload == original.payload
```

## Validation Tests

### Comparing with fldigi Output

**Method 1: Generate frames with pydigi, compare to fldigi**

1. Generate frame with pydigi:
   ```python
   frame = ARQFrame('0', '0', CONREQ, "W1ABC:1025 K6XYZ:24 0 7")
   frame_bytes = frame.build()
   print(frame_bytes.hex())
   ```

2. Generate same frame with fldigi
3. Compare hex dumps byte-by-byte

**Method 2: Parse fldigi-generated frames**

1. Capture fldigi frame from audio or source
2. Parse with pydigi:
   ```python
   fldigi_frame_hex = "01..."  # From capture
   frame_bytes = bytes.fromhex(fldigi_frame_hex)
   parsed = ARQFrame.parse(frame_bytes)
   # Should parse without errors
   ```

## Interoperability Tests (Optional)

### Audio Loopback with fldigi

**Setup**:
1. Virtual audio cable (Linux: JACK, Windows: VB-Cable)
2. fldigi configured to use virtual audio
3. pydigi generates audio → virtual cable → fldigi
4. fldigi generates audio → virtual cable → pydigi (manual demod)

**Test Sequence**:
1. **pydigi sends CONREQ** → fldigi receives and displays
2. **fldigi sends CONACK** → pydigi receives (after manual demod)
3. Verify connection established

**Challenges**:
- Requires manual demodulation (pydigi is TX-only currently)
- Need proper timing/delays
- Audio synchronization

### Alternative: Frame Validation Only

Instead of full audio loopback:
1. Generate frames with pydigi
2. Save as text/hex
3. Manually inject into fldigi for parsing
4. Verify fldigi accepts them

## Test Data

### Sample Frames for Testing

```python
# CONREQ frame
CONREQ_PAYLOAD = "W1ABC:1025 K6XYZ:24 0 7 T60R5W10"

# STATUS frame
STATUS_PAYLOAD = "\x30\x32\x35\x21\x24"  # Last=48 Good=50 End=53 Missing=[1,4]

# Data block
DATA_PAYLOAD = "Hello World! This is a test message."

# Empty frame
EMPTY_PAYLOAD = ""

# Max size
MAX_PAYLOAD = "X" * 512
```

## Running Tests

### Run All Tests
```bash
pytest tests/test_arq/ -v
```

### Run Specific Test File
```bash
pytest tests/test_arq/test_crc.py -v
```

### Run with Coverage
```bash
pytest tests/test_arq/ --cov=pydigi.arq --cov-report=html
```

### Run Specific Test
```bash
pytest tests/test_arq/test_frame.py::test_conreq_frame_format -v
```

## Continuous Integration

Add to CI pipeline:
```yaml
# .github/workflows/test.yml
- name: Test ARQ
  run: |
    pytest tests/test_arq/ -v
```

## Test Checklist

Before considering implementation complete:

- [ ] All CRC tests pass
- [ ] All frame tests pass
- [ ] All block tracking tests pass
- [ ] Integration tests pass
- [ ] CRC verified against fldigi (at least 3 test vectors)
- [ ] CONREQ frame matches fldigi format
- [ ] STATUS frame parses correctly
- [ ] Data blocks 0-63 work
- [ ] Block wrapping works across boundary
- [ ] Missing block detection works
- [ ] Full connection handshake works in tests
- [ ] Text transmission works (multi-block)
- [ ] Retransmission logic works
- [ ] File transfer works (with Base64)
- [ ] (Optional) Real fldigi frame validates

## Debugging Tips

### CRC Mismatch
```python
# Print CRC calculation step-by-step
crc = CRC16()
print(f"Initial: 0x{crc.value():04X}")
for byte in data:
    crc.update(byte)
    print(f"After 0x{byte:02X}: 0x{crc.value():04X}")
print(f"Final: {crc.hex_string()}")
```

### Frame Parse Errors
```python
# Hexdump frame
print("Frame hex:", frame_bytes.hex())
print("Frame chars:", [f"0x{b:02X}" for b in frame_bytes])

# Check each component
print(f"SOH: 0x{frame_bytes[0]:02X}")
print(f"Version: '{chr(frame_bytes[1])}'")
print(f"Stream: '{chr(frame_bytes[2])}'")
print(f"Type: 0x{frame_bytes[3]:02X}")
print(f"Terminator: 0x{frame_bytes[-1]:02X}")
```

### Block Wrapping Issues
```python
# Trace block numbers
for i in range(70):
    block = (i - 1) % 64
    print(f"Iteration {i}: block {block}")
```

## Success Criteria

Tests are sufficient when:
1. ✅ All unit tests pass
2. ✅ CRC matches fldigi on known inputs
3. ✅ Frames parse fldigi-generated data
4. ✅ Integration tests show correct protocol flow
5. ✅ (Optional) Real fldigi accepts our frames
