"""Real-time audio I/O using sounddevice.

This module provides real-time audio input/output capabilities for streaming
audio to and from sound cards, enabling live modem operations.
"""

import numpy as np
import sounddevice as sd
from typing import Callable, Optional, List, Dict, Any
from collections import deque
import threading


def list_devices() -> List[Dict[str, Any]]:
    """List all available audio devices.

    Returns:
        List of device info dictionaries with keys:
        - name: Device name
        - index: Device index
        - hostapi: Host API index
        - max_input_channels: Maximum input channels
        - max_output_channels: Maximum output channels
        - default_samplerate: Default sample rate
    """
    devices = sd.query_devices()
    if isinstance(devices, dict):
        # Single device
        return [devices]
    return list(devices)


def get_default_input_device() -> Optional[int]:
    """Get default input device index.

    Returns:
        Device index or None if no input device available
    """
    try:
        return sd.default.device[0]  # Input device
    except (AttributeError, IndexError):
        return None


def get_default_output_device() -> Optional[int]:
    """Get default output device index.

    Returns:
        Device index or None if no output device available
    """
    try:
        return sd.default.device[1]  # Output device
    except (AttributeError, IndexError):
        return None


class AudioDevice:
    """Real-time audio device for input and output streaming.

    This class provides bidirectional audio I/O with buffering and callback
    support. It handles timing mismatches through ring buffering and queue
    management.

    Example:
        >>> def on_audio(samples):
        ...     print(f"Received {len(samples)} samples")
        >>>
        >>> device = AudioDevice(sample_rate=8000)
        >>> device.start_input(on_audio)
        >>> # Audio will be delivered to on_audio callback
        >>> device.stop()
    """

    def __init__(
        self,
        sample_rate: int = 8000,
        channels: int = 1,
        input_device: Optional[int] = None,
        output_device: Optional[int] = None,
        blocksize: int = 512,
    ):
        """Initialize audio device.

        Args:
            sample_rate: Sample rate in Hz (default 8000)
            channels: Number of audio channels (default 1 for mono)
            input_device: Input device index (None = default)
            output_device: Output device index (None = default)
            blocksize: Audio block size in samples (affects latency)
        """
        self.sample_rate = sample_rate
        self.channels = channels
        self.blocksize = blocksize

        # Device selection
        self.input_device = input_device if input_device is not None else get_default_input_device()
        self.output_device = output_device if output_device is not None else get_default_output_device()

        # Streams
        self._input_stream: Optional[sd.InputStream] = None
        self._output_stream: Optional[sd.OutputStream] = None

        # Callbacks
        self._input_callback: Optional[Callable[[np.ndarray], None]] = None

        # Input ring buffer (protects against timing jitter)
        self._input_buffer = deque(maxlen=sample_rate * 5)  # 5 seconds max
        self._input_lock = threading.Lock()

        # Output queue (FIFO for transmit samples)
        self._output_queue = deque()
        self._output_lock = threading.Lock()

        # Statistics
        self.input_overruns = 0
        self.output_underruns = 0

    def start_input(self, callback: Callable[[np.ndarray], None]) -> None:
        """Start audio input stream.

        Args:
            callback: Function called with numpy array of audio samples.
                     Signature: callback(samples: np.ndarray) -> None
                     Samples are float32 in range [-1.0, 1.0]

        Raises:
            RuntimeError: If input stream is already running
            sd.PortAudioError: If audio device cannot be opened
        """
        if self._input_stream is not None and self._input_stream.active:
            raise RuntimeError("Input stream already running")

        self._input_callback = callback

        def _stream_callback(indata, frames, time, status):
            """Internal callback for sounddevice input stream."""
            if status:
                # Log buffer under/overrun issues
                if status.input_overflow:
                    self.input_overruns += 1

            # Copy samples (indata is 2D: [frames, channels])
            samples = indata[:, 0] if self.channels == 1 else indata

            # Add to ring buffer
            with self._input_lock:
                self._input_buffer.extend(samples)

            # Deliver to user callback
            if self._input_callback:
                try:
                    self._input_callback(samples.copy())
                except Exception as e:
                    print(f"Error in input callback: {e}")

        # Open input stream
        self._input_stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            device=self.input_device,
            blocksize=self.blocksize,
            callback=_stream_callback,
            dtype=np.float32,
        )

        self._input_stream.start()

    def start_output(self) -> None:
        """Start audio output stream.

        Output audio is queued via write_output() and played continuously.
        If the queue is empty, silence is output (preventing underruns).

        Raises:
            RuntimeError: If output stream is already running
            sd.PortAudioError: If audio device cannot be opened
        """
        if self._output_stream is not None and self._output_stream.active:
            raise RuntimeError("Output stream already running")

        def _stream_callback(outdata, frames, time, status):
            """Internal callback for sounddevice output stream."""
            if status:
                # Log buffer under/overrun issues
                if status.output_underflow:
                    self.output_underruns += 1

            # Get samples from queue
            with self._output_lock:
                available = len(self._output_queue)
                if available >= frames:
                    # Enough samples in queue
                    for i in range(frames):
                        outdata[i] = self._output_queue.popleft()
                else:
                    # Not enough samples - output what we have + silence
                    for i in range(available):
                        outdata[i] = self._output_queue.popleft()
                    for i in range(available, frames):
                        outdata[i] = 0.0  # Silence

        # Open output stream
        self._output_stream = sd.OutputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            device=self.output_device,
            blocksize=self.blocksize,
            callback=_stream_callback,
            dtype=np.float32,
        )

        self._output_stream.start()

    def write_output(self, samples: np.ndarray) -> None:
        """Queue audio samples for output.

        Samples are added to the output queue and will be played by the
        output stream. If the stream is not running, samples are queued
        and will play when start_output() is called.

        Args:
            samples: Audio samples as numpy array (float32, [-1.0, 1.0])
                    Can be 1D array for mono or 2D array for multi-channel

        Example:
            >>> device = AudioDevice()
            >>> device.start_output()
            >>> # Generate 1 second of 1000 Hz tone
            >>> t = np.linspace(0, 1, 8000)
            >>> tone = np.sin(2 * np.pi * 1000 * t)
            >>> device.write_output(tone)
        """
        # Ensure 1D array for mono
        if samples.ndim == 2 and self.channels == 1:
            samples = samples[:, 0]

        # Add to output queue
        with self._output_lock:
            self._output_queue.extend(samples)

    def get_input_buffer_size(self) -> int:
        """Get current input buffer size in samples.

        Returns:
            Number of samples in input ring buffer
        """
        with self._input_lock:
            return len(self._input_buffer)

    def get_output_queue_size(self) -> int:
        """Get current output queue size in samples.

        Returns:
            Number of samples waiting to be played
        """
        with self._output_lock:
            return len(self._output_queue)

    def clear_output_queue(self) -> None:
        """Clear all samples from output queue.

        This stops current transmission and allows immediate queuing
        of new samples without waiting for existing queue to drain.
        """
        with self._output_lock:
            self._output_queue.clear()

    def stop(self) -> None:
        """Stop all active streams.

        This stops both input and output streams and clears buffers.
        The device can be restarted by calling start_input() and/or
        start_output() again.
        """
        # Stop input stream
        if self._input_stream is not None:
            try:
                self._input_stream.stop()
                self._input_stream.close()
            except Exception:
                pass
            finally:
                self._input_stream = None

        # Stop output stream
        if self._output_stream is not None:
            try:
                self._output_stream.stop()
                self._output_stream.close()
            except Exception:
                pass
            finally:
                self._output_stream = None

        # Clear buffers
        with self._input_lock:
            self._input_buffer.clear()

        with self._output_lock:
            self._output_queue.clear()

    def is_input_active(self) -> bool:
        """Check if input stream is active.

        Returns:
            True if input stream is running
        """
        return self._input_stream is not None and self._input_stream.active

    def is_output_active(self) -> bool:
        """Check if output stream is active.

        Returns:
            True if output stream is running
        """
        return self._output_stream is not None and self._output_stream.active

    def __del__(self):
        """Cleanup streams on deletion."""
        self.stop()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop()
        return False
