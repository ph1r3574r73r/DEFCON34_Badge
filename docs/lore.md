# Lore & backstory (DC34 badge)

The story DEF CON, CHEESO, and bunnie actually told — then what it does **not** mean for CTF / `k0`.

**Contents:** [Origin](#origin) · [Official story](#official-story-def-con--wired) · [Agency as silicon](#agency-as-silicon-why-this-badge) · [How to read the art](#how-to-read-the-art) · [Where the art lives](#where-the-art-actually-lives) · [HUMAN vs INHUMAN vs CTF](#human-vs-inhuman-vs-ctf-badge) · [Is the board the CTF?](#insights-is-the-board-the-ctf) · [Team](#team-public-bios-only) · [Look-order](#suggested-look-order) · [Press index](#press-index-story-sources-dated)

| Tell it | Source |
| --- | --- |
| Wearable + family / #badgelife | [CHEESO](https://cheeso.io/defcon-34-badge) |
| At-con how-to + team bios | [defcon.org/34b](https://defcon.org/34b) |
| Official reveal copy | [DEF CON 34 news](https://defcon.org/html/defcon-34/dc-34-news.html) |
| Silicon / Moss / 27k / token | [Wired (Kim Zetter)](https://www.wired.com/story/defcon-34-badge-baochip-andrew-bunnie-huang/) |
| Why the chip exists (IRIS, hitchhike, MMU) | [bunnie — Baochip-1x](https://www.bunniestudios.com/blog/2026/baochip-1x-a-mostly-open-22nm-soc-for-high-assurance-applications/) |
| Floor talk (chip, BIO, token, agency) | [DEF CON 34 — bunnie (YouTube)](https://www.youtube.com/watch?v=1plmJlWSKa0) |

Hardware files: [media.defcon.org/34 badge](https://media.defcon.org/DEF%20CON%2034/DEF%20CON%2034%20badge/). Pinouts: [hardware.md](hardware.md). Light game: [genetics.md](genetics.md). Flags: [challenges.md](challenges.md). Token after the con: [getting-started.md](getting-started.md#after-the-con-security-token).

**Artist blogs:** Delia’s public writeup **is** the CHEESO page. [cheeso.io](https://cheeso.io/) itself is agency marketing, not extra badge lore. Yafsec points at [Darknet Diaries 87](https://darknetdiaries.com/episode/87/) (GGOH) as *his* story, not badge stego.

---

## Origin

Late **2025**, Amsterdam dinner: **Joe Grand (Kingpin)** introduced **bunnie** to **Yafsec** (Edwin van Andel). Yafsec spun up **CHEESO**; Delia took art; Wietsman routed the carrier. ~8 months to ship.

That lineage matters: Kingpin made the first electronic DEF CON badge (**DC14 / 2006**). DC34 is **20 years of #badgelife**. The **back** of the carrier is an explicit homage — DEF CON logo as battery holder, Joe named on the edges.

Theme of the con: **Agency** — inspect, detach, keep using. CHEESO’s line: *“DEFCON is not just a con. It’s 34 years of family. Family that should be protected.”* The removable core → FIDO2/TOTP token is the punchline of that sentence, not a side quest.

Dutch coverage (Tweakers → [TechNieuwsVandaag recap](https://technieuwsvandaag.nl/nederlands-ontwerp-def-con-badge/), 6 Aug): CHEESO + Yafsec did the *wearable*; bunnie did silicon/firmware. Yafsec cannot travel to the US (stated on 34b / CHEESO bios).

**Jeff Moss (Dark Tangent)**, in public Discord commentary before the con: they pushed the Wired reveal **before** Black Hat news ate the week so people would **bring tools and get ready to hack it**, and so open code would have more than just con week to land. *“We haven’t ever had something like this.”*

---

## Official story (DEF CON + Wired)

This is the narrative the org wanted attendees to hear. It is **not** a last-48h drop — the news posts landed before doors, and Thu/Fri news is parties + headsets.

### How DEF CON framed it

1. **Theme first.** DC34 theme = **Agency**: self-determination in the tech you use; chart your own course; move attention toward tools that support that.
2. **Badge Alert: SAO Edition** ([news](https://defcon.org/html/defcon-34/dc-34-news.html)) — tease before the reveal: electronic-badge year, “hardware hacking legend,” *“it will be iconic. First round Hall of Fame.”* Also: *“it’s a platform… first-of-its-kind inspectable platform.”* The only concrete drop in that post was the [SAO spec sheet](https://media.defcon.org/DEF%20CON%2034/DEF%20CON%2034%20badge/DEF%20CON%2034%20SAO%20Spec%20Sheet.pdf) so add-on builders could start.
3. **“The wait is over. Meet the DEF CON 34 badge!”** — bunnie + open, inspectable **Baochip**. Holders are “the first to get their hands on a radically transparent device” that can be a **security token, password manager, HSM, pretty light generator** — hoped to stay useful after closing ceremonies. Points at Wired, not at a puzzle writeup.
4. **34b** after pickup: how to breed lights, how to update, how to convert the core. Quote they reuse everywhere:

> “It's a full-fledged, first-of-its-kind inspectable platform. Long after closing ceremonies we think you'll still be using this device to regain some agency and security in this rapidly complexifying world.”
> — [defcon.org/34b](https://defcon.org/34b) / Badge Alert copy

Pre-reg note that matters for lore, not for flags: pre-register → guaranteed **HUMAN** badge even if they run out. Staff / village / CTF / goon / community / exhibitor colorways are the **INHUMAN** family.

### How Wired framed it (Kim Zetter, ~1 Aug)

[Wired](https://www.wired.com/story/defcon-34-badge-baochip-andrew-bunnie-huang/) is the official exclusive. The [r/Defcon x-post](https://www.reddit.com/r/Defcon/comments/1vbt117/the_new_defcon_badges_pack_a_unique_open_source/) is that story republished, not a separate dump.

Plot:

1. DEF CON badges have always been more than ID — puzzles, crypto, eggs, even watch gear trains. This year the *device itself* is the thesis.
2. Late 2025, bunnie told **Jeff Moss (Dark Tangent)** he was about to ship Baochip. Moss heard **Agency** in it: verifiable silicon + a thing you keep using. ~**27,000** badges = first mass drop of a chip that until then was a tiny engineering sample.
3. Past badges used COTS MCUs. DC34 is custom, **mostly-open** silicon: OS, firmware, CPU core, crypto engines, I/O published. Huang: *probably the world’s first open-source security token you can inspect all the way down to the bootloader and transistors.*
4. Detach the transparent core → **FIDO2** key + TOTP + password manager. Pretty lights are the *conference* life; the token is the *after* life.
5. Factory stills in the piece: IR image of the die, panels ~a meter on a side. Same visual language as CHEESO’s “oh, and a peacock.”

Syndication (same week): [Techmeme 260801](https://www.techmeme.com/260801/p10), Hackster, TechTimes, Dutch Tweakers recap. Press coverage does not publish `Kp` or a carrier-art cipher.

---

## Agency as silicon (why *this* badge)

CHEESO designed something you want to wear. bunnie designed something you can **trust or attack with your own eyes**. The lore is that those are the same sentence.

From [bunnie’s Baochip-1x post](https://www.bunniestudios.com/blog/2026/baochip-1x-a-mostly-open-22nm-soc-for-high-assurance-applications/) (10 Mar 2026) + 34b / CHEESO:

| Beat | What it means on the badge |
| --- | --- |
| **Betrusted / Snowden question** | “Can we trust hardware not to betray us?” Precursor → Xous → Baochip. DC34 is that research program handed to 27k hackers. |
| **IRIS** | Package lets IR through the die. Compare transistor layout to published RTL without destroying the chip. Transparency is literal. |
| **Hitchhike** | bunnie did not VC-fund a solo tapeout. He rode unused floorplan on **Crossbar**’s 22 nm RRAM security chip (TSMC), swapped in Vexriscv + BIO PicoRVs. “Two brains, one body.” |
| **Mostly open** | Everything that *computes* on data is public. Closed bits (AXI, USB PHY, analog, pads) are framed as “wires.” Honest, not NDA-cosplay. |
| **MMU in a badge MCU** | Virtual memory on a conference toy → Xous processes, not toaster firmware. That’s why it can be a real token after Sunday. |
| **Camera ethics** | Low-res, nearsighted, B&W, no photo store — DEF CON privacy culture baked into the art of the device. |
| **Dev mode is a one-way door** | Load your own code → secrets wipe. The story: *choose* agency (own the silicon) or keep the conference game. See [challenges.md](challenges.md). |

CHEESO’s “secret thing” list matches that split: trade lights, put a picture on the OLED, hunt **two secure-boot keys** (`BAO1`/`BAO2`) for the vuln log — and don’t flip to developer mode if you still want the conference flags.

Talk on the floor: bunnie, **“The DEF CON 34 Badge,”** Fri 7 Aug 2026, 10:30, Main Track 1 ([speakers](https://www.defcon.org/html/defcon-34/dc-34-speakers.html)). Same story, live — **[watch the recording](https://www.youtube.com/watch?v=1plmJlWSKa0)** (DEF CON Video Team).

---

## How to read the art

| Motif | Meaning (as stated) |
| --- | --- |
| **HUMAN = sun** | Attendees / “humans.” Originally one Solarpunk mark; split into two shapes. |
| **INHUMAN = gears / cogwheel** | Staff / departments (goon, village, CTF, community, exhibitor-class, …). |
| **Together** | Solarpunk logo reconstituted if you mentally join sun + gears. |
| **White peacock** (under the core) | Protection, courage, triumph of good over evil. Revealed when you pop the module. |
| **12 hexagons** in the peacock | **12 badge designs this year**, excluding Uber. Silver inlay = HUMAN; gold = INHUMAN. |
| **Peranakan styling** | Callback to **DEF CON Singapore**’s inaugural year (not a crypto alphabet). |
| **Leto Sans** | Chosen for low-vision readability. |
| **Poster on CHEESO** | Titled **“Gotta catch ’em all”** — Pokémon wink at **light genetics** / collect-the-genome, not a second flag format. |

Fab notes from KiCad (not lore, but how the art is built):

- HUMAN: **2-layer**, matte black soldermask, **HASL** copper rim + silver windows, white/silver ink on User.1 / User.2.
- INHUMAN: **4-layer**, department soldermask (12 colorways + Uber), **ENIG** gold inlay. KiCad mask default is **Pantone Cool Gray 8C** (exhibitor).

Wietsman’s 34b joke — *“If you think the SAO specs sheet is a spec sheet, bite me”* — the [SAO PDF](https://media.defcon.org/DEF%20CON%2034/DEF%20CON%2034%20badge/DEF%20CON%2034%20SAO%20Spec%20Sheet.pdf) is mechanical + electrical, not a puzzle sheet.

---

## Where the art actually lives

Not as readable silk strings (footprints are polygons). Sources:

| Source | Link |
| --- | --- |
| CHEESO gallery (HUMAN/INHUMAN front+back, protos, poster) | [cheeso.io/defcon-34-badge](https://cheeso.io/defcon-34-badge) |
| Official stills + mfg / Uber clips | [media pictures/](https://media.defcon.org/DEF%20CON%2034/DEF%20CON%2034%20badge/DEF%20CON%2034%20badge%20-%20pictures/) |
| HUMAN KiCad + PDF | [human-carrier/](https://media.defcon.org/DEF%20CON%2034/DEF%20CON%2034%20badge/DEF%20CON%2034%20badge%20-%20hardware/DEF%20CON%2034%20badge%20human-carrier/) |
| INHUMAN KiCad | [nonhuman-carrier/](https://media.defcon.org/DEF%20CON%2034/DEF%20CON%2034%20badge/DEF%20CON%2034%20badge%20-%20hardware/DEF%20CON%2034%20badge%20nonhuman-carrier/) |
| Peacock / hex / back-logo footprints | [`Library.pretty/Human.pretty/`](https://media.defcon.org/DEF%20CON%2034/DEF%20CON%2034%20badge/DEF%20CON%2034%20badge%20-%20hardware/DEF%20CON%2034%20badge%20human-carrier/Library.pretty/Human.pretty/) (`hex1–3`, `HUMAN_BACK_LOGOS*`, `Bird_artwork*`, `Human_text_*`, …) |
| On-badge tour bitmaps | [dc34-vault `tour_*.svg`](https://github.com/bunnie/dc34-vault/tree/main/src/bitmaps) (credits / genetics explainer, not stego) |

Open KiCad on the `.kicad_pcb` + pretty lib to see copper/mask/inlay the way fab did. Photos on CHEESO are the fastest “what does it look like” pass.

---

## HUMAN vs INHUMAN vs “CTF badge”

Same **core**. Two **carrier outlines**. INHUMAN departments share **`dc34-exhibitor-v2`**; only **ID resistors** + soldermask/inlay color change.

Firmware `BadgeType` ↔ schematic ID (SAO 1–2–3, LSB first) ↔ light niche:

| Type | ID bits | Hue niche (approx) |
| --- | --- | --- |
| Uber | `000` | 220–255 (18 LEDs, unpublished carrier) |
| Other / exhibitor-class | `100` | 160–192 |
| Community | `010` | 32–80 |
| Village | `110` | 80–128 |
| **CTF + contest** | `001` | **192–220** |
| Human | `101` | 128–160 (higher inbreeding mutation) |
| Goon | `011` | 0–20 (forced red base) |

**CTF on this badge = a department colorway + genetics palette**, same LED chain, same SAOs. It is **not** DEF CON CTF village hardware and **not** a second silkscreen puzzle board.

---

## Insights: is the board the CTF?

**Mostly no.** Bunnie’s published game (`defcon-scheme.md`) is:

1. **Honest toy** — breed encrypted light genomes (QR). Theme language: diploid / meiosis / inbreeding. “Gotta catch ’em all.”
2. **Cheater door** — dev mode can paint any lights but **wipes** secrets. If you keep secrets *and* get arbitrary code, *he* wins (audit).
3. **Flags** — shared `k0`/`Ko`, RRAM `THE_FLAG_1`, teased flag-2, plus **two secure-boot keys** (`BAO1`/`BAO2`) called out on CHEESO. See [challenges.md](challenges.md).
4. **Kp drip** — social/HTML proclamations, not hidden in peacock copper.

CHEESO Hall of Fame (already hit Thu Aug 6): boot-trampoline + SATP / BDMA → `k0` + flag1. That is loader/silicon, **not** carrier art.

What the **boards** *do* give you:

- Type ID resistors → firmware knows HUMAN vs CTF vs goon → **starting genome hue**, not a flag string.
- I2C **0x3C / 0x19**, accel IRQs on INHUMAN SAO GPIOs, GPIO4 wake — SAO/BIO playground ([SAO spec](https://media.defcon.org/DEF%20CON%2034/DEF%20CON%2034%20badge/DEF%20CON%2034%20SAO%20Spec%20Sheet.pdf)).
- **TP36** = end of WS2812 chain; detach pads for LED hacking.
- Peacock under the module is **meant to be seen** after token conversion — agency metaphor, not a scan-the-feathers cipher.
- About → **Cheeso** credit screen → **~Meditations~** (`k0` hash / Sealed). Soft eggs only.

Treat copper hexagons / Kingpin back / Peranakan flourish as **narrative**, unless you find an actual encoding (none in footprint text; those mods are geometry-only).

---

## Team (public bios only)

| Who | Role | Public extra |
| --- | --- | --- |
| **bunnie** | SoC, core PCB, plastics, firmware, ops | [bunniestudios](https://www.bunniestudios.com/) |
| **Delia** (CHEESO) | Artwork / “make weird ideas look intentional” | [cheeso.io](https://cheeso.io/) — Romanian in NL; “zoomed to 420%” |
| **Yafsec** | NL lead, design with Delia | GGOH; [DD 87](https://darknetdiaries.com/episode/87/); DC672; “I am not Kevin Nash” |
| **Wietsman** | Carrier placement / routing | Prior Dutch badges (e.g. [WICCON 2023](https://github.com/Wietsman/wiccon_badge_2023)); Eradix; SAO-spec joke |

Vendors (execution, not lore): AQS, King Credie (PCBs), Jiadaxing (plastics + Uber machine work), Aqua Jiang, Crossbar/TSMC.

---

## Suggested look-order

1. DEF CON news **Badge Alert** + **Meet the badge** + [Wired](https://www.wired.com/story/defcon-34-badge-baochip-andrew-bunnie-huang/) (why Moss said yes).
2. CHEESO story + proto gallery + “Gotta catch ’em all” poster.
3. Pop the core: peacock + 12 hexes (protection / token reveal).
4. Flip the carrier: Kingpin / DC14 back (20 years of #badgelife).
5. HUMAN vs a staff INHUMAN side-by-side (sun vs gears, silver vs gold).
6. On-badge tour: light-gene explainers → About/Cheeso → Meditations (hash check only).
7. For flags / crypto, see [challenges.md](challenges.md) — art and press are flavor for genetics, not the sealed writeups.

---

## Press index (story sources, dated)

| When | What | Lore or noise |
| --- | --- | --- |
| Theme season | DEF CON 34 theme = Agency | Thesis for the whole badge |
| Pre-reveal | [Badge Alert: SAO Edition](https://defcon.org/html/defcon-34/dc-34-news.html) | Platform tease + SAO sheet only |
| ~1 Aug 2026 | [Wired / Zetter](https://www.wired.com/story/defcon-34-badge-baochip-andrew-bunnie-huang/) + [r/Defcon 1vbt117](https://www.reddit.com/r/Defcon/comments/1vbt117/the_new_defcon_badges_pack_a_unique_open_source/) | Official exclusive; Moss + bunnie + 27k + token |
| Same window | [Techmeme](https://www.techmeme.com/260801/p10), Hackster, TechTimes | Wired echoes |
| 6 Aug 2026 | [Tweakers / TNV recap](https://technieuwsvandaag.nl/nederlands-ontwerp-def-con-badge/) | NL wearable vs bunnie silicon |
| Thu–Fri news | Welcome party, KevOps (“bring your badge”), headsets | Logistics, not lore |
| Thu 6 Aug | media.defcon.org hardware dump + CHEESO Hall of Fame extracts | Files + early extract credits |
| Fri 7 Aug 10:30 | bunnie talk “The DEF CON 34 Badge” — **[YouTube](https://www.youtube.com/watch?v=1plmJlWSKa0)** | Live telling of the above |

Living how-to page: [34b](https://defcon.org/34b).
