"""
Synchronization Detection Components

This module provides components for detecting preamble/postamble patterns
and managing decoder state machines for synchronization.

Preambles and postambles are sync patterns transmitted before/after data:
    - Help receiver detect start/end of transmission
    - Enable timing and frequency synchronization
    - Distinguish sync from actual message data

Reference:
    - CLAUDE.md: "CRITICAL IMPLEMENTATION REQUIREMENTS" on preamble/postamble
    - fldigi: Search for 'preamble', 'postamble', 'tx_init', 'tx_flush'
"""

import numpy as np
from typing import Optional, Tuple, List, Union
from collections import deque
from enum import Enum


class DecoderState(Enum):
    """Decoder synchronization states."""
    IDLE = "idle"           # No signal, waiting
    PREAMBLE = "preamble"   # Detected signal, looking for preamble
    DATA = "data"           # Preamble found, decoding data
    POSTAMBLE = "postamble" # Detected postamble, finishing up


class SyncPattern:
    """
    Defines a synchronization pattern.

    A sync pattern is a known sequence of symbols or bits that
    the receiver looks for to establish synchronization.

    Examples:
        - PSK31: 32 phase reversals (alternating 0° and 180°)
        - QPSK: Specific bit pattern
        - MFSK: Specific tone sequence
        - RTTY: LTRS characters (0x1F)
    """

    def __init__(
        self,
        pattern: Union[np.ndarray, list],
        name: str = "sync",
        pattern_type: str = "symbols"
    ):
        """
        Initialize sync pattern.

        Args:
            pattern: Expected pattern (array of symbols, bits, or phases)
            name: Name for this pattern (e.g., "preamble", "postamble")
            pattern_type: Type of pattern:
                         "symbols" - symbol values
                         "bits" - bit sequence
                         "phase" - phase angles (radians)
                         "complex" - complex constellation points
        """
        self.pattern = np.array(pattern)
        self.name = name
        self.pattern_type = pattern_type
        self.length = len(pattern)

        # Pre-calculate normalization for correlation
        if pattern_type == "complex":
            self.energy = np.sum(np.abs(pattern) ** 2)
        else:
            self.energy = np.sum(pattern ** 2) if len(pattern) > 0 else 1.0

    def __repr__(self):
        return f"SyncPattern(name='{self.name}', length={self.length}, type='{self.pattern_type}')"


class SyncDetector:
    """
    Detects known sync patterns in symbol stream using correlation.

    Cross-correlates incoming symbols with expected pattern(s).
    When correlation exceeds threshold, pattern is detected.

    Can handle multiple patterns simultaneously (e.g., different
    preamble variants or both preamble and postamble).

    Example:
        >>> # PSK31 preamble: alternating phase reversals
        >>> preamble = SyncPattern(
        >>>     pattern=[1, -1, 1, -1, 1, -1, 1, -1],
        >>>     name="preamble",
        >>>     pattern_type="symbols"
        >>> )
        >>> detector = SyncDetector(preamble, threshold=0.8)
        >>>
        >>> for symbol in symbols:
        >>>     detected, pattern_name = detector.update(symbol)
        >>>     if detected:
        >>>         print(f"Detected {pattern_name}!")
    """

    def __init__(
        self,
        patterns: Union[SyncPattern, List[SyncPattern]],
        threshold: float = 0.8,
        min_spacing: int = 0
    ):
        """
        Initialize sync detector.

        Args:
            patterns: SyncPattern or list of SyncPatterns to detect
            threshold: Normalized correlation threshold (0-1)
                      0.5 = weak detection (many false alarms)
                      0.8 = moderate detection (recommended)
                      0.95 = strict detection (may miss in noise)
            min_spacing: Minimum symbols between detections (prevents re-trigger)
        """
        # Convert single pattern to list
        if isinstance(patterns, SyncPattern):
            patterns = [patterns]
        self.patterns = patterns
        self.threshold = threshold
        self.min_spacing = min_spacing

        # Create buffer for each pattern
        self.buffers = {p.name: deque(maxlen=p.length) for p in patterns}

        # Track last detection time
        self.last_detection = {p.name: -1000 for p in patterns}
        self.symbol_count = 0

    def update(self, symbol: Union[complex, float, int]) -> Tuple[bool, Optional[str]]:
        """
        Process one symbol and check for pattern detection.

        Args:
            symbol: Input symbol (type depends on pattern_type)

        Returns:
            (detected, pattern_name) tuple:
                - detected: True if any pattern detected
                - pattern_name: Name of detected pattern (or None)
        """
        self.symbol_count += 1

        for pattern in self.patterns:
            buf = self.buffers[pattern.name]
            buf.append(symbol)

            # Need full buffer for correlation
            if len(buf) < pattern.length:
                continue

            # Check spacing since last detection
            if self.symbol_count - self.last_detection[pattern.name] < self.min_spacing:
                continue

            # Calculate correlation
            corr = self._correlate(buf, pattern)

            if corr > self.threshold:
                # Pattern detected!
                self.last_detection[pattern.name] = self.symbol_count
                return True, pattern.name

        return False, None

    def _correlate(self, buffer: deque, pattern: SyncPattern) -> float:
        """
        Compute normalized correlation between buffer and pattern.

        Args:
            buffer: Sliding window buffer
            pattern: Expected sync pattern

        Returns:
            Normalized correlation (0-1)
        """
        buf_array = np.array(buffer)

        if pattern.pattern_type == "complex":
            # Complex correlation: |sum(a * conj(b))| / sqrt(|a|² * |b|²)
            correlation = np.abs(np.sum(buf_array * np.conj(pattern.pattern)))
            buf_energy = np.sum(np.abs(buf_array) ** 2)

        elif pattern.pattern_type == "phase":
            # Phase correlation: compare phase differences
            # Convert to complex phasors first
            buf_phasor = np.exp(1j * buf_array)
            pattern_phasor = np.exp(1j * pattern.pattern)
            correlation = np.abs(np.sum(buf_phasor * np.conj(pattern_phasor)))
            buf_energy = len(buf_array)  # Unit magnitude phasors

        else:
            # Real correlation (symbols or bits)
            correlation = np.abs(np.sum(buf_array * pattern.pattern))
            buf_energy = np.sum(buf_array ** 2)

        # Normalize
        if buf_energy < 1e-10:
            return 0.0

        normalized = correlation / np.sqrt(pattern.energy * buf_energy + 1e-10)
        return min(normalized, 1.0)  # Clamp to [0, 1]

    def reset(self):
        """Clear all buffers and reset detector state."""
        for pattern in self.patterns:
            self.buffers[pattern.name].clear()
            self.last_detection[pattern.name] = -1000
        self.symbol_count = 0

    def reset_pattern(self, pattern_name: str):
        """Reset state for a specific pattern."""
        if pattern_name in self.buffers:
            self.buffers[pattern_name].clear()
            self.last_detection[pattern_name] = -1000


class DecoderStateMachine:
    """
    State machine for decoder synchronization.

    Manages transitions between decoder states:
        IDLE → PREAMBLE → DATA → POSTAMBLE → IDLE

    This helps decoders:
        - Know when to start/stop decoding
        - Apply different processing in each state
        - Track message boundaries

    Example:
        >>> fsm = DecoderStateMachine()
        >>> dcd = EnergyDCD()
        >>> preamble_detector = SyncDetector(preamble_pattern)
        >>>
        >>> for sample in samples:
        >>>     # Update DCD
        >>>     signal_present, snr = dcd.update(sample)
        >>>
        >>>     # Update state machine
        >>>     if signal_present and fsm.state == DecoderState.IDLE:
        >>>         fsm.transition('signal_detected')
        >>>
        >>>     if fsm.state == DecoderState.PREAMBLE:
        >>>         # Look for preamble
        >>>         if preamble_detector.update(symbol)[0]:
        >>>             fsm.transition('preamble_found')
        >>>
        >>>     if fsm.state == DecoderState.DATA:
        >>>         # Decode data
        >>>         decode_symbol(symbol)
    """

    def __init__(self, initial_state: DecoderState = DecoderState.IDLE):
        """
        Initialize state machine.

        Args:
            initial_state: Starting state (usually IDLE)
        """
        self.state = initial_state
        self.previous_state = None

        # State transition history
        self.history = []
        self.max_history = 10

        # Callbacks for state transitions
        self.on_enter_callbacks = {}
        self.on_exit_callbacks = {}

    def transition(self, event: str) -> DecoderState:
        """
        Update state based on event.

        Args:
            event: Event name:
                  'signal_detected' - DCD triggered
                  'preamble_found' - Preamble detected
                  'data_start' - Ready to decode data
                  'postamble_found' - Postamble detected
                  'signal_lost' - DCD dropped
                  'timeout' - No activity timeout
                  'reset' - Force reset to IDLE

        Returns:
            New state
        """
        old_state = self.state

        # State transition logic
        if event == 'reset':
            self.state = DecoderState.IDLE

        elif self.state == DecoderState.IDLE:
            if event == 'signal_detected':
                self.state = DecoderState.PREAMBLE

        elif self.state == DecoderState.PREAMBLE:
            if event == 'preamble_found' or event == 'data_start':
                self.state = DecoderState.DATA
            elif event == 'signal_lost' or event == 'timeout':
                self.state = DecoderState.IDLE

        elif self.state == DecoderState.DATA:
            if event == 'postamble_found':
                self.state = DecoderState.POSTAMBLE
            elif event == 'signal_lost' or event == 'timeout':
                self.state = DecoderState.IDLE

        elif self.state == DecoderState.POSTAMBLE:
            # Always return to IDLE after postamble
            self.state = DecoderState.IDLE

        # Track transition
        if self.state != old_state:
            self.previous_state = old_state
            self._record_transition(old_state, self.state, event)

            # Call callbacks
            self._call_exit_callback(old_state)
            self._call_enter_callback(self.state)

        return self.state

    def _record_transition(self, from_state: DecoderState, to_state: DecoderState, event: str):
        """Record state transition in history."""
        self.history.append({
            'from': from_state,
            'to': to_state,
            'event': event
        })
        if len(self.history) > self.max_history:
            self.history.pop(0)

    def _call_enter_callback(self, state: DecoderState):
        """Call on_enter callback for state."""
        if state in self.on_enter_callbacks:
            self.on_enter_callbacks[state]()

    def _call_exit_callback(self, state: DecoderState):
        """Call on_exit callback for state."""
        if state in self.on_exit_callbacks:
            self.on_exit_callbacks[state]()

    def register_on_enter(self, state: DecoderState, callback):
        """
        Register callback for entering a state.

        Args:
            state: State to trigger on
            callback: Function to call (no arguments)

        Example:
            >>> def on_enter_data():
            >>>     print("Starting to decode data")
            >>> fsm.register_on_enter(DecoderState.DATA, on_enter_data)
        """
        self.on_enter_callbacks[state] = callback

    def register_on_exit(self, state: DecoderState, callback):
        """Register callback for exiting a state."""
        self.on_exit_callbacks[state] = callback

    def reset(self):
        """Reset to IDLE state."""
        self.transition('reset')
        self.history = []

    def get_state(self) -> DecoderState:
        """Get current state."""
        return self.state

    def is_idle(self) -> bool:
        """Check if in IDLE state."""
        return self.state == DecoderState.IDLE

    def is_acquiring(self) -> bool:
        """Check if acquiring (PREAMBLE state)."""
        return self.state == DecoderState.PREAMBLE

    def is_decoding(self) -> bool:
        """Check if decoding data (DATA state)."""
        return self.state == DecoderState.DATA

    def is_finishing(self) -> bool:
        """Check if finishing (POSTAMBLE state)."""
        return self.state == DecoderState.POSTAMBLE

    def get_history(self) -> List[dict]:
        """Get transition history."""
        return self.history.copy()

    def __repr__(self):
        return f"DecoderStateMachine(state={self.state.value})"


def create_psk_preamble_pattern(num_reversals: int = 32) -> SyncPattern:
    """
    Create PSK preamble pattern (phase reversals).

    PSK modes (PSK31, PSK63, PSK125) use phase reversals as preamble.
    This is alternating 0° and 180° phase shifts.

    Args:
        num_reversals: Number of phase reversals
                      PSK31: 32 (default)
                      PSK63: 64
                      PSK125: 125

    Returns:
        SyncPattern for PSK preamble

    Example:
        >>> preamble = create_psk_preamble_pattern(32)
        >>> detector = SyncDetector(preamble)
    """
    # Alternating +1 and -1 (0° and 180°)
    pattern = np.array([1 if i % 2 == 0 else -1 for i in range(num_reversals)])
    return SyncPattern(pattern, name="psk_preamble", pattern_type="symbols")


def create_rtty_preamble_pattern(num_ltrs: int = 8) -> SyncPattern:
    """
    Create RTTY preamble pattern (LTRS characters).

    RTTY sends LTRS (Letters shift) characters as preamble.
    LTRS code is 0x1F (5 bits: 11111).

    Args:
        num_ltrs: Number of LTRS characters (typically 8)

    Returns:
        SyncPattern for RTTY preamble

    Example:
        >>> preamble = create_rtty_preamble_pattern(8)
        >>> detector = SyncDetector(preamble)
    """
    # LTRS = 0x1F = 11111 in Baudot code
    ltrs_bits = [1, 1, 1, 1, 1]
    pattern = np.array(ltrs_bits * num_ltrs)
    return SyncPattern(pattern, name="rtty_preamble", pattern_type="bits")


def create_tone_sequence_pattern(tone_indices: list, name: str = "tone_preamble") -> SyncPattern:
    """
    Create preamble pattern for tone-based modes.

    Some MFSK modes use specific tone sequences as preamble.

    Args:
        tone_indices: List of tone indices (e.g., [0, 1, 2, 3, 0])
        name: Pattern name

    Returns:
        SyncPattern for tone sequence

    Example:
        >>> # DominoEX uses specific tone sequence
        >>> preamble = create_tone_sequence_pattern([0, 1, 2, 3], "domino_preamble")
    """
    pattern = np.array(tone_indices)
    return SyncPattern(pattern, name=name, pattern_type="symbols")
