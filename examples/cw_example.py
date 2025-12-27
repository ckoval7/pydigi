#!/usr/bin/env python3
"""
Example: Generate CW (Morse Code) audio.

This example demonstrates how to use the CW modem to generate
Morse code audio and save it to a WAV file.
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from pydigi import CW, save_wav


def main():
    print("PyDigi CW (Morse Code) Example")
    print("=" * 50)

    # Create CW modem instance
    # Parameters:
    #   wpm: Words per minute (5-200, typical 10-40)
    #   rise_time: Edge rise time in ms (prevents key clicks)
    #   sample_rate: Audio sample rate in Hz
    #   frequency: Audio tone frequency in Hz
    cw = CW(wpm=20, rise_time=4.0, sample_rate=8000, frequency=800)

    # Text to transmit
    text = "CQ CQ CQ DE W1ABC W1ABC K"

    print(f"\nGenerating Morse code for: {text}")
    print(f"Speed: {cw.wpm} WPM")
    print(f"Frequency: {cw.frequency} Hz")
    print(f"Sample rate: {cw.sample_rate} Hz")

    # Estimate duration
    duration = cw.estimate_duration(text)
    print(f"Estimated duration: {duration:.2f} seconds")

    # Generate audio
    print("\nGenerating audio...")
    audio = cw.modulate(text)

    print(f"Generated {len(audio)} samples ({len(audio)/cw.sample_rate:.2f} seconds)")
    print(f"Peak amplitude: {max(abs(audio)):.3f}")

    # Save to WAV file
    output_file = "cw_output.wav"
    print(f"\nSaving to {output_file}...")
    save_wav(output_file, audio, sample_rate=int(cw.sample_rate))

    print(f"Done! WAV file saved to {output_file}")
    print("\nYou can now:")
    print("  1. Play the file with any audio player")
    print("  2. Decode it with fldigi or similar software")
    print("  3. Use it with GNU Radio or other DSP tools")

    # Generate a second example with different parameters
    print("\n" + "=" * 50)
    print("Generating second example at 15 WPM, 1000 Hz...")

    cw2 = CW(wpm=15, frequency=1000)
    text2 = "HELLO WORLD"
    audio2 = cw2.modulate(text2)

    output_file2 = "cw_output_15wpm.wav"
    save_wav(output_file2, audio2, sample_rate=int(cw2.sample_rate))
    print(f"Saved to {output_file2}")

    # Example with prosigns
    print("\n" + "=" * 50)
    print("Generating example with prosigns...")

    cw3 = CW(wpm=25, frequency=850)
    text3 = "TEST <AR> <SK>"  # AR = end of message, SK = end of contact
    audio3 = cw3.modulate(text3)

    output_file3 = "cw_prosigns.wav"
    save_wav(output_file3, audio3, sample_rate=int(cw3.sample_rate))
    print(f"Text: {text3}")
    print(f"Saved to {output_file3}")


if __name__ == "__main__":
    main()
