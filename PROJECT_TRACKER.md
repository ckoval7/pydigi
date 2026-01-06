# PyDigi Project Tracker

**Last Updated:** 2026-01-04

## Project Status Summary

**TX Implementation: ✅ COMPLETE (100%)**
- All 22 stable fldigi mode families implemented (~151 mode variants)
- Modes: CW, RTTY, PSK, QPSK, 8PSK, Olivia, Contestia, MFSK, Hellschreiber, DominoEX, FSQ, Thor, Throb, MT63, PSK Extended, 8PSK FEC, Multi-Carrier PSK-R, IFKP, SCAMP, NAVTEX/SITOR-B, WEFAX

**RX Implementation: 🔄 IN PROGRESS (4 decoders working, framework integrated)**
- ✅ PSK decoder (all rates: 31/63/125/250/500/1000) - **Using framework components**
- ✅ QPSK decoder (all rates: 31/63/125/250/500) - **Using framework components**
- ✅ 8PSK decoder (non-FEC, all rates: 125/250/500/1000) - **Using framework components**
- 🔧 8PSK FEC decoder (85% - minor silence handling issue)
- 📋 18+ decoder families remaining (see Decoder Roadmap below)

**Core Infrastructure: ✅ COMPLETE**
- NCO (oscillator.py)
- Filters (FIR, moving average, Goertzel, bandpass/lowpass)
- FFT operations (fft.py)
- Convolutional encoder (encoder.py)
- Viterbi FEC decoder (viterbi.py) - 100% verified
- Audio I/O utilities
- Base modem classes

**Decoder API Components: ✅ COMPLETE (2026-01-04)**
- **Timing Recovery** (timing_recovery.py)
  - SymbolSlicer - Simple decimating slicer
  - EarlyLateGate - Early-late gate timing recovery
  - GardnerTimingRecovery - Advanced Gardner algorithm
- **Data Carrier Detect** (dcd.py)
  - EnergyDCD - Energy-based signal detection
  - PreambleDetector - Correlation-based preamble detection
  - ToneDCD - Tone-based detection for FSK modes
- **Automatic Frequency Control** (afc.py)
  - PhaseAFC - AFC for PSK/QPSK/8PSK modes
  - ToneAFC - AFC for MFSK/FSQ/RTTY modes
  - PLL - Full phase-locked loop implementation
- **Sync Detection** (sync_detector.py)
  - SyncPattern - Define sync patterns
  - SyncDetector - Correlation-based pattern detection
  - DecoderStateMachine - State management (IDLE/PREAMBLE/DATA/POSTAMBLE)
  - Helper functions for PSK, RTTY, MFSK preambles
- **De-interleavers** (interleave.py)
  - BlockDeinterleaver - For Olivia, Contestia, MT63, Thor
  - ConvolutionalDeinterleaver - For some MFSK variants
- **Testing & Validation** (utils/)
  - Noise generation (AWGN, frequency offset, phase noise, timing jitter, multipath)
  - Performance measurements (BER, SER, SNR, throughput)
  - Error pattern analysis
  - Performance profiler
- **Documentation**: See DECODER_INFRASTRUCTURE.md and DECODER_API_SUMMARY.md

**Framework Integration: ✅ COMPLETE (2026-01-05)**
- ✅ PSK decoder refactored to use framework components:
  - NCO (oscillator.py) - Replaced manual phase accumulator
  - PhaseAFC (afc.py) - Replaced custom AFC implementation
  - EnergyDCD (dcd.py) - Replaced simple threshold-based DCD
- ✅ QPSK decoder refactored to use framework components:
  - NCO, PhaseAFC, EnergyDCD integrated
  - Maintained fldigi-compatible Viterbi FEC decoding
- ✅ 8PSK decoder refactored to use framework components:
  - NCO, PhaseAFC, EnergyDCD integrated
  - Kept pattern-based DCD for preamble/postamble detection
- ✅ All tests passing (test_psk_decoder.py)
- **Benefits**:
  - Reduced code duplication across decoders
  - Consistent API for timing recovery, DCD, and AFC
  - Easier to maintain and extend
  - Better separation of concerns

---

## Current RX Decoder Status

### Working Decoders (4/22 families)

#### 1. PSK Decoder (pydigi/modems/psk_decoder.py) ✅
- **Status**: Fully working for all PSK rates
- **Modes**: PSK31, PSK63, PSK125, PSK250, PSK500, PSK1000
- **Features**:
  - Baseband conversion with NCO
  - Matched filtering with decimation
  - Symbol timing recovery
  - Differential phase detection
  - PSK varicode decoding
  - DCD-based preamble/postamble detection

#### 2. QPSK Decoder (pydigi/modems/qpsk_decoder.py) ✅
- **Status**: Fully working for all QPSK rates
- **Modes**: QPSK31, QPSK63, QPSK125, QPSK250, QPSK500
- **Features**:
  - 4-phase differential detection
  - Viterbi FEC decoding (K=5)
  - PSK varicode decoding
  - Symbol timing recovery

#### 3. 8PSK Decoder (pydigi/modems/psk8_decoder.py) ✅
- **Status**: Fully working for non-FEC modes
- **Modes**: 8PSK125, 8PSK250, 8PSK500, 8PSK1000
- **Features**:
  - 8-phase differential detection
  - MFSK varicode decoding
  - Symbol timing recovery
  - Successfully decodes all message lengths

#### 4. 8PSK FEC Decoder (pydigi/modems/psk8_fec_decoder.py) 🔧
- **Status**: 85% complete
- **Modes**: 8PSK125F/FL, 8PSK250F/FL, 8PSK500F, 8PSK1000F, 8PSK1200F
- **Working**:
  - Symbol-level FEC pipeline verified (100%)
  - Soft bit mapping correct
  - Viterbi decoder (K=5/13/16) working perfectly
  - Audio loopback works WITH noise (0.02-0.05)
- **Issue**: Fails with leading silence + noise=0.0
  - Pure zeros during silence corrupt FEC decoder state
  - Works perfectly without leading silence
  - Next: Investigate silence processing in FEC state machine

### Core Decoder Components

#### Viterbi FEC Decoder (pydigi/core/viterbi.py) ✅
- **Status**: 100% verified and optimized
- **Features**:
  - Core algorithm matches fldigi exactly
  - Supports K=5, K=13, K=16 constraint lengths
  - State transitions verified step-by-step
  - Performance optimized: 45x speedup (25ms → 0.5ms for K=16)
  - Decoder latency properly handled: offset = traceback - chunksize + 1
  - Used by: QPSK, 8PSK FEC, Olivia, Contestia, Thor

---

## Decoder Roadmap (Sorted by Difficulty)

### EASY: Variants of Existing Decoders (6 families)

These decoders are variations of already-implemented decoders. Main work is parameter tuning and testing.

#### 1. PSK Extended Modes (single-carrier variants)
- **Difficulty**: ⭐ (trivial - reuse PSK decoder)
- **Modes**: PSK1000, PSK63F (6 modes total, 4 are multi-carrier)
- **Why easy**: Single-carrier modes use existing PSK decoder with different baud rates
- **Implementation**: Add baud rate configs to psk_decoder.py
- **Reference**: fldigi/src/psk/psk.cxx
- **Estimated effort**: 1-2 hours

#### 2. 8PSK FEC Variants (remaining modes)
- **Difficulty**: ⭐ (trivial - reuse 8PSK FEC decoder)
- **Modes**: 8PSK125FL, 8PSK250FL (long interleaver variants)
- **Why easy**: Same as 8PSK FEC, just longer interleaver depth
- **Implementation**: Fix silence issue first, then add interleaver configs
- **Reference**: fldigi/src/psk/psk.cxx
- **Estimated effort**: 2-4 hours (after silence fix)

#### 3. Throb Decoders
- **Difficulty**: ⭐⭐ (easy)
- **Modes**: Throb1, Throb2, Throb4, ThrobX1, ThrobX2, ThrobX4 (6 modes)
- **Why easy**: Dual-tone amplitude detection, no carrier tracking needed
- **Technique**: Goertzel filter pairs for each tone combination
- **Implementation**: Create throb_decoder.py with dual Goertzel detectors
- **Reference**: fldigi/src/throb/throb.cxx
- **Estimated effort**: 1 day

#### 4. CW Decoder (Morse Code)
- **Difficulty**: ⭐⭐ (easy)
- **Why easy**: Simple envelope detection + timing analysis
- **Technique**:
  - Envelope detection (Hilbert transform or simple rectification)
  - Threshold-based mark/space detection
  - Timing analysis for dot/dash/space classification
  - Morse table lookup
- **Implementation**: Create cw_decoder.py
- **Reference**: fldigi/src/cw/cw.cxx
- **Estimated effort**: 1-2 days

#### 5. RTTY Decoder
- **Difficulty**: ⭐⭐ (easy)
- **Why easy**: Dual-tone FSK detection, well-understood protocol
- **Technique**:
  - Dual Goertzel filters for mark/space tones
  - Bit timing recovery
  - Baudot code table lookup
  - LTRS/FIGS shift handling
- **Implementation**: Create rtty_decoder.py
- **Reference**: fldigi/src/rtty/rtty.cxx
- **Estimated effort**: 2-3 days

#### 6. FSQ Decoder
- **Difficulty**: ⭐⭐ (easy-medium)
- **Modes**: FSQ-2, FSQ-3, FSQ-4.5, FSQ-6 (4 modes, plus FSQ-1.5)
- **Why easy**: Character-based FSK similar to RTTY, reuse tone detection
- **Technique**:
  - 33-tone Goertzel filter bank
  - Character symbol detection
  - FSQ varicode decoding
  - Timing recovery
- **Implementation**: Create fsq_decoder.py
- **Reference**: fldigi/src/fsq/fsq.cxx
- **Estimated effort**: 3-4 days

---

### MEDIUM: New Techniques, Moderate Complexity (7 families)

These require new DSP techniques but are well-documented and straightforward.

#### 7. MFSK Decoders (Basic)
- **Difficulty**: ⭐⭐⭐ (medium)
- **Modes**: MFSK4, MFSK8, MFSK11, MFSK16, MFSK22, MFSK31, MFSK32 (7 modes)
- **Why medium**: Multi-tone FSK, need tone bank + FEC
- **Technique**:
  - FFT-based tone detection (sliding window)
  - Symbol timing recovery
  - Gray code to data bits
  - Viterbi FEC decoding (already have this!)
  - Varicode decoding
- **Implementation**: Create mfsk_decoder.py
- **Reference**: fldigi/src/mfsk/mfsk.cxx, pj_mfsk.h
- **Estimated effort**: 1 week

#### 8. MFSK Decoders (Large)
- **Difficulty**: ⭐⭐⭐ (medium)
- **Modes**: MFSK64, MFSK64L, MFSK128, MFSK128L (4 modes)
- **Why medium**: Larger FFT bins, longer interleaving
- **Technique**: Same as basic MFSK but with:
  - Larger FFT windows
  - Longer interleaver buffers (L = long interleaver)
  - More tones to track
- **Implementation**: Extend mfsk_decoder.py
- **Reference**: fldigi/src/mfsk/mfsk.cxx
- **Estimated effort**: 3-4 days (after basic MFSK working)

#### 9. DominoEX Decoders
- **Difficulty**: ⭐⭐⭐ (medium)
- **Modes**: DominoEX Micro, 4, 5, 8, 11, 16, 22, 44, 88 (9 modes)
- **Why medium**: IFK (incremental frequency keying) + FEC
- **Technique**:
  - 18-tone FFT-based detection
  - IFK symbol decoding (frequency increments)
  - Viterbi FEC decoding
  - Varicode decoding
- **Implementation**: Create dominoex_decoder.py
- **Reference**: fldigi/src/dominoex/dominoex.cxx
- **Estimated effort**: 1 week

#### 10. Thor Decoders
- **Difficulty**: ⭐⭐⭐ (medium)
- **Modes**: Thor Micro, 4, 5, 8, 11, 16, 22, 25, 32, 44, 56, 25x4, 50x1, 50x2, 100 (15 modes)
- **Why medium**: Similar to DominoEX but with interleaving
- **Technique**:
  - 18-tone FFT-based detection
  - IFK symbol decoding
  - Interleaving/de-interleaving
  - Viterbi FEC decoding
  - Varicode decoding
- **Implementation**: Create thor_decoder.py
- **Reference**: fldigi/src/thor/thor.cxx
- **Estimated effort**: 1 week

#### 11. Hellschreiber Decoders
- **Difficulty**: ⭐⭐⭐ (medium)
- **Modes**: Feld Hell, Slow Hell, X5, X9, FSK Hell, FSK Hell-105, Hell-80 (7 modes)
- **Why medium**: Time-frequency pixel detection, different from other modes
- **Technique**:
  - For amplitude modes (Feld/Slow/X5/X9): envelope detection + timing
  - For FSK modes: dual-tone detection
  - Character recognition from pixel patterns
  - Timing recovery for pixel clock
- **Implementation**: Create hell_decoder.py
- **Reference**: fldigi/src/hell/hell.cxx
- **Estimated effort**: 1-2 weeks

#### 12. IFKP Decoders
- **Difficulty**: ⭐⭐⭐ (medium)
- **Modes**: IFKP-0.5, IFKP-1.0, IFKP-2.0 (3 modes)
- **Why medium**: Incremental frequency keying, similar to DominoEX
- **Technique**:
  - FFT-based tone detection
  - IFK differential decoding
  - Symbol timing recovery
  - IFKP character table lookup
- **Implementation**: Create ifkp_decoder.py
- **Reference**: fldigi/src/ifkp/ifkp.cxx
- **Estimated effort**: 4-5 days

#### 13. SCAMP Decoders
- **Difficulty**: ⭐⭐⭐⭐ (medium-hard)
- **Modes**: SCAMPFSK, SCAMPOOK, SCFSKFST, SCFSKSLW, SCOOKSLW, SCFSKVSL (6 modes)
- **Why medium-hard**: Hybrid FSK/OOK modes, less common technique
- **Technique**:
  - FSK modes: Multi-tone detection
  - OOK modes: Amplitude detection
  - SCAMP varicode decoding
  - Timing recovery
- **Implementation**: Create scamp_decoder.py
- **Reference**: fldigi/src/scamp/scamp.cxx
- **Estimated effort**: 1 week

---

### HARD: Advanced Techniques, High Complexity (5 families)

These require advanced DSP techniques, interleaving, and/or significant new infrastructure.

#### 14. Olivia Decoders
- **Difficulty**: ⭐⭐⭐⭐ (hard)
- **Modes**: 36 configurations (4 bandwidths × 9 tone counts)
  - Bandwidths: 125, 250, 500, 1000, 2000 Hz
  - Tones: 2, 4, 8, 16, 32, 64, 128, 256 tones
- **Why hard**: MFSK + Walsh functions + interleaving + FEC
- **Technique**:
  - FFT-based multi-tone detection
  - Walsh function encoding/decoding (Fast Hadamard Transform)
  - Block interleaving/de-interleaving
  - Viterbi FEC decoding
  - Character assembly
- **Implementation**: Create olivia_decoder.py
- **Reference**: fldigi/src/olivia/olivia.cxx, pj_mfsk.h, pj_fht.h
- **Estimated effort**: 2-3 weeks

#### 15. Contestia Decoders
- **Difficulty**: ⭐⭐⭐⭐ (hard)
- **Modes**: 36 configurations (same structure as Olivia)
- **Why hard**: Nearly identical to Olivia, different interleaver depth
- **Technique**: Same as Olivia with different parameters
- **Implementation**: Create contestia_decoder.py (or extend olivia_decoder.py)
- **Reference**: fldigi/src/contestia/contestia.cxx
- **Estimated effort**: 1 week (after Olivia working)

#### 16. MT63 Decoders
- **Difficulty**: ⭐⭐⭐⭐⭐ (very hard)
- **Modes**: MT63-500S/L, MT63-1000S/L, MT63-2000S/L (6 modes)
- **Why very hard**: 64-carrier OFDM + interleaving + FEC
- **Technique**:
  - 64-carrier OFDM reception
  - Per-carrier DBPSK demodulation
  - Time and frequency interleaving
  - Viterbi FEC decoding (K=5)
  - Block interleaver (S=short, L=long)
  - Sync sequence detection
- **Implementation**: Create mt63_decoder.py
- **Reference**: fldigi/src/mt63/mt63.cxx
- **Estimated effort**: 3-4 weeks

#### 17. PSK Extended (Multi-Carrier) Decoders
- **Difficulty**: ⭐⭐⭐⭐ (hard)
- **Modes**: 2X_PSK500, 4X_PSK500, 2X_PSK800, 2X_PSK1000, 6X_PSK250, 12X_PSK125
- **Why hard**: Multiple parallel PSK decoders + combining logic
- **Technique**:
  - N parallel PSK decoders at different frequencies
  - Frequency offset management
  - Symbol synchronization across carriers
  - Data combining/merging
- **Implementation**: Extend psk_decoder.py with multi-carrier support
- **Reference**: fldigi/src/psk/psk.cxx (MULTI_CARRIER sections)
- **Estimated effort**: 2 weeks

#### 18. NAVTEX/SITOR-B Decoders
- **Difficulty**: ⭐⭐⭐⭐ (hard)
- **Modes**: NAVTEX, SITOR-B (2 modes)
- **Why hard**: ARQ protocol handling + FSK + error detection
- **Technique**:
  - FSK demodulation (170 Hz shift)
  - CCIR476 code decoding
  - ARQ state machine
  - Error detection and repeat requests
  - NAVTEX message formatting
- **Implementation**: Create navtex_decoder.py
- **Reference**: fldigi/src/navtex/navtex.cxx
- **Estimated effort**: 2 weeks

---

### SPECIAL: Non-Standard Decoders (1 family)

#### 19. WEFAX Decoders
- **Difficulty**: ⭐⭐⭐⭐ (hard - different domain)
- **Modes**: WEFAX-576, WEFAX-288 (2 modes)
- **Why hard**: Image decoding, not text communication
- **Technique**:
  - AM demodulation (1500 Hz black, 2300 Hz white)
  - Scanline synchronization (675 Hz start, 450 Hz phasing)
  - IOC576/IOC288 standards (Index of Cooperation)
  - Image buffer assembly
  - Output to PNG/BMP
- **Implementation**: Create wefax_decoder.py
- **Reference**: fldigi/src/wefax/wefax.cxx
- **Estimated effort**: 1-2 weeks
- **Note**: Lower priority - image mode, less common usage

---

## Decoder Implementation Priority

### Phase 1: Complete PSK Family (HIGHEST PRIORITY)
1. ✅ PSK decoder (done)
2. ✅ QPSK decoder (done)
3. ✅ 8PSK decoder (done)
4. 🔧 Fix 8PSK FEC silence issue
5. Add 8PSK FEC long interleaver variants
6. Add PSK Extended single-carrier modes

**Rationale**: PSK is the most popular HF digital mode family. Completing all PSK variants gives maximum utility.

### Phase 2: Simple Modes (QUICK WINS)
7. CW decoder
8. RTTY decoder
9. Throb decoders
10. FSQ decoder

**Rationale**: These are relatively easy and commonly used modes. Good for building momentum.

### Phase 3: MFSK Family
11. Basic MFSK decoders (4/8/11/16/22/31/32)
12. Large MFSK decoders (64/64L/128/128L)
13. DominoEX decoders
14. Thor decoders
15. IFKP decoders

**Rationale**: MFSK techniques are reusable across multiple mode families. Builds foundation for harder modes.

### Phase 4: Advanced Modes
16. Hellschreiber decoders
17. Olivia decoders
18. Contestia decoders
19. SCAMP decoders

**Rationale**: These are less common but useful for completeness. Olivia/Contestia share implementation.

### Phase 5: Most Complex
20. MT63 decoders (OFDM - most complex)
21. PSK Extended multi-carrier decoders
22. NAVTEX/SITOR-B decoders (ARQ protocol)

**Rationale**: These require the most advanced techniques. Tackle after gaining experience with simpler decoders.

### Phase 6: Special Cases
23. WEFAX decoders (image mode)

**Rationale**: Different use case (images vs text). Can be done independently.

---

## Completed TX Implementations (Archive)

All 22 mode families have working TX implementations. Details archived for brevity:

### Basic Modes
- **CW** (pydigi/modems/cw.py): Morse code, 5-200 WPM, raised cosine shaping
- **RTTY** (pydigi/modems/rtty.py): Baudot code, 45.45/50/56/75/100/110/150/200/300 baud
- **Hellschreiber** (pydigi/modems/hell.py): 7 modes including Feld, Slow, FSK variants

### PSK Family
- **PSK** (pydigi/modems/psk.py): PSK31/63/125/250/500/1000 - 6 modes
- **QPSK** (pydigi/modems/qpsk.py): QPSK31/63/125/250/500 - 5 modes with Viterbi FEC
- **8PSK** (pydigi/modems/psk8.py): 8PSK125/250/500/1000 - 4 modes
- **8PSK FEC** (pydigi/modems/psk8_fec.py): 7 modes with K=5/13/16 Viterbi FEC
- **PSK Extended** (pydigi/modems/psk_extended.py): 8 modes including multi-carrier
- **PSK-R** (pydigi/modems/psk_extended.py): 33 modes (27 PSK-R + 6 standard multi-carrier)

### MFSK Family
- **MFSK** (pydigi/modems/mfsk.py): 11 modes (MFSK4/8/11/16/22/31/32/64/64L/128/128L)
- **Olivia** (pydigi/modems/olivia.py): 36 configurations with Walsh functions + FEC
- **Contestia** (pydigi/modems/contestia.py): 36 configurations similar to Olivia
- **DominoEX** (pydigi/modems/dominoex.py): 9 modes with IFK modulation
- **Thor** (pydigi/modems/thor.py): 15 modes with IFK + interleaving
- **IFKP** (pydigi/modems/ifkp.py): 3 modes (IFKP-0.5/1.0/2.0)

### Other Modes
- **Throb** (pydigi/modems/throb.py): 6 modes with dual-tone amplitude modulation
- **FSQ** (pydigi/modems/fsq.py): 5 baud rates (1.5/2.0/3.0/4.5/6.0)
- **MT63** (pydigi/modems/mt63.py): 6 modes with 64-carrier OFDM
- **SCAMP** (pydigi/modems/scamp.py): 6 variants (FSK/OOK hybrid modes)
- **NAVTEX/SITOR-B** (pydigi/modems/navtex.py): 2 ARQ modes
- **WEFAX** (pydigi/modems/wefax.py): 2 image transmission modes (IOC576/288)

**All TX modes validated**: Signals decode correctly in fldigi.

---

## Technical Implementation Notes

### Key Decoder Components Needed

1. **Timing Recovery**: AFC (Automatic Frequency Control) + symbol timing
2. **Synchronization**: Preamble detection, DCD (Data Carrier Detect)
3. **Demodulation**: Phase detection, frequency detection, amplitude detection
4. **FEC Decoding**: Viterbi (already have), convolutional codes
5. **De-interleaving**: Block and convolutional interleavers
6. **Character Decoding**: Varicode tables, baudot, ASCII

### Reusable Decoder Building Blocks

- ✅ **Viterbi decoder** (pydigi/core/viterbi.py): Works perfectly for K=5/13/16
- ✅ **NCO** (pydigi/core/oscillator.py): Frequency translation
- ✅ **Filters** (pydigi/core/filters.py): FIR, moving average, Goertzel
- ✅ **FFT** (pydigi/core/fft.py): Spectral analysis for tone detection
- ✅ **Varicode tables**: PSK, MFSK, Throb, FSQ variants
- 📋 **Need to add**: AFC, symbol timing recovery, de-interleaver classes

### Decoder Testing Strategy

1. **Unit tests**: Test individual components (timing recovery, demodulation)
2. **Loopback tests**: Encode → Decode in Python, verify perfect recovery
3. **Noise tests**: Add AWGN, verify degradation gracefully
4. **fldigi validation**: Encode in Python → Decode in fldigi
5. **Cross-validation**: Encode in fldigi → Decode in Python

---

## Known Issues

### Current Issues
- **8PSK FEC Decoder**: Fails with leading silence + noise=0.0 (85% complete)
  - Pure zeros during silence corrupt FEC state
  - Works perfectly with noise > 0.02 or without leading silence
  - Next: Investigate FEC state initialization during silence

### Fixed Issues (Summary)
- ✅ PSK critical bugs (pulse shaping, bit mapping, postamble) - Fixed 2025-12-13
- ✅ DSP filtering (normalization, phase interpolation, bandpass) - Fixed 2025-12-13
- ✅ Viterbi decoder latency (offset calculation) - Fixed 2026-01-03
- ✅ All TX modes now generate valid signals that decode in fldigi

---

## Project History (Condensed)

**December 2025**: Project started. Implemented all 22 TX mode families over ~17 sessions.
- Sessions 1-3: Core infrastructure, CW, RTTY, PSK31
- Sessions 4-7: QPSK, 8PSK, debugging PSK modes
- Sessions 8-12: Olivia, Contestia, MFSK, Hellschreiber, DominoEX
- Sessions 13-17: FSQ, Thor, Throb, MT63, PSK Extended, 8PSK FEC

**January 2026**: Started RX decoder implementation.
- Jan 3: Implemented PSK, QPSK, 8PSK, 8PSK FEC decoders
- Jan 3: Fixed Viterbi decoder latency issue, verified 100% accuracy
- Jan 4: Current focus on fixing 8PSK FEC silence handling

---

## Next Steps

1. **Fix 8PSK FEC silence handling** (high priority)
2. **Add remaining 8PSK FEC variants** (long interleaver modes)
3. **Start Phase 2 decoders**: CW, RTTY, Throb, FSQ (quick wins)
4. **Build reusable decoder components**: AFC, timing recovery, de-interleaver
5. **Implement MFSK decoder family** (builds foundation for 5+ mode families)

---

**Reference**: fldigi source code in `/home/corey/pydigi/fldigi/` (read-only, for implementation guidance)
