# PyDigi API Standard

**Version:** 1.0
**Last Updated:** 2025-12-24

This document defines the unified API standard for all PyDigi modem implementations.

---

## Design Principles

1. **Consistency First**: All modems follow identical patterns
2. **Inheritance-Based**: Proper use of base class methods
3. **Type-Safe**: Complete type hints on all public APIs
4. **Configurable**: Users can control key parameters
5. **Sensible Defaults**: Works out-of-the-box with minimal config

---

## Base Class Contract

All modems MUST inherit from `Modem` (defined in `pydigi.modems.base`).

### Required Method Implementations

```python
from abc import ABC, abstractmethod
import numpy as np
from typing import Optional

class Modem(ABC):
    """Base class for all modem implementations."""

    def __init__(self,
                 sample_rate: int = 8000,
                 leading_silence: float = 0.0,
                 trailing_silence: float = 0.0):
        """Initialize modem with sample rate and silence padding."""
        self.sample_rate = sample_rate
        self.leading_silence = leading_silence
        self.trailing_silence = trailing_silence

    @abstractmethod
    def tx_init(self) -> None:
        """Initialize transmitter state. Called before tx_process()."""
        pass

    @abstractmethod
    def tx_process(self, text: str) -> np.ndarray:
        """
        Generate modulated signal from text.

        Args:
            text: Text to transmit

        Returns:
            numpy array of float32 samples, normalized to [-1.0, 1.0]
        """
        pass

    def modulate(self,
                 text: str,
                 frequency: Optional[float] = None,
                 sample_rate: Optional[float] = None,
                 leading_silence: Optional[float] = None,
                 trailing_silence: Optional[float] = None) -> np.ndarray:
        """
        Public API: Generate modulated signal.

        Args:
            text: Text to transmit
            frequency: Optional carrier frequency override (Hz)
            sample_rate: Optional sample rate override (Hz)
            leading_silence: Duration of silence in seconds to add before signal
            trailing_silence: Duration of silence in seconds to add after signal

        Returns:
            numpy array of float32 samples, normalized to [-1.0, 1.0]
        """
        # Store original values
        original_freq = getattr(self, 'frequency', None)
        original_sr = self.sample_rate

        # Apply overrides if provided
        if frequency is not None:
            self.frequency = frequency
        if sample_rate is not None:
            self.sample_rate = sample_rate

        # Determine silence durations
        lead_silence = leading_silence if leading_silence is not None else self.leading_silence
        trail_silence = trailing_silence if trailing_silence is not None else self.trailing_silence

        # Initialize and process
        self.tx_init()
        signal = self.tx_process(text)

        # Add silence padding if requested
        if lead_silence > 0 or trail_silence > 0:
            lead_samples = int(lead_silence * self.sample_rate)
            trail_samples = int(trail_silence * self.sample_rate)

            if lead_samples > 0 or trail_samples > 0:
                leading_zeros = np.zeros(lead_samples, dtype=signal.dtype)
                trailing_zeros = np.zeros(trail_samples, dtype=signal.dtype)
                signal = np.concatenate([leading_zeros, signal, trailing_zeros])

        # Restore original values
        if frequency is not None and original_freq is not None:
            self.frequency = original_freq
        if sample_rate is not None:
            self.sample_rate = original_sr

        return signal
```

---

## Standard `__init__()` Signature

### Parameter Naming Rules

**MUST use these exact names:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `sample_rate` | `int` | Sample rate in Hz (NOT `samplerate` or `sr`) |
| `frequency` | `float` | Carrier/base frequency in Hz (NOT `freq`) |
| `tx_amplitude` | `float` | Transmit amplitude, 0.0 to 1.0 (default: 0.8) |
| `baud` | `float` | Baud rate (symbols/sec) for baudrate-based modes |
| `symlen` | `int` | Symbol length in samples (for symbol-based modes) |

### Parameter Ordering Rules

**Standard order for common parameters:**

```python
def __init__(self,
             # Primary mode-specific parameters first
             mode_param1,
             mode_param2,
             # Then standard parameters in this order:
             sample_rate: int = 8000,
             frequency: float = 1000,
             tx_amplitude: float = 0.8,
             # Then optional/advanced parameters
             **kwargs):
```

### Examples by Modem Category

#### Simple FSK/PSK Modems (CW, RTTY, PSK, QPSK)
```python
def __init__(self,
             baud: float,                    # Primary parameter
             sample_rate: int = 8000,        # Standard parameters
             frequency: float = 1000,
             tx_amplitude: float = 0.8,
             # Mode-specific options
             **mode_kwargs):
```

#### Multi-tone Modems (MFSK, Olivia, Contestia)
```python
def __init__(self,
             tones: int,                     # Primary parameter
             bandwidth: int,                 # Secondary parameter
             sample_rate: int = 8000,        # Standard parameters
             frequency: float = 1500,
             tx_amplitude: float = 0.8,
             **mode_kwargs):
```

#### Symbol-based Modems (DominoEX, Thor, Throb)
```python
def __init__(self,
             symlen: int,                    # Primary parameter (samples per symbol)
             sample_rate: int = 8000,        # Standard parameters
             frequency: float = 1500,
             tx_amplitude: float = 0.8,
             **mode_kwargs):
```

---

## Silence Padding

### Overview

All modems support configurable silence padding at the start and end of generated signals. This is useful for:
- Ensuring receiver synchronization (PTT delays, VOX activation)
- Creating clean transitions between transmissions
- Testing and debugging (visual separation in audio editors)
- Compatibility with hardware that needs lead-in time

### Configuration

Silence padding can be configured in two ways:

**1. At modem initialization (default for all transmissions):**
```python
modem = PSK31(leading_silence=0.5, trailing_silence=0.5)
audio = modem.modulate("TEST")  # Includes 0.5s silence on each end
```

**2. Per transmission (overrides instance defaults):**
```python
modem = PSK31()  # No default silence
audio = modem.modulate("TEST", leading_silence=0.3, trailing_silence=0.2)
```

### Implementation

The base `Modem` class handles all silence padding automatically in the `modulate()` method:
- Silence is added AFTER the signal is generated by `tx_process()`
- Silence is pure zeros (amplitude = 0.0)
- Sample count is calculated as `int(silence_duration * sample_rate)`
- Silence uses the same dtype as the signal (typically `float32`)

**Modem implementers do NOT need to handle silence padding** - it's handled by the base class.

### Parameter Naming

| Parameter | Type | Description |
|-----------|------|-------------|
| `leading_silence` | `float` | Duration in seconds to add before signal (default: 0.0) |
| `trailing_silence` | `float` | Duration in seconds to add after signal (default: 0.0) |

---

## Standard `modulate()` Signature

**All modems MUST use this exact signature:**

```python
def modulate(self,
             text: str,
             frequency: Optional[float] = None,
             sample_rate: Optional[float] = None,
             leading_silence: Optional[float] = None,
             trailing_silence: Optional[float] = None) -> np.ndarray:
    """
    Generate modulated audio signal from text.

    Args:
        text: Text string to transmit
        frequency: Optional carrier frequency override (Hz)
        sample_rate: Optional sample rate override (Hz)
        leading_silence: Duration of silence in seconds to add before signal
        trailing_silence: Duration of silence in seconds to add after signal

    Returns:
        Numpy array of float32 samples, normalized to [-1.0, 1.0]

    Example:
        >>> modem = PSK31()
        >>> signal = modem.modulate("CQ CQ DE W1ABC")
        >>> save_wav("output.wav", signal, 8000)
        >>> # Add 0.5s silence before and after
        >>> signal = modem.modulate("TEST", leading_silence=0.5, trailing_silence=0.5)
    """
    # Default implementation in base class handles parameter overrides
    # and calls tx_init() + tx_process()
    pass
```

**Rules:**
1. DO NOT override `modulate()` unless absolutely necessary
2. Implement `tx_init()` and `tx_process()` instead
3. If you must override, call `super().modulate()` first
4. Always return `np.ndarray` of `float32`
5. Always normalize output to [-1.0, 1.0]

---

## Standard `tx_process()` Signature

**CRITICAL: This signature is FIXED and cannot be changed:**

```python
def tx_process(self, text: str) -> np.ndarray:
    """
    Internal method: Generate modulated signal from text.

    Args:
        text: Text to transmit (only parameter allowed!)

    Returns:
        Numpy array of float32 samples

    Note:
        - Access frequency via self.frequency
        - Access sample_rate via self.sample_rate
        - Access tx_amplitude via self.tx_amplitude
        - DO NOT add extra parameters to this method!
    """
    pass
```

**Inheritance Contract:**
- MUST take exactly one parameter: `text: str`
- MUST NOT add `frequency`, `sample_rate`, or any other parameters
- MUST access configuration via `self.*` attributes
- MUST return `np.ndarray`

---

## Preamble and Postamble Handling

### Standard Pattern

All modems should handle preamble/postamble consistently:

```python
class MyModem(Modem):
    def __init__(self,
                 sample_rate: int = 8000,
                 frequency: float = 1000,
                 tx_amplitude: float = 0.8,
                 preamble_symbols: Optional[int] = None,
                 postamble_symbols: Optional[int] = None):
        super().__init__(sample_rate)
        self.frequency = frequency
        self.tx_amplitude = tx_amplitude
        self.preamble_symbols = preamble_symbols
        self.postamble_symbols = postamble_symbols

    def tx_process(self, text: str) -> np.ndarray:
        samples = []

        # Generate preamble
        if self.preamble_symbols:
            preamble = self._generate_preamble(self.preamble_symbols)
            samples.append(preamble)

        # Generate data
        data = self._encode_and_modulate(text)
        samples.append(data)

        # Generate postamble
        if self.postamble_symbols:
            postamble = self._generate_postamble(self.postamble_symbols)
            samples.append(postamble)

        return np.concatenate(samples)
```

### Standard Parameter Names

| Parameter | Type | Description |
|-----------|------|-------------|
| `preamble_symbols` | `Optional[int]` | Number of preamble symbols (None = auto) |
| `postamble_symbols` | `Optional[int]` | Number of postamble symbols (None = auto) |

**For character-based modes (RTTY):**
- Use `preamble_chars` and `postamble_chars` instead

---

## Amplitude and Normalization

### Standard Approach

1. **Add `tx_amplitude` parameter to all modems**
   ```python
   def __init__(self, ..., tx_amplitude: float = 0.8):
       self.tx_amplitude = tx_amplitude
   ```

2. **Apply amplitude scaling in `tx_process()`**
   ```python
   def tx_process(self, text: str) -> np.ndarray:
       # Generate signal
       signal = self._modulate(text)

       # Scale to tx_amplitude
       signal = signal * self.tx_amplitude

       # Normalize to prevent clipping
       max_val = np.max(np.abs(signal))
       if max_val > 1.0:
           signal = signal / max_val

       return signal.astype(np.float32)
   ```

3. **Return `float32` arrays**
   - Always cast final output to `np.float32`
   - Ensures consistent memory usage

---

## Type Hints Standard

### Required Type Hints

**ALL public methods MUST have complete type hints:**

```python
from typing import Optional, Union, List, Tuple
import numpy as np

class MyModem(Modem):
    def __init__(self,
                 baud: float,
                 sample_rate: int = 8000,
                 frequency: float = 1000,
                 tx_amplitude: float = 0.8) -> None:
        """Type hints on __init__ (return None)."""
        pass

    def tx_init(self) -> None:
        """Type hints on tx_init (return None)."""
        pass

    def tx_process(self, text: str) -> np.ndarray:
        """Type hints on tx_process (return np.ndarray)."""
        pass

    def modulate(self,
                 text: str,
                 frequency: Optional[float] = None,
                 sample_rate: Optional[float] = None) -> np.ndarray:
        """Type hints on modulate (return np.ndarray)."""
        pass
```

### Standard Imports

```python
from typing import Optional, Union, List, Tuple, Dict, Any
import numpy as np
import numpy.typing as npt

# For numpy array type hints (optional, but recommended):
NDArrayFloat = npt.NDArray[np.float32]
```

---

## Docstring Standard

### Format: Google Style

```python
def modulate(self, text: str, frequency: Optional[float] = None) -> np.ndarray:
    """
    Generate modulated audio signal from text.

    This method generates a complete transmission including preamble,
    data, and postamble suitable for over-the-air transmission or
    saving to a WAV file.

    Args:
        text: ASCII text string to transmit. Special characters may be
            filtered or replaced depending on modem character set.
        frequency: Optional carrier frequency in Hz. If None, uses the
            frequency specified in __init__(). Typical range: 500-3000 Hz.
        sample_rate: Optional sample rate in Hz. If None, uses the
            sample_rate specified in __init__(). Typical: 8000 or 11025 Hz.

    Returns:
        Numpy array of float32 audio samples, normalized to [-1.0, 1.0].
        Length depends on text length and modem baud rate.

    Raises:
        ValueError: If text contains characters not supported by this modem.

    Example:
        >>> modem = PSK31()
        >>> signal = modem.modulate("CQ CQ DE W1ABC")
        >>> print(f"Generated {len(signal)} samples")
        >>> save_wav("cq.wav", signal, 8000)

    Note:
        The returned signal is ready for transmission without further
        processing. For SSB transmission, feed to upper sideband modulator.
    """
    pass
```

---

## Configuration Storage

### Store ALL Parameters as Instance Attributes

```python
class MyModem(Modem):
    def __init__(self,
                 baud: float,
                 sample_rate: int = 8000,
                 frequency: float = 1000,
                 tx_amplitude: float = 0.8,
                 custom_param: int = 42):
        super().__init__(sample_rate)

        # Store ALL parameters
        self.baud = baud
        self.frequency = frequency
        self.tx_amplitude = tx_amplitude
        self.custom_param = custom_param

        # Computed values (marked with underscore)
        self._samples_per_symbol = int(self.sample_rate / self.baud)
```

**Rules:**
1. Store parameters exactly as passed (don't compute immediately)
2. Use `_underscore` prefix for computed/derived values
3. Recompute derived values if `sample_rate` changes
4. Allow read access to all config via properties

---

## Modem Variants and Convenience Instances

### Pattern: Module-Level Instances

```python
# In pydigi/modems/__init__.py

from .psk import PSK

# Create convenience instances with standard configurations
PSK31 = PSK(baud=31.25)
PSK63 = PSK(baud=62.5)
PSK125 = PSK(baud=125)
PSK250 = PSK(baud=250)
PSK500 = PSK(baud=500)
PSK1000 = PSK(baud=1000)

__all__ = [
    'PSK',          # Base class
    'PSK31',        # Convenience instances
    'PSK63',
    'PSK125',
    'PSK250',
    'PSK500',
    'PSK1000',
]
```

### Usage Examples

```python
# Users can import pre-configured modems
from pydigi import PSK31, PSK63

signal = PSK31.modulate("CQ CQ DE W1ABC")

# Or create custom configurations
from pydigi import PSK

custom_modem = PSK(baud=31.25, frequency=1500, tx_amplitude=0.9)
signal = custom_modem.modulate("Custom settings")
```

---

## Special Cases: Non-Text Modems

### WEFAX (Image Transmission)

WEFAX is unique - it transmits images rather than text. It follows a dual-method approach:

**Primary Interface: `transmit_image()`**
```python
def transmit_image(self,
                  image: Union[np.ndarray, str, Path],
                  lpm: Optional[int] = None,
                  include_apt_start: bool = True,
                  include_phasing: bool = True,
                  include_apt_stop: bool = True,
                  include_black: bool = True) -> np.ndarray:
    """
    Transmit an image using WEFAX modulation.

    Args:
        image: Input image (numpy array, PIL Image, or file path)
        lpm: Lines per minute (default: use mode's default_lpm)
        include_apt_start: Include APT START tone (default: True)
        include_phasing: Include phasing pattern (default: True)
        include_apt_stop: Include APT STOP tone (default: True)
        include_black: Include black signal (default: True)

    Returns:
        Audio samples for complete WEFAX transmission
    """
```

**Compatibility Interface: `tx_process()`**
```python
def tx_process(self, text: str) -> np.ndarray:
    """
    Generate WEFAX test pattern (text parameter ignored).

    For WEFAX, the text parameter is ignored and a black/white
    bar test pattern is generated instead. This maintains API
    compatibility with the base Modem class.

    Use transmit_image() for actual image transmission.
    """
```

**Usage Example:**
```python
from pydigi import WEFAX576
from pydigi.utils.audio import save_wav

# Create WEFAX modem
wefax = WEFAX576()

# Transmit an image file
audio = wefax.transmit_image("weather_map.png")
save_wav("wefax_output.wav", audio, 11025)

# Transmit from numpy array
import numpy as np
img = np.random.randint(0, 256, (200, 1809), dtype=np.uint8)
audio = wefax.transmit_image(img, lpm=120)

# Generate test pattern (using standard modulate API)
audio = wefax.modulate("")  # Generates test pattern
```

**Image Input Handling:**
- Accepts numpy arrays (H, W) with grayscale values 0-255
- Accepts PIL Image objects (converted to grayscale)
- Accepts file paths (requires Pillow: `pip install Pillow`)
- Automatically resizes to WEFAX width (1809 for WEFAX-576, 904 for WEFAX-288)

**Key Differences from Text Modems:**
1. Primary interface is `transmit_image()`, not `modulate()`
2. `tx_process()` generates test pattern instead of processing text
3. Fixed sample rate: 11025 Hz (matches fldigi)
4. FM modulation where pixel values map to frequencies

**Installation Note:**
```bash
# For image file support
pip install pydigi[image]
```

---

## Migration Guide

### For Each Modem Implementation

**Step 1: Update `__init__()` signature**
- Rename parameters: `samplerate` → `sample_rate`, `freq` → `frequency`
- Add `tx_amplitude` parameter if missing (default: 0.8)
- Reorder parameters: mode-specific → standard → optional

**Step 2: Fix `tx_process()` signature**
- MUST be exactly: `def tx_process(self, text: str) -> np.ndarray:`
- Remove any extra parameters (frequency, sample_rate, etc.)
- Access via `self.frequency`, `self.sample_rate` instead

**Step 3: Remove `modulate()` override if possible**
- Use base class implementation
- Only override if absolutely necessary (special parameter handling)

**Step 4: Add type hints**
- Import: `from typing import Optional`
- Add hints to all parameters and return types

**Step 5: Apply amplitude scaling**
- Multiply signal by `self.tx_amplitude`
- Normalize to [-1.0, 1.0] range
- Cast to `np.float32` before returning

**Step 6: Update docstrings**
- Use Google-style format
- Document all parameters
- Include example usage

---

## Priority Order for Migration

### Critical (Fix Immediately)

1. **Throb** - `tx_process()` has wrong signature (breaks inheritance)
2. **MFSK** - Doesn't implement `tx_process()` at all
3. **Olivia** - Doesn't implement `tx_process()` properly
4. **Contestia** - Same as Olivia
5. **DominoEX** - Overrides `modulate()` unnecessarily
6. **Thor** - Overrides `modulate()` unnecessarily

### High Priority (Standardize Next)

7. **Add `tx_amplitude`** to all modems missing it:
   - DominoEX, Thor, Throb, MFSK, Olivia, Contestia, FSQ, MT63, IFKP

8. **Parameter renaming**:
   - Thor: `samplerate` → `sample_rate`
   - Any others with non-standard names

### Medium Priority

9. **Type hints**: Add to all modems missing them
10. **Docstrings**: Standardize format across all modems

### Low Priority

11. **Preamble/postamble standardization**: Unify parameter names
12. **Filter control**: Extend to more modems if applicable

---

## Validation Checklist

For each modem, verify:

- [ ] Inherits from `Modem` base class
- [ ] `__init__()` uses standard parameter names (`sample_rate`, `frequency`, `tx_amplitude`)
- [ ] `__init__()` has type hints on all parameters
- [ ] `tx_init()` is implemented
- [ ] `tx_process(self, text: str)` has correct signature (only `text` parameter)
- [ ] `tx_process()` returns `np.ndarray` of `float32`
- [ ] `modulate()` NOT overridden (unless absolutely necessary)
- [ ] All config stored as instance attributes
- [ ] Output normalized to [-1.0, 1.0]
- [ ] Docstrings in Google-style format
- [ ] Example usage in docstring

---

## Files to Update

### Core Files
- `/home/corey/pydigi/pydigi/modems/base.py` - Update base class
- `/home/corey/pydigi/pydigi/modems/__init__.py` - Update exports

### Modem Implementations (by priority)
1. `/home/corey/pydigi/pydigi/modems/throb.py` ⚠️ CRITICAL
2. `/home/corey/pydigi/pydigi/modems/mfsk.py` ⚠️ CRITICAL
3. `/home/corey/pydigi/pydigi/modems/olivia.py` ⚠️ CRITICAL
4. `/home/corey/pydigi/pydigi/modems/contestia.py` ⚠️ CRITICAL
5. `/home/corey/pydigi/pydigi/modems/dominoex.py`
6. `/home/corey/pydigi/pydigi/modems/thor.py`
7. `/home/corey/pydigi/pydigi/modems/fsq.py`
8. `/home/corey/pydigi/pydigi/modems/mt63.py`
9. `/home/corey/pydigi/pydigi/modems/ifkp.py`
10. `/home/corey/pydigi/pydigi/modems/hell.py`
11. `/home/corey/pydigi/pydigi/modems/cw.py`
12. `/home/corey/pydigi/pydigi/modems/rtty.py`
13. `/home/corey/pydigi/pydigi/modems/psk.py`
14. `/home/corey/pydigi/pydigi/modems/qpsk.py`
15. `/home/corey/pydigi/pydigi/modems/psk8.py`
16. `/home/corey/pydigi/pydigi/modems/psk8_fec.py`
17. `/home/corey/pydigi/pydigi/modems/psk_extended.py`

---

## Testing Strategy

After each change:
1. Import the modem: `from pydigi import ModemName`
2. Instantiate: `modem = ModemName()`
3. Generate signal: `signal = modem.modulate("TEST")`
4. Verify return type: `isinstance(signal, np.ndarray)`
5. Verify dtype: `signal.dtype == np.float32`
6. Verify range: `-1.0 <= signal.min()` and `signal.max() <= 1.0`
7. Generate WAV: `save_wav("test.wav", signal, 8000)`
8. Decode with fldigi to verify correctness

---

**End of API Standard Document**
