"""
Symbol Timing Recovery Components

This module provides timing recovery algorithms for symbol synchronization
in digital communication systems. Timing recovery determines the optimal
sampling instant for each symbol.

Reference:
    - "A BPSK/QPSK Timing-Error Detector for Sampled Receivers" - Gardner (1986)
    - "Digital Communications" - Proakis, Chapter 6
    - GNU Radio: gr-digital/lib/symbol_sync_cc_impl.cc
"""

import numpy as np
from typing import Tuple, List, Optional


class SymbolSlicer:
    """
    Simple decimating symbol slicer with no timing recovery.

    Takes every Nth sample where N is the samples_per_symbol rate.
    This is the simplest approach - good for strong signals with
    accurate timing, but no clock drift correction.

    Use this for:
    - Initial decoder implementations
    - Strong signals with negligible timing error
    - Testing and validation

    For production decoders with weak signals or timing drift,
    use GardnerTimingRecovery or EarlyLateGate instead.

    Example:
        >>> slicer = SymbolSlicer(samples_per_symbol=4)
        >>> samples = np.array([...])  # 100 samples
        >>> symbols = slicer.process(samples)  # Returns ~25 symbols
    """

    def __init__(self, samples_per_symbol: int, initial_phase: float = 0.0):
        """
        Initialize the symbol slicer.

        Args:
            samples_per_symbol: Number of samples per symbol (decimation factor)
            initial_phase: Initial sampling phase offset (0.0 to 1.0)
                          0.0 = sample at beginning of symbol period
                          0.5 = sample at middle of symbol period
        """
        if samples_per_symbol < 1:
            raise ValueError("samples_per_symbol must be >= 1")
        if not 0.0 <= initial_phase < 1.0:
            raise ValueError("initial_phase must be in range [0.0, 1.0)")

        self.samples_per_symbol = samples_per_symbol
        self.phase = initial_phase * samples_per_symbol

    def process(self, samples: np.ndarray) -> np.ndarray:
        """
        Decimate samples to extract symbols.

        Args:
            samples: Input sample array (complex or real)

        Returns:
            Array of symbols (decimated samples)
        """
        symbols = []

        for sample in samples:
            self.phase += 1.0

            if self.phase >= self.samples_per_symbol:
                symbols.append(sample)
                self.phase -= self.samples_per_symbol

        return np.array(symbols, dtype=samples.dtype)

    def reset(self, initial_phase: float = 0.0):
        """
        Reset the slicer state.

        Args:
            initial_phase: Initial sampling phase offset (0.0 to 1.0)
        """
        if not 0.0 <= initial_phase < 1.0:
            raise ValueError("initial_phase must be in range [0.0, 1.0)")
        self.phase = initial_phase * self.samples_per_symbol


class EarlyLateGate:
    """
    Early-Late Gate timing recovery.

    Compares energy in early vs late samples to adjust timing phase.
    Simple and robust, but less optimal than Gardner for data-directed recovery.

    Algorithm:
        1. Take 3 samples per symbol: early, on-time, late
        2. Compare energy: |early|² vs |late|²
        3. If early > late: sample clock is late, advance
        4. If late > early: sample clock is early, retard
        5. Adjust sampling phase accordingly

    Use for:
        - CW (Morse code)
        - FSK modes
        - Non-linear modulations

    Example:
        >>> gate = EarlyLateGate(samples_per_symbol=4, loop_bw=0.01)
        >>> for sample in samples:
        >>>     symbol, ready = gate.update(sample)
        >>>     if ready:
        >>>         process_symbol(symbol)
    """

    def __init__(self, samples_per_symbol: float, loop_bw: float = 0.01):
        """
        Initialize early-late gate timing recovery.

        Args:
            samples_per_symbol: Nominal samples per symbol
            loop_bw: Loop bandwidth (lower = more filtering, slower tracking)
        """
        self.sps = samples_per_symbol
        self.loop_bw = loop_bw
        self.mu = 0.5  # Timing phase (0 to 1)
        self.omega = samples_per_symbol

        # Loop filter gains
        self.gain = loop_bw

        # Sample buffer for early/prompt/late
        self.early = 0.0
        self.prompt = 0.0
        self.late = 0.0

        self.sample_count = 0

    def update(self, sample: complex) -> Tuple[Optional[complex], bool]:
        """
        Process one sample, return symbol when ready.

        Args:
            sample: Input sample (complex or real)

        Returns:
            (symbol, ready) tuple:
                - symbol: Output symbol (None if not ready)
                - ready: True if symbol is valid
        """
        # Rotate samples through early/prompt/late
        self.early = self.prompt
        self.prompt = self.late
        self.late = sample

        self.sample_count += 1

        # Check if we should output a symbol
        if self.sample_count >= self.omega:
            # Output the prompt sample
            symbol = self.prompt

            # Calculate timing error: |early|² - |late|²
            early_power = np.abs(self.early) ** 2
            late_power = np.abs(self.late) ** 2
            error = early_power - late_power

            # Update timing with loop filter
            self.omega -= self.gain * error

            # Clamp omega to reasonable range
            self.omega = np.clip(self.omega, self.sps * 0.8, self.sps * 1.2)

            # Reset counter
            self.sample_count = 0

            return symbol, True

        return None, False

    def reset(self):
        """Reset the timing recovery state."""
        self.mu = 0.5
        self.omega = self.sps
        self.sample_count = 0
        self.early = 0.0
        self.prompt = 0.0
        self.late = 0.0


class GardnerTimingRecovery:
    """
    Gardner timing error detector for symbol synchronization.

    The Gardner algorithm is a data-directed timing recovery method that
    works well for linear modulations (PSK, QAM). It operates at 2 samples
    per symbol and doesn't require knowledge of the transmitted data.

    Algorithm:
        1. Sample at rate 2× symbol rate (interpolated)
        2. At symbol k: prev = x[k-1], curr = x[k], next = x[k+1]
        3. Error = real(curr) × (real(prev) - real(next))
        4. Positive error → clock is late, advance phase
        5. Negative error → clock is early, retard phase

    Reference:
        Gardner, F. "A BPSK/QPSK Timing-Error Detector for Sampled Receivers"
        IEEE Trans. Comm., Vol. COM-34, May 1986

    Use for:
        - PSK (BPSK, QPSK, 8PSK)
        - QAM
        - Any linear modulation

    Example:
        >>> recovery = GardnerTimingRecovery(samples_per_symbol=4)
        >>> symbols = recovery.process(samples)
    """

    def __init__(
        self,
        samples_per_symbol: float,
        loop_bw: float = 0.01,
        damping: float = 1.0,
        max_deviation: float = 0.2
    ):
        """
        Initialize Gardner timing recovery.

        Args:
            samples_per_symbol: Nominal samples per symbol (typically 2-8)
            loop_bw: Loop bandwidth (0.001 to 0.1, lower = slower tracking)
            damping: Damping factor (typically 0.707 to 1.0)
            max_deviation: Maximum allowed timing deviation (fraction of symbol period)
        """
        self.sps = samples_per_symbol
        self.loop_bw = loop_bw
        self.damping = damping
        self.max_deviation = max_deviation

        # Timing state
        self.mu = 0.0  # Fractional timing offset (0 to 1)
        self.omega = samples_per_symbol  # Current estimate of samples per symbol

        # Loop filter gains (proportional and integral)
        # Using natural frequency formulation
        omega_n = loop_bw * 2 * np.pi
        self.gain_omega = (omega_n ** 2) / self.sps  # Integral gain
        self.gain_mu = 2 * damping * omega_n  # Proportional gain

        # Sample history for interpolation
        self.prev_sample = 0.0 + 0.0j
        self.curr_sample = 0.0 + 0.0j

        # Symbol history for Gardner detector
        self.prev_symbol = 0.0 + 0.0j

        # Sample accumulator
        self.sample_buffer = []

    def process(self, samples: np.ndarray) -> np.ndarray:
        """
        Process a block of samples and extract symbols.

        Args:
            samples: Input sample array (complex or real)

        Returns:
            Array of recovered symbols
        """
        symbols = []

        for sample in samples:
            symbol, ready = self._update(sample)
            if ready:
                symbols.append(symbol)

        return np.array(symbols, dtype=samples.dtype)

    def _update(self, sample: complex) -> Tuple[Optional[complex], bool]:
        """
        Process one sample using Gardner timing recovery.

        Args:
            sample: Input sample

        Returns:
            (symbol, ready) tuple
        """
        # Update sample buffer
        self.sample_buffer.append(sample)

        # Advance timing phase
        self.mu += 1.0 / self.omega

        # Check if we've accumulated enough phase for a symbol
        if self.mu >= 1.0:
            self.mu -= 1.0

            # Need at least 2 samples for interpolation
            if len(self.sample_buffer) < 2:
                return None, False

            # Interpolate symbol at mu
            # Linear interpolation between samples
            idx = len(self.sample_buffer) - 2
            alpha = self.mu  # Fractional delay
            symbol = (1 - alpha) * self.sample_buffer[idx] + alpha * self.sample_buffer[idx + 1]

            # Gardner timing error detector
            # error = real(mid) * (real(early) - real(late))
            if self.prev_symbol is not None:
                mid = symbol
                early = self.prev_symbol

                # Get "late" sample (half symbol period ahead)
                # This is approximate - we take next available sample
                if len(self.sample_buffer) > idx + 1:
                    late = self.sample_buffer[-1]

                    # Gardner error (works for real and complex)
                    error = np.real(mid) * (np.real(early) - np.real(late))

                    # Update timing with loop filter
                    self.omega += self.gain_omega * error

                    # Clamp omega to prevent runaway
                    omega_min = self.sps * (1.0 - self.max_deviation)
                    omega_max = self.sps * (1.0 + self.max_deviation)
                    self.omega = np.clip(self.omega, omega_min, omega_max)

            # Save for next iteration
            self.prev_symbol = symbol

            # Clear old samples from buffer (keep last few for interpolation)
            if len(self.sample_buffer) > 4:
                self.sample_buffer = self.sample_buffer[-4:]

            return symbol, True

        return None, False

    def reset(self):
        """Reset the timing recovery state."""
        self.mu = 0.0
        self.omega = self.sps
        self.prev_sample = 0.0 + 0.0j
        self.curr_sample = 0.0 + 0.0j
        self.prev_symbol = 0.0 + 0.0j
        self.sample_buffer = []
