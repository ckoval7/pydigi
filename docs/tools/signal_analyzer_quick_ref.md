# Signal Analyzer Quick Reference

## Import

```python
from pydigi.utils import SignalAnalyzer, quick_analyze, quick_compare, compare_with_fldigi
```

## One-Line Analysis

```python
metrics = quick_analyze(signal, sample_rate=8000, plot_path='analysis.png')
```

## Full Analysis

```python
analyzer = SignalAnalyzer(sample_rate=8000)
metrics = analyzer.analyze(signal, label="My Signal")
analyzer.print_metrics()
analyzer.plot(save_path='plot.png')
```

## Compare Signals

```python
comparison = quick_compare(signal1, signal2,
                          label1="Ours", label2="Reference",
                          plot_path='compare.png')
```

## Compare with fldigi WAV

```python
comparison = compare_with_fldigi(our_signal, "fldigi.wav", plot_path='comp.png')
```

## Window Analysis

```python
windows = analyzer.analyze_windows(window_duration=0.1)  # 100ms windows
for w in windows:
    print(f"{w['start_time']:.2f}s: RMS={w['rms']:.4f}")
```

## Load WAV File

```python
analyzer = SignalAnalyzer(sample_rate=8000)
signal = analyzer.load_wav('input.wav')
metrics = analyzer.analyze(signal)
```

## Check Metrics

```python
# Time domain
print(f"Duration: {metrics.duration:.2f}s")
print(f"RMS: {metrics.rms:.4f}")
print(f"Peak: {metrics.peak_amplitude:.4f}")
print(f"Crest factor: {metrics.crest_factor:.2f}")
print(f"DC offset: {metrics.dc_offset:.6f}")

# Frequency domain
print(f"Peak freq: {metrics.peak_freq:.1f} Hz")
print(f"Bandwidth (-3dB): {metrics.bandwidth_3db:.1f} Hz")
print(f"Spectral centroid: {metrics.spectral_centroid:.1f} Hz")

# Periodicity
if metrics.detected_period:
    print(f"Period: {metrics.detected_period} samples")
    print(f"Period strength: {metrics.periodicity_strength:.3f}")
```

## Problem Detection

```python
# Frequency accuracy
target = 1000
if abs(metrics.peak_freq - target) > 10:
    print(f"⚠ Frequency error: {metrics.peak_freq - target:+.1f} Hz")

# DC offset
if abs(metrics.dc_offset) > 0.01:
    print(f"⚠ DC offset: {metrics.dc_offset:.4f}")

# Clipping
if metrics.peak_amplitude > 0.99:
    print("⚠ Possible clipping!")

# Low signal
if metrics.rms < 0.01:
    print("⚠ Signal level too low")
```

## Comparison Checks

```python
comparison = analyzer.compare(signal1, signal2, "Ours", "Reference")

# Print report
analyzer.print_comparison(comparison)

# Check specific metrics
print(f"RMS diff: {comparison['rms_diff_db']:.2f} dB")
print(f"Freq error: {comparison['freq_error_hz']:+.2f} Hz")
print(f"Correlation: {comparison['correlation']:.4f}")

# Good match?
if comparison['correlation'] > 0.9:
    print("✓ Excellent match!")
```

## Common Workflows

### Debug New Modem

```python
# 1. Generate signal
signal = modem.modulate("TEST")

# 2. Quick check
metrics = quick_analyze(signal, plot_path='debug.png')

# 3. Check frequency
if abs(metrics.peak_freq - expected_freq) > 10:
    print("Frequency problem!")

# 4. Check structure
windows = analyzer.analyze_windows(0.1)
# Look for preamble/data/postamble patterns
```

### Compare with fldigi

```python
# 1. Generate with fldigi, save as WAV
# 2. Generate with pydigi
our_signal = pydigi.mt63_1000l_modulate("TEST", freq=1000, sample_rate=8000)

# 3. Compare
comparison = compare_with_fldigi(our_signal, "fldigi_test.wav")

# 4. Check correlation
if comparison['correlation'] < 0.7:
    print("Implementation differs from fldigi!")
```

### Regression Testing

```python
# Save baseline metrics
baseline = quick_analyze(known_good_signal, plot=False)

# After code changes
new_signal = modem.modulate("TEST")
current = quick_analyze(new_signal, plot=False)

# Compare
freq_change = current.peak_freq - baseline.peak_freq
rms_change = current.rms - baseline.rms

if abs(freq_change) > 1:
    print(f"⚠ Frequency changed by {freq_change:+.2f} Hz")
if abs(rms_change) / baseline.rms > 0.05:
    print(f"⚠ RMS changed by {100*rms_change/baseline.rms:+.1f}%")
```

## Modem-Specific APIs

```python
# PSK, QPSK, EightPSK - frequency in constructor
psk31 = pydigi.PSK31(frequency=1000)
signal = psk31.modulate("TEXT")

# RTTY - frequency in modulate()
rtty = pydigi.RTTY()
signal = rtty.modulate("TEXT", frequency=1500, sample_rate=8000)

# MT63 - direct functions
signal = pydigi.mt63_1000l_modulate("TEXT", freq=1000, sample_rate=8000)

# Others - check examples/
```

## Tips

- Use `quick_analyze()` for fast checks during development
- Use `quick_compare()` to validate against references
- Generate plots to visually debug issues
- Check DC offset to find DSP bugs
- Use window analysis to understand signal structure
- Save analysis plots in version control for regression tracking
- Compare with fldigi early and often
