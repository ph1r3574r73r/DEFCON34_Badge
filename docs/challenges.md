# Challenges & secrets

Spoilers kept light. The fun is the **climb**, not the pastebin.

**Credits:** [CREDITS.md](CREDITS.md)

New here? Play the light game first ([genetics.md](genetics.md) · [The Light Bank](https://ph1r3574r73r.github.io/DEFCON34_Badge/)), poke the OLED, read source. Developer mode wipes the interesting secrets — choose wisely.

## Known challenge themes

1. **Light patterns** — Trade encrypted LED genomes. Ask nicely. Host donor: [The Light Bank](https://ph1r3574r73r.github.io/DEFCON34_Badge/). Lore/art: [lore.md](lore.md) (CTF **badge type** ≠ CTF village puzzle).
2. **Custom screen art** — Put an image on the OLED: [dc34-image](https://github.com/bunnie/dc34-image).
3. **Shared light key `k0` / `Ko`** — Locked honest breeding during the hunt. Design: [`defcon-scheme.md`](https://github.com/bunnie/dc34-vault/blob/main/defcon-scheme.md). The community published the full key afterward; The Light Bank uses it so breeding stays playable.
4. **RRAM FT flags** — Secrets planted in on-chip slots (table below).
5. **Secure boot keys** — Harder track (`BAO1` / `BAO2`). Tell bunnie if you find them.
6. **Eggs / soft UI** — About → … → **~Meditations~** (hash / Sealed). Spam the nub or flip the badge to crank mutation ([genetics.md](genetics.md)). Skip `factory://…`, `self_destruct`, and casual `test k0` while still hunting.

## Three provisioned flags

Discord (bunnie): developer mode wipes **three** provisioned “flags.” Working map:

| # | Flag | Location | Notes |
| --- | --- | --- | --- |
| 1 | Light key `k0`/`Ko` | PDDB `dc34`/`k0` | Explicit “first flag” once extracted → light exchange / re-inject via `test k0` |
| 2 | `THE_FLAG_1` | RRAM Data slot **260** | FT-planted; “you've captured a flag!” in `bao1x-api`. Wiped on developer mode. Sealed dump tooling: [`tools/132hop`](../tools/132hop/). |
| 3 | Second RRAM flag (teased) | **Unknown** | “There is a second flag stored somewhere else.” No `THE_FLAG_2` in open repos. Free slots **269–271** are a common guess (259 is still `SWAP_KEY` on ship). |

**Do not** enter developer mode to dump these — they are erased.

### Sealed dump of `THE_FLAG_1` (loader hop)

Primary writeup: amattas — [*Only 132 Bytes…*](https://www.anthonymattas.com/articles/only-132-bytes).

This repo’s [`tools/132hop`](../tools/132hop/) rebuilds that hop offline. **Why we prefer QR frames over hex OCR:** while the hop runs there is no USB console — only the OLED — and photographing a 128×128 hex grid loses to bloom / `6` vs `b`. QR + checksums turned the dump into something a camera can verify. Also: **U-mode** (not S-mode) or you get a convincing page of zeros. Details and commands: [132hop README](../tools/132hop/README.md).

Published flag1 digest (SHA-256): `8e817665bab84a5131b08b9c7f2be4773d45ee86eaed25389212c9183c4c057a`.

Paths that **don’t** read slot 260: stock USB/vault APIs, BIO host DMA (filters on), gene-QR / `k0` bruting, hex OCR heroics.

## Conference light key (`k0`)

Design doc: [`defcon-scheme.md`](https://github.com/bunnie/dc34-vault/blob/main/defcon-scheme.md)

| Piece | Role |
| --- | --- |
| `K` (256-bit) | Full AES-256-GCM-SIV key = PDDB secret `dc34` / `k0` |
| `Ko` (~96 bits Day 1) | Secret prefix — the flag to capture |
| `Kp` (~160 bits Day 1) | Public / leaked portion; more bits released each day of the con |
| `DC34_HEADER` | Public QR preamble: `49db7671f34435ed5fddffdfcbb7508a` |

Implementation notes:

- Stored in PDDB dict `dc34`, key `k0` ([`dc34-api`](https://github.com/bunnie/dc34-api)).
- Cipher: `Aes256GcmSiv::new(k0)` ([`config.rs`](https://github.com/bunnie/dc34-vault/blob/main/src/config.rs)).
- **Erased** when the badge enters developer mode.
- Factory provisioning uses `test k0 <base64(k0‖crc32)>` — sample vectors in console source are **test** keys, not production.
- `test k0check` (dumps `k0`) is behind the `hazardous-test` cargo feature — **not** on stock conference builds.

### Verify the badge still has the real key

Menu → **About** → click through Bunnie / Baochip / Cheeso / Info → **~Meditations~** diagnostics:

- Shows `k0: <8 hex chars>` = first 8 hex digits of `SHA256(k0)`
- Should say **Sealed** (not Developer)
- Comment in vault source: correct hash prefix is **`dca9ea49`**

### Ways people approached `Ko`

| Approach | Notes |
| --- | --- |
| **Vuln / extraction** | Break sealed firmware / PDDB / keystore **without** wiping secrets — bunnie wants the writeup |
| **Brute force** | Day 1 ≈ 96 unknown bits; strength drops as more `Kp` bits are leaked (schedule in `defcon-scheme.md`) |
| **Capture QR traffic** | Header+nonce are clear; ciphertext is AES-GCM-SIV under `K` — useful once candidate keys exist. Stock GeneScan also logs full QR text over USB @ Info (capture helper, not a key dump). |
| **Wait for leaks** | `Kp` expansions are “by proclamation” (social / Discord / site). Starter 16 bytes appeared in an HTML comment on [defcon.org/34b](https://defcon.org/34b). Community later published full `k0` so breeding stayed playable. |

**Do not** flash custom / **developer-signed** firmware first — that is a one-way wipe of conference secrets. Unsigned loader *header* hops (amattas / `tools/132hop`) are a different story — restore stock `loader.uf2` when done.

## Report

Email **dc34@baochip.com** (or Discord / Matrix). Prefer reproducing on latest firmware.

## Developer mode tradeoff

Dev mode erases challenge keys. That cannot be casually undone for conference crypto.
