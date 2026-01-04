#!/usr/bin/env python3
"""
Test SignalTrimmer with 8PSK125 FEC

Demonstrates how the SignalTrimmer helps the 8PSK FEC decoder handle
noisy silence - the original problem this utility was designed to solve.
"""

import sys
import os
import numpy as np

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from pydigi.modems.psk8_fec import EightPSK_250F
from pydigi.modems.psk8_fec_decoder import EightPSK_250F_Decoder
from pydigi.utils.signal_trimmer import SignalTrimmer


def test_baseline():
    """Test 1: Baseline with pure silence (should work)."""
    print("\n" + "="*70)
    print("TEST 1: Baseline - Pure Silence")
    print("="*70)

    # Generate signal
    encoder = EightPSK_250F()
    decoder = EightPSK_250F_Decoder(squelch_enabled=False)
    test_message = "HELLO WORLD 8PSK TEST"

    print(f"\n[1] Encoding message: '{test_message}'")
    signal = encoder.modulate(test_message)

    # Add pure silence
    silence = np.zeros(4000, dtype=np.float32)  # 0.5s @ 8kHz
    audio = np.concatenate([silence, signal, silence])

    print(f"  Signal: {len(signal)} samples")
    print(f"  With silence: {len(audio)} samples ({len(audio)/8000:.2f}s)")

    # Decode without trimming
    print("\n[2] Decoding WITHOUT trimmer...")
    decoded = decoder.demodulate(audio)
    print(f"  Decoded: '{decoded}'")

    if test_message in decoded:
        print(f"  ✓ SUCCESS: Message found in decoded output")
    else:
        print(f"  ✗ PARTIAL: Message not fully decoded")

    return test_message in decoded


def test_noisy_silence_without_trimmer():
    """Test 2: Noisy silence WITHOUT trimmer (expected to fail)."""
    print("\n" + "="*70)
    print("TEST 2: Noisy Silence WITHOUT Trimmer")
    print("="*70)

    # Generate signal
    encoder = EightPSK_250F()
    decoder = EightPSK_250F_Decoder(squelch_enabled=False)
    test_message = "HELLO WORLD 8PSK TEST"

    print(f"\n[1] Encoding message: '{test_message}'")
    signal = encoder.modulate(test_message)

    # Add noisy silence (this causes problems!)
    noise_level = 0.01  # RMS amplitude
    noise_samples = 4000  # 0.5s @ 8kHz
    leading_noise = np.random.normal(0, noise_level, noise_samples).astype(np.float32)
    trailing_noise = np.random.normal(0, noise_level, noise_samples).astype(np.float32)

    audio = np.concatenate([leading_noise, signal, trailing_noise])

    signal_power = np.mean(signal ** 2)
    noise_power = np.mean(leading_noise ** 2)
    snr_db = 10 * np.log10(signal_power / noise_power)

    print(f"  Signal: {len(signal)} samples")
    print(f"  Noise: {noise_level:.4f} RMS, SNR: {snr_db:.1f} dB")
    print(f"  Total: {len(audio)} samples ({len(audio)/8000:.2f}s)")

    # Decode without trimming
    print("\n[2] Decoding WITHOUT trimmer...")
    decoded = decoder.demodulate(audio)
    print(f"  Decoded: '{decoded}'")

    if test_message in decoded:
        print(f"  ✓ SUCCESS: Message found (noise didn't cause issues)")
        return True
    else:
        print(f"  ✗ EXPECTED FAILURE: Noisy silence corrupted decoder state")
        print(f"     This is the known issue that SignalTrimmer solves!")
        return False


def test_noisy_silence_with_trimmer():
    """Test 3: Noisy silence WITH trimmer (expected to work)."""
    print("\n" + "="*70)
    print("TEST 3: Noisy Silence WITH Trimmer")
    print("="*70)

    # Generate signal
    encoder = EightPSK_250F()
    decoder = EightPSK_250F_Decoder(squelch_enabled=False)
    test_message = "HELLO WORLD 8PSK TEST"

    print(f"\n[1] Encoding message: '{test_message}'")
    signal = encoder.modulate(test_message)

    # Add noisy silence
    noise_level = 0.01  # RMS amplitude
    noise_samples = 4000  # 0.5s @ 8kHz
    leading_noise = np.random.normal(0, noise_level, noise_samples).astype(np.float32)
    trailing_noise = np.random.normal(0, noise_level, noise_samples).astype(np.float32)

    audio = np.concatenate([leading_noise, signal, trailing_noise])

    signal_power = np.mean(signal ** 2)
    noise_power = np.mean(leading_noise ** 2)
    snr_db = 10 * np.log10(signal_power / noise_power)

    print(f"  Signal: {len(signal)} samples")
    print(f"  Noise: {noise_level:.4f} RMS, SNR: {snr_db:.1f} dB")
    print(f"  Total: {len(audio)} samples ({len(audio)/8000:.2f}s)")

    # Trim BEFORE decoding
    print("\n[2] Trimming with SignalTrimmer...")
    trimmer = SignalTrimmer(preset='psk125')
    result = trimmer.trim_deep_search(audio, return_metadata=True)

    print(f"  Original: {len(audio)} samples")
    print(f"  Trimmed: {len(result.trimmed_audio)} samples")
    print(f"  Leading removed: {result.leading_samples_removed} / {noise_samples} ({100*result.leading_samples_removed/noise_samples:.1f}%)")
    print(f"  Trailing removed: {result.trailing_samples_removed} / {noise_samples} ({100*result.trailing_samples_removed/noise_samples:.1f}%)")
    print(f"  Noise floor: {np.sqrt(result.noise_floor):.5f} RMS")
    print(f"  Peak SNR: {result.peak_snr_db:.1f} dB")

    # Decode trimmed audio
    print("\n[3] Decoding trimmed audio...")
    decoded = decoder.demodulate(result.trimmed_audio)
    print(f"  Decoded: '{decoded}'")

    if test_message in decoded:
        print(f"  ✓ SUCCESS: Message decoded correctly!")
        print(f"     SignalTrimmer fixed the noisy silence problem!")
        return True
    else:
        print(f"  ✗ FAILURE: Message still not decoded")
        return False


def test_real_time_streaming():
    """Test 4: Real-time streaming mode."""
    print("\n" + "="*70)
    print("TEST 4: Real-Time Streaming Mode")
    print("="*70)

    # Generate signal
    encoder = EightPSK_250F()
    decoder = EightPSK_250F_Decoder(squelch_enabled=False)
    test_message = "REALTIME TEST MESSAGE"

    print(f"\n[1] Encoding message: '{test_message}'")
    signal = encoder.modulate(test_message)

    # Add silence for realistic streaming scenario
    silence_before = np.zeros(4000, dtype=np.float32)
    silence_after = np.zeros(4000, dtype=np.float32)
    audio = np.concatenate([silence_before, signal, silence_after])

    print(f"  Total: {len(audio)} samples ({len(audio)/8000:.2f}s)")

    # Process in real-time chunks
    print("\n[2] Processing in real-time chunks with trimmer...")
    trimmer = SignalTrimmer(preset='psk125')
    chunk_size = 512  # ~64ms @ 8kHz

    output_chunks = []
    active_chunks = 0
    idle_chunks = 0

    for i in range(0, len(audio), chunk_size):
        chunk = audio[i:i+chunk_size]
        trimmed_chunk, is_active = trimmer.trim_real_time(chunk)

        if is_active:
            active_chunks += 1
        else:
            idle_chunks += 1

        if len(trimmed_chunk) > 0:
            output_chunks.append(trimmed_chunk)

    # Combine and decode
    if output_chunks:
        trimmed_audio = np.concatenate(output_chunks)
    else:
        trimmed_audio = np.array([], dtype=np.float32)

    print(f"  Active chunks: {active_chunks}")
    print(f"  Idle chunks: {idle_chunks}")
    print(f"  Output: {len(trimmed_audio)} samples ({100*len(trimmed_audio)/len(audio):.1f}% of input)")

    print("\n[3] Decoding streamed output...")
    decoded = decoder.demodulate(trimmed_audio)
    print(f"  Decoded: '{decoded}'")

    if test_message in decoded:
        print(f"  ✓ SUCCESS: Real-time trimming works!")
        return True
    else:
        print(f"  ✗ PARTIAL: Message not fully decoded")
        return False


def test_various_noise_levels():
    """Test 5: Various noise levels."""
    print("\n" + "="*70)
    print("TEST 5: Various Noise Levels")
    print("="*70)

    encoder = EightPSK_250F()
    test_message = "NOISE TEST"
    signal = encoder.modulate(test_message)

    noise_levels = [0.001, 0.005, 0.01, 0.02, 0.05]
    noise_samples = 4000

    print(f"\n  Testing with noise levels: {noise_levels}")
    print(f"  Message: '{test_message}'")
    print()

    results = []

    for noise_level in noise_levels:
        # Create noisy audio
        leading_noise = np.random.normal(0, noise_level, noise_samples).astype(np.float32)
        trailing_noise = np.random.normal(0, noise_level, noise_samples).astype(np.float32)
        audio = np.concatenate([leading_noise, signal, trailing_noise])

        signal_power = np.mean(signal ** 2)
        noise_power = np.mean(leading_noise ** 2)
        snr_db = 10 * np.log10(signal_power / noise_power)

        # Trim and decode
        trimmer = SignalTrimmer(preset='psk125')
        result = trimmer.trim_deep_search(audio, return_metadata=True)

        decoder = EightPSK_250F_Decoder(squelch_enabled=False)
        decoded = decoder.demodulate(result.trimmed_audio)

        success = test_message in decoded
        results.append(success)

        status = "✓" if success else "✗"
        print(f"  Noise {noise_level:.4f} RMS (SNR {snr_db:5.1f} dB): {status} | " +
              f"Trimmed {result.leading_samples_removed + result.trailing_samples_removed:4d} samples")

    print()
    success_count = sum(results)
    print(f"  Results: {success_count}/{len(noise_levels)} successful")

    return success_count >= len(noise_levels) * 0.6  # 60% success rate


def main():
    """Run all tests."""
    print("\n" + "#"*70)
    print("# SignalTrimmer Test with 8PSK125 FEC")
    print("# Testing the solution to noisy silence decoder issues")
    print("#"*70)

    results = []

    try:
        results.append(("Baseline (pure silence)", test_baseline()))
        results.append(("Noisy silence WITHOUT trimmer", test_noisy_silence_without_trimmer()))
        results.append(("Noisy silence WITH trimmer", test_noisy_silence_with_trimmer()))
        results.append(("Real-time streaming", test_real_time_streaming()))
        results.append(("Various noise levels", test_various_noise_levels()))

        # Summary
        print("\n" + "="*70)
        print("TEST SUMMARY")
        print("="*70)

        for test_name, result in results:
            status = "✓ PASS" if result else "✗ FAIL"
            print(f"  {status:8s} | {test_name}")

        passed = sum(1 for _, r in results if r)
        total = len(results)

        print(f"\n  Overall: {passed}/{total} tests passed")

        if results[2][1]:  # The key test: noisy silence WITH trimmer
            print("\n" + "#"*70)
            print("# SUCCESS: SignalTrimmer solves the noisy silence issue!")
            print("#"*70)
            return 0
        else:
            print("\n  Note: The trimmer may need tuning for this specific case")
            return 1

    except Exception as e:
        print(f"\n✗ Error during tests: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
