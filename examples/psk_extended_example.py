#!/usr/bin/env python3
"""
PSK Extended Modes Example

Demonstrates PSK Extended modes including:
- PSK1000: High-speed BPSK at 1000 baud
- PSK63F: PSK63 with Forward Error Correction
- Multi-carrier PSK: Multiple parallel carriers for diversity
"""

from pydigi.modems.psk import PSK1000
from pydigi.modems.psk_extended import (
    PSK63F,
    PSK_2X_PSK500,
    PSK_4X_PSK500,
    PSK_2X_PSK800,
    PSK_2X_PSK1000,
    PSK_6X_PSK250,
    PSK_12X_PSK125,
)
from pydigi.utils.audio import save_wav

# Test message
test_message = "CQ CQ DE W1ABC PSK EXTENDED TEST"

print("=" * 60)
print("PSK Extended Modes Example")
print("=" * 60)
print()

# Example 1: PSK1000 - High speed BPSK
print("1. PSK1000 (1000 baud BPSK)")
print("-" * 40)
psk1000 = PSK1000()
audio = psk1000.modulate(test_message, frequency=1500)
save_wav("psk1000_output.wav", audio, 8000)
duration = len(audio) / 8000
print(f"Mode: {psk1000.mode_name}")
print(f"Baud rate: {psk1000.baud} baud")
print(f"Generated {len(audio)} samples ({duration:.2f} seconds)")
print(f"Saved to: psk1000_output.wav")
print()

# Example 2: PSK63F - PSK63 with FEC
print("2. PSK63F (PSK63 with Forward Error Correction)")
print("-" * 40)
psk63f = PSK63F()
audio = psk63f.modulate(test_message, frequency=1500)
save_wav("psk63f_output.wav", audio, 8000)
duration = len(audio) / 8000
print(f"Mode: {psk63f.mode_name}")
print(f"Baud rate: {psk63f.baud} baud")
print(f"FEC: Convolutional K=5, rate 1/2")
print(f"Varicode: MFSK/ARQ")
print(f"Generated {len(audio)} samples ({duration:.2f} seconds)")
print(f"Saved to: psk63f_output.wav")
print()

# Example 3: 2X_PSK500 - 2 carriers at 500 baud each
print("3. 2X_PSK500 (2 carriers @ 500 baud each)")
print("-" * 40)
psk = PSK_2X_PSK500()
audio = psk.modulate(test_message, frequency=1500)
save_wav("2x_psk500_output.wav", audio, 8000)
duration = len(audio) / 8000
print(f"Mode: {psk.mode_name}")
print(f"Number of carriers: {psk.num_carriers}")
print(f"Baud rate per carrier: {psk.baud} baud")
print(f"Carrier spacing: {psk.separation * psk.baud:.0f} Hz")
print(f"Carrier frequencies: {[f'{f:.0f} Hz' for f in psk._carrier_freqs]}")
print(f"Generated {len(audio)} samples ({duration:.2f} seconds)")
print(f"Saved to: 2x_psk500_output.wav")
print()

# Example 4: 12X_PSK125 - 12 carriers at 125 baud each
print("4. 12X_PSK125 (12 carriers @ 125 baud each)")
print("-" * 40)
psk = PSK_12X_PSK125()
audio = psk.modulate("WIDE BAND TEST 12X PSK", frequency=1500)
save_wav("12x_psk125_output.wav", audio, 8000)
duration = len(audio) / 8000
print(f"Mode: {psk.mode_name}")
print(f"Number of carriers: {psk.num_carriers}")
print(f"Baud rate per carrier: {psk.baud} baud")
print(f"Carrier spacing: {psk.separation * psk.baud:.0f} Hz")
print(f"Total bandwidth: ~{psk.num_carriers * psk.separation * psk.baud:.0f} Hz")
print(f"Generated {len(audio)} samples ({duration:.2f} seconds)")
print(f"Saved to: 12x_psk125_output.wav")
print()

# Example 5: Comparison of different multi-carrier modes
print("5. Multi-carrier PSK Mode Comparison")
print("-" * 40)
modes = [
    ("2X_PSK500", PSK_2X_PSK500()),
    ("4X_PSK500", PSK_4X_PSK500()),
    ("6X_PSK250", PSK_6X_PSK250()),
    ("12X_PSK125", PSK_12X_PSK125()),
    ("2X_PSK800", PSK_2X_PSK800()),
    ("2X_PSK1000", PSK_2X_PSK1000()),
]

short_msg = "TEST"
for name, modem in modes:
    audio = modem.modulate(short_msg, frequency=1500)
    duration = len(audio) / 8000
    bandwidth = modem.num_carriers * modem.separation * modem.baud
    filename = f"{name.lower()}_output.wav"
    save_wav(filename, audio, 8000)
    print(
        f"{name:15s}: {modem.num_carriers:2d} carriers × {modem.baud:4.0f} baud = ~{bandwidth:4.0f} Hz BW, {duration:.2f}s → {filename}"
    )

print()
print("=" * 60)
print("All PSK Extended examples complete!")
print("=" * 60)
print()
print("Mode Summary:")
print("  PSK1000:       High-speed single carrier (1000 baud)")
print("  PSK63F:        PSK63 with FEC for improved reliability")
print("  Multi-carrier: Multiple parallel carriers for diversity")
print()
print("Multi-carrier modes trade bandwidth for robustness against")
print("selective fading and interference.")
print()
