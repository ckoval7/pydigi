# Throb

Throb is a dual-tone amplitude-modulated digital mode where each character is represented by two simultaneous tones. The mode is highly resistant to propagation-induced phase shifts and requires no carrier tracking.

Available in 6 modes:
- **Throb1/2/4**: Standard modes with 9 tones, 45 characters
- **ThrobX1/2/4**: Extended modes with 11 tones, 55 characters

## Module Reference

::: pydigi.modems.throb
    options:
      show_root_heading: true
      show_source: true
      members:
        - Throb
        - Throb1
        - Throb2
        - Throb4
        - ThrobX1
        - ThrobX2
        - ThrobX4

## Varicode Reference

::: pydigi.varicode.throb_varicode
    options:
      show_root_heading: true
      show_source: true
      members:
        - encode_throb
        - encode_throbx
        - get_tone_pair
        - ThrobEncoder
        - ThrobXEncoder

## Decoder

For decoding Throb signals, see the [Throb Decoder](throb_decoder.md) documentation
