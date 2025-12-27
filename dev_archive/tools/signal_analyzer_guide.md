# Signal Analyzer Guide

The PyDigi Signal Analyzer is a comprehensive tool for analyzing and comparing modem signals during development and debugging. It provides detailed time-domain, frequency-domain, and phase analysis, along with signal comparison capabilities.

## Quick Start

### Analyze a Single Signal

```python
import pydigi
from pydigi.utils import quick_analyze

# Generate a signal
signal = pydigi.psk31_modulate("HELLO WORLD", freq=1000, sample_rate=8000)

# Quick analysis with automatic plotting
metrics = quick_analyze(signal, sample_rate=8000, plot_path='analysis.png')
```

### Compare Two Signals

```python
from pydigi.utils import quick_compare

signal1 = pydigi.psk31_modulate("TEST", freq=1000, sample_rate=8000)
signal2 = pydigi.psk63_modulate("TEST", freq=1000, sample_rate=8000)

comparison = quick_compare(signal1, signal2,
                          label1="PSK31", label2="PSK63",
                          plot_path='comparison.png')
```

### Compare with fldigi Reference

```python
from pydigi.utils import compare_with_fldigi

our_signal = pydigi.mt63_1000l_modulate("TEST", freq=1000, sample_rate=8000)
comparison = compare_with_fldigi(our_signal, "fldigi_reference.wav",
                                plot_path='fldigi_comparison.png')
```

## Command-Line Tool

The `analyze_signal.py` script provides command-line access to all analyzer features.

### List Available Modes

```bash
python analyze_signal.py --list-modes
```

### Analyze a Mode

```bash
# Analyze PSK31
python analyze_signal.py --mode psk31 --text "HELLO WORLD" --freq 1000

# Analyze MT63-1000L
python analyze_signal.py --mode mt63-1000l --text "CQ CQ" --freq 1500
```

### Compare Two Modes

```bash
python analyze_signal.py --compare --mode1 psk31 --mode2 psk63 --text "TEST"
```

### Compare with fldigi WAV File

```bash
# Generate signal with fldigi and save as WAV, then:
python analyze_signal.py --mode mt63-1000l --text "TEST" --compare-wav fldigi_output.wav
```

### Analyze Existing WAV File

```bash
python analyze_signal.py --wav-file my_signal.wav
```

### Batch Analyze All Modes

```bash
python analyze_signal.py --batch --text "CQ" --freq 1000
```

## Python API

### SignalAnalyzer Class

The `SignalAnalyzer` class provides comprehensive signal analysis capabilities.

```python
from pydigi.utils import SignalAnalyzer

# Create analyzer
analyzer = SignalAnalyzer(sample_rate=8000)

# Analyze signal
metrics = analyzer.analyze(signal, label="My Signal")

# Print detailed report
analyzer.print_metrics()

# Generate plots
analyzer.plot(save_path='analysis.png')

# Analyze in time windows
windows = analyzer.analyze_windows(window_duration=0.1)  # 100ms windows
for window in windows[:5]:
    print(f"{window['start_time']:.2f}s: RMS={window['rms']:.4f}")
```

### Signal Comparison

```python
# Compare two signals
analyzer = SignalAnalyzer(sample_rate=8000)
comparison = analyzer.compare(signal1, signal2,
                             label1="Our Signal",
                             label2="Reference")

# Print comparison report
analyzer.print_comparison(comparison)

# Generate comparison plots
analyzer.plot_comparison(save_path='comparison.png')
```

### Load WAV Files

```python
analyzer = SignalAnalyzer(sample_rate=8000)
signal = analyzer.load_wav('input.wav')
metrics = analyzer.analyze(signal)
```

## Analysis Metrics

The `SignalMetrics` class contains all computed metrics:

### Time Domain Metrics

- **duration**: Signal duration in seconds
- **num_samples**: Number of samples
- **sample_rate**: Sample rate in Hz
- **peak_amplitude**: Maximum absolute amplitude
- **rms**: Root Mean Square amplitude
- **crest_factor**: Peak-to-RMS ratio
- **dc_offset**: DC component of signal

### Frequency Domain Metrics

- **peak_freq**: Frequency with maximum magnitude
- **center_freq**: Spectral centroid (center of mass)
- **bandwidth_3db**: Bandwidth at -3dB (half power)
- **bandwidth_10pct**: Bandwidth at 10% of peak magnitude
- **spectral_centroid**: Weighted average frequency

### Phase Metrics

- **phase_std**: Standard deviation of phase changes
- **phase_transitions**: Number of significant phase transitions (>90°)

### Periodicity Metrics

- **detected_period**: Detected signal period in samples
- **periodicity_strength**: Autocorrelation peak strength (0-1)

## Comparison Metrics

When comparing two signals, these additional metrics are computed:

- **rms_ratio**: RMS amplitude ratio (signal1/signal2)
- **rms_diff_db**: RMS difference in dB
- **peak_ratio**: Peak amplitude ratio
- **peak_diff_db**: Peak difference in dB
- **freq_error_hz**: Peak frequency error in Hz
- **freq_error_pct**: Peak frequency error in percent
- **period_diff**: Period difference in samples
- **period_match**: Whether periods match (within 10 samples)
- **correlation**: Normalized cross-correlation

## Visualizations

The analyzer generates comprehensive plots including:

1. **Time Domain Waveform**: Full signal with amplitude over time
2. **Frequency Spectrum**: Magnitude spectrum with peak frequency marker
3. **Spectrogram**: Time-frequency representation
4. **Autocorrelation**: For periodicity detection
5. **RMS over Time**: Signal power in time windows

For comparisons, additional plots show:

- Side-by-side time domain comparison
- Overlaid spectrum comparison
- Spectrum difference plot
- Side-by-side spectrograms
- RMS comparison over time
- RMS ratio over time

## Use Cases

### 1. Verify Carrier Frequency

```python
signal = pydigi.psk31_modulate("TEST", freq=1000, sample_rate=8000)
analyzer = SignalAnalyzer(sample_rate=8000)
metrics = analyzer.analyze(signal)

target_freq = 1000
freq_error = abs(metrics.peak_freq - target_freq)
if freq_error > 10:
    print(f"WARNING: Frequency error {freq_error:.1f} Hz")
else:
    print(f"Frequency accurate: {metrics.peak_freq:.1f} Hz")
```

### 2. Check Signal Levels

```python
metrics = analyzer.analyze(signal)

if metrics.peak_amplitude > 0.99:
    print("WARNING: Possible clipping!")
elif metrics.rms < 0.01:
    print("WARNING: Signal level too low")
else:
    print(f"Signal level OK (RMS: {metrics.rms:.4f})")
```

### 3. Detect DC Offset

```python
if abs(metrics.dc_offset) > 0.01:
    print(f"WARNING: DC offset detected: {metrics.dc_offset:.4f}")
```

### 4. Verify Symbol Timing

```python
# For PSK31, symbol period should be ~256 samples at 8kHz (32ms)
expected_period = 256

if metrics.detected_period:
    period_error = abs(metrics.detected_period - expected_period)
    if period_error > 10:
        print(f"WARNING: Symbol timing off by {period_error} samples")
    else:
        print(f"Symbol timing correct: {metrics.detected_period} samples")
```

### 5. Compare with Reference Implementation

```python
# Generate signals
our_signal = pydigi.mt63_1000l_modulate("TEST", freq=1000, sample_rate=8000)

# Load fldigi reference
analyzer = SignalAnalyzer(sample_rate=8000)
fldigi_signal = analyzer.load_wav('fldigi_mt63_test.wav')

# Compare
comparison = analyzer.compare(our_signal, fldigi_signal,
                             "PyDigi", "fldigi")

# Check correlation
if comparison['correlation'] > 0.9:
    print("Excellent match with fldigi!")
elif comparison['correlation'] > 0.7:
    print("Good match with fldigi")
else:
    print(f"Poor match: correlation = {comparison['correlation']:.3f}")
```

### 6. Debug Bandwidth Issues

```python
metrics = analyzer.analyze(signal)
print(f"Bandwidth (-3dB): {metrics.bandwidth_3db:.1f} Hz")
print(f"Bandwidth (10%):  {metrics.bandwidth_10pct:.1f} Hz")

# MT63-1000 should have ~1kHz bandwidth
expected_bw = 1000
if abs(metrics.bandwidth_3db - expected_bw) > 100:
    print("WARNING: Bandwidth incorrect!")
```

### 7. Analyze Preamble and Data Sections

```python
# Analyze in 100ms windows to see signal structure
windows = analyzer.analyze_windows(window_duration=0.1)

print("Signal structure:")
for i, window in enumerate(windows[:20]):  # First 2 seconds
    t = window['start_time']
    rms = window['rms']
    if rms < 0.01:
        print(f"{t:.2f}s: Silence (RMS={rms:.6f})")
    elif rms > 0.2:
        print(f"{t:.2f}s: Strong signal (RMS={rms:.4f}) - likely preamble")
    else:
        print(f"{t:.2f}s: Normal signal (RMS={rms:.4f}) - likely data")
```

## Tips for Modem Development

1. **Always check frequency accuracy first** - If the carrier frequency is wrong, everything else will be wrong too.

2. **Compare with fldigi early and often** - Generate reference signals with fldigi and use `compare_with_fldigi()` to verify correctness.

3. **Use window analysis to understand signal structure** - The `analyze_windows()` method helps identify preambles, data, and postambles.

4. **Watch for clipping** - If `peak_amplitude` > 0.99, you're likely clipping and losing data.

5. **Check DC offset** - Non-zero DC offset can indicate DSP bugs or incorrect initialization.

6. **Verify periodicity** - Symbol timing issues show up as incorrect detected periods.

7. **Use batch analysis for regression testing** - Run `analyze_signal.py --batch` regularly to catch regressions across all modes.

8. **Save analysis plots** - Visual comparison is often the fastest way to spot problems.

## Examples

See `examples/signal_analyzer_example.py` for comprehensive usage examples including:

- Basic signal analysis
- Advanced analysis with custom settings
- Comparing different modes
- Comparing with fldigi reference
- Automated problem detection
- Batch mode analysis

Run the examples:

```bash
cd examples
python signal_analyzer_example.py
```

## Integration with Existing Tools

The signal analyzer can replace or augment existing ad-hoc analysis scripts:

**Before:**
```python
# Old ad-hoc approach
fft = np.fft.rfft(signal)
freqs = np.fft.rfftfreq(len(signal), 1/8000)
peak_idx = np.argmax(np.abs(fft))
peak_freq = freqs[peak_idx]
print(f"Peak: {peak_freq}")
```

**After:**
```python
# New standardized approach
from pydigi.utils import quick_analyze
metrics = quick_analyze(signal, sample_rate=8000)
# Automatically prints comprehensive report and generates plots
```

## Troubleshooting

### Matplotlib Backend Issues

If plots don't display:

```python
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
```

### Memory Issues with Large Signals

For very long signals, analyze only a portion:

```python
# Analyze first 10 seconds
signal_portion = signal[:10 * sample_rate]
metrics = analyzer.analyze(signal_portion)
```

### WAV File Loading Issues

Ensure WAV files are 16-bit PCM format. To convert:

```bash
ffmpeg -i input.wav -acodec pcm_s16le -ar 8000 output.wav
```

## Future Enhancements

Planned features for future versions:

- Eye diagram generation for symbol timing analysis
- Constellation diagrams for PSK modes
- SNR estimation
- THD (Total Harmonic Distortion) calculation
- Automated regression testing framework
- Export metrics to JSON/CSV for analysis
- Real-time analysis mode
- Integration with GNU Radio

## Summary

The Signal Analyzer provides a standardized, comprehensive toolkit for modem development:

- **Simple API**: Quick analysis with one function call
- **Comprehensive metrics**: Time, frequency, and phase analysis
- **Visual debugging**: Automatic plot generation
- **Comparison tools**: Compare implementations easily
- **Command-line access**: Shell integration for automation
- **Extensible**: Easy to add custom metrics and plots

Use it throughout your development workflow to catch bugs early, verify correctness, and understand signal behavior.
