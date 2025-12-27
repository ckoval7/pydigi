"""
MT63 modem implementation - Completely rebuilt from fldigi source documentation.

MT63 is a robust OFDM (Orthogonal Frequency Division Multiplexed) mode using:
- 64 parallel carriers with differential BPSK modulation
- Walsh-Hadamard Forward Error Correction (7 bits → 64 chips = 9.1× overhead)
- Block interleaving for burst error resistance
- Raised cosine symbol shaping for minimal ISI
- Three bandwidths: 500 Hz, 1000 Hz, 2000 Hz
- Two interleave depths: Short (32 symbols ≈ 0.8s), Long (64 symbols ≈ 1.6s)

Based on MT63 by Pawel Jalocha (SP9VRC) and fldigi implementation by Dave Freese (W1HKJ)
Reference: See MT63_ANALYSIS.md, MT63_QUICK_REFERENCE.md, MT63_IMPLEMENTATION_ROADMAP.md
"""

import numpy as np
from ..core.mt63_data import (
    SYMBOL_LEN, SYMBOL_SEPAR, DATA_CARR_SEPAR, DATA_CARRIERS,
    SHORT_INTLV_PATT, LONG_INTLV_PATT, SYMBOL_SHAPE
)
from ..core.mt63_filters import (
    PolyphaseInterpolator, OverlapAddWindow
)


def walsh_inverse_transform(data):
    """
    Fast Walsh-Hadamard inverse transform.

    The Walsh transform provides Forward Error Correction in MT63.
    Each 7-bit character is encoded as one of 128 Walsh functions (64 positive, 64 negative).

    Args:
        data: numpy array of length 2^N (typically 64 for MT63)

    Returns:
        Transformed data (in-place modification)

    Algorithm (from fldigi src/mt63/mt63base.cxx):
        Butterfly structure similar to FFT, but using only +/- operations
        Step size decreases from N/2 down to 1
        ptr1 = data[ptr2], ptr1' = ptr1 - ptr2, ptr2' = ptr1 + ptr2
    """
    data = np.array(data, dtype=np.float64, copy=True)
    length = len(data)
    step = length // 2

    while step > 0:
        ptr = 0
        while ptr < length:
            for ptr2 in range(ptr, ptr + step):
                bit1 = data[ptr2]
                bit2 = data[ptr2 + step]
                data[ptr2] = bit1 - bit2        # First half: difference
                data[ptr2 + step] = bit1 + bit2  # Second half: sum
            ptr += 2 * step
        step //= 2

    return data


def walsh_transform(data):
    """
    Fast Walsh-Hadamard forward transform (for decoding).

    Args:
        data: numpy array of length 2^N

    Returns:
        Transformed data, normalized by length

    Algorithm: Similar to inverse, but step size increases from 1 to N/2
    """
    data = np.array(data, dtype=np.float64, copy=True)
    length = len(data)
    step = 1

    while step < length:
        ptr = 0
        while ptr < length:
            for ptr2 in range(ptr, ptr + step):
                bit1 = data[ptr2]
                bit2 = data[ptr2 + step]
                data[ptr2] = bit1 + bit2        # First half: sum
                data[ptr2 + step] = bit2 - bit1  # Second half: difference
            ptr += 2 * step
        step *= 2

    # NOTE: No normalization to match fldigi exactly
    # fldigi's dspWalshTrans doesn't normalize
    # For decoding, only relative magnitudes matter, not absolute values
    return data


class MT63Encoder:
    """
    MT63 character encoder with Walsh FEC and block interleaving.

    Signal flow (from MT63_DIAGRAMS.md):
        ASCII char → Walsh mapping → Inverse Walsh transform → 64 chips →
        Bit conversion → Interleave write → Interleave read → Output bits[64]

    Reference: MT63_ANALYSIS.md lines 593-669
    """

    def __init__(self, carriers=64, interleave=32, pattern=None):
        """
        Initialize MT63 encoder.

        Args:
            carriers: Number of data carriers (must be power of 2, always 64 for MT63)
            interleave: Interleave depth (32 for short, 64 for long)
            pattern: Interleave pattern array (see MT63_ANALYSIS.md line 673-691)
        """
        self.data_carriers = carriers
        self.interleave_len = interleave
        self.code_mask = 2 * carriers - 1  # 127 for 64 carriers (7-bit ASCII)

        # Set interleave pattern
        if pattern is None:
            pattern = LONG_INTLV_PATT if interleave == 64 else SHORT_INTLV_PATT

        # Compute interleave lookup table
        # IntlvPatt[i] tells how many symbols back to read bit i from
        # Pattern value N means "read bit from N symbols ago"
        self.interleave_pattern = np.zeros(carriers, dtype=np.int32)
        p = 0
        for i in range(carriers):
            self.interleave_pattern[i] = p * carriers
            p += pattern[i]
            if p >= interleave:
                p -= interleave

        # Interleave pipe (circular buffer)
        # Size = interleave_len × carriers bits
        # Short: 32 × 64 = 2048 bits, Long: 64 × 64 = 4096 bits
        self.interleave_size = interleave * carriers
        # Initialize with zeros (matching fldigi's RandFill=0 default)
        # Random initialization causes gibberish in decoded output
        self.interleave_pipe = np.zeros(self.interleave_size, dtype=np.uint8)
        self.interleave_ptr = 0

        # Working buffers
        self.walsh_buff = np.zeros(carriers, dtype=np.float64)
        self.output = np.zeros(carriers, dtype=np.uint8)

    def process(self, code):
        """
        Encode one character.

        Args:
            code: 7-bit ASCII character code (0-127)

        Returns:
            Array of 64 bits to transmit on each carrier (0 or 1)

        Algorithm (from MT63_ANALYSIS.md lines 632-669):
            1. Mask to 7 bits
            2. Map to Walsh function (0-63 positive, 64-127 negative)
            3. Inverse Walsh transform → 64 soft values
            4. Convert to bits
            5. Store in interleave pipe
            6. Read interleaved output
            7. Advance pointer
        """
        # Step 1: Mask to 7 bits
        code = code & self.code_mask

        # Step 2: Map to Walsh function
        self.walsh_buff.fill(0.0)
        if code < self.data_carriers:
            # Codes 0-63: positive Walsh functions
            self.walsh_buff[code] = 1.0
        else:
            # Codes 64-127: negative Walsh functions
            self.walsh_buff[code - self.data_carriers] = -1.0

        # Step 3: Inverse Walsh transform
        self.walsh_buff = walsh_inverse_transform(self.walsh_buff)

        # Step 4: Convert to bits (negative → 1, positive → 0)
        # This matches fldigi: bit[i] = (WalshBuff[i] < 0.0) ? 1 : 0
        for i in range(self.data_carriers):
            self.interleave_pipe[self.interleave_ptr + i] = 1 if self.walsh_buff[i] < 0.0 else 0

        # Step 5: Read interleaved bits for output
        # For each carrier i, read from IntlvPtr + IntlvPatt[i] + i
        for i in range(self.data_carriers):
            k = self.interleave_ptr + self.interleave_pattern[i]
            if k >= self.interleave_size:
                k -= self.interleave_size
            # Add carrier index and wrap again if needed
            idx = k + i
            if idx >= self.interleave_size:
                idx -= self.interleave_size
            self.output[i] = self.interleave_pipe[idx]

        # Step 6: Advance interleave pointer
        self.interleave_ptr += self.data_carriers
        if self.interleave_ptr >= self.interleave_size:
            self.interleave_ptr -= self.interleave_size

        return self.output.copy()


class MT63Modulator:
    """
    MT63 OFDM modulator using IFFT.

    Signal flow (from MT63_ANALYSIS.md lines 149-210):
        Encoder bits[64] → Phase modulation (differential BPSK) →
        Populate FFT bins (bit-reversed) → IFFT (2×512pt) →
        Negate imaginary → Window → Overlap-add → I/Q combine → Audio out

    Reference: MT63_ANALYSIS.md Transmitter section
    """

    def __init__(self, freq, bandwidth, interleave_len, sample_rate=8000):
        """
        Initialize MT63 modulator.

        Args:
            freq: Center frequency in Hz (typically 750, 1000, or 1500)
            bandwidth: Bandwidth in Hz (500, 1000, or 2000)
            interleave_len: Interleave depth (32 or 64)
            sample_rate: Audio sample rate (must be 8000 Hz for MT63)

        Reference: MT63_ANALYSIS.md lines 113-149, MT63_QUICK_REFERENCE.md lines 16-24
        """
        if sample_rate != 8000:
            raise ValueError("MT63 requires 8000 Hz sample rate")

        self.freq = freq
        self.bandwidth = bandwidth
        self.sample_rate = sample_rate
        self.interleave_len = interleave_len

        # Fixed MT63 parameters (from symbol.dat)
        self.fft_size = SYMBOL_LEN  # 512
        self.window_len = SYMBOL_LEN  # 512
        self.symbol_separ = SYMBOL_SEPAR  # 200 samples (64 ms @ 8 kHz)

        # Mode-specific parameters (from MT63_QUICK_REFERENCE.md lines 16-24)
        if bandwidth == 500:
            # FirstDataCarr = floor((freq - BW/2) * 256/500 + 0.5)
            self.first_data_carr = int(np.floor((freq - bandwidth / 2.0) * 256 / 500 + 0.5))
            self.interpolate_ratio = 8  # 1000 Hz → 8000 Hz
            self.alias_filter_len = 128
        elif bandwidth == 1000:
            # FirstDataCarr = floor((freq - BW/2) * 128/500 + 0.5)
            self.first_data_carr = int(np.floor((freq - bandwidth / 2.0) * 128 / 500 + 0.5))
            self.interpolate_ratio = 4  # 2000 Hz → 8000 Hz
            self.alias_filter_len = 64
        elif bandwidth == 2000:
            # FirstDataCarr = floor((freq - BW/2) * 64/500 + 0.5)
            self.first_data_carr = int(np.floor((freq - bandwidth / 2.0) * 64 / 500 + 0.5))
            self.interpolate_ratio = 2  # 4000 Hz → 8000 Hz
            self.alias_filter_len = 64
        else:
            raise ValueError(f"Invalid bandwidth: {bandwidth}, must be 500, 1000, or 2000")

        # Transmit amplitude (from MT63_QUICK_REFERENCE.md line 48)
        # TxAmpl = 4.0 / DataCarriers = 4.0/64 = 0.0625
        self.tx_ampl = 4.0 / DATA_CARRIERS

        # Phase vectors for each carrier (differential BPSK state)
        # TxVect[i] indexes into FFT twiddle factors (0 to 511)
        self.tx_vect = np.zeros(DATA_CARRIERS, dtype=np.int32)
        self.phase_corr = np.zeros(DATA_CARRIERS, dtype=np.int32)

        # Initialize phase vectors (spread initial phases)
        # This provides smooth spectrum and avoids peaks
        mask = self.fft_size - 1
        step = 0
        incr = 1
        p = 0
        for i in range(DATA_CARRIERS):
            self.tx_vect[i] = p
            step += incr
            p = (p + step) & mask

        # Compute phase correction for symbol separation
        # (from MT63_ANALYSIS.md lines 960-961, MT63_QUICK_REFERENCE.md lines 243-247)
        # dspPhaseCorr[i] = (SymbolSepar * carrier_freq) mod FFT.Size
        incr = (SYMBOL_SEPAR * DATA_CARR_SEPAR) & mask
        p = (SYMBOL_SEPAR * self.first_data_carr) & mask
        for i in range(DATA_CARRIERS):
            self.phase_corr[i] = p
            p = (p + incr) & mask

        # Pre-compute FFT twiddle factors (phase angles for each carrier)
        # exp(2πi·k/N) for k=0..N-1
        self.carrier_phases = np.exp(2j * np.pi * np.arange(self.fft_size) / self.fft_size)

        # Compute bit-reverse lookup table for FFT
        # This is CRITICAL - fldigi uses bit-reversed indexing!
        self.bit_rev_table = self._compute_bit_reverse_table(self.fft_size)

        # Overlap-and-add window processor
        # Slide distance = SymbolSepar/2 = 100 samples (from MT63_ANALYSIS.md lines 255-256)
        self.overlap_window = OverlapAddWindow(
            window_len=self.window_len,
            slide_dist=self.symbol_separ // 2,  # 100 samples
            window_shape=SYMBOL_SHAPE
        )

        # Polyphase interpolator for I/Q to real conversion
        # Calculate filter passband (from MT63_ANALYSIS.md lines 120-127)
        # hbw = 1.5 × BW/2 (50% margin)
        hbw = 1.5 * bandwidth / 2.0
        omega_low = max((freq - hbw), 100) * (np.pi / 4000)
        omega_high = min((freq + hbw), 4000) * (np.pi / 4000)

        self.interpolator = PolyphaseInterpolator(
            filter_len=self.alias_filter_len,
            rate=self.interpolate_ratio,
            low_omega=omega_low,
            high_omega=omega_high
        )

        # Create encoder instance
        pattern = LONG_INTLV_PATT if interleave_len == 64 else SHORT_INTLV_PATT
        self.encoder = MT63Encoder(
            carriers=DATA_CARRIERS,
            interleave=interleave_len,
            pattern=pattern
        )

    def _compute_bit_reverse_table(self, size):
        """
        Compute bit-reverse lookup table for FFT.

        Args:
            size: FFT size (must be power of 2)

        Returns:
            Array where table[i] = bit-reversed index of i
        """
        bits = int(np.log2(size))
        table = np.zeros(size, dtype=np.int32)

        for i in range(size):
            # Reverse the bits
            result = 0
            for bit in range(bits):
                if i & (1 << bit):
                    result |= 1 << (bits - 1 - bit)
            table[i] = result

        return table

    def encode_char_no_tx(self, code):
        """
        Encode a character to fill the interleaver without outputting audio.

        This is used for the preamble null characters that fill the interleaver
        but don't produce transmitted audio (matching fldigi's behavior).

        IMPORTANT: We MUST run through the complete OFDM processing to advance
        all internal DSP states (overlap window, interpolator), but simply
        discard the output audio instead of transmitting it.

        Args:
            code: 7-bit ASCII character code (0-127)
        """
        # Step 1: Encode character to fill interleaver
        bits = self.encoder.process(code)

        # Step 2: Update phase vectors (maintains differential BPSK state)
        mask = self.fft_size - 1
        flip = self.fft_size // 2  # 256 = π radians

        for i in range(DATA_CARRIERS):
            if bits[i]:
                # Bit 1: no flip, only phase correction
                self.tx_vect[i] = (self.tx_vect[i] + self.phase_corr[i]) & mask
            else:
                # Bit 0: π flip + phase correction
                self.tx_vect[i] = (self.tx_vect[i] + self.phase_corr[i] + flip) & mask

        # Step 3: Process through OFDM pipeline to advance DSP states
        # This advances overlap window and interpolator state, critical for
        # proper operation. We generate the audio but discard it.
        _ = self._process_tx_vect()
        # Audio is generated but returned to caller, who discards it

    def send_char(self, code):
        """
        Modulate one character into audio samples.

        Args:
            code: 7-bit ASCII character code (0-127)

        Returns:
            Audio samples for one symbol period (200 samples @ decimated rate,
            then interpolated to 400/800/1600 samples @ 8000 Hz)

        Algorithm (from MT63_ANALYSIS.md lines 151-210):
            1. Encode character → 64 bits
            2. Update phase vectors (differential BPSK)
            3. Generate OFDM symbol
        """
        # Step 1: Encode character
        bits = self.encoder.process(code)

        # Step 2: Update phase vectors (differential BPSK)
        # From MT63_ANALYSIS.md lines 159-166
        # bit=1: no phase flip, bit=0: π phase flip
        mask = self.fft_size - 1
        flip = self.fft_size // 2  # 256 = π radians in phase space

        for i in range(DATA_CARRIERS):
            # Match fldigi exactly: if (Encoder.Output[i]) → no flip
            if bits[i]:
                # Bit 1: no flip, only phase correction
                self.tx_vect[i] = (self.tx_vect[i] + self.phase_corr[i]) & mask
            else:
                # Bit 0: π flip + phase correction
                self.tx_vect[i] = (self.tx_vect[i] + self.phase_corr[i] + flip) & mask

        # Step 3: Generate OFDM symbol
        return self._process_tx_vect()

    def _process_tx_vect(self):
        """
        Generate OFDM symbol from phase vectors.

        Returns:
            Audio samples

        Algorithm (from MT63_ANALYSIS.md lines 169-210):
            a. Populate FFT bins (bit-reversed order)
            b. IFFT (two 512-point for even/odd carriers)
            c. Negate imaginary parts (IFFT convention)
            d. Apply overlapping window
            e. Convert I/Q to real with anti-alias filter

        Critical details:
            - Carriers alternate between two FFT buffers
            - Bit-reversed indexing for in-place IFFT
            - Complex conjugate (negate imaginary) when placing carriers
            - IFFT output: negate imaginary again per fldigi convention
        """
        # Step a: Initialize frequency domain buffers (two 512-point FFTs)
        freq_buff1 = np.zeros(self.window_len, dtype=np.complex128)
        freq_buff2 = np.zeros(self.window_len, dtype=np.complex128)

        mask = self.fft_size - 1

        # Populate FFT bins with carriers
        # NOTE: fldigi uses bit-reversed indexing because their CoreProc expects
        # bit-reversed input. NumPy's ifft does NOT - it handles bit-reversal internally.
        # So we use normal indexing here.
        for i in range(DATA_CARRIERS):
            # Calculate carrier frequency bin
            carrier_idx = (self.first_data_carr + i * DATA_CARR_SEPAR) & mask

            # Get carrier phase from phase vector
            # fldigi uses: Twiddle[TxVect[i]].re and -Twiddle[TxVect[i]].im
            # Which is the conjugate: conj(exp(2πj*phase/N))
            # But we use ifft (not fft), so we DON'T need conjugate
            # Try WITHOUT conjugate:
            phase = self.carrier_phases[self.tx_vect[i]]

            # Alternate carriers between buffers (even/odd separation)
            # This creates two half-symbols for overlap-add
            if i & 1:
                freq_buff2[carrier_idx] = self.tx_ampl * phase
            else:
                freq_buff1[carrier_idx] = self.tx_ampl * phase

        # Step b: IFFT both buffers
        # NumPy's ifft already includes 1/N scaling
        time1 = np.fft.ifft(freq_buff1) * self.window_len
        time2 = np.fft.ifft(freq_buff2) * self.window_len

        # Step c: REMOVED imaginary negation - testing theory
        # fldigi negates because they use FFT instead of IFFT
        # We use proper IFFT, so we might not need this
        # time1.imag *= -1
        # time2.imag *= -1

        # Combine into single buffer (1024 complex samples)
        combined_time = np.concatenate([time1, time2])

        # Step d: Apply overlap-add windowing
        # Input: 2×512 = 1024 samples
        # Output: 2×100 = 200 complex samples (decimated by slide)
        complex_output = self.overlap_window.process(combined_time)

        # Step e: Interpolate and convert I/Q to real
        # 200 complex → 200×interpolate_ratio real samples @ 8000 Hz
        real_output = self.interpolator.process(complex_output)

        return real_output

    def send_jam(self):
        """
        Send jamming sequence (random ±90° phase shifts).

        Used at end of transmission to help receiver detect signal drop.
        From MT63_ANALYSIS.md lines 212-220
        """
        mask = self.fft_size - 1
        left = self.fft_size // 4        # 128 = +90°
        right = 3 * (self.fft_size // 4)  # 384 = -90°

        for i in range(DATA_CARRIERS):
            # Random left or right 90° phase shift
            if np.random.randint(0, 512) & 0x100:
                self.tx_vect[i] = (self.tx_vect[i] + self.phase_corr[i] + left) & mask
            else:
                self.tx_vect[i] = (self.tx_vect[i] + self.phase_corr[i] + right) & mask

        return self._process_tx_vect()


def mt63_modulate(text, mode="MT63-1000L", freq=1000, sample_rate=8000, use_twotone_preamble=True):
    """
    Generate MT63 modulated audio.

    Args:
        text: Text string to transmit (7-bit ASCII)
        mode: MT63 mode variant (MT63-500S, MT63-500L, MT63-1000S,
              MT63-1000L, MT63-2000S, MT63-2000L)
        freq: Center frequency in Hz
        sample_rate: Audio sample rate (must be 8000 Hz)
        use_twotone_preamble: If True, send 2-second two-tone preamble for better sync

    Returns:
        numpy array of audio samples (float, range -1 to +1)

    Preamble/Postamble (from MT63_ANALYSIS.md lines 229-254):
        - Optional: Two-tone preamble (2 seconds) for AFC/sync
        - Preamble: DataInterleave null characters (0x00) for sync
        - Postamble: DataInterleave null characters (flush) + jam symbol
        - Duration: 0.8 sec (short) or 1.6 sec (long)
    """
    if sample_rate != 8000:
        raise ValueError("MT63 requires 8000 Hz sample rate")

    # Parse mode
    mode = mode.upper()
    if "500" in mode:
        bandwidth = 500
    elif "1000" in mode:
        bandwidth = 1000
    elif "2000" in mode:
        bandwidth = 2000
    else:
        raise ValueError(f"Unknown MT63 mode: {mode}")

    interleave = 64 if mode.endswith("L") else 32

    # Create modulator
    modulator = MT63Modulator(freq, bandwidth, interleave, sample_rate)

    audio_samples = []
    max_val = 0.0  # Track maximum value (like fldigi)

    # OPTIONAL TWO-TONE PREAMBLE: Helps fldigi AFC and sync
    # Sends two continuous tones (default 4 seconds to match fldigi):
    #   Tone 1: Lower edge of band (freq - bandwidth/2)
    #   Tone 2: Upper area (freq + 31*bandwidth/64)
    # Reference: fldigi/src/mt63/mt63.cxx lines 73-90
    # Default: 4 seconds (fldigi's MT63TONEDURATION default)
    if use_twotone_preamble:
        tone_duration = 4.0  # seconds (matches fldigi default)
        # TONE_AMP = 0.8 in fldigi (mt63.h:34)
        # Each tone: TONE_AMP * 0.5 = 0.4
        TONE_AMP = 0.8
        tone_amp = TONE_AMP * 0.5  # 0.4 per tone

        # Calculate tone frequencies
        tone1_freq = freq - bandwidth / 2.0
        tone2_freq = freq + 31.0 * bandwidth / 64.0

        # Generate tones
        tone_samples = int(sample_rate * tone_duration)
        t = np.arange(tone_samples) / sample_rate
        omega1 = 2.0 * np.pi * tone1_freq
        omega2 = 2.0 * np.pi * tone2_freq

        # Two-tone signal: 0.4*cos(w1*t) + 0.4*cos(w2*t)
        # Maximum amplitude: 0.8 (when both cosines = 1)
        tones = tone_amp * np.cos(omega1 * t) + tone_amp * np.cos(omega2 * t)

        # Apply soft start (40 samples)
        for i in range(min(40, len(tones))):
            tones[i] *= (1.0 - np.exp(-i / 40.0))

        # Apply soft stop (40 samples)
        for i in range(min(40, len(tones))):
            idx = len(tones) - 1 - i
            tones[idx] *= (1.0 - np.exp(-i / 40.0))

        audio_samples.append(tones)
        max_val = max(max_val, np.max(np.abs(tones)))

    # PREAMBLE: Send null characters to fill the interleaver
    # This allows the receiver to synchronize
    # From MT63_ANALYSIS.md lines 235-239
    # NOTE: We transmit these to ensure reliable decoding
    for _ in range(interleave):
        samples = modulator.send_char(0)
        sample_max = np.max(np.abs(samples))
        if sample_max > max_val:
            max_val = sample_max
        audio_samples.append(samples)

    # Send the actual data
    for char in text:
        code = ord(char)
        if code > 127:
            # MT63 uses 7-bit ASCII, send escape sequence for 8-bit
            # From MT63_ANALYSIS.md lines 1001-1018
            samples = modulator.send_char(127)  # Escape code
            sample_max = np.max(np.abs(samples))
            if sample_max > max_val:
                max_val = sample_max
            audio_samples.append(samples)
            code = code & 127

        samples = modulator.send_char(code)
        sample_max = np.max(np.abs(samples))
        if sample_max > max_val:
            max_val = sample_max
        audio_samples.append(samples)

    # POSTAMBLE: Send null characters to flush the interleaver
    # From MT63_ANALYSIS.md lines 241-248
    for _ in range(interleave):
        samples = modulator.send_char(0)
        sample_max = np.max(np.abs(samples))
        if sample_max > max_val:
            max_val = sample_max
        audio_samples.append(samples)

    # Send jam sequence to help receiver detect end
    jam_samples = modulator.send_jam()
    sample_max = np.max(np.abs(jam_samples))
    if sample_max > max_val:
        max_val = sample_max
    audio_samples.append(jam_samples)

    # Normalize by global maximum (like fldigi tracks maxval)
    # From MT63_ANALYSIS.md lines 206-209
    if max_val > 0:
        normalized_samples = [samples / max_val for samples in audio_samples]
    else:
        normalized_samples = audio_samples

    # Concatenate all audio
    audio = np.concatenate(normalized_samples)

    return audio


# Convenience functions for each mode
def mt63_500s_modulate(text, freq=750, sample_rate=8000, use_twotone_preamble=True):
    """Generate MT63-500 Short interleave (32 symbols)."""
    return mt63_modulate(text, "MT63-500S", freq, sample_rate, use_twotone_preamble)


def mt63_500l_modulate(text, freq=750, sample_rate=8000, use_twotone_preamble=True):
    """Generate MT63-500 Long interleave (64 symbols)."""
    return mt63_modulate(text, "MT63-500L", freq, sample_rate, use_twotone_preamble)


def mt63_1000s_modulate(text, freq=1000, sample_rate=8000, use_twotone_preamble=True):
    """Generate MT63-1000 Short interleave (32 symbols)."""
    return mt63_modulate(text, "MT63-1000S", freq, sample_rate, use_twotone_preamble)


def mt63_1000l_modulate(text, freq=1000, sample_rate=8000, use_twotone_preamble=True):
    """Generate MT63-1000 Long interleave (64 symbols)."""
    return mt63_modulate(text, "MT63-1000L", freq, sample_rate, use_twotone_preamble)


def mt63_2000s_modulate(text, freq=1500, sample_rate=8000, use_twotone_preamble=True):
    """Generate MT63-2000 Short interleave (32 symbols)."""
    return mt63_modulate(text, "MT63-2000S", freq, sample_rate, use_twotone_preamble)


def mt63_2000l_modulate(text, freq=1500, sample_rate=8000, use_twotone_preamble=True):
    """Generate MT63-2000 Long interleave (64 symbols)."""
    return mt63_modulate(text, "MT63-2000L", freq, sample_rate, use_twotone_preamble)
