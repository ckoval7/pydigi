# Decoder Infrastructure Components

**Last Updated:** 2026-01-04

This document details the reusable decoder components needed for implementing the remaining 18 decoder families. These components will be shared across multiple decoders to avoid code duplication and ensure consistent behavior.

---

## Overview

Many decoders share common DSP building blocks. Rather than reimplementing these in each decoder, we should build reusable classes that can be configured and composed.

**Current Decoder Components** (already implemented):
- ✅ NCO (Numerically Controlled Oscillator) - `pydigi/core/oscillator.py`
- ✅ FIR Filter with decimation - `pydigi/core/filters.py`
- ✅ Goertzel DFT Filter - `pydigi/core/filters.py`
- ✅ Moving Average Filter - `pydigi/core/filters.py`
- ✅ FFT operations - `pydigi/core/fft.py`
- ✅ Viterbi FEC Decoder - `pydigi/core/viterbi.py`
- ✅ Varicode tables - `pydigi/varicode/*.py`

**Missing Components** (need to implement):
- 📋 AFC (Automatic Frequency Control)
- 📋 Symbol Timing Recovery
- 📋 DCD (Data Carrier Detect)
- 📋 Preamble/Postamble Detection
- 📋 De-interleavers (Block and Convolutional)
- 📋 Testing/Validation Utilities

---

## 1. AFC (Automatic Frequency Control)

### What It Does
Tracks and corrects for frequency offset between transmitter and receiver. Radios may be slightly off-frequency due to:
- Oscillator drift (temperature, aging)
- Doppler shift (moving stations)
- Operator tuning error

AFC continuously adjusts the receiver's center frequency to lock onto the actual signal frequency.

### Why It's Needed
Most real-world signals have 5-50 Hz of frequency error. Without AFC:
- Phase-based decoders (PSK, QPSK, 8PSK) accumulate phase error and fail
- Tone-based decoders (MFSK, RTTY, FSQ) detect wrong tones
- The decoder must tolerate this drift over time

### How It Works

**Approach 1: Phase-Based AFC (for PSK family)**
```
1. Track phase change rate over multiple symbols
2. Phase drift = frequency offset × time
3. Estimate offset: freq_error = phase_drift / (2π × symbol_period)
4. Update NCO frequency to compensate
```

**Approach 2: Tone-Based AFC (for MFSK family)**
```
1. Detect strongest tone in FFT
2. Compare to expected tone center frequency
3. Offset = detected_freq - expected_freq
4. Adjust receiver center frequency
```

**Approach 3: PLL (Phase-Locked Loop)**
```
1. Use phase detector to measure error
2. Loop filter smooths error signal
3. NCO adjusts frequency based on filtered error
4. Classic feedback control system
```

### Implementation Plan

**File**: `pydigi/core/afc.py`

**Classes**:
```python
class PhaseAFC:
    """AFC for phase-based modes (PSK, QPSK, 8PSK)"""
    def __init__(self, alpha=0.01, max_offset=100.0):
        self.alpha = alpha  # Tracking rate (low = slow, stable)
        self.max_offset = max_offset  # Hz
        self.freq_offset = 0.0

    def update(self, phase_error):
        """Update frequency offset estimate from phase error"""
        self.freq_offset += self.alpha * phase_error
        self.freq_offset = np.clip(self.freq_offset, -self.max_offset, self.max_offset)
        return self.freq_offset

class ToneAFC:
    """AFC for tone-based modes (MFSK, FSQ, RTTY)"""
    def __init__(self, center_freq, alpha=0.05, max_offset=50.0):
        self.center_freq = center_freq
        self.alpha = alpha
        self.max_offset = max_offset
        self.freq_offset = 0.0

    def update(self, detected_freq):
        """Update offset from detected tone frequency"""
        error = detected_freq - self.center_freq
        self.freq_offset += self.alpha * error
        self.freq_offset = np.clip(self.freq_offset, -self.max_offset, self.max_offset)
        return self.freq_offset

class PLL:
    """Phase-Locked Loop for carrier tracking"""
    def __init__(self, bandwidth, damping=0.707):
        # Classic 2nd-order PLL
        # See: Gardner, "Phaselock Techniques" 3rd ed.
        pass
```

### Used By
- **All PSK decoders**: PSK, QPSK, 8PSK, PSK Extended (16 modes)
- **All MFSK decoders**: MFSK, DominoEX, Thor, Olivia, Contestia (70+ modes)
- **FSK decoders**: RTTY, FSQ, IFKP, SCAMP (15+ modes)
- **OFDM decoders**: MT63 (6 modes)

**Total**: Used by ~100+ modes across all families

### Priority
**HIGH** - Should implement early. Almost every decoder needs this.

### Reference
- fldigi source: Look for `afcmetric`, `freqerr`, `set_freq()` calls
- `fldigi/src/psk/psk.cxx`: Lines with `afcmetric`, `frequency` adjustments
- `fldigi/src/mfsk/mfsk.cxx`: Tone tracking logic
- Classic DSP textbooks: Gardner, Lyons, Proakis

---

## 2. Symbol Timing Recovery

### What It Does
Determines the optimal sampling instant for each symbol. The receiver doesn't know:
- Exactly when symbols start/end (timing offset)
- Exact symbol rate (clock drift between TX and RX)

Symbol timing recovery finds and tracks the symbol boundaries.

### Why It's Needed
Sampling at the wrong time causes:
- **ISI (Inter-Symbol Interference)**: Adjacent symbols bleed together
- **Reduced SNR**: Sampling during transitions instead of stable regions
- **Bit errors**: Even with perfect frequency lock

Modern decoders need timing accuracy to within ~5-10% of symbol period.

### How It Works

**Approach 1: Early-Late Gate**
```
1. Take 3 samples per symbol: early, on-time, late
2. Compare energy: |early|² vs |late|²
3. If early > late: sample clock is late, advance
4. If late > early: sample clock is early, retard
5. Adjust sampling phase accordingly
```

**Approach 2: Gardner Timing Error Detector**
```
1. Take samples at rate 2× symbol rate
2. At symbol k: prev = x[k-1], curr = x[k], next = x[k+1]
3. Error = real(curr) × (real(prev) - real(next))
4. Positive error → clock is late
5. Feed error to loop filter, adjust NCO phase
```

**Approach 3: Mueller & Müller**
```
For data-directed timing recovery:
1. Use known/decided symbol values
2. Error = real(x[k]) × imag(x[k-1]) - imag(x[k]) × real(x[k-1])
3. More robust with low SNR
```

**Approach 4: Peak Detection** (for CW, RTTY, simple modes)
```
1. Detect signal envelope
2. Find rising/falling edges
3. Track edge timing
4. Derive symbol clock from edge spacing
```

### Implementation Plan

**File**: `pydigi/core/timing_recovery.py`

**Classes**:
```python
class GardnerTimingRecovery:
    """Gardner timing error detector - works for PSK, QAM, etc."""
    def __init__(self, samples_per_symbol, loop_bw=0.01):
        self.sps = samples_per_symbol
        self.loop_bw = loop_bw
        self.mu = 0.0  # Timing phase (0-1)
        self.omega = samples_per_symbol  # Clock period
        self.gain_mu = 0.175  # Timing gain
        self.gain_omega = 0.25 * gain_mu * gain_mu  # Frequency gain

    def update(self, samples):
        """
        Process samples, return symbol samples and timing info
        Uses interpolator to get samples at mu + k*omega
        """
        pass

class EarlyLateGate:
    """Simple early-late timing recovery"""
    def __init__(self, samples_per_symbol):
        self.sps = samples_per_symbol
        self.timing_offset = 0.0

    def update(self, samples):
        """Compare early vs late energy, adjust timing"""
        pass

class SymbolSlicer:
    """
    Simple decimating symbol slicer
    Just takes every Nth sample - no timing recovery
    Good for strong signals with accurate clocks
    """
    def __init__(self, samples_per_symbol):
        self.sps = samples_per_symbol
        self.phase = 0

    def update(self, samples):
        """Return symbols by decimation"""
        symbols = []
        for i, sample in enumerate(samples):
            self.phase += 1
            if self.phase >= self.sps:
                symbols.append(sample)
                self.phase = 0
        return np.array(symbols)
```

### Used By
- **All PSK decoders**: PSK, QPSK, 8PSK (16 modes)
- **All MFSK decoders**: MFSK, DominoEX, Thor, Olivia, Contestia (70+ modes)
- **FSK decoders**: RTTY, FSQ, IFKP, SCAMP (15+ modes)
- **Other**: CW, Throb, Hellschreiber (13 modes)

**Total**: All decoders need some form of timing recovery

### Priority
**HIGH** - Critical for medium/hard decoders. Simple decoders can use basic decimation.

### Reference
- **Paper**: "A BPSK/QPSK Timing-Error Detector for Sampled Receivers" - Gardner (1986)
- **Book**: "Digital Communications" - Proakis, Chapter 6
- **fldigi**: `fldigi/src/include/modem.h`, search for timing recovery in each mode
- **GNU Radio**: `gr-digital/lib/symbol_sync_cc_impl.cc`

---

## 3. DCD (Data Carrier Detect)

### What It Does
Detects when a signal is present vs. when there's just noise. Provides:
- **Signal detection**: Is someone transmitting?
- **SNR estimation**: How strong is the signal?
- **Squelch control**: Suppress decoding during noise-only periods

### Why It's Needed
Without DCD:
- Decoder tries to decode noise → garbage output
- No way to know when message starts/ends
- Can't measure signal quality
- Wastes CPU processing noise

### How It Works

**Approach 1: Energy Detector**
```
1. Measure average signal power over window
2. Compare to noise floor estimate
3. If power > threshold × noise_floor: DCD = TRUE
4. Use hysteresis to prevent flutter
```

**Approach 2: Correlation-Based**
```
1. Look for known patterns (preamble, sync words)
2. Correlate incoming signal with expected pattern
3. If correlation peak > threshold: DCD = TRUE
4. More robust, but requires known sequence
```

**Approach 3: Tone Detection** (for FSK modes)
```
1. Check if expected tones are present
2. Use Goertzel filters or FFT
3. If tone SNR > threshold: DCD = TRUE
```

### Implementation Plan

**File**: `pydigi/core/dcd.py`

**Classes**:
```python
class EnergyDCD:
    """Simple energy-based data carrier detect"""
    def __init__(self, threshold=6.0, attack=0.1, decay=0.01):
        self.threshold_db = threshold  # dB above noise
        self.attack = attack  # Fast attack
        self.decay = decay    # Slow decay
        self.noise_floor = 1e-6
        self.signal_power = 0.0

    def update(self, samples):
        """
        Update DCD state from samples
        Returns: (dcd_active, snr_db)
        """
        power = np.mean(np.abs(samples)**2)

        # Update noise floor (slow decay, no attack during signal)
        if power < self.noise_floor * 10:
            self.noise_floor = (1-self.decay)*self.noise_floor + self.decay*power

        # Update signal power (fast attack, slow decay)
        if power > self.signal_power:
            self.signal_power = (1-self.attack)*self.signal_power + self.attack*power
        else:
            self.signal_power = (1-self.decay)*self.signal_power + self.decay*power

        snr_linear = self.signal_power / (self.noise_floor + 1e-10)
        snr_db = 10 * np.log10(snr_linear)

        dcd_active = snr_db > self.threshold_db

        return dcd_active, snr_db

class PreambleDetector:
    """Correlation-based preamble detection"""
    def __init__(self, preamble_symbols, threshold=0.8):
        self.preamble = np.array(preamble_symbols)
        self.threshold = threshold
        self.buffer = []

    def update(self, symbol):
        """
        Check if buffer matches preamble
        Returns: True if preamble detected
        """
        self.buffer.append(symbol)
        if len(self.buffer) > len(self.preamble):
            self.buffer.pop(0)

        if len(self.buffer) == len(self.preamble):
            correlation = np.abs(np.correlate(self.buffer, self.preamble)[0])
            normalized = correlation / len(self.preamble)
            return normalized > self.threshold

        return False
```

### Used By
- **All decoders**: Every decoder needs to know when signal is present
- **Especially important for**:
  - CW (detect key-down vs key-up)
  - RTTY, FSQ (detect mark/space tones)
  - PSK family (detect carrier presence)
  - MFSK family (detect tone presence)

**Total**: All 22 decoder families

### Priority
**MEDIUM** - Nice to have early, but simple decoders can work without it initially. Can start with basic energy detection and enhance later.

### Reference
- fldigi: Search for `metric`, `s2n` (signal-to-noise), `squelch`
- `fldigi/src/psk/psk.cxx`: `afcmetric` is a combined AFC + DCD metric
- Classic radar: Constant False Alarm Rate (CFAR) detectors

---

## 4. Preamble/Postamble Detection

### What It Does
Identifies the start and end of messages by detecting known sync patterns:
- **Preamble**: Sent before data to help receiver synchronize
- **Postamble**: Sent after data to signal end of transmission

### Why It's Needed
Many modes send specific patterns for sync:
- **PSK31**: 32 phase reversals (0° to 180° repeatedly)
- **QPSK**: Specific bit patterns
- **MFSK**: Specific tone sequences
- **RTTY**: LTRS characters (0x1F)

Detecting these helps:
- Know when to start decoding data
- Distinguish preamble from actual message
- Detect end of transmission
- Improve timing/frequency lock before data

### How It Works

**Pattern Matching Approach**:
```
1. Define expected preamble pattern (symbol sequence)
2. Maintain sliding window buffer of received symbols
3. Correlate buffer with expected pattern
4. If correlation > threshold: preamble detected
5. Switch from "sync" mode to "data" mode
```

**State Machine Approach**:
```
States: IDLE → PREAMBLE → DATA → POSTAMBLE → IDLE

IDLE:
  - Wait for energy/DCD
  - When signal detected → PREAMBLE

PREAMBLE:
  - Look for known sync pattern
  - Update AFC/timing aggressively
  - When pattern detected → DATA

DATA:
  - Decode characters
  - If postamble pattern detected → POSTAMBLE
  - If signal lost → IDLE

POSTAMBLE:
  - Verify end pattern
  - Flush buffers
  - → IDLE
```

### Implementation Plan

**File**: `pydigi/core/sync_detector.py`

**Classes**:
```python
class SyncPattern:
    """Defines a synchronization pattern"""
    def __init__(self, pattern, name="sync"):
        self.pattern = np.array(pattern)
        self.name = name
        self.length = len(pattern)

class SyncDetector:
    """Detects known sync patterns in symbol stream"""
    def __init__(self, patterns, threshold=0.8):
        """
        patterns: list of SyncPattern objects or single pattern
        threshold: correlation threshold (0-1)
        """
        if isinstance(patterns, SyncPattern):
            patterns = [patterns]
        self.patterns = patterns
        self.threshold = threshold
        self.buffers = {p.name: [] for p in patterns}

    def update(self, symbol):
        """
        Check if any pattern is detected
        Returns: (detected, pattern_name) or (False, None)
        """
        for pattern in self.patterns:
            buf = self.buffers[pattern.name]
            buf.append(symbol)

            if len(buf) > pattern.length:
                buf.pop(0)

            if len(buf) == pattern.length:
                corr = self._correlate(buf, pattern.pattern)
                if corr > self.threshold:
                    # Clear buffer after detection
                    self.buffers[pattern.name] = []
                    return True, pattern.name

        return False, None

    def _correlate(self, buf, pattern):
        """Compute normalized correlation"""
        # For phase symbols: correlation of angles
        # For amplitude: correlation of magnitudes
        # Implementation depends on symbol type
        pass

class DecoderStateMachine:
    """State machine for decoder synchronization"""
    def __init__(self):
        self.state = 'IDLE'
        self.states = ['IDLE', 'PREAMBLE', 'DATA', 'POSTAMBLE']

    def update(self, event):
        """
        Update state based on event
        events: 'signal_detected', 'preamble_found', 'postamble_found', 'signal_lost'
        """
        if self.state == 'IDLE' and event == 'signal_detected':
            self.state = 'PREAMBLE'
        elif self.state == 'PREAMBLE' and event == 'preamble_found':
            self.state = 'DATA'
        elif self.state == 'DATA' and event == 'postamble_found':
            self.state = 'POSTAMBLE'
        elif event == 'signal_lost':
            self.state = 'IDLE'

        return self.state
```

### Used By
- **PSK family**: PSK, QPSK, 8PSK all use phase reversal preambles (16 modes)
- **MFSK family**: DominoEX, Thor have specific preamble tones (24 modes)
- **RTTY**: LTRS character preamble (9 modes)
- **FSQ**: Specific preamble sequences (5 modes)
- **Others**: MT63, Olivia, Contestia have sync patterns (42+ modes)

**Total**: ~96+ modes use preamble/postamble

### Priority
**MEDIUM** - Important for robust decoding, but simple decoders can work without explicit detection. Can be added incrementally.

### Reference
- Check CLAUDE.md: "CRITICAL IMPLEMENTATION REQUIREMENTS" section on preamble/postamble
- fldigi: Search for `preamble`, `postamble`, `tx_init`, `tx_flush` in each mode's .cxx
- Example: `fldigi/src/psk/psk.cxx` line ~440: `preamble = dcdbits;`

---

## 5. De-interleavers

### What It Does
Reverses the interleaving applied by the transmitter. Interleaving spreads consecutive bits across time/frequency to combat burst errors.

**Example**: Without interleaving, a 0.1s noise burst destroys 10 consecutive bits → uncorrectable.
With interleaving, those 10 bits are spread across 1 second → only 1 bit error per 100ms block → FEC can correct.

### Why It's Needed
Many modes use interleaving for robustness:
- **Block Interleaving**: Olivia, Contestia, MT63, Thor
- **Convolutional Interleaving**: Some MFSK variants

The decoder must de-interleave before FEC decoding.

### Types of Interleavers

**Block Interleaver**:
```
Write bits in row-major order into matrix
Read bits in column-major order for transmission

Transmit order: col0[all rows], col1[all rows], ...
Receive: Fill matrix column-by-column
De-interleave: Read row-by-row

Example 4×4:
Original:  0  1  2  3      Transmit:  0 4  8 12
           4  5  6  7                 1 5  9 13
           8  9 10 11                 2 6 10 14
          12 13 14 15                 3 7 11 15
```

**Convolutional Interleaver**:
```
Uses delay lines of increasing length
Each bit path has different delay: 0, D, 2D, 3D, ...
At receiver, reverse delays to reconstruct
More complex but lower latency than block
```

### Implementation Plan

**File**: `pydigi/core/interleaver.py`

**Classes**:
```python
class BlockDeinterleaver:
    """Block de-interleaver for burst error protection"""
    def __init__(self, rows, cols):
        """
        rows: number of rows in interleaver matrix
        cols: number of columns
        Block size = rows × cols bits
        """
        self.rows = rows
        self.cols = cols
        self.block_size = rows * cols
        self.matrix = np.zeros((rows, cols), dtype=int)
        self.col_index = 0
        self.row_index = 0
        self.bits_in = 0

    def push_bit(self, bit):
        """
        Add one bit to de-interleaver
        Returns: (ready, deinterleaved_block) or (False, None)
        """
        # Fill column-by-column (reverse of transmitter)
        self.matrix[self.row_index, self.col_index] = bit
        self.row_index += 1

        if self.row_index >= self.rows:
            self.row_index = 0
            self.col_index += 1

        if self.col_index >= self.cols:
            # Block complete, read row-by-row
            deinterleaved = self.matrix.flatten('C')  # C-order = row-major
            self.col_index = 0
            return True, deinterleaved

        return False, None

    def push_bits(self, bits):
        """Push multiple bits, return completed blocks"""
        blocks = []
        for bit in bits:
            ready, block = self.push_bit(bit)
            if ready:
                blocks.append(block)
        return blocks

class ConvolutionalDeinterleaver:
    """Convolutional de-interleaver (less common, more complex)"""
    def __init__(self, branches, delay):
        """
        branches: number of parallel branches
        delay: delay increment (samples or bits)
        """
        self.branches = branches
        self.delay = delay
        # Each branch has a FIFO of length (branch_num * delay)
        self.fifos = [collections.deque(maxlen=i*delay if i > 0 else 1)
                      for i in range(branches)]
        self.branch_index = 0

    def push_symbol(self, symbol):
        """
        De-interleave one symbol
        Returns: de-interleaved symbol
        """
        fifo = self.fifos[self.branch_index]

        # Push new symbol, get delayed symbol
        if len(fifo) < fifo.maxlen:
            fifo.append(symbol)
            output = 0  # Not ready yet
        else:
            fifo.append(symbol)
            output = fifo.popleft()

        self.branch_index = (self.branch_index + 1) % self.branches
        return output
```

### Used By

**Block De-interleaver**:
- **Olivia**: 2×2, 4×4, 8×8 blocks depending on mode (36 configs)
- **Contestia**: Similar to Olivia (36 configs)
- **MT63**: 32×64 or 64×64 interleaver (6 modes)
- **Thor**: Various sizes (15 modes)

**Convolutional De-interleaver**:
- Some MFSK variants (4 modes)

**Total**: ~97 modes need de-interleaving

### Priority
**MEDIUM-HIGH** - Not needed for easy decoders, but essential for:
- Olivia/Contestia (hard)
- MT63 (very hard)
- Thor (medium)

Should implement before starting Olivia/Contestia/MT63.

### Reference
- **Paper**: "Optimal Interleaving Schemes for Block and Convolutional Codes" - Ramsey (1970)
- **fldigi**:
  - Olivia: `fldigi/src/olivia/olivia.cxx` - search for `Interleave`
  - MT63: `fldigi/src/mt63/mt63.cxx` - look for interleaver dimensions
  - Thor: `fldigi/src/thor/thor.cxx` - interleaver setup
- **Reference**: `pj_mfsk.h` has interleaver code for Olivia

---

## 6. Testing and Validation Utilities

### What's Needed

These aren't decoder components per se, but essential infrastructure for validating decoders work correctly.

### 6.1 AWGN (Additive White Gaussian Noise) Generator

**What**: Adds realistic noise to test signals
**Why**: Verify decoders work at various SNR levels
**File**: `pydigi/utils/noise.py`

```python
def add_awgn(signal, snr_db):
    """
    Add white Gaussian noise to achieve target SNR

    Args:
        signal: Input signal (complex or real)
        snr_db: Desired signal-to-noise ratio in dB

    Returns:
        Noisy signal
    """
    signal_power = np.mean(np.abs(signal)**2)
    snr_linear = 10**(snr_db/10)
    noise_power = signal_power / snr_linear

    if np.iscomplexobj(signal):
        noise = np.sqrt(noise_power/2) * (np.random.randn(len(signal)) +
                                          1j*np.random.randn(len(signal)))
    else:
        noise = np.sqrt(noise_power) * np.random.randn(len(signal))

    return signal + noise
```

### 6.2 SNR Measurement

**What**: Measure signal-to-noise ratio of received signal
**Why**: Characterize decoder performance vs SNR
**File**: `pydigi/utils/measurements.py`

```python
def estimate_snr(signal, noise_only_samples=None):
    """
    Estimate SNR of signal

    Methods:
    1. If noise_only_samples provided: direct measurement
    2. Otherwise: use signal variance estimation
    """
    pass
```

### 6.3 BER (Bit Error Rate) Calculator

**What**: Compare transmitted bits to received bits, count errors
**Why**: Standard metric for decoder performance
**File**: `pydigi/utils/measurements.py`

```python
def calculate_ber(tx_bits, rx_bits, skip_initial=0):
    """
    Calculate bit error rate

    Args:
        tx_bits: Transmitted bit sequence
        rx_bits: Received bit sequence
        skip_initial: Skip first N bits (for synchronization)

    Returns:
        (errors, total_bits, ber)
    """
    # Handle length mismatch
    # Count bit errors
    # Return statistics
    pass
```

### 6.4 Loopback Test Framework

**What**: Automated TX → RX testing
**Why**: Verify encode/decode cycles work perfectly
**File**: `pydigi/tests/test_loopback.py`

```python
class LoopbackTester:
    """Framework for testing TX → RX cycles"""

    def test_mode(self, mode_name, test_text, snr_db=None):
        """
        1. Encode test_text using TX modem
        2. Optionally add noise
        3. Decode using RX modem
        4. Compare decoded text to original
        5. Report: success, errors, SNR threshold
        """
        pass
```

### 6.5 Performance Profiler

**What**: Measure decoder CPU/memory usage
**Why**: Ensure decoders are efficient enough for real-time
**File**: `pydigi/utils/profiler.py`

```python
class DecoderProfiler:
    """Profile decoder performance"""

    def profile_decoder(self, decoder, test_signal, duration=10.0):
        """
        Measure:
        - Samples processed per second
        - CPU usage
        - Memory footprint
        - Latency (input to output delay)

        Returns: Performance report
        """
        pass
```

### Priority
**MEDIUM** - Very useful for development and validation, but not blocking decoder implementation. Can build incrementally as needed.

---

## Implementation Priority and Order

### Phase 1: Essential (Do First)
1. **SymbolSlicer** (simple decimating slicer) - Needed immediately for basic decoders
2. **EnergyDCD** (basic DCD) - Helps with all decoders
3. **AWGN generator** - For testing
4. **Loopback test framework** - For validation

### Phase 2: Important (Do Soon)
5. **PhaseAFC** - Needed for PSK family completion
6. **ToneAFC** - Needed for MFSK/FSK decoders
7. **GardnerTimingRecovery** - Better than simple slicer
8. **SyncDetector** - Improves robustness
9. **BER calculator** - For validation

### Phase 3: Advanced (Do Before Hard Modes)
10. **BlockDeinterleaver** - Required for Olivia, Contestia, MT63, Thor
11. **PreambleDetector** - Improves sync
12. **PLL** - More robust than simple AFC
13. **ConvolutionalDeinterleaver** - Needed for some modes
14. **Performance profiler** - Optimization

---

## Summary

**Already Have** (7 components):
- NCO, FIR Filter, Goertzel, Moving Average, FFT, Viterbi, Varicode

**Need to Build** (14 components):
- Phase AFC, Tone AFC, PLL (3)
- Gardner Timing, Early-Late, Symbol Slicer (3)
- Energy DCD, Preamble Detector (2)
- Sync Detector, State Machine (2)
- Block Deinterleaver, Convolutional Deinterleaver (2)
- AWGN, BER calculator (2)

**Estimated Effort**:
- Phase 1 (4 components): 1-2 days
- Phase 2 (5 components): 3-4 days
- Phase 3 (5 components): 3-4 days
- **Total**: ~1-2 weeks to build all infrastructure

**Recommended Approach**:
1. Build Phase 1 components now (before starting more decoders)
2. Build Phase 2 components as you start MFSK/FSK decoders
3. Build Phase 3 components before attempting Olivia/Contestia/MT63

This infrastructure investment will make all subsequent decoders much easier to implement and ensure consistent, high-quality results.
