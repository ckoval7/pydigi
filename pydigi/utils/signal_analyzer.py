#!/usr/bin/env python3
"""
Standardized signal analysis tool for modem development and debugging.

This module provides comprehensive signal analysis capabilities including:
- Time-domain analysis (waveform, envelope, RMS)
- Frequency-domain analysis (spectrum, bandwidth, center frequency)
- Spectrogram (time-frequency representation)
- Phase analysis (instantaneous phase, phase transitions)
- Symbol timing and periodicity detection
- Signal comparison (our signals vs reference/fldigi signals)
- Statistical metrics (SNR, THD, etc.)
- Comprehensive visualization and reporting
"""

import numpy as np
from typing import Optional, Dict, List, Tuple, Union
from dataclasses import dataclass, field
from pathlib import Path
import wave


@dataclass
class SignalMetrics:
    """Container for signal analysis metrics."""
    # Time domain
    duration: float = 0.0
    num_samples: int = 0
    sample_rate: int = 8000
    peak_amplitude: float = 0.0
    rms: float = 0.0
    crest_factor: float = 0.0
    dc_offset: float = 0.0

    # Frequency domain
    peak_freq: float = 0.0
    center_freq: float = 0.0
    bandwidth_3db: float = 0.0
    bandwidth_10pct: float = 0.0
    spectral_centroid: float = 0.0

    # Phase
    phase_std: float = 0.0
    phase_transitions: int = 0

    # Periodicity
    detected_period: Optional[int] = None
    periodicity_strength: float = 0.0

    # Additional data
    extra: Dict = field(default_factory=dict)


class SignalAnalyzer:
    """
    Comprehensive signal analyzer for modem development.

    Usage:
        # Analyze a single signal
        analyzer = SignalAnalyzer(sample_rate=8000)
        metrics = analyzer.analyze(audio_data)
        analyzer.plot(save_path='analysis.png')

        # Compare two signals
        analyzer.compare(our_signal, reference_signal)
        analyzer.plot_comparison(save_path='comparison.png')
    """

    def __init__(self, sample_rate: int = 8000):
        """Initialize signal analyzer.

        Args:
            sample_rate: Sample rate in Hz (default: 8000)
        """
        self.sample_rate = sample_rate
        self.signal = None
        self.metrics = None
        self.comparison_signal = None
        self.comparison_metrics = None

    def analyze(self, signal: np.ndarray, label: str = "Signal") -> SignalMetrics:
        """Perform comprehensive signal analysis.

        Args:
            signal: Audio signal as numpy array
            label: Label for this signal

        Returns:
            SignalMetrics object with all computed metrics
        """
        self.signal = np.asarray(signal, dtype=float)
        metrics = SignalMetrics()

        # Basic time domain metrics
        metrics.num_samples = len(self.signal)
        metrics.duration = len(self.signal) / self.sample_rate
        metrics.sample_rate = self.sample_rate
        metrics.peak_amplitude = np.max(np.abs(self.signal))
        metrics.rms = np.sqrt(np.mean(self.signal**2))
        metrics.crest_factor = metrics.peak_amplitude / (metrics.rms + 1e-10)
        metrics.dc_offset = np.mean(self.signal)

        # Frequency domain analysis
        self._analyze_spectrum(metrics)

        # Phase analysis
        self._analyze_phase(metrics)

        # Periodicity detection
        self._detect_periodicity(metrics)

        self.metrics = metrics
        return metrics

    def _analyze_spectrum(self, metrics: SignalMetrics):
        """Analyze frequency spectrum."""
        # Compute FFT
        fft = np.fft.rfft(self.signal)
        freqs = np.fft.rfftfreq(len(self.signal), 1/self.sample_rate)
        magnitude = np.abs(fft)
        power = magnitude ** 2

        # Store for plotting
        metrics.extra['freqs'] = freqs
        metrics.extra['magnitude'] = magnitude
        metrics.extra['power'] = power

        # Find peak frequency
        peak_idx = np.argmax(magnitude)
        metrics.peak_freq = freqs[peak_idx]

        # Spectral centroid (center of mass)
        metrics.spectral_centroid = np.sum(freqs * magnitude) / (np.sum(magnitude) + 1e-10)
        metrics.center_freq = metrics.spectral_centroid

        # Bandwidth at -3dB (half power)
        half_power = 0.707 * magnitude[peak_idx]
        half_power_mask = magnitude > half_power
        if np.any(half_power_mask):
            half_power_freqs = freqs[half_power_mask]
            metrics.bandwidth_3db = half_power_freqs.max() - half_power_freqs.min()

        # Bandwidth at 10% of peak
        threshold = 0.1 * magnitude[peak_idx]
        active_mask = magnitude > threshold
        if np.any(active_mask):
            active_freqs = freqs[active_mask]
            metrics.bandwidth_10pct = active_freqs.max() - active_freqs.min()

    def _analyze_phase(self, metrics: SignalMetrics):
        """Analyze phase characteristics."""
        # Compute analytic signal using Hilbert transform
        try:
            from scipy.signal import hilbert
            analytic = hilbert(self.signal)
            instantaneous_phase = np.unwrap(np.angle(analytic))

            metrics.extra['instantaneous_phase'] = instantaneous_phase
            metrics.phase_std = np.std(np.diff(instantaneous_phase))

            # Count significant phase transitions (> 90 degrees)
            phase_diff = np.diff(instantaneous_phase)
            metrics.phase_transitions = np.sum(np.abs(phase_diff) > np.pi/2)
        except ImportError:
            # scipy not available, skip phase analysis
            pass

    def _detect_periodicity(self, metrics: SignalMetrics,
                           search_range: Tuple[int, int] = (50, 2000)):
        """Detect signal periodicity using autocorrelation.

        Args:
            metrics: SignalMetrics object to update
            search_range: (min_period, max_period) in samples
        """
        # Use autocorrelation to find periodicity
        signal_norm = self.signal - np.mean(self.signal)
        autocorr = np.correlate(signal_norm, signal_norm, mode='full')
        autocorr = autocorr[len(autocorr)//2:]  # Keep only positive lags

        # Normalize
        if autocorr[0] > 0:
            autocorr = autocorr / autocorr[0]

        metrics.extra['autocorr'] = autocorr

        # Search for peak in expected range
        min_period, max_period = search_range
        max_period = min(max_period, len(autocorr))

        if max_period > min_period:
            search_region = autocorr[min_period:max_period]
            if len(search_region) > 0:
                peak_idx = np.argmax(search_region)
                metrics.detected_period = min_period + peak_idx
                metrics.periodicity_strength = search_region[peak_idx]

    def analyze_windows(self, window_duration: float = 0.1) -> List[Dict]:
        """Analyze signal in time windows.

        Args:
            window_duration: Window duration in seconds

        Returns:
            List of dictionaries with per-window metrics
        """
        if self.signal is None:
            raise ValueError("No signal loaded. Call analyze() first.")

        window_size = int(window_duration * self.sample_rate)
        num_windows = len(self.signal) // window_size

        windows = []
        for i in range(num_windows):
            start = i * window_size
            end = start + window_size
            window = self.signal[start:end]

            window_metrics = {
                'window_idx': i,
                'start_time': start / self.sample_rate,
                'end_time': end / self.sample_rate,
                'rms': np.sqrt(np.mean(window**2)),
                'peak': np.max(np.abs(window)),
                'mean': np.mean(window),
            }
            windows.append(window_metrics)

        return windows

    def compare(self, signal1: np.ndarray, signal2: np.ndarray,
                label1: str = "Signal 1", label2: str = "Signal 2") -> Dict:
        """Compare two signals and compute difference metrics.

        Args:
            signal1: First signal (e.g., our generated signal)
            signal2: Second signal (e.g., reference signal)
            label1: Label for first signal
            label2: Label for second signal

        Returns:
            Dictionary with comparison metrics
        """
        # Analyze both signals
        metrics1 = self.analyze(signal1, label1)
        self.metrics = metrics1

        analyzer2 = SignalAnalyzer(self.sample_rate)
        metrics2 = analyzer2.analyze(signal2, label2)
        self.comparison_signal = signal2
        self.comparison_metrics = metrics2

        # Compute comparison metrics
        comparison = {
            'label1': label1,
            'label2': label2,
            'metrics1': metrics1,
            'metrics2': metrics2,
        }

        # RMS difference
        comparison['rms_ratio'] = metrics1.rms / (metrics2.rms + 1e-10)
        comparison['rms_diff_db'] = 20 * np.log10(comparison['rms_ratio'] + 1e-10)

        # Peak difference
        comparison['peak_ratio'] = metrics1.peak_amplitude / (metrics2.peak_amplitude + 1e-10)
        comparison['peak_diff_db'] = 20 * np.log10(comparison['peak_ratio'] + 1e-10)

        # Frequency error
        comparison['freq_error_hz'] = metrics1.peak_freq - metrics2.peak_freq
        comparison['freq_error_pct'] = 100 * comparison['freq_error_hz'] / (metrics2.peak_freq + 1e-10)

        # Period comparison
        if metrics1.detected_period and metrics2.detected_period:
            comparison['period_diff'] = metrics1.detected_period - metrics2.detected_period
            comparison['period_match'] = abs(comparison['period_diff']) < 10

        # Signal correlation (if same length)
        min_len = min(len(signal1), len(signal2))
        if min_len > 0:
            s1_norm = signal1[:min_len] - np.mean(signal1[:min_len])
            s2_norm = signal2[:min_len] - np.mean(signal2[:min_len])

            correlation = np.correlate(s1_norm, s2_norm, mode='valid')[0]
            norm1 = np.sqrt(np.sum(s1_norm**2))
            norm2 = np.sqrt(np.sum(s2_norm**2))
            comparison['correlation'] = correlation / (norm1 * norm2 + 1e-10)

        return comparison

    def load_wav(self, filepath: Union[str, Path]) -> np.ndarray:
        """Load audio from WAV file.

        Args:
            filepath: Path to WAV file

        Returns:
            Audio signal as float array normalized to [-1, 1]
        """
        filepath = Path(filepath)
        with wave.open(str(filepath), 'rb') as wf:
            sample_rate = wf.getframerate()
            num_frames = wf.getnframes()
            audio_bytes = wf.readframes(num_frames)

            # Convert to numpy array
            if wf.getsampwidth() == 2:  # 16-bit
                audio = np.frombuffer(audio_bytes, dtype=np.int16)
                audio = audio.astype(float) / 32768.0
            else:
                raise ValueError(f"Unsupported sample width: {wf.getsampwidth()}")

            if sample_rate != self.sample_rate:
                print(f"Warning: WAV file sample rate ({sample_rate}) differs from analyzer ({self.sample_rate})")
                self.sample_rate = sample_rate

            return audio

    def print_metrics(self, metrics: Optional[SignalMetrics] = None):
        """Print comprehensive metrics report.

        Args:
            metrics: SignalMetrics to print (default: self.metrics)
        """
        if metrics is None:
            metrics = self.metrics

        if metrics is None:
            print("No metrics available. Call analyze() first.")
            return

        print("=" * 70)
        print("SIGNAL ANALYSIS REPORT")
        print("=" * 70)

        print("\nTIME DOMAIN")
        print("-" * 70)
        print(f"Duration:        {metrics.duration:.3f} seconds ({metrics.num_samples} samples)")
        print(f"Sample Rate:     {metrics.sample_rate} Hz")
        print(f"Peak Amplitude:  {metrics.peak_amplitude:.6f}")
        print(f"RMS:             {metrics.rms:.6f}")
        print(f"Crest Factor:    {metrics.crest_factor:.2f} ({20*np.log10(metrics.crest_factor):.1f} dB)")
        print(f"DC Offset:       {metrics.dc_offset:.6f}")

        print("\nFREQUENCY DOMAIN")
        print("-" * 70)
        print(f"Peak Frequency:     {metrics.peak_freq:.2f} Hz")
        print(f"Spectral Centroid:  {metrics.spectral_centroid:.2f} Hz")
        print(f"Bandwidth (-3dB):   {metrics.bandwidth_3db:.2f} Hz")
        print(f"Bandwidth (10%):    {metrics.bandwidth_10pct:.2f} Hz")

        if 'instantaneous_phase' in metrics.extra:
            print("\nPHASE ANALYSIS")
            print("-" * 70)
            print(f"Phase Std Dev:      {metrics.phase_std:.4f} rad")
            print(f"Phase Transitions:  {metrics.phase_transitions}")

        if metrics.detected_period:
            print("\nPERIODICITY")
            print("-" * 70)
            print(f"Detected Period:    {metrics.detected_period} samples ({metrics.detected_period/metrics.sample_rate*1000:.2f} ms)")
            print(f"Periodicity Strength: {metrics.periodicity_strength:.3f}")

        print("=" * 70)

    def print_comparison(self, comparison: Dict):
        """Print comparison report.

        Args:
            comparison: Comparison dictionary from compare()
        """
        print("=" * 70)
        print("SIGNAL COMPARISON REPORT")
        print("=" * 70)
        print(f"\n{comparison['label1']} vs {comparison['label2']}")

        print("\nAMPLITUDE")
        print("-" * 70)
        print(f"RMS Ratio:    {comparison['rms_ratio']:.4f} ({comparison['rms_diff_db']:+.2f} dB)")
        print(f"Peak Ratio:   {comparison['peak_ratio']:.4f} ({comparison['peak_diff_db']:+.2f} dB)")

        print("\nFREQUENCY")
        print("-" * 70)
        print(f"Peak Freq Error:  {comparison['freq_error_hz']:+.2f} Hz ({comparison['freq_error_pct']:+.2f}%)")

        if 'period_diff' in comparison:
            print("\nPERIODICITY")
            print("-" * 70)
            print(f"Period Difference: {comparison['period_diff']} samples")
            print(f"Periods Match:     {'YES' if comparison['period_match'] else 'NO'}")

        if 'correlation' in comparison:
            print("\nCORRELATION")
            print("-" * 70)
            print(f"Normalized Correlation: {comparison['correlation']:.4f}")

        print("=" * 70)

    def plot(self, save_path: Optional[str] = None, show: bool = False):
        """Generate comprehensive visualization plots.

        Args:
            save_path: Path to save figure (default: display only)
            show: Whether to display the plot interactively
        """
        if self.signal is None or self.metrics is None:
            print("No signal to plot. Call analyze() first.")
            return

        try:
            import matplotlib
            if not show:
                matplotlib.use('Agg')
            import matplotlib.pyplot as plt
        except ImportError:
            print("Matplotlib not available for plotting")
            return

        fig = plt.figure(figsize=(14, 10))
        gs = fig.add_gridspec(3, 2, hspace=0.3, wspace=0.3)

        # Time domain waveform
        ax1 = fig.add_subplot(gs[0, :])
        t = np.arange(len(self.signal)) / self.sample_rate
        ax1.plot(t, self.signal, linewidth=0.5, alpha=0.8)
        ax1.set_xlabel('Time (s)')
        ax1.set_ylabel('Amplitude')
        ax1.set_title('Time Domain Waveform')
        ax1.grid(True, alpha=0.3)
        ax1.axhline(0, color='k', linewidth=0.5)

        # Spectrum
        ax2 = fig.add_subplot(gs[1, 0])
        freqs = self.metrics.extra.get('freqs', [])
        magnitude = self.metrics.extra.get('magnitude', [])
        if len(freqs) > 0:
            magnitude_db = 20 * np.log10(magnitude + 1e-10)
            ax2.plot(freqs, magnitude_db, linewidth=0.8)
            ax2.axvline(self.metrics.peak_freq, color='r', linestyle='--',
                       label=f'Peak: {self.metrics.peak_freq:.1f} Hz', linewidth=1.5)
            ax2.set_xlabel('Frequency (Hz)')
            ax2.set_ylabel('Magnitude (dB)')
            ax2.set_title('Frequency Spectrum')
            ax2.grid(True, alpha=0.3)
            ax2.legend()
            ax2.set_xlim(0, self.sample_rate / 2)

        # Spectrogram
        ax3 = fig.add_subplot(gs[1, 1])
        # Use shorter duration for spectrogram if signal is very long
        spec_duration = min(2.0, self.metrics.duration)
        spec_samples = int(spec_duration * self.sample_rate)
        ax3.specgram(self.signal[:spec_samples], NFFT=512, Fs=self.sample_rate,
                     cmap='viridis', scale='dB')
        ax3.set_xlabel('Time (s)')
        ax3.set_ylabel('Frequency (Hz)')
        ax3.set_title(f'Spectrogram (first {spec_duration:.1f}s)')
        ax3.set_ylim(0, min(3000, self.sample_rate/2))

        # Autocorrelation (periodicity)
        ax4 = fig.add_subplot(gs[2, 0])
        autocorr = self.metrics.extra.get('autocorr', [])
        if len(autocorr) > 0:
            # Plot first 2000 lags
            lags = np.arange(min(2000, len(autocorr)))
            ax4.plot(lags, autocorr[:len(lags)], linewidth=0.8)
            if self.metrics.detected_period:
                ax4.axvline(self.metrics.detected_period, color='r', linestyle='--',
                           label=f'Period: {self.metrics.detected_period} samples', linewidth=1.5)
            ax4.set_xlabel('Lag (samples)')
            ax4.set_ylabel('Autocorrelation')
            ax4.set_title('Autocorrelation (Periodicity Detection)')
            ax4.grid(True, alpha=0.3)
            if self.metrics.detected_period:
                ax4.legend()

        # RMS over time
        ax5 = fig.add_subplot(gs[2, 1])
        windows = self.analyze_windows(window_duration=0.1)
        times = [w['start_time'] for w in windows]
        rms_values = [w['rms'] for w in windows]
        ax5.plot(times, rms_values, linewidth=1.5, marker='o', markersize=3)
        ax5.set_xlabel('Time (s)')
        ax5.set_ylabel('RMS')
        ax5.set_title('RMS over Time (100ms windows)')
        ax5.grid(True, alpha=0.3)

        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
            print(f"Plot saved to {save_path}")

        if show:
            plt.show()
        else:
            plt.close()

    def plot_comparison(self, save_path: Optional[str] = None, show: bool = False,
                       duration: float = 1.0):
        """Generate comparison visualization.

        Args:
            save_path: Path to save figure (default: display only)
            show: Whether to display the plot interactively
            duration: Duration in seconds to plot (default: 1.0)
        """
        if self.signal is None or self.comparison_signal is None:
            print("No signals to compare. Call compare() first.")
            return

        try:
            import matplotlib
            if not show:
                matplotlib.use('Agg')
            import matplotlib.pyplot as plt
        except ImportError:
            print("Matplotlib not available for plotting")
            return

        fig, axes = plt.subplots(4, 2, figsize=(14, 12))

        samples = int(duration * self.sample_rate)
        t = np.arange(min(samples, len(self.signal))) / self.sample_rate

        # Time domain comparison
        axes[0, 0].plot(t, self.signal[:len(t)], alpha=0.7, label='Signal 1', linewidth=0.8)
        axes[0, 0].set_title('Signal 1 - Time Domain')
        axes[0, 0].set_xlabel('Time (s)')
        axes[0, 0].set_ylabel('Amplitude')
        axes[0, 0].grid(True, alpha=0.3)
        axes[0, 0].legend()

        t2 = np.arange(min(samples, len(self.comparison_signal))) / self.sample_rate
        axes[0, 1].plot(t2, self.comparison_signal[:len(t2)], alpha=0.7,
                       label='Signal 2', color='orange', linewidth=0.8)
        axes[0, 1].set_title('Signal 2 - Time Domain')
        axes[0, 1].set_xlabel('Time (s)')
        axes[0, 1].set_ylabel('Amplitude')
        axes[0, 1].grid(True, alpha=0.3)
        axes[0, 1].legend()

        # Spectrum comparison
        freqs1 = self.metrics.extra.get('freqs', [])
        mag1 = self.metrics.extra.get('magnitude', [])
        freqs2 = self.comparison_metrics.extra.get('freqs', [])
        mag2 = self.comparison_metrics.extra.get('magnitude', [])

        if len(freqs1) > 0 and len(freqs2) > 0:
            axes[1, 0].plot(freqs1, 20*np.log10(mag1 + 1e-10), label='Signal 1', linewidth=0.8)
            axes[1, 0].plot(freqs2, 20*np.log10(mag2 + 1e-10), label='Signal 2',
                           alpha=0.7, linewidth=0.8)
            axes[1, 0].set_title('Spectrum Overlay')
            axes[1, 0].set_xlabel('Frequency (Hz)')
            axes[1, 0].set_ylabel('Magnitude (dB)')
            axes[1, 0].grid(True, alpha=0.3)
            axes[1, 0].legend()
            axes[1, 0].set_xlim(0, self.sample_rate / 2)

            # Spectrum difference
            if len(mag1) == len(mag2):
                diff_db = 20*np.log10(mag1 + 1e-10) - 20*np.log10(mag2 + 1e-10)
                axes[1, 1].plot(freqs1, diff_db, linewidth=0.8, color='red')
                axes[1, 1].axhline(0, color='k', linestyle='--', linewidth=0.5)
                axes[1, 1].set_title('Spectrum Difference (Signal1 - Signal2)')
                axes[1, 1].set_xlabel('Frequency (Hz)')
                axes[1, 1].set_ylabel('Difference (dB)')
                axes[1, 1].grid(True, alpha=0.3)
                axes[1, 1].set_xlim(0, self.sample_rate / 2)

        # Spectrograms
        spec_samples = min(int(2.0 * self.sample_rate), len(self.signal))
        axes[2, 0].specgram(self.signal[:spec_samples], NFFT=512,
                           Fs=self.sample_rate, cmap='viridis')
        axes[2, 0].set_title('Signal 1 - Spectrogram')
        axes[2, 0].set_ylabel('Frequency (Hz)')
        axes[2, 0].set_ylim(0, min(3000, self.sample_rate/2))

        spec_samples2 = min(int(2.0 * self.sample_rate), len(self.comparison_signal))
        axes[2, 1].specgram(self.comparison_signal[:spec_samples2], NFFT=512,
                           Fs=self.sample_rate, cmap='viridis')
        axes[2, 1].set_title('Signal 2 - Spectrogram')
        axes[2, 1].set_ylabel('Frequency (Hz)')
        axes[2, 1].set_ylim(0, min(3000, self.sample_rate/2))

        # RMS comparison
        windows1 = self.analyze_windows(window_duration=0.1)

        # Temporarily switch signal for window analysis
        temp_signal = self.signal
        self.signal = self.comparison_signal
        windows2 = self.analyze_windows(window_duration=0.1)
        self.signal = temp_signal

        times1 = [w['start_time'] for w in windows1]
        rms1 = [w['rms'] for w in windows1]
        times2 = [w['start_time'] for w in windows2]
        rms2 = [w['rms'] for w in windows2]

        axes[3, 0].plot(times1, rms1, label='Signal 1', marker='o', markersize=3)
        axes[3, 0].plot(times2, rms2, label='Signal 2', marker='s', markersize=3, alpha=0.7)
        axes[3, 0].set_title('RMS Comparison (100ms windows)')
        axes[3, 0].set_xlabel('Time (s)')
        axes[3, 0].set_ylabel('RMS')
        axes[3, 0].grid(True, alpha=0.3)
        axes[3, 0].legend()

        # RMS ratio over time
        min_windows = min(len(rms1), len(rms2))
        ratio = [rms1[i] / (rms2[i] + 1e-10) for i in range(min_windows)]
        axes[3, 1].plot(times1[:min_windows], ratio, linewidth=1.5, color='purple')
        axes[3, 1].axhline(1.0, color='k', linestyle='--', linewidth=0.5)
        axes[3, 1].set_title('RMS Ratio (Signal1 / Signal2)')
        axes[3, 1].set_xlabel('Time (s)')
        axes[3, 1].set_ylabel('Ratio')
        axes[3, 1].grid(True, alpha=0.3)

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
            print(f"Comparison plot saved to {save_path}")

        if show:
            plt.show()
        else:
            plt.close()


# Convenience functions for quick analysis
def quick_analyze(signal: np.ndarray, sample_rate: int = 8000,
                 plot: bool = True, plot_path: str = 'signal_analysis.png') -> SignalMetrics:
    """Quick analysis of a signal with optional plotting.

    Args:
        signal: Audio signal to analyze
        sample_rate: Sample rate in Hz
        plot: Whether to generate plots
        plot_path: Path to save plot

    Returns:
        SignalMetrics object
    """
    analyzer = SignalAnalyzer(sample_rate)
    metrics = analyzer.analyze(signal)
    analyzer.print_metrics()

    if plot:
        analyzer.plot(save_path=plot_path)

    return metrics


def quick_compare(signal1: np.ndarray, signal2: np.ndarray,
                 label1: str = "Our Signal", label2: str = "Reference",
                 sample_rate: int = 8000, plot: bool = True,
                 plot_path: str = 'signal_comparison.png') -> Dict:
    """Quick comparison of two signals with optional plotting.

    Args:
        signal1: First signal (e.g., our generated signal)
        signal2: Second signal (e.g., reference/fldigi signal)
        label1: Label for first signal
        label2: Label for second signal
        sample_rate: Sample rate in Hz
        plot: Whether to generate plots
        plot_path: Path to save plot

    Returns:
        Comparison dictionary
    """
    analyzer = SignalAnalyzer(sample_rate)
    comparison = analyzer.compare(signal1, signal2, label1, label2)
    analyzer.print_comparison(comparison)

    if plot:
        analyzer.plot_comparison(save_path=plot_path)

    return comparison


def compare_with_fldigi(our_signal: np.ndarray, fldigi_wav_path: str,
                       sample_rate: int = 8000, plot_path: str = 'fldigi_comparison.png'):
    """Compare our generated signal with fldigi WAV file.

    Args:
        our_signal: Our generated signal
        fldigi_wav_path: Path to fldigi-generated WAV file
        sample_rate: Sample rate in Hz
        plot_path: Path to save comparison plot
    """
    analyzer = SignalAnalyzer(sample_rate)
    fldigi_signal = analyzer.load_wav(fldigi_wav_path)

    comparison = analyzer.compare(our_signal, fldigi_signal,
                                  "PyDigi", "fldigi")
    analyzer.print_comparison(comparison)
    analyzer.plot_comparison(save_path=plot_path)

    return comparison
