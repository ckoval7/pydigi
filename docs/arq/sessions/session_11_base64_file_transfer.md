# Session 11: Base64 & File Transfer

**Duration**: 2-3 hours
**Priority**: MEDIUM
**Status**: ✅ Complete

## Goal

Implement Base64 encoding/decoding and file transfer functionality to allow sending and receiving binary files over ARQ connections. This matches fldigi's FLARQ file transfer feature, allowing images, documents, and other binary files to be transmitted reliably over radio.

## Prerequisites

- Sessions 1-9 complete (CRC, Frames, Blocks, Config/State, Protocol, Handlers, TX, RX, ABORT)
- Python 3.8+
- pytest installed
- fldigi source code available for reference

## Deliverables

1. Base64 codec module (`pydigi/arq/base64_codec.py`)
2. File transfer methods (`send_file()`, callbacks)
3. File reception and reassembly logic
4. Comprehensive tests (`tests/test_arq/test_base64_codec.py`, `tests/test_arq/test_file_transfer.py`)
5. File transfer example (`examples/arq_file_transfer.py`)
6. This session guide document

## Base64 & File Transfer Overview

FLARQ supports transferring files by encoding them in Base64 and wrapping them with special markers. This allows binary files to be reliably transmitted as text over the ARQ link.

### File Transfer Format

The file transfer format matches fldigi exactly:

```
ARQ:FILE::<filename>\n
ARQ:ENCODING::BASE64\n
ARQ:SIZE::<base64_size>\n
ARQ::STX\n
<base64 encoded data>
ARQ::ETX\n
```

### Key Markers

- **ARQ:FILE::** - Start of file transfer, followed by filename
- **ARQ:ENCODING::BASE64** - Indicates Base64 encoding
- **ARQ:SIZE::** - Size of base64 data (for progress tracking)
- **ARQ::STX** - Start of text/data marker
- **ARQ::ETX** - End of text/data marker

### Supported File Types

- Text files (ASCII, UTF-8)
- Email files
- Images (JPEG, PNG, GIF, etc.)
- Binary files (documents, archives, etc.)

All files are encoded using Base64 before transmission.

## Implementation Steps

### Step 1: Create Base64 Codec Module (45 minutes)

Create `pydigi/arq/base64_codec.py` based on fldigi's `flarq-src/b64.cxx`:

```python
"""Base64 encoding/decoding for ARQ file transfers."""

import base64
from typing import Union


class Base64Codec:
    """Base64 encoder/decoder matching fldigi's implementation.

    Args:
        crlf: If True, insert line breaks every 72 characters
    """

    LINELEN = 72  # Line length for CRLF mode

    def __init__(self, crlf: bool = False):
        self.crlf = crlf

    def encode(self, data: Union[bytes, str]) -> str:
        """Encode data to Base64 string."""
        # Convert string to bytes if needed
        if isinstance(data, str):
            data = data.encode('latin-1')

        # Use Python's base64 encoding
        encoded = base64.b64encode(data).decode('ascii')

        # Add line breaks if requested
        if self.crlf:
            lines = []
            for i in range(0, len(encoded), self.LINELEN):
                lines.append(encoded[i:i + self.LINELEN])
            return '\n'.join(lines) + '\n'

        return encoded

    def decode(self, data: str) -> bytes:
        """Decode Base64 string to binary data."""
        # Remove whitespace
        cleaned = ''.join(c for c in data if c > ' ')

        # Validate characters
        valid_chars = set('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=')
        for c in cleaned:
            if c not in valid_chars:
                raise ValueError("Illegal character in b64 file.")

        # Check length
        if len(cleaned) % 4 != 0:
            raise ValueError("b64 file length error.")

        # Decode
        return base64.b64decode(cleaned)
```

**Reference**: `fldigi/src/flarq-src/b64.cxx` and `b64.h`

### Step 2: Add File Transfer Methods to Protocol (60 minutes)

Add to `pydigi/arq/protocol.py`:

#### Import Base64 Codec

```python
from .base64_codec import Base64Codec
```

#### Add State Variables to `__init__()`

```python
# File transfer state
self._rx_file_active = False  # Currently receiving a file
self._rx_file_name = ""  # Name of file being received
self._rx_file_data = ""  # Accumulated file data (base64)
self._rx_file_size = 0  # Expected file size
self._rx_file_encoding = ""  # Encoding type

# Base64 codec for file transfers
self._b64_codec = Base64Codec(crlf=True)
```

#### Add File Callback

```python
self._rx_file_callback: Optional[Callable[[str, bytes], None]] = None

def set_rx_file_callback(self, callback: Callable[[str, bytes], None]) -> None:
    """Set callback for received files.

    Args:
        callback: Function that receives filename and file data (bytes)
    """
    self._rx_file_callback = callback
```

#### Implement send_file()

```python
def send_file(self, file_path: str, description: Optional[str] = None) -> None:
    """Send a file over ARQ link.

    Args:
        file_path: Path to file to send
        description: Optional description (not used)

    Raises:
        ARQConnectionError: If not connected
        FileNotFoundError: If file doesn't exist
    """
    if not self.state.is_connected():
        raise ARQConnectionError("Cannot send file: not connected")

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    # Read file
    with open(file_path, 'rb') as f:
        file_data = f.read()

    # Get filename
    filename = os.path.basename(file_path)

    # Encode to Base64
    b64_data = self._b64_codec.encode(file_data)
    b64_size = len(b64_data)

    # Build file transfer message
    message = f"ARQ:FILE::{filename}\n"
    message += "ARQ:ENCODING::BASE64\n"
    message += f"ARQ:SIZE::{b64_size}\n"
    message += "ARQ::STX\n"
    message += b64_data
    message += "ARQ::ETX\n"

    # Send using normal text transmission
    self.send_text(message)

    self._emit_status(f"Queued file '{filename}' for transmission ({len(file_data)} bytes)")
```

**Reference**: `fldigi/src/flarq-src/flarq.cxx` (sendBinaryFile, sendImageFile)

### Step 3: Implement File Reception (60 minutes)

Modify text reception to detect file transfer markers:

#### Update _process_received_text()

Replace the direct `_rx_text_callback` call with:

```python
# Process text (check for file transfer markers)
self._process_received_text(block['text'])
```

#### Add File Processing Method

```python
def _process_received_text(self, text: str) -> None:
    """Process received text for file transfer markers."""

    # Check for file transfer start
    if "ARQ:FILE::" in text:
        start_idx = text.find("ARQ:FILE::") + len("ARQ:FILE::")
        end_idx = text.find("\n", start_idx)
        if end_idx != -1:
            self._rx_file_name = text[start_idx:end_idx]
            self._rx_file_active = True
            self._rx_file_data = ""
            self._emit_status(f"Receiving file: {self._rx_file_name}")

    if "ARQ:ENCODING::BASE64" in text:
        self._rx_file_encoding = "BASE64"

    if "ARQ:SIZE::" in text:
        start_idx = text.find("ARQ:SIZE::") + len("ARQ:SIZE::")
        end_idx = text.find("\n", start_idx)
        if end_idx != -1:
            try:
                self._rx_file_size = int(text[start_idx:end_idx])
            except ValueError:
                pass

    # Check for data markers
    if "ARQ::STX" in text:
        stx_idx = text.find("ARQ::STX")
        data_start = stx_idx + len("ARQ::STX\n")

        etx_idx = text.find("ARQ::ETX", data_start)
        if etx_idx != -1:
            # Complete file in one chunk
            self._rx_file_data += text[data_start:etx_idx]
            self._complete_file_reception()
        else:
            # Partial data
            self._rx_file_data += text[data_start:]
    elif "ARQ::ETX" in text:
        etx_idx = text.find("ARQ::ETX")
        if self._rx_file_active:
            self._rx_file_data += text[:etx_idx]
            self._complete_file_reception()
    elif self._rx_file_active:
        # Accumulate file data
        if text and not text.startswith("ARQ::"):
            self._rx_file_data += text

    # If not receiving file, call text callback
    if not self._rx_file_active and self._rx_text_callback:
        if not any(m in text for m in ["ARQ:FILE::", "ARQ:ENCODING::", "ARQ:SIZE::", "ARQ::STX", "ARQ::ETX"]):
            self._rx_text_callback(text)
```

#### Add File Completion Method

```python
def _complete_file_reception(self) -> None:
    """Complete file reception and decode."""
    if not self._rx_file_name:
        self._emit_status("File reception error: no filename")
        self._rx_file_active = False
        return

    try:
        # Decode Base64 data
        file_data = self._b64_codec.decode(self._rx_file_data)

        # Call file callback
        if self._rx_file_callback:
            self._rx_file_callback(self._rx_file_name, file_data)

        self._emit_status(
            f"File received: {self._rx_file_name} ({len(file_data)} bytes)"
        )
    except Exception as e:
        self._emit_status(f"File decode error: {e}")

    # Reset file transfer state
    self._rx_file_active = False
    self._rx_file_name = ""
    self._rx_file_data = ""
    self._rx_file_size = 0
    self._rx_file_encoding = ""
```

**Reference**: `fldigi/src/flarq-src/flarq.cxx` (processArqText)

### Step 4: Create Tests (45 minutes)

Create comprehensive tests in `tests/test_arq/test_base64_codec.py` and `tests/test_arq/test_file_transfer.py`:

```python
def test_encode_decode_roundtrip():
    """Test encoding and decoding round trip."""
    codec = Base64Codec()
    test_data = b"Hello, World!"
    encoded = codec.encode(test_data)
    decoded = codec.decode(encoded)
    assert decoded == test_data

def test_send_file_basic():
    """Test sending a small file."""
    # Setup two connected stations
    arq1 = ARQProtocol(...)
    arq2 = ARQProtocol(...)

    # Connect stations...

    # Send file
    arq1.send_file(temp_file)

    # Process frames
    for _ in range(100):
        arq1.process()
        arq2.process()

    # Verify file received
    assert received_file == original_file
```

Run tests:

```bash
pytest tests/test_arq/test_base64_codec.py -v
pytest tests/test_arq/test_file_transfer.py -v
```

## Validation Checkpoint

✅ **Session 11 is complete when**:

1. ✅ Base64 codec implemented and tested
   - Encoding works correctly
   - Decoding works correctly
   - Round-trip tests pass
   - Line breaks (CRLF mode) work correctly

2. ✅ File transfer functionality implemented
   - `send_file()` method works
   - File format markers are correct
   - Reception and reassembly work
   - File callback is called with correct data

3. ✅ Tests pass
   - All Base64 codec tests pass
   - Basic file transfer tests pass
   - Binary file transfer works

4. ✅ Example works
   - `examples/arq_file_transfer.py` demonstrates file transfer
   - Both text and binary files transfer correctly

## Common Pitfalls

1. **Base64 padding**: Python's base64 is more forgiving than fldigi. Validate input properly.
2. **Line breaks**: CRLF mode should insert newlines every 72 characters.
3. **Marker detection**: Make sure all ARQ:: markers are detected correctly across block boundaries.
4. **File reassembly**: Files may arrive in multiple blocks - accumulate properly.
5. **Binary data**: Always handle files as binary (bytes), not text.

## Reference Files

Primary references in fldigi source:
- `fldigi/src/flarq-src/b64.cxx` - Base64 implementation
- `fldigi/src/flarq-src/b64.h` - Base64 header
- `fldigi/src/flarq-src/flarq.cxx` - File transfer functions (sendBinaryFile, sendImageFile, processArqText)

Key markers defined in `flarq.cxx`:
```cpp
std::string arqstart = "ARQ::STX\n";
std::string arqend   = "ARQ::ETX\n";
std::string arqfile = "ARQ:FILE::";
std::string arqbase64 = "ARQ:ENCODING::BASE64\n";
```

## Next Steps

After completing Session 11:

→ **Session 12**: Integration Testing
   Test complete ARQ system with real data transfers

→ **Session 13**: Documentation & Polish
   Complete API documentation and user guides

→ **Session 14** (Optional): Interoperability Testing
   Test with actual fldigi if desired

## Progress Check

- [x] Base64 codec implementation
- [x] File transfer methods
- [x] File reception and reassembly
- [x] Tests created and passing
- [x] Example created
- [x] Documentation complete

**Status**: ✅ Session 11 Complete!
