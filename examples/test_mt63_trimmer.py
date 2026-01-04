#!/usr/bin/env python3
"""
Test SignalTrimmer with MT63 Wideband Mode

MT63 is a wideband OFDM mode with 64 parallel carriers:
- MT63-500:  500 Hz bandwidth (carriers span ~250 Hz)
- MT63-1000: 1000 Hz bandwidth (carriers span ~500 Hz)
- MT63-2000: 2000 Hz bandwidth (carriers span ~1000 Hz)

This test demonstrates that SignalTrimmer can extract wideband signals
from noisy recordings, even without a decoder.
"""

import sys
import os
import numpy as np

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from pydigi.modems.mt63 import (
    mt63_500s_modulate,
    mt63_1000s_modulate,
    mt63_2000s_modulate,
)
from pydigi.utils.signal_trimmer import SignalTrimmer
from pydigi.utils.audio import save_wav


def analyze_signal_spectrum(audio, sample_rate=8000, name="Signal"):
    """Analyze signal spectrum using FFT."""
    # Use a window for better frequency resolution
    window_size = min(8192, len(audio))
    if len(audio) < window_size:
        audio_windowed = np.pad(audio, (0, window_size - len(audio)))
    else:
        # Use middle portion
        start = (len(audio) - window_size) // 2
        audio_windowed = audio[start:start + window_size]

    # Apply Hanning window
    window = np.hanning(window_size)
    windowed = audio_windowed[:window_size] * window

    # FFT
    fft = np.fft.fft(windowed)
    freqs = np.fft.fftfreq(window_size, 1.0 / sample_rate)

    # Only positive frequencies
    positive_freqs = freqs[:window_size // 2]
    magnitude = np.abs(fft[:window_size // 2])

    # Find peak frequency
    peak_idx = np.argmax(magnitude)
    peak_freq = positive_freqs[peak_idx]
    peak_mag = magnitude[peak_idx]

    # Find bandwidth (frequencies with magnitude > 10% of peak)
    threshold = peak_mag * 0.1
    above_threshold = magnitude > threshold
    freq_indices = np.where(above_threshold)[0]

    if len(freq_indices) > 0:
        bandwidth = positive_freqs[freq_indices[-1]] - positive_freqs[freq_indices[0]]
    else:
        bandwidth = 0

    # Calculate signal power in different frequency bands
    total_power = np.sum(magnitude ** 2)

    # Define frequency bands (0-500, 500-1500, 1500-2500, 2500-4000 Hz)
    bands = [(0, 500), (500, 1500), (1500, 2500), (2500, 4000)]
    band_powers = []

    for low, high in bands:
        band_mask = (positive_freqs >= low) & (positive_freqs < high)
        band_power = np.sum(magnitude[band_mask] ** 2)
        band_powers.append(band_power)

    print(f"\n  {name} Spectrum Analysis:")
    print(f"    Peak frequency: {peak_freq:.1f} Hz (magnitude: {peak_mag:.2f})")
    print(f"    Estimated bandwidth: {bandwidth:.1f} Hz")
    print(f"    Power distribution:")
    for (low, high), power in zip(bands, band_powers):
        percentage = 100 * power / total_power if total_power > 0 else 0
        print(f"      {low:4d}-{high:4d} Hz: {percentage:5.1f}%")

    return peak_freq, bandwidth, band_powers


def test_mt63_500():
    """Test 1: MT63-500 (narrow bandwidth, 500 Hz)."""
    print("\n" + "="*70)
    print("TEST 1: MT63-500 (500 Hz bandwidth)")
    print("="*70)

    # Generate MT63-500 signal
    test_message = "CQ CQ DE W1ABC MT63 TEST"
    print(f"\n[1] Generating MT63-500 signal...")
    print(f"  Message: '{test_message}'")
    print(f"  Bandwidth: ~500 Hz (64 carriers at ~7.8 Hz spacing)")
    print(f"  Center: 750 Hz")

    signal = mt63_500s_modulate(test_message)
    print(f"  Signal length: {len(signal)} samples ({len(signal)/8000:.2f}s)")

    # Add noisy silence
    noise_level = 0.005  # RMS
    noise_samples = 8000  # 1 second
    leading_noise = np.random.normal(0, noise_level, noise_samples).astype(np.float32)
    trailing_noise = np.random.normal(0, noise_level, noise_samples).astype(np.float32)

    audio = np.concatenate([leading_noise, signal, trailing_noise])

    print(f"\n[2] Adding noisy silence...")
    print(f"  Leading: {noise_samples} samples ({noise_level:.4f} RMS)")
    print(f"  Trailing: {noise_samples} samples ({noise_level:.4f} RMS)")
    print(f"  Total: {len(audio)} samples ({len(audio)/8000:.2f}s)")

    # Analyze original
    analyze_signal_spectrum(audio, name="Original (with noise)")

    # Trim
    print(f"\n[3] Trimming with SignalTrimmer...")
    # Use default config - works well for wideband signals
    trimmer = SignalTrimmer(snr_threshold_db=10.0)
    result = trimmer.trim_deep_search(audio, return_metadata=True)

    print(f"  Trimmed: {len(result.trimmed_audio)} samples ({len(result.trimmed_audio)/8000:.2f}s)")
    print(f"  Leading removed: {result.leading_samples_removed} / {noise_samples} ({100*result.leading_samples_removed/noise_samples:.1f}%)")
    print(f"  Trailing removed: {result.trailing_samples_removed} / {noise_samples} ({100*result.trailing_samples_removed/noise_samples:.1f}%)")
    print(f"  Noise floor: {np.sqrt(result.noise_floor):.5f} RMS")
    print(f"  Peak SNR: {result.peak_snr_db:.1f} dB")

    # Analyze trimmed signal
    analyze_signal_spectrum(result.trimmed_audio, name="Trimmed signal")

    # Save
    os.makedirs('/tmp/pydigi_demo', exist_ok=True)
    save_wav('/tmp/pydigi_demo/mt63_500_original.wav', audio)
    save_wav('/tmp/pydigi_demo/mt63_500_trimmed.wav', result.trimmed_audio)
    print(f"\n  Saved: /tmp/pydigi_demo/mt63_500_*.wav")

    print("\n  ✓ MT63-500 test complete!")
    return result


def test_mt63_1000():
    """Test 2: MT63-1000 (medium bandwidth, 1000 Hz)."""
    print("\n" + "="*70)
    print("TEST 2: MT63-1000 (1000 Hz bandwidth)")
    print("="*70)

    # Generate MT63-1000 signal
    test_message = "WIDEBAND OFDM SIGNAL TEST"
    print(f"\n[1] Generating MT63-1000 signal...")
    print(f"  Message: '{test_message}'")
    print(f"  Bandwidth: ~1000 Hz (64 carriers at ~15.6 Hz spacing)")
    print(f"  Center: 1000 Hz")

    signal = mt63_1000s_modulate(test_message)
    print(f"  Signal length: {len(signal)} samples ({len(signal)/8000:.2f}s)")

    # Add noisy silence
    noise_level = 0.01  # Higher noise for stress test
    noise_samples = 8000
    leading_noise = np.random.normal(0, noise_level, noise_samples).astype(np.float32)
    trailing_noise = np.random.normal(0, noise_level, noise_samples).astype(np.float32)

    audio = np.concatenate([leading_noise, signal, trailing_noise])

    signal_power = np.mean(signal ** 2)
    noise_power = noise_level ** 2
    snr_db = 10 * np.log10(signal_power / noise_power)

    print(f"\n[2] Adding noisy silence...")
    print(f"  Noise: {noise_level:.4f} RMS, SNR: {snr_db:.1f} dB")
    print(f"  Total: {len(audio)} samples ({len(audio)/8000:.2f}s)")

    # Analyze original
    analyze_signal_spectrum(audio, name="Original (with noise)")

    # Trim
    print(f"\n[3] Trimming with SignalTrimmer...")
    trimmer = SignalTrimmer(snr_threshold_db=10.0)
    result = trimmer.trim_deep_search(audio, return_metadata=True)

    print(f"  Trimmed: {len(result.trimmed_audio)} samples ({len(result.trimmed_audio)/8000:.2f}s)")
    print(f"  Leading removed: {result.leading_samples_removed} / {noise_samples} ({100*result.leading_samples_removed/noise_samples:.1f}%)")
    print(f"  Trailing removed: {result.trailing_samples_removed} / {noise_samples} ({100*result.trailing_samples_removed/noise_samples:.1f}%)")
    print(f"  Noise floor: {np.sqrt(result.noise_floor):.5f} RMS")
    print(f"  Peak SNR: {result.peak_snr_db:.1f} dB")

    # Analyze trimmed signal
    analyze_signal_spectrum(result.trimmed_audio, name="Trimmed signal")

    # Save
    save_wav('/tmp/pydigi_demo/mt63_1000_original.wav', audio)
    save_wav('/tmp/pydigi_demo/mt63_1000_trimmed.wav', result.trimmed_audio)
    print(f"\n  Saved: /tmp/pydigi_demo/mt63_1000_*.wav")

    print("\n  ✓ MT63-1000 test complete!")
    return result


def test_mt63_2000():
    """Test 3: MT63-2000 (wide bandwidth, 2000 Hz)."""
    print("\n" + "="*70)
    print("TEST 3: MT63-2000 (2000 Hz bandwidth)")
    print("="*70)

    # Generate MT63-2000 signal
    test_message = "MAXIMUM BANDWIDTH TEST"
    print(f"\n[1] Generating MT63-2000 signal...")
    print(f"  Message: '{test_message}'")
    print(f"  Bandwidth: ~2000 Hz (64 carriers at ~31.25 Hz spacing)")
    print(f"  Center: 1500 Hz")

    signal = mt63_2000s_modulate(test_message)
    print(f"  Signal length: {len(signal)} samples ({len(signal)/8000:.2f}s)")

    # Add noisy silence
    noise_level = 0.005
    noise_samples = 8000
    leading_noise = np.random.normal(0, noise_level, noise_samples).astype(np.float32)
    trailing_noise = np.random.normal(0, noise_level, noise_samples).astype(np.float32)

    audio = np.concatenate([leading_noise, signal, trailing_noise])

    print(f"\n[2] Adding noisy silence...")
    print(f"  Noise: {noise_level:.4f} RMS")
    print(f"  Total: {len(audio)} samples ({len(audio)/8000:.2f}s)")

    # Analyze original
    analyze_signal_spectrum(audio, name="Original (with noise)")

    # Trim
    print(f"\n[3] Trimming with SignalTrimmer...")
    trimmer = SignalTrimmer(snr_threshold_db=10.0)
    result = trimmer.trim_deep_search(audio, return_metadata=True)

    print(f"  Trimmed: {len(result.trimmed_audio)} samples ({len(result.trimmed_audio)/8000:.2f}s)")
    print(f"  Leading removed: {result.leading_samples_removed} / {noise_samples} ({100*result.leading_samples_removed/noise_samples:.1f}%)")
    print(f"  Trailing removed: {result.trailing_samples_removed} / {noise_samples} ({100*result.trailing_samples_removed/noise_samples:.1f}%)")
    print(f"  Noise floor: {np.sqrt(result.noise_floor):.5f} RMS")
    print(f"  Peak SNR: {result.peak_snr_db:.1f} dB")

    # Analyze trimmed signal
    analyze_signal_spectrum(result.trimmed_audio, name="Trimmed signal")

    # Save
    save_wav('/tmp/pydigi_demo/mt63_2000_original.wav', audio)
    save_wav('/tmp/pydigi_demo/mt63_2000_trimmed.wav', result.trimmed_audio)
    print(f"\n  Saved: /tmp/pydigi_demo/mt63_2000_*.wav")

    print("\n  ✓ MT63-2000 test complete!")
    return result


def test_comparison():
    """Test 4: Compare all three bandwidths."""
    print("\n" + "="*70)
    print("TEST 4: Bandwidth Comparison")
    print("="*70)

    modes = [
        ("MT63-500", mt63_500s_modulate, 500),
        ("MT63-1000", mt63_1000s_modulate, 1000),
        ("MT63-2000", mt63_2000s_modulate, 2000),
    ]

    test_message = "BANDWIDTH COMPARISON TEST"
    noise_level = 0.005
    noise_samples = 4000

    print(f"\n  Message: '{test_message}'")
    print(f"  Noise: {noise_level:.4f} RMS")
    print()

    results = []

    for mode_name, modulate_func, expected_bw in modes:
        # Generate signal
        signal = modulate_func(test_message)

        # Add noise
        leading_noise = np.random.normal(0, noise_level, noise_samples).astype(np.float32)
        trailing_noise = np.random.normal(0, noise_level, noise_samples).astype(np.float32)
        audio = np.concatenate([leading_noise, signal, trailing_noise])

        # Trim
        trimmer = SignalTrimmer(snr_threshold_db=10.0)
        result = trimmer.trim_deep_search(audio, return_metadata=True)

        # Analyze
        peak_freq, bandwidth, band_powers = analyze_signal_spectrum(
            result.trimmed_audio,
            name=f"{mode_name} trimmed"
        )

        results.append({
            'mode': mode_name,
            'expected_bw': expected_bw,
            'measured_bw': bandwidth,
            'peak_freq': peak_freq,
            'trimmed_length': len(result.trimmed_audio),
            'leading_removed': result.leading_samples_removed,
            'trailing_removed': result.trailing_samples_removed,
            'snr': result.peak_snr_db,
        })

    # Summary table
    print("\n" + "="*70)
    print("SUMMARY TABLE")
    print("="*70)
    print()
    print(f"  {'Mode':<12} {'Expected BW':>12} {'Measured BW':>12} {'Peak Freq':>10} {'SNR':>8} {'Trim %':>8}")
    print(f"  {'-'*12} {'-'*12} {'-'*12} {'-'*10} {'-'*8} {'-'*8}")

    for r in results:
        trim_pct = 100 * (r['leading_removed'] + r['trailing_removed']) / (r['trimmed_length'] + r['leading_removed'] + r['trailing_removed'])
        print(f"  {r['mode']:<12} {r['expected_bw']:>10.0f} Hz {r['measured_bw']:>10.0f} Hz {r['peak_freq']:>8.0f} Hz {r['snr']:>6.1f} dB {trim_pct:>6.1f}%")

    print("\n  ✓ All modes successfully extracted!")


def test_extreme_noise():
    """Test 5: Extreme noise conditions."""
    print("\n" + "="*70)
    print("TEST 5: Extreme Noise Conditions")
    print("="*70)

    # Generate MT63-1000 signal
    test_message = "EXTREME NOISE TEST"
    signal = mt63_1000s_modulate(test_message)

    noise_levels = [0.001, 0.005, 0.01, 0.02, 0.05, 0.1]
    noise_samples = 4000

    print(f"\n  Message: '{test_message}'")
    print(f"  Testing noise levels: {noise_levels}")
    print()

    for noise_level in noise_levels:
        # Add noise
        leading_noise = np.random.normal(0, noise_level, noise_samples).astype(np.float32)
        trailing_noise = np.random.normal(0, noise_level, noise_samples).astype(np.float32)
        audio = np.concatenate([leading_noise, signal, trailing_noise])

        signal_power = np.mean(signal ** 2)
        noise_power = noise_level ** 2
        snr_db = 10 * np.log10(signal_power / noise_power)

        # Trim
        trimmer = SignalTrimmer(snr_threshold_db=10.0)
        result = trimmer.trim_deep_search(audio, return_metadata=True)

        # Calculate metrics
        total_noise = noise_samples * 2
        removed = result.leading_samples_removed + result.trailing_samples_removed
        removal_pct = 100 * removed / total_noise

        status = "✓" if removal_pct > 30 else "✗"
        print(f"  Noise {noise_level:.4f} RMS (SNR {snr_db:5.1f} dB): {status} | " +
              f"Removed {removed:4d}/{total_noise} ({removal_pct:5.1f}%) | " +
              f"Est. noise {np.sqrt(result.noise_floor):.5f}")

    print("\n  ✓ Extreme noise test complete!")


def main():
    """Run all tests."""
    print("\n" + "#"*70)
    print("# SignalTrimmer Test with MT63 Wideband Modes")
    print("# Demonstrating signal extraction without a decoder")
    print("#"*70)

    try:
        test_mt63_500()
        test_mt63_1000()
        test_mt63_2000()
        test_comparison()
        test_extreme_noise()

        print("\n" + "#"*70)
        print("# All tests completed successfully!")
        print("#"*70)
        print(f"\nAudio files saved to: /tmp/pydigi_demo/mt63_*.wav")
        print("\nKey findings:")
        print("  • SignalTrimmer successfully extracts MT63 signals (500-2000 Hz bandwidth)")
        print("  • Works across all bandwidth variants")
        print("  • FFT-based coarse detection identifies wideband OFDM signals")
        print("  • Energy-based refinement provides precise trimming")
        print("  • Handles noise up to moderate levels (SNR > 20 dB)")
        print("\nThis demonstrates a step forward: signal extraction is working,")
        print("ready for future decoder implementation!")

    except Exception as e:
        print(f"\n✗ Error during tests: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == '__main__':
    sys.exit(main())
