#!/usr/bin/env python3
"""
Example demonstrating audio resampling in pydigi.

This is particularly useful for SCAMP which is fixed at 8000 Hz,
but you want to output at 48000 Hz for modern audio interfaces or SDR hardware.

Also useful for resampling any modem output to match your audio hardware.
"""

import sys

sys.path.insert(0, ".")

import numpy as np
from pydigi.modems.scamp import SCAMP
from pydigi.modems.psk import PSK
from pydigi.modems.rtty import RTTY
from pydigi.utils import (
    resample,
    resample_to_48k,
    resample_from_modem,
    resample_preset,
    get_resampling_info,
)


def example_basic_resampling():
    """Basic resampling example with SCAMP."""
    print("=" * 60)
    print("Example 1: Basic SCAMP resampling (8kHz -> 48kHz)")
    print("=" * 60)

    # SCAMP is locked at 8000 Hz
    scamp = SCAMP(mode="SCAMPFSK", frequency=1500)
    audio_8k = scamp.modulate("HELLO WORLD FROM SCAMP")

    print(f"Original audio: {len(audio_8k)} samples at {scamp.sample_rate} Hz")
    print(f"Duration: {len(audio_8k) / scamp.sample_rate:.2f} seconds")

    # Resample to 48000 Hz
    audio_48k = resample_to_48k(audio_8k, original_rate=8000)

    print(f"Resampled audio: {len(audio_48k)} samples at 48000 Hz")
    print(f"Duration: {len(audio_48k) / 48000:.2f} seconds")
    print(f"Ratio: {len(audio_48k) / len(audio_8k):.1f}x\n")


def example_scamp_resampling():
    """SCAMP resampling example."""
    print("=" * 60)
    print("Example 2: SCAMP resampling (8kHz -> 44.1kHz)")
    print("=" * 60)

    # SCAMP is also locked at 8000 Hz
    scamp = SCAMP(mode="SCAMPFSK", frequency=1000)
    audio_8k = scamp.modulate("CQ CQ CQ DE W1ABC W1ABC K")

    print(f"Original: {len(audio_8k)} samples at {scamp.sample_rate} Hz")

    # Resample to 44100 Hz (CD quality)
    audio_44k = resample(audio_8k, 8000, 44100)

    print(f"Resampled: {len(audio_44k)} samples at 44100 Hz")
    print(f"Ratio: {len(audio_44k) / len(audio_8k):.4f}x\n")


def example_modem_aware_resampling():
    """Automatic resampling based on modem sample rate."""
    print("=" * 60)
    print("Example 3: Modem-aware resampling")
    print("=" * 60)

    # Works with any modem
    psk31 = PSK(baud=31.25, sample_rate=8000)
    audio = psk31.modulate("PSK31 TEST")

    # Automatically detects modem's sample rate
    audio_48k = resample_from_modem(audio, psk31, 48000)

    print(f"PSK31 at {psk31.sample_rate} Hz: {len(audio)} samples")
    print(f"Resampled to 48000 Hz: {len(audio_48k)} samples\n")


def example_preset_resampling():
    """Using resampling presets for common conversions."""
    print("=" * 60)
    print("Example 4: Using presets for common conversions")
    print("=" * 60)

    scamp = SCAMP(mode="SCAMPFSK", frequency=1000)
    audio = scamp.modulate("PRESET TEST")

    # Use convenient presets
    audio_48k = resample_preset(audio, "8k_to_48k")
    audio_44k = resample_preset(audio, "8k_to_44k")
    audio_16k = resample_preset(audio, "8k_to_16k")

    print(f"Original (8kHz): {len(audio)} samples")
    print(f"48kHz preset: {len(audio_48k)} samples")
    print(f"44.1kHz preset: {len(audio_44k)} samples")
    print(f"16kHz preset: {len(audio_16k)} samples\n")


def example_resampling_info():
    """Get detailed information about resampling operations."""
    print("=" * 60)
    print("Example 5: Resampling information and quality")
    print("=" * 60)

    conversions = [
        (8000, 48000),
        (8000, 44100),
        (11025, 48000),
        (8000, 12000),
    ]

    for orig, target in conversions:
        info = get_resampling_info(orig, target)
        print(f"{orig} Hz -> {target} Hz:")
        print(f"  Ratio: {info['ratio']:.4f} ({info['up']}/{info['down']})")
        print(f"  Quality: {info['quality']}")
        print(f"  Recommended method: {info['recommended_method']}")
        print()


def example_save_resampled_wav():
    """Example of generating and saving resampled audio to WAV."""
    print("=" * 60)
    print("Example 6: Generate SCAMP and save as 48kHz WAV")
    print("=" * 60)

    try:
        from scipy.io import wavfile

        # Generate SCAMP signal
        scamp = SCAMP(mode="SCAMPFSK", frequency=1500)
        message = "CQ CQ CQ DE W1ABC W1ABC SCAMP TEST K"
        audio_8k = scamp.modulate(message)

        # Resample to 48kHz
        audio_48k = resample_to_48k(audio_8k)

        # Convert to 16-bit PCM
        audio_int16 = np.int16(audio_48k * 32767)

        # Save to WAV file
        filename = "/tmp/scamp_48khz.wav"
        wavfile.write(filename, 48000, audio_int16)

        print(f"Saved: {filename}")
        print(f"  Sample rate: 48000 Hz")
        print(f"  Duration: {len(audio_48k) / 48000:.2f} seconds")
        print(f"  Format: 16-bit PCM\n")

    except ImportError:
        print("scipy not available for WAV export\n")


def example_gnuradio_use_case():
    """Example for using resampled audio with GNU Radio."""
    print("=" * 60)
    print("Example 7: Preparing audio for GNU Radio at 48kHz")
    print("=" * 60)

    # Many SDR applications use 48000 Hz sample rate
    target_rate = 48000

    # Generate SCAMP signal (locked at 8000 Hz)
    scamp = SCAMP(mode="SCAMPFSK", frequency=1500)
    audio_8k = scamp.modulate("GNU RADIO TEST")

    # Resample for GNU Radio
    audio_48k = resample_to_48k(audio_8k)

    print(f"Generated SCAMP at {scamp.sample_rate} Hz")
    print(f"Resampled to {target_rate} Hz for SDR")
    print(f"Ready to feed to GNU Radio blocks")
    print(f"Signal bandwidth: {scamp.bandwidth_hz} Hz")
    print(f"Center frequency: {scamp.frequency} Hz (audio)\n")


def example_comparison():
    """Compare original vs resampled signal properties."""
    print("=" * 60)
    print("Example 8: Signal preservation during resampling")
    print("=" * 60)

    # Generate test signal
    psk63 = PSK(baud=62.5, sample_rate=8000, frequency=1000)
    audio_8k = psk63.modulate("RESAMPLE TEST")

    # Resample
    audio_48k = resample_to_48k(audio_8k)

    # Check signal properties
    duration_8k = len(audio_8k) / 8000
    duration_48k = len(audio_48k) / 48000

    peak_8k = np.max(np.abs(audio_8k))
    peak_48k = np.max(np.abs(audio_48k))

    rms_8k = np.sqrt(np.mean(audio_8k**2))
    rms_48k = np.sqrt(np.mean(audio_48k**2))

    print(f"Duration preservation:")
    print(f"  8kHz: {duration_8k:.4f} seconds")
    print(f"  48kHz: {duration_48k:.4f} seconds")
    print(f"  Difference: {abs(duration_8k - duration_48k) * 1000:.4f} ms")
    print()
    print(f"Signal level preservation:")
    print(f"  Peak (8kHz): {peak_8k:.6f}")
    print(f"  Peak (48kHz): {peak_48k:.6f}")
    print(f"  RMS (8kHz): {rms_8k:.6f}")
    print(f"  RMS (48kHz): {rms_48k:.6f}")
    print()


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("PYDIGI RESAMPLER EXAMPLES")
    print("=" * 60 + "\n")

    example_basic_resampling()
    example_scamp_resampling()
    example_modem_aware_resampling()
    example_preset_resampling()
    example_resampling_info()
    example_save_resampled_wav()
    example_gnuradio_use_case()
    example_comparison()

    print("=" * 60)
    print("All examples completed!")
    print("=" * 60)
