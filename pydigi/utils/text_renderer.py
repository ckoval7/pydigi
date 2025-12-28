"""
Text Rendering Utility for WEFAX

This module provides text-to-image rendering capabilities for WEFAX modem,
converting text strings into grayscale images suitable for WEFAX transmission.

The rendering uses the bundled DejaVu Sans Mono font and follows letter-sized
page formatting with configurable margins.
"""

import os
import warnings
from typing import List, Optional, Tuple
import numpy as np


# Page dimensions in inches
LETTER_WIDTH_INCHES = 8.5
LETTER_HEIGHT_INCHES = 11.0

# WEFAX standard vertical resolution
WEFAX_LPI = 96  # Lines Per Inch (standard for all WEFAX modes)


def _get_bundled_font_path() -> str:
    """
    Get path to bundled DejaVuSansMono.ttf font.

    Returns:
        Absolute path to the bundled font file
    """
    fonts_dir = os.path.join(os.path.dirname(__file__), "..", "fonts")
    font_path = os.path.join(fonts_dir, "DejaVuSansMono.ttf")
    return os.path.abspath(font_path)


def _calculate_horizontal_dpi(image_width: int) -> int:
    """
    Calculate horizontal DPI based on image width and letter page width.

    Note: WEFAX uses rectangular pixels, not square pixels!
    Horizontal DPI varies by mode, but vertical is fixed at 96 LPI.

    Args:
        image_width: Image width in pixels

    Returns:
        Horizontal DPI (dots per inch)
    """
    return int(image_width / LETTER_WIDTH_INCHES)


def _calculate_page_dimensions(
    image_width: int, margins: Tuple[float, float, float, float]
) -> Tuple[int, int, int, int]:
    """
    Calculate page and printable area dimensions.

    IMPORTANT: WEFAX uses rectangular pixels!
    - Horizontal resolution: varies by mode (WEFAX_576 = ~213 DPI, WEFAX_288 = ~106 DPI)
    - Vertical resolution: FIXED at 96 LPI for all WEFAX modes

    Args:
        image_width: Image width in pixels
        margins: Margins in inches (top, right, bottom, left)

    Returns:
        Tuple of (page_width, page_height, printable_width, printable_height) in pixels
    """
    horizontal_dpi = _calculate_horizontal_dpi(image_width)

    # Full page dimensions
    page_width = image_width
    page_height = int(LETTER_HEIGHT_INCHES * WEFAX_LPI)  # Use fixed 96 LPI

    # Printable area (subtract margins)
    margin_top, margin_right, margin_bottom, margin_left = margins
    printable_width = int((LETTER_WIDTH_INCHES - margin_left - margin_right) * horizontal_dpi)
    printable_height = int((LETTER_HEIGHT_INCHES - margin_top - margin_bottom) * WEFAX_LPI)

    return page_width, page_height, printable_width, printable_height


def _calculate_default_font_size(image_width: int, target_chars_per_line: int = 45) -> int:
    """
    Calculate default font size for readable text at 96 LPI.

    At 96 LPI, vertical resolution is low, so we need larger fonts
    to maintain readability. Targets approximately 45 characters per line.

    Note: Font size is calculated to give ~24-28 pixels of height at 96 LPI,
    which provides good readability for monospace text.

    Args:
        image_width: Image width in pixels
        target_chars_per_line: Target number of characters per line

    Returns:
        Font size in points
    """
    # For 96 LPI, we want fonts that are large enough to be readable
    # A good target is ~24-28 pixels tall, which is 18-21pt at 96 DPI
    # We'll use a fixed larger size that works well for WEFAX

    # Calculate based on giving good vertical pixel height
    # Target: 24 pixels tall at 96 LPI = 24/96 * 72 = 18pt
    base_font_size = 18

    # Adjust slightly based on mode (more horizontal space = can be slightly larger)
    horizontal_dpi = _calculate_horizontal_dpi(image_width)
    if horizontal_dpi > 150:  # WEFAX_576
        return 20
    else:  # WEFAX_288
        return 18


def _load_font(font_size: int, font_path: Optional[str] = None):
    """
    Load font with fallback chain.

    Loading priority:
    1. User-specified font_path (if provided)
    2. Bundled DejaVuSansMono.ttf
    3. PIL default font

    Args:
        font_size: Font size in points
        font_path: Optional path to custom font file

    Returns:
        PIL ImageFont object
    """
    try:
        from PIL import ImageFont
    except ImportError:
        raise ImportError(
            "Pillow (PIL) is required for text rendering. "
            "Install with: pip install 'pydigi[image]' or pip install Pillow"
        )

    # Try user-specified font first
    if font_path is not None:
        try:
            font = ImageFont.truetype(font_path, font_size)
            return font
        except (OSError, IOError) as e:
            warnings.warn(f"Could not load font from {font_path}: {e}. Trying bundled font.")

    # Try bundled font
    bundled_font_path = _get_bundled_font_path()
    try:
        font = ImageFont.truetype(bundled_font_path, font_size)
        return font
    except (OSError, IOError) as e:
        warnings.warn(
            f"Could not load bundled font from {bundled_font_path}: {e}. "
            "Using PIL default font (quality may be reduced)."
        )

    # Fallback to PIL default
    try:
        # Try to get a default font with size
        font = ImageFont.load_default()
        return font
    except Exception as e:
        raise RuntimeError(f"Could not load any font: {e}")


def _wrap_text(text: str, font, max_width: int) -> List[str]:
    """
    Wrap text to fit within specified width.

    Preserves existing newlines and wraps at word boundaries.

    Args:
        text: Text to wrap
        font: PIL ImageFont object
        max_width: Maximum width in pixels

    Returns:
        List of text lines
    """
    try:
        from PIL import ImageDraw, Image
    except ImportError:
        raise ImportError(
            "Pillow (PIL) is required for text rendering. "
            "Install with: pip install 'pydigi[image]' or pip install Pillow"
        )

    # Create a temporary image for text measurement
    temp_img = Image.new("L", (1, 1), color=255)
    draw = ImageDraw.Draw(temp_img)

    lines = []

    # Split by existing newlines first
    paragraphs = text.split("\n")

    for paragraph in paragraphs:
        if not paragraph:
            # Empty line - preserve it
            lines.append("")
            continue

        # Wrap this paragraph
        words = paragraph.split()
        current_line = []

        for word in words:
            # Try adding this word to current line
            test_line = " ".join(current_line + [word])

            # Measure the width
            try:
                # Modern Pillow (>= 8.0)
                bbox = draw.textbbox((0, 0), test_line, font=font)
                line_width = bbox[2] - bbox[0]
            except AttributeError:
                # Older Pillow
                line_width, _ = draw.textsize(test_line, font=font)

            if line_width <= max_width:
                # Fits - add word to current line
                current_line.append(word)
            else:
                # Doesn't fit - finish current line and start new one
                if current_line:
                    lines.append(" ".join(current_line))
                    current_line = [word]
                else:
                    # Single word is too long - add it anyway
                    lines.append(word)

        # Add remaining words
        if current_line:
            lines.append(" ".join(current_line))

    return lines


def _render_page(
    lines: List[str],
    page_width: int,
    page_height: int,
    printable_width: int,
    printable_height: int,
    margins: Tuple[float, float, float, float],
    font,
    dpi: int,
) -> Tuple[np.ndarray, int]:
    """
    Render lines of text onto a single page.

    Args:
        lines: List of text lines to render
        page_width: Full page width in pixels
        page_height: Full page height in pixels
        printable_width: Printable area width in pixels
        printable_height: Printable area height in pixels
        margins: Margins in inches (top, right, bottom, left)
        font: PIL ImageFont object
        dpi: Dots per inch

    Returns:
        Tuple of (rendered page as numpy array, number of lines rendered)
    """
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        raise ImportError(
            "Pillow (PIL) is required for text rendering. "
            "Install with: pip install 'pydigi[image]' or pip install Pillow"
        )

    # Create white background
    img = Image.new("L", (page_width, page_height), color=255)
    draw = ImageDraw.Draw(img)

    # Calculate margins in pixels
    margin_top, margin_right, margin_bottom, margin_left = margins
    margin_left_px = int(margin_left * dpi)
    margin_top_px = int(margin_top * dpi)

    # Get line height
    try:
        # Measure a sample line to get height
        bbox = draw.textbbox((0, 0), "Ayg", font=font)
        line_height = bbox[3] - bbox[1]
    except AttributeError:
        # Older Pillow
        _, line_height = draw.textsize("Ayg", font=font)

    # Add some spacing between lines (1.1x line height for tighter spacing)
    line_spacing = int(line_height * 1.1)

    # Render lines
    y = margin_top_px
    lines_rendered = 0

    for line in lines:
        # Check if we have room for this line
        if y + line_height > margin_top_px + printable_height:
            # Page is full
            break

        # Draw the line
        draw.text((margin_left_px, y), line, fill=0, font=font)

        y += line_spacing
        lines_rendered += 1

    # Convert to numpy array
    img_array = np.array(img, dtype=np.uint8)

    return img_array, lines_rendered


def render_text_for_wefax(
    text: str,
    mode: str,
    image_width: int,
    font_size: Optional[int] = None,
    margins: Tuple[float, float, float, float] = (1.0, 1.0, 1.0, 1.0),
    font_path: Optional[str] = None,
    markdown: bool = False,
) -> List[np.ndarray]:
    """
    Render text as grayscale images for WEFAX transmission.

    Converts text string into one or more letter-sized page images with
    monospace font and specified margins. Multi-page text is automatically
    paginated.

    IMPORTANT: WEFAX uses 96 LPI (Lines Per Inch) vertical resolution,
    which is different from the horizontal DPI. This creates rectangular
    pixels, not square pixels.

    Args:
        text: Text string to render
        mode: WEFAX mode name (e.g., "WEFAX_576", "WEFAX_288")
        image_width: Image width in pixels (1809 for WEFAX_576, 904 for WEFAX_288)
        font_size: Font size in points (auto-calculated if None)
        margins: Margins in inches (top, right, bottom, left), default: 1" all sides
        font_path: Optional path to custom TTF font file
        markdown: If True, render text as markdown with formatting support (default: False)

    Returns:
        List of grayscale page images as numpy arrays (H x W, uint8, 0-255)
        Height will be 96 LPI × page_height_inches (e.g., 11" × 96 = 1056 lines)

    Raises:
        ImportError: If Pillow (PIL) is not installed
        RuntimeError: If no font could be loaded

    Example:
        >>> from pydigi.utils.text_renderer import render_text_for_wefax
        >>> text = "WEATHER REPORT\\nWind: 15kt\\nTemp: 20°C"
        >>> pages = render_text_for_wefax(text, "WEFAX_576", 1809)
        >>> print(f"Rendered {len(pages)} page(s)")
        >>> print(f"Page 1 shape: {pages[0].shape}")  # (1056, 1809) for letter size

        >>> # Markdown rendering
        >>> markdown_text = "# Weather Report\\n**Wind**: 15kt\\n*Temp*: 20°C"
        >>> pages = render_text_for_wefax(markdown_text, "WEFAX_576", 1809, markdown=True)
    """
    # Use markdown renderer if requested
    if markdown:
        from .markdown_renderer import render_markdown_for_wefax

        return render_markdown_for_wefax(
            text,
            mode,
            image_width,
            font_size,
            margins,
        )

    # Calculate page dimensions (uses 96 LPI for vertical)
    horizontal_dpi = _calculate_horizontal_dpi(image_width)
    page_width, page_height, printable_width, printable_height = _calculate_page_dimensions(
        image_width, margins
    )

    # Calculate or use provided font size
    if font_size is None:
        font_size = _calculate_default_font_size(image_width)

    # Load font
    font = _load_font(font_size, font_path)

    # Wrap text to fit width
    wrapped_lines = _wrap_text(text, font, printable_width)

    # Render pages
    pages = []
    line_idx = 0

    while line_idx < len(wrapped_lines):
        # Render this page (use WEFAX_LPI for vertical calculations)
        page_img, lines_rendered = _render_page(
            wrapped_lines[line_idx:],
            page_width,
            page_height,
            printable_width,
            printable_height,
            margins,
            font,
            WEFAX_LPI,  # Use fixed 96 LPI for vertical spacing
        )

        pages.append(page_img)
        line_idx += lines_rendered

        # Safety check - if no lines rendered, break to avoid infinite loop
        if lines_rendered == 0:
            warnings.warn("Could not fit any more text on page. Some text may be truncated.")
            break

    return pages
