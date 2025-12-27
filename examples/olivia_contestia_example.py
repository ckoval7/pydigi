"""
Example usage of Olivia and Contestia modems.

This script demonstrates how to use the Olivia and Contestia MFSK modems
with various configurations.
"""

from pydigi import Olivia, Contestia, save_wav
from pydigi import (
    Olivia4_125, Olivia8_250, Olivia8_500, Olivia16_500,
    Olivia16_1000, Olivia32_1000
)
from pydigi import (
    Contestia4_125, Contestia4_250, Contestia8_125, Contestia8_250,
    Contestia8_500, Contestia16_500, Contestia32_1000
)

# Test message
MESSAGE = "CQ CQ CQ DE W1ABC W1ABC K"
SHORT_MESSAGE = "HELLO WORLD"

def main():
    print("PyDigi Olivia and Contestia Modem Examples")
    print("=" * 60)

    # Example 1: Olivia 32/1000 (most popular mode)
    print("\n1. Olivia 32/1000 (popular mode)")
    modem = Olivia32_1000()
    audio = modem.modulate(MESSAGE, frequency=1500)
    save_wav('olivia_32_1000.wav', audio, 8000)
    print(f"   Generated: olivia_32_1000.wav ({len(audio)} samples, {len(audio)/8000:.2f}s)")
    print(f"   Mode: {modem}")

    # Example 2: Olivia 16/500
    print("\n2. Olivia 16/500")
    modem = Olivia16_500()
    audio = modem.modulate(MESSAGE, frequency=1500)
    save_wav('olivia_16_500.wav', audio, 8000)
    print(f"   Generated: olivia_16_500.wav ({len(audio)} samples, {len(audio)/8000:.2f}s)")
    print(f"   Mode: {modem}")

    # Example 3: Olivia 8/250
    print("\n3. Olivia 8/250")
    modem = Olivia8_250()
    audio = modem.modulate(MESSAGE, frequency=1500)
    save_wav('olivia_8_250.wav', audio, 8000)
    print(f"   Generated: olivia_8_250.wav ({len(audio)} samples, {len(audio)/8000:.2f}s)")
    print(f"   Mode: {modem}")

    # Example 4: Olivia 4/125 (narrowest bandwidth)
    print("\n4. Olivia 4/125 (narrowest bandwidth)")
    modem = Olivia4_125()
    audio = modem.modulate(SHORT_MESSAGE, frequency=1500)
    save_wav('olivia_4_125.wav', audio, 8000)
    print(f"   Generated: olivia_4_125.wav ({len(audio)} samples, {len(audio)/8000:.2f}s)")
    print(f"   Mode: {modem}")

    # Example 5: Contestia 8/250 (popular mode)
    print("\n5. Contestia 8/250 (popular mode)")
    modem = Contestia8_250()
    audio = modem.modulate(MESSAGE, frequency=1500)
    save_wav('contestia_8_250.wav', audio, 8000)
    print(f"   Generated: contestia_8_250.wav ({len(audio)} samples, {len(audio)/8000:.2f}s)")
    print(f"   Mode: {modem}")

    # Example 6: Contestia 16/500
    print("\n6. Contestia 16/500")
    modem = Contestia16_500()
    audio = modem.modulate(MESSAGE, frequency=1500)
    save_wav('contestia_16_500.wav', audio, 8000)
    print(f"   Generated: contestia_16_500.wav ({len(audio)} samples, {len(audio)/8000:.2f}s)")
    print(f"   Mode: {modem}")

    # Example 7: Contestia 32/1000
    print("\n7. Contestia 32/1000")
    modem = Contestia32_1000()
    audio = modem.modulate(MESSAGE, frequency=1500)
    save_wav('contestia_32_1000.wav', audio, 8000)
    print(f"   Generated: contestia_32_1000.wav ({len(audio)} samples, {len(audio)/8000:.2f}s)")
    print(f"   Mode: {modem}")

    # Example 8: Contestia 4/125 (narrowest bandwidth)
    print("\n8. Contestia 4/125 (narrowest bandwidth)")
    modem = Contestia4_125()
    audio = modem.modulate(SHORT_MESSAGE, frequency=1500)
    save_wav('contestia_4_125.wav', audio, 8000)
    print(f"   Generated: contestia_4_125.wav ({len(audio)} samples, {len(audio)/8000:.2f}s)")
    print(f"   Mode: {modem}")

    # Example 9: Custom Olivia configuration
    print("\n9. Custom Olivia configuration (64 tones, 2000 Hz BW)")
    modem = Olivia(tones=64, bandwidth=2000, frequency=1500)
    audio = modem.modulate(SHORT_MESSAGE)
    save_wav('olivia_64_2000.wav', audio, 8000)
    print(f"   Generated: olivia_64_2000.wav ({len(audio)} samples, {len(audio)/8000:.2f}s)")
    print(f"   Mode: {modem}")

    # Example 10: Mode comparison (same message, different modes)
    print("\n10. Mode comparison (same message)")
    test_msg = "TEST123"
    modes = [
        (Olivia8_250(), "olivia_8_250_test.wav"),
        (Olivia16_500(), "olivia_16_500_test.wav"),
        (Olivia32_1000(), "olivia_32_1000_test.wav"),
        (Contestia8_250(), "contestia_8_250_test.wav"),
    ]

    print(f"   Message: '{test_msg}'")
    for modem, filename in modes:
        audio = modem.modulate(test_msg, frequency=1500)
        save_wav(f"{filename}", audio, 8000)
        duration = len(audio) / 8000
        print(f"   {modem.mode_name:20s}: {duration:5.2f}s, {len(audio):6d} samples")

    # Example 11: Without preamble/postamble tones
    print("\n11. Olivia 16/500 without preamble/postamble tones")
    modem = Olivia16_500()
    modem.send_start_tones = False
    modem.send_stop_tones = False
    audio = modem.modulate(SHORT_MESSAGE, frequency=1500)
    save_wav('olivia_16_500_no_tones.wav', audio, 8000)
    print(f"   Generated: olivia_16_500_no_tones.wav ({len(audio)} samples, {len(audio)/8000:.2f}s)")
    print(f"   Note: No preamble/postamble tones - shorter transmission")

    # Example 12: Different center frequencies
    print("\n12. Multiple frequencies (simulating multi-channel)")
    modem = Olivia8_250()
    frequencies = [1000, 1500, 2000]
    for i, freq in enumerate(frequencies):
        audio = modem.modulate(f"CH{i+1}", frequency=freq)
        save_wav(f"olivia_8_250_ch{i+1}.wav", audio, 8000)
        print(f"   Channel {i+1}: {freq} Hz - olivia_8_250_ch{i+1}.wav")

    print("\n" + "=" * 60)
    print("All examples completed!")
    print("Generated 20+ WAV files ready for testing in fldigi")
    print("\nTo test in fldigi:")
    print("1. Load one of the WAV files")
    print("2. Select the corresponding Olivia or Contestia mode")
    print("3. Tune to the signal and it should decode")


if __name__ == "__main__":
    main()
