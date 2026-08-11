# DEF CON 34 badge — notes from the floor

You got a glowing peacock (or a cog). It’s also a tiny computer you can **inspect**, **hack**, and **keep using** after Sunday.

This repo is field notes and toys from DEF CON 34: how the light game works, what’s safe to poke while **Sealed**, sealed-dump tooling, and **The Light Bank** — a browser donor for breeding LED genomes.

Official how-to (start here if you’re holding a badge): **[defcon.org/34b](https://defcon.org/34b)**  
Found something cool? Tell the builders: **dc34@baochip.com**

Built by **bunnie** (Baochip) + **CHEESO**. Theme of the year: **agency**.

Best first watch: [bunnie’s DEF CON 34 badge talk](https://www.youtube.com/watch?v=1plmJlWSKa0) (chip, BIO, token, why it exists).

---

## Try the fun stuff first

### The Light Bank

Design a donor gene → scan your badge’s nonce QR → mint a gene QR it will accept.

```bash
cd tools/genomics && python3 -m http.server 8765
# open http://127.0.0.1:8765/  (webcam needs localhost, not file://)
```

After this repo is on GitHub: **Settings → Pages → GitHub Actions** deploys that folder automatically.

Same-type donors can trigger **inbreeding** mutation. Mutation **None** sends your design verbatim — the badge still *mixes* it with a new egg. Details: [docs/genetics.md](docs/genetics.md).

### Talk to the badge over USB

```bash
# macOS — port name varies
.venv/bin/python scripts/upload_oled.py --png your-128x128.png
```

More: [docs/getting-started.md](docs/getting-started.md) · [docs/development.md](docs/development.md)

### Deeper: sealed flag dump

Want `THE_FLAG_1` **without** wiping the toy? amattas’s hop is the path; this tree’s QR-on-OLED variant is why filming beats OCR.

→ original: [*Only 132 Bytes…*](https://www.anthonymattas.com/articles/only-132-bytes)  
→ why QR + how to flash: [`tools/132hop/`](tools/132hop/)  
→ challenge map: [docs/challenges.md](docs/challenges.md)

**House rules while sealed-hunting:** don’t flash developer-signed firmware, don’t CRC-valid `test k0 …`, always restore stock `loader.uf2` after a hang hop. Dev mode is a one-way door — secrets go bye-bye.

---

## Map of the repo

| Want… | Go here |
| --- | --- |
| “What *is* this badge?” | [docs/overview.md](docs/overview.md) · [docs/lore.md](docs/lore.md) |
| Buttons, lights, updates | [docs/getting-started.md](docs/getting-started.md) |
| Pinouts / SAO / KiCad | [docs/hardware.md](docs/hardware.md) |
| Breed / genomes | [docs/genetics.md](docs/genetics.md) · [`tools/genomics/`](tools/genomics/) |
| Host USB / gene scripts | [`scripts/README.md`](scripts/README.md) |
| What’s the challenge? | [docs/challenges.md](docs/challenges.md) |
| Sealed hop / QR dump | [`tools/132hop/`](tools/132hop/) |
| Keep it after the con | [docs/getting-started.md](docs/getting-started.md#after-the-con-security-token) |
| Upstream + community code | [docs/repos.md](docs/repos.md) |
| Who taught us | [docs/CREDITS.md](docs/CREDITS.md) |

Private Discord dumps, raw device captures, promo/reference stills, BT6 branding, and chat scrapers stay **off git** (`/captures/`, `/local_scripts/`, genomics stills). Share writeups, not other people’s DMs or third-party art.

---

## Spirit check

- **Ask before you scan.** Breeding is consent-QR culture.
- **Read the source.** Most of the platform is public — that’s the point.
- **Credit the climb.** See [CREDITS](docs/CREDITS.md) — amattas, ohyou_, and a lot of Discord brain-melts.
- **Leave it better.** Responsible disclosure beats a flex that bricks someone else’s badge.

See a nice light pattern? Ask nicely and trade.  
See a sealed secret? Write it up so the next person learns faster than you did.

---

*Authoritative docs live on [34b](https://defcon.org/34b). This tree is community notes + tools — see [LICENSE](LICENSE). Bring curiosity, leave ego at coat check.*
