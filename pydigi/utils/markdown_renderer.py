"""
Markdown Rendering Utility for WEFAX

This module provides markdown-to-image rendering capabilities for WEFAX modem,
converting markdown text into grayscale images with proper formatting (headers,
bold, italic, lists, code blocks, etc.).

Requires:
    - Pillow (PIL) for image rendering
    - markdown2 for markdown parsing
"""

import os
import re
import warnings
from typing import List, Optional, Tuple, Dict
from enum import Enum
import numpy as np


# Page dimensions in inches
LETTER_WIDTH_INCHES = 8.5
LETTER_HEIGHT_INCHES = 11.0

# WEFAX standard vertical resolution
WEFAX_LPI = 96  # Lines Per Inch (standard for all WEFAX modes)


class TextStyle(Enum):
    """Text formatting styles."""
    NORMAL = "normal"
    BOLD = "bold"
    ITALIC = "italic"
    BOLD_ITALIC = "bold_italic"
    CODE = "code"


class Element:
    """Base class for rendered elements."""
    def __init__(self, style: TextStyle = TextStyle.NORMAL):
        self.style = style


class TextElement(Element):
    """Text with optional formatting."""
    def __init__(self, text: str, style: TextStyle = TextStyle.NORMAL):
        super().__init__(style)
        self.text = text


class LineBreakElement(Element):
    """Line break element."""
    pass


class HeaderElement(Element):
    """Header element with level (1-6)."""
    def __init__(self, text: str, level: int):
        super().__init__(TextStyle.BOLD)
        self.text = text
        self.level = level  # 1-6


class ListItemElement(Element):
    """List item element."""
    def __init__(self, text: str, ordered: bool = False, number: Optional[int] = None, indent: int = 0):
        super().__init__(TextStyle.NORMAL)
        self.text = text
        self.ordered = ordered
        self.number = number
        self.indent = indent


class CodeBlockElement(Element):
    """Code block element."""
    def __init__(self, code: str, language: Optional[str] = None):
        super().__init__(TextStyle.CODE)
        self.code = code
        self.language = language


class HorizontalRuleElement(Element):
    """Horizontal rule element."""
    pass


class BlockquoteElement(Element):
    """Blockquote element."""
    def __init__(self, text: str):
        super().__init__(TextStyle.ITALIC)
        self.text = text


def _get_bundled_font_path(style: TextStyle = TextStyle.NORMAL) -> str:
    """
    Get path to bundled DejaVuSansMono font variant.

    Args:
        style: Text style (normal, bold, italic, bold_italic)

    Returns:
        Absolute path to the bundled font file
    """
    fonts_dir = os.path.join(os.path.dirname(__file__), "..", "fonts")

    font_files = {
        TextStyle.NORMAL: "DejaVuSansMono.ttf",
        TextStyle.BOLD: "DejaVuSansMono-Bold.ttf",
        TextStyle.ITALIC: "DejaVuSansMono-Oblique.ttf",
        TextStyle.BOLD_ITALIC: "DejaVuSansMono-BoldOblique.ttf",
        TextStyle.CODE: "DejaVuSansMono.ttf",
    }

    font_file = font_files.get(style, "DejaVuSansMono.ttf")
    font_path = os.path.join(fonts_dir, font_file)
    return os.path.abspath(font_path)


def _calculate_horizontal_dpi(image_width: int) -> int:
    """
    Calculate horizontal DPI based on image width and letter page width.

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

    Args:
        image_width: Image width in pixels
        margins: Margins in inches (top, right, bottom, left)

    Returns:
        Tuple of (page_width, page_height, printable_width, printable_height) in pixels
    """
    horizontal_dpi = _calculate_horizontal_dpi(image_width)

    # Full page dimensions
    page_width = image_width
    page_height = int(LETTER_HEIGHT_INCHES * WEFAX_LPI)

    # Printable area (subtract margins)
    margin_top, margin_right, margin_bottom, margin_left = margins
    printable_width = int((LETTER_WIDTH_INCHES - margin_left - margin_right) * horizontal_dpi)
    printable_height = int((LETTER_HEIGHT_INCHES - margin_top - margin_bottom) * WEFAX_LPI)

    return page_width, page_height, printable_width, printable_height


def _load_fonts(base_font_size: int) -> Dict[TextStyle, any]:
    """
    Load all font variants.

    Args:
        base_font_size: Base font size in points

    Returns:
        Dictionary mapping TextStyle to PIL ImageFont objects
    """
    try:
        from PIL import ImageFont
    except ImportError:
        raise ImportError(
            "Pillow (PIL) is required for markdown rendering. "
            "Install with: pip install 'pydigi[image]' or pip install Pillow"
        )

    fonts = {}
    for style in TextStyle:
        try:
            font_path = _get_bundled_font_path(style)
            fonts[style] = ImageFont.truetype(font_path, base_font_size)
        except (OSError, IOError) as e:
            warnings.warn(f"Could not load font for {style.value}: {e}. Using normal font.")
            font_path = _get_bundled_font_path(TextStyle.NORMAL)
            fonts[style] = ImageFont.truetype(font_path, base_font_size)

    return fonts


def _parse_inline_markdown(text: str) -> List[TextElement]:
    """
    Parse inline markdown formatting (bold, italic, code).

    Args:
        text: Text with inline markdown

    Returns:
        List of TextElement objects with appropriate styling
    """
    elements = []

    # Pattern to match inline markdown:
    # **bold**, *italic*, `code`, ***bold-italic***
    pattern = r'(\*\*\*[^*]+\*\*\*|\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`)'

    parts = re.split(pattern, text)

    for part in parts:
        if not part:
            continue

        if part.startswith('***') and part.endswith('***'):
            # Bold italic
            elements.append(TextElement(part[3:-3], TextStyle.BOLD_ITALIC))
        elif part.startswith('**') and part.endswith('**'):
            # Bold
            elements.append(TextElement(part[2:-2], TextStyle.BOLD))
        elif part.startswith('*') and part.endswith('*'):
            # Italic
            elements.append(TextElement(part[1:-1], TextStyle.ITALIC))
        elif part.startswith('`') and part.endswith('`'):
            # Inline code
            elements.append(TextElement(part[1:-1], TextStyle.CODE))
        else:
            # Normal text
            elements.append(TextElement(part, TextStyle.NORMAL))

    return elements


def _parse_markdown_to_elements(markdown_text: str) -> List[Element]:
    """
    Parse markdown text into structured elements.

    Args:
        markdown_text: Markdown formatted text

    Returns:
        List of Element objects
    """
    elements = []
    lines = markdown_text.split('\n')

    i = 0
    in_code_block = False
    code_block_lines = []
    code_language = None

    while i < len(lines):
        line = lines[i]

        # Code blocks
        if line.strip().startswith('```'):
            if not in_code_block:
                # Start code block
                in_code_block = True
                code_language = line.strip()[3:].strip() or None
                code_block_lines = []
            else:
                # End code block
                in_code_block = False
                elements.append(CodeBlockElement('\n'.join(code_block_lines), code_language))
                code_block_lines = []
                code_language = None
            i += 1
            continue

        if in_code_block:
            code_block_lines.append(line)
            i += 1
            continue

        # Headers
        header_match = re.match(r'^(#{1,6})\s+(.+)$', line)
        if header_match:
            level = len(header_match.group(1))
            text = header_match.group(2)
            elements.append(HeaderElement(text, level))
            i += 1
            continue

        # Horizontal rule
        if re.match(r'^(-{3,}|\*{3,}|_{3,})$', line.strip()):
            elements.append(HorizontalRuleElement())
            i += 1
            continue

        # Blockquote
        if line.strip().startswith('>'):
            quote_text = line.strip()[1:].strip()
            elements.append(BlockquoteElement(quote_text))
            i += 1
            continue

        # Unordered list
        list_match = re.match(r'^(\s*)([-*+])\s+(.+)$', line)
        if list_match:
            indent = len(list_match.group(1)) // 2
            text = list_match.group(3)
            elements.append(ListItemElement(text, ordered=False, indent=indent))
            i += 1
            continue

        # Ordered list
        ordered_match = re.match(r'^(\s*)(\d+)\.\s+(.+)$', line)
        if ordered_match:
            indent = len(ordered_match.group(1)) // 2
            number = int(ordered_match.group(2))
            text = ordered_match.group(3)
            elements.append(ListItemElement(text, ordered=True, number=number, indent=indent))
            i += 1
            continue

        # Empty line
        if not line.strip():
            elements.append(LineBreakElement())
            i += 1
            continue

        # Regular paragraph - parse inline formatting
        inline_elements = _parse_inline_markdown(line)
        elements.extend(inline_elements)
        elements.append(LineBreakElement())
        i += 1

    return elements


def _render_elements_to_pages(
    elements: List[Element],
    page_width: int,
    page_height: int,
    printable_width: int,
    printable_height: int,
    margins: Tuple[float, float, float, float],
    fonts: Dict[TextStyle, any],
    base_font_size: int,
) -> List[np.ndarray]:
    """
    Render parsed elements onto pages.

    Args:
        elements: List of parsed elements
        page_width: Full page width in pixels
        page_height: Full page height in pixels
        printable_width: Printable area width in pixels
        printable_height: Printable area height in pixels
        margins: Margins in inches (top, right, bottom, left)
        fonts: Dictionary of fonts for different styles
        base_font_size: Base font size in points

    Returns:
        List of rendered pages as numpy arrays
    """
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        raise ImportError(
            "Pillow (PIL) is required for markdown rendering. "
            "Install with: pip install 'pydigi[image]' or pip install Pillow"
        )

    pages = []

    # Create first page
    img = Image.new("L", (page_width, page_height), color=255)
    draw = ImageDraw.Draw(img)

    # Calculate margins in pixels
    margin_top, margin_right, margin_bottom, margin_left = margins
    margin_left_px = int(margin_left * _calculate_horizontal_dpi(page_width))
    margin_top_px = int(margin_top * WEFAX_LPI)

    # Current position
    y = margin_top_px
    x = margin_left_px  # Track horizontal position for inline elements

    # Get base line height
    base_font = fonts[TextStyle.NORMAL]
    try:
        bbox = draw.textbbox((0, 0), "Ayg", font=base_font)
        base_line_height = bbox[3] - bbox[1]
    except AttributeError:
        _, base_line_height = draw.textsize("Ayg", font=base_font)

    line_spacing = int(base_line_height * 1.2)

    for element in elements:
        # Check if we need a new page
        if y + line_spacing * 2 > margin_top_px + printable_height:
            # Save current page
            pages.append(np.array(img, dtype=np.uint8))

            # Create new page
            img = Image.new("L", (page_width, page_height), color=255)
            draw = ImageDraw.Draw(img)
            y = margin_top_px
            x = margin_left_px

        if isinstance(element, HeaderElement):
            # Render header with larger font (headers are always bold by default)
            header_font_size = base_font_size + (6 - element.level) * 4
            try:
                from PIL import ImageFont
                header_font_bold = ImageFont.truetype(_get_bundled_font_path(TextStyle.BOLD), header_font_size)
                header_font_normal = ImageFont.truetype(_get_bundled_font_path(TextStyle.NORMAL), header_font_size)
                header_font_code = ImageFont.truetype(_get_bundled_font_path(TextStyle.CODE), int(header_font_size * 0.9))
            except:
                header_font_bold = fonts[TextStyle.BOLD]
                header_font_normal = fonts[TextStyle.NORMAL]
                header_font_code = fonts[TextStyle.CODE]

            # Parse inline markdown in header
            inline_elements = _parse_inline_markdown(element.text)

            current_x = margin_left_px
            max_height = 0

            for inline_elem in inline_elements:
                # Headers are bold by default, but support code inline
                if inline_elem.style == TextStyle.CODE:
                    h_font = header_font_code
                else:
                    h_font = header_font_bold

                # Add light gray background for inline code
                if inline_elem.style == TextStyle.CODE:
                    try:
                        bbox = draw.textbbox((current_x, y), inline_elem.text, font=h_font)
                        bg_rect = [bbox[0] - 2, bbox[1] - 2, bbox[2] + 2, bbox[3] + 2]
                    except AttributeError:
                        width, height = draw.textsize(inline_elem.text, font=h_font)
                        bg_rect = [current_x - 2, y - 2, current_x + width + 2, y + height + 2]
                    draw.rectangle(bg_rect, fill=230)

                draw.text((current_x, y), inline_elem.text, fill=0, font=h_font)

                # Advance x
                try:
                    bbox = draw.textbbox((0, 0), inline_elem.text, font=h_font)
                    text_width = bbox[2] - bbox[0]
                    text_height = bbox[3] - bbox[1]
                except AttributeError:
                    text_width, text_height = draw.textsize(inline_elem.text, font=h_font)

                current_x += text_width
                max_height = max(max_height, text_height)

            y += int(max_height * 1.5)
            x = margin_left_px  # Reset x for next line

        elif isinstance(element, TextElement):
            # Render text with appropriate style (inline)
            font = fonts.get(element.style, fonts[TextStyle.NORMAL])

            # Add light gray background for code
            if element.style == TextStyle.CODE:
                try:
                    bbox = draw.textbbox((x, y), element.text, font=font)
                    bg_rect = [bbox[0] - 2, bbox[1] - 2, bbox[2] + 2, bbox[3] + 2]
                except AttributeError:
                    width, height = draw.textsize(element.text, font=font)
                    bg_rect = [x - 2, y - 2, x + width + 2, y + height + 2]

                draw.rectangle(bg_rect, fill=230)

            draw.text((x, y), element.text, fill=0, font=font)

            # Advance x position for next inline element
            try:
                bbox = draw.textbbox((0, 0), element.text, font=font)
                text_width = bbox[2] - bbox[0]
            except AttributeError:
                text_width, _ = draw.textsize(element.text, font=font)

            x += text_width

        elif isinstance(element, LineBreakElement):
            y += line_spacing
            x = margin_left_px  # Reset x for next line

        elif isinstance(element, ListItemElement):
            # Render list item with bullet or number
            indent_px = element.indent * 20
            list_x = margin_left_px + indent_px

            if element.ordered:
                prefix = f"{element.number}. "
            else:
                prefix = "• "

            # Draw prefix
            font = fonts[TextStyle.NORMAL]
            draw.text((list_x, y), prefix, fill=0, font=font)

            # Advance x past the prefix
            try:
                bbox = draw.textbbox((0, 0), prefix, font=font)
                prefix_width = bbox[2] - bbox[0]
            except AttributeError:
                prefix_width, _ = draw.textsize(prefix, font=font)

            current_x = list_x + prefix_width

            # Parse and render inline markdown in list item text
            inline_elements = _parse_inline_markdown(element.text)
            for inline_elem in inline_elements:
                inline_font = fonts.get(inline_elem.style, fonts[TextStyle.NORMAL])

                # Add light gray background for inline code
                if inline_elem.style == TextStyle.CODE:
                    try:
                        bbox = draw.textbbox((current_x, y), inline_elem.text, font=inline_font)
                        bg_rect = [bbox[0] - 2, bbox[1] - 2, bbox[2] + 2, bbox[3] + 2]
                    except AttributeError:
                        width, height = draw.textsize(inline_elem.text, font=inline_font)
                        bg_rect = [current_x - 2, y - 2, current_x + width + 2, y + height + 2]
                    draw.rectangle(bg_rect, fill=230)

                draw.text((current_x, y), inline_elem.text, fill=0, font=inline_font)

                # Advance x
                try:
                    bbox = draw.textbbox((0, 0), inline_elem.text, font=inline_font)
                    text_width = bbox[2] - bbox[0]
                except AttributeError:
                    text_width, _ = draw.textsize(inline_elem.text, font=inline_font)
                current_x += text_width

            y += line_spacing
            x = margin_left_px  # Reset x for next line

        elif isinstance(element, CodeBlockElement):
            # Render code block with gray background
            code_lines = element.code.split('\n')
            font = fonts[TextStyle.CODE]

            # Calculate code block height
            block_height = len(code_lines) * line_spacing + 10

            # Draw background
            draw.rectangle(
                [margin_left_px, y, margin_left_px + printable_width - 20, y + block_height],
                fill=230
            )

            # Draw code lines
            code_y = y + 5
            for code_line in code_lines:
                draw.text((margin_left_px + 10, code_y), code_line, fill=0, font=font)
                code_y += line_spacing

            y += block_height + 10
            x = margin_left_px  # Reset x for next line

        elif isinstance(element, HorizontalRuleElement):
            # Draw horizontal line
            draw.line(
                [(margin_left_px, y + 5), (margin_left_px + printable_width, y + 5)],
                fill=0,
                width=2
            )
            y += 20
            x = margin_left_px  # Reset x for next line

        elif isinstance(element, BlockquoteElement):
            # Draw blockquote with left border and inline markdown support
            border_x = margin_left_px + 10
            quote_x = border_x + 15

            # Parse inline markdown in blockquote text
            inline_elements = _parse_inline_markdown(element.text)

            # Calculate total height for border
            max_height = base_line_height

            # Draw left border
            draw.line(
                [(border_x, y), (border_x, y + max_height)],
                fill=100,
                width=3
            )

            # Render inline elements
            current_x = quote_x
            for inline_elem in inline_elements:
                # For blockquotes, use italic as base, but preserve bold/code styles
                if inline_elem.style == TextStyle.NORMAL:
                    inline_font = fonts[TextStyle.ITALIC]
                elif inline_elem.style == TextStyle.BOLD:
                    inline_font = fonts[TextStyle.BOLD_ITALIC]
                else:
                    inline_font = fonts.get(inline_elem.style, fonts[TextStyle.ITALIC])

                # Add light gray background for inline code
                if inline_elem.style == TextStyle.CODE:
                    try:
                        bbox = draw.textbbox((current_x, y), inline_elem.text, font=inline_font)
                        bg_rect = [bbox[0] - 2, bbox[1] - 2, bbox[2] + 2, bbox[3] + 2]
                    except AttributeError:
                        width, height = draw.textsize(inline_elem.text, font=inline_font)
                        bg_rect = [current_x - 2, y - 2, current_x + width + 2, y + height + 2]
                    draw.rectangle(bg_rect, fill=230)

                draw.text((current_x, y), inline_elem.text, fill=0, font=inline_font)

                # Advance x
                try:
                    bbox = draw.textbbox((0, 0), inline_elem.text, font=inline_font)
                    text_width = bbox[2] - bbox[0]
                except AttributeError:
                    text_width, _ = draw.textsize(inline_elem.text, font=inline_font)
                current_x += text_width

            y += line_spacing * 1.5
            x = margin_left_px  # Reset x for next line

    # Save last page
    if y > margin_top_px:
        pages.append(np.array(img, dtype=np.uint8))

    return pages


def render_markdown_for_wefax(
    markdown_text: str,
    mode: str,
    image_width: int,
    font_size: Optional[int] = None,
    margins: Tuple[float, float, float, float] = (1.0, 1.0, 1.0, 1.0),
) -> List[np.ndarray]:
    """
    Render markdown text as grayscale images for WEFAX transmission.

    Supports:
    - Headers (# ## ### #### ##### ######)
    - Bold (**text**)
    - Italic (*text*)
    - Bold+Italic (***text***)
    - Inline code (`code`)
    - Code blocks (```language...```)
    - Lists (ordered and unordered)
    - Blockquotes (>)
    - Horizontal rules (---)

    Args:
        markdown_text: Markdown formatted text
        mode: WEFAX mode name (e.g., "WEFAX_576", "WEFAX_288")
        image_width: Image width in pixels
        font_size: Base font size in points (auto-calculated if None)
        margins: Margins in inches (top, right, bottom, left)

    Returns:
        List of grayscale page images as numpy arrays

    Raises:
        ImportError: If Pillow or markdown2 is not installed
    """
    # Calculate page dimensions
    page_width, page_height, printable_width, printable_height = _calculate_page_dimensions(
        image_width, margins
    )

    # Calculate base font size if not provided
    if font_size is None:
        horizontal_dpi = _calculate_horizontal_dpi(image_width)
        if horizontal_dpi > 150:  # WEFAX_576
            font_size = 18
        else:  # WEFAX_288
            font_size = 16

    # Load fonts
    fonts = _load_fonts(font_size)

    # Parse markdown to elements
    elements = _parse_markdown_to_elements(markdown_text)

    # Render elements to pages
    pages = _render_elements_to_pages(
        elements,
        page_width,
        page_height,
        printable_width,
        printable_height,
        margins,
        fonts,
        font_size,
    )

    return pages
