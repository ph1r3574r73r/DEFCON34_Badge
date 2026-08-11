# 132hop archive — earlier exfil paths

Kept so others can see what we tried before QR. Prefer the front-door `asid_qr` path in the parent README.

| Variant / tool | What it taught |
| --- | --- |
| `asid_oled` (`oled_dump.py`) | U-mode works; hex OCR on OLED does not |
| `asid_pages` + `decode_pager.py` / `font6x12.py` | More slots, still OCR flake |
| `asid_scd` + `unwrap.py` / `derive.py` | SPI SCD QR can checksum while the flash image still isn’t SCD |

Build archive UF2s from the parent dir:

```bash
.venv/bin/python tools/132hop/build.py --selftest --all-archive --loader /path/to/ship/loader.uf2
```

Then flash with `tools/132hop/flash.py --uf2 tools/132hop/out/hop_asid_oled.uf2` (etc.) and restore stock `loader.uf2`.
