"""
Base64 encoding/decoding for ARQ file transfers.

This module provides Base64 encoding and decoding functionality that matches
the behavior of fldigi's b64.cxx implementation. It supports optional CRLF
line breaks at 72 characters for compatibility with email and text-based
protocols.

Reference: fldigi/src/flarq-src/b64.cxx
"""

import base64
from typing import Union


class Base64Codec:
    """
    Base64 encoder/decoder matching fldigi's implementation.

    This class provides Base64 encoding and decoding with optional line breaks
    at 72 characters (LINELEN in fldigi). The line breaks can be enabled for
    text-based protocols that require fixed-width lines.

    Args:
        crlf: If True, insert line breaks every 72 characters (default: False)

    Example:
        >>> codec = Base64Codec(crlf=True)
        >>> encoded = codec.encode(b"Hello, World!")
        >>> decoded = codec.decode(encoded)
        >>> decoded == b"Hello, World!"
        True
    """

    LINELEN = 72  # Line length for CRLF mode (matches fldigi)

    def __init__(self, crlf: bool = False):
        """
        Initialize the Base64 codec.

        Args:
            crlf: If True, insert newlines every 72 characters
        """
        self.crlf = crlf

    def encode(self, data: Union[bytes, str]) -> str:
        """
        Encode data to Base64 string.

        Args:
            data: Binary data or string to encode

        Returns:
            Base64 encoded string, optionally with line breaks

        Example:
            >>> codec = Base64Codec()
            >>> codec.encode(b"test")
            'dGVzdA=='
        """
        # Convert string to bytes if needed
        if isinstance(data, str):
            data = data.encode('latin-1')

        # Use Python's base64 encoding
        encoded = base64.b64encode(data).decode('ascii')

        # Add line breaks if requested (matching fldigi behavior)
        if self.crlf:
            # Insert newline every LINELEN characters
            lines = []
            for i in range(0, len(encoded), self.LINELEN):
                lines.append(encoded[i:i + self.LINELEN])
            # Join with newlines and add final newline
            return '\n'.join(lines) + '\n'

        return encoded

    def decode(self, data: str) -> bytes:
        """
        Decode Base64 string to binary data.

        This method is tolerant of whitespace and line breaks, matching
        fldigi's behavior. Invalid characters will raise a decoding error.

        Args:
            data: Base64 encoded string (may contain whitespace/newlines)

        Returns:
            Decoded binary data

        Raises:
            ValueError: If the input contains invalid Base64 characters

        Example:
            >>> codec = Base64Codec()
            >>> codec.decode('dGVzdA==')
            b'test'
        """
        # Remove whitespace (spaces, newlines, etc.) - matches fldigi behavior
        # fldigi skips characters <= ' ' (ASCII 32)
        cleaned = ''.join(c for c in data if c > ' ')

        # Validate that all characters are valid Base64 (matching fldigi)
        # Valid chars: A-Z, a-z, 0-9, +, /, =
        valid_chars = set('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=')
        for c in cleaned:
            if c not in valid_chars:
                raise ValueError("Illegal character in b64 file.")

        # Check length (must be multiple of 4 after removing padding)
        if len(cleaned) % 4 != 0:
            raise ValueError("b64 file length error.")

        try:
            # Decode using Python's base64
            return base64.b64decode(cleaned)
        except Exception as e:
            # Any other errors
            raise ValueError("Illegal character in b64 file.")


def encode_file(file_path: str, crlf: bool = True) -> str:
    """
    Encode a file to Base64 string.

    Convenience function to read a file and encode it to Base64.

    Args:
        file_path: Path to file to encode
        crlf: If True, insert line breaks every 72 characters

    Returns:
        Base64 encoded string

    Raises:
        FileNotFoundError: If file doesn't exist
        IOError: If file cannot be read

    Example:
        >>> encoded = encode_file('/path/to/image.png')
        >>> len(encoded) > 0
        True
    """
    with open(file_path, 'rb') as f:
        data = f.read()

    codec = Base64Codec(crlf=crlf)
    return codec.encode(data)


def decode_file(encoded_data: str, output_path: str) -> int:
    """
    Decode Base64 string and write to file.

    Convenience function to decode Base64 data and save to a file.

    Args:
        encoded_data: Base64 encoded string
        output_path: Path where decoded file should be saved

    Returns:
        Number of bytes written

    Raises:
        ValueError: If Base64 data is invalid
        IOError: If file cannot be written

    Example:
        >>> decode_file('dGVzdA==', '/tmp/test.bin')
        4
    """
    codec = Base64Codec()
    data = codec.decode(encoded_data)

    with open(output_path, 'wb') as f:
        f.write(data)

    return len(data)
