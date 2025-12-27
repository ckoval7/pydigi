The fldigi source code is available in fldigi/. It is to be used for reference only, do not edit anything. Use the fldigi source to find the math for each modem implementation and build a python library. Our primary goal is to use python to provide a function with parameters such as op mode, audio freq, and a text string, and have it return an array of floats with the audio data. This can then be used to feed gnuradio, create a wav file, or other similar uses. Let's support decoding as well, but only after TX works.

Create a project tracker file. Always keep it updated with our current progress.

Previously we tried just building a library around fldigi itself, but that grew insanely complex.

## CRITICAL IMPLEMENTATION REQUIREMENTS

### Preamble and Postamble
**IMPORTANT**: When implementing any new modem mode, ALWAYS check the fldigi source for preamble and postamble requirements:

1. **Preamble** - Synchronization padding sent BEFORE data
   - Allows receiver to detect start of transmission
   - Enables bit/symbol timing synchronization
   - Usually consists of known patterns (RTTY: LTRS characters, PSK: phase reversals)
   - Check fldigi's `tx_init()` and look for `preamble =` assignments
   - Common variable: `dcdbits` (in PSK) or specific character sequences (in RTTY)

2. **Postamble** - Ending padding sent AFTER data
   - Ensures last character decodes properly
   - Helps receiver detect end of transmission
   - Check fldigi's `tx_flush()` function for postamble implementation
   - Usually matches or complements the preamble pattern

3. **How to Find in fldigi Source**:
   - Search for `preamble` in the mode's .cxx file
   - Look at `tx_init()` function - often sets `preamble = dcdbits` or similar
   - Check `tx_process()` or `tx_char()` for preamble sending logic
   - Look for `tx_flush()` function for postamble implementation
   - Search for mode-specific settings like `TTY_LTRS` or `dcdbits`

4. **Examples**:
   - **RTTY**: Sends 8 LTRS characters (code 0x1F) before and after data (configurable)
   - **PSK31**: Sends 32 symbols (phase reversals) as preamble, 32 symbols (0 degrees) as postamble
   - **PSK63**: Sends 64 symbols (scales with baud rate)

Without proper preamble/postamble, decoders will miss characters or fail to decode at all!