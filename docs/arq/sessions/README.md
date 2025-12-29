# FLARQ Implementation - Session Guides

Step-by-step guides for implementing FLARQ ARQ protocol support in pydigi.

## Session Overview

| Session | Title | Duration | Priority | Status |
|---------|-------|----------|----------|--------|
| 1 | [CRC-16 Implementation](session_01_crc16.md) | 2-3h | ⭐ CRITICAL | ✅ Complete |
| 2 | [Frame Builder/Parser](session_02_frames.md) | 2-3h | ⭐ CRITICAL | ✅ Complete |
| 3 | [Block Tracking & Wrapping](session_03_blocks.md) | 2-3h | ⭐ HIGH | ✅ Complete |
| 4 | [Config & State Machine](session_04_config_state.md) | 1-2h | MEDIUM | ✅ Complete |
| 5 | [Protocol Skeleton & Connection](session_05_protocol.md) | 3-4h | HIGH | ✅ Complete |
| 6 | [Frame Handler Stubs](session_06_frame_handlers.md) | 2-3h | HIGH | ✅ Complete |
| 7 | [Text Transmission](session_07_text_transmission.md) | 3-4h | HIGH | ✅ Complete |
| 8 | [Reception & Reassembly](session_08_reception_reassembly.md) | 3-4h | HIGH | ✅ Complete |
| 9 | [ABORT Handling](session_09_abort_handling.md) | 2-3h | MEDIUM | ✅ Complete |
| 10 | Main Loop & Timing | 3-4h | HIGH | Not Started |
| 11 | Base64 & File Transfer | 2-3h | MEDIUM | Not Started |
| 12 | Integration Testing | 2-3h | HIGH | Not Started |
| 13 | Documentation & Polish | 1-2h | MEDIUM | Not Started |
| 14 | Interoperability Testing | 2-3h | LOW (Optional) | Not Started |

**Total Time**: 30-40 hours

## Quick Start

### Starting Implementation

1. Begin with **Session 1: CRC-16** - This is the most critical component
2. Work sequentially through Sessions 1-3 (the foundation)
3. Then proceed with Sessions 4-13

### Prerequisites

- Python 3.8+
- pytest for testing
- numpy (already required by pydigi)
- fldigi source code in `fldigi/src/flarq-src/` for reference

### Session Format

Each session guide includes:
- **Goal**: What you'll accomplish
- **Deliverables**: Specific files/code to create
- **Implementation Steps**: Detailed step-by-step instructions
- **Validation Checkpoint**: Clear "done" criteria
- **Common Pitfalls**: Things to watch out for
- **Reference Files**: Where to look in fldigi source

## Critical Sessions (Start Here)

### Session 1: CRC-16 ⭐
**Why Critical**: Every ARQ frame uses CRC-16 for error detection. If this doesn't match fldigi exactly, communication fails.

**Key Points**:
- Polynomial: 0xA001
- Initial value: 0xFFFF
- Output: 4-char uppercase hex

[Start Session 1 →](session_01_crc16.md)

### Session 2: Frame Builder/Parser ⭐
**Why Critical**: Frame format must be byte-for-byte compatible with fldigi.

**Key Points**:
- Frame structure: `<SOH>[Header(4)][Payload][CRC(4)]<EOT|SOH>`
- CRC validation
- Proper terminator selection

[Start Session 2 →](session_02_frames.md)

### Session 3: Block Tracking
**Why Important**: Block numbering wraps at 64, missing block detection is complex.

**Key Points**:
- Modulo-64 arithmetic
- Missing block detection across wrap boundary
- Block queue management

## Implementation Strategy

### Sequential (Recommended)
Work through sessions 1-13 in order. Each builds on previous sessions.

### Parallel Possibilities
After Session 2, you can work on Sessions 3 and 4 in parallel if desired:
- Session 3: Block Tracking
- Session 4: Config & State Machine

Both are independent of each other but required for Session 5.

## Testing Strategy

Each session includes:
- **Unit tests** for the component
- **Validation checkpoint** to verify completion
- **Test examples** from fldigi

Run tests after each session before moving on:
```bash
pytest tests/test_arq/test_<component>.py -v
```

## Progress Tracking

Update the status in the table above as you complete sessions.

Mark complete when:
- ✅ All deliverables created
- ✅ All tests pass
- ✅ Validation checkpoint requirements met

## Getting Help

### Documentation
- [Protocol Reference](../protocol_reference.md) - Technical details
- [Overview](../overview.md) - Architecture
- [Testing Guide](../testing_guide.md) - Testing strategy

### fldigi Source Reference
All references to fldigi source files assume the source is at:
```
/home/corey/pydigi/fldigi/src/flarq-src/
```

Key files:
- `include/arq.h` - Class definitions
- `arq.cxx` - Core implementation
- `b64.cxx` - Base64 encoding

## After Completion

Once all sessions complete:
1. Run full test suite
2. Create examples
3. Update PROJECT_TRACKER.md
4. (Optional) Test with real fldigi via audio loopback

## Session Details

### Detailed Guides Available
- ✅ [Session 1: CRC-16](session_01_crc16.md) - Complete
- ✅ [Session 2: Frames](session_02_frames.md) - Complete
- ✅ [Session 3: Block Tracking](session_03_blocks.md) - Complete
- ✅ [Session 4: Config & State Machine](session_04_config_state.md) - Complete
- ✅ [Session 5: Protocol Skeleton & Connection](session_05_protocol.md) - Complete
- ✅ [Session 6: Frame Handler Stubs](session_06_frame_handlers.md) - Complete
- ✅ [Session 7: Text Transmission](session_07_text_transmission.md) - Complete
- ✅ [Session 8: Reception & Reassembly](session_08_reception_reassembly.md) - Complete
- ✅ [Session 9: ABORT Handling](session_09_abort_handling.md) - Complete
- ⏳ Session 10-14: See main plan file

More detailed session guides will be created as needed during implementation.
