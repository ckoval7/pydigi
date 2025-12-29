#!/usr/bin/env python3
"""
Example: Automatic PSK signal detection and decoding

This example shows:
1. Automatic carrier frequency detection using FFT peak detection
2. Handling multiple simultaneous PSK signals

Usage:
    # Auto-detect and decode single signal
    python auto_detect_psk.py <wav_file> <baud>

    # Auto-detect and decode multiple signals
    python auto_detect_psk.py <wav_file> <baud> --multi

Examples:
    python auto_detect_psk.py test.wav 125
    python auto_detect_psk.py multi_signal.wav 31.25 --multi
"""

import sys
import os
import numpy as np
import wave
from typing import Dict

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from pydigi.core.signal_detector import SignalDetector, MultiSignalDetector
from pydigi.modems.psk_decoder import PSKDecoder


def load_wav(filename):
    """Load WAV file and return samples and sample rate."""
    with wave.open(filename, 'rb') as wf:
        n_channels = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        framerate = wf.getframerate()
        n_frames = wf.getnframes()

        print(f"WAV file: {filename}")
        print(f"  Duration: {n_frames/framerate:.2f} seconds")
        print(f"  Sample rate: {framerate} Hz")

        audio_bytes = wf.readframes(n_frames)

        if sampwidth == 2:
            samples = np.frombuffer(audio_bytes, dtype=np.int16)
            samples = samples.astype(np.float32) / 32768.0
        elif sampwidth == 4:
            samples = np.frombuffer(audio_bytes, dtype=np.float32)
        else:
            raise ValueError(f"Unsupported sample width: {sampwidth}")

        if n_channels == 2:
            samples = samples.reshape(-1, 2).mean(axis=1)

        return samples, framerate


def auto_detect_single_signal(wav_file: str, baud: float):
    """
    Automatically detect and decode a single PSK signal.

    Args:
        wav_file: Path to WAV file
        baud: PSK baud rate
    """
    print(f"\n{'='*70}")
    print(f"AUTO-DETECT AND DECODE PSK{int(baud)}")
    print(f"{'='*70}\n")

    # Load audio
    samples, sample_rate = load_wav(wav_file)
    print()

    # Step 1: Detect carrier frequency
    print("[1/3] Detecting carrier frequency...")
    detector = SignalDetector(
        sample_rate=sample_rate,
        fft_size=8192,  # Larger FFT for better frequency resolution
        min_freq=500,
        max_freq=2500,
        threshold_db=6.0,
        estimator='multi'  # Use multi-estimator for best accuracy
    )

    # Use enough samples for FFT (at least 2x FFT size)
    detect_samples = min(len(samples), detector.fft_size * 2)
    peaks = detector.detect(samples[:detect_samples], num_peaks=5)

    if not peaks:
        print("  ✗ No signals detected!")
        return

    print(f"  ✓ Found {len(peaks)} signal(s):")
    for i, peak in enumerate(peaks):
        print(f"    [{i+1}] {peak.frequency:.1f} Hz - SNR: {peak.snr:.1f} dB")

    # Use strongest signal
    carrier_freq = peaks[0].frequency
    print(f"\n  Using strongest signal at {carrier_freq:.1f} Hz")

    # Step 2: Initialize decoder
    print(f"\n[2/3] Initializing PSK{int(baud)} decoder...")
    decoder = PSKDecoder(
        baud=baud,
        sample_rate=sample_rate,
        frequency=carrier_freq,
        afc_enabled=True,
        squelch_enabled=False,
    )

    # Collect decoded text
    decoded_text = []
    def text_callback(char):
        decoded_text.append(char)
        print(char, end='', flush=True)

    decoder.set_text_callback(text_callback)

    # Step 3: Decode
    print(f"\n[3/3] Decoding...\n")
    print("-" * 70)
    decoder.process(samples)
    print()
    print("-" * 70)

    # Show results
    stats = decoder.get_stats()
    print(f"\nResults:")
    print(f"  Decoded text: '{''.join(decoded_text)}'")
    print(f"  Symbols: {stats['symbols_received']}")
    print(f"  Characters: {stats['chars_decoded']}")
    print(f"  Metric: {stats['metric']:.2f}")
    print(f"  Final frequency: {stats['frequency']:.2f} Hz (error: {stats['freqerr']:.4f} Hz)")


def auto_detect_multi_signal(wav_file: str, baud: float):
    """
    Automatically detect and decode multiple simultaneous PSK signals.

    This creates a separate decoder instance for each detected signal.

    Args:
        wav_file: Path to WAV file
        baud: PSK baud rate
    """
    print(f"\n{'='*70}")
    print(f"MULTI-SIGNAL DETECTION - PSK{int(baud)}")
    print(f"{'='*70}\n")

    # Load audio
    samples, sample_rate = load_wav(wav_file)
    print()

    # Step 1: Detect all signals
    print("[1/3] Detecting signals...")
    detector = SignalDetector(
        sample_rate=sample_rate,
        fft_size=8192,  # Larger FFT for better frequency resolution
        min_freq=500,
        max_freq=2500,
        threshold_db=6.0,
        estimator='multi'  # Use multi-estimator for best accuracy
    )

    # Use enough samples for FFT
    detect_samples = min(len(samples), detector.fft_size * 2)
    peaks = detector.detect(
        samples[:detect_samples],
        num_peaks=10,  # Look for up to 10 signals
        min_spacing_hz=150  # Minimum 150 Hz apart
    )

    if not peaks:
        print("  ✗ No signals detected!")
        return

    print(f"  ✓ Found {len(peaks)} signal(s):")
    for i, peak in enumerate(peaks):
        print(f"    [{i+1}] {peak.frequency:.1f} Hz - SNR: {peak.snr:.1f} dB")

    # Step 2: Create decoder for each signal
    print(f"\n[2/3] Creating {len(peaks)} decoder instances...")
    decoders: Dict[int, PSKDecoder] = {}
    decoded_texts: Dict[int, list] = {}

    for i, peak in enumerate(peaks):
        freq = peak.frequency
        print(f"  Decoder {i+1}: {freq:.1f} Hz")

        decoder = PSKDecoder(
            baud=baud,
            sample_rate=sample_rate,
            frequency=freq,
            afc_enabled=True,
            squelch_enabled=True,  # Use squelch for multi-signal
        )

        # Create text callback for this decoder
        decoded_texts[i] = []
        def make_callback(idx):
            def callback(char):
                decoded_texts[idx].append(char)
            return callback

        decoder.set_text_callback(make_callback(i))
        decoders[i] = decoder

    # Step 3: Decode all signals in parallel
    print(f"\n[3/3] Decoding {len(decoders)} signals in parallel...\n")

    for decoder in decoders.values():
        decoder.process(samples)

    # Show results for each signal
    print("=" * 70)
    print("RESULTS")
    print("=" * 70)

    for i, (decoder, text_list) in enumerate(zip(decoders.values(), decoded_texts.values())):
        peak = peaks[i]
        stats = decoder.get_stats()
        text = ''.join(decoded_texts[i])

        print(f"\nSignal {i+1}: {peak.frequency:.1f} Hz (SNR: {peak.snr:.1f} dB)")
        print(f"  Decoded: '{text}'")
        print(f"  Symbols: {stats['symbols_received']}, Chars: {stats['chars_decoded']}")
        print(f"  Metric: {stats['metric']:.2f}, DCD: {stats['dcd']}")


def show_spectrum(wav_file: str):
    """
    Show spectrum visualization (simple text-based).

    Args:
        wav_file: Path to WAV file
    """
    samples, sample_rate = load_wav(wav_file)
    print()

    detector = SignalDetector(sample_rate=sample_rate)
    freqs, mags = detector.get_spectrum(samples)

    # Find range to display (500-2500 Hz)
    idx_start = np.argmax(freqs >= 500)
    idx_end = np.argmax(freqs >= 2500)

    print("\nSpectrum (500-2500 Hz):")
    print("-" * 70)

    # Get peaks for marking
    peaks = detector.detect(samples, num_peaks=10)
    peak_freqs = {int(p.frequency) for p in peaks}

    # Display spectrum in 50 Hz bins
    for freq in range(500, 2500, 50):
        idx = np.argmax(freqs >= freq)
        if idx < len(mags):
            mag = mags[idx]
            # Normalize to 0-50 range for display
            normalized = int((mag + 100) / 2)  # Assume -100 to 0 dB range
            normalized = max(0, min(50, normalized))

            # Create bar
            bar = '█' * normalized
            marker = ' *' if freq in peak_freqs else ''
            print(f"  {freq:4d} Hz: {bar:50s} {mag:6.1f} dB{marker}")

    print("-" * 70)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    wav_file = sys.argv[1]
    baud = float(sys.argv[2])

    if not os.path.exists(wav_file):
        print(f"Error: File not found: {wav_file}")
        sys.exit(1)

    # Check for multi-signal mode
    multi = '--multi' in sys.argv or '-m' in sys.argv
    spectrum = '--spectrum' in sys.argv or '-s' in sys.argv

    if spectrum:
        show_spectrum(wav_file)
    elif multi:
        auto_detect_multi_signal(wav_file, baud)
    else:
        auto_detect_single_signal(wav_file, baud)
