#!/usr/bin/env python3
"""
Throb Modem Examples

This script demonstrates all six Throb modes with various test scenarios.

Throb is a dual-tone amplitude-modulated mode where each character is
represented by two simultaneous tones. It's highly resistant to propagation-
induced phase shifts and requires no carrier tracking.

Reference: fldigi/src/throb/throb.cxx
"""

from pydigi import Throb1, Throb2, Throb4, ThrobX1, ThrobX2, ThrobX4, save_wav


def example1_basic_throb():
    """Example 1: Basic Throb1 transmission (slowest mode)."""
    print("Example 1: Basic Throb1 (1 baud)")

    modem = Throb1()
    text = "CQ CQ DE W1ABC"

    audio = modem.modulate(text, frequency=1500)
    duration = modem.estimate_duration(text)

    save_wav("throb1_basic.wav", audio, 8000)

    print(f"  Text: '{text}'")
    print(f"  Duration: {duration:.2f}s")
    print(f"  Samples: {len(audio)}")
    print(f"  Mode: Throb1 (9 tones, 45 chars, 1 baud)")
    print()


def example2_mode_comparison():
    """Example 2: Compare all three regular Throb modes."""
    print("Example 2: Throb Mode Comparison")

    text = "TEST"

    modes = [
        ("Throb1", Throb1(), "1 baud, narrow"),
        ("Throb2", Throb2(), "2 baud, narrow"),
        ("Throb4", Throb4(), "4 baud, wide"),
    ]

    for mode_name, modem, description in modes:
        audio = modem.modulate(text, frequency=1500)
        duration = modem.estimate_duration(text)

        filename = f"throb_{mode_name.lower()}_compare.wav"
        save_wav(filename, audio, 8000)

        print(f"  {mode_name}: {duration:.2f}s ({description})")

    print()


def example3_throbx_modes():
    """Example 3: ThrobX modes (extended character set)."""
    print("Example 3: ThrobX Modes (Extended Character Set)")

    text = "HELLO WORLD!"

    modes = [
        ("ThrobX1", ThrobX1(), "1 baud, 11 tones, 55 chars"),
        ("ThrobX2", ThrobX2(), "2 baud, 11 tones, 55 chars"),
        ("ThrobX4", ThrobX4(), "4 baud, 11 tones, 55 chars"),
    ]

    for mode_name, modem, description in modes:
        audio = modem.modulate(text, frequency=1500)
        duration = modem.estimate_duration(text)

        filename = f"throb_{mode_name.lower()}_test.wav"
        save_wav(filename, audio, 8000)

        print(f"  {mode_name}: {duration:.2f}s ({description})")

    print()


def example4_special_characters():
    """Example 4: Special characters in Throb and ThrobX."""
    print("Example 4: Special Characters")

    # Throb uses shift codes for special characters
    text_throb = "TEST-123"  # '-' requires shift
    modem_throb = Throb2()
    audio_throb = modem_throb.modulate(text_throb, frequency=1500)
    save_wav("throb2_special_chars.wav", audio_throb, 8000)
    print(f"  Throb2: '{text_throb}' (shift codes for '-')")

    # ThrobX has extended character set with more punctuation
    text_throbx = "TEST-123 @#!"
    modem_throbx = ThrobX2()
    audio_throbx = modem_throbx.modulate(text_throbx, frequency=1500)
    save_wav("throbx2_special_chars.wav", audio_throbx, 8000)
    print(f"  ThrobX2: '{text_throbx}' (extended charset)")
    print()


def example5_frequency_tests():
    """Example 5: Different center frequencies."""
    print("Example 5: Different Center Frequencies")

    text = "FREQ TEST"
    modem = Throb4()  # Fast mode for quicker tests

    frequencies = [1000, 1500, 2000]

    for freq in frequencies:
        audio = modem.modulate(text, frequency=freq)
        filename = f"throb4_freq_{freq}hz.wav"
        save_wav(filename, audio, 8000)
        print(f"  Generated: {filename} (center: {freq} Hz)")

    print()


def example6_numbers_punctuation():
    """Example 6: Numbers and punctuation."""
    print("Example 6: Numbers and Punctuation")

    text = "123 456 7890"
    modem = Throb2()

    audio = modem.modulate(text, frequency=1500)
    duration = modem.estimate_duration(text)

    save_wav("throb2_numbers.wav", audio, 8000)

    print(f"  Text: '{text}'")
    print(f"  Duration: {duration:.2f}s")
    print()


def example7_long_message():
    """Example 7: Longer message transmission."""
    print("Example 7: Long Message")

    text = "THE QUICK BROWN FOX JUMPS OVER THE LAZY DOG"
    modem = Throb4()  # Use faster mode for long messages

    audio = modem.modulate(text, frequency=1500)
    duration = modem.estimate_duration(text)

    save_wav("throb4_long_message.wav", audio, 8000)

    print(f"  Text: '{text}'")
    print(f"  Duration: {duration:.2f}s")
    print(f"  Characters: {len(text)}")
    print()


def example8_speed_comparison():
    """Example 8: Speed comparison across all modes."""
    print("Example 8: Speed Comparison (All 6 Modes)")

    text = "SPEED TEST 123"

    modes = [
        ("Throb1", Throb1()),
        ("Throb2", Throb2()),
        ("Throb4", Throb4()),
        ("ThrobX1", ThrobX1()),
        ("ThrobX2", ThrobX2()),
        ("ThrobX4", ThrobX4()),
    ]

    for mode_name, modem in modes:
        audio = modem.modulate(text, frequency=1500)
        duration = modem.estimate_duration(text)

        filename = f"throb_{mode_name.lower()}_speed.wav"
        save_wav(filename, audio, 8000)

        # Calculate effective baud rate
        symbols = len(text) + 5  # Approximate (includes preamble/postamble)
        effective_baud = symbols / duration

        print(f"  {mode_name:10s}: {duration:6.2f}s ({effective_baud:.2f} baud)")

    print()


def example9_throbx_punctuation():
    """Example 9: ThrobX extended punctuation set."""
    print("Example 9: ThrobX Extended Punctuation")

    # ThrobX supports many more punctuation characters
    text = "TEST: #@ + - ; ? !"
    modem = ThrobX2()

    audio = modem.modulate(text, frequency=1500)
    duration = modem.estimate_duration(text)

    save_wav("throbx2_punctuation.wav", audio, 8000)

    print(f"  Text: '{text}'")
    print(f"  Duration: {duration:.2f}s")
    print(f"  Extended charset: # @ + - ; : ? ! =")
    print()


def example10_all_modes():
    """Example 10: Generate test file for each mode with same message."""
    print("Example 10: All Modes - Same Message")

    text = "TEST 123"

    modes = [
        ("Throb1", Throb1()),
        ("Throb2", Throb2()),
        ("Throb4", Throb4()),
        ("ThrobX1", ThrobX1()),
        ("ThrobX2", ThrobX2()),
        ("ThrobX4", ThrobX4()),
    ]

    print(f"  Message: '{text}'")
    print(f"\n  Mode      Duration  Samples   Bandwidth")
    print(f"  --------  --------  --------  ---------")

    for mode_name, modem in modes:
        audio = modem.modulate(text, frequency=1500)
        duration = modem.estimate_duration(text)

        # Estimate bandwidth
        if "X" in mode_name:
            if "4" in mode_name:
                bw = 156  # ThrobX4 wide
            else:
                bw = 78  # ThrobX1/2 narrow
        else:
            if "4" in mode_name:
                bw = 128  # Throb4 wide
            else:
                bw = 64  # Throb1/2 narrow

        filename = f"throb_all_{mode_name.lower()}.wav"
        save_wav(filename, audio, 8000)

        print(f"  {mode_name:8s}  {duration:6.2f}s  {len(audio):8d}  {bw:5d} Hz")

    print()


if __name__ == "__main__":
    print("=" * 70)
    print("Throb Modem Examples")
    print("=" * 70)
    print()

    example1_basic_throb()
    example2_mode_comparison()
    example3_throbx_modes()
    example4_special_characters()
    example5_frequency_tests()
    example6_numbers_punctuation()
    example7_long_message()
    example8_speed_comparison()
    example9_throbx_punctuation()
    example10_all_modes()

    print("=" * 70)
    print("All examples completed successfully!")
    print("=" * 70)
