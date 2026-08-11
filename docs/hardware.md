# Hardware

## Architecture at a glance

```
┌─────────────────────────────────────────────┐
│              Badge carrier PCB              │
│  (HUMAN sun / INHUMAN gear art + LEDs)      │
│                                             │
│   ┌─────────────────────────────────────┐   │
│   │     Removable core module           │   │
│   │  Baochip-1x · OLED · camera · USB-C │   │
│   └─────────────────────────────────────┘   │
│                                             │
│   2× AA batteries · 2× SAO ports            │
└─────────────────────────────────────────────┘
```

Detach the core → standalone security token (USB-C powered). Carrier keeps solder pads for LED experiments after removal.

Published KiCad / PDFs / photos: [media.defcon.org — DEF CON 34 badge](https://media.defcon.org/DEF%20CON%2034/DEF%20CON%2034%20badge/) ([hardware/](https://media.defcon.org/DEF%20CON%2034/DEF%20CON%2034%20badge/DEF%20CON%2034%20badge%20-%20hardware/), [pictures/](https://media.defcon.org/DEF%20CON%2034/DEF%20CON%2034%20badge/DEF%20CON%2034%20badge%20-%20pictures/)). Dead LED? [Jump table](#led-jump-tables). Art / lore: [lore.md](lore.md).

## Baochip-1x SoC

Mostly open-source RISC-V security SoC designed by bunnie; fabricated in **TSMC 22nm** (WLCSP packaging with exposed backside for inspection).

| Spec | Detail |
| --- | --- |
| CPU | 350 MHz Vexriscv **RV32-IMAC** + MMU |
| I/O cores (BIO) | 4× 700 MHz PicoRV32 **RV32-EC/Zmmul** |
| SRAM | 2 MiB on-chip |
| NVM | 4 MiB on-chip **RRAM** (flash-like, harder invasive extraction story) |
| Crypto | On-chip accelerators, TRNG, secure key storage, glitch sensors, etc. |
| Process | TSMC 22ULL; part often styled Baochip-1x / bao1x |
| Openness | Mostly open RTL — data-transforming logic published; some fab/analog/bus pieces remain proprietary |

### Why “mostly” open / inspectable

Traditional secure elements are black boxes. Baochip publishes hardware design and RTL so you can compare intent vs silicon. Packaging supports **IRIS** (Infra-Red, In-Situ) inspection: shine IR through the die and compare against published reference imagery without destroying the chip.

What IRIS can constrain well: macro/meso-scale blocks (RAMs, major peripherals, unexpected large extras). What it does **not** fully prove alone: every micro-scale gate or all fab-process subtleties. Treat it as raising assurance and attack cost — not absolute proof against a nation-state fab adversary.

Further reading: [baochip/baochip-1x](https://github.com/baochip/baochip-1x) (RTL), [bunnie’s Baochip-1x post](https://www.bunniestudios.com/blog/2026/baochip-1x-a-mostly-open-22nm-soc-for-high-assurance-applications/), [DEF CON 34 talk (YouTube)](https://www.youtube.com/watch?v=1plmJlWSKa0), [baochip.com](https://baochip.com/), [IRIS](https://bunnie.org/iris), [IRIS paper](https://arxiv.org/abs/2303.07406).

## Core module I/O

| Interface | Notes |
| --- | --- |
| **USB-C** | Host connection; powers module when detached |
| **OLED** | 128×128 black & white |
| **Camera** | Low-res, nearsighted, B&W by default; QR-oriented; **no photo storage** (privacy culture) |
| **Buttons** | Middle button: nonce QR / camera; other controls per UI |
| **Reset** | Flat panel on lower-right edge of module (used for update mode) |

## Published hardware files

Index: [DEF CON 34 badge on media.defcon.org](https://media.defcon.org/DEF%20CON%2034/DEF%20CON%2034%20badge/) (dropped ~2026-08-06). GitHub only has the **core** ([bunnie/dc34-core-hw](https://github.com/bunnie/dc34-core-hw), CERN OHL-W-2.0); carriers live on the media server. CHEESO still says schematics “will be published” on [cheeso.io/defcon-34-badge](https://cheeso.io/defcon-34-badge) — use media.defcon.org.

| Path | What’s in it |
| --- | --- |
| [hardware/](https://media.defcon.org/DEF%20CON%2034/DEF%20CON%2034%20badge/DEF%20CON%2034%20badge%20-%20hardware/) | KiCad + PDFs + case STEPs |
| [hardware/human-carrier/](https://media.defcon.org/DEF%20CON%2034/DEF%20CON%2034%20badge/DEF%20CON%2034%20badge%20-%20hardware/DEF%20CON%2034%20badge%20human-carrier/) | Sun PCB — [`dc34-human-v3-binv.kicad_pcb`](https://media.defcon.org/DEF%20CON%2034/DEF%20CON%2034%20badge/DEF%20CON%2034%20badge%20-%20hardware/DEF%20CON%2034%20badge%20human-carrier/dc34-human-v3-binv.kicad_pcb) / [`.kicad_sch`](https://media.defcon.org/DEF%20CON%2034/DEF%20CON%2034%20badge/DEF%20CON%2034%20badge%20-%20hardware/DEF%20CON%2034%20badge%20human-carrier/dc34-human-v3-binv.kicad_sch) / [PDF](https://media.defcon.org/DEF%20CON%2034/DEF%20CON%2034%20badge/DEF%20CON%2034%20badge%20-%20hardware/DEF%20CON%2034%20badge%20human-carrier/dc34-human-v3-binv.pdf) |
| [hardware/nonhuman-carrier/](https://media.defcon.org/DEF%20CON%2034/DEF%20CON%2034%20badge/DEF%20CON%2034%20badge%20-%20hardware/DEF%20CON%2034%20badge%20nonhuman-carrier/) | Gears PCB (all INHUMAN colorways) — [`dc34-exhibitor-v2.kicad_pcb`](https://media.defcon.org/DEF%20CON%2034/DEF%20CON%2034%20badge/DEF%20CON%2034%20badge%20-%20hardware/DEF%20CON%2034%20badge%20nonhuman-carrier/dc34-exhibitor-v2.kicad_pcb) / [`.kicad_sch`](https://media.defcon.org/DEF%20CON%2034/DEF%20CON%2034%20badge/DEF%20CON%2034%20badge%20-%20hardware/DEF%20CON%2034%20badge%20nonhuman-carrier/dc34-exhibitor-v2.kicad_sch) (no PDF) |
| [hardware/core-board/](https://media.defcon.org/DEF%20CON%2034/DEF%20CON%2034%20badge/DEF%20CON%2034%20badge%20-%20hardware/DEF%20CON%2034%20badge%20core-board/) | Same as GitHub + [schematic PDF](https://media.defcon.org/DEF%20CON%2034/DEF%20CON%2034%20badge/DEF%20CON%2034%20badge%20-%20hardware/DEF%20CON%2034%20badge%20core-board/defcon-34-v3.pdf) (`power` / `ux` / `memory` / `daric` sheets) |
| [hardware/case/](https://media.defcon.org/DEF%20CON%2034/DEF%20CON%2034%20badge/DEF%20CON%2034%20badge%20-%20hardware/DEF%20CON%2034%20badge%20case/) | Module plastics: [`dc34-module-top.STEP`](https://media.defcon.org/DEF%20CON%2034/DEF%20CON%2034%20badge/DEF%20CON%2034%20badge%20-%20hardware/DEF%20CON%2034%20badge%20case/dc34-module-top.STEP) · [`dc34-module-bot.STEP`](https://media.defcon.org/DEF%20CON%2034/DEF%20CON%2034%20badge/DEF%20CON%2034%20badge%20-%20hardware/DEF%20CON%2034%20badge%20case/dc34-module-bot.STEP) · [`silicone_plug.stp`](https://media.defcon.org/DEF%20CON%2034/DEF%20CON%2034%20badge/DEF%20CON%2034%20badge%20-%20hardware/DEF%20CON%2034%20badge%20case/silicone_plug.stp) |
| [pictures/](https://media.defcon.org/DEF%20CON%2034/DEF%20CON%2034%20badge/DEF%20CON%2034%20badge%20-%20pictures/) | Promo / mfg stills + Human / Uber / manufacturing clips |
| [software/](https://media.defcon.org/DEF%20CON%2034/DEF%20CON%2034%20badge/DEF%20CON%2034%20badge%20-%20software/) | UF2s (also [latest.zip](https://media.defcon.org/DEF%20CON%2034/DEF%20CON%2034%20badge/latest.zip)) |
| [SAO spec PDF](https://media.defcon.org/DEF%20CON%2034/DEF%20CON%2034%20badge/DEF%20CON%2034%20SAO%20Spec%20Sheet.pdf) | Dual SAO mechanical + electrical (3.0 V, 100 mA total, GPIO4 wake) |

Upstream KiCad is on media.defcon.org (and core on GitHub). **Uber carrier KiCad is not published.**

## Carrier board

| Feature | Notes |
| --- | --- |
| Power | **2× AA** (Keystone 2460 holders, series → `PACK_P`); ~3 days intermittent use (SAOs not included). Schematic: remove cells for storage **>3 weeks** or USB-only use (no storage disconnect circuit). |
| VLED | ~3.89 V boost (MT3608) for WS2812 / SK6812 (min ~3.7 V + margin). Shared pour on the carrier. |
| Logic / SAO | **+3.0 V** (not 3.3 V) — camera I/O VDD limit. [SAO spec](https://media.defcon.org/DEF%20CON%2034/DEF%20CON%2034%20badge/DEF%20CON%2034%20SAO%20Spec%20Sheet.pdf) same number. |
| SAO | **2×** unkeyed 6-pin headers (**J3** left / **J4** right). I2C devices on-badge at **0x3C** and **0x19**. **SAO GPIO4** = open-drain **wake** from sleep. INHUMAN note: SAO GPIOs also carry **accelerometer IRQs**. |
| LEDs | 2× eye **WS2812B-2020** (D1/D2) + 8× ring **SK6812SIDE-A-RVS** ([LCSC C2890037](https://www.lcsc.com/product-detail/C2890037.html), [datasheet](https://wmsc.lcsc.com/wmsc/upload/file/pdf/v2/lcsc/2108251530_OPSCO-Optoelectronics-SK6812SIDE-A-RVS_C2890037.pdf)). Chain + [jump table](#led-jump-tables). |
| After detach | Batteries / VLED / SAO stay on the carrier. **TP36** = `LED8-DOUT` (end of chain tap). Data in is **J6 `WS2812_DRV`** (needs the core or an external driver). |
| Layers | HUMAN **2-layer**; INHUMAN **4-layer** (same LED circuit; harder to scrape inner traces). |

### Badge-type ID (SAO 1–2–3, LSB first)

From carrier schematic “coding table”. `111` = no board mated.

| Bits (1 2 3) | Type |
| --- | --- |
| `101` | HUMAN |
| `011` | Goon (E) |
| `110` | Village (D) |
| `001` | CTF + contest (C) |
| `010` | Community (B) |
| `100` | CFP / artist / press / exhibitor / vendor / speaker (A) |
| `000` | Uber |
| `111` | No carrier |

INHUMAN colorways share **`dc34-exhibitor-v2`**; ID resistors differ, not the LED layout. Physical soldermask (CHEESO poster + photos): Goon red · Village orange · Community teal · CTF navy · Contest yellow · CFP white · Artist hot pink · Press green · Exhibitor cool gray · Vendor purple · Speaker cyan · Uber black (machined). HUMAN is the sun carrier: black mask + white ink + copper HASL rim.

DEF CON `#badge-life-chat`: SAO headers look **upside-down / 180°** vs classic SAOs (same rotation story as J6). 180° adapters were rumored; not confirmed as a handout. LED data is **BIO pin 15** (`WS2812_DRV`) — not reachable from SAO GPIOs.

### SAO headers (J3 / J4) — both carriers

2×3, 2.54 mm. Matches the [SAO spec](https://media.defcon.org/DEF%20CON%2034/DEF%20CON%2034%20badge/DEF%20CON%2034%20SAO%20Spec%20Sheet.pdf) (VDD = **3.0 V**).

| Pad | J3 (left) | J4 (right) |
| --- | --- | --- |
| 1 | SAO_GPIO1 | SAO_GPIO3 |
| 2 | SAO_GPIO2 | SAO_GPIO4 (wake, OD) |
| 3 | I2C0_SDA | I2C0_SDA |
| 4 | I2C0_SCL | I2C0_SCL |
| 5 | +3.0 V | +3.0 V |
| 6 | GND | GND |

### Core ↔ carrier mate (J6, 2×6 / 2 mm)

Core **J6** is male; carrier **J6** is female, footprint **rotated 180°**. **KiCad pad numbers do not match** across the two boards — use **net names**.

| Signal | Core J6 pad | Carrier J6 pad |
| --- | --- | --- |
| WS2812 data (`WS2812_HV` → `WS2812_DRV`) | 1 | 11 |
| I2C0_SCL | 2 | 12 |
| VLED | 3 | 9 |
| PACK_P (battery +) | 5 | 7 |
| I2C0_SDA | 6 | 8 |
| SAO_GPIO1 | 7 | 5 |
| SAO_GPIO3 | 8 | 6 |
| +3.0 V | 9 | 3 |
| SAO_GPIO2 | 11 | 1 |
| SAO_GPIO4 | 12 | 2 |
| ID / GND pair | 4 & 10 (`Net-(D5-A1)` on core) | 4 & 10 (GND on carrier) |

Core test points for the same nets: **TP14** `WS2812_HV`, **TP10** `VLED`, **TP12** `PACK_P`, **TP13/TP26** `+3.0V`, **TP4/TP7** I2C, **TP19–24** SAO GPIOs. Debug UART: core **J1** pad1 `DUART`, pad2 GND.

## Core module extras

| Ref | What |
| --- | --- |
| **J2** | USB-C (USB2 only) |
| **J1** | 1×4 debug: DUART / GND / CON_FROM_HOST / CON_TO_HOST |
| **P1** | 26-pin FPC (factory / JTAG-ish / host console) |
| **SW2** | Jog (Haoyu TS-1513B) |
| **SW3 / SW5** | Push (matrix with jog) |
| **SW1 / SW4** | Reset / power-related (flat edge reset used for update mode) |
| **U3** | SN74LVC1T45 — WS2812 level shift to VLED |

## Firmware / OS stack

Runs **[Xous OS](https://github.com/betrusted-io/xous-core)** — a pure Rust embedded microkernel:

- Hardware memory protection / isolated address spaces
- System services in userland
- Targeted at high-assurance embedded apps

See [development.md](development.md) for app repos ([dc34-vault](https://github.com/bunnie/dc34-vault), [dc34-console](https://github.com/bunnie/dc34-console), [dc34-api](https://github.com/bunnie/dc34-api), [dc34-core-hw](https://github.com/bunnie/dc34-core-hw)).

## Related hardware

- **Dabao** — Baochip-1x eval board ([Crowd Supply](https://www.crowdsupply.com/), PCB files on Baochip site)
- **Uber badge** — separate limited design (machined cases via Jiadaxing)

## Security features (reported / intended)

- Secure boot
- TRNG
- Hardware crypto accelerators
- Hardware key storage / protected key slots
- Monotonic / one-way counters
- RRAM for secrets (raises invasive extraction cost vs classic flash narratives)
- Glitch sensors / physical hardening features
- Post-con: FIDO2, TOTP, password manager roles

**Limits:** invasive fab attacks, advanced fault injection, side channels, software bugs, and closed fab/analog slices remain in scope. Bunnie has invited DEF CON researchers to find issues — expect patches (and already did for early firmware).

---

## LED jump tables

Skip a missing / pad-ripped LED by bridging **data only**. **VLED** and **GND** are shared pours — do not jump them unless you’re replacing the LED or power to other LEDs is actually broken.

Firmware drives **10** LEDs on stock HUMAN/INHUMAN (indices 0–1 = eyes, 2–9 = ring). Skipping one shifts colors after the gap by one slot; remaining LEDs still light. Uber firmware uses **18** LEDs — see [Uber](#uber-leds).

HUMAN vs INHUMAN: **same LED chain, same pad functions** — only board outline / layer count differ. INHUMAN is 4-layer, so scrape-to-trace is harder; prefer jumping neighbor pads.

**Compass:** hold the badge face-up with **LED8 (top of ring) = north**. Eyes sit west/east of the core.

### Shared pad map (HUMAN + INHUMAN)

Pin **numbers** are fixed on the part. Which net sits left vs right changes with how the LED is oriented.

| Part | Pad 1 | Pad 2 | Pad 3 | Pad 4 |
| --- | --- | --- | --- | --- |
| **D1 / D2** (eyes, WS2812B-2020) | DOUT | GND (VSS) | **DIN** | VLED (VDD) |
| **LED1–8** (ring, SK6812 side-fire) | **DIN** | VDD | **DOUT** | GND |

Eyes and ring footprints are **not** the same pinout.

### Chain order

```
WS2812_DRV → D1 → D2 → LED1 → LED2 → LED3 → LED4 → LED5 → LED6 → LED7 → LED8
             (W eye) (E eye)   NE     E      SE     S      SW     W      NW     N
```

### Jump table — one LED missing

**Pads left → right** = as seen looking at the **back** of the badge (solder / copper side). Prefer pad numbers / continuity when unsure.

| Missing | Bearing | Pads left → right (back) | Jump **from** | Jump **to** | Notes |
| --- | --- | --- | --- | --- | --- |
| **D1** | W (left eye) | GND · DOUT · VDD · DIN | `WS2812_DRV` (or DIN stub at D1) | **D2** pad **3** (DIN) | First in chain |
| **D2** | E (right eye) | GND · DOUT · VDD · DIN | **D1** pad **1** (DOUT) | **LED1** pad **1** (DIN) | |
| **LED1** | NE | GND · DOUT · VDD · DIN | **D2** pad **1** (DOUT) | **LED2** pad **1** (DIN) | |
| **LED2** | E | GND · DOUT · VDD · DIN | **LED1** pad **3** (DOUT) | **LED3** pad **1** (DIN) | |
| **LED3** | SE | DIN · VDD · DOUT · GND | **LED2** pad **3** (DOUT) | **LED4** pad **1** (DIN) | |
| **LED4** | S | DIN · VDD · DOUT · GND | **LED3** pad **3** (DOUT) | **LED5** pad **1** (DIN) | Or short DIN↔DOUT stubs at empty LED4 |
| **LED5** | SW | DIN · VDD · DOUT · GND | **LED4** pad **3** (DOUT) | **LED6** pad **1** (DIN) | |
| **LED6** | W | GND · DOUT · VDD · DIN | **LED5** pad **3** (DOUT) | **LED7** pad **1** (DIN) | |
| **LED7** | NW | GND · DOUT · VDD · DIN | **LED6** pad **3** (DOUT) | **LED8** pad **1** (DIN) | |
| **LED8** | N | GND · DOUT · VDD · DIN | — | — | **No jump** — end of chain |

If copper stubs remain under a missing part, bridge that footprint’s **DIN ↔ DOUT** only. Do not short data to VLED/GND.

### Core module (no decorative LEDs)

The core only **drives** the carrier chain:

- Baochip pin → level shifter (**U3** SN74LVC1T45) → **`WS2812_HV`**
- Connector **J6** (2×6, 2 mm): pin **1** = `WS2812_HV`, pin **3** = `VLED`
- Test points: **TP14** = `WS2812_HV`, **TP10** = `VLED`

If the carrier is dark but the core is fine: check mate / J6 pin 1 continuity into **D1** DIN. After detach, **TP36** is `LED8-DOUT` (end-of-chain tap). Inject data on carrier **J6 pad 11** (`WS2812_DRV`) without the core — see [J6 mate](#core--carrier-mate-j6-26--2-mm).

### Uber LEDs

No public carrier KiCad. Firmware: `dc34-console` `feature = "uber"` → **`LED_COUNT = 18`** (stock is 10). Same BIO pin (15) / WS2812 protocol. Continuity-hunt **DIN/DOUT** between neighbors; do **not** assume HUMAN/INHUMAN pad left/right order.

### After the jump

1. Power off while soldering.
2. Confirm continuity: from → to (~0 Ω), open to VLED and GND.
3. Power on: LEDs before the gap animate; LEDs after the gap light again → jump good.
