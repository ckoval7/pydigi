"""Base modem class for pydigi.

This module provides the abstract base class for all modem implementations in pydigi.
All digital mode modems (PSK, RTTY, MT63, etc.) inherit from the Modem class defined here.

The base class provides:
    - Common initialization and state management
    - Frequency and sample rate control
    - Abstract methods for transmission (tx_init, tx_process)
    - High-level modulate() API for text-to-audio conversion

Based on fldigi's modem.h interface.

Example:
    Creating a new modem implementation::

        from pydigi.modems.base import Modem
        import numpy as np

        class MyModem(Modem):
            def __init__(self, sample_rate=8000, frequency=1000):
                super().__init__("MyModem", sample_rate, frequency)

            def tx_init(self):
                # Initialize transmitter state
                pass

            def tx_process(self, text: str) -> np.ndarray:
                # Generate audio from text
                return np.array([], dtype=np.float32)

Attributes:
    OUTBUFSIZE (int): Size of output buffer (65536 samples)
"""

from abc import ABC, abstractmethod
import numpy as np
from typing import Optional


# Constants from fldigi/src/include/modem.h
OUTBUFSIZE = 65536  # Output buffer size


class Modem(ABC):
    """
    Abstract base class for all modems.

    This class defines the interface that all modem implementations must follow.
    It provides common functionality for frequency control, sample rate management,
    and output buffering.

    Attributes:
        mode_name: Name of the modem mode (e.g., "CW", "RTTY", "PSK31")
        sample_rate: Sample rate in Hz (default: 8000)
        frequency: Transmit/receive frequency in Hz (audio frequency, not RF)
        bandwidth: Signal bandwidth in Hz

    Based on fldigi/src/include/modem.h
    """

    def __init__(
        self,
        mode_name: str,
        sample_rate: float = 8000.0,
        frequency: float = 1000.0
    ):
        """
        Initialize the base modem.

        Args:
            mode_name: Name of the modem mode
            sample_rate: Sample rate in Hz (default: 8000)
            frequency: Center frequency in Hz (default: 1000)
        """
        self.mode_name = mode_name
        self.sample_rate = sample_rate
        self._frequency = frequency
        self._bandwidth = 0.0  # To be set by derived classes

        # Output buffer
        self.output_buffer = np.zeros(OUTBUFSIZE, dtype=np.float64)
        self.output_ptr = 0

        # Transmission state
        self._tx_initialized = False

    @property
    def frequency(self) -> float:
        """Get the current frequency in Hz."""
        return self._frequency

    @frequency.setter
    def frequency(self, freq: float) -> None:
        """
        Set the frequency.

        Args:
            freq: Frequency in Hz
        """
        self._frequency = freq

    @property
    def bandwidth(self) -> float:
        """Get the signal bandwidth in Hz."""
        return self._bandwidth

    @abstractmethod
    def tx_init(self) -> None:
        """
        Initialize the transmitter.

        This method should set up any modem-specific state needed for transmission.
        Must be implemented by derived classes.
        """
        pass

    @abstractmethod
    def tx_process(self, text: str) -> np.ndarray:
        """
        Process text and generate modulated audio samples.

        This is the core transmission method that converts text to audio.
        Must be implemented by derived classes.

        Args:
            text: Text string to transmit

        Returns:
            Array of float audio samples in range [-1.0, 1.0]
        """
        pass

    def modulate(
        self,
        text: str,
        frequency: Optional[float] = None,
        sample_rate: Optional[float] = None
    ) -> np.ndarray:
        """
        High-level API: Modulate text to audio samples.

        This is the main public interface for using a modem.

        Args:
            text: Text string to transmit
            frequency: Frequency in Hz (default: use modem's current frequency)
            sample_rate: Sample rate in Hz (default: use modem's current sample rate)

        Returns:
            Array of float audio samples in range [-1.0, 1.0]

        Example:
            >>> modem = CW()
            >>> audio = modem.modulate("HELLO", frequency=800, sample_rate=8000)
            >>> # audio is now a numpy array that can be saved to WAV or used with GNU Radio
        """
        # Store original values
        original_freq = self.frequency
        original_sr = self.sample_rate

        # Apply overrides if provided
        if frequency is not None:
            self.frequency = frequency
        if sample_rate is not None:
            self.sample_rate = sample_rate

        # Initialize and process
        self.tx_init()
        audio = self.tx_process(text)

        # Restore original values
        self.frequency = original_freq
        self.sample_rate = original_sr

        # Ensure output is in proper range
        # Normalize if peak exceeds 1.0
        peak = np.max(np.abs(audio))
        if peak > 1.0:
            audio = audio / peak

        return audio

    def reset(self) -> None:
        """
        Reset the modem state.

        Clears buffers and reinitializes for a fresh transmission.
        """
        self.output_buffer.fill(0.0)
        self.output_ptr = 0
        self._tx_initialized = False

    def __str__(self) -> str:
        """String representation of the modem."""
        return (f"{self.mode_name} Modem "
                f"(freq={self.frequency:.1f} Hz, "
                f"sr={self.sample_rate:.0f} Hz, "
                f"bw={self.bandwidth:.1f} Hz)")

    def __repr__(self) -> str:
        """Detailed representation of the modem."""
        return (f"{self.__class__.__name__}("
                f"mode_name='{self.mode_name}', "
                f"sample_rate={self.sample_rate}, "
                f"frequency={self.frequency})")
