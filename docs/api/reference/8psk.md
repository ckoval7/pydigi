# 8PSK (Eight-Phase PSK)

8PSK uses eight phase states to encode 3 bits per symbol, providing three times the data rate of BPSK at the same baud rate.

## 8PSK Encoder (No FEC)

::: pydigi.modems.psk8
    options:
      show_root_heading: true
      show_source: true

## 8PSK Decoder (No FEC)

The 8PSK decoder supports non-FEC modes (8PSK125, 8PSK250, 8PSK500, 8PSK1000) with MFSK varicode encoding.

### Module Reference

::: pydigi.modems.psk8_decoder
    options:
      show_root_heading: true
      show_source: true
      members:
        - EightPSKDecoder
        - EightPSK_125_Decoder
        - EightPSK_250_Decoder
        - EightPSK_500_Decoder
        - EightPSK_1000_Decoder

### Examples

#### Basic Decoding

```python
from pydigi.modems.psk8_decoder import EightPSKDecoder

# Decode 8PSK250 signal
decoder = EightPSKDecoder(baud=250, frequency=1000)
text = decoder.demodulate(audio_samples)
print(text)
```

#### Using Convenience Functions

```python
from pydigi.modems.psk8_decoder import EightPSK_250_Decoder

# Simpler API for standard modes
decoder = EightPSK_250_Decoder(frequency=1000)
text = decoder.demodulate(audio_samples)
```

## 8PSK Encoder with FEC

8PSK with Forward Error Correction adds convolutional coding and interleaving for improved reliability.

::: pydigi.modems.psk8_fec
    options:
      show_root_heading: true
      show_source: true

## 8PSK Decoder with FEC

The 8PSK FEC decoder supports FEC modes (8PSK125F, 8PSK125FL, 8PSK250F, 8PSK250FL, 8PSK500F, 8PSK1000F, 8PSK1200F) with Viterbi decoding, deinterleaving, and soft decision decoding.

### Overview

The EightPSKFECDecoder class provides advanced decoding features:

- **Gray-mapped constellation** for optimal soft decoding
- **Viterbi algorithm** for convolutional code decoding (K=13 or K=16)
- **Bit deinterleaving** for burst error protection
- **Puncturing support** for higher-rate modes (500F, 1000F, 1200F)
- **Sample-level signal detection** to prevent noise corruption
- **Silence handling** - Properly handles pure silence and noisy silence without FEC corruption

**Status**: ✅ 100% Complete - All 7 modes working (fixed 2026-01-09)

### Module Reference

::: pydigi.modems.psk8_fec_decoder
    options:
      show_root_heading: true
      show_source: true
      members:
        - EightPSKFECDecoder
        - EightPSK_125F_Decoder
        - EightPSK_125FL_Decoder
        - EightPSK_250F_Decoder
        - EightPSK_250FL_Decoder
        - EightPSK_500F_Decoder
        - EightPSK_1000F_Decoder
        - EightPSK_1200F_Decoder

### Examples

#### Basic FEC Decoding

```python
from pydigi.modems.psk8_fec_decoder import EightPSKFECDecoder

# Decode 8PSK250F signal
decoder = EightPSKFECDecoder(baud=250, frequency=1000)
text = decoder.demodulate(audio_samples)
print(text)
```

#### Using Convenience Functions

```python
from pydigi.modems.psk8_fec_decoder import EightPSK_250F_Decoder

# Simpler API for standard FEC modes
decoder = EightPSK_250F_Decoder(frequency=1000)
text = decoder.demodulate(audio_samples)
```

#### Long Interleave Mode

```python
from pydigi.modems.psk8_fec_decoder import EightPSK_250FL_Decoder

# Use long interleave for better burst error protection
decoder = EightPSK_250FL_Decoder(frequency=1000)
text = decoder.demodulate(audio_samples)
```

#### Real-Time Streaming with FEC

```python
from pydigi.modems.psk8_fec_decoder import EightPSKFECDecoder

decoder = EightPSKFECDecoder(baud=250, frequency=1000)

# Set callback for character-by-character output
def on_character(char):
    print(char, end='', flush=True)

decoder.set_text_callback(on_character)

# Process audio stream
for audio_chunk in audio_stream:
    decoder.process(audio_chunk)
```

#### Monitor FEC Metrics

```python
from pydigi.modems.psk8_fec_decoder import EightPSKFECDecoder

decoder = EightPSKFECDecoder(baud=250, frequency=1000, afc_enabled=True)

# Process some audio
decoder.process(audio_samples)

# Check decoder statistics
stats = decoder.get_stats()
print(f"Signal quality: {stats['metric']:.1f}")
print(f"FEC metric: {stats['fecmet']:.1f}")
print(f"DCD: {stats['dcd']}")
print(f"Frequency: {stats['frequency']:.1f} Hz")
```
