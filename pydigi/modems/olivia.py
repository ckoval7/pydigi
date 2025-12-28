"""Olivia modem implementation.

Olivia is a robust MFSK (Multiple Frequency Shift Keying) mode with strong Forward
Error Correction (FEC) designed for weak signal HF work. It uses Fast Hadamard Transform
for FEC encoding and provides excellent performance under noisy conditions.

The Olivia mode family offers 36 different configurations combining various numbers
of tones (4, 8, 16, 32, 64) with different bandwidths (125, 250, 500, 1000, 2000 Hz).
The most popular variant is Olivia 32/1000 (32 tones, 1000 Hz bandwidth).

Key Features:
    - MFSK modulation with 4-256 tones
    - Strong FEC using Fast Hadamard Transform
    - Multiple bandwidth options (125-2000 Hz)
    - Excellent weak-signal performance
    - Block interleaving for time diversity
    - Ideal for HF propagation conditions

Common Modes:
    - Olivia 4/125: 4 tones, 125 Hz bandwidth (very narrow)
    - Olivia 8/250: 8 tones, 250 Hz bandwidth
    - Olivia 16/500: 16 tones, 500 Hz bandwidth
    - Olivia 32/1000: 32 tones, 1000 Hz bandwidth (most popular)
    - Olivia 64/2000: 64 tones, 2000 Hz bandwidth (fastest)

Example:
    Generate Olivia 32/1000 signal::

        from pydigi.modems.olivia import Olivia32_1000
        from pydigi.utils.audio import save_wav

        modem = Olivia32_1000()
        audio = modem.modulate("CQ CQ DE W1ABC")
        save_wav("olivia_test.wav", audio, 8000)

Reference:
    - fldigi/src/olivia/olivia.cxx
    - fldigi/src/include/jalocha/pj_mfsk.h

Attributes:
    OLIVIA_MODES (dict): Dictionary of standard Olivia mode configurations
"""

import numpy as np
from .base import Modem
from ..core.mfsk_encoder import MFSKEncoder
from ..core.mfsk_modulator import MFSKModulator


# Common Olivia configurations
# Format: (tones, bandwidth) - tones must be power of 2, bandwidth in Hz
OLIVIA_MODES = {
    "OLIVIA-4-125": (4, 125),
    "OLIVIA-4-250": (4, 250),
    "OLIVIA-4-500": (4, 500),
    "OLIVIA-4-1000": (4, 1000),
    "OLIVIA-4-2000": (4, 2000),
    "OLIVIA-8-125": (8, 125),
    "OLIVIA-8-250": (8, 250),
    "OLIVIA-8-500": (8, 500),
    "OLIVIA-8-1000": (8, 1000),
    "OLIVIA-8-2000": (8, 2000),
    "OLIVIA-16-500": (16, 500),
    "OLIVIA-16-1000": (16, 1000),
    "OLIVIA-16-2000": (16, 2000),
    "OLIVIA-32-1000": (32, 1000),  # Popular "Olivia 32/1000"
    "OLIVIA-32-2000": (32, 2000),
    "OLIVIA-64-2000": (64, 2000),
}


class Olivia(Modem):
    """
    Olivia MFSK modem with FEC.

    Olivia uses MFSK modulation with Fast Hadamard Transform for forward error
    correction. It's designed for weak signal HF operation and provides excellent
    performance in noisy conditions.

    Reference: fldigi/src/olivia/olivia.cxx
    """

    def __init__(
        self,
        tones: int = 32,
        bandwidth: int = 1000,
        sample_rate: int = 8000,
        frequency: float = 1500.0,
        tx_amplitude: float = 0.8,
        reverse: bool = False,
        send_start_tones: bool = True,
        send_stop_tones: bool = True,
    ):
        """
        Initialize Olivia modem.

        Args:
            tones: Number of tones (4, 8, 16, 32, 64, 128, 256)
            bandwidth: Bandwidth in Hz (125, 250, 500, 1000, 2000)
            sample_rate: Sample rate in Hz (default: 8000)
            frequency: Center frequency in Hz (default: 1500)
            tx_amplitude: Transmit amplitude 0.0-1.0 (default: 0.8)
            reverse: Reverse tone order (default: False)
            send_start_tones: Send preamble tones (default: True)
            send_stop_tones: Send postamble tones (default: True)

        Reference:
            fldigi/src/olivia/olivia.cxx lines 61-92 (tx_init)
            fldigi/src/include/jalocha/pj_mfsk.h lines 1693-1747 (Preset)
        """
        super().__init__(f"OLIVIA-{tones}-{bandwidth}", sample_rate, frequency)

        self.tones = tones
        self._bandwidth = bandwidth
        self.tx_amplitude = tx_amplitude
        self.reverse = reverse
        self.send_start_tones = send_start_tones
        self.send_stop_tones = send_stop_tones

        # Calculate bits per symbol
        self.bits_per_symbol = int(np.log2(tones))
        if 2**self.bits_per_symbol != tones:
            raise ValueError(f"Tones must be a power of 2, got {tones}")

        # Calculate symbol length
        # Reference: fldigi/src/include/jalocha/pj_mfsk.h line 1719-1720
        self.symbol_len = 1 << (self.bits_per_symbol + 7 - int(np.log2(bandwidth // 125)))

        # Calculate first carrier
        # Reference: fldigi/src/olivia/olivia.cxx lines 77-84
        fc_offset = bandwidth * (1.0 - 0.5 / tones) / 2.0
        if reverse:
            first_carrier_mult = (frequency + fc_offset) / 500.0
        else:
            first_carrier_mult = (frequency - fc_offset) / 500.0
        self.first_carrier = int((self.symbol_len / 16) * first_carrier_mult) + 1

        # Create encoder and modulator
        self.encoder = MFSKEncoder(bits_per_symbol=self.bits_per_symbol, mode="olivia")
        self.modulator = MFSKModulator(
            symbol_len=self.symbol_len,
            first_carrier=self.first_carrier,
            bits_per_symbol=self.bits_per_symbol,
            sample_rate=sample_rate,
            use_gray_code=True,
            reverse=reverse,
        )

        # Preamble configuration
        self.preamble_symbols = 32  # Number of preamble symbols

        # Tone generation for preamble/postamble
        # Reference: fldigi/src/olivia/olivia.cxx lines 105-132 (send_tones)
        # SCBLOCKSIZE = 512, TONE_DURATION = SCBLOCKSIZE * 16
        self.scblocksize = 512
        self.tone_duration = self.scblocksize * 16  # 8192 samples
        self._build_tone_shapes()

    def _build_tone_shapes(self):
        """
        Build amplitude shaping for preamble/postamble tones.

        Reference:
            fldigi/src/olivia/olivia.cxx lines 522-524
        """
        sr4 = self.tone_duration // 4
        # Initialize to 1.0 (flat)
        self.ampshape = np.ones(sr4, dtype=np.float64)

        # Shape the first SR4/8 samples (rise)
        # and last SR4/8 samples (fall)
        edge_len = sr4 // 8
        for i in range(edge_len):
            shape_val = 0.5 * (1.0 - np.cos(np.pi * i / edge_len))
            self.ampshape[i] = shape_val
            self.ampshape[sr4 - 1 - i] = shape_val

    def _generate_preamble_tones(self):
        """
        Generate preamble tones (alternating edge frequencies).

        Sends two tones at the edges of the bandwidth to help the receiver
        synchronize and estimate the signal parameters.

        Returns:
            numpy array of audio samples

        Reference:
            fldigi/src/olivia/olivia.cxx lines 105-132
        """
        tone_bw = self._bandwidth
        tone_midfreq = self.frequency

        # Calculate edge frequencies
        if self.reverse:
            freqa = tone_midfreq + (tone_bw / 2.0)
            freqb = tone_midfreq - (tone_bw / 2.0)
        else:
            freqa = tone_midfreq - (tone_bw / 2.0)
            freqb = tone_midfreq + (tone_bw / 2.0)

        # Build tone buffer
        tonebuff = np.zeros(self.tone_duration, dtype=np.float64)
        sr4 = self.tone_duration // 4

        # Generate shaped tones using NCO
        # Reference: fldigi/src/olivia/olivia.cxx lines 52-60 (nco function)
        preamble_phase = 0.0
        for i in range(sr4):
            tonebuff[i] = np.cos(preamble_phase) * self.ampshape[i]
            tonebuff[2 * sr4 + i] = tonebuff[i]
            preamble_phase += 2.0 * np.pi * freqa / self.sample_rate
            # Wrap phase at PI (not 2*PI like usual)
            if preamble_phase > np.pi:
                preamble_phase -= 2.0 * np.pi

        preamble_phase = 0.0
        for i in range(sr4):
            tonebuff[sr4 + i] = np.cos(preamble_phase) * self.ampshape[i]
            tonebuff[3 * sr4 + i] = tonebuff[sr4 + i]
            preamble_phase += 2.0 * np.pi * freqb / self.sample_rate
            # Wrap phase at PI (not 2*PI like usual)
            if preamble_phase > np.pi:
                preamble_phase -= 2.0 * np.pi

        return tonebuff

    def tx_init(self) -> None:
        """
        Initialize transmitter.

        Reference:
            fldigi/src/olivia/olivia.cxx lines 61-92
        """
        self.modulator.reset()
        self._tx_initialized = True

    def tx_process(self, text: str) -> np.ndarray:
        """
        Process text and generate modulated audio.

        Args:
            text: Text string to transmit

        Returns:
            numpy array of audio samples normalized to [-1.0, 1.0]

        Reference:
            fldigi/src/olivia/olivia.cxx lines 160-229 (tx_process)
            fldigi/src/include/jalocha/pj_mfsk.h lines 1813-1834 (Output)
        """
        output = []

        # Send preamble tones if enabled
        if self.send_start_tones:
            preamble = self._generate_preamble_tones()
            output.append(preamble)

            # Send initial NULL character to start encoder
            # Reference: fldigi/src/olivia/olivia.cxx line 180
            input_block = np.zeros(self.bits_per_symbol, dtype=np.uint8)
            symbols = self.encoder.encode_block(input_block)
            for symbol in symbols:
                self.modulator.send(symbol)
                output.append(self.modulator.output())

        # Process characters in groups of bits_per_symbol
        # Each FEC block encodes bits_per_symbol different characters
        # Reference: fldigi/src/include/jalocha/pj_mfsk.h lines 1819-1827
        text_bytes = [ord(c) for c in text]

        # Pad message to multiple of bits_per_symbol to avoid partial blocks
        # Pad with NULLs (0) like fldigi does when it runs out of data
        # Reference: fldigi/src/include/jalocha/pj_mfsk.h line 1826
        remainder = len(text_bytes) % self.bits_per_symbol
        if remainder != 0:
            padding_needed = self.bits_per_symbol - remainder
            text_bytes.extend([0] * padding_needed)

        # Process in chunks of bits_per_symbol
        for i in range(0, len(text_bytes), self.bits_per_symbol):
            # Get chunk of characters (exactly bits_per_symbol)
            chunk = text_bytes[i : i + self.bits_per_symbol]

            # Build input block
            input_block = np.array(chunk, dtype=np.uint8)

            # Encode block
            symbols = self.encoder.encode_block(input_block)

            # Modulate and output each symbol
            for symbol in symbols:
                self.modulator.send(symbol)
                output.append(self.modulator.output())

        # Send additional NULL blocks to flush the encoder
        # This ensures the decoder properly terminates
        # Reference: fldigi/src/include/jalocha/pj_mfsk.h lines 1825-1826
        for flush_block in range(2):
            input_block = np.zeros(self.bits_per_symbol, dtype=np.uint8)
            symbols = self.encoder.encode_block(input_block)
            for symbol in symbols:
                self.modulator.send(symbol)
                output.append(self.modulator.output())

        # Send postamble tones if enabled
        if self.send_stop_tones:
            # Send postamble tones
            # Reference: fldigi/src/olivia/olivia.cxx lines 216-220
            postamble = self._generate_preamble_tones()
            output.append(postamble)

            # Add silence block after postamble (SCBLOCKSIZE = 512 samples)
            # This ensures clean separation between transmissions
            # Reference: fldigi/src/olivia/olivia.cxx line 219
            silence = np.zeros(self.scblocksize, dtype=np.float64)
            output.append(silence)

        # Concatenate all output
        if output:
            signal = np.concatenate(output)
        else:
            signal = np.array([], dtype=np.float64)

        # Apply amplitude scaling
        signal = signal * self.tx_amplitude

        # Normalize to [-1.0, 1.0]
        max_val = np.max(np.abs(signal))
        if max_val > 1.0:
            signal = signal / max_val

        return signal.astype(np.float32)


# Convenience functions for popular Olivia modes
def Olivia4_125(**kwargs):
    """Olivia 4 tones, 125 Hz bandwidth."""
    return Olivia(tones=4, bandwidth=125, **kwargs)


def Olivia8_250(**kwargs):
    """Olivia 8 tones, 250 Hz bandwidth."""
    return Olivia(tones=8, bandwidth=250, **kwargs)


def Olivia8_500(**kwargs):
    """Olivia 8 tones, 500 Hz bandwidth."""
    return Olivia(tones=8, bandwidth=500, **kwargs)


def Olivia16_500(**kwargs):
    """Olivia 16 tones, 500 Hz bandwidth."""
    return Olivia(tones=16, bandwidth=500, **kwargs)


def Olivia16_1000(**kwargs):
    """Olivia 16 tones, 1000 Hz bandwidth."""
    return Olivia(tones=16, bandwidth=1000, **kwargs)


def Olivia32_1000(**kwargs):
    """Olivia 32 tones, 1000 Hz bandwidth (popular mode)."""
    return Olivia(tones=32, bandwidth=1000, **kwargs)
