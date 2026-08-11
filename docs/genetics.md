# DC34 light genetics

Conference badges play a **collect-the-lights** game. Patterns are genomes; QR “breeding” mixes them. Shared key `k0` / `Ko` locks honest exchange — wipe it (developer mode) and sealed badges will no longer accept your genes.

Source of truth: [`defcon-scheme.md`](https://github.com/bunnie/dc34-vault/blob/main/defcon-scheme.md), [`dc34-api`](https://github.com/bunnie/dc34-api), vault breed path, BIO renderer in [`dc34-console` lightgenes](https://github.com/bunnie/dc34-console). Host port in this repo: [`scripts/dc34_gene.py`](../scripts/dc34_gene.py). Browser donor: [The Light Bank](../tools/genomics/).

---

## Theme

| Idea | How it shows up |
| --- | --- |
| **Human** badge | Attendee type; UX tour + art |
| **Diploid genome** | Two haploid strands stored as the light gene |
| **Breeding** | Consent QR (nonce) → encrypted gamete QR → keep/rollback |
| **Evolution** | Meiosis + mutation (elevated on inbreeding) |
| **Types as niches** | Firmware: Uber / Goon / Community / Village / CTF / Human / Other. Floor sim also names the 13 physical colorways (Contest separate from CTF; CFP / Artist / Press / Exhibitor / Vendor / Speaker under Other). |
| **Honest vs cheat** | Dev mode can paint any lights but **wipes** `k0` so sealed badges reject the gene |

`k0` is the lock on the toy, not the toy itself. CHEESO poster: **“Gotta catch ’em all.”** Full art/story: [lore.md](lore.md).

---

## Protocol (honest firmware)

1. **Consent** — Receiver shows `DC34_HEADER ‖ Nonce1` (12 B nonce) as QR (`ShowKey`).
2. **Transfer** — Donor scans nonce, responds with  
   `AES-256-GCM-SIV(K, Nonce1, padded_gamete[16], AD=[]) ‖ tag` (32 B payload, base45 QR).
3. **Syngamy** — Receiver decrypts, may **mutate** sperm if same `BadgeType` (inbreeding), builds new diploid `[egg, sperm]`, confirms keep/rollback.
4. **Timeout** — ~1 minute window so posted QR pairs don’t farm easily.

Header: `49db7671f34435ed5fddffdfcbb7508a`.

---

## Genome layers

| Layer | Size | Meaning |
| --- | --- | --- |
| **Haploid** | 9 B | One gamete / strand |
| **Diploid** | 18 B | `[egg, sperm]` in PDDB |
| **Phenotype** | 9 B | Blended expression for rendering (`Diploid::phenotype`) |
| **Padded gamete** | 16 B | QR plaintext: haploid[9] ‖ `00…` ‖ `badge_type` @ byte 15 |
| **Gene QR** | 32 B CT‖tag | Encrypted padded gamete |

### Haploid fields (`#[repr(C)]`)

| Offset | Field | Role in BIO renderer (`main.c`) |
| --- | --- | --- |
| 0 | `cd_period` | Spatial frequency of brightness cosine around the ring (0–6 typical) |
| 1 | `cd_rate` | Maps to animation period τ (~60–700 ms units) |
| 2 | `cd_dir` | `>128` → brightness wave direction flips |
| 3 | `sat` | HSV saturation |
| 4 | `hue_ratedir` | Low nibble = hue scroll rate; high nibble = hue direction |
| 5 | `hue_base` | Min hue of palette window |
| 6 | `hue_bound` | Max hue (≥ base) |
| 7 | `chaser` | C name `lin`: if `<88`, rare “shoot” / eye flash variant (~3% after summing) |
| 8 | `nonlin` | `>127` → square brightness (dimmer, battery-friendly) |

Hardware: 8 ring WS2812 + 2 eyes on BIO pin 15; eyes gated by `jack_eyes` on non-Uber builds.

### Meiosis

Per-locus pick from parent A or B (hue trio stays together). Not a 50/50 blend — that is **phenotype**.

### Phenotype dominance

- Period → mean (cap 6); rate → mean  
- `cd_dir` / `sat` / `chaser` → saturating add (high wins)  
- Hue window → min base, max bound (wider wins)  
- `hue_ratedir` → inverse-add toward slower cycling  
- Firmware quirk: phenotype `nonlin` uses `a.chaser + b.nonlin`

### Mutation

Gray-code bit flips; rates `None / Baseline(64) / Elevated(100) / Radioactive(140) / Apocalyptic(240)` = roll threshold vs `u8`.  
**Inbreeding** (same badge type): Human starts at Elevated; others Baseline; then `max(inbreeding, ambient)`.

**UI to raise ambient mutation** (floor tip): spam the side nub up/down, or flip the badge so the DEF CON logo inverts repeatedly → **Elevated → Radioactive → Apocalyptic**. Approx odds / bit-scramble intensity:

| Mode | `rate.roll()` threshold | ~P(mutate per trait) | `to_bit_changes` |
| --- | --- | --- | --- |
| Baseline | 64 | ~25% | 1 |
| Elevated | 100 | ~39% | 3 |
| Radioactive | 140 | ~55% | 7 |
| Apocalyptic | 240 | ~94% | 31 (`0x1f`) |

Type speed / chaser caps (from `BadgeType` in api): Community fastest (`cd_period_max=2`), Human `5`, CTF/Other `6`. Uber+Village chaser `0..=45`; Human/Community/Goon/CTF `90..=255`; Other `0..=255`.

### BadgeType palette biases

| Type | Hue range (approx) | Physical colorways | Notes |
| --- | --- | --- | --- |
| Goon | 0–20 | Goon (red) | Forces `hue_base=0` (red) |
| Community | 32–80 | Community (teal) | |
| Village | 80–128 | Village (orange) | Narrower `cd_dir` |
| **Human** | 128–160 | Human (black + white ink) | “Average” niche — harder to get novelty → higher inbreeding mutation |
| Other | 160–192 | CFP / Artist / Press / Exhibitor / Vendor / Speaker | Shared SAO `100` |
| CTF | 192–220 | CTF (navy) + Contest (yellow) | Shared SAO `001` |
| Uber | 220–255 | Uber (black machined) | `hue_bound=255`; dimmer shift in BIO |

Exact sat/chaser/nonlin/period caps: see `BadgeType` methods in api / `dc34_gene.py`.

---

## Breeding with a known `K`

Encrypted gene QRs are AES-GCM-SIV under `K = Ko ‖ Kp`. Once `K` is known, [The Light Bank](../tools/genomics/) can mint/accept the same nonce ↔ gene QRs as honest firmware. Offline helpers: `scripts/verify_k0_gene.py`, `scripts/breed_sim.py`.

---

## Host tooling

| Tool | Role |
| --- | --- |
| `scripts/dc34_gene.py` | Haploid/Diploid/meiosis/mutate + `approx_frame` |
| `scripts/breed_sim.py` | Offline peer breed (needs `--key-hex` for crypto steps) |
| `scripts/genetics_farm.py` | Multi-nonce breed helper (research) |
| [`tools/genomics/`](../tools/genomics/) | **The Light Bank** — [live](https://ph1r3574r73r.github.io/DEFCON34_Badge/) · donor UI + QR breed |

Open [The Light Bank](https://ph1r3574r73r.github.io/DEFCON34_Badge/) (or `tools/genomics/` via `python3 -m http.server`). Webcam needs localhost/HTTPS.
