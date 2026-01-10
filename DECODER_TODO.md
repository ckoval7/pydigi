# PyDigi Decoder Implementation TODO List

**Last Updated:** 2026-01-04

**Current Status**: 5/22 decoder families working (PSK, QPSK, 8PSK, 8PSK-FEC*, RTTY)

This list is sorted by estimated difficulty and implementation priority.

---

## ⭐ EASY - Quick Wins (Estimated: 1-3 days each)

### 1. PSK Extended (single-carrier) - ⚠️ PARTIAL
- [x] PSK1000 decoder ✅ **WORKING** (uses PSKDecoder with baud=1000)
- [ ] PSK63F decoder ⚠️ **IN PROGRESS** (dual-path Viterbi implemented, DCD issues)
- **Files**: `pydigi/modems/psk_decoder.py`, `pydigi/modems/psk63f_decoder.py`
- **Reference**: `fldigi/src/psk/psk.cxx` (rx_pskr function for PSK63F)
- **Difficulty**: ⭐ PSK1000 done, ⭐⭐⭐ PSK63F needs DCD state machine
- **Status**: PSK1000 complete. PSK63F has dual-decoder voting implemented, but DCD pattern detection not working.

#### PSK63F Investigation Notes (2026-01-09):
**Fixes Applied:**
1. ✅ Bit extraction order fixed (MSB first like fldigi: 0x08, 0x04, 0x02, 0x01)
2. ✅ Symbol pair reversal added before Viterbi (fldigi psk.cxx lines 1264-1266)
3. ⚠️ PSK-R DCD pattern detection added but NOT triggering

**Remaining Issues:**
1. **Viterbi latency**: 57-bit delay causes first characters to be lost
2. **DCD pattern not detected**: The PSK-R preamble patterns (0x0A0A0A0A, etc.) are not appearing in the decoded bit stream. The dcdshreg shows all zeros from Viterbi output during preamble.
3. **Root cause hypothesis**: The Viterbi decoder outputs all zeros during the preamble period (first ~57 bits), so the DCD pattern detection never triggers.

**Verified Working:**
- Viterbi FEC pipeline correctly decodes bits (verified with synthetic test: 120 input bits → exact match at offset 57)
- Symbol pair reversal is correct per fldigi behavior
- Bit extraction order is correct (MSB first)
- MFSK varicode decoder works correctly
- With squelch disabled, message partially decodes: "HE QUICK BROWN FOX JU..." (missing first char, corruption at end)

**Next Steps:**
1. Investigate why Viterbi outputs zeros during preamble instead of alternating pattern
2. The preamble encoder sends alternating 1/0 through FEC, which should produce patterns like 11, 01, 10, 00, 11... but Viterbi outputs all zeros
3. May need to compare encoder output vs what decoder receives at soft symbol level
4. Alternative: Use metric-based DCD instead of pattern-based (less accurate but may work)

### 2. ~~8PSK FEC Long Interleaver Variants~~ ✅ COMPLETE (2026-01-09)
- [x] Fixed 8PSK FEC silence handling issue
- [x] 8PSK125FL decoder (already implemented)
- [x] 8PSK250FL decoder (already implemented)
- **Files**: `pydigi/modems/psk8_fec_decoder.py`
- **Status**: All 7 modes working (125F/FL, 250F/FL, 500F, 1000F, 1200F)
- **Fix**: Pure silence now skipped to prevent deinterleaver corruption

### 3. CW Decoder (Morse Code) - 1-2 days
- [ ] Envelope detection (Hilbert transform)
- [ ] Threshold-based mark/space detection
- [ ] Timing analysis (dot/dash/space classification)
- [ ] Morse table lookup
- [ ] Handle variable WPM (5-200 WPM)
- **Files**: Create `pydigi/modems/cw_decoder.py`
- **Reference**: `fldigi/src/cw/cw.cxx`
- **Difficulty**: ⭐⭐ Easy

### 4. RTTY Decoder - ✅ COMPLETE
- [x] Dual Goertzel filters (mark/space tones)
- [x] Bit timing recovery
- [x] Baudot code table lookup
- [x] LTRS/FIGS shift character handling
- [x] Handle 8 baud rates (45.45-300 baud)
- **Files**: `pydigi/modems/rtty_decoder.py`
- **Reference**: `fldigi/src/rtty/rtty.cxx`
- **Difficulty**: ⭐⭐ Easy
- **Status**: ✅ Working! Loopback test passes, works down to 5 dB SNR

### 5. Throb Decoders - 1 day (all 6 modes)
- [ ] Dual-tone Goertzel filter bank
- [ ] Amplitude detection (no carrier tracking)
- [ ] Throb varicode decoding (45-char set)
- [ ] ThrobX varicode decoding (55-char set)
- [ ] Modes: Throb1, Throb2, Throb4, ThrobX1, ThrobX2, ThrobX4
- **Files**: Create `pydigi/modems/throb_decoder.py`
- **Reference**: `fldigi/src/throb/throb.cxx`
- **Difficulty**: ⭐⭐ Easy

### 6. FSQ Decoder - 3-4 days
- [ ] 33-tone Goertzel filter bank
- [ ] Symbol timing recovery
- [ ] FSQ varicode decoding
- [ ] Modes: FSQ-1.5, FSQ-2, FSQ-3, FSQ-4.5, FSQ-6
- **Files**: Create `pydigi/modems/fsq_decoder.py`
- **Reference**: `fldigi/src/fsq/fsq.cxx`
- **Difficulty**: ⭐⭐ Easy-Medium

---

## ⭐⭐⭐ MEDIUM - New Techniques (Estimated: 1-2 weeks each)

### 7. MFSK Decoders (Basic 7 modes) - 1 week
- [ ] FFT-based tone detection (sliding window)
- [ ] Symbol timing recovery
- [ ] Gray code to data bits conversion
- [ ] Viterbi FEC decoding (K=5) - already have this!
- [ ] MFSK varicode decoding
- [ ] Modes: MFSK4, MFSK8, MFSK11, MFSK16, MFSK22, MFSK31, MFSK32
- **Files**: Create `pydigi/modems/mfsk_decoder.py`
- **Reference**: `fldigi/src/mfsk/mfsk.cxx`, `pj_mfsk.h`
- **Difficulty**: ⭐⭐⭐ Medium
- **Note**: Foundation for DominoEX, Thor, Olivia, Contestia

### 8. MFSK Decoders (Large 4 modes) - 3-4 days
- [ ] Larger FFT windows (64/128 tones)
- [ ] Long interleaver buffers
- [ ] Modes: MFSK64, MFSK64L, MFSK128, MFSK128L
- **Files**: Extend `pydigi/modems/mfsk_decoder.py`
- **Reference**: `fldigi/src/mfsk/mfsk.cxx`
- **Difficulty**: ⭐⭐⭐ Medium
- **Dependency**: Basic MFSK decoder must work first

### 9. DominoEX Decoders - 1 week
- [ ] 18-tone FFT-based detection
- [ ] IFK (Incremental Frequency Keying) symbol decoding
- [ ] Viterbi FEC decoding (K=5)
- [ ] DominoEX varicode decoding
- [ ] Modes: DominoEX Micro, 4, 5, 8, 11, 16, 22, 44, 88
- **Files**: Create `pydigi/modems/dominoex_decoder.py`
- **Reference**: `fldigi/src/dominoex/dominoex.cxx`
- **Difficulty**: ⭐⭐⭐ Medium

### 10. Thor Decoders - 1 week
- [ ] 18-tone FFT-based detection
- [ ] IFK symbol decoding
- [ ] Block de-interleaving
- [ ] Viterbi FEC decoding (K=5)
- [ ] Thor varicode decoding
- [ ] Modes: Thor Micro, 4, 5, 8, 11, 16, 22, 25, 32, 44, 56, 25x4, 50x1, 50x2, 100
- **Files**: Create `pydigi/modems/thor_decoder.py`
- **Reference**: `fldigi/src/thor/thor.cxx`
- **Difficulty**: ⭐⭐⭐ Medium

### 11. Hellschreiber Decoders - 1-2 weeks
- [ ] Amplitude modes: Envelope detection + timing (Feld, Slow, X5, X9)
- [ ] FSK modes: Dual-tone detection (FSK Hell, FSK Hell-105, Hell-80)
- [ ] Pixel pattern recognition
- [ ] Character recognition from pixel columns
- [ ] Timing recovery for pixel clock
- **Files**: Create `pydigi/modems/hell_decoder.py`
- **Reference**: `fldigi/src/hell/hell.cxx`
- **Difficulty**: ⭐⭐⭐ Medium
- **Note**: Different technique (pixel-based, not symbol-based)

### 12. IFKP Decoders - 4-5 days
- [ ] FFT-based tone detection
- [ ] IFK differential decoding
- [ ] Symbol timing recovery
- [ ] IFKP character table lookup
- [ ] Modes: IFKP-0.5, IFKP-1.0, IFKP-2.0
- **Files**: Create `pydigi/modems/ifkp_decoder.py`
- **Reference**: `fldigi/src/ifkp/ifkp.cxx`
- **Difficulty**: ⭐⭐⭐ Medium

### 13. SCAMP Decoders - 1 week
- [ ] FSK modes: Multi-tone detection
- [ ] OOK modes: Amplitude detection
- [ ] SCAMP varicode decoding
- [ ] Symbol timing recovery
- [ ] Modes: SCAMPFSK, SCAMPOOK, SCFSKFST, SCFSKSLW, SCOOKSLW, SCFSKVSL
- **Files**: Create `pydigi/modems/scamp_decoder.py`
- **Reference**: `fldigi/src/scamp/scamp.cxx`
- **Difficulty**: ⭐⭐⭐⭐ Medium-Hard

---

## ⭐⭐⭐⭐ HARD - Advanced Techniques (Estimated: 2-4 weeks each)

### 14. Olivia Decoders - 2-3 weeks
- [ ] FFT-based multi-tone detection
- [ ] Walsh function decoding (Fast Hadamard Transform)
- [ ] Block de-interleaving
- [ ] Viterbi FEC decoding (K=5)
- [ ] Character assembly
- [ ] 36 configurations: 5 bandwidths × 9 tone counts (2-256 tones)
- **Files**: Create `pydigi/modems/olivia_decoder.py`
- **Reference**: `fldigi/src/olivia/olivia.cxx`, `pj_mfsk.h`, `pj_fht.h`
- **Difficulty**: ⭐⭐⭐⭐ Hard
- **Note**: Foundation for Contestia decoder

### 15. Contestia Decoders - 1 week
- [ ] Same as Olivia with different interleaver depth
- [ ] 36 configurations (same structure as Olivia)
- **Files**: Create `pydigi/modems/contestia_decoder.py` or extend Olivia
- **Reference**: `fldigi/src/contestia/contestia.cxx`
- **Difficulty**: ⭐⭐⭐⭐ Hard
- **Dependency**: Olivia decoder must work first

### 16. PSK Extended (Multi-Carrier) - 2 weeks
- [ ] N parallel PSK decoders at different frequencies
- [ ] Frequency offset management
- [ ] Symbol synchronization across carriers
- [ ] Data combining/merging logic
- [ ] Modes: 2X_PSK500, 4X_PSK500, 2X_PSK800, 2X_PSK1000, 6X_PSK250, 12X_PSK125
- **Files**: Extend `pydigi/modems/psk_decoder.py`
- **Reference**: `fldigi/src/psk/psk.cxx` (MULTI_CARRIER sections)
- **Difficulty**: ⭐⭐⭐⭐ Hard

### 17. NAVTEX/SITOR-B Decoders - 2 weeks
- [ ] FSK demodulation (170 Hz shift)
- [ ] CCIR476 code decoding
- [ ] ARQ state machine implementation
- [ ] Error detection logic
- [ ] Repeat request handling
- [ ] NAVTEX message formatting
- **Files**: Create `pydigi/modems/navtex_decoder.py`
- **Reference**: `fldigi/src/navtex/navtex.cxx`
- **Difficulty**: ⭐⭐⭐⭐ Hard
- **Note**: ARQ protocol is complex

---

## ⭐⭐⭐⭐⭐ VERY HARD - Most Complex (Estimated: 3-4 weeks)

### 18. MT63 Decoders - 3-4 weeks
- [ ] 64-carrier OFDM reception
- [ ] Per-carrier DBPSK demodulation
- [ ] Time and frequency de-interleaving
- [ ] Viterbi FEC decoding (K=5)
- [ ] Block de-interleaver (short/long variants)
- [ ] Sync sequence detection
- [ ] Modes: MT63-500S, MT63-500L, MT63-1000S, MT63-1000L, MT63-2000S, MT63-2000L
- **Files**: Create `pydigi/modems/mt63_decoder.py`
- **Reference**: `fldigi/src/mt63/mt63.cxx`
- **Difficulty**: ⭐⭐⭐⭐⭐ Very Hard
- **Note**: Most complex decoder - 64-carrier OFDM

---

## 🎨 SPECIAL - Image Mode (Estimated: 1-2 weeks)

### 19. WEFAX Decoders - 1-2 weeks
- [ ] AM demodulation (1500 Hz = black, 2300 Hz = white)
- [ ] Scanline synchronization (675 Hz start, 450 Hz phasing)
- [ ] IOC576/IOC288 standards implementation
- [ ] Image buffer assembly (grayscale scanlines)
- [ ] Output to PNG/BMP files
- [ ] Modes: WEFAX-576, WEFAX-288
- **Files**: Create `pydigi/modems/wefax_decoder.py`
- **Reference**: `fldigi/src/wefax/wefax.cxx`
- **Difficulty**: ⭐⭐⭐⭐ Hard (different domain)
- **Note**: Lower priority - image transmission, not text

---

## 🔧 Infrastructure Needed

Before starting medium/hard decoders, consider building these reusable components:

### Timing and Synchronization
- [ ] AFC (Automatic Frequency Control) class
- [ ] Symbol timing recovery class (Gardner, Mueller-Muller, etc.)
- [ ] DCD (Data Carrier Detect) helper
- [ ] Preamble/postamble detection utilities

### De-interleaving
- [ ] Block de-interleaver class (for Olivia, Contestia, Thor, MT63)
- [ ] Convolutional de-interleaver class (for some MFSK modes)

### Testing Utilities
- [ ] AWGN (Additive White Gaussian Noise) generator
- [ ] SNR measurement utilities
- [ ] BER (Bit Error Rate) calculator
- [ ] Loopback test framework (TX → RX validation)

---

## 📊 Progress Tracking

**Completed Decoders**: 5/22 families (22.7%)
- ✅ PSK (6 modes)
- ✅ QPSK (5 modes)
- ✅ 8PSK (4 modes)
- ✅ 8PSK FEC (7 modes - **FIXED 2026-01-09**)
- ✅ RTTY (supports all baud rates: 45, 45.45, 50, 56, 75, 100, 110, 150, 200, 300)
- ✅ Throb (6 modes)

**Next Milestone**: Complete PSK family (item 1: PSK Extended single-carrier modes)

**Current Blockers**: None

**Estimated Total Effort**:
- Easy modes (6): ~2 weeks
- Medium modes (7): ~10 weeks
- Hard modes (4): ~9 weeks
- Very hard modes (1): ~4 weeks
- Special modes (1): ~2 weeks
- **Total**: ~27 weeks (6-7 months) for all decoders

---

## 🎯 Recommended Implementation Order

1. ~~**Fix 8PSK FEC**~~ ✅ COMPLETE (2026-01-09)
2. **PSK Extended single-carrier modes** (complete PSK family - highest utility)
3. **FSQ** (easy, commonly used for keyboard-to-keyboard)
4. **Throb + FSQ** (easy, build momentum)
5. **MFSK basic** (foundation for multiple mode families)
6. **DominoEX + Thor** (build on MFSK foundation)
7. **MFSK large + IFKP** (complete MFSK family)
8. **Hellschreiber** (unique technique)
9. **Olivia + Contestia** (tackle together, share code)
10. **SCAMP** (less common, but not too hard)
11. **PSK Extended multi-carrier** (complex but useful)
12. **MT63** (most complex, save for last)
13. **NAVTEX/SITOR-B** (ARQ protocol)
14. **WEFAX** (special case, can be done anytime)
