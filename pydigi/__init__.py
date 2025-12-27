"""
PyDigi - Pure Python implementation of digital modem algorithms from fldigi.

Main package exports for easy access to modems.
"""

__version__ = "0.1.0"

# Import modems for easy access
from .modems.cw import CW
from .modems.rtty import RTTY
from .modems.psk import PSK, PSK31, PSK63, PSK125, PSK250, PSK500
from .modems.qpsk import QPSK, QPSK31, QPSK63, QPSK125, QPSK250, QPSK500
from .modems.psk8 import EightPSK, EightPSK_125, EightPSK_250, EightPSK_500, EightPSK_1000
from .modems.olivia import (
    Olivia, Olivia4_125, Olivia8_250, Olivia8_500,
    Olivia16_500, Olivia16_1000, Olivia32_1000
)
from .modems.contestia import (
    Contestia, Contestia4_125, Contestia4_250, Contestia8_125,
    Contestia8_250, Contestia8_500, Contestia16_500, Contestia32_1000
)
from .modems.mfsk import (
    MFSK, MFSK4, MFSK8, MFSK11, MFSK16, MFSK22, MFSK31,
    MFSK32, MFSK64, MFSK64L, MFSK128, MFSK128L
)
from .modems.dominoex import (
    DominoEX, DominoEX_Micro, DominoEX_4, DominoEX_5, DominoEX_8,
    DominoEX_11, DominoEX_16, DominoEX_22, DominoEX_44, DominoEX_88
)
from .modems.fsq import FSQ, FSQ_2, FSQ_3, FSQ_6
from .modems.thor import (
    Thor, ThorMicro, Thor4, Thor5, Thor8, Thor11, Thor16, Thor22,
    Thor25, Thor32, Thor44, Thor56, Thor25x4, Thor50x1, Thor50x2, Thor100
)
from .modems.throb import (
    Throb, Throb1, Throb2, Throb4, ThrobX1, ThrobX2, ThrobX4
)
from .modems.mt63 import (
    mt63_modulate, mt63_500s_modulate, mt63_500l_modulate,
    mt63_1000s_modulate, mt63_1000l_modulate, mt63_2000s_modulate,
    mt63_2000l_modulate
)

# Import utilities
from .utils.audio import save_wav, load_wav

__all__ = [
    'CW',
    'RTTY',
    'PSK',
    'PSK31',
    'PSK63',
    'PSK125',
    'PSK250',
    'PSK500',
    'QPSK',
    'QPSK31',
    'QPSK63',
    'QPSK125',
    'QPSK250',
    'QPSK500',
    'EightPSK',
    'EightPSK_125',
    'EightPSK_250',
    'EightPSK_500',
    'EightPSK_1000',
    'Olivia',
    'Olivia4_125',
    'Olivia8_250',
    'Olivia8_500',
    'Olivia16_500',
    'Olivia16_1000',
    'Olivia32_1000',
    'Contestia',
    'Contestia4_125',
    'Contestia4_250',
    'Contestia8_125',
    'Contestia8_250',
    'Contestia8_500',
    'Contestia16_500',
    'Contestia32_1000',
    'MFSK',
    'MFSK4',
    'MFSK8',
    'MFSK11',
    'MFSK16',
    'MFSK22',
    'MFSK31',
    'MFSK32',
    'MFSK64',
    'MFSK64L',
    'MFSK128',
    'MFSK128L',
    'DominoEX',
    'DominoEX_Micro',
    'DominoEX_4',
    'DominoEX_5',
    'DominoEX_8',
    'DominoEX_11',
    'DominoEX_16',
    'DominoEX_22',
    'DominoEX_44',
    'DominoEX_88',
    'FSQ',
    'FSQ_2',
    'FSQ_3',
    'FSQ_6',
    'Thor',
    'ThorMicro',
    'Thor4',
    'Thor5',
    'Thor8',
    'Thor11',
    'Thor16',
    'Thor22',
    'Thor25',
    'Thor32',
    'Thor44',
    'Thor56',
    'Thor25x4',
    'Thor50x1',
    'Thor50x2',
    'Thor100',
    'Throb',
    'Throb1',
    'Throb2',
    'Throb4',
    'ThrobX1',
    'ThrobX2',
    'ThrobX4',
    'mt63_modulate',
    'mt63_500s_modulate',
    'mt63_500l_modulate',
    'mt63_1000s_modulate',
    'mt63_1000l_modulate',
    'mt63_2000s_modulate',
    'mt63_2000l_modulate',
    'save_wav',
    'load_wav',
    '__version__',
]
