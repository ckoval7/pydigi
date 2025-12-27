# 8PSK (Eight-Phase PSK)

8PSK uses eight phase states to encode 3 bits per symbol, providing three times the data rate of BPSK at the same baud rate.

## 8PSK (No FEC)

::: pydigi.modems.psk8
    options:
      show_root_heading: true
      show_source: true

## 8PSK with FEC

8PSK with Forward Error Correction adds convolutional coding and interleaving for improved reliability.

::: pydigi.modems.psk8_fec
    options:
      show_root_heading: true
      show_source: true
