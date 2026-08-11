# Overview

The DEF CON 34 badge is an electronic conference badge that doubles as a **first-of-its-kind inspectable open hardware platform**. Built by Andrew “bunnie” Huang (Baochip) with the CHEESO team (Netherlands / Singapore).

DEF CON’s 2026 theme is **agency**: inspect the device, detach the compute core, and keep using it as a security token after closing ceremonies. It also marks **20 years of electronic badges** (#badgelife) — the back art pays homage to Joe Grand (Kingpin), who built the first electronic DEF CON badge (DC14 / 2006).

**Watch:** [bunnie’s DEF CON 34 badge talk](https://www.youtube.com/watch?v=1plmJlWSKa0) · **How-to:** [defcon.org/34b](https://defcon.org/34b) · **Story / art:** [lore.md](lore.md)

## Badge variants

| Family | Shape | PCB | Inlay |
| --- | --- | --- | --- |
| **HUMAN** | Sun | 2-layer; matte black front, copper back | Silver |
| **INHUMAN** | Cogwheel / gears | 4-layer; department colorways | Gold |

There are **13** physical badges: **12** peacock hex designs + Uber. Firmware still only has **7** `BadgeType`s (CTF+Contest share one; CFP/Artist/Press/Exhibitor/Vendor/Speaker share Other). Carrier ID bits (SAO 1–2–3, LSB first) map HUMAN / goon / village / CTF / community / exhibitor-class / uber — see [hardware.md](hardware.md#badge-type-id-sao-123-lsb-first). KiCad: [media hardware/](https://media.defcon.org/DEF%20CON%2034/DEF%20CON%2034%20badge/DEF%20CON%2034%20badge%20-%20hardware/).

A transparent **center module** (Baochip core) sits in every badge. Remove it and the white peacock artwork is fully revealed. Conversion kit needs a **T6 Torx** bit — [after the con](getting-started.md#after-the-con-security-token).

## Design notes (short)

1. **Shapes** — Solarpunk logo split into sun (HUMAN) and gears (INHUMAN).
2. **Front art** — Solarpunk + Peranakan styling (DEF CON Singapore callback); peacock = protection / courage.
3. **Back art** — Homage to Kingpin’s DC14 badge; DEF CON logo holds the batteries.
4. **Hexagons** — 12 peacock hexes = 12 designs (excl. Uber); silver on HUMAN, gold on INHUMAN.
5. **Font** — Leto Sans (low-vision readability).

Team, vendors, press timeline, and “is the board the CTF?”: [lore.md](lore.md).

> “It's a full-fledged, first-of-its-kind inspectable platform. Long after closing ceremonies we think you'll still be using this device to regain some agency and security in this rapidly complexifying world.”  
> — [defcon.org/34b](https://defcon.org/34b)
