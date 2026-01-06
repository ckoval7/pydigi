"""Utility modules for pydigi."""

from .signal_analyzer import (
    SignalAnalyzer,
    SignalMetrics,
    quick_analyze,
    quick_compare,
    compare_with_fldigi,
)
from .resampler import (
    resample,
    resample_to_48k,
    resample_from_modem,
    resample_preset,
    compute_resampled_length,
    get_resampling_info,
    COMMON_CONVERSIONS,
)
from .signal_trimmer import (
    SignalTrimmer,
    TrimResult,
)
from .noise import (
    add_awgn,
    add_frequency_offset,
    add_phase_noise,
    add_timing_jitter,
    add_multipath_fading,
    calculate_signal_power,
    db_to_linear,
    linear_to_db,
    estimate_snr,
)
from .measurements import (
    BERResult,
    SERResult,
    calculate_ber,
    calculate_ser,
    estimate_snr as measure_snr,
    measure_throughput,
    PerformanceProfiler,
    analyze_error_pattern,
)

__all__ = [
    "SignalAnalyzer",
    "SignalMetrics",
    "quick_analyze",
    "quick_compare",
    "compare_with_fldigi",
    "resample",
    "resample_to_48k",
    "resample_from_modem",
    "resample_preset",
    "compute_resampled_length",
    "get_resampling_info",
    "COMMON_CONVERSIONS",
    "SignalTrimmer",
    "TrimResult",
    # Noise generation
    "add_awgn",
    "add_frequency_offset",
    "add_phase_noise",
    "add_timing_jitter",
    "add_multipath_fading",
    "calculate_signal_power",
    "db_to_linear",
    "linear_to_db",
    "estimate_snr",
    # Measurements
    "BERResult",
    "SERResult",
    "calculate_ber",
    "calculate_ser",
    "measure_snr",
    "measure_throughput",
    "PerformanceProfiler",
    "analyze_error_pattern",
]
