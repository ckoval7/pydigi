# Decoder API Components

This page documents the reusable decoder infrastructure components that provide building blocks for implementing digital mode decoders.

## Overview

The decoder API provides standardized, reusable components for:

- **Timing Recovery**: Extract symbols at optimal sampling points
- **Data Carrier Detect (DCD)**: Detect signal presence and measure SNR
- **Automatic Frequency Control (AFC)**: Track and correct frequency offsets
- **Sync Detection**: Detect preamble/postamble patterns
- **De-interleaving**: Reverse interleaving for FEC
- **Testing & Validation**: Add noise, measure BER/SER, profile performance

These components eliminate code duplication and ensure consistent, high-quality decoder implementations across all 22+ modem families.

!!! info "Implementation Status"
    All decoder API components are **fully implemented and tested** as of 2026-01-04. See [DECODER_API_SUMMARY.md](https://github.com/yourusername/pydigi/blob/master/DECODER_API_SUMMARY.md) for detailed documentation.

---

## Timing Recovery

::: pydigi.core.timing_recovery

### SymbolSlicer

Simple decimating symbol slicer for basic timing recovery.

```python
from pydigi.core import SymbolSlicer

# Create slicer for 4 samples per symbol
slicer = SymbolSlicer(samples_per_symbol=4)

# Process samples
symbols = slicer.process(samples)
```

**When to use:**
- Initial decoder implementations
- Strong signals with accurate timing
- Testing and validation

::: pydigi.core.timing_recovery.SymbolSlicer

---

### EarlyLateGate

Early-late gate timing recovery algorithm.

```python
from pydigi.core import EarlyLateGate

gate = EarlyLateGate(samples_per_symbol=4, loop_bw=0.01)

for sample in samples:
    symbol, ready = gate.update(sample)
    if ready:
        process_symbol(symbol)
```

**When to use:**
- CW (Morse code)
- FSK modes (RTTY, FSQ)
- Non-linear modulations

::: pydigi.core.timing_recovery.EarlyLateGate

---

### GardnerTimingRecovery

Advanced Gardner timing error detector for data-directed timing recovery.

```python
from pydigi.core import GardnerTimingRecovery

recovery = GardnerTimingRecovery(
    samples_per_symbol=4,
    loop_bw=0.01,
    damping=1.0
)

symbols = recovery.process(samples)
```

**When to use:**
- PSK (BPSK, QPSK, 8PSK)
- QAM
- Any linear modulation
- Production decoders

::: pydigi.core.timing_recovery.GardnerTimingRecovery

---

## Data Carrier Detect (DCD)

::: pydigi.core.dcd

### EnergyDCD

Energy-based data carrier detect with SNR estimation.

```python
from pydigi.core import EnergyDCD

dcd = EnergyDCD(
    threshold_db=6.0,
    attack=0.1,
    decay=0.01
)

for samples in signal_blocks:
    active, snr = dcd.update(samples)
    if active:
        print(f"Signal detected! SNR: {snr:.1f} dB")
```

**Features:**
- Automatic noise floor tracking
- Fast attack, slow decay
- Hysteresis to prevent flutter
- SNR estimation

::: pydigi.core.dcd.EnergyDCD

---

### PreambleDetector

Correlation-based preamble detection for known sync patterns.

```python
from pydigi.core import PreambleDetector
import numpy as np

# PSK31 preamble: alternating phase reversals
preamble = np.array([1, -1, 1, -1, 1, -1, 1, -1])
detector = PreambleDetector(preamble, threshold=0.8)

for symbol in symbols:
    if detector.update(symbol):
        print("Preamble detected!")
```

**When to use:**
- PSK phase reversal preambles
- RTTY LTRS character preambles
- MFSK tone sequence preambles

::: pydigi.core.dcd.PreambleDetector

---

### ToneDCD

Tone-based DCD for FSK modes using FFT analysis.

```python
from pydigi.core import ToneDCD

# For RTTY with mark=2125 Hz, space=2295 Hz
dcd = ToneDCD(
    tone_freqs=[2125, 2295],
    sample_rate=8000,
    threshold_db=10.0
)

active, tone_snr = dcd.update(samples)
```

**When to use:**
- RTTY
- FSQ
- MFSK modes

::: pydigi.core.dcd.ToneDCD

---

## Automatic Frequency Control (AFC)

::: pydigi.core.afc

### PhaseAFC

AFC for phase-based modulations (PSK, QPSK, 8PSK).

```python
from pydigi.core import PhaseAFC, NCO

afc = PhaseAFC(alpha=0.01, max_offset=100.0)
nco = NCO(frequency=1000.0, sample_rate=8000)

for sample in samples:
    # Mix down to baseband
    baseband = sample * nco.mix_down()

    # Demodulate and get phase error
    phase_error = demodulate(baseband)

    # Update AFC
    freq_offset = afc.update(phase_error)
    nco.set_frequency(1000.0 + freq_offset)
```

**Features:**
- 1st and 2nd order loop options
- Configurable tracking rate
- Max offset clamping

::: pydigi.core.afc.PhaseAFC

---

### ToneAFC

AFC for tone-based modulations (MFSK, FSQ, RTTY).

```python
from pydigi.core import ToneAFC

# For MFSK16 centered at 1500 Hz
afc = ToneAFC(center_freq=1500.0, alpha=0.05)

# Detect tone from FFT
detected_tone_freq = find_peak_frequency(fft_output)

# Update AFC
freq_offset = afc.update(detected_tone_freq)
actual_center = 1500.0 + freq_offset
```

**Features:**
- Tone frequency tracking
- Adaptive filtering
- Tone history statistics

::: pydigi.core.afc.ToneAFC

---

### PLL

Full Phase-Locked Loop for carrier tracking.

```python
from pydigi.core import PLL

pll = PLL(bandwidth=0.01, damping=0.707)

for sample in samples:
    # Get PLL output (tracking carrier)
    carrier = pll.step(sample)

    # Baseband signal
    baseband = sample * np.conj(carrier)
```

**Features:**
- 2nd-order loop filter
- Configurable bandwidth and damping
- Most sophisticated AFC option

::: pydigi.core.afc.PLL

---

## Sync Detection

::: pydigi.core.sync_detector

### SyncPattern

Define synchronization patterns for detection.

```python
from pydigi.core import SyncPattern

pattern = SyncPattern(
    pattern=[1, -1, 1, -1, 1, -1],
    name="psk_preamble",
    pattern_type="symbols"
)
```

**Pattern Types:**
- `"symbols"` - Symbol values
- `"bits"` - Bit sequences
- `"phase"` - Phase angles (radians)
- `"complex"` - Complex constellation points

::: pydigi.core.sync_detector.SyncPattern

---

### SyncDetector

Detect sync patterns using cross-correlation.

```python
from pydigi.core import SyncDetector, create_psk_preamble_pattern

preamble = create_psk_preamble_pattern(32)
detector = SyncDetector(preamble, threshold=0.8)

for symbol in symbols:
    detected, pattern_name = detector.update(symbol)
    if detected:
        print(f"Detected {pattern_name}!")
```

**Features:**
- Multiple pattern support
- Normalized correlation
- Minimum spacing between detections

::: pydigi.core.sync_detector.SyncDetector

---

### DecoderStateMachine

State machine for decoder synchronization.

```python
from pydigi.core import DecoderStateMachine, DecoderState

fsm = DecoderStateMachine()

# Transition based on events
if signal_detected:
    fsm.transition('signal_detected')  # IDLE → PREAMBLE

if preamble_found:
    fsm.transition('preamble_found')   # PREAMBLE → DATA

if postamble_found:
    fsm.transition('postamble_found')  # DATA → POSTAMBLE → IDLE
```

**States:**
- `IDLE` - No signal, waiting
- `PREAMBLE` - Detected signal, looking for preamble
- `DATA` - Decoding data
- `POSTAMBLE` - Finishing up

::: pydigi.core.sync_detector.DecoderStateMachine

---

### Helper Functions

Convenience functions for creating common preamble patterns.

```python
from pydigi.core import (
    create_psk_preamble_pattern,
    create_rtty_preamble_pattern,
    create_tone_sequence_pattern
)

# PSK31 preamble (32 phase reversals)
psk_preamble = create_psk_preamble_pattern(32)

# RTTY preamble (8 LTRS characters)
rtty_preamble = create_rtty_preamble_pattern(8)

# Custom tone sequence
tone_preamble = create_tone_sequence_pattern([0, 1, 2, 3])
```

::: pydigi.core.sync_detector.create_psk_preamble_pattern
::: pydigi.core.sync_detector.create_rtty_preamble_pattern
::: pydigi.core.sync_detector.create_tone_sequence_pattern

---

## De-interleaving

::: pydigi.core.interleave

### BlockDeinterleaver

Generic block de-interleaver for burst error protection.

```python
from pydigi.core import BlockDeinterleaver

# For a 4×4 interleaver (Olivia, Contestia)
deinterleaver = BlockDeinterleaver(rows=4, cols=4)

for symbol in received_symbols:
    ready, block = deinterleaver.push_symbol(symbol)
    if ready:
        # Process de-interleaved block
        decoded_bits = fec_decode(block)
```

**Used by:**
- Olivia (2×2, 4×4, 8×8)
- Contestia (2×2, 4×4, 8×8)
- MT63 (32×64, 64×64)
- Thor (various sizes)

::: pydigi.core.interleave.BlockDeinterleaver

---

### ConvolutionalDeinterleaver

Convolutional de-interleaver with delay lines.

```python
from pydigi.core import ConvolutionalDeinterleaver

deinterleaver = ConvolutionalDeinterleaver(branches=4, delay=10)

for symbol in symbols:
    output = deinterleaver.push_symbol(symbol)
    if output is not None:
        process_symbol(output)
```

**Features:**
- Lower latency than block interleaving
- Automatic initialization
- Used by some MFSK variants

::: pydigi.core.interleave.ConvolutionalDeinterleaver

---

## Testing & Validation

### Noise Generation

::: pydigi.utils.noise

Add realistic channel impairments for testing.

```python
from pydigi.utils import add_awgn, add_frequency_offset

# Add 10 dB SNR noise
noisy_signal = add_awgn(clean_signal, snr_db=10.0)

# Simulate 50 Hz tuning error
offset_signal = add_frequency_offset(signal, 50.0, sample_rate=8000)

# Test decoder
decoded = decoder.decode(noisy_signal)
```

**Available Functions:**

::: pydigi.utils.noise.add_awgn
::: pydigi.utils.noise.add_frequency_offset
::: pydigi.utils.noise.add_phase_noise
::: pydigi.utils.noise.add_timing_jitter
::: pydigi.utils.noise.add_multipath_fading

---

### Performance Measurements

::: pydigi.utils.measurements

Measure and characterize decoder performance.

```python
from pydigi.utils import calculate_ber, PerformanceProfiler

# BER measurement
result = calculate_ber(tx_bits, rx_bits, skip_initial=10)
print(f"BER: {result.ber:.2e} ({result.bit_errors}/{result.total_bits})")

# Performance profiling
profiler = PerformanceProfiler()
profiler.start()
decoded = decoder.decode(signal)
stats = profiler.stop(num_samples=len(signal), sample_rate=8000)
print(f"Real-time factor: {stats['realtime_factor']:.1f}x")
```

**Available Functions:**

::: pydigi.utils.measurements.calculate_ber
::: pydigi.utils.measurements.calculate_ser
::: pydigi.utils.measurements.measure_throughput
::: pydigi.utils.measurements.PerformanceProfiler
::: pydigi.utils.measurements.analyze_error_pattern

---

## See Also

- [Decoder API User Guide](../../guides/decoder-api.md) - Comprehensive guide with examples
- [PSK Decoder](psk_decoder.md) - Example decoder using these components
- [Signal Detection Guide](../../guides/signal-detection.md) - DCD and sync detection
- [DECODER_API_SUMMARY.md](https://github.com/yourusername/pydigi/blob/master/DECODER_API_SUMMARY.md) - Complete API summary
- [DECODER_INFRASTRUCTURE.md](https://github.com/yourusername/pydigi/blob/master/DECODER_INFRASTRUCTURE.md) - Design documentation
