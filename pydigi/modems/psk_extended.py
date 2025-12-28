"""
PSK Extended modes implementation.

Based on fldigi's PSK implementation (fldigi/src/psk/psk.cxx).
Includes PSK63F (PSK63 with FEC), multi-carrier PSK modes, and PSK-R modes.

PSK Extended Modes:
- PSK63F: PSK63 with Forward Error Correction (FEC)
- Multi-carrier PSK: Multiple parallel PSK carriers for diversity
  - 12X_PSK125: 12 carriers @ 125 baud each
  - 6X_PSK250: 6 carriers @ 250 baud each
  - 2X_PSK500: 2 carriers @ 500 baud each
  - 4X_PSK500: 4 carriers @ 500 baud each
  - 2X_PSK800: 2 carriers @ 800 baud each
  - 2X_PSK1000: 2 carriers @ 1000 baud each
- Multi-carrier PSK-R: Robust multi-carrier with FEC and interleaving
  - 2X_PSK125R through 32X_PSK63R (various configurations)
"""

import numpy as np
from typing import Optional
from scipy import signal
from ..core.oscillator import NCO
from ..core.encoder import ConvolutionalEncoder, create_mfsk_encoder
from ..core.interleave import Interleave, INTERLEAVE_FWD
from ..core.dsp_utils import (
    generate_raised_cosine_shape,
    apply_baseband_filter,
    modulate_to_carrier,
    normalize_audio,
)
from ..modems.base import Modem
from ..varicode.mfsk_varicode import encode_text_to_bits


class PSK63F(Modem):
    """
    PSK63F modem - PSK63 with Forward Error Correction.

    PSK63F uses BPSK modulation at 62.5 baud with:
    - Convolutional encoding (K=5, rate 1/2 FEC)
    - MFSK/ARQ varicode (not PSK varicode)
    - No interleaving (unlike other PSK-R modes)
    - Differential phase encoding

    Technical Details:
        - Modulation: BPSK (Binary Phase Shift Keying)
        - Baud rate: 62.5 baud (symbollen = 128 samples @ 8kHz)
        - FEC: Convolutional encoder K=5, POLY1=0x17, POLY2=0x19
        - Character encoding: MFSK/ARQ varicode
        - Pulse shaping: Raised cosine
        - Preamble: 64 symbols (dcdbits = 64)

    Attributes:
        sample_rate: Audio sample rate in Hz (default: 8000)
        frequency: Carrier frequency in Hz (default: 1000)

    Example:
        >>> psk63f = PSK63F()
        >>> audio = psk63f.modulate("TEST PSK63F", frequency=1500)
    """

    def __init__(
        self, sample_rate: float = 8000.0, frequency: float = 1000.0, tx_amplitude: float = 0.8
    ):
        """
        Initialize the PSK63F modem.

        Args:
            sample_rate: Audio sample rate in Hz (default: 8000)
            frequency: Carrier frequency in Hz (default: 1000)
            tx_amplitude: Transmit amplitude scaling (0.0 to 1.0, default: 0.8)
        """
        super().__init__(mode_name="PSK63F", sample_rate=sample_rate, frequency=frequency)

        self.baud = 62.5  # PSK63 baud rate
        self.tx_amplitude = max(0.0, min(1.0, tx_amplitude))
        self._nco: Optional[NCO] = None
        self._prev_phase = 0.0
        self._symbol_samples = 0
        self._tx_shape = None
        self._encoder: Optional[ConvolutionalEncoder] = None
        self._preamble_sent = False
        self._init_parameters()

    def _init_parameters(self):
        """Initialize internal parameters."""
        # Calculate samples per symbol
        self._symbol_samples = int(self.sample_rate / self.baud + 0.5)

        # Generate raised cosine pulse shape
        self._tx_shape = generate_raised_cosine_shape(self._symbol_samples)

        # Create convolutional encoder (K=5, rate 1/2)
        # Polynomials: POLY1=0x17, POLY2=0x19 (from fldigi psk.cxx line 67-68)
        self._encoder = ConvolutionalEncoder(k=5, poly1=0x17, poly2=0x19)

    def _generate_raised_cosine_shape(self, length: int) -> np.ndarray:
        """
        Generate raised cosine pulse shape for symbol transitions.

        Args:
            length: Number of samples in the shape (symbol length)

        Returns:
            Array of shape coefficients
        """
        # From fldigi: tx_shape[i] = 0.5 * cos(i * PI / symbollen) + 0.5
        n = np.arange(length, dtype=np.float32)
        shape = 0.5 * np.cos(np.pi * n / length) + 0.5
        return shape

    def tx_init(self):
        """Initialize the transmitter."""
        self._nco = NCO(self.sample_rate, self.frequency)
        self._prev_phase = 0.0
        self._preamble_sent = False
        if self._encoder:
            self._encoder.reset()

    def _tx_symbol(self, phase: float) -> tuple:
        """
        Transmit a single symbol with given phase.

        Args:
            phase: Phase offset (0 or pi radians)

        Returns:
            Tuple of (I samples, Q samples) for the symbol
        """
        i_samples = []
        q_samples = []

        # Generate symbol samples with smooth phase transition
        for i in range(self._symbol_samples):
            # Smooth transition using raised cosine shape
            # Current phase interpolates between previous and new phase
            current_phase = self._prev_phase + (phase - self._prev_phase) * (
                1.0 - self._tx_shape[i]
            )

            # Generate complex exponential
            i_sample = np.cos(current_phase)
            q_sample = np.sin(current_phase)

            i_samples.append(i_sample)
            q_samples.append(q_sample)

        # Update previous phase for next symbol
        self._prev_phase = phase

        return i_samples, q_samples

    def _tx_bit(self, bit: int) -> tuple:
        """
        Transmit a single bit using differential BPSK.

        Args:
            bit: Input bit (0 or 1)

        Returns:
            Tuple of (I samples, Q samples)
        """
        # Differential encoding: bit 1 = phase reversal, bit 0 = no change
        if bit:
            self._prev_phase += np.pi

        # Normalize phase to [-pi, pi]
        while self._prev_phase > np.pi:
            self._prev_phase -= 2 * np.pi
        while self._prev_phase < -np.pi:
            self._prev_phase += 2 * np.pi

        return self._tx_symbol(self._prev_phase)

    def _tx_preamble(self, num_symbols: int = 64) -> tuple:
        """
        Transmit preamble for receiver synchronization.

        PSK63F uses 64 symbols of preamble (dcdbits = 64 from fldigi).
        Preamble consists of alternating 1/0 bit pattern after FEC encoding.

        Args:
            num_symbols: Number of preamble symbols (default: 64)

        Returns:
            Tuple of (I samples, Q samples)
        """
        i_samples = []
        q_samples = []

        # Send alternating pattern through FEC encoder
        # FEC prep: alternating 1/0 sequence
        for i in range(num_symbols // 2):
            # Encode bit 1
            encoded_bits = self._encoder.encode(1)
            for bit in [encoded_bits & 1, (encoded_bits >> 1) & 1]:
                i_sym, q_sym = self._tx_bit(bit)
                i_samples.extend(i_sym)
                q_samples.extend(q_sym)

            # Encode bit 0
            encoded_bits = self._encoder.encode(0)
            for bit in [encoded_bits & 1, (encoded_bits >> 1) & 1]:
                i_sym, q_sym = self._tx_bit(bit)
                i_samples.extend(i_sym)
                q_samples.extend(q_sym)

        return i_samples, q_samples

    def _tx_char(self, char_code: int) -> tuple:
        """
        Transmit a single character using MFSK varicode and FEC.

        Args:
            char_code: ASCII character code

        Returns:
            Tuple of (I samples, Q samples)
        """
        i_samples = []
        q_samples = []

        # Get MFSK varicode bits for this character
        from ..varicode.mfsk_varicode import encode_char

        varicode = encode_char(char_code)

        # Encode each bit with FEC and transmit
        for bit_char in varicode:
            bit = int(bit_char)

            # Encode bit through convolutional encoder (1 bit in, 2 bits out)
            encoded_bits = self._encoder.encode(bit)

            # Transmit both output bits (low bit first)
            bit0 = encoded_bits & 1
            bit1 = (encoded_bits >> 1) & 1

            i_sym0, q_sym0 = self._tx_bit(bit0)
            i_samples.extend(i_sym0)
            q_samples.extend(q_sym0)

            i_sym1, q_sym1 = self._tx_bit(bit1)
            i_samples.extend(i_sym1)
            q_samples.extend(q_sym1)

        return i_samples, q_samples

    def _tx_postamble(self, num_symbols: int = 64) -> tuple:
        """
        Transmit postamble for clean ending.

        Args:
            num_symbols: Number of postamble symbols (default: 64)

        Returns:
            Tuple of (I samples, Q samples)
        """
        i_samples = []
        q_samples = []

        # Flush encoder and send zeros
        for i in range(num_symbols // 2):
            encoded_bits = self._encoder.encode(0)
            for bit in [encoded_bits & 1, (encoded_bits >> 1) & 1]:
                i_sym, q_sym = self._tx_bit(bit)
                i_samples.extend(i_sym)
                q_samples.extend(q_sym)

        return i_samples, q_samples

    def tx_process(
        self, text: str, preamble_symbols: int = 64, postamble_symbols: int = 64
    ) -> np.ndarray:
        """
        Process text for transmission.

        Args:
            text: Text to transmit
            preamble_symbols: Number of preamble symbols (default: 64)
            postamble_symbols: Number of postamble symbols (default: 64)

        Returns:
            Complete audio samples including preamble, text, and postamble
        """
        i_samples = []
        q_samples = []

        # Send preamble
        if not self._preamble_sent:
            i_preamble, q_preamble = self._tx_preamble(preamble_symbols)
            i_samples.extend(i_preamble)
            q_samples.extend(q_preamble)
            self._preamble_sent = True

        # Transmit each character
        for char in text:
            char_code = ord(char)
            i_char, q_char = self._tx_char(char_code)
            i_samples.extend(i_char)
            q_samples.extend(q_char)

        # Send postamble
        i_postamble, q_postamble = self._tx_postamble(postamble_symbols)
        i_samples.extend(i_postamble)
        q_samples.extend(q_postamble)

        # Convert to numpy arrays
        i_baseband = np.array(i_samples, dtype=np.float32)
        q_baseband = np.array(q_samples, dtype=np.float32)

        # Modulate onto carrier frequency
        output = self._modulate_to_carrier(i_baseband, q_baseband)

        # Normalize and apply amplitude scaling
        max_amp = np.max(np.abs(output))
        if max_amp > 0:
            output = output / max_amp * self.tx_amplitude

        return output

    def _modulate_to_carrier(self, i_samples: np.ndarray, q_samples: np.ndarray) -> np.ndarray:
        """
        Modulate I/Q baseband samples onto carrier frequency.

        Args:
            i_samples: In-phase baseband samples
            q_samples: Quadrature baseband samples

        Returns:
            Modulated audio samples
        """
        num_samples = len(i_samples)

        # Generate carrier
        t = np.arange(num_samples, dtype=np.float32) / self.sample_rate
        carrier_i = np.cos(2.0 * np.pi * self.frequency * t)
        carrier_q = np.sin(2.0 * np.pi * self.frequency * t)

        # Quadrature modulation
        output = i_samples * carrier_i + q_samples * carrier_q

        return output.astype(np.float32)

    def modulate(
        self,
        text: str,
        frequency: Optional[float] = None,
        sample_rate: Optional[float] = None,
        preamble_symbols: int = 64,
        postamble_symbols: int = 64,
    ) -> np.ndarray:
        """
        Modulate text into PSK63F audio signal.

        Args:
            text: Text string to modulate
            frequency: Carrier frequency in Hz (default: uses initialized value)
            sample_rate: Sample rate in Hz (default: uses initialized value)
            preamble_symbols: Number of preamble symbols (default: 64)
            postamble_symbols: Number of postamble symbols (default: 64)

        Returns:
            Audio samples as numpy array of float32 values (-1.0 to 1.0)

        Example:
            >>> psk63f = PSK63F()
            >>> audio = psk63f.modulate("HELLO WORLD", frequency=1500)
        """
        # Update parameters if provided
        if frequency is not None:
            self.frequency = frequency
        if sample_rate is not None:
            if sample_rate != self.sample_rate:
                self.sample_rate = sample_rate
                self._init_parameters()

        # Initialize transmitter
        self.tx_init()

        # Process text and generate audio
        audio = self.tx_process(text, preamble_symbols, postamble_symbols)

        return audio

    def __repr__(self) -> str:
        """String representation of the modem."""
        return f"PSK63F(freq={self.frequency}Hz, fs={self.sample_rate}Hz)"


class MultiCarrierPSK(Modem):
    """
    Multi-carrier PSK modem.

    Transmits the same data across multiple parallel PSK carriers for
    improved robustness against selective fading. Each carrier uses
    standard BPSK with differential encoding and PSK varicode.

    Multi-carrier modes:
        - 12X_PSK125: 12 carriers @ 125 baud each
        - 6X_PSK250: 6 carriers @ 250 baud each
        - 2X_PSK500: 2 carriers @ 500 baud each
        - 4X_PSK500: 4 carriers @ 500 baud each
        - 2X_PSK800: 2 carriers @ 800 baud each
        - 2X_PSK1000: 2 carriers @ 1000 baud each

    Technical Details:
        - Modulation: BPSK on each carrier
        - Carriers: Symmetrically spaced around center frequency
        - Carrier spacing: separation * symbol_bandwidth (default 1.4)
        - Character encoding: PSK varicode
        - Pulse shaping: Raised cosine

    Attributes:
        baud: Symbol rate per carrier in baud
        num_carriers: Number of parallel carriers
        separation: Carrier spacing factor (default: 1.4)

    Example:
        >>> # 2 carriers at 500 baud each
        >>> psk = MultiCarrierPSK(num_carriers=2, baud=500)
        >>> audio = psk.modulate("TEST 2X_PSK500", frequency=1500)
    """

    def __init__(
        self,
        num_carriers: int,
        baud: float,
        separation: float = 1.4,
        sample_rate: float = 8000.0,
        frequency: float = 1000.0,
        tx_amplitude: float = 0.8,
    ):
        """
        Initialize the multi-carrier PSK modem.

        Args:
            num_carriers: Number of parallel carriers (2, 4, 6, or 12)
            baud: Symbol rate per carrier in baud
            separation: Carrier spacing factor (default: 1.4, matches fldigi)
            sample_rate: Audio sample rate in Hz (default: 8000)
            frequency: Center carrier frequency in Hz (default: 1000)
            tx_amplitude: Transmit amplitude scaling (0.0 to 1.0, default: 0.8)
        """
        # Generate mode name
        mode_name = f"{num_carriers}X_PSK{int(baud)}"

        super().__init__(mode_name=mode_name, sample_rate=sample_rate, frequency=frequency)

        if num_carriers < 1 or num_carriers > 32:
            raise ValueError(f"num_carriers must be 1-32, got {num_carriers}")
        if baud <= 0 or baud > 1000:
            raise ValueError(f"baud must be > 0 and <= 1000, got {baud}")

        self.baud = baud
        self.num_carriers = num_carriers
        self.separation = separation
        self.tx_amplitude = max(0.0, min(1.0, tx_amplitude))

        self._nco: Optional[NCO] = None
        self._prev_symbols = []  # Track previous symbol (complex) for each carrier
        self._symbol_samples = 0
        self._tx_shape = None
        self._carrier_freqs = []  # Frequency for each carrier
        self._carrier_phase_acc = []  # Phase accumulator for each carrier
        self._preamble_sent = False
        self._tx_symbols_buffer = []  # Buffer for collecting symbols before transmission
        self._init_parameters()

    def _init_parameters(self):
        """Initialize internal parameters."""
        # Calculate samples per symbol
        self._symbol_samples = int(self.sample_rate / self.baud + 0.5)

        # Generate raised cosine pulse shape
        self._tx_shape = generate_raised_cosine_shape(self._symbol_samples)

        # Calculate carrier frequencies
        # sc_bw = sample_rate / symbollen (symbol bandwidth)
        sc_bw = self.sample_rate / self._symbol_samples

        # Carrier spacing: separation * symbol_bandwidth
        inter_carrier = self.separation * sc_bw

        # Calculate carrier frequencies symmetrically around center frequency
        # From fldigi: frequencies[0] = get_txfreq_woffset() + ((-1 * numcarriers) + 1) * inter_carrier / 2
        self._carrier_freqs = []
        first_freq = self.frequency + ((-1 * self.num_carriers) + 1) * inter_carrier / 2

        for i in range(self.num_carriers):
            freq = first_freq + i * inter_carrier
            self._carrier_freqs.append(freq)

        # Initialize previous symbol for each carrier (start at 1+0j)
        self._prev_symbols = [complex(1.0, 0.0)] * self.num_carriers
        self._carrier_phase_acc = [0.0] * self.num_carriers

        # Calculate default dcdbits (preamble/postamble length) based on baud rate
        # From fldigi psk.cxx mode initialization
        if self.baud <= 125:
            self._default_dcdbits = 128
        elif self.baud >= 1000:
            self._default_dcdbits = 1024
        else:
            self._default_dcdbits = 512

    def _generate_raised_cosine_shape(self, length: int) -> np.ndarray:
        """
        Generate raised cosine pulse shape for symbol transitions.

        Args:
            length: Number of samples in the shape (symbol length)

        Returns:
            Array of shape coefficients
        """
        n = np.arange(length, dtype=np.float32)
        shape = 0.5 * np.cos(np.pi * n / length) + 0.5
        return shape

    def tx_init(self):
        """Initialize the transmitter."""
        self._nco = NCO(self.sample_rate, self.frequency)
        self._prev_symbols = [complex(1.0, 0.0)] * self.num_carriers
        self._carrier_phase_acc = [0.0] * self.num_carriers
        self._tx_symbols_buffer = []
        self._preamble_sent = False

    def _tx_symbol(self, bit: int) -> Optional[np.ndarray]:
        """
        Buffer a symbol and transmit when we have enough for all carriers.

        This matches fldigi's tx_symbol() behavior where symbols are collected
        for each carrier before transmission.

        Args:
            bit: Input bit (0 or 1)

        Returns:
            Audio samples if ready to transmit, None if still buffering
        """
        # Calculate new symbol via differential encoding
        # NOTE: fldigi uses inverted encoding: bit 0 = phase reversal, bit 1 = no change
        carrier_index = len(self._tx_symbols_buffer)

        if not bit:  # bit 0: multiply by -1 (180° rotation)
            new_symbol = self._prev_symbols[carrier_index] * complex(-1.0, 0.0)
        else:  # bit 1: multiply by 1 (no rotation)
            new_symbol = self._prev_symbols[carrier_index] * complex(1.0, 0.0)

        self._tx_symbols_buffer.append(new_symbol)

        # If we have symbols for all carriers, transmit and reset buffer
        if len(self._tx_symbols_buffer) >= self.num_carriers:
            output = self._tx_carriers(self._tx_symbols_buffer)
            self._tx_symbols_buffer = []
            return output

        # Not ready to transmit yet
        return None

    def _tx_carriers(self, symbols: list) -> np.ndarray:
        """
        Transmit symbols on all carriers (matches fldigi's tx_carriers()).

        Args:
            symbols: List of complex symbols for each carrier

        Returns:
            Array of real output samples (sum of all carriers)
        """
        # Initialize output accumulator
        output = np.zeros(self._symbol_samples, dtype=np.float32)

        # Generate samples for each carrier and sum
        for car in range(self.num_carriers):
            symbol = symbols[car]
            prev_symbol = self._prev_symbols[car]
            freq = self._carrier_freqs[car]

            # Phase increment per sample for this carrier
            delta = 2.0 * np.pi * freq / self.sample_rate

            # Generate carrier samples with smooth phase transition
            for i in range(self._symbol_samples):
                # Smooth transition using raised cosine shape
                # Interpolate baseband I and Q between previous and current symbol
                shapeA = self._tx_shape[i]
                shapeB = 1.0 - shapeA

                # Interpolate complex symbols
                # From fldigi: ival = shapeA * prevsymbol.real() + shapeB * symbol.real()
                ival = shapeA * prev_symbol.real + shapeB * symbol.real
                qval = shapeA * prev_symbol.imag + shapeB * symbol.imag

                # Quadrature modulation: I*cos(carrier) + Q*sin(carrier)
                # From fldigi line 2274: outbuf[i] = (ival * cos(phaseacc) + qval * sin(phaseacc)) / numcarriers
                if car == 0:
                    output[i] = ival * np.cos(self._carrier_phase_acc[car]) + qval * np.sin(
                        self._carrier_phase_acc[car]
                    )
                else:
                    output[i] += ival * np.cos(self._carrier_phase_acc[car]) + qval * np.sin(
                        self._carrier_phase_acc[car]
                    )

                # Advance carrier phase
                self._carrier_phase_acc[car] += delta
                if self._carrier_phase_acc[car] > 2.0 * np.pi:
                    self._carrier_phase_acc[car] -= 2.0 * np.pi

            # Update previous symbol for this carrier
            self._prev_symbols[car] = symbol

        # Normalize by number of carriers to prevent clipping
        output /= self.num_carriers

        return output

    def _tx_preamble(self, num_symbols: int = 32) -> list:
        """
        Generate preamble bits.

        Args:
            num_symbols: Number of preamble symbols (total calls to tx_symbol)

        Returns:
            List of preamble bits
        """
        # Send repeated bit 0 (which causes phase reversals due to inverted encoding)
        # This creates the two-tone preamble pattern
        # num_symbols is the total number of calls to tx_symbol (not per carrier)
        # Each call buffers one symbol for one carrier
        # After numcarriers calls, all carriers transmit together
        return [0] * num_symbols

    def _tx_char_bits(self, char_code: int) -> list:
        """
        Get bits for a single character using PSK varicode.

        Args:
            char_code: ASCII character code

        Returns:
            List of bits for this character
        """
        # Get PSK varicode bits for this character
        from ..varicode.psk_varicode import encode_char

        varicode = encode_char(char_code)

        # Convert to bits and add two zero bits as character delimiter
        bits = [int(b) for b in varicode] + [0, 0]
        return bits

    def _tx_postamble(self, num_symbols: int = 32) -> list:
        """
        Generate postamble bits.

        Args:
            num_symbols: Number of postamble symbols (total calls to tx_symbol)

        Returns:
            List of postamble bits
        """
        # Send zeros for clean ending
        return [0] * num_symbols

    def tx_process(
        self, text: str, preamble_symbols: int = None, postamble_symbols: int = None
    ) -> np.ndarray:
        """
        Process text for transmission.

        Args:
            text: Text to transmit
            preamble_symbols: Number of preamble symbols (total calls to tx_symbol).
                            If None, uses default based on baud rate (128-1024).
            postamble_symbols: Number of postamble symbols (total calls to tx_symbol).
                            If None, uses default based on baud rate (128-1024).

        Returns:
            Complete audio samples including preamble, text, and postamble
        """
        # Use default dcdbits if not specified
        if preamble_symbols is None:
            preamble_symbols = self._default_dcdbits
        if postamble_symbols is None:
            postamble_symbols = self._default_dcdbits
        all_samples = []

        # Collect all bits to transmit
        all_bits = []

        # Add preamble
        if not self._preamble_sent:
            all_bits.extend(self._tx_preamble(preamble_symbols))
            self._preamble_sent = True

        # Add bits for each character
        for char in text:
            char_code = ord(char)
            all_bits.extend(self._tx_char_bits(char_code))

        # Add postamble
        all_bits.extend(self._tx_postamble(postamble_symbols))

        # Transmit bits using the buffering system
        for bit in all_bits:
            audio = self._tx_symbol(bit)
            if audio is not None:
                all_samples.extend(audio)

        # Flush any remaining buffered symbols
        # This shouldn't normally happen if all_bits is a multiple of num_carriers
        while len(self._tx_symbols_buffer) > 0:
            # Pad with zeros to fill the buffer
            while len(self._tx_symbols_buffer) < self.num_carriers:
                carrier_index = len(self._tx_symbols_buffer)
                # bit 1 = no change
                new_symbol = self._prev_symbols[carrier_index] * complex(1.0, 0.0)
                self._tx_symbols_buffer.append(new_symbol)

            audio = self._tx_carriers(self._tx_symbols_buffer)
            all_samples.extend(audio)
            self._tx_symbols_buffer = []

        # Convert to numpy array
        output = np.array(all_samples, dtype=np.float32)

        # Normalize and apply amplitude scaling
        max_amp = np.max(np.abs(output))
        if max_amp > 0:
            output = output / max_amp * self.tx_amplitude

        return output

    def modulate(
        self,
        text: str,
        frequency: Optional[float] = None,
        sample_rate: Optional[float] = None,
        preamble_symbols: int = None,
        postamble_symbols: int = None,
    ) -> np.ndarray:
        """
        Modulate text into multi-carrier PSK audio signal.

        Args:
            text: Text string to modulate
            frequency: Center carrier frequency in Hz (default: uses initialized value)
            sample_rate: Sample rate in Hz (default: uses initialized value)
            preamble_symbols: Number of preamble symbols (default: auto-calculated based on baud rate)
            postamble_symbols: Number of postamble symbols (default: auto-calculated based on baud rate)

        Returns:
            Audio samples as numpy array of float32 values (-1.0 to 1.0)

        Example:
            >>> psk = MultiCarrierPSK(num_carriers=2, baud=500)
            >>> audio = psk.modulate("HELLO WORLD", frequency=1500)
        """
        # Update parameters if provided
        if frequency is not None:
            self.frequency = frequency
        if sample_rate is not None:
            if sample_rate != self.sample_rate:
                self.sample_rate = sample_rate
                self._init_parameters()

        # Initialize transmitter
        self.tx_init()

        # Process text and generate audio
        audio = self.tx_process(text, preamble_symbols, postamble_symbols)

        return audio

    def __repr__(self) -> str:
        """String representation of the modem."""
        return (
            f"{self.mode_name}(freq={self.frequency}Hz, "
            f"carriers={self.num_carriers}, baud={self.baud}, "
            f"fs={self.sample_rate}Hz)"
        )


# Convenience functions for common multi-carrier PSK modes


def PSK_12X_PSK125(
    sample_rate: float = 8000.0, frequency: float = 1000.0, tx_amplitude: float = 0.8
) -> MultiCarrierPSK:
    """Create a 12X_PSK125 modem (12 carriers @ 125 baud each)."""
    return MultiCarrierPSK(
        num_carriers=12,
        baud=125,
        sample_rate=sample_rate,
        frequency=frequency,
        tx_amplitude=tx_amplitude,
    )


def PSK_6X_PSK250(
    sample_rate: float = 8000.0, frequency: float = 1000.0, tx_amplitude: float = 0.8
) -> MultiCarrierPSK:
    """Create a 6X_PSK250 modem (6 carriers @ 250 baud each)."""
    return MultiCarrierPSK(
        num_carriers=6,
        baud=250,
        sample_rate=sample_rate,
        frequency=frequency,
        tx_amplitude=tx_amplitude,
    )


def PSK_2X_PSK500(
    sample_rate: float = 8000.0, frequency: float = 1000.0, tx_amplitude: float = 0.8
) -> MultiCarrierPSK:
    """Create a 2X_PSK500 modem (2 carriers @ 500 baud each)."""
    return MultiCarrierPSK(
        num_carriers=2,
        baud=500,
        sample_rate=sample_rate,
        frequency=frequency,
        tx_amplitude=tx_amplitude,
    )


def PSK_4X_PSK500(
    sample_rate: float = 8000.0, frequency: float = 1000.0, tx_amplitude: float = 0.8
) -> MultiCarrierPSK:
    """Create a 4X_PSK500 modem (4 carriers @ 500 baud each)."""
    return MultiCarrierPSK(
        num_carriers=4,
        baud=500,
        sample_rate=sample_rate,
        frequency=frequency,
        tx_amplitude=tx_amplitude,
    )


def PSK_2X_PSK800(
    sample_rate: float = 8000.0, frequency: float = 1000.0, tx_amplitude: float = 0.8
) -> MultiCarrierPSK:
    """Create a 2X_PSK800 modem (2 carriers @ 800 baud each)."""
    return MultiCarrierPSK(
        num_carriers=2,
        baud=800,
        sample_rate=sample_rate,
        frequency=frequency,
        tx_amplitude=tx_amplitude,
    )


def PSK_2X_PSK1000(
    sample_rate: float = 8000.0, frequency: float = 1000.0, tx_amplitude: float = 0.8
) -> MultiCarrierPSK:
    """Create a 2X_PSK1000 modem (2 carriers @ 1000 baud each)."""
    return MultiCarrierPSK(
        num_carriers=2,
        baud=1000,
        sample_rate=sample_rate,
        frequency=frequency,
        tx_amplitude=tx_amplitude,
    )


class MultiCarrierPSKR(Modem):
    """
    Multi-carrier PSK-R (Robust) modem.

    PSK-R adds robustness to multi-carrier PSK through:
    - Convolutional FEC (K=7, POLY1=0x6d, POLY2=0x4f)
    - Bit interleaving for burst error protection
    - MFSK varicode (no character delimiters)
    - Dual Viterbi decoding (RX only, not implemented for TX)

    Based on fldigi's PSK-R implementation (fldigi/src/psk/psk.cxx).

    Multi-carrier PSK-R modes:
        - 4X_PSK63R, 5X_PSK63R, 10X_PSK63R, 20X_PSK63R, 32X_PSK63R
        - 4X_PSK125R, 5X_PSK125R, 10X_PSK125R, 12X_PSK125R, 16X_PSK125R
        - 2X_PSK250R, 3X_PSK250R, 5X_PSK250R, 6X_PSK250R, 7X_PSK250R
        - 2X_PSK500R, 3X_PSK500R, 4X_PSK500R
        - 2X_PSK800R
        - 2X_PSK1000R

    Technical Details:
        - Modulation: BPSK on each carrier with differential encoding
        - FEC: Convolutional encoder K=7 (rate 1/2)
        - Interleaving: 2x2xN (N varies by baud rate)
        - Character encoding: MFSK/ARQ varicode
        - Pulse shaping: Raised cosine

    Attributes:
        baud: Symbol rate per carrier in baud
        num_carriers: Number of parallel carriers
        interleave_depth: Interleaver depth (2x2xN)
        separation: Carrier spacing factor (default: 1.4)

    Example:
        >>> # 12 carriers at 125 baud with PSK-R
        >>> psk = MultiCarrierPSKR(num_carriers=12, baud=125, interleave_depth=160)
        >>> audio = psk.modulate("TEST 12X_PSK125R", frequency=1500)
    """

    def __init__(
        self,
        num_carriers: int,
        baud: float,
        interleave_depth: int,
        separation: float = 1.4,
        sample_rate: float = 8000.0,
        frequency: float = 1000.0,
        tx_amplitude: float = 0.8,
    ):
        """
        Initialize the multi-carrier PSK-R modem.

        Args:
            num_carriers: Number of parallel carriers (2-32)
            baud: Symbol rate per carrier in baud
            interleave_depth: Interleaver depth N for 2x2xN interleaver
            separation: Carrier spacing factor (default: 1.4)
            sample_rate: Audio sample rate in Hz (default: 8000)
            frequency: Center carrier frequency in Hz (default: 1000)
            tx_amplitude: Transmit amplitude scaling (0.0 to 1.0, default: 0.8)
        """
        # Generate mode name
        mode_name = f"{num_carriers}X_PSK{int(baud)}R"

        super().__init__(mode_name=mode_name, sample_rate=sample_rate, frequency=frequency)

        if num_carriers < 1 or num_carriers > 32:
            raise ValueError(f"num_carriers must be 1-32, got {num_carriers}")
        if baud <= 0 or baud > 1000:
            raise ValueError(f"baud must be > 0 and <= 1000, got {baud}")

        self.baud = baud
        self.num_carriers = num_carriers
        self.interleave_depth = interleave_depth
        self.separation = separation
        self.tx_amplitude = max(0.0, min(1.0, tx_amplitude))

        self._nco: Optional[NCO] = None
        self._prev_symbols = []  # Track previous symbol (complex) for each carrier
        self._symbol_samples = 0
        self._tx_shape = None
        self._carrier_freqs = []  # Frequency for each carrier
        self._carrier_phase_acc = []  # Phase accumulator for each carrier
        self._encoder: Optional[ConvolutionalEncoder] = None
        self._interleaver: Optional[Interleave] = None
        self._preamble_sent = False

        # Calculate preamble symbols based on baud rate
        # From fldigi: dcdbits varies by mode (128-1024 for multi-carrier PSK-R)
        if baud <= 63:
            self._dcdbits = 128
        elif baud <= 125:
            self._dcdbits = 512
        else:
            self._dcdbits = 1024

        self._init_parameters()

    def _init_parameters(self):
        """Initialize internal parameters."""
        # Calculate samples per symbol
        self._symbol_samples = int(self.sample_rate / self.baud + 0.5)

        # Generate raised cosine pulse shape
        self._tx_shape = generate_raised_cosine_shape(self._symbol_samples)

        # Create PSK-R convolutional encoder (K=7)
        # From fldigi psk.cxx lines 72-74: PSKR_K=7, PSKR_POLY1=0x6d, PSKR_POLY2=0x4f
        self._encoder = create_mfsk_encoder()  # K=7, POLY1=0x6d, POLY2=0x4f

        # Create interleaver (2x2xdepth)
        # Size = 2 (bits per symbol for FEC output)
        # Depth = interleave_depth parameter
        self._interleaver = Interleave(
            size=2, depth=self.interleave_depth, direction=INTERLEAVE_FWD
        )

        # Calculate carrier frequencies
        sc_bw = self.sample_rate / self._symbol_samples
        inter_carrier = self.separation * sc_bw

        # Calculate carrier frequencies symmetrically around center frequency
        self._carrier_freqs = []
        first_freq = self.frequency + ((-1 * self.num_carriers) + 1) * inter_carrier / 2

        for i in range(self.num_carriers):
            freq = first_freq + i * inter_carrier
            self._carrier_freqs.append(freq)

        # Initialize previous symbol for each carrier (start at 1+0j)
        self._prev_symbols = [complex(1.0, 0.0)] * self.num_carriers
        self._carrier_phase_acc = [0.0] * self.num_carriers

    def _generate_raised_cosine_shape(self, length: int) -> np.ndarray:
        """
        Generate raised cosine pulse shape for symbol transitions.

        Args:
            length: Number of samples in the shape (symbol length)

        Returns:
            Array of shape coefficients
        """
        n = np.arange(length, dtype=np.float32)
        shape = 0.5 * np.cos(np.pi * n / length) + 0.5
        return shape

    def tx_init(self):
        """Initialize the transmitter."""
        self._nco = NCO(self.sample_rate, self.frequency)
        self._prev_symbols = [complex(1.0, 0.0)] * self.num_carriers
        self._carrier_phase_acc = [0.0] * self.num_carriers
        self._preamble_sent = False
        if self._encoder:
            self._encoder.reset()
        if self._interleaver:
            self._interleaver.flush()

    def _tx_symbol_all_carriers(self, symbols: list) -> np.ndarray:
        """
        Transmit symbols on all carriers.

        Args:
            symbols: List of complex symbols for each carrier

        Returns:
            Array of real output samples (sum of all carriers)
        """
        # Initialize output accumulator
        output = np.zeros(self._symbol_samples, dtype=np.float32)

        # Generate samples for each carrier and sum
        for car in range(self.num_carriers):
            symbol = symbols[car]
            prev_symbol = self._prev_symbols[car]
            freq = self._carrier_freqs[car]

            # Phase increment per sample for this carrier
            delta = 2.0 * np.pi * freq / self.sample_rate

            # Generate carrier samples with smooth phase transition
            for i in range(self._symbol_samples):
                # Smooth transition using raised cosine shape
                # Interpolate baseband I and Q between previous and current symbol
                shapeA = self._tx_shape[i]
                shapeB = 1.0 - shapeA

                # Interpolate complex symbols
                # From fldigi: ival = shapeA * prevsymbol.real() + shapeB * symbol.real()
                ival = shapeA * prev_symbol.real + shapeB * symbol.real
                qval = shapeA * prev_symbol.imag + shapeB * symbol.imag

                # Quadrature modulation: I*cos(carrier) + Q*sin(carrier)
                if car == 0:
                    output[i] = ival * np.cos(self._carrier_phase_acc[car]) + qval * np.sin(
                        self._carrier_phase_acc[car]
                    )
                else:
                    output[i] += ival * np.cos(self._carrier_phase_acc[car]) + qval * np.sin(
                        self._carrier_phase_acc[car]
                    )

                # Advance carrier phase
                self._carrier_phase_acc[car] += delta
                if self._carrier_phase_acc[car] > 2.0 * np.pi:
                    self._carrier_phase_acc[car] -= 2.0 * np.pi

            # Update previous symbol for this carrier
            self._prev_symbols[car] = symbol

        # Normalize by number of carriers to prevent clipping
        output /= self.num_carriers

        return output

    def _tx_bit_all_carriers(self, bit: int) -> np.ndarray:
        """
        Transmit a single bit on all carriers using differential BPSK.

        Args:
            bit: Input bit (0 or 1)

        Returns:
            Array of real output samples
        """
        # Calculate new symbol for each carrier via complex multiplication
        # From fldigi: symbol = prevsymbol * sym_vec_pos[sym]
        # For BPSK: bit 0 -> sym 0 -> sym_vec_pos[0] = (-1, 0)
        #           bit 1 -> sym 8 -> sym_vec_pos[8] = (1, 0)
        # NOTE: fldigi uses inverted encoding: bit 0 = phase reversal, bit 1 = no change
        symbols = []
        for car in range(self.num_carriers):
            if not bit:  # bit 0: multiply by -1 (180° rotation)
                new_symbol = self._prev_symbols[car] * complex(-1.0, 0.0)
            else:  # bit 1: multiply by 1 (no rotation)
                new_symbol = self._prev_symbols[car] * complex(1.0, 0.0)
            symbols.append(new_symbol)

        return self._tx_symbol_all_carriers(symbols)

    def _tx_preamble(self) -> np.ndarray:
        """
        Transmit preamble for receiver synchronization.

        PSK-R preamble: alternating 1/0 bit pattern through FEC encoder,
        which creates the DCD-ON pattern (0x0A0A0A0A or similar).

        Returns:
            Array of real output samples
        """
        samples = []

        # Clear interleaver for preamble
        if self._interleaver:
            self._interleaver.flush()

        # Send alternating pattern through FEC encoder
        # From fldigi: preamble for PSK-R is alternating 1/0 through FEC
        num_preamble_bits = self._dcdbits // 2  # Divide by 2 since FEC doubles

        for i in range(num_preamble_bits):
            # Alternating 1/0 pattern
            bit = i % 2

            # Encode bit through convolutional encoder (1 bit in, 2 bits out)
            encoded_bits = self._encoder.encode(bit)

            # Create 2-symbol array for interleaver
            symbols = np.array([encoded_bits & 1, (encoded_bits >> 1) & 1], dtype=np.uint8)

            # Pass through interleaver
            self._interleaver.symbols(symbols)

            # Transmit both interleaved bits on all carriers
            for sym_bit in symbols:
                sym_samples = self._tx_bit_all_carriers(sym_bit)
                samples.extend(sym_samples)

        return np.array(samples, dtype=np.float32)

    def _tx_char(self, char_code: int) -> np.ndarray:
        """
        Transmit a single character using MFSK varicode with FEC and interleaving.

        Args:
            char_code: ASCII character code

        Returns:
            Array of real output samples
        """
        samples = []

        # Get MFSK varicode bits for this character
        from ..varicode.mfsk_varicode import encode_char

        varicode = encode_char(char_code)

        # Encode each bit with FEC, interleave, and transmit
        for bit_char in varicode:
            bit = int(bit_char)

            # Encode bit through convolutional encoder (1 bit in, 2 bits out)
            encoded_bits = self._encoder.encode(bit)

            # Create 2-symbol array for interleaver
            symbols = np.array([encoded_bits & 1, (encoded_bits >> 1) & 1], dtype=np.uint8)

            # Pass through interleaver
            self._interleaver.symbols(symbols)

            # Transmit both interleaved bits on all carriers
            for sym_bit in symbols:
                sym_samples = self._tx_bit_all_carriers(sym_bit)
                samples.extend(sym_samples)

        return np.array(samples, dtype=np.float32)

    def _tx_postamble(self) -> np.ndarray:
        """
        Transmit postamble for clean ending.

        PSK-R postamble: flush encoder with zeros, then additional padding.

        Returns:
            Array of real output samples
        """
        samples = []

        # Flush encoder - send enough zeros to clear the encoder state
        # From fldigi: flushlength varies, but for PSK-R we need to flush the encoder
        flush_bits = self._encoder.k - 1  # Standard flush length

        for _ in range(flush_bits + self._dcdbits // 4):
            encoded_bits = self._encoder.encode(0)

            # Create 2-symbol array for interleaver
            symbols = np.array([encoded_bits & 1, (encoded_bits >> 1) & 1], dtype=np.uint8)

            # Pass through interleaver
            self._interleaver.symbols(symbols)

            # Transmit both interleaved bits
            for sym_bit in symbols:
                sym_samples = self._tx_bit_all_carriers(sym_bit)
                samples.extend(sym_samples)

        return np.array(samples, dtype=np.float32)

    def tx_process(self, text: str) -> np.ndarray:
        """
        Process text for transmission.

        Args:
            text: Text to transmit

        Returns:
            Complete audio samples including preamble, text, and postamble
        """
        samples = []

        # Send preamble
        if not self._preamble_sent:
            preamble = self._tx_preamble()
            samples.extend(preamble)
            self._preamble_sent = True

        # Transmit each character
        for char in text:
            char_code = ord(char)
            char_samples = self._tx_char(char_code)
            samples.extend(char_samples)

        # Send postamble
        postamble = self._tx_postamble()
        samples.extend(postamble)

        # Convert to numpy array
        output = np.array(samples, dtype=np.float32)

        # Normalize and apply amplitude scaling
        max_amp = np.max(np.abs(output))
        if max_amp > 0:
            output = output / max_amp * self.tx_amplitude

        return output

    def modulate(
        self, text: str, frequency: Optional[float] = None, sample_rate: Optional[float] = None
    ) -> np.ndarray:
        """
        Modulate text into multi-carrier PSK-R audio signal.

        Args:
            text: Text string to modulate
            frequency: Center carrier frequency in Hz (default: uses initialized value)
            sample_rate: Sample rate in Hz (default: uses initialized value)

        Returns:
            Audio samples as numpy array of float32 values (-1.0 to 1.0)

        Example:
            >>> psk = MultiCarrierPSKR(num_carriers=12, baud=125, interleave_depth=160)
            >>> audio = psk.modulate("HELLO WORLD", frequency=1500)
        """
        # Update parameters if provided
        if frequency is not None:
            self.frequency = frequency
        if sample_rate is not None:
            if sample_rate != self.sample_rate:
                self.sample_rate = sample_rate
                self._init_parameters()

        # Initialize transmitter
        self.tx_init()

        # Process text and generate audio
        audio = self.tx_process(text)

        return audio

    def __repr__(self) -> str:
        """String representation of the modem."""
        return (
            f"{self.mode_name}(freq={self.frequency}Hz, "
            f"carriers={self.num_carriers}, baud={self.baud}, "
            f"interleave_depth={self.interleave_depth}, "
            f"fs={self.sample_rate}Hz)"
        )


# Convenience functions for PSK-R modes
# Interleave depths from fldigi psk.cxx


def PSKR_4X_PSK63R(
    sample_rate: float = 8000.0, frequency: float = 1000.0, tx_amplitude: float = 0.8
) -> MultiCarrierPSKR:
    """Create a 4X_PSK63R modem (4 carriers @ 63 baud with PSK-R)."""
    return MultiCarrierPSKR(
        num_carriers=4,
        baud=62.5,
        interleave_depth=80,
        sample_rate=sample_rate,
        frequency=frequency,
        tx_amplitude=tx_amplitude,
    )


def PSKR_5X_PSK63R(
    sample_rate: float = 8000.0, frequency: float = 1000.0, tx_amplitude: float = 0.8
) -> MultiCarrierPSKR:
    """Create a 5X_PSK63R modem (5 carriers @ 63 baud with PSK-R)."""
    return MultiCarrierPSKR(
        num_carriers=5,
        baud=62.5,
        interleave_depth=260,
        sample_rate=sample_rate,
        frequency=frequency,
        tx_amplitude=tx_amplitude,
    )


def PSKR_10X_PSK63R(
    sample_rate: float = 8000.0, frequency: float = 1000.0, tx_amplitude: float = 0.8
) -> MultiCarrierPSKR:
    """Create a 10X_PSK63R modem (10 carriers @ 63 baud with PSK-R)."""
    return MultiCarrierPSKR(
        num_carriers=10,
        baud=62.5,
        interleave_depth=160,
        sample_rate=sample_rate,
        frequency=frequency,
        tx_amplitude=tx_amplitude,
    )


def PSKR_20X_PSK63R(
    sample_rate: float = 8000.0, frequency: float = 1000.0, tx_amplitude: float = 0.8
) -> MultiCarrierPSKR:
    """Create a 20X_PSK63R modem (20 carriers @ 63 baud with PSK-R)."""
    return MultiCarrierPSKR(
        num_carriers=20,
        baud=62.5,
        interleave_depth=160,
        sample_rate=sample_rate,
        frequency=frequency,
        tx_amplitude=tx_amplitude,
    )


def PSKR_32X_PSK63R(
    sample_rate: float = 8000.0, frequency: float = 1000.0, tx_amplitude: float = 0.8
) -> MultiCarrierPSKR:
    """Create a 32X_PSK63R modem (32 carriers @ 63 baud with PSK-R)."""
    return MultiCarrierPSKR(
        num_carriers=32,
        baud=62.5,
        interleave_depth=160,
        sample_rate=sample_rate,
        frequency=frequency,
        tx_amplitude=tx_amplitude,
    )


def PSKR_4X_PSK125R(
    sample_rate: float = 8000.0, frequency: float = 1000.0, tx_amplitude: float = 0.8
) -> MultiCarrierPSKR:
    """Create a 4X_PSK125R modem (4 carriers @ 125 baud with PSK-R)."""
    return MultiCarrierPSKR(
        num_carriers=4,
        baud=125,
        interleave_depth=80,
        sample_rate=sample_rate,
        frequency=frequency,
        tx_amplitude=tx_amplitude,
    )


def PSKR_5X_PSK125R(
    sample_rate: float = 8000.0, frequency: float = 1000.0, tx_amplitude: float = 0.8
) -> MultiCarrierPSKR:
    """Create a 5X_PSK125R modem (5 carriers @ 125 baud with PSK-R)."""
    return MultiCarrierPSKR(
        num_carriers=5,
        baud=125,
        interleave_depth=160,
        sample_rate=sample_rate,
        frequency=frequency,
        tx_amplitude=tx_amplitude,
    )


def PSKR_10X_PSK125R(
    sample_rate: float = 8000.0, frequency: float = 1000.0, tx_amplitude: float = 0.8
) -> MultiCarrierPSKR:
    """Create a 10X_PSK125R modem (10 carriers @ 125 baud with PSK-R)."""
    return MultiCarrierPSKR(
        num_carriers=10,
        baud=125,
        interleave_depth=160,
        sample_rate=sample_rate,
        frequency=frequency,
        tx_amplitude=tx_amplitude,
    )


def PSKR_12X_PSK125R(
    sample_rate: float = 8000.0, frequency: float = 1000.0, tx_amplitude: float = 0.8
) -> MultiCarrierPSKR:
    """Create a 12X_PSK125R modem (12 carriers @ 125 baud with PSK-R)."""
    return MultiCarrierPSKR(
        num_carriers=12,
        baud=125,
        interleave_depth=160,
        sample_rate=sample_rate,
        frequency=frequency,
        tx_amplitude=tx_amplitude,
    )


def PSKR_16X_PSK125R(
    sample_rate: float = 8000.0, frequency: float = 1000.0, tx_amplitude: float = 0.8
) -> MultiCarrierPSKR:
    """Create a 16X_PSK125R modem (16 carriers @ 125 baud with PSK-R)."""
    return MultiCarrierPSKR(
        num_carriers=16,
        baud=125,
        interleave_depth=160,
        sample_rate=sample_rate,
        frequency=frequency,
        tx_amplitude=tx_amplitude,
    )


def PSKR_2X_PSK250R(
    sample_rate: float = 8000.0, frequency: float = 1000.0, tx_amplitude: float = 0.8
) -> MultiCarrierPSKR:
    """Create a 2X_PSK250R modem (2 carriers @ 250 baud with PSK-R)."""
    return MultiCarrierPSKR(
        num_carriers=2,
        baud=250,
        interleave_depth=160,
        sample_rate=sample_rate,
        frequency=frequency,
        tx_amplitude=tx_amplitude,
    )


def PSKR_3X_PSK250R(
    sample_rate: float = 8000.0, frequency: float = 1000.0, tx_amplitude: float = 0.8
) -> MultiCarrierPSKR:
    """Create a 3X_PSK250R modem (3 carriers @ 250 baud with PSK-R)."""
    return MultiCarrierPSKR(
        num_carriers=3,
        baud=250,
        interleave_depth=160,
        sample_rate=sample_rate,
        frequency=frequency,
        tx_amplitude=tx_amplitude,
    )


def PSKR_5X_PSK250R(
    sample_rate: float = 8000.0, frequency: float = 1000.0, tx_amplitude: float = 0.8
) -> MultiCarrierPSKR:
    """Create a 5X_PSK250R modem (5 carriers @ 250 baud with PSK-R)."""
    return MultiCarrierPSKR(
        num_carriers=5,
        baud=250,
        interleave_depth=160,
        sample_rate=sample_rate,
        frequency=frequency,
        tx_amplitude=tx_amplitude,
    )


def PSKR_6X_PSK250R(
    sample_rate: float = 8000.0, frequency: float = 1000.0, tx_amplitude: float = 0.8
) -> MultiCarrierPSKR:
    """Create a 6X_PSK250R modem (6 carriers @ 250 baud with PSK-R)."""
    return MultiCarrierPSKR(
        num_carriers=6,
        baud=250,
        interleave_depth=160,
        sample_rate=sample_rate,
        frequency=frequency,
        tx_amplitude=tx_amplitude,
    )


def PSKR_7X_PSK250R(
    sample_rate: float = 8000.0, frequency: float = 1000.0, tx_amplitude: float = 0.8
) -> MultiCarrierPSKR:
    """Create a 7X_PSK250R modem (7 carriers @ 250 baud with PSK-R)."""
    return MultiCarrierPSKR(
        num_carriers=7,
        baud=250,
        interleave_depth=160,
        sample_rate=sample_rate,
        frequency=frequency,
        tx_amplitude=tx_amplitude,
    )


def PSKR_2X_PSK500R(
    sample_rate: float = 8000.0, frequency: float = 1000.0, tx_amplitude: float = 0.8
) -> MultiCarrierPSKR:
    """Create a 2X_PSK500R modem (2 carriers @ 500 baud with PSK-R)."""
    return MultiCarrierPSKR(
        num_carriers=2,
        baud=500,
        interleave_depth=160,
        sample_rate=sample_rate,
        frequency=frequency,
        tx_amplitude=tx_amplitude,
    )


def PSKR_3X_PSK500R(
    sample_rate: float = 8000.0, frequency: float = 1000.0, tx_amplitude: float = 0.8
) -> MultiCarrierPSKR:
    """Create a 3X_PSK500R modem (3 carriers @ 500 baud with PSK-R)."""
    return MultiCarrierPSKR(
        num_carriers=3,
        baud=500,
        interleave_depth=160,
        sample_rate=sample_rate,
        frequency=frequency,
        tx_amplitude=tx_amplitude,
    )


def PSKR_4X_PSK500R(
    sample_rate: float = 8000.0, frequency: float = 1000.0, tx_amplitude: float = 0.8
) -> MultiCarrierPSKR:
    """Create a 4X_PSK500R modem (4 carriers @ 500 baud with PSK-R)."""
    return MultiCarrierPSKR(
        num_carriers=4,
        baud=500,
        interleave_depth=160,
        sample_rate=sample_rate,
        frequency=frequency,
        tx_amplitude=tx_amplitude,
    )


def PSKR_2X_PSK800R(
    sample_rate: float = 8000.0, frequency: float = 1000.0, tx_amplitude: float = 0.8
) -> MultiCarrierPSKR:
    """Create a 2X_PSK800R modem (2 carriers @ 800 baud with PSK-R)."""
    return MultiCarrierPSKR(
        num_carriers=2,
        baud=800,
        interleave_depth=160,
        sample_rate=sample_rate,
        frequency=frequency,
        tx_amplitude=tx_amplitude,
    )


def PSKR_2X_PSK1000R(
    sample_rate: float = 8000.0, frequency: float = 1000.0, tx_amplitude: float = 0.8
) -> MultiCarrierPSKR:
    """Create a 2X_PSK1000R modem (2 carriers @ 1000 baud with PSK-R)."""
    return MultiCarrierPSKR(
        num_carriers=2,
        baud=1000,
        interleave_depth=160,
        sample_rate=sample_rate,
        frequency=frequency,
        tx_amplitude=tx_amplitude,
    )
