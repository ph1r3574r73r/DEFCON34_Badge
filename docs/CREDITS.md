# Credits

DEF CON works because people share. Mistakes in this tree are on the authors; many breakthroughs started as someone else’s late-night “wait, what if…”

## They built the toy

| Who | What |
| --- | --- |
| **Andrew “bunnie” Huang** / Baochip | Silicon, core module, firmware, manufacturing, the challenge design |
| **CHEESO** — Yafsec, Delia, Wietsman | The thing you actually want to wear |
| **DEF CON / Dark Tangent** | Another year of #badgelife |
| **Kingpin (Joe Grand)** | Twenty years of electronic badges — homage on the back of the carrier |

## They showed the path

| Who | What others learned |
| --- | --- |
| **Anthony Mattas (amattas)** | [*Only 132 Bytes…*](https://www.anthonymattas.com/articles/only-132-bytes) — the sealed loader hop. Read that first. This repo’s [`tools/132hop`](../tools/132hop/) rebuilds it; we switched to QR-on-OLED because hex OCR on a glowing 128×128 panel loses to bloom / `6` vs `b`. |
| **ohyou_** | Early extract energy; later dropped the public `k0` so everyone could keep breeding |
| **eaglerific** | U-mode / Coreuser “why is my dump all zeros?” |
| **srpape**, **aarondb_** | Trampoline / patched-loader ideas; About-page readout |
| **h3xcat** | SPI / swap TOCTOU rabbit hole (hardware-shaped) |
| **jonfen** | Gene-crypto / `k0` tooling |
| **yi5** | Helped the `k0` paste travel |

## Repos worth reading

| Repo | Why |
| --- | --- |
| [vmfunc/dc34-badge](https://github.com/vmfunc/dc34-badge) | Soft-path dead ends |
| [thehinac/dc34_badge](https://github.com/thehinac/dc34_badge) | QR/serial footguns; don’t `test k0` casually |
| [sbellem/baobit](https://github.com/sbellem/baobit) | Reproducible boot builds |

More: [repos.md](repos.md).

## Art / outlines

| Asset | Source |
| --- | --- |
| Light Bank `human.svg` / `inhuman.svg` | Simplified outlines from public carrier KiCad on [media.defcon.org](https://media.defcon.org/DEF%20CON%2034/DEF%20CON%2034%20badge/) |
| Light Bank `uber.svg` | Approximate silhouette (Uber KiCad unpublished) |
| CHEESO / DEF CON promo stills | **Not shipped** — link the official galleries; don’t mirror |

## Pay it forward

New find? **dc34@baochip.com** (and Discord / Matrix if that’s where the builders are hanging).  
Writeups > spoilers without context. Teach the next human.
