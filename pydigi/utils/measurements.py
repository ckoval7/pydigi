"""
Performance Measurement Utilities

This module provides tools for measuring and characterizing decoder performance:
    - BER (Bit Error Rate)
    - SER (Symbol Error Rate)
    - SNR estimation
    - Throughput measurement
    - Latency measurement

Use these for:
    - Validating decoder correctness
    - Characterizing performance vs SNR
    - Comparing different implementations
    - Optimization and profiling
"""

import numpy as np
import time
from typing import Tuple, Optional, Dict
from dataclasses import dataclass


@dataclass
class BERResult:
    """Results from BER calculation."""
    bit_errors: int
    total_bits: int
    ber: float
    error_positions: list  # Indices where errors occurred

    def __str__(self):
        return f"BER: {self.ber:.2e} ({self.bit_errors}/{self.total_bits} errors)"


@dataclass
class SERResult:
    """Results from SER calculation."""
    symbol_errors: int
    total_symbols: int
    ser: float
    error_positions: list

    def __str__(self):
        return f"SER: {self.ser:.2e} ({self.symbol_errors}/{self.total_symbols} errors)"


def calculate_ber(
    tx_bits: np.ndarray,
    rx_bits: np.ndarray,
    skip_initial: int = 0,
    skip_final: int = 0
) -> BERResult:
    """
    Calculate Bit Error Rate between transmitted and received bits.

    BER is the fundamental performance metric for digital communications:
        BER = (number of bit errors) / (total bits)

    Args:
        tx_bits: Transmitted bit sequence (0s and 1s)
        rx_bits: Received bit sequence (0s and 1s)
        skip_initial: Skip first N bits (for synchronization settling)
        skip_final: Skip last N bits (for flush symbols)

    Returns:
        BERResult with error statistics

    Example:
        >>> tx = np.array([0, 1, 1, 0, 1, 0])
        >>> rx = np.array([0, 1, 0, 0, 1, 0])  # 1 error at position 2
        >>> result = calculate_ber(tx, rx)
        >>> print(result)
        BER: 1.67e-01 (1/6 errors)
        >>> print(f"Error at bit {result.error_positions[0]}")
        Error at bit 2
    """
    # Convert to numpy arrays
    tx_bits = np.asarray(tx_bits, dtype=int)
    rx_bits = np.asarray(rx_bits, dtype=int)

    # Handle length mismatch
    min_len = min(len(tx_bits), len(rx_bits))
    if len(tx_bits) != len(rx_bits):
        print(f"Warning: Length mismatch (TX: {len(tx_bits)}, RX: {len(rx_bits)}). Using min length.")
        tx_bits = tx_bits[:min_len]
        rx_bits = rx_bits[:min_len]

    # Apply skip parameters
    start_idx = skip_initial
    end_idx = len(tx_bits) - skip_final

    if start_idx >= end_idx:
        raise ValueError("skip_initial + skip_final exceeds sequence length")

    tx_bits = tx_bits[start_idx:end_idx]
    rx_bits = rx_bits[start_idx:end_idx]

    # Find errors
    errors = tx_bits != rx_bits
    error_positions = np.where(errors)[0] + start_idx  # Adjust for skipped bits
    bit_errors = np.sum(errors)
    total_bits = len(tx_bits)

    # Calculate BER
    ber = bit_errors / total_bits if total_bits > 0 else 0.0

    return BERResult(
        bit_errors=bit_errors,
        total_bits=total_bits,
        ber=ber,
        error_positions=error_positions.tolist()
    )


def calculate_ser(
    tx_symbols: np.ndarray,
    rx_symbols: np.ndarray,
    skip_initial: int = 0,
    skip_final: int = 0
) -> SERResult:
    """
    Calculate Symbol Error Rate.

    SER measures errors at symbol level (before bit mapping).
    For M-ary modulation, one symbol error may cause multiple bit errors.

    Args:
        tx_symbols: Transmitted symbol sequence
        rx_symbols: Received symbol sequence
        skip_initial: Skip first N symbols
        skip_final: Skip last N symbols

    Returns:
        SERResult with error statistics

    Example:
        >>> tx_syms = np.array([0, 1, 2, 3, 2, 1])
        >>> rx_syms = np.array([0, 1, 3, 3, 2, 1])  # Error at position 2
        >>> result = calculate_ser(tx_syms, rx_syms)
        >>> print(result)
        SER: 1.67e-01 (1/6 errors)
    """
    # Convert to numpy arrays
    tx_symbols = np.asarray(tx_symbols)
    rx_symbols = np.asarray(rx_symbols)

    # Handle length mismatch
    min_len = min(len(tx_symbols), len(rx_symbols))
    if len(tx_symbols) != len(rx_symbols):
        print(f"Warning: Length mismatch (TX: {len(tx_symbols)}, RX: {len(rx_symbols)})")
        tx_symbols = tx_symbols[:min_len]
        rx_symbols = rx_symbols[:min_len]

    # Apply skip parameters
    start_idx = skip_initial
    end_idx = len(tx_symbols) - skip_final

    if start_idx >= end_idx:
        raise ValueError("skip_initial + skip_final exceeds sequence length")

    tx_symbols = tx_symbols[start_idx:end_idx]
    rx_symbols = rx_symbols[start_idx:end_idx]

    # Find errors (handle both numeric and complex symbols)
    errors = tx_symbols != rx_symbols
    error_positions = np.where(errors)[0] + start_idx
    symbol_errors = np.sum(errors)
    total_symbols = len(tx_symbols)

    # Calculate SER
    ser = symbol_errors / total_symbols if total_symbols > 0 else 0.0

    return SERResult(
        symbol_errors=symbol_errors,
        total_symbols=total_symbols,
        ser=ser,
        error_positions=error_positions.tolist()
    )


def estimate_snr(
    signal: np.ndarray,
    noise: Optional[np.ndarray] = None,
    method: str = 'power'
) -> float:
    """
    Estimate Signal-to-Noise Ratio.

    Args:
        signal: Received signal with noise
        noise: Optional noise-only reference
        method: Estimation method:
               'power' - Compare signal power to noise power
               'variance' - Use signal variance
               'min-max' - Use min/max power ratio

    Returns:
        Estimated SNR in dB

    Example:
        >>> # With known noise
        >>> snr = estimate_snr(noisy_signal, noise_samples)
        >>>
        >>> # Without noise reference
        >>> snr = estimate_snr(noisy_signal, method='variance')
    """
    if noise is not None:
        # Direct measurement
        signal_power = np.mean(np.abs(signal) ** 2)
        noise_power = np.mean(np.abs(noise) ** 2)
        snr_linear = (signal_power - noise_power) / (noise_power + 1e-10)
        return 10 * np.log10(snr_linear + 1e-10)

    # Estimate from signal alone
    if method == 'power':
        signal_power = np.mean(np.abs(signal) ** 2)
        # Estimate noise as minimum power
        noise_estimate = np.percentile(np.abs(signal) ** 2, 10)  # 10th percentile
        snr_linear = signal_power / (noise_estimate + 1e-10)
    elif method == 'variance':
        # Use variance of magnitude
        mag = np.abs(signal)
        signal_estimate = np.mean(mag)
        noise_estimate = np.std(mag)
        snr_linear = (signal_estimate ** 2) / (noise_estimate ** 2 + 1e-10)
    elif method == 'min-max':
        power = np.abs(signal) ** 2
        signal_estimate = np.percentile(power, 90)  # 90th percentile
        noise_estimate = np.percentile(power, 10)   # 10th percentile
        snr_linear = signal_estimate / (noise_estimate + 1e-10)
    else:
        raise ValueError(f"Unknown method: {method}")

    return 10 * np.log10(snr_linear + 1e-10)


def measure_throughput(
    num_bits: int,
    duration_seconds: float
) -> Dict[str, float]:
    """
    Calculate throughput metrics.

    Args:
        num_bits: Number of bits processed
        duration_seconds: Processing time in seconds

    Returns:
        Dictionary with throughput metrics:
            - bits_per_second
            - characters_per_second (assuming 8 bits/char)
            - words_per_minute (assuming 50 chars/word)

    Example:
        >>> start = time.time()
        >>> decoded = decoder.decode(signal)
        >>> duration = time.time() - start
        >>> metrics = measure_throughput(len(decoded) * 8, duration)
        >>> print(f"Throughput: {metrics['words_per_minute']:.1f} WPM")
    """
    if duration_seconds <= 0:
        raise ValueError("Duration must be positive")

    bits_per_second = num_bits / duration_seconds
    chars_per_second = bits_per_second / 8
    words_per_minute = chars_per_second * 60 / 50  # 50 chars per word

    return {
        'bits_per_second': bits_per_second,
        'characters_per_second': chars_per_second,
        'words_per_minute': words_per_minute
    }


class PerformanceProfiler:
    """
    Profile decoder performance.

    Measures CPU time, memory usage, latency, and throughput.

    Example:
        >>> profiler = PerformanceProfiler()
        >>> profiler.start()
        >>> decoded = decoder.decode(signal)
        >>> stats = profiler.stop(num_samples=len(signal))
        >>> print(f"Processing rate: {stats['samples_per_second']:.0f} samples/sec")
        >>> print(f"Real-time factor: {stats['realtime_factor']:.1f}x")
    """

    def __init__(self):
        self.start_time = None
        self.end_time = None

    def start(self):
        """Start profiling."""
        self.start_time = time.perf_counter()

    def stop(
        self,
        num_samples: int,
        sample_rate: Optional[float] = None
    ) -> Dict[str, float]:
        """
        Stop profiling and return statistics.

        Args:
            num_samples: Number of samples processed
            sample_rate: Optional sample rate (Hz) for real-time factor calculation

        Returns:
            Dictionary with performance metrics
        """
        if self.start_time is None:
            raise RuntimeError("Profiler not started")

        self.end_time = time.perf_counter()
        duration = self.end_time - self.start_time

        stats = {
            'duration_seconds': duration,
            'samples_processed': num_samples,
            'samples_per_second': num_samples / duration if duration > 0 else 0
        }

        if sample_rate is not None:
            # Real-time factor: how many times faster than real-time
            # 1.0 = real-time, 10.0 = 10x faster than real-time
            signal_duration = num_samples / sample_rate
            stats['signal_duration_seconds'] = signal_duration
            stats['realtime_factor'] = signal_duration / duration if duration > 0 else 0

        return stats

    def reset(self):
        """Reset profiler state."""
        self.start_time = None
        self.end_time = None


def analyze_error_pattern(
    errors: np.ndarray,
    max_burst_gap: int = 5
) -> Dict[str, any]:
    """
    Analyze error pattern for burst vs random errors.

    Args:
        errors: Boolean array where True indicates error
        max_burst_gap: Maximum gap (in bits) within a burst

    Returns:
        Dictionary with error pattern analysis:
            - total_errors: Total number of errors
            - num_bursts: Number of error bursts
            - longest_burst: Length of longest burst
            - burst_lengths: List of all burst lengths
            - random_errors: Number of isolated errors

    Example:
        >>> tx = np.array([0,1,0,1,0,1,0,1,0,1])
        >>> rx = np.array([0,0,0,1,0,0,0,0,0,1])  # Errors at 1,5,6,7
        >>> errors = tx != rx
        >>> pattern = analyze_error_pattern(errors)
        >>> print(f"Bursts: {pattern['num_bursts']}")
        >>> print(f"Random: {pattern['random_errors']}")
    """
    error_positions = np.where(errors)[0]

    if len(error_positions) == 0:
        return {
            'total_errors': 0,
            'num_bursts': 0,
            'longest_burst': 0,
            'burst_lengths': [],
            'random_errors': 0
        }

    # Find bursts by grouping errors close together
    bursts = []
    current_burst = [error_positions[0]]

    for i in range(1, len(error_positions)):
        if error_positions[i] - error_positions[i-1] <= max_burst_gap:
            # Part of current burst
            current_burst.append(error_positions[i])
        else:
            # Start new burst
            bursts.append(current_burst)
            current_burst = [error_positions[i]]

    bursts.append(current_burst)

    # Analyze bursts
    burst_lengths = [len(b) for b in bursts]
    random_errors = sum(1 for length in burst_lengths if length == 1)

    return {
        'total_errors': len(error_positions),
        'num_bursts': len(bursts),
        'longest_burst': max(burst_lengths) if burst_lengths else 0,
        'burst_lengths': burst_lengths,
        'random_errors': random_errors
    }
