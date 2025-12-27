# Why PSK and RTTY Use Different Approaches

## TL;DR

- **PSK**: Baseband I/Q → Filter → Quadrature modulation ✓
- **RTTY**: Direct FSK at carrier frequency ✓

## The Difference

### PSK (Phase Shift Keying)

PSK is a **linear modulation** that works perfectly with I/Q baseband:

```
Baseband:  I(t), Q(t)  (in-phase and quadrature components)
Filter:    Lowpass on I and Q separately
Modulate:  output = I(t)×cos(ωt) + Q(t)×sin(ωt)
```

This is the **standard SDR approach** for PSK/QAM modulation.

**Why it works:**
- Phase information is preserved in I/Q components
- Linear filtering maintains phase relationships
- Quadrature modulation cleanly mixes to carrier
- Result: Clean PSK at carrier frequency

### RTTY (FSK - Frequency Shift Keying)

FSK is a **frequency modulation** that doesn't work well with simple I/Q baseband:

**What happens if we try baseband FSK:**
```
Baseband:  cos(2π×shift/2×t)  (mark or space tone at baseband)
Carrier:   cos(2π×fc×t)
Product:   cos(2π×shift/2×t) × cos(2π×fc×t)
```

Using the trig identity: cos(A)×cos(B) = 0.5[cos(A+B) + cos(A-B)]

**Result:**
```
= 0.5[cos(2π(fc + shift/2)t) + cos(2π(fc - shift/2)t)]
```

This creates **both upper and lower sidebands** - basically double-sideband AM, not clean FSK!

**What we want for FSK:**
```
Mark:  cos(2π(fc + shift/2)t)  ONLY
Space: cos(2π(fc - shift/2)t)  ONLY
```

**Solution:** Generate FSK **directly at carrier frequency**
- Mark: Generate tone at fc + shift/2
- Space: Generate tone at fc - shift/2
- No mixing needed, no unwanted sidebands

## Mathematical Explanation

### PSK (Works with Baseband)

For BPSK with differential encoding:
- Baseband symbols: +1 or -1 (I component), Q = 0
- Modulation: I(t)×cos(ωt)
- Phase changes → frequency shifts are instantaneous

With I/Q:
- I(t) = baseband data (after pulse shaping)
- Q(t) = baseband data with 90° phase shift
- Result: s(t) = I(t)cos(ωt) + Q(t)sin(ωt)

This is **linear modulation** - filtering I and Q separately works perfectly.

### FSK (Doesn't Work with Simple Baseband)

For FSK:
- Need instantaneous frequency: f(t) = fc + Δf×m(t)
- Where m(t) = ±1 for mark/space
- Phase is integral of frequency: φ(t) = ∫f(t)dt

**Option 1: Complex baseband** (correct but complicated)
- Generate complex exponential: exp(j2πΔf×t)
- Apply to I/Q: I(t) + jQ(t)
- This is essentially what we do by generating at carrier!

**Option 2: Direct generation** (simpler for FSK)
- Just generate the two tones directly
- cos(2π(fc + shift/2)t) for mark
- cos(2π(fc - shift/2)t) for space
- Clean, simple, correct

## Summary

| Aspect | PSK | RTTY/FSK |
|--------|-----|----------|
| Modulation Type | Linear (phase) | Non-linear (frequency) |
| Baseband Approach | ✓ Works perfectly | ✗ Creates sidebands |
| Generation | I/Q → Quadrature mix | Direct at carrier |
| Filtering | Baseband lowpass | Raised cosine shaping |
| Complexity | More complex | Simpler |

## Implementation in PyDigi

### PSK (pydigi/modems/psk.py)
```python
# Generate baseband I/Q
i_samples, q_samples = generate_baseband_iq(symbols)

# Filter at baseband
i_filtered = lowpass_filter(i_samples)
q_filtered = lowpass_filter(q_samples)

# Quadrature modulation
output = i_filtered * cos(ωt) + q_filtered * sin(ωt)
```

### RTTY (pydigi/modems/rtty.py)
```python
# Generate FSK directly at carrier
if bit == 1:
    output = generate_tone(carrier + shift/2)  # Mark
else:
    output = generate_tone(carrier - shift/2)  # Space
```

## References

- **PSK/QAM**: "Digital Communications" by Proakis & Salehi
  - Chapter on linear modulation and I/Q representation

- **FSK**: "Wireless Communications" by Rappaport
  - Chapter on frequency modulation and FM generation

- **SDR Theory**: "Software Receiver Design" by Johnson et al.
  - Explains why baseband I/Q works for linear modulations
  - Discusses FSK implementation alternatives
