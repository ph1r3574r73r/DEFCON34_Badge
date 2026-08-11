# 132-byte loader hop

Offline rebuild of amattas’s sealed hop — [*Only 132 Bytes…*](https://www.anthonymattas.com/articles/only-132-bytes). Read that first.

Patches the **unsigned** loader header (AAD length 37 → trailing bytes not signed), parks stage-2 before the kernel sigblock, dumps keystore slots while still **Sealed**, then you restore stock `loader.uf2`. Boot1’s 32 B RMW flash writer is what makes the header patch survivable.

## Why QR on the OLED (not hex)

While the hop runs, **Xous is down** — no USB console. The only easy “response channel” is the 128×128 OLED.

We tried hex first (`asid_oled` / `asid_pages` in [`archive/`](archive/)): photograph the panel, OCR later. On a glowing 128×128 grid that fails in boring ways — bloom, phone HDR, and glyph twins like **`6` vs `b`**. You can get a beautiful dump that still hashes wrong.

So the preferred path is **`asid_qr`**: encode the same dump as QR v6-M frames on the OLED, film one full loop (~169 frames), decode with OpenCV. Checksums tell you if a page was missed; no hand transcription. Same hop class as amattas — different exfil.

**U-mode matters too:** S-mode + ASID 3 can return a page of **zeros** that looks like a successful dump. Working variants drop to **User mode** with the PTE User bit set (see `eaglerific` / CREDITS). If every nibble is `0`, you’re in the wrong identity — not “empty slots.”

## Front door

| Script | Role |
| --- | --- |
| **`dump_via_qr.py`** | build → handback smoke → QR flash → restore |
| `decode_qr.py` | film → JSON dump (verify flag1 SHA) |
| `build.py` / `flash.py` | offline UF2 build + Update-mode write |
| `oled_qr.py` + `oled_common.py` + `qr_v6.py` | stage-2 + QR tables |
| `asm.py` / `payload.py` / `constants.py` / `uf2util.py` | hop guts |

Smoke variants: `handback` (must stay Sealed), `spin`, `asid_hold` (S-mode zeros trap — educational).

`THE_FLAG_1` is RRAM data slot **260**. Published digest: SHA-256 `8e817665bab84a5131b08b9c7f2be4773d45ee86eaed25389212c9183c4c057a`. Prefer verifying that over pasting raw hex.

## Quick path (QR)

```bash
# venv with pyserial + qrcode (+ opencv for decode)
python tools/132hop/dump_via_qr.py build --loader /path/to/ship/loader.uf2
python tools/132hop/dump_via_qr.py handback   # prove still Sealed
python tools/132hop/dump_via_qr.py flash      # OLED QR loop (hangs on purpose)
# film one full loop, then:
.venv/bin/python tools/132hop/decode_qr.py /path/to/video.mov --layout asid -o dump_qr.json
python tools/132hop/dump_via_qr.py restore --loader /path/to/ship/loader.uf2
```

Ship `loader.uf2` from [34b](https://defcon.org/34b) / CI — not committed here. Artifacts → `tools/132hop/out/` (gitignored).

Update mode: hold **any** button + **RESET** (lower-right) until OLED says **Update mode**. After dump hops, Meditations should still show **Sealed**.

```bash
.venv/bin/python tools/132hop/inspect_loader.py
.venv/bin/python tools/132hop/build.py --selftest
.venv/bin/python tools/132hop/build.py --all          # spin / handback / hold / qr
```

Hex OCR / SPI SCD side quests: [`archive/`](archive/).

## Do not

- Flash **developer-signed** images (wipes conference secrets)
- Run `baosec-init` / `self_destruct` / CRC-valid `test k0 …` while sealed-hunting
- Improvise UF2 past the kernel sigblock
- Expect USB serial hex from hang hops (no Xous → no CDC)

Challenge context: [docs/challenges.md](../../docs/challenges.md). Credits: [docs/CREDITS.md](../../docs/CREDITS.md).
