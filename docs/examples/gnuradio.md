# GNU Radio Integration

PyDigi works seamlessly with GNU Radio since it returns standard numpy arrays.

## Using PyDigi as a Source

```python
import numpy as np
from gnuradio import gr, blocks, audio
from pydigi import PSK31

class psk31_source(gr.sync_block):
    """GNU Radio source block that generates PSK31."""

    def __init__(self, text="CQ CQ CQ DE W1ABC"):
        gr.sync_block.__init__(
            self,
            name="PSK31 Source",
            in_sig=None,
            out_sig=[np.float32]
        )
        self.psk = PSK31()
        self.audio = self.psk.modulate(text)
        self.offset = 0

    def work(self, input_items, output_items):
        out = output_items[0]
        n = min(len(out), len(self.audio) - self.offset)

        if n > 0:
            out[:n] = self.audio[self.offset:self.offset+n]
            self.offset += n
            return n

        return -1  # EOF
```

## Simple Flowgraph

```python
from gnuradio import gr, blocks, audio
from pydigi import PSK31

# Generate PSK31 signal
psk = PSK31()
audio_data = psk.modulate("HELLO WORLD")

# Create flowgraph
tb = gr.top_block()

# Vector source from PyDigi audio
src = blocks.vector_source_f(audio_data.tolist(), False)

# Audio sink
sink = audio.sink(int(psk.sample_rate))

# Connect
tb.connect(src, sink)

# Run
tb.run()
```

## See Also

- [Basic Examples](basic.md)
- [API Reference](../api/overview.md)
