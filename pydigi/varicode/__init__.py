"""Varicode encoding/decoding modules for different modem types."""

from . import baudot
from . import psk_varicode
from . import mfsk_varicode
from . import dominoex_varicode
from . import fsq_varicode
from . import thor_varicode
from . import throb_varicode
from . import navtex_varicode

__all__ = [
    "baudot",
    "psk_varicode",
    "mfsk_varicode",
    "dominoex_varicode",
    "fsq_varicode",
    "thor_varicode",
    "throb_varicode",
    "navtex_varicode",
]
