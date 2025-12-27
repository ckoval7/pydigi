"""
SCAMP (Secure Communication via Amplitude Modulated Pulses) modem implementation.

Based on fldigi's SCAMP implementation (fldigi/src/scamp/scamp.cxx).
Supports 6 mode variants with FSK and OOK modulation at various speeds.

SCAMP uses Golay(24,12) error correction coding combined with 6-bit character
encoding to provide robust, narrow-band communication.
"""

import numpy as np
from typing import Optional
from scipy import signal
from ..core.oscillator import NCO
from ..core.dsp_utils import normalize_audio
from ..modems.base import Modem
from ..varicode.scamp_varicode import text_to_codewords
from ..core.golay import (
    golay_encode,
    add_reversal_bits,
    SCAMP_SOLID_CODEWORD,
    SCAMP_DOTTED_CODEWORD,
    SCAMP_INIT_CODEWORD,
    SCAMP_SYNC_CODEWORD,
    SCAMP_RES_CODE_END_TRANSMISSION_FRAME,
    golay_encode,
    SCAMP_RES_CODE_END_TRANSMISSION
)


class SCAMP(Modem):
    """
    SCAMP (Secure Communication via Amplitude Modulated Pulses) modem.

    SCAMP is a robust, narrow-band digital mode that uses Golay(24,12) FEC
    (Forward Error Correction) to provide reliable communication even under
    poor conditions. It can correct up to 3 bit errors per 24-bit codeword.

    Modulation Types:
        - FSK (Frequency Shift Keying): Binary FSK with mark/space frequencies
        - OOK (On-Off Keying): Amplitude modulation (on = 1, off = 0)

    Mode Variants (6 total):
        FSK Modes:
            - SCAMPFSK: Standard FSK (66.67 Hz shift, 133 Hz BW, 33.33 baud)
            - SCFSKFST: Fast FSK (166.67 Hz shift, 333 Hz BW, 83.33 baud)
            - SCFSKSLW: Slow FSK (41.67 Hz shift, 69.44 Hz BW, 13.89 baud)
            - SCFSKVSL: Very Slow FSK (20.83 Hz shift, 34.72 Hz BW, 6.94 baud)

        OOK Modes:
            - SCAMPOOK: Standard OOK (62.5 Hz BW, 31.25 baud)
            - SCOOKSLW: Slow OOK (27.78 Hz BW, 13.89 baud)

    Technical Details:
        - Sample Rate: Fixed at 8000 Hz (matching fldigi)
        - FEC: Golay(24,12) - corrects up to 3 bit errors
        - Frame Structure: 30 bits (24 Golay bits + 6 reversal bits)
        - Character Encoding: 6-bit (60 character set) or 8-bit raw
        - Reversal Bits: Embedded at positions 1,5,9,13,17,21 for sync

    Attributes:
        mode: SCAMP mode variant name
        sample_rate: Audio sample rate (fixed at 8000 Hz)
        frequency: Carrier frequency in Hz
        samples_per_bit: Number of audio samples per data bit
        is_fsk: True for FSK modes, False for OOK modes
        shift_hz: Frequency shift for FSK modes (0 for OOK)

    Example:
        >>> # Standard FSK mode
        >>> modem = SCAMP(mode='SCAMPFSK')
        >>> audio = modem.modulate("CQ CQ DE W1ABC")
        >>>
        >>> # Fast FSK mode
        >>> modem = SCAMP(mode='SCFSKFST', frequency=1500)
        >>> audio = modem.modulate("FAST TEST")
        >>>
        >>> # OOK mode (on-off keying)
        >>> modem = SCAMP(mode='SCAMPOOK')
        >>> audio = modem.modulate("OOK MODE")
    """

    # Mode configuration
    # Format: 'mode_name': (is_fsk, samples_per_bit_base, shift_hz, bandwidth_hz, channel_bw_hz)
    # samples_per_bit_base is multiplied by (samplerate/2000) to get actual samples
    MODES = {
        'SCAMPFSK': {
            'is_fsk': True,
            'samples_per_bit': 60,      # 60 * (8000/2000) = 240 samples/bit
            'shift_hz': 66.67,          # Frequency shift
            'bandwidth_hz': 133.33,     # Total bandwidth
            'channel_bw_hz': 33.33,     # Channel bandwidth
            'baud': 33.33               # 8000/240 = 33.33 baud
        },
        'SCAMPOOK': {
            'is_fsk': False,
            'samples_per_bit': 64,      # 64 * (8000/2000) = 256 samples/bit
            'shift_hz': 0,              # No shift for OOK
            'bandwidth_hz': 62.5,       # Total bandwidth
            'channel_bw_hz': 31.25,     # Channel bandwidth
            'baud': 31.25               # 8000/256 = 31.25 baud
        },
        'SCFSKFST': {
            'is_fsk': True,
            'samples_per_bit': 24,      # 24 * (8000/2000) = 96 samples/bit
            'shift_hz': 166.67,         # Frequency shift
            'bandwidth_hz': 333.33,     # Total bandwidth
            'channel_bw_hz': 83.33,     # Channel bandwidth
            'baud': 83.33               # 8000/96 = 83.33 baud
        },
        'SCFSKSLW': {
            'is_fsk': True,
            'samples_per_bit': 144,     # 144 * (8000/2000) = 576 samples/bit
            'shift_hz': 41.67,          # Frequency shift
            'bandwidth_hz': 69.44,      # Total bandwidth (41.67 + 2*13.89)
            'channel_bw_hz': 41.67,     # Channel bandwidth
            'baud': 13.89               # 8000/576 = 13.89 baud
        },
        'SCOOKSLW': {
            'is_fsk': False,
            'samples_per_bit': 144,     # 144 * (8000/2000) = 576 samples/bit
            'shift_hz': 0,              # No shift for OOK
            'bandwidth_hz': 27.78,      # Total bandwidth (2*13.89)
            'channel_bw_hz': 41.67,     # Channel bandwidth
            'baud': 13.89               # 8000/576 = 13.89 baud
        },
        'SCFSKVSL': {
            'is_fsk': True,
            'samples_per_bit': 288,     # 288 * (8000/2000) = 1152 samples/bit
            'shift_hz': 20.83,          # Frequency shift (half of SCFSKSLW)
            'bandwidth_hz': 34.72,      # Total bandwidth (0.5*(41.67+2*13.89))
            'channel_bw_hz': 20.83,     # Channel bandwidth
            'baud': 6.94                # 8000/1152 = 6.94 baud
        },
    }

    def __init__(
        self,
        mode: str = 'SCAMPFSK',
        sample_rate: int = 8000,
        frequency: float = 1000.0,
        tx_amplitude: float = 0.8,
        repeat_frames: int = None,
        resync_frames: int = 0,
        enable_filter: bool = True,
        filter_bw_multiplier: float = 1.5
    ):
        """
        Initialize the SCAMP modem.

        Args:
            mode: SCAMP mode variant. Options:
                  - 'SCAMPFSK': Standard FSK (33.33 baud, 133 Hz BW)
                  - 'SCAMPOOK': Standard OOK (31.25 baud, 62.5 Hz BW)
                  - 'SCFSKFST': Fast FSK (83.33 baud, 333 Hz BW)
                  - 'SCFSKSLW': Slow FSK (13.89 baud, 69.44 Hz BW)
                  - 'SCOOKSLW': Slow OOK (13.89 baud, 27.78 Hz BW)
                  - 'SCFSKVSL': Very Slow FSK (6.94 baud, 34.72 Hz BW)
            sample_rate: Audio sample rate in Hz (fixed at 8000, other values ignored)
            frequency: Carrier frequency in Hz (default: 1000)
            tx_amplitude: Transmit amplitude scaling (0.0 to 1.0, default: 0.8)
            repeat_frames: Number of times to repeat preamble/postamble frames (1-9).
                          If None, uses mode-appropriate default: 4 for fast modes,
                          2 for standard modes, 1 for slow modes.
            resync_frames: Send resync every N frames (0 = disabled, 1-9, default: 0)
            enable_filter: Enable low-pass filtering on baseband (default: True)
            filter_bw_multiplier: Filter bandwidth multiplier relative to signal BW (default: 1.5)

        Raises:
            ValueError: If mode is not recognized
        """
        # SCAMP requires 8000 Hz sample rate (matching fldigi)
        sample_rate = 8000

        super().__init__(mode_name=mode, sample_rate=sample_rate, frequency=frequency)

        if mode not in self.MODES:
            valid_modes = ', '.join(self.MODES.keys())
            raise ValueError(f"Invalid SCAMP mode '{mode}'. Valid modes: {valid_modes}")

        self.mode = mode
        mode_cfg = self.MODES[mode]

        # Mode parameters
        self.is_fsk = mode_cfg['is_fsk']
        self.shift_hz = mode_cfg['shift_hz']
        self.bandwidth_hz = mode_cfg['bandwidth_hz']
        self.channel_bw_hz = mode_cfg['channel_bw_hz']
        self.baud = mode_cfg['baud']

        # Calculate samples per bit
        # In fldigi: circbuffer_samples = base * (samplerate/2000)
        base = mode_cfg['samples_per_bit']
        self.samples_per_bit = int(base * (self.sample_rate / 2000))

        # TX parameters
        self.tx_amplitude = max(0.0, min(1.0, tx_amplitude))

        # Set default repeat_frames based on mode speed if not specified
        # Faster modes need more repetitions for reliable end-of-transmission detection
        if repeat_frames is None:
            if mode == 'SCFSKFST':  # Fast mode (83.33 baud)
                repeat_frames = 4
            elif mode in ['SCAMPFSK', 'SCAMPOOK']:  # Standard modes (31-33 baud)
                repeat_frames = 2
            else:  # Slow/very slow modes (6-14 baud)
                repeat_frames = 1

        self.repeat_frames = max(1, min(9, repeat_frames))
        self.resync_frames = max(0, min(9, resync_frames))

        # Filter parameters
        self.enable_filter = enable_filter
        self.filter_bw_multiplier = filter_bw_multiplier

        # Internal state
        self._nco: Optional[NCO] = None
        self._phase = 0.0  # Carrier phase
        self._duplicate_code = 0xFFFF  # Track duplicate codewords

    def tx_init(self):
        """Initialize transmitter state."""
        self._nco = NCO(self.sample_rate, self.frequency)
        self._phase = 0.0
        self._duplicate_code = 0xFFFF

    def _apply_lowpass_filter(self, audio: np.ndarray) -> np.ndarray:
        """
        Apply low-pass filter to clean up the baseband spectrum.

        This reduces spectral splatter, especially important for OOK modes
        where abrupt amplitude transitions create wide sidebands.

        Args:
            audio: Input audio samples

        Returns:
            Filtered audio samples
        """
        if not self.enable_filter or len(audio) < 10:
            return audio

        # Calculate filter cutoff based on signal bandwidth
        # Use the theoretical bandwidth of the mode
        cutoff_hz = self.bandwidth_hz * self.filter_bw_multiplier
        nyquist = self.sample_rate / 2.0
        cutoff_normalized = cutoff_hz / nyquist

        # Ensure cutoff is valid (must be < 1.0)
        cutoff_normalized = min(cutoff_normalized, 0.95)

        # Design 5th order Butterworth lowpass filter
        # Butterworth provides flat passband and smooth rolloff
        b, a = signal.butter(5, cutoff_normalized, btype='low')

        # Apply zero-phase filtering (filtfilt = forward + backward pass)
        # This eliminates phase distortion while doubling the filter order
        filtered = signal.filtfilt(b, a, audio)

        return filtered.astype(np.float32)

    def _send_frame_fsk(self, frame: int) -> np.ndarray:
        """
        Send a 30-bit frame using FSK modulation.

        FSK (Frequency Shift Keying):
        - Bit 1: carrier + shift/2
        - Bit 0: carrier - shift/2

        Based on fldigi/src/scamp/scamp.cxx:375-384

        Args:
            frame: 30-bit frame value

        Returns:
            Audio samples for the frame
        """
        # Phase increment for carrier frequency
        # phaseinc = 2π * frequency / samplerate
        carrier_inc = 2.0 * np.pi * self.frequency / self.sample_rate

        # Phase increment for shift (±shift/2)
        # shift_freq = π * shift_hz / samplerate
        shift_inc = np.pi * self.shift_hz / self.sample_rate

        output = []

        # Send 30 bits, MSB first - direct frequency modulation at carrier
        for bit_no in range(30):
            # Extract bit (MSB first, matching fldigi line 373)
            bit_val = (frame >> (29 - bit_no)) & 1

            # Calculate phase increment: carrier ± shift
            # freq = phaseinc + (bitv ? shift_freq : -shift_freq)
            phase_inc = carrier_inc + (shift_inc if bit_val else -shift_inc)

            # Generate samples for this bit
            for _ in range(self.samples_per_bit):
                # Direct sine generation at modulated frequency
                output.append(np.sin(self._phase))
                self._phase += phase_inc

                # Keep phase in range [0, 2π)
                if self._phase >= 2.0 * np.pi:
                    self._phase -= 2.0 * np.pi

        return np.array(output, dtype=np.float32)

    def _send_frame_ook(self, frame: int) -> np.ndarray:
        """
        Send a 30-bit frame using OOK modulation.

        OOK (On-Off Keying):
        - Bit 1: full amplitude
        - Bit 0: zero amplitude

        Args:
            frame: 30-bit frame value

        Returns:
            Audio samples for the frame
        """
        # Generate baseband amplitude envelope
        baseband = []

        # Send 30 bits, MSB first - generate baseband amplitude
        for bit_no in range(30):
            # Extract bit (MSB first)
            bit_val = (frame >> (29 - bit_no)) & 1

            # Amplitude based on bit value (baseband envelope)
            amplitude = 1.0 if bit_val else 0.0

            # Generate baseband envelope samples for this bit
            for _ in range(self.samples_per_bit):
                baseband.append(amplitude)

        baseband = np.array(baseband, dtype=np.float32)

        # Apply lowpass filter to baseband envelope
        baseband = self._apply_lowpass_filter(baseband)

        # Mix to carrier frequency (amplitude modulation)
        n_samples = len(baseband)
        carrier_phase = self._phase
        carrier_inc = 2.0 * np.pi * self.frequency / self.sample_rate

        output = []
        for i in range(n_samples):
            # Amplitude modulation: baseband envelope × carrier
            output.append(baseband[i] * np.sin(carrier_phase))
            carrier_phase += carrier_inc
            if carrier_phase >= 2.0 * np.pi:
                carrier_phase -= 2.0 * np.pi

        self._phase = carrier_phase
        return np.array(output, dtype=np.float32)

    def _send_frame(self, frame: int) -> np.ndarray:
        """
        Send a 30-bit SCAMP frame.

        Args:
            frame: 30-bit frame value

        Returns:
            Audio samples for the frame
        """
        if self.is_fsk:
            return self._send_frame_fsk(frame)
        else:
            return self._send_frame_ook(frame)

    def _send_preamble(self) -> np.ndarray:
        """
        Generate SCAMP preamble sequence.

        Preamble differs by mode:
        - FSK: 1x SOLID codeword (all 1s)
        - OOK: 4x DOTTED codeword (alternating pattern)
        Then both modes send:
        - INIT codeword (repeated based on repeat_frames)
        - SYNC codeword (repeated based on repeat_frames)

        Returns:
            Audio samples for preamble
        """
        samples = []

        # Initial preamble pattern
        if self.is_fsk:
            # FSK: Send SOLID codeword (all 1s) once
            samples.append(self._send_frame(SCAMP_SOLID_CODEWORD))
        else:
            # OOK: Send DOTTED codeword (alternating pattern) 4 times
            for _ in range(4):
                samples.append(self._send_frame(SCAMP_DOTTED_CODEWORD))

        # Send INIT codeword (repeated)
        for _ in range(self.repeat_frames):
            samples.append(self._send_frame(SCAMP_INIT_CODEWORD))

        # Send SYNC codeword (repeated)
        for _ in range(self.repeat_frames):
            samples.append(self._send_frame(SCAMP_SYNC_CODEWORD))

        return np.concatenate(samples)

    def _send_postamble(self) -> np.ndarray:
        """
        Generate SCAMP postamble sequence.

        Sends END_TRANSMISSION frame repeated based on repeat_frames.

        Returns:
            Audio samples for postamble
        """
        samples = []

        # Send END_TRANSMISSION frame (repeated)
        for _ in range(self.repeat_frames):
            samples.append(self._send_frame(SCAMP_RES_CODE_END_TRANSMISSION_FRAME))

        return np.concatenate(samples)

    def _encode_and_send_codeword(self, codeword: int) -> np.ndarray:
        """
        Encode a 12-bit codeword using Golay encoding and send as frame.

        Args:
            codeword: 12-bit codeword (0x000 to 0xFFF)

        Returns:
            Audio samples for the encoded frame
        """
        # Apply Golay(24,12) encoding
        golay_codeword = golay_encode(codeword & 0xFFF)

        # Add reversal bits to create 30-bit frame
        frame = add_reversal_bits(golay_codeword)

        # Send the frame
        return self._send_frame(frame)

    def tx_process(self, text: str) -> np.ndarray:
        """
        Generate SCAMP modulated audio from text.

        This is the main transmit function that:
        1. Sends preamble (for sync and timing recovery)
        2. Encodes text to 12-bit codewords
        3. Applies Golay(24,12) FEC encoding
        4. Adds reversal bits (creates 30-bit frames)
        5. Generates baseband signal and applies low-pass filtering
        6. Modulates to carrier frequency using FSK or OOK
        7. Sends postamble (end of transmission marker)

        Args:
            text: Text string to transmit

        Returns:
            Normalized audio samples as float32 numpy array [-1.0, 1.0]

        Example:
            >>> modem = SCAMP(mode='SCAMPFSK')
            >>> audio = modem.tx_process("HELLO WORLD")
            >>> # Save to WAV or feed to gnuradio
        """
        samples = []

        # Send preamble
        samples.append(self._send_preamble())

        # Encode text to codewords
        codewords = text_to_codewords(text)

        # Send each codeword (baseband filtering happens inside _send_frame)
        for codeword in codewords:
            frame_samples = self._encode_and_send_codeword(codeword)
            samples.append(frame_samples)

        # Send postamble
        samples.append(self._send_postamble())

        # Concatenate all samples
        audio = np.concatenate(samples)

        # Apply amplitude scaling and normalize
        audio = audio * self.tx_amplitude
        audio = normalize_audio(audio)

        return audio.astype(np.float32)


# Convenience instances for each mode
def create_mode_instance(mode: str, **kwargs) -> SCAMP:
    """Create a SCAMP instance for a specific mode."""
    return SCAMP(mode=mode, **kwargs)


# Export convenience constructors (matching API standard)
SCAMPFSK = lambda **kwargs: SCAMP(mode='SCAMPFSK', **kwargs)
SCAMPOOK = lambda **kwargs: SCAMP(mode='SCAMPOOK', **kwargs)
SCFSKFST = lambda **kwargs: SCAMP(mode='SCFSKFST', **kwargs)
SCFSKSLW = lambda **kwargs: SCAMP(mode='SCFSKSLW', **kwargs)
SCOOKSLW = lambda **kwargs: SCAMP(mode='SCOOKSLW', **kwargs)
SCFSKVSL = lambda **kwargs: SCAMP(mode='SCFSKVSL', **kwargs)
