# FLARQ ARQ Protocol Implementation

This directory contains documentation for the FLARQ ARQ protocol implementation in pydigi.

## What is FLARQ?

FLARQ (Fast Light Automatic Repeat reQuest) is a reliable file transfer protocol for HF radio based on the K9PS ARQ specification. It provides:

- **Automatic error detection** with CRC-16 checksums
- **Automatic retransmission** of corrupted/missing data blocks
- **Block-based transfer** with 0-63 wrapping counter
- **Transport agnostic** - works over PSK, QPSK, MFSK, Thor, MT63, etc.
- **File transfer support** via Base64 encoding

**Use case**: Send documents, images, or data files over HF radio with guaranteed delivery (similar to TCP but for radio)

## Implementation Status

**Current Status**: ABORT Handling Complete (9 of 14 sessions)

**Progress Tracker**:
- [x] Session 1: CRC-16 Implementation ⭐ CRITICAL
- [x] Session 2: Frame Builder/Parser ⭐ CRITICAL
- [x] Session 3: Block Tracking & Wrapping
- [x] Session 4: Config & State Machine
- [x] Session 5: Protocol Skeleton & Connection
- [x] Session 6: Frame Handler Stubs
- [x] Session 7: Text Transmission
- [x] Session 8: Reception & Reassembly
- [x] Session 9: ABORT Handling
- [ ] Session 10: Main Loop & Timing
- [ ] Session 11: Base64 & File Transfer
- [ ] Session 12: Integration Testing
- [ ] Session 13: Documentation & Polish
- [ ] Session 14: Interoperability Testing (Optional)

## Documentation Files

- **[overview.md](overview.md)** - High-level architecture and design
- **[sessions/](sessions/)** - Step-by-step implementation guides for each session
- **[protocol_reference.md](protocol_reference.md)** - Technical protocol details
- **[testing_guide.md](testing_guide.md)** - Testing strategy and validation

## Quick Start (After Implementation)

Once implemented, using FLARQ will be simple:

```python
from pydigi import PSK31
from pydigi.arq import ARQProtocol

# Create modem
modem = PSK31(frequency=1000, sample_rate=8000)

# Wrap with ARQ protocol
arq = ARQProtocol(modem, my_call="W1ABC")

# Connect and send file
await arq.connect("K6XYZ")
await arq.send_file("document.txt")
await arq.disconnect()
```

## Implementation Time Estimate

- **Total**: 30-40 hours
- **Duration**: 8-10 weeks (incremental, multi-session work)
- **Complexity**: High - strict interoperability requirements

## Dependencies

New dependency added for ARQ support:
- **crcmod >= 1.7** - CRC-16-MODBUS calculations (standard, well-tested)

Install all dependencies:
```bash
pip install -r requirements.txt
```

See [DEPENDENCIES.md](DEPENDENCIES.md) for detailed information.

## Next Steps

Start with **Session 1: CRC-16 Implementation** (2-3 hours, CRITICAL)

See [sessions/session_01_crc16.md](sessions/session_01_crc16.md) for detailed instructions.
