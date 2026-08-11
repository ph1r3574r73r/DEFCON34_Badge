# Host scripts

Python helpers that talk to a DEF CON 34 badge over USB-serial (or run gene crypto offline).

Needs a venv with at least `pyserial` (Pillow for `--png` OLED uploads):

```bash
python3 -m venv .venv
.venv/bin/pip install pyserial pillow
```

Port defaults **auto-detect** `/dev/cu.usbmodem*` / `/dev/ttyACM*`. Pass `--port` to pin one.

## Front door

| Script | Role |
| --- | --- |
| [`upload_oled.py`](upload_oled.py) | Push a 128×128 B&W image (or text lines) to the OLED |
| [`dc34_gene.py`](dc34_gene.py) | Haploid / diploid / meiosis / mutate + frame approx |
| [`breed_sim.py`](breed_sim.py) | Offline peer breed (`--key-hex` for crypto steps) |
| [`verify_k0_gene.py`](verify_k0_gene.py) | Check gene QR decrypts under a candidate `k0` |
| [`gen_nonce_qr.py`](gen_nonce_qr.py) | Mint fake nonce QRs for solo gene-crypto experiments |
| [`serial_port.py`](serial_port.py) | Shared USB port picker (imported by the others) |

Browser donor UI: [`../tools/genomics/`](../tools/genomics/). Genetics notes: [`../docs/genetics.md`](../docs/genetics.md).

## Research / dead ends (still useful to read)

These are sealed-safe experiments from the hunt — kept so others can learn what we tried. Not required for Light Bank or the sealed hop.

| Script | What we learned |
| --- | --- |
| [`bio_memprobe.py`](bio_memprobe.py) | Stock BIO DMA filters stay on — host WR blocked |
| [`usb_ifram_stress.py`](usb_ifram_stress.py) | CDC DoS / disconnect; not a `k0` leak |
| [`boot1_audit_capture.py`](boot1_audit_capture.py) | Sealed-safe boot1 `audit` capture helper |
| [`genetics_farm.py`](genetics_farm.py) | Multi-nonce gene-QR farm (pre–public-`k0`) |
| [`parse_swap_uf2.py`](parse_swap_uf2.py) | Parse public update `swap.uf2` headers |

Sealed flag dump tooling lives under [`../tools/132hop/`](../tools/132hop/).
