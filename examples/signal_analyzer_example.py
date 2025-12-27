#!/usr/bin/env python3
"""
Example usage of the SignalAnalyzer tool.

This demonstrates various ways to analyze and compare modem signals
during development and debugging.
"""

import numpy as np
import pydigi
from pydigi.utils import (
    SignalAnalyzer,
    quick_analyze,
    quick_compare,
    compare_with_fldigi,
)


def example_1_basic_analysis():
    """Example 1: Basic signal analysis."""
    print("\n" + "="*70)
    print("EXAMPLE 1: Basic Signal Analysis")
    print("="*70)

    # Generate a test signal
    signal = pydigi.psk31_modulate("HELLO WORLD", freq=1000, sample_rate=8000)

    # Quick analysis with automatic plotting
    metrics = quick_analyze(signal, sample_rate=8000,
                           plot=True, plot_path='ex1_psk31_analysis.png')

    print(f"\nKey metrics:")
    print(f"  Duration: {metrics.duration:.2f}s")
    print(f"  Peak frequency: {metrics.peak_freq:.1f} Hz")
    print(f"  RMS: {metrics.rms:.4f}")
    print(f"  Detected period: {metrics.detected_period} samples")


def example_2_advanced_analysis():
    """Example 2: Advanced analysis with custom settings."""
    print("\n" + "="*70)
    print("EXAMPLE 2: Advanced Analysis")
    print("="*70)

    # Generate signal
    signal = pydigi.rtty_modulate("THE QUICK BROWN FOX", freq=1000, sample_rate=8000)

    # Create analyzer instance for more control
    analyzer = SignalAnalyzer(sample_rate=8000)

    # Analyze signal
    metrics = analyzer.analyze(signal, label="RTTY Signal")

    # Print detailed metrics
    analyzer.print_metrics()

    # Analyze in time windows
    print("\nWindow analysis (first 10 windows, 100ms each):")
    windows = analyzer.analyze_windows(window_duration=0.1)
    for window in windows[:10]:
        print(f"  {window['start_time']:.2f}s - {window['end_time']:.2f}s: "
              f"RMS={window['rms']:.4f}, Peak={window['peak']:.4f}")

    # Generate plots
    analyzer.plot(save_path='ex2_rtty_advanced.png')


def example_3_compare_modes():
    """Example 3: Compare two different modem signals."""
    print("\n" + "="*70)
    print("EXAMPLE 3: Compare Different Modes")
    print("="*70)

    text = "TEST"

    # Generate two different mode signals
    psk31_signal = pydigi.psk31_modulate(text, freq=1000, sample_rate=8000)
    psk63_signal = pydigi.psk63_modulate(text, freq=1000, sample_rate=8000)

    # Compare them
    comparison = quick_compare(psk31_signal, psk63_signal,
                              label1="PSK31", label2="PSK63",
                              sample_rate=8000,
                              plot=True, plot_path='ex3_psk31_vs_psk63.png')

    print(f"\nKey differences:")
    print(f"  RMS ratio: {comparison['rms_ratio']:.3f} ({comparison['rms_diff_db']:+.2f} dB)")
    print(f"  Peak frequency match: {comparison['freq_error_hz']:+.2f} Hz error")


def example_4_compare_with_fldigi():
    """Example 4: Compare our signal with fldigi reference."""
    print("\n" + "="*70)
    print("EXAMPLE 4: Compare with fldigi Reference")
    print("="*70)

    # Generate our signal
    our_signal = pydigi.mt63_1000l_modulate("TEST", freq=1000, sample_rate=8000)

    # Assume we have a fldigi-generated WAV file for comparison
    # (This is just an example - the file may not exist)
    fldigi_wav = "fldigi_mt63_1000l_test.wav"

    try:
        comparison = compare_with_fldigi(our_signal, fldigi_wav,
                                        sample_rate=8000,
                                        plot_path='ex4_fldigi_comparison.png')

        print(f"\nComparison with fldigi:")
        print(f"  Correlation: {comparison.get('correlation', 'N/A')}")
        print(f"  Frequency error: {comparison['freq_error_hz']:+.2f} Hz")
        print(f"  RMS difference: {comparison['rms_diff_db']:+.2f} dB")

    except FileNotFoundError:
        print(f"\nNote: fldigi reference file '{fldigi_wav}' not found.")
        print("To use this feature, generate a reference signal with fldigi and save as WAV.")


def example_5_detect_problems():
    """Example 5: Use analyzer to detect common problems."""
    print("\n" + "="*70)
    print("EXAMPLE 5: Problem Detection")
    print("="*70)

    # Generate a signal
    signal = pydigi.psk31_modulate("CQ CQ CQ DE PYDIGI", freq=1500, sample_rate=8000)

    analyzer = SignalAnalyzer(sample_rate=8000)
    metrics = analyzer.analyze(signal)

    # Check for common issues
    print("\nAutomated checks:")

    # Check 1: Frequency accuracy
    target_freq = 1500
    freq_error = abs(metrics.peak_freq - target_freq)
    if freq_error > 10:
        print(f"  ⚠ WARNING: Frequency error {freq_error:.1f} Hz (expected {target_freq} Hz)")
    else:
        print(f"  ✓ Frequency accurate: {metrics.peak_freq:.1f} Hz (error: {freq_error:.1f} Hz)")

    # Check 2: DC offset
    if abs(metrics.dc_offset) > 0.01:
        print(f"  ⚠ WARNING: Significant DC offset: {metrics.dc_offset:.4f}")
    else:
        print(f"  ✓ DC offset acceptable: {metrics.dc_offset:.6f}")

    # Check 3: Clipping
    if metrics.peak_amplitude > 0.99:
        print(f"  ⚠ WARNING: Possible clipping! Peak = {metrics.peak_amplitude:.4f}")
    else:
        print(f"  ✓ No clipping detected (peak: {metrics.peak_amplitude:.4f})")

    # Check 4: Signal level
    if metrics.rms < 0.01:
        print(f"  ⚠ WARNING: Signal level very low: RMS = {metrics.rms:.6f}")
    elif metrics.rms < 0.1:
        print(f"  ⚠ Signal level low: RMS = {metrics.rms:.4f}")
    else:
        print(f"  ✓ Signal level good: RMS = {metrics.rms:.4f}")

    # Check 5: Crest factor (should be reasonable for most modes)
    if metrics.crest_factor > 20:
        print(f"  ⚠ WARNING: Very high crest factor: {metrics.crest_factor:.1f}")
    else:
        print(f"  ✓ Crest factor acceptable: {metrics.crest_factor:.1f}")

    analyzer.print_metrics()
    analyzer.plot(save_path='ex5_problem_detection.png')


def example_6_batch_analysis():
    """Example 6: Batch analyze multiple modes."""
    print("\n" + "="*70)
    print("EXAMPLE 6: Batch Mode Analysis")
    print("="*70)

    # Test multiple modes
    modes = [
        ("PSK31", pydigi.psk31_modulate, 1000),
        ("PSK63", pydigi.psk63_modulate, 1000),
        ("RTTY", pydigi.rtty_modulate, 1000),
        ("CW", pydigi.cw_modulate, 800),
    ]

    text = "TEST"
    results = []

    print(f"\nAnalyzing {len(modes)} modes...")
    print("-" * 70)

    for mode_name, modulate_func, target_freq in modes:
        try:
            # Generate signal
            signal = modulate_func(text, freq=target_freq, sample_rate=8000)

            # Analyze
            analyzer = SignalAnalyzer(sample_rate=8000)
            metrics = analyzer.analyze(signal, label=mode_name)

            results.append((mode_name, metrics, target_freq))

            # Quick summary
            freq_error = metrics.peak_freq - target_freq
            print(f"{mode_name:8s}: Peak={metrics.peak_freq:7.1f} Hz "
                  f"(target={target_freq:4d} Hz, error={freq_error:+6.1f} Hz), "
                  f"RMS={metrics.rms:.4f}, "
                  f"BW={metrics.bandwidth_3db:6.1f} Hz")

        except Exception as e:
            print(f"{mode_name:8s}: ERROR - {e}")

    # Summary table
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    print(f"{'Mode':<10} {'Duration':<10} {'Peak Freq':<12} {'Freq Error':<12} {'RMS':<8} {'BW (-3dB)'}")
    print("-" * 70)
    for mode_name, metrics, target_freq in results:
        freq_error = metrics.peak_freq - target_freq
        print(f"{mode_name:<10} {metrics.duration:>6.2f}s    {metrics.peak_freq:>7.1f} Hz   "
              f"{freq_error:>+7.1f} Hz    {metrics.rms:>6.4f}   {metrics.bandwidth_3db:>6.1f} Hz")


if __name__ == "__main__":
    print("\nSignal Analyzer Examples")
    print("=" * 70)
    print("\nThese examples demonstrate how to use the SignalAnalyzer tool")
    print("for modem development and debugging.")

    # Run all examples
    try:
        example_1_basic_analysis()
    except Exception as e:
        print(f"\nExample 1 failed: {e}")

    try:
        example_2_advanced_analysis()
    except Exception as e:
        print(f"\nExample 2 failed: {e}")

    try:
        example_3_compare_modes()
    except Exception as e:
        print(f"\nExample 3 failed: {e}")

    try:
        example_4_compare_with_fldigi()
    except Exception as e:
        print(f"\nExample 4 failed: {e}")

    try:
        example_5_detect_problems()
    except Exception as e:
        print(f"\nExample 5 failed: {e}")

    try:
        example_6_batch_analysis()
    except Exception as e:
        print(f"\nExample 6 failed: {e}")

    print("\n" + "="*70)
    print("Examples complete! Check the generated PNG files for visualizations.")
    print("="*70)
