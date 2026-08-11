# BIO memprobe (sealed-safe)

Unsigned PicoRV firewall probe — FIFO3 report, SAO1 blink while idle. Used to check whether stock firmware leaves DMA windows open to host SRAM (it doesn’t — filters stay on).

## Build

Needs Zig + a clone of [baochip/bio-sim](https://github.com/baochip/bio-sim):

```bash
cd /path/to/bio-sim/sw
zig build -Dmodule=memprobe -Demit-listing=false
# copy memprobe.bin next to this README
```

Source of truth for C: `bio/memprobe/main.c`.

## Run

```bash
.venv/bin/python scripts/bio_memprobe.py
# or after already loaded:
.venv/bin/python scripts/bio_memprobe.py --skip-upload --rx 64
```

Expect: local CANARY OK; WRPROBE reads ≠ writes (`blocked/gutter`); DONE. Meditations should still show **Sealed**.

Live check (2026-08-07): canary OK; host WR blocked; firewall on.
