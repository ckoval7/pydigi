"""ARQ-to-Audio bridge for real-time ARQ over radio.

This module connects ARQ protocol to PSK modems and audio I/O,
enabling real-time ARQ communication over audio links.
"""

import numpy as np
from typing import Optional
from collections import deque
import time

from .protocol import ARQProtocol
from .frame_extractor import FrameExtractor
from ..modems.psk import PSK
from ..modems.psk_decoder import PSKDecoder
from ..utils.audio_io import AudioDevice


class ARQAudioBridge:
    """Bridge ARQ protocol to audio I/O via PSK modem.

    This class integrates:
    - TX path: ARQ frames → PSK modulation → audio output
    - RX path: audio input → PSK demodulation → frame extraction → ARQ

    Supports both real audio devices and in-memory loopback for testing.

    Example (loopback mode):
        >>> arq = ARQProtocol()
        >>> arq.config.my_call = "W1ABC"
        >>> bridge = ARQAudioBridge(arq, modem_baud=125, loopback_mode=True)
        >>> bridge.start()
        >>> # ARQ protocol now communicates via audio
    """

    def __init__(
        self,
        arq_protocol: ARQProtocol,
        modem_baud: float = 125,
        carrier_freq: float = 1000,
        sample_rate: int = 8000,
        audio_device: Optional[AudioDevice] = None,
        loopback_mode: bool = False,
        inter_frame_gap_ms: float = 100,
        debug: bool = False,
    ):
        """Initialize ARQ audio bridge.

        Args:
            arq_protocol: ARQ protocol instance to bridge
            modem_baud: PSK baud rate (31.25, 63, 125, 250, 500)
            carrier_freq: Audio carrier frequency in Hz
            sample_rate: Audio sample rate in Hz
            audio_device: Audio device for I/O (None = create default)
            loopback_mode: Enable in-memory loopback (for testing)
            inter_frame_gap_ms: Silence between frames in milliseconds
            debug: Enable debug output
        """
        self.arq = arq_protocol
        self.modem_baud = modem_baud
        self.carrier_freq = carrier_freq
        self.sample_rate = sample_rate
        self.loopback_mode = loopback_mode
        self.inter_frame_gap_ms = inter_frame_gap_ms
        self.debug = debug

        # Audio device
        if loopback_mode:
            self.audio_device = None  # No real audio in loopback mode
        else:
            self.audio_device = audio_device or AudioDevice(sample_rate=sample_rate)

        # PSK modem (TX)
        self.psk_encoder = PSK(baud=modem_baud, sample_rate=sample_rate)

        # PSK decoder (RX)
        self.psk_decoder = PSKDecoder(
            baud=modem_baud,
            sample_rate=sample_rate,
            frequency=carrier_freq
        )

        # Frame extractor (RX path: decoder chars → ARQ frames)
        self.frame_extractor = FrameExtractor(
            frame_callback=self._on_frame_extracted,
            debug=debug
        )

        # Connect decoder to frame extractor
        self.psk_decoder.set_text_callback(self.frame_extractor.process_char)

        # TX queue (frames waiting to be transmitted)
        self._tx_queue = deque()

        # Loopback connection (for in-memory testing)
        self._loopback_peer: Optional['ARQAudioBridge'] = None

        # State
        self._running = False

        # Statistics
        self.frames_sent = 0
        self.frames_received = 0
        self.audio_samples_tx = 0
        self.audio_samples_rx = 0

    def start(self) -> None:
        """Start audio streams and connect to ARQ protocol.

        This:
        1. Registers callback with ARQ protocol for outgoing frames
        2. Starts audio input/output streams (if not loopback mode)
        3. Begins processing loop
        """
        if self._running:
            return

        # Connect ARQ protocol TX callback
        self.arq.set_send_callback(self._on_arq_send)

        # Start audio streams (unless loopback mode)
        if not self.loopback_mode and self.audio_device:
            self.audio_device.start_input(self._on_audio_rx)
            self.audio_device.start_output()

        self._running = True

        if self.debug:
            print(f"[Bridge] Started (loopback={self.loopback_mode})")

    def stop(self) -> None:
        """Stop audio streams and disconnect."""
        if not self._running:
            return

        # Stop audio streams
        if not self.loopback_mode and self.audio_device:
            self.audio_device.stop()

        self._running = False

        if self.debug:
            print("[Bridge] Stopped")

    def connect_loopback(self, other_bridge: 'ARQAudioBridge') -> None:
        """Connect to another bridge for in-memory loopback testing.

        This creates a bidirectional audio connection where:
        - Our TX audio → other bridge's RX
        - Other bridge's TX audio → our RX

        Args:
            other_bridge: Another ARQAudioBridge instance to connect with

        Note:
            Both bridges must be in loopback_mode=True
        """
        if not self.loopback_mode or not other_bridge.loopback_mode:
            raise ValueError("Both bridges must be in loopback_mode for loopback connection")

        self._loopback_peer = other_bridge

        if self.debug:
            print(f"[Bridge] Loopback connected")

    def _on_arq_send(self, frame_bytes: bytes) -> None:
        """Callback for ARQ protocol sending frames.

        This is the TX path entry point.

        Args:
            frame_bytes: Complete ARQ frame to transmit
        """
        if self.debug:
            print(f"[Bridge] ARQ wants to send frame: {len(frame_bytes)} bytes")

        # Convert frame bytes to text string (PSK varicode encodes text)
        # ARQ frames use latin-1 encoding which preserves all byte values
        try:
            frame_text = frame_bytes.decode('latin-1')
        except UnicodeDecodeError as e:
            print(f"[Bridge] Error decoding frame: {e}")
            return

        # Modulate to audio using PSK
        audio = self.psk_encoder.modulate(
            frame_text,
            frequency=self.carrier_freq,
            sample_rate=self.sample_rate
        )

        # Add inter-frame gap (silence) after frame
        gap_samples = int(self.sample_rate * self.inter_frame_gap_ms / 1000)
        silence = np.zeros(gap_samples, dtype=np.float32)
        audio_with_gap = np.concatenate([audio, silence])

        if self.debug:
            print(f"[Bridge] Modulated to {len(audio_with_gap)} samples")

        # Transmit audio
        if self.loopback_mode:
            # In loopback mode, send directly to peer's RX
            if self._loopback_peer:
                self._loopback_peer._on_audio_rx(audio_with_gap)
            else:
                if self.debug:
                    print("[Bridge] Warning: No loopback peer connected")
        else:
            # Real audio mode - queue for output
            if self.audio_device:
                self.audio_device.write_output(audio_with_gap)
                self.audio_samples_tx += len(audio_with_gap)

        self.frames_sent += 1

    def _on_audio_rx(self, samples: np.ndarray) -> None:
        """Callback for received audio samples.

        This is the RX path entry point.

        Args:
            samples: Audio samples from input device or loopback
        """
        # Feed samples to PSK decoder
        self.psk_decoder.process(samples)
        self.audio_samples_rx += len(samples)

        # Decoder will call frame_extractor via text_callback
        # Frame extractor will call _on_frame_extracted when complete frame found

    def _on_frame_extracted(self, frame_bytes: bytes) -> None:
        """Callback from frame extractor when complete valid frame received.

        This completes the RX path by delivering frame to ARQ protocol.

        Args:
            frame_bytes: Complete validated ARQ frame
        """
        if self.debug:
            print(f"[Bridge] Received complete frame: {len(frame_bytes)} bytes")

        # Deliver to ARQ protocol
        self.arq.receive_frame(frame_bytes)
        self.frames_received += 1

    def process(self) -> None:
        """Process ARQ protocol state machine.

        This should be called regularly (e.g., in a loop) to allow
        the ARQ protocol to handle timeouts, retransmissions, etc.

        In a real application, this might run in a thread or event loop.
        """
        self.arq.process()

    def get_stats(self) -> dict:
        """Get bridge statistics.

        Returns:
            Dictionary with keys:
            - frames_sent: Frames transmitted
            - frames_received: Frames received
            - audio_samples_tx: Audio samples transmitted
            - audio_samples_rx: Audio samples received
            - frame_extractor_stats: Stats from frame extractor
            - decoder_stats: Stats from PSK decoder
        """
        return {
            'frames_sent': self.frames_sent,
            'frames_received': self.frames_received,
            'audio_samples_tx': self.audio_samples_tx,
            'audio_samples_rx': self.audio_samples_rx,
            'frame_extractor_stats': self.frame_extractor.get_stats(),
            'decoder_stats': self.psk_decoder.get_stats(),
        }

    def __enter__(self):
        """Context manager entry."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop()
        return False
