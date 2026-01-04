#!/usr/bin/env python3
"""
Signal Trimming Demo

Demonstrates the SignalTrimmer utility for removing leading/trailing silence
from audio signals. Shows both deep search (pre-recorded) and real-time modes.
"""

import sys
import os
import numpy as np

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from pydigi.modems.psk import PSK
from pydigi.utils.signal_trimmer import SignalTrimmer
from pydigi.utils.audio import save_wav


def demo_deep_search():
    """Demonstrate deep search mode for pre-recorded signals."""
    print("\n" + "="*70)
    print("DEMO 1: Deep Search Mode (Pre-recorded Signals)")
    print("="*70)

    # Generate a PSK signal with silence padding
    print("\n[1] Generating PSK31 signal with silence...")
    psk = PSK(baud=31.25, leading_silence=0.5, trailing_silence=0.5)
    test_message = "CQ CQ CQ DE W1ABC PSK31 TEST"
    audio_with_silence = psk.modulate(test_message)

    print(f"  Message: '{test_message}'")
    print(f"  Audio length: {len(audio_with_silence)} samples ({len(audio_with_silence)/8000:.2f}s)")
    print(f"  Expected silence: 0.5s leading + 0.5s trailing = 1.0s total")

    # Trim using deep search
    print("\n[2] Trimming with deep search...")
    trimmer = SignalTrimmer(preset='psk31')
    result = trimmer.trim_deep_search(audio_with_silence, return_metadata=True)

    print(f"\n  Results:")
    print(f"    Trimmed length: {len(result.trimmed_audio)} samples ({len(result.trimmed_audio)/8000:.2f}s)")
    print(f"    Leading silence removed: {result.leading_samples_removed} samples ({result.leading_samples_removed/8000:.3f}s)")
    print(f"    Trailing silence removed: {result.trailing_samples_removed} samples ({result.trailing_samples_removed/8000:.3f}s)")
    print(f"    Total reduction: {result.leading_samples_removed + result.trailing_samples_removed} samples ({(result.leading_samples_removed + result.trailing_samples_removed)/8000:.3f}s)")
    print(f"    Noise floor: {np.sqrt(result.noise_floor):.6f} RMS")
    print(f"    Peak SNR: {result.peak_snr_db:.1f} dB")
    print(f"    Detection method: {result.detection_method}")

    # Save results
    print("\n[3] Saving audio files...")
    os.makedirs('/tmp/pydigi_demo', exist_ok=True)
    save_wav('/tmp/pydigi_demo/original_with_silence.wav', audio_with_silence)
    save_wav('/tmp/pydigi_demo/trimmed.wav', result.trimmed_audio)
    print(f"  Saved: /tmp/pydigi_demo/original_with_silence.wav")
    print(f"  Saved: /tmp/pydigi_demo/trimmed.wav")

    print("\n  ✓ Deep search demo complete!")


def demo_noisy_silence():
    """Demonstrate handling of noisy silence."""
    print("\n" + "="*70)
    print("DEMO 2: Noisy Silence Handling")
    print("="*70)

    # Generate signal with noisy silence
    print("\n[1] Generating signal with noisy silence...")
    psk = PSK(baud=63, leading_silence=0.0, trailing_silence=0.0)
    signal = psk.modulate("TESTING NOISY SILENCE")

    # Add noise before and after
    noise_level = 0.005  # RMS
    noise_duration = 0.5  # seconds
    noise_samples = int(noise_duration * 8000)

    leading_noise = np.random.normal(0, noise_level, noise_samples).astype(np.float32)
    trailing_noise = np.random.normal(0, noise_level, noise_samples).astype(np.float32)
    audio = np.concatenate([leading_noise, signal, trailing_noise])

    signal_power = np.mean(signal ** 2)
    noise_power = np.mean(leading_noise ** 2)
    snr_db = 10 * np.log10(signal_power / noise_power)

    print(f"  Signal length: {len(signal)} samples")
    print(f"  Leading noise: {noise_samples} samples ({noise_level:.4f} RMS)")
    print(f"  Trailing noise: {noise_samples} samples ({noise_level:.4f} RMS)")
    print(f"  Signal SNR: {snr_db:.1f} dB")

    # Trim
    print("\n[2] Trimming noisy signal...")
    trimmer = SignalTrimmer(preset='psk63', snr_threshold_db=10.0)
    result = trimmer.trim_deep_search(audio, return_metadata=True)

    print(f"\n  Results:")
    print(f"    Original: {len(audio)} samples")
    print(f"    Trimmed: {len(result.trimmed_audio)} samples")
    print(f"    Leading removed: {result.leading_samples_removed}/{noise_samples} ({100*result.leading_samples_removed/noise_samples:.1f}%)")
    print(f"    Trailing removed: {result.trailing_samples_removed}/{noise_samples} ({100*result.trailing_samples_removed/noise_samples:.1f}%)")
    print(f"    Estimated noise floor: {np.sqrt(result.noise_floor):.5f} RMS (expected ~{noise_level:.5f})")
    print(f"    Peak SNR: {result.peak_snr_db:.1f} dB")

    # Save
    print("\n[3] Saving audio files...")
    save_wav('/tmp/pydigi_demo/noisy_original.wav', audio)
    save_wav('/tmp/pydigi_demo/noisy_trimmed.wav', result.trimmed_audio)
    print(f"  Saved: /tmp/pydigi_demo/noisy_original.wav")
    print(f"  Saved: /tmp/pydigi_demo/noisy_trimmed.wav")

    print("\n  ✓ Noisy silence demo complete!")


def demo_real_time():
    """Demonstrate real-time mode for streaming audio."""
    print("\n" + "="*70)
    print("DEMO 3: Real-Time Mode (Streaming)")
    print("="*70)

    # Generate test signal
    print("\n[1] Generating streaming test signal...")
    psk = PSK(baud=125, leading_silence=0.3, trailing_silence=0.3)
    test_message = "REAL TIME TEST MESSAGE"
    audio = psk.modulate(test_message)

    print(f"  Message: '{test_message}'")
    print(f"  Total length: {len(audio)} samples ({len(audio)/8000:.2f}s)")

    # Process in chunks (simulate streaming)
    print("\n[2] Processing in real-time chunks...")
    trimmer = SignalTrimmer(preset='psk125')
    chunk_size = 512  # ~64ms chunks @ 8kHz
    output_chunks = []
    signal_active_count = 0
    signal_inactive_count = 0

    print(f"  Chunk size: {chunk_size} samples ({chunk_size/8000*1000:.1f}ms)")
    print(f"\n  Processing:")

    for i in range(0, len(audio), chunk_size):
        chunk = audio[i:i+chunk_size]
        trimmed_chunk, is_active = trimmer.trim_real_time(chunk)

        if is_active:
            signal_active_count += 1
        else:
            signal_inactive_count += 1

        if len(trimmed_chunk) > 0:
            output_chunks.append(trimmed_chunk)

        # Print status every 10 chunks
        if (i // chunk_size) % 10 == 0:
            status = "ACTIVE" if is_active else "IDLE"
            print(f"    Chunk {i//chunk_size:3d}: {status:8s} | Input: {len(chunk):3d} → Output: {len(trimmed_chunk):3d} samples")

    # Combine output
    if output_chunks:
        output_audio = np.concatenate(output_chunks)
    else:
        output_audio = np.array([], dtype=np.float32)

    print(f"\n  Results:")
    print(f"    Input chunks: {len(audio)//chunk_size}")
    print(f"    Active chunks: {signal_active_count}")
    print(f"    Idle chunks: {signal_inactive_count}")
    print(f"    Original length: {len(audio)} samples")
    print(f"    Trimmed length: {len(output_audio)} samples")
    print(f"    Reduction: {len(audio) - len(output_audio)} samples ({100*(1 - len(output_audio)/len(audio)):.1f}%)")

    # Save
    print("\n[3] Saving audio files...")
    save_wav('/tmp/pydigi_demo/realtime_original.wav', audio)
    save_wav('/tmp/pydigi_demo/realtime_trimmed.wav', output_audio)
    print(f"  Saved: /tmp/pydigi_demo/realtime_original.wav")
    print(f"  Saved: /tmp/pydigi_demo/realtime_trimmed.wav")

    print("\n  ✓ Real-time demo complete!")


def demo_presets():
    """Demonstrate different preset configurations."""
    print("\n" + "="*70)
    print("DEMO 4: Preset Configurations")
    print("="*70)

    # Generate test signal
    psk = PSK(baud=31.25, leading_silence=0.5, trailing_silence=0.5)
    audio = psk.modulate("PRESET TEST")

    print(f"\n  Test signal: {len(audio)} samples ({len(audio)/8000:.2f}s)")
    print(f"\n  Comparing different presets:\n")

    presets = ['psk31', 'weak_signals', 'noisy_environment']

    for preset in presets:
        trimmer = SignalTrimmer(preset=preset)
        result = trimmer.trim_deep_search(audio, return_metadata=True)

        print(f"  Preset: {preset:20s}")
        print(f"    SNR threshold: {trimmer.snr_threshold_db:5.1f} dB")
        print(f"    Trimmed length: {len(result.trimmed_audio):5d} samples")
        print(f"    Leading removed: {result.leading_samples_removed:4d} samples ({result.leading_samples_removed/8000:.3f}s)")
        print(f"    Trailing removed: {result.trailing_samples_removed:4d} samples ({result.trailing_samples_removed/8000:.3f}s)")
        print()

    print("  ✓ Preset comparison complete!")


def demo_configuration():
    """Demonstrate dynamic configuration."""
    print("\n" + "="*70)
    print("DEMO 5: Dynamic Configuration")
    print("="*70)

    # Create trimmer
    print("\n[1] Creating trimmer with default settings...")
    trimmer = SignalTrimmer()
    print(f"  Initial SNR threshold: {trimmer.snr_threshold_db} dB")
    print(f"  Initial noise window: {trimmer.noise_window_duration} s")

    # Update configuration
    print("\n[2] Updating configuration...")
    trimmer.configure(snr_threshold_db=15.0, noise_window_duration=0.2)
    print(f"  Updated SNR threshold: {trimmer.snr_threshold_db} dB")
    print(f"  Updated noise window: {trimmer.noise_window_duration} s")

    # Test with signal
    psk = PSK(baud=31.25, leading_silence=0.4, trailing_silence=0.4)
    audio = psk.modulate("CONFIG TEST")

    result_before = SignalTrimmer(snr_threshold_db=10.0).trim_deep_search(audio, return_metadata=True)
    result_after = trimmer.trim_deep_search(audio, return_metadata=True)

    print(f"\n[3] Comparison:")
    print(f"  With SNR 10 dB: trimmed to {len(result_before.trimmed_audio)} samples")
    print(f"  With SNR 15 dB: trimmed to {len(result_after.trimmed_audio)} samples")
    print(f"  Difference: {abs(len(result_after.trimmed_audio) - len(result_before.trimmed_audio))} samples")

    print("\n  ✓ Configuration demo complete!")


def main():
    """Run all demos."""
    print("\n" + "#"*70)
    print("# SignalTrimmer Demonstration")
    print("# Generic signal detection and silence trimming utility")
    print("#"*70)

    try:
        demo_deep_search()
        demo_noisy_silence()
        demo_real_time()
        demo_presets()
        demo_configuration()

        print("\n" + "#"*70)
        print("# All demos completed successfully!")
        print("#"*70)
        print(f"\nAudio files saved to: /tmp/pydigi_demo/")
        print("You can listen to them to compare original vs. trimmed audio.")

    except Exception as e:
        print(f"\n✗ Error during demo: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == '__main__':
    sys.exit(main())
