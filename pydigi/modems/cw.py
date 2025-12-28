"""
CW (Morse Code) modem implementation.

Based on fldigi's CW implementation (fldigi/src/cw/cw.cxx).
Generates Morse code audio signals with configurable speed and edge shaping.
"""

import numpy as np
from typing import Optional, Dict, List
from ..core.oscillator import NCO
from ..modems.base import Modem


# Morse code lookup table from fldigi
# Format: character -> (morse_pattern, timing_pattern)
# In timing_pattern: 0.33 = dit (1 unit), 1.0 = dah (3 units)
MORSE_TABLE: Dict[str, str] = {
    # Letters
    "A": ".-",
    "B": "-...",
    "C": "-.-.",
    "D": "-..",
    "E": ".",
    "F": "..-.",
    "G": "--.",
    "H": "....",
    "I": "..",
    "J": ".---",
    "K": "-.-",
    "L": ".-..",
    "M": "--",
    "N": "-.",
    "O": "---",
    "P": ".--.",
    "Q": "--.-",
    "R": ".-.",
    "S": "...",
    "T": "-",
    "U": "..-",
    "V": "...-",
    "W": ".--",
    "X": "-..-",
    "Y": "-.--",
    "Z": "--..",
    # Numbers
    "0": "-----",
    "1": ".----",
    "2": "..---",
    "3": "...--",
    "4": "....-",
    "5": ".....",
    "6": "-....",
    "7": "--...",
    "8": "---..",
    "9": "----.",
    # Punctuation
    ".": ".-.-.-",  # Period
    ",": "--..--",  # Comma
    "?": "..--..",  # Question mark
    "'": ".----.",  # Apostrophe
    "!": "-.-.--",  # Exclamation mark
    "/": "-..-.",  # Slash
    "(": "-.--.",  # Left parenthesis
    ")": "-.--.-",  # Right parenthesis
    "&": ".-...",  # Ampersand
    ":": "---...",  # Colon
    ";": "-.-.-.",  # Semicolon
    "=": "-...-",  # Equal sign
    "+": ".-.-.",  # Plus sign
    "-": "-....-",  # Hyphen
    "_": "..--.-",  # Underscore
    '"': ".-..-.",  # Quote
    "$": "...-..-",  # Dollar sign
    "@": ".--.-.",  # At sign
    # Prosigns (special combinations)
    "<AR>": ".-.-.",  # End of message
    "<SK>": "...-.-",  # End of contact
    "<BT>": "-...-",  # Break
    "<KN>": "-.--.",  # Invitation to specific station
    "<AS>": ".-...",  # Wait
}


class CW(Modem):
    """
    CW (Morse Code) modem.

    Generates CW (Continuous Wave) Morse code signals with proper timing
    and edge shaping to prevent key clicks.

    Timing in Morse code:
        - Dit (dot): 1 unit
        - Dah (dash): 3 units
        - Inter-element gap: 1 unit
        - Inter-character gap: 3 units
        - Inter-word gap: 7 units

    WPM (Words Per Minute) calculation:
        - PARIS is the standard word (50 units total)
        - WPM = 1200 / (dit_length_ms * 50)
        - At 20 WPM: dit = 60ms

    Attributes:
        wpm: Words per minute (5-200, typical 10-40)
        rise_time: Edge rise/fall time in milliseconds (default: 4ms)
        tone_freq: Audio tone frequency in Hz (inherited from base, default: 800 Hz)

    Example:
        >>> cw = CW(wpm=20)
        >>> audio = cw.modulate("CQ CQ CQ DE W1ABC", frequency=800)
        >>> # Save to WAV or use with GNU Radio
    """

    def __init__(
        self,
        wpm: float = 20.0,
        rise_time: float = 4.0,
        sample_rate: float = 8000.0,
        frequency: float = 800.0,
    ):
        """
        Initialize the CW modem.

        Args:
            wpm: Words per minute (default: 20, range: 5-200)
            rise_time: Edge rise/fall time in ms (default: 4ms)
            sample_rate: Sample rate in Hz (default: 8000)
            frequency: Tone frequency in Hz (default: 800)
        """
        super().__init__("CW", sample_rate=sample_rate, frequency=frequency)

        self.wpm = wpm
        self.rise_time = rise_time

        # Calculate timing
        self._update_timing()

        # NCO for tone generation
        self.nco = NCO(sample_rate=sample_rate, frequency=frequency)

        # Bandwidth (approximately the keying rate)
        self._bandwidth = 1000.0 / self.dit_samples * self.sample_rate

    def _update_timing(self) -> None:
        """Update timing parameters based on WPM."""
        # Calculate dit length in seconds
        # PARIS = 50 units, so 1 WPM = 50 units per minute
        # dit_time = 60 / (50 * WPM)
        self.dit_time = 1.2 / self.wpm  # seconds
        self.dah_time = 3.0 * self.dit_time

        # Convert to samples
        self.dit_samples = int(self.dit_time * self.sample_rate)
        self.dah_samples = int(self.dah_time * self.sample_rate)

        # Inter-element gap (between dits/dahs in a character)
        self.element_gap_samples = self.dit_samples

        # Inter-character gap
        self.char_gap_samples = 3 * self.dit_samples

        # Inter-word gap
        self.word_gap_samples = 7 * self.dit_samples

        # Edge shaping samples (rise/fall time)
        self.rise_samples = int((self.rise_time / 1000.0) * self.sample_rate)

        # Ensure rise time doesn't exceed dit time
        if self.rise_samples > self.dit_samples // 2:
            self.rise_samples = self.dit_samples // 2

    def _generate_edge_shape(self, n_samples: int, rising: bool = True) -> np.ndarray:
        """
        Generate raised cosine edge shaping to prevent key clicks.

        Args:
            n_samples: Number of samples for the edge
            rising: True for rising edge, False for falling edge

        Returns:
            Array of amplitude values (0 to 1)
        """
        if n_samples <= 0:
            return np.array([])

        # Raised cosine envelope
        t = np.arange(n_samples) / n_samples
        if rising:
            # 0 to 1
            envelope = 0.5 * (1.0 - np.cos(np.pi * t))
        else:
            # 1 to 0
            envelope = 0.5 * (1.0 + np.cos(np.pi * t))

        return envelope

    def _generate_element(self, duration_samples: int) -> np.ndarray:
        """
        Generate a single dit or dah with edge shaping.

        Args:
            duration_samples: Total duration in samples

        Returns:
            Audio samples for the element
        """
        # Generate tone
        tone = self.nco.step_real(duration_samples)

        # Apply edge shaping
        if self.rise_samples > 0:
            # Rising edge
            if self.rise_samples < duration_samples:
                tone[: self.rise_samples] *= self._generate_edge_shape(
                    self.rise_samples, rising=True
                )

            # Falling edge
            if self.rise_samples < duration_samples:
                tone[-self.rise_samples :] *= self._generate_edge_shape(
                    self.rise_samples, rising=False
                )

        return tone

    def _encode_character(self, char: str) -> Optional[str]:
        """
        Encode a character to morse code pattern.

        Args:
            char: Character to encode

        Returns:
            Morse pattern (e.g., ".-" for 'A'), or None if not found
        """
        char = char.upper()

        # Check for prosigns (enclosed in < >)
        if char in MORSE_TABLE:
            return MORSE_TABLE[char]

        return None

    def _generate_morse_pattern(self, pattern: str) -> np.ndarray:
        """
        Generate audio for a morse code pattern.

        Args:
            pattern: Morse pattern (e.g., ".-" for 'A')

        Returns:
            Audio samples
        """
        audio_segments = []

        for i, symbol in enumerate(pattern):
            if symbol == ".":
                # Dit
                audio_segments.append(self._generate_element(self.dit_samples))
            elif symbol == "-":
                # Dah
                audio_segments.append(self._generate_element(self.dah_samples))
            else:
                # Unknown symbol, skip
                continue

            # Add inter-element gap (except after last element)
            if i < len(pattern) - 1:
                audio_segments.append(np.zeros(self.element_gap_samples))

        if audio_segments:
            return np.concatenate(audio_segments)
        return np.array([])

    def tx_init(self) -> None:
        """Initialize the transmitter."""
        # Update NCO frequency
        self.nco.frequency = self.frequency
        self.nco.reset()

        # Update timing if WPM changed
        self._update_timing()

    def tx_process(self, text: str) -> np.ndarray:
        """
        Process text and generate CW audio.

        Args:
            text: Text to transmit in Morse code

        Returns:
            Audio samples (float array)
        """
        audio_segments = []

        # Process each character
        i = 0
        while i < len(text):
            char = text[i]

            # Handle prosigns (enclosed in < >)
            if char == "<":
                end = text.find(">", i)
                if end != -1:
                    prosign = text[i : end + 1]
                    pattern = self._encode_character(prosign)
                    if pattern:
                        audio_segments.append(self._generate_morse_pattern(pattern))
                        audio_segments.append(np.zeros(self.char_gap_samples))
                    i = end + 1
                    continue

            # Handle spaces (word gaps)
            if char == " ":
                audio_segments.append(np.zeros(self.word_gap_samples))
                i += 1
                continue

            # Regular character
            pattern = self._encode_character(char)
            if pattern:
                audio_segments.append(self._generate_morse_pattern(pattern))
                audio_segments.append(np.zeros(self.char_gap_samples))

            i += 1

        # Concatenate all segments
        if audio_segments:
            return np.concatenate(audio_segments)
        return np.array([])

    def set_wpm(self, wpm: float) -> None:
        """
        Set the transmission speed in words per minute.

        Args:
            wpm: Words per minute (5-200)
        """
        self.wpm = max(5.0, min(200.0, wpm))  # Clamp to valid range
        self._update_timing()
        self._tx_initialized = False  # Force re-initialization

    def get_character_duration(self, char: str) -> float:
        """
        Get the duration of a character in seconds.

        Useful for estimating transmission time.

        Args:
            char: Character to check

        Returns:
            Duration in seconds
        """
        pattern = self._encode_character(char)
        if not pattern:
            return 0.0

        # Count dits and dahs
        n_dits = pattern.count(".")
        n_dahs = pattern.count("-")
        n_elements = len(pattern)

        # Total time: dits + dahs + inter-element gaps + inter-char gap
        duration = (
            n_dits * self.dit_time
            + n_dahs * self.dah_time
            + (n_elements - 1) * self.dit_time  # Inter-element gaps
            + 3 * self.dit_time
        )  # Inter-char gap

        return duration

    def estimate_duration(self, text: str) -> float:
        """
        Estimate the total transmission duration for a text string.

        Args:
            text: Text to transmit

        Returns:
            Estimated duration in seconds
        """
        total_time = 0.0

        for char in text:
            if char == " ":
                total_time += 7 * self.dit_time  # Word gap
            else:
                total_time += self.get_character_duration(char)

        return total_time
