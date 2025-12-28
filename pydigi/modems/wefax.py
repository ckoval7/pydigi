"""
WEFAX (Weather Facsimile) Modem Implementation

WEFAX is an image transmission mode using FM (Frequency Modulation) to send
weather maps and satellite imagery. Unlike other pydigi modems which are
text-based, WEFAX transmits grayscale images scanline by scanline.

Supported modes:
- WEFAX_576: IOC=576, default LPM=120, APT START=300Hz, image width=1809 pixels
- WEFAX_288: IOC=288, default LPM=60, APT START=675Hz, image width=904 pixels

Both modes use APT STOP=450Hz and fixed sample rate of 11025 Hz.

Reference: fldigi/src/wefax/wefax.cxx
"""

import numpy as np
import math
from typing import Optional, Union
from pathlib import Path
from .base import Modem


class WEFAX(Modem):
    """
    WEFAX (Weather Facsimile) modem for image and text transmission.

    WEFAX uses FM where pixel grayscale values (0-255) are mapped to audio
    frequencies. The complete transmission includes:
    1. APT START tone (5 sec synchronization)
    2. PHASING pattern (20 lines for synchronization)
    3. ENDPHASING (1 line of white)
    4. IMAGE DATA (scanline by scanline)
    5. APT STOP tone (5 sec)
    6. BLACK signal (10 sec)

    WEFAX supports two transmission modes:
    - Image transmission: Use transmit_image() to send numpy arrays, PIL images, or image files
    - Text transmission: Use tx_process() or modulate() to render and send text as images

    Text is rendered as monospace on letter-sized pages (8.5" x 11") with configurable
    margins using the bundled DejaVu Sans Mono font (15pt default). Multi-page text is
    automatically paginated and transmitted with APT STOP tone separators between pages.

    Markdown support (optional):
    Enable text_markdown=True to render formatted text with:
    - Headers (# ## ### #### ##### ######) - different sizes, bold
    - Bold text (**text**)
    - Italic text (*text*)
    - Bold+Italic (***text***)
    - Inline code (`code`) - gray background
    - Code blocks (```language...```) - gray background
    - Lists (ordered and unordered)
    - Blockquotes (> text)
    - Horizontal rules (---)

    Default text rendering settings:
    - Font: DejaVu Sans Mono, 15pt
    - Page size: Letter (8.5" x 11")
    - Margins: 1" on all sides
    - Characters per line: ~50
    - Lines per page: ~80-85
    """

    # Mode definitions
    MODE_PARAMS = {
        "WEFAX_576": {
            "ioc": 576,
            "default_lpm": 120,
            "apt_start": 300.0,  # Hz
            "apt_stop": 450.0,  # Hz
            "image_width": 1809,  # pixels (IOC * pi)
        },
        "WEFAX_288": {
            "ioc": 288,
            "default_lpm": 60,
            "apt_start": 675.0,  # Hz
            "apt_stop": 450.0,  # Hz
            "image_width": 904,  # pixels (IOC * pi)
        },
    }

    def __init__(
        self,
        mode: str = "WEFAX_576",
        sample_rate: float = 11025.0,
        carrier: float = 1900.0,
        fm_deviation: float = 400.0,
        apt_start_duration: float = 5.0,
        apt_stop_duration: float = 5.0,
        black_duration: float = 10.0,
        phasing_lines: int = 20,
        phase_inverted: bool = False,
        text_font_size: Optional[int] = None,
        text_margins: tuple = (1.0, 1.0, 1.0, 1.0),
        text_font_path: Optional[str] = None,
        text_markdown: bool = False,
    ):
        """
        Initialize WEFAX modem.

        Args:
            mode: WEFAX mode name (WEFAX_576 or WEFAX_288)
            sample_rate: Sample rate in Hz (default: 11025, matches fldigi)
            carrier: Center frequency in Hz (default: 1900)
            fm_deviation: FM deviation in Hz (default: 400, DWD uses 425)
            apt_start_duration: APT START tone duration in seconds (default: 5.0)
            apt_stop_duration: APT STOP tone duration in seconds (default: 5.0)
            black_duration: BLACK signal duration in seconds (default: 10.0)
            phasing_lines: Number of phasing lines (default: 20)
            phase_inverted: Invert phasing pattern black/white (default: False)
            text_font_size: Font size in points for text rendering (default: auto-calculated)
            text_margins: Text margins in inches (top, right, bottom, left) (default: 1" all sides)
            text_font_path: Path to custom TTF font file (default: use bundled DejaVu Sans Mono)
            text_markdown: Enable markdown formatting for text (bold, italic, headers, etc.) (default: False)
        """
        mode = mode.upper()
        if mode not in self.MODE_PARAMS:
            raise ValueError(
                f"Unknown WEFAX mode: {mode}. Valid modes: {list(self.MODE_PARAMS.keys())}"
            )

        super().__init__(mode_name=mode, sample_rate=sample_rate, frequency=carrier)

        # Get mode parameters
        self.mode_params = self.MODE_PARAMS[mode]
        self.ioc = self.mode_params["ioc"]
        self.default_lpm = self.mode_params["default_lpm"]
        self.apt_start_freq = self.mode_params["apt_start"]
        self.apt_stop_freq = self.mode_params["apt_stop"]
        self.image_width = self.mode_params["image_width"]

        # Frequency modulation parameters
        self.carrier = carrier
        self.fm_deviation = fm_deviation

        # Transmission parameters
        self.apt_start_duration = apt_start_duration
        self.apt_stop_duration = apt_stop_duration
        self.black_duration = black_duration
        self.phasing_lines = phasing_lines
        self.phase_inverted = phase_inverted

        # Text rendering parameters
        self.text_font_size = text_font_size
        self.text_margins = text_margins
        self.text_font_path = text_font_path
        self.text_markdown = text_markdown

        # Calculate bandwidth (full FM bandwidth)
        self._bandwidth = 2.0 * (fm_deviation + self.default_lpm * self.image_width / 60.0)

        # Sine lookup table (for performance, like fldigi)
        self.sine_table = None
        self.sine_table_size = 8192
        self.phase_accumulator = 0.0

    def tx_init(self) -> None:
        """Initialize transmitter state."""
        # Initialize sine lookup table
        self._init_sine_table()
        self.phase_accumulator = 0.0

    def _init_sine_table(self) -> None:
        """
        Initialize sine lookup table for fast tone generation.

        Uses an 8192-element table (like fldigi) for performance.
        """
        if self.sine_table is None:
            self.sine_table = np.sin(
                2.0 * np.pi * np.arange(self.sine_table_size) / self.sine_table_size
            )

    def _pixel_to_frequency(self, pixel_value: float) -> float:
        """
        Convert pixel grayscale value to FM frequency.

        Formula from fldigi wefax.cxx line 1994:
        normalized = pixel_value / 256.0
        frequency = carrier + 2.0 * (normalized - 0.5) * fm_deviation

        Args:
            pixel_value: Pixel value in range 0-255 (0=black, 255=white)

        Returns:
            Frequency in Hz

        Example:
            With carrier=1900Hz, deviation=400Hz:
            Black (0)   → 1900 + 2*(0-0.5)*400 = 1500 Hz
            Gray (128)  → 1900 + 2*(0.5-0.5)*400 = 1900 Hz
            White (255) → 1900 + 2*(1-0.5)*400 = 2300 Hz
        """
        normalized = pixel_value / 256.0
        frequency = self.carrier + 2.0 * (normalized - 0.5) * self.fm_deviation
        return frequency

    def _generate_tone(self, frequency: float, n_samples: int) -> np.ndarray:
        """
        Generate FM tone at specified frequency using sine lookup table.

        Args:
            frequency: Frequency in Hz
            n_samples: Number of samples to generate

        Returns:
            Audio samples for the tone
        """
        samples = np.zeros(n_samples, dtype=np.float64)

        # Calculate phase increment per sample
        phase_increment = self.sine_table_size * frequency / self.sample_rate

        for i in range(n_samples):
            # Get sample from lookup table using linear interpolation
            table_idx = int(self.phase_accumulator) % self.sine_table_size
            samples[i] = self.sine_table[table_idx]

            # Advance phase
            self.phase_accumulator += phase_increment
            if self.phase_accumulator >= self.sine_table_size:
                self.phase_accumulator -= self.sine_table_size

        return samples

    def _generate_apt_tone(self, apt_frequency: float, duration: float) -> np.ndarray:
        """
        Generate APT START or STOP tone.

        APT tones are FM-modulated constant frequency signals. The modulation
        is set to produce the specific APT frequency (300, 450, or 675 Hz).

        From fldigi wefax.cxx line 2052:
        buf = 0.5 - (carrier - apt_freq) / (2.0 * fm_deviation)
        This creates a constant value that, when FM modulated, produces apt_freq.

        Args:
            apt_frequency: APT tone frequency in Hz (300, 450, or 675)
            duration: Duration in seconds

        Returns:
            Audio samples for the APT tone
        """
        n_samples = int(duration * self.sample_rate)

        # Generate FM-modulated tone at constant APT frequency
        return self._generate_tone(apt_frequency, n_samples)

    def _calculate_samples_per_line(self, lpm: int) -> int:
        """
        Calculate number of samples per scanline based on LPM.

        Formula from fldigi wefax.cxx line 465:
        samples_per_line = sample_rate * 60.0 / lpm

        Args:
            lpm: Lines per minute

        Returns:
            Number of samples per scanline

        Examples:
            LPM=120 @ 11025 Hz → 5512 samples/line
            LPM=60 @ 11025 Hz → 11025 samples/line
        """
        return int(self.sample_rate * 60.0 / lpm)

    def _generate_phasing(self, lpm: int) -> np.ndarray:
        """
        Generate phasing synchronization pattern.

        Phasing consists of 20 lines of alternating black/white bars,
        followed by 1 line of solid white (ENDPHASING).

        Pattern from fldigi wefax.cxx lines 2062-2065:
        phase_pos = sample_idx / samples_per_line
        is_white = (phase_pos < 0.025) or (phase_pos >= 0.975)
        pixel = WHITE if is_white else BLACK

        ENDPHASING from fldigi wefax.cxx lines 2072-2080:
        One full line of white (or black if phase inverted)

        Args:
            lpm: Lines per minute

        Returns:
            Audio samples for phasing pattern including ENDPHASING
        """
        samples_per_line = self._calculate_samples_per_line(lpm)
        # Add 1 extra line for ENDPHASING
        total_samples = samples_per_line * (self.phasing_lines + 1)
        audio = np.zeros(total_samples, dtype=np.float64)

        sample_idx = 0
        # Generate the 20 phasing lines
        for line in range(self.phasing_lines):
            for i in range(samples_per_line):
                # Calculate position within line (0.0 to 1.0)
                phase_pos = i / samples_per_line

                # Determine if this should be white or black
                is_white = (phase_pos < 0.025) or (phase_pos >= 0.975)

                # Apply phase inversion if configured
                if self.phase_inverted:
                    is_white = not is_white

                # Convert to pixel value
                pixel = 255 if is_white else 0

                # Generate tone at pixel frequency
                freq = self._pixel_to_frequency(pixel)
                table_idx = int(self.phase_accumulator) % self.sine_table_size
                audio[sample_idx] = self.sine_table[table_idx]

                # Advance phase
                phase_increment = self.sine_table_size * freq / self.sample_rate
                self.phase_accumulator += phase_increment
                if self.phase_accumulator >= self.sine_table_size:
                    self.phase_accumulator -= self.sine_table_size

                sample_idx += 1

        # Generate ENDPHASING line (one full line of white, or black if inverted)
        endphasing_pixel = 0 if self.phase_inverted else 255
        endphasing_freq = self._pixel_to_frequency(endphasing_pixel)
        for i in range(samples_per_line):
            table_idx = int(self.phase_accumulator) % self.sine_table_size
            audio[sample_idx] = self.sine_table[table_idx]

            # Advance phase
            phase_increment = self.sine_table_size * endphasing_freq / self.sample_rate
            self.phase_accumulator += phase_increment
            if self.phase_accumulator >= self.sine_table_size:
                self.phase_accumulator -= self.sine_table_size

            sample_idx += 1

        return audio

    def _transmit_scanline(self, scanline: np.ndarray, samples_per_line: int) -> np.ndarray:
        """
        Transmit one image scanline.

        Converts pixel values to frequencies and generates FM-modulated audio.
        Uses nearest-neighbor resampling (matches fldigi implementation).

        Args:
            scanline: Image row as 1D numpy array of pixel values (0-255)
            samples_per_line: Number of audio samples to generate for this line

        Returns:
            Audio samples for this scanline
        """
        audio = np.zeros(samples_per_line, dtype=np.float64)
        img_width = len(scanline)

        # Calculate ratio for resampling scanline to audio samples
        ratio = img_width / samples_per_line

        for i in range(samples_per_line):
            # Map audio sample index to image pixel index (nearest-neighbor)
            pixel_idx = int(i * ratio)
            if pixel_idx >= img_width:
                pixel_idx = img_width - 1

            # Get pixel value and convert to frequency
            pixel = scanline[pixel_idx]
            freq = self._pixel_to_frequency(pixel)

            # Generate sample from lookup table
            table_idx = int(self.phase_accumulator) % self.sine_table_size
            audio[i] = self.sine_table[table_idx]

            # Advance phase
            phase_increment = self.sine_table_size * freq / self.sample_rate
            self.phase_accumulator += phase_increment
            if self.phase_accumulator >= self.sine_table_size:
                self.phase_accumulator -= self.sine_table_size

        return audio

    def _generate_black(self, duration: float) -> np.ndarray:
        """
        Generate black signal (lowest frequency).

        The black signal is an FM-modulated tone at the frequency corresponding
        to pixel value 0 (black). This is used at the end of transmission.

        Args:
            duration: Duration in seconds

        Returns:
            Audio samples for black signal
        """
        n_samples = int(duration * self.sample_rate)
        # Black is pixel value 0, which maps to the lowest FM frequency
        freq = self._pixel_to_frequency(0)
        return self._generate_tone(freq, n_samples)

    def _load_image(self, image_input: Union[np.ndarray, str, Path]) -> np.ndarray:
        """
        Load and convert image to grayscale numpy array.

        Args:
            image_input: Can be:
                - numpy array (H, W) or (H, W, 1) or (H, W, 3) or (H, W, 4)
                - PIL Image object
                - File path (str or Path)

        Returns:
            Grayscale image as numpy array (H, W) with values 0-255 (uint8)
        """
        # If already a numpy array
        if isinstance(image_input, np.ndarray):
            img = image_input

            # Convert to grayscale if needed
            if len(img.shape) == 3:
                if img.shape[2] == 3:  # RGB
                    # Convert RGB to grayscale: 0.299*R + 0.587*G + 0.114*B
                    img = 0.299 * img[:, :, 0] + 0.587 * img[:, :, 1] + 0.114 * img[:, :, 2]
                elif img.shape[2] == 4:  # RGBA
                    # Convert RGBA to grayscale (ignore alpha)
                    img = 0.299 * img[:, :, 0] + 0.587 * img[:, :, 1] + 0.114 * img[:, :, 2]
                elif img.shape[2] == 1:  # Already grayscale with channel dim
                    img = img[:, :, 0]

            # Ensure uint8 range
            if img.dtype == np.float32 or img.dtype == np.float64:
                # Assume float images are in 0-1 range
                img = (img * 255).astype(np.uint8)
            else:
                img = img.astype(np.uint8)

            return img

        # Try to load with PIL
        try:
            from PIL import Image

            if isinstance(image_input, Image.Image):
                # Already a PIL Image
                pil_img = image_input
            else:
                # Load from file path
                pil_img = Image.open(image_input)

            # Convert to grayscale
            pil_img = pil_img.convert("L")

            # Convert to numpy array
            img = np.array(pil_img, dtype=np.uint8)

            return img

        except ImportError:
            raise ImportError(
                "Pillow (PIL) is required for loading image files. "
                "Install it with: pip install Pillow\n"
                "Or provide a numpy array directly."
            )

    def _resize_image(self, image: np.ndarray, target_width: Optional[int] = None) -> np.ndarray:
        """
        Resize image to match WEFAX width.

        Maintains aspect ratio by adjusting height.

        Args:
            image: Image as numpy array (H, W)
            target_width: Target width in pixels (default: use mode's image_width)

        Returns:
            Resized image as numpy array
        """
        if target_width is None:
            target_width = self.image_width

        height, width = image.shape

        # If already correct width, return as-is
        if width == target_width:
            return image

        # Calculate new height to maintain aspect ratio
        aspect_ratio = height / width
        target_height = int(target_width * aspect_ratio)

        # Try to use PIL for high-quality resizing
        try:
            from PIL import Image

            pil_img = Image.fromarray(image, mode="L")
            pil_img = pil_img.resize((target_width, target_height), Image.Resampling.LANCZOS)
            return np.array(pil_img, dtype=np.uint8)

        except ImportError:
            # Fallback to simple numpy resizing (nearest neighbor)
            # This is basic but works without PIL
            resized = np.zeros((target_height, target_width), dtype=np.uint8)

            for i in range(target_height):
                for j in range(target_width):
                    src_i = int(i * height / target_height)
                    src_j = int(j * width / target_width)
                    resized[i, j] = image[src_i, src_j]

            return resized

    def _validate_image(self, image: np.ndarray) -> None:
        """
        Validate image dimensions and data type.

        Args:
            image: Image to validate

        Raises:
            ValueError: If image is invalid
        """
        if not isinstance(image, np.ndarray):
            raise ValueError("Image must be a numpy array")

        if len(image.shape) != 2:
            raise ValueError(f"Image must be 2D (height, width), got shape {image.shape}")

        if image.shape[0] == 0 or image.shape[1] == 0:
            raise ValueError("Image has zero height or width")

    def _generate_test_pattern(self, width: int = None, height: int = 200) -> np.ndarray:
        """
        Generate black/white bar test pattern.

        Creates vertical bars alternating between black and white.

        Args:
            width: Image width in pixels (default: use mode's image_width)
            height: Image height in pixels (default: 200)

        Returns:
            Test pattern as numpy array (H, W)
        """
        if width is None:
            width = self.image_width

        pattern = np.zeros((height, width), dtype=np.uint8)

        # Create vertical bars (10 bars total)
        num_bars = 10
        bar_width = width // num_bars

        for i in range(num_bars):
            start_col = i * bar_width
            end_col = min((i + 1) * bar_width, width)

            # Alternate between white (255) and black (0)
            if i % 2 == 0:
                pattern[:, start_col:end_col] = 255
            else:
                pattern[:, start_col:end_col] = 0

        return pattern

    def transmit_test_pattern(self, width: Optional[int] = None, height: int = 200) -> np.ndarray:
        """
        Generate and transmit black/white bar test pattern.

        This method creates a vertical bar test pattern and transmits it
        using WEFAX modulation. Useful for testing without requiring an
        image file or text input.

        Args:
            width: Image width in pixels (default: use mode's image_width)
            height: Image height in pixels (default: 200)

        Returns:
            Audio samples for test pattern transmission

        Example:
            >>> wefax = WEFAX576()
            >>> audio = wefax.transmit_test_pattern()
            >>> save_wav("test_pattern.wav", audio, wefax.sample_rate)
        """
        pattern = self._generate_test_pattern(width, height)
        return self.transmit_image(pattern)

    def transmit_image(
        self,
        image: Union[np.ndarray, str, Path],
        lpm: Optional[int] = None,
        include_apt_start: bool = True,
        include_phasing: bool = True,
        include_apt_stop: bool = True,
        include_black: bool = True,
    ) -> np.ndarray:
        """
        Transmit an image using WEFAX modulation.

        This is the primary interface for WEFAX transmission.

        Complete transmission sequence:
        1. APT START tone (5 sec)
        2. PHASING pattern (20 lines)
        3. ENDPHASING (1 line of white)
        4. IMAGE DATA (scanline by scanline)
        5. APT STOP tone (5 sec)
        6. BLACK signal (10 sec)

        Args:
            image: Input image (numpy array, PIL Image, or file path)
            lpm: Lines per minute (default: use mode's default_lpm)
            include_apt_start: Include APT START tone (default: True)
            include_phasing: Include phasing pattern (default: True)
            include_apt_stop: Include APT STOP tone (default: True)
            include_black: Include black signal (default: True)

        Returns:
            Audio samples for complete WEFAX transmission

        Example:
            >>> wefax = WEFAX576()
            >>> audio = wefax.transmit_image("weather_map.png")
            >>> save_wav("wefax_transmission.wav", audio, 11025)
        """
        # Use default LPM if not specified
        if lpm is None:
            lpm = self.default_lpm

        # Initialize transmitter
        self.tx_init()

        # Load and prepare image
        img = self._load_image(image)
        self._validate_image(img)
        img = self._resize_image(img, self.image_width)

        # Calculate samples per line
        samples_per_line = self._calculate_samples_per_line(lpm)

        # Build transmission
        audio_parts = []

        # 1. APT START tone
        if include_apt_start:
            apt_start = self._generate_apt_tone(self.apt_start_freq, self.apt_start_duration)
            audio_parts.append(apt_start)

        # 2. PHASING pattern
        if include_phasing:
            phasing = self._generate_phasing(lpm)
            audio_parts.append(phasing)

        # 3. IMAGE DATA - transmit scanline by scanline
        img_height = img.shape[0]
        for row_idx in range(img_height):
            scanline = img[row_idx, :]
            scanline_audio = self._transmit_scanline(scanline, samples_per_line)
            audio_parts.append(scanline_audio)

        # 4. APT STOP tone
        if include_apt_stop:
            apt_stop = self._generate_apt_tone(self.apt_stop_freq, self.apt_stop_duration)
            audio_parts.append(apt_stop)

        # 5. BLACK signal
        if include_black:
            black = self._generate_black(self.black_duration)
            audio_parts.append(black)

        # Concatenate all parts
        audio = np.concatenate(audio_parts)

        return audio

    def tx_process(self, text: str) -> np.ndarray:
        """
        Process text and generate WEFAX audio.

        Renders text as monospace on letter-sized page with 1" margins,
        then transmits as WEFAX image. Multi-page text is concatenated
        with APT STOP tone separators between pages.

        Args:
            text: Text string to render and transmit (empty string generates test pattern)

        Returns:
            Audio samples for complete WEFAX transmission

        Raises:
            ImportError: If Pillow (PIL) is not installed

        Example:
            >>> wefax = WEFAX576()
            >>> text = "WEATHER REPORT\\nWind: 15kt\\nTemp: 20°C"
            >>> audio = wefax.modulate(text)
            >>> save_wav("weather.wav", audio, wefax.sample_rate)

        Note:
            Empty text generates a test pattern for backwards compatibility.
            For explicit test pattern generation, use transmit_test_pattern().
        """
        # Empty text - transmit test pattern for backwards compatibility
        if not text or text.strip() == "":
            return self.transmit_test_pattern()

        # Check PIL availability
        try:
            from PIL import Image, ImageDraw, ImageFont
        except ImportError:
            raise ImportError(
                "Pillow (PIL) is required for text transmission. "
                "Install with: pip install 'pydigi[image]' or pip install Pillow"
            )

        # Render text to image(s)
        from ..utils.text_renderer import render_text_for_wefax

        images = render_text_for_wefax(
            text=text,
            mode=self.mode_name,
            image_width=self.image_width,
            font_size=self.text_font_size,
            margins=self.text_margins,
            font_path=self.text_font_path,
            markdown=self.text_markdown,
        )

        # Warn if many pages
        if len(images) > 50:
            import warnings

            warnings.warn(f"Text spans {len(images)} pages, transmission will be very long")

        # Transmit each page and concatenate audio
        audio_parts = []
        for i, image in enumerate(images):
            if i > 0:
                # Add 2-second gap between pages (APT STOP tone)
                gap = self._generate_apt_tone(self.apt_stop_freq, 2.0)
                audio_parts.append(gap)

            # Transmit this page
            page_audio = self.transmit_image(image)
            audio_parts.append(page_audio)

        return np.concatenate(audio_parts)


# Convenience functions for creating specific WEFAX modes


def WEFAX576(sample_rate: float = 11025.0, carrier: float = 1900.0, **kwargs) -> WEFAX:
    """
    Create WEFAX_576 modem.

    WEFAX_576: IOC=576, default LPM=120, APT START=300Hz, image width=1809 pixels

    Args:
        sample_rate: Sample rate in Hz (default: 11025)
        carrier: Carrier frequency in Hz (default: 1900)
        **kwargs: Additional arguments passed to WEFAX constructor

    Returns:
        WEFAX modem configured for WEFAX_576 mode
    """
    return WEFAX("WEFAX_576", sample_rate, carrier, **kwargs)


def WEFAX288(sample_rate: float = 11025.0, carrier: float = 1900.0, **kwargs) -> WEFAX:
    """
    Create WEFAX_288 modem.

    WEFAX_288: IOC=288, default LPM=60, APT START=675Hz, image width=904 pixels

    Args:
        sample_rate: Sample rate in Hz (default: 11025)
        carrier: Carrier frequency in Hz (default: 1900)
        **kwargs: Additional arguments passed to WEFAX constructor

    Returns:
        WEFAX modem configured for WEFAX_288 mode
    """
    return WEFAX("WEFAX_288", sample_rate, carrier, **kwargs)
