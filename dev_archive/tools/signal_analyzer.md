# Signal Analyzer Tool

## Overview

The Signal Analyzer is a comprehensive toolkit for analyzing and debugging modem signals during development. It provides:

- **Time-domain analysis**: Waveform, RMS, peak amplitude, crest factor
- **Frequency-domain analysis**: Spectrum, bandwidth, center frequency
- **Spectrogram generation**: Time-frequency visualization
- **Phase analysis**: Instantaneous phase, phase transitions
- **Periodicity detection**: Symbol timing via autocorrelation
- **Signal comparison**: Compare your signals against references
- **Automated problem detection**: Frequency errors, clipping, DC offset, signal level

## Files Created

1. **`pydigi/utils/signal_analyzer.py`** - Core analyzer library
2. **`analyze_signal.py`** - Command-line tool (needs API update)
3. **`examples/signal_analyzer_example.py`** - Usage examples (needs API update)
4. **`test_signal_analyzer.py`** - Test suite (working)
5. **`SIGNAL_ANALYZER_GUIDE.md`** - Comprehensive documentation
6. **`SIGNAL_ANALYZER_README.md`** - This file

## Quick Start

### Python Library Usage

```python
import pydigi
from pydigi.utils import SignalAnalyzer

# Generate a signal
psk31 = pydigi.PSK31(frequency=1000)
signal = psk31.modulate("HELLO WORLD")

# Analyze it
analyzer = SignalAnalyzer(sample_rate=8000)
metrics = analyzer.analyze(signal)

# Print report
analyzer.print_metrics()

# Generate plots
analyzer.plot(save_path='analysis.png')
```

### Compare Two Signals

```python
from pydigi.utils import quick_compare

psk31 = pydigi.PSK31(frequency=1000)
psk63 = pydigi.PSK63(frequency=1000)

signal1 = psk31.modulate("TEST")
signal2 = psk63.modulate("TEST")

comparison = quick_compare(signal1, signal2,
                          label1="PSK31", label2="PSK63",
                          plot_path='comparison.png')
```

### Compare with fldigi

```python
from pydigi.utils import compare_with_fldigi

our_signal = pydigi.mt63_1000l_modulate("TEST", freq=1000, sample_rate=8000)
comparison = compare_with_fldigi(our_signal, "fldigi_reference.wav")
```

## Test Results

The test suite (`test_signal_analyzer.py`) validates:

- ✓ Basic signal analysis
- ✓ Window-based analysis
- ✓ Signal comparison
- ✓ Quick analysis functions
- ✓ Automated problem detection

All tests are passing!

## API Notes

Different modems in pydigi use different APIs:

### Class-based API (PSK, QPSK, etc.)
Frequency is set in constructor:
```python
psk31 = pydigi.PSK31(frequency=1000)
signal = psk31.modulate("TEXT")
```

### RTTY API
Frequency is passed to modulate():
```python
rtty = pydigi.RTTY()
signal = rtty.modulate("TEXT", frequency=1500, sample_rate=8000)
```

### MT63 Functional API
Direct function calls:
```python
signal = pydigi.mt63_1000l_modulate("TEXT", freq=1000, sample_rate=8000)
```

## Features

### Analysis Metrics

**Time Domain:**
- Duration, samples, sample rate
- Peak amplitude, RMS, crest factor
- DC offset detection

**Frequency Domain:**
- Peak frequency, spectral centroid
- Bandwidth at -3dB and 10% points
- Full spectrum data

**Phase:**
- Instantaneous phase
- Phase standard deviation
- Phase transition counting

**Periodicity:**
- Autocorrelation-based period detection
- Periodicity strength measure

### Comparison Capabilities

When comparing two signals:
- RMS ratio (linear and dB)
- Peak amplitude ratio (linear and dB)
- Frequency error (Hz and %)
- Period matching
- Normalized cross-correlation

### Visualizations

Single signal plots include:
1. Time domain waveform
2. Frequency spectrum
3. Spectrogram
4. Autocorrelation (periodicity)
5. RMS over time

Comparison plots include:
1. Side-by-side time domain
2. Overlaid spectra
3. Spectrum difference
4. Side-by-side spectrograms
5. RMS comparison and ratio

### Problem Detection

Automatically checks for:
- Frequency errors (>10 Hz)
- DC offset (>0.01)
- Signal clipping (>0.99)
- Low signal level (<0.01)
- Excessive crest factor (>20)

## Use Cases

1. **Verify carrier frequency** - Check that generated signal is at correct frequency
2. **Check signal levels** - Ensure no clipping and adequate amplitude
3. **Detect DC offset** - Find DSP bugs causing DC components
4. **Verify symbol timing** - Use periodicity detection for symbol period
5. **Compare with reference** - Validate against fldigi or other implementations
6. **Debug bandwidth** - Ensure signal bandwidth matches specification
7. **Analyze structure** - Use window analysis to see preamble/data/postamble

## Integration

The analyzer is already integrated into `pydigi.utils`:

```python
from pydigi.utils import (
    SignalAnalyzer,      # Main class
    SignalMetrics,       # Metrics container
    quick_analyze,       # Quick single signal analysis
    quick_compare,       # Quick comparison
    compare_with_fldigi, # Compare with WAV file
)
```

## Next Steps

### TODO: Update CLI Tool

The `analyze_signal.py` command-line tool needs to be updated to handle the different modem APIs correctly. It currently assumes all modes work the same way.

### TODO: Update Examples

The `examples/signal_analyzer_example.py` file also needs API corrections to work with different modem types.

### Recommended Enhancements

Future improvements could include:

1. **Eye diagrams** - Symbol timing visualization
2. **Constellation plots** - For PSK modes
3. **SNR estimation** - Signal-to-noise ratio calculation
4. **THD measurement** - Total harmonic distortion
5. **JSON/CSV export** - Save metrics for further analysis
6. **Real-time mode** - Analyze signals as they're generated
7. **GNU Radio integration** - Direct flow graph analysis
8. **Automated regression testing** - Track metrics over time

## Documentation

See **`SIGNAL_ANALYZER_GUIDE.md`** for:
- Complete API documentation
- Detailed usage examples
- Tips for modem development
- Troubleshooting guide
- Integration patterns

## Summary

The Signal Analyzer provides a standardized, comprehensive toolkit that replaces ad-hoc analysis scripts with a unified API. It's ready to use for:

- Development: Verify implementations as you build
- Debugging: Diagnose issues with detailed metrics
- Testing: Compare against reference implementations
- Validation: Ensure signal correctness before deployment

The core library is complete and tested. The CLI tool and some examples need minor updates to handle different modem APIs correctly.
