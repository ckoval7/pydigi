# Decoder API User Guide

This guide shows you how to use PyDigi's decoder API components to build robust digital mode decoders.

## Overview

The decoder API provides reusable building blocks that handle common tasks:

- **Timing Recovery** - Extract symbols at the right moment
- **Frequency Tracking** - Lock onto the signal frequency
- **Signal Detection** - Know when a signal is present
- **Synchronization** - Find message start/end
- **Error Correction** - De-interleave and decode FEC
- **Testing** - Validate your decoder

!!! tip "Complete Reference"
    See the [Decoder API Reference](../api/reference/decoder_api.md) for detailed API documentation.

---

## Quick Start

Here's a minimal decoder using the API components:

```python
from pydigi.core import (
    SymbolSlicer,
    EnergyDCD,
    PhaseAFC
)
import numpy as np

class SimpleDecoder:
    def __init__(self, sample_rate=8000, carrier_freq=1000.0, baud_rate=31.25):
        # Calculate samples per symbol
        self.sps = int(sample_rate / baud_rate)

        # Timing recovery (simple decimation)
        self.slicer = SymbolSlicer(samples_per_symbol=self.sps)

        # Signal detection
        self.dcd = EnergyDCD(threshold_db=6.0)

        # Frequency tracking
        self.afc = PhaseAFC(alpha=0.01, max_offset=100.0)

    def decode(self, samples):
        # Check for signal
        active, snr = self.dcd.update(samples)

        if not active:
            return ""  # No signal

        # Extract symbols
        symbols = self.slicer.process(samples)

        # Decode symbols to text
        text = self.decode_symbols(symbols)

        return text
```

---

## Building a Complete Decoder

Let's build a full-featured PSK decoder step by step.

### Step 1: Setup Components

```python
from pydigi.core import (
    NCO,
    FIRFilter,
    GardnerTimingRecovery,
    EnergyDCD,
    PhaseAFC,
    SyncDetector,
    DecoderStateMachine,
    DecoderState,
    create_psk_preamble_pattern
)
from pydigi.varicode import PSKVaricode

class PSKDecoder:
    def __init__(self, sample_rate=8000, carrier_freq=1000.0, baud_rate=31.25):
        self.sample_rate = sample_rate
        self.carrier_freq = carrier_freq
        self.baud_rate = baud_rate
        self.sps = int(sample_rate / baud_rate)

        # NCO for frequency conversion
        self.nco = NCO(frequency=carrier_freq, sample_rate=sample_rate)

        # Matched filter
        self.filter = FIRFilter(
            filter_type='lowpass',
            cutoff=baud_rate * 1.2,
            sample_rate=sample_rate,
            num_taps=64
        )

        # Timing recovery
        self.timing = GardnerTimingRecovery(
            samples_per_symbol=self.sps,
            loop_bw=0.01
        )

        # DCD
        self.dcd = EnergyDCD(threshold_db=6.0, attack=0.1, decay=0.01)

        # AFC
        self.afc = PhaseAFC(alpha=0.01, max_offset=100.0)

        # Preamble detection
        preamble_pattern = create_psk_preamble_pattern(32)
        self.preamble_detector = SyncDetector(preamble_pattern, threshold=0.8)

        # State machine
        self.state_machine = DecoderStateMachine()

        # Varicode decoder
        self.varicode = PSKVaricode()

        # State
        self.prev_phase = 0.0
        self.decoded_text = ""
```

### Step 2: Signal Processing Pipeline

```python
    def process_samples(self, samples):
        """Process a block of samples."""
        results = []

        for sample in samples:
            # 1. Mix down to baseband
            baseband = sample * self.nco.mix_down()

            # 2. Apply matched filter
            filtered = self.filter.filter(baseband)

            # 3. Update DCD
            active, snr = self.dcd.update([filtered])

            # 4. Update state machine
            if active and self.state_machine.state == DecoderState.IDLE:
                self.state_machine.transition('signal_detected')
            elif not active and self.state_machine.state != DecoderState.IDLE:
                self.state_machine.transition('signal_lost')

            # 5. Symbol timing recovery
            symbol, ready = self.timing._update(filtered)

            if ready:
                result = self.process_symbol(symbol)
                if result:
                    results.append(result)

        return ''.join(results)

    def process_symbol(self, symbol):
        """Process one symbol."""
        # Get phase
        phase = np.angle(symbol)

        # State-dependent processing
        state = self.state_machine.state

        if state == DecoderState.PREAMBLE:
            # Look for preamble
            detected, _ = self.preamble_detector.update(symbol)
            if detected:
                self.state_machine.transition('preamble_found')
                return None

        elif state == DecoderState.DATA:
            # Differential phase detection
            delta_phase = phase - self.prev_phase

            # Wrap to [-π, π]
            while delta_phase > np.pi:
                delta_phase -= 2 * np.pi
            while delta_phase < -np.pi:
                delta_phase += 2 * np.pi

            # Update AFC
            freq_offset = self.afc.update(delta_phase)
            self.nco.set_frequency(self.carrier_freq + freq_offset)

            # Decode bit (BPSK: phase change > π/2 = 1, else = 0)
            bit = 1 if abs(delta_phase) > np.pi / 2 else 0

            # Decode varicode
            char = self.varicode.decode_bit(bit)
            if char:
                return char

        self.prev_phase = phase
        return None
```

---

## Common Patterns

### Pattern 1: DCD-Gated Processing

Only process symbols when a signal is present:

```python
from pydigi.core import EnergyDCD

class DCDGatedDecoder:
    def __init__(self):
        self.dcd = EnergyDCD(threshold_db=6.0)
        self.active = False

    def decode(self, samples):
        # Update DCD
        self.active, snr = self.dcd.update(samples)

        if not self.active:
            return ""  # No signal, skip processing

        # Signal present - process it
        return self.process_signal(samples)
```

### Pattern 2: AFC Loop

Track and correct frequency offset:

```python
from pydigi.core import PhaseAFC, NCO

class AFCDecoder:
    def __init__(self, carrier_freq, sample_rate):
        self.nco = NCO(frequency=carrier_freq, sample_rate=sample_rate)
        self.afc = PhaseAFC(alpha=0.01)
        self.carrier_freq = carrier_freq

    def process_sample(self, sample):
        # Mix to baseband
        baseband = sample * self.nco.mix_down()

        # Demodulate and get phase error
        phase_error = self.demodulate(baseband)

        # Update AFC
        freq_offset = self.afc.update(phase_error)

        # Apply correction
        self.nco.set_frequency(self.carrier_freq + freq_offset)

        return baseband
```

### Pattern 3: State Machine Control

Manage decoder states for sync and data:

```python
from pydigi.core import DecoderStateMachine, DecoderState

class StatefulDecoder:
    def __init__(self):
        self.fsm = DecoderStateMachine()

        # Register callbacks
        self.fsm.register_on_enter(
            DecoderState.DATA,
            self.on_start_decoding
        )
        self.fsm.register_on_exit(
            DecoderState.DATA,
            self.on_stop_decoding
        )

    def on_start_decoding(self):
        print("Started decoding data")
        self.reset_decoder()

    def on_stop_decoding(self):
        print("Stopped decoding data")
        self.flush_buffers()

    def process(self, sample):
        if self.fsm.state == DecoderState.IDLE:
            # Wait for signal
            pass
        elif self.fsm.state == DecoderState.PREAMBLE:
            # Look for preamble
            if self.detect_preamble(sample):
                self.fsm.transition('preamble_found')
        elif self.fsm.state == DecoderState.DATA:
            # Decode data
            self.decode_symbol(sample)
```

### Pattern 4: De-interleaving with FEC

De-interleave symbols before FEC decoding:

```python
from pydigi.core import BlockDeinterleaver, ViterbiDecoder

class InterleavedDecoder:
    def __init__(self, rows=4, cols=4):
        # De-interleaver
        self.deinterleaver = BlockDeinterleaver(rows=rows, cols=cols)

        # FEC decoder
        self.viterbi = ViterbiDecoder(constraint_length=5)

    def process_symbol(self, symbol):
        # Push symbol to de-interleaver
        ready, block = self.deinterleaver.push_symbol(symbol)

        if ready:
            # De-interleaved block ready - decode with FEC
            soft_bits = self.symbol_to_soft_bits(block)
            decoded_bits = self.viterbi.decode(soft_bits)
            return self.bits_to_text(decoded_bits)

        return None
```

---

## Testing Your Decoder

### Test with AWGN

Add noise at various SNR levels:

```python
from pydigi.utils import add_awgn, calculate_ber
import numpy as np

# Generate clean signal
tx_bits = np.random.randint(0, 2, 1000)
tx_signal = modulator.modulate(tx_bits)

# Test at different SNR levels
for snr in [0, 5, 10, 15, 20]:
    # Add noise
    noisy = add_awgn(tx_signal, snr_db=snr)

    # Decode
    rx_bits = decoder.decode(noisy)

    # Measure BER
    result = calculate_ber(tx_bits, rx_bits, skip_initial=32)

    print(f"SNR {snr:2d} dB: BER = {result.ber:.2e}")
```

### Test with Frequency Offset

Simulate tuning error:

```python
from pydigi.utils import add_frequency_offset

# Simulate 50 Hz offset
offset_signal = add_frequency_offset(
    signal,
    offset_hz=50.0,
    sample_rate=8000
)

# Your AFC should handle this
decoded = decoder.decode(offset_signal)
```

### Profile Performance

Measure real-time performance:

```python
from pydigi.utils import PerformanceProfiler

profiler = PerformanceProfiler()

# Profile decoding
profiler.start()
decoded = decoder.decode(signal)
stats = profiler.stop(num_samples=len(signal), sample_rate=8000)

print(f"Processing rate: {stats['samples_per_second']:.0f} samples/sec")
print(f"Real-time factor: {stats['realtime_factor']:.1f}x")
print(f"Signal duration: {stats['signal_duration_seconds']:.2f}s")
print(f"Processing time: {stats['duration_seconds']:.2f}s")
```

---

## Advanced Topics

### Using Gardner Timing Recovery

For best performance with PSK/QAM:

```python
from pydigi.core import GardnerTimingRecovery

timing = GardnerTimingRecovery(
    samples_per_symbol=4,
    loop_bw=0.01,        # Lower = more stable, slower tracking
    damping=1.0,          # 1.0 = critically damped
    max_deviation=0.2     # Allow ±20% timing variation
)

# Process samples
symbols = timing.process(samples)

# Or sample-by-sample
for sample in samples:
    symbol, ready = timing._update(sample)
    if ready:
        process_symbol(symbol)
```

### Using Sync Detector with Multiple Patterns

Detect both preamble and postamble:

```python
from pydigi.core import SyncPattern, SyncDetector

# Define patterns
preamble = SyncPattern([1, -1, 1, -1], name="preamble")
postamble = SyncPattern([0, 0, 0, 0], name="postamble")

# Create detector
detector = SyncDetector(
    patterns=[preamble, postamble],
    threshold=0.8,
    min_spacing=10  # Prevent re-triggers
)

# Detect
for symbol in symbols:
    detected, pattern_name = detector.update(symbol)
    if detected:
        if pattern_name == "preamble":
            start_decoding()
        elif pattern_name == "postamble":
            stop_decoding()
```

### Using 2nd-Order AFC

For better frequency tracking:

```python
from pydigi.core import PhaseAFC

afc = PhaseAFC(alpha=0.01, max_offset=100.0, damping=1.0)

# Use 2nd-order loop
freq_offset = afc.update_2nd_order(
    phase_error=phase_error,
    loop_gain=1.0
)
```

### Analyzing Error Patterns

Understand your decoder's error characteristics:

```python
from pydigi.utils import analyze_error_pattern

# Get errors
errors = tx_bits != rx_bits

# Analyze pattern
pattern = analyze_error_pattern(errors, max_burst_gap=5)

print(f"Total errors: {pattern['total_errors']}")
print(f"Bursts: {pattern['num_bursts']}")
print(f"Longest burst: {pattern['longest_burst']}")
print(f"Random errors: {pattern['random_errors']}")
print(f"Burst lengths: {pattern['burst_lengths']}")
```

---

## Best Practices

### 1. Choose the Right Components

**For Simple Decoders:**
- SymbolSlicer (timing)
- EnergyDCD (detection)
- PhaseAFC or ToneAFC (frequency tracking)

**For Production Decoders:**
- GardnerTimingRecovery (timing)
- EnergyDCD + PreambleDetector (detection)
- PhaseAFC/ToneAFC or PLL (frequency tracking)
- DecoderStateMachine (state management)

**For Complex Modes (Olivia, MT63):**
- All of the above, plus:
- BlockDeinterleaver
- Viterbi decoder
- Robust sync detection

### 2. Tune Loop Bandwidths

**Timing Recovery:**
- Start with `loop_bw=0.01`
- Increase for faster tracking (less stable)
- Decrease for more filtering (slower)

**AFC:**
- PSK: `alpha=0.01` to `0.05`
- MFSK: `alpha=0.05` to `0.1` (faster tones)
- Lower for weak signals

### 3. Set Appropriate Thresholds

**DCD:**
- Strong signals: `threshold_db=10.0`
- Moderate signals: `threshold_db=6.0`
- Weak signals: `threshold_db=3.0`

**Sync Detection:**
- Strict: `threshold=0.9` (fewer false alarms)
- Moderate: `threshold=0.8` (recommended)
- Loose: `threshold=0.6` (more tolerant)

### 4. Test Thoroughly

Always test your decoder with:
- ✅ Clean signals (no noise)
- ✅ AWGN at 0, 5, 10, 15, 20 dB SNR
- ✅ Frequency offsets (±50 Hz, ±100 Hz)
- ✅ Timing drift
- ✅ Phase noise
- ✅ Real-world signals (if available)

---

## Example: Complete QPSK Decoder

Here's a complete example using all the components:

```python
from pydigi.core import *
from pydigi.varicode import PSKVaricode
import numpy as np

class QPSKDecoder:
    def __init__(self, sample_rate=8000, carrier_freq=1000.0, baud_rate=31.25):
        # Parameters
        self.sample_rate = sample_rate
        self.carrier_freq = carrier_freq
        self.baud_rate = baud_rate
        self.sps = int(sample_rate / baud_rate)

        # Components
        self.nco = NCO(frequency=carrier_freq, sample_rate=sample_rate)
        self.filter = FIRFilter('lowpass', baud_rate*1.2, sample_rate, 64)
        self.timing = GardnerTimingRecovery(self.sps, loop_bw=0.01)
        self.dcd = EnergyDCD(threshold_db=6.0)
        self.afc = PhaseAFC(alpha=0.01, max_offset=100.0)
        self.fsm = DecoderStateMachine()
        self.varicode = PSKVaricode()

        # Preamble detection
        preamble = create_psk_preamble_pattern(32)
        self.sync = SyncDetector(preamble, threshold=0.8)

        # State
        self.prev_symbol = 0+0j

    def decode(self, samples):
        text = ""

        for sample in samples:
            # Baseband conversion
            baseband = sample * self.nco.mix_down()
            filtered = self.filter.filter(baseband)

            # DCD
            active, snr = self.dcd.update([filtered])

            # State machine
            if active and self.fsm.is_idle():
                self.fsm.transition('signal_detected')
            elif not active and not self.fsm.is_idle():
                self.fsm.transition('signal_lost')

            # Timing recovery
            symbol, ready = self.timing._update(filtered)

            if ready and self.fsm.state != DecoderState.IDLE:
                char = self.process_symbol(symbol)
                if char:
                    text += char

        return text

    def process_symbol(self, symbol):
        # Preamble detection
        if self.fsm.is_acquiring():
            detected, _ = self.sync.update(symbol)
            if detected:
                self.fsm.transition('preamble_found')
            return None

        # Data decoding
        if self.fsm.is_decoding():
            # QPSK differential detection
            phase_diff = np.angle(symbol * np.conj(self.prev_symbol))

            # Map to dibits (00, 01, 10, 11)
            # QPSK: 4 phases, 2 bits per symbol
            dibit = int((phase_diff + np.pi) / (np.pi/2)) % 4
            bits = [(dibit >> 1) & 1, dibit & 1]

            # AFC update
            freq_offset = self.afc.update(phase_diff / 2)
            self.nco.set_frequency(self.carrier_freq + freq_offset)

            # Decode bits
            text = ""
            for bit in bits:
                char = self.varicode.decode_bit(bit)
                if char:
                    text += char

            self.prev_symbol = symbol
            return text

        return None
```

---

## See Also

- [Decoder API Reference](../api/reference/decoder_api.md) - Complete API documentation
- [PSK Decoder](decoders.md) - Working PSK decoder example
- [Signal Detection Guide](signal-detection.md) - DCD techniques
- [DECODER_API_SUMMARY.md](https://github.com/yourusername/pydigi/blob/master/DECODER_API_SUMMARY.md) - Component summary
- [DECODER_INFRASTRUCTURE.md](https://github.com/yourusername/pydigi/blob/master/DECODER_INFRASTRUCTURE.md) - Design documentation
