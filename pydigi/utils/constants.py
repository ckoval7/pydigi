"""
Constants used throughout pydigi.
"""

# Sample rates
DEFAULT_SAMPLE_RATE = 8000  # Hz
COMMON_SAMPLE_RATES = [8000, 11025, 22050, 44100, 48000]

# Frequency ranges (audio frequencies, not RF)
MIN_AUDIO_FREQ = 200  # Hz
MAX_AUDIO_FREQ = 3500  # Hz
DEFAULT_FREQ = 1000  # Hz

# Buffer sizes
OUTPUT_BUFFER_SIZE = 65536  # From fldigi modem.h

# Mathematical constants
TWOPI = 6.283185307179586  # 2 * pi
