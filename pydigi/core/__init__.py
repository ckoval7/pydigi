"""
Core DSP components for pydigi.
"""

from .oscillator import NCO, generate_tone, generate_complex_tone
from .filters import (
    FIRFilter,
    MovingAverageFilter,
    GoertzelFilter,
    sinc,
    cosc,
    hamming,
    blackman,
    raised_cosine,
)
from .fft import (
    fft,
    ifft,
    rfft,
    irfft,
    fftshift,
    ifftshift,
    magnitude_spectrum,
    power_spectrum,
    power_spectrum_db,
    SlidingFFT,
    OverlapAddFFT,
)
from .encoder import ConvolutionalEncoder, create_qpsk_encoder, create_mfsk_encoder
from .fht import fht, ifht
from .mfsk_encoder import MFSKEncoder
from .mfsk_modulator import MFSKModulator
from .interleave import Interleave, INTERLEAVE_FWD, INTERLEAVE_REV
from .dsp_utils import (
    generate_raised_cosine_shape,
    apply_baseband_filter,
    modulate_to_carrier,
    normalize_audio,
)

__all__ = [
    # Oscillator
    "NCO",
    "generate_tone",
    "generate_complex_tone",
    # Filters
    "FIRFilter",
    "MovingAverageFilter",
    "GoertzelFilter",
    "sinc",
    "cosc",
    "hamming",
    "blackman",
    "raised_cosine",
    # FFT
    "fft",
    "ifft",
    "rfft",
    "irfft",
    "fftshift",
    "ifftshift",
    "magnitude_spectrum",
    "power_spectrum",
    "power_spectrum_db",
    "SlidingFFT",
    "OverlapAddFFT",
    # Encoder
    "ConvolutionalEncoder",
    "create_qpsk_encoder",
    "create_mfsk_encoder",
    # FHT and MFSK
    "fht",
    "ifht",
    "MFSKEncoder",
    "MFSKModulator",
    # Interleave
    "Interleave",
    "INTERLEAVE_FWD",
    "INTERLEAVE_REV",
    # DSP Utilities
    "generate_raised_cosine_shape",
    "apply_baseband_filter",
    "modulate_to_carrier",
    "normalize_audio",
]
