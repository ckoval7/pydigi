# Decoder API Documentation Index

This document provides a quick reference to all decoder API documentation.

## Quick Links

### For Users

- **[Decoder API User Guide](guides/decoder-api.md)** - Start here! Comprehensive guide with examples
- **[Decoder API Reference](api/reference/decoder_api.md)** - Complete API documentation
- **[PSK Decoder Example](guides/decoders.md)** - Working decoder example
- **[Signal Detection Guide](guides/signal-detection.md)** - DCD and sync techniques

### For Developers

- **[DECODER_INFRASTRUCTURE.md](../DECODER_INFRASTRUCTURE.md)** - Design documentation
- **[DECODER_API_SUMMARY.md](../DECODER_API_SUMMARY.md)** - Implementation summary
- **[PROJECT_TRACKER.md](../PROJECT_TRACKER.md)** - Project status

## Documentation Structure

### User Guide: `guides/decoder-api.md`

The main guide for learning the decoder API. Covers:

- Quick start example
- Building a complete decoder step-by-step
- Common patterns (DCD gating, AFC loops, state machines)
- Testing your decoder (AWGN, frequency offset, profiling)
- Advanced topics (Gardner timing, sync detection, error analysis)
- Best practices

**Start here if you're new to the decoder API!**

### API Reference: `api/reference/decoder_api.md`

Complete API documentation with:

- All classes and functions
- Parameters and return values
- Usage examples
- When to use each component
- Links to source code

**Use this for detailed API information.**

## Components by Category

### Timing Recovery
- **SymbolSlicer** - Simple decimating slicer
- **EarlyLateGate** - Early-late gate algorithm
- **GardnerTimingRecovery** - Advanced Gardner algorithm

**Documentation:**
- [User Guide Section](guides/decoder-api.md#step-1-setup-components)
- [API Reference](api/reference/decoder_api.md#timing-recovery)

### Data Carrier Detect (DCD)
- **EnergyDCD** - Energy-based signal detection
- **PreambleDetector** - Correlation-based preamble detection
- **ToneDCD** - Tone-based detection for FSK

**Documentation:**
- [User Guide Pattern](guides/decoder-api.md#pattern-1-dcd-gated-processing)
- [API Reference](api/reference/decoder_api.md#data-carrier-detect-dcd)

### Automatic Frequency Control (AFC)
- **PhaseAFC** - For PSK/QPSK/8PSK
- **ToneAFC** - For MFSK/FSQ/RTTY
- **PLL** - Full phase-locked loop

**Documentation:**
- [User Guide Pattern](guides/decoder-api.md#pattern-2-afc-loop)
- [API Reference](api/reference/decoder_api.md#automatic-frequency-control-afc)

### Sync Detection
- **SyncPattern** - Define sync patterns
- **SyncDetector** - Detect patterns via correlation
- **DecoderStateMachine** - State management
- Helper functions for common preambles

**Documentation:**
- [User Guide Pattern](guides/decoder-api.md#pattern-3-state-machine-control)
- [API Reference](api/reference/decoder_api.md#sync-detection)

### De-interleaving
- **BlockDeinterleaver** - For Olivia, Contestia, MT63, Thor
- **ConvolutionalDeinterleaver** - For MFSK variants

**Documentation:**
- [User Guide Pattern](guides/decoder-api.md#pattern-4-de-interleaving-with-fec)
- [API Reference](api/reference/decoder_api.md#de-interleaving)

### Testing & Validation
- **Noise generation** - AWGN, frequency offset, phase noise
- **Performance measurements** - BER, SER, SNR, throughput
- **Error analysis** - Burst vs random errors
- **Performance profiling** - CPU, memory, real-time factor

**Documentation:**
- [User Guide Section](guides/decoder-api.md#testing-your-decoder)
- [API Reference](api/reference/decoder_api.md#testing-validation)

## Examples

### Minimal Decoder
See [Quick Start](guides/decoder-api.md#quick-start) in the user guide.

### Complete PSK Decoder
See [Building a Complete Decoder](guides/decoder-api.md#building-a-complete-decoder) in the user guide.

### Complete QPSK Decoder
See [Example: Complete QPSK Decoder](guides/decoder-api.md#example-complete-qpsk-decoder) in the user guide.

## Common Tasks

### I want to...

**Build my first decoder**
→ Start with [Quick Start](guides/decoder-api.md#quick-start)

**Understand timing recovery**
→ Read [Timing Recovery](api/reference/decoder_api.md#timing-recovery) in API reference

**Add frequency tracking**
→ See [Pattern 2: AFC Loop](guides/decoder-api.md#pattern-2-afc-loop)

**Detect preambles**
→ See [Sync Detection](api/reference/decoder_api.md#sync-detection)

**Test my decoder with noise**
→ See [Testing Your Decoder](guides/decoder-api.md#testing-your-decoder)

**Measure BER performance**
→ See [Test with AWGN](guides/decoder-api.md#test-with-awgn)

**Profile decoder performance**
→ See [Profile Performance](guides/decoder-api.md#profile-performance)

**Implement de-interleaving**
→ See [Pattern 4: De-interleaving](guides/decoder-api.md#pattern-4-de-interleaving-with-fec)

## Source Code

All decoder API components are in:

- `pydigi/core/timing_recovery.py`
- `pydigi/core/dcd.py`
- `pydigi/core/afc.py`
- `pydigi/core/sync_detector.py`
- `pydigi/core/interleave.py` (de-interleavers)
- `pydigi/utils/noise.py`
- `pydigi/utils/measurements.py`

Import from:
```python
from pydigi.core import SymbolSlicer, EnergyDCD, PhaseAFC, ...
from pydigi.utils import add_awgn, calculate_ber, ...
```

## Related Documentation

- **[PSK Decoder Guide](guides/decoders.md)** - Working example
- **[Signal Detection](guides/signal-detection.md)** - DCD techniques
- **[Frequency Estimation](guides/frequency-estimation.md)** - Frequency tracking
- **[Core DSP API](api/reference/dsp.md)** - Low-level DSP components

## Getting Help

1. Check the [User Guide](guides/decoder-api.md) for common patterns
2. Search the [API Reference](api/reference/decoder_api.md) for specific components
3. Study the [PSK Decoder Example](guides/decoders.md)
4. Review the source code (it's well-documented!)

## Contributing

Found an issue or want to improve the documentation?

- Submit issues on GitHub
- See [Contributing Guide](contributing.md)

---

**Last Updated:** 2026-01-04

**Status:** All decoder API components are complete and documented
