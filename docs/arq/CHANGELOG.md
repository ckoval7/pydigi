# FLARQ Implementation - Changelog

## 2025-12-28 - Session 7: Text Transmission Complete

### Added
- ✅ **Text transmission functionality** in `pydigi/arq/protocol.py`
- ✅ **send_text()** method to queue text for transmission
- ✅ **_send_blocks()** method for block transmission with windowing
- ✅ **_send_data_frame()** helper for DATA frames
- ✅ **_send_poll()** helper for POLL frames
- ✅ **9 comprehensive tests** for text transmission (104 total ARQ tests now)
- ✅ **Session 7 implementation guide** in `docs/arq/sessions/session_07_text_transmission.md`

### Modified
- **protocol.py**: Updated `process()` to call `_send_blocks()` when blocks are queued
- **protocol.py**: Added `_tx_blocks` queue for transmission
- **protocol.py**: Improved retry and timeout handling
- **test_protocol.py**: Added 9 new tests for transmission functionality

### Key Features
- Text automatically broken into buffer-sized blocks (default 128 bytes)
- Send window management prevents buffer overflow at receiver
- Retransmissions prioritized over new blocks
- max_headers limit prevents flooding (default 8 frames per send)
- Block tracker integration for sequence numbering
- Automatic POLL frame sending for acknowledgment requests

### Testing
- All 104 ARQ tests passing
- Protocol coverage: 86% (up from 84%)
- Tests cover:
  - Single and multiple block transmission
  - Retransmission priority
  - Send window management
  - max_headers limiting
  - Connection state validation
  - Process loop integration

### References
- fldigi source: `fldigi/src/flarq-src/arq.cxx`
  - `sendText()`: lines 1165-1180
  - `sendblocks()`: lines 1182-1221
  - `textFrame()`: lines 592-604
  - `transmitdata()`: lines 1273-1292

## 2025-12-28 - Documentation Created & Dependencies Updated

### Added
- ✅ **Documentation structure** created in `docs/arq/`
- ✅ **`crcmod>=1.7`** added to `requirements.txt` for CRC-16-MODBUS
- ✅ Complete implementation guides for Sessions 1-2
- ✅ Technical reference documentation
- ✅ Testing strategy guide
- ✅ Dependencies documentation

### Files Created

**Documentation (8 files, ~35 KB)**:
- `docs/arq/README.md` - Main documentation index
- `docs/arq/overview.md` - Architecture overview
- `docs/arq/protocol_reference.md` - Technical protocol specification
- `docs/arq/testing_guide.md` - Testing strategy
- `docs/arq/IMPLEMENTATION_STATUS.md` - Progress tracker
- `docs/arq/DEPENDENCIES.md` - Dependency information
- `docs/arq/sessions/README.md` - Session index
- `docs/arq/sessions/session_01_crc16.md` - CRC-16 implementation guide
- `docs/arq/sessions/session_02_frames.md` - Frame implementation guide

**Code Structure**:
- `pydigi/arq/__init__.py` - Empty placeholder
- `tests/test_arq/` - Empty test directory

### Modified

**requirements.txt**:
```diff
# Core dependencies
numpy>=1.20.0
scipy>=1.7.0
typing-extensions>=4.0.0

+# ARQ protocol support
+crcmod>=1.7
+
# Optional audio support
soundfile>=0.10.0
```

### Key Decisions

1. **Use `crcmod` library** instead of manual CRC implementation
   - fldigi uses standard CRC-16-MODBUS (polynomial 0xA001, init 0xFFFF)
   - `crcmod` provides well-tested, industry-standard implementation
   - Reduces implementation complexity and risk

2. **Verified test vectors** against fldigi algorithm:
   ```python
   test_vectors = [
       (b'', 'FFFF'),
       (b'Hello', 'F377'),
       (b'Hello World', 'DAED'),
       (b'\x0100cW1ABC:1025 K6XYZ:24 0 7', '13FF'),
   ]
   ```

3. **Documentation-first approach**
   - Complete session guides before implementation
   - Clear validation checkpoints for each session
   - Multi-session design for incremental work

### Implementation Status

- **Planning**: ✅ Complete
- **Documentation**: ✅ Complete
- **Dependencies**: ✅ Updated
- **Implementation**: ⬜ Not Started (ready to begin Session 1)

### Next Steps

1. Install dependencies: `pip install -r requirements.txt`
2. Start Session 1: CRC-16 Implementation
   - Follow `docs/arq/sessions/session_01_crc16.md`
   - Create `pydigi/arq/crc.py`
   - Create `tests/test_arq/test_crc.py`
   - Validate against test vectors

### References

- Full implementation plan: `/home/corey/.claude/plans/imperative-bubbling-parasol.md`
- fldigi source: `fldigi/src/flarq-src/`
- K9PS ARQ Spec: `fldigi/aux/ARQ2.pdf`
