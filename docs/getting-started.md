# Getting started

Authoritative steps: **[DEF CON 34 Badge Help](https://defcon.org/34b)**.  
Hardware: [media.defcon.org](https://media.defcon.org/DEF%20CON%2034/DEF%20CON%2034%20badge/) · [SAO spec](https://media.defcon.org/DEF%20CON%2034/DEF%20CON%2034%20badge/DEF%20CON%2034%20SAO%20Spec%20Sheet.pdf). Dead LED? [hardware.md jump table](hardware.md#led-jump-tables).

## Community

- [Baochip Discord](https://discord.gg/hyWrYz7fa) (badge help; invite may expire)
- [DEF CON Discord](https://discord.gg/defcon) — `#badge-life-chat`
- [Matrix](https://matrix.to/#/#precursor.dev:matrix.org)

Found a real vuln / flag? **dc34@baochip.com** — writeups welcome.

## Exchange light patterns (“gotta catch ’em all”)

1. **Middle button** → your badge shows a **nonce QR** (consent).
2. Donor **scans your nonce** (their middle button = camera).
3. You **scan** their **encrypted gene** QR.
4. Keep or rollback the new lights.

Tip: see a nice pattern? Ask nicely and trade.  
Want to *be* the donor from a laptop? → [The Light Bank](https://ph1r3574r73r.github.io/DEFCON34_Badge/) ([source](../tools/genomics/)).

## Badge customization tools

| Tool | Purpose |
| --- | --- |
| [dc34-image](https://github.com/bunnie/dc34-image) | Official — 128×128 B&W to the OLED over USB |
| [`scripts/upload_oled.py`](../scripts/upload_oled.py) | Same idea, local helper ([development.md](development.md#upload-a-custom-oled-image)) |
| [dc34-bio](https://github.com/bunnie/dc34-bio) | Upload BIO binaries (SAO hacking) |
| [dc34-console](https://github.com/bunnie/dc34-console) | On-badge console (REPL, power, LEDs) |
| [bio-sim](https://github.com/baochip/bio-sim) | RTL sim of the BIO CPU |
| [BIO-surfer](https://baochip.com/bio-surfer/) | Browser view of BIO sim results |

Quick image upload (macOS — find port with `ls /dev/cu.usbmodem*`):

```bash
.venv/bin/python scripts/upload_oled.py --png /path/to/your-128x128.png
# or official:
# pipx install git+https://github.com/bunnie/dc34-image.git
# dc34-image --port /dev/cu.usbmodemXXXX --image your-128x128.png --force
```

One static image only; idle UI already dissolves yours ↔ DEF CON logo.

## Firmware updates

Vulnerabilities get found; patches ship. Download the latest zip (extract before copying):

| Mirror | URL |
| --- | --- |
| Baochip / Betrusted CI | [dc34-badge/latest.zip](https://ci.betrusted.io/releases/latest/baochip/dc34-badge/latest.zip) |
| DEF CON mirror | [defcon.org/34b/latest.zip](https://defcon.org/34b/latest.zip) |

### How to apply

1. Hold **any button** while pressing **reset** or power-cycling.
2. Reset = flat panel on the **lower-right** edge of the module.
3. Screen should say **Update mode**.
4. Connect USB to a host.
5. Extract the zip; copy **three files** onto the mass-storage device:
   - `loader.uf2`
   - `xous.uf2`
   - `swap.uf2`
6. Do **not** copy the raw `.zip`.
7. On Linux: run `sync` or unmount so writes finish.
8. Press **any button** to **commit**. Skipping this leaves swap partially written.

Retry by re-entering Update mode if it fails.

**Most common failure modes:** forgetting `sync` on Linux; forgetting to press a button to commit.

## Developer mode warning

Loading your **own code** puts the badge into **developer mode**. That is a **one-way door**: provisioned secrets are **erased**. You will **lose** the ability to exchange lights with others (until encryption keys are otherwise recovered — treat that as a challenge, not a guarantee).

Choose wisely before flashing experimental firmware during the con.

## After the con (security token)

The removable core is meant for life **beyond** DEF CON as an inspectable open-source security token ([Agency lore](lore.md)).

1. Use the **printed instructions** in the badge conversion kit.
2. You need a **T6 star (Torx)** screwdriver bit.
3. Detach / rehouse the core so it works as a standalone USB-C device.

After conversion it can act as **FIDO2**, **TOTP**, and a password-manager companion (with the browser helper). Exact UX: [dc34-vault](https://github.com/bunnie/dc34-vault).

| Browser | Link |
| --- | --- |
| Chrome | [Chrome Web Store](https://chrome.google.com/webstore/detail/fbjafgnnhopnfkbiegkgncbhadjcgoap) |
| Firefox | [baochip-qr on AMO](https://addons.mozilla.org/addon/baochip-qr/) |

**Power:** USB-C powers the detached core; AA cells stay on the carrier for badge/SAO use.  
**Trust model:** mostly-open RTL + IRIS packaging + Xous — verify rather than trust opaque silicon ([Emerick](https://www.linkedin.com/pulse/def-con-34-baochip-badge-analysis-shift-hardware-root-joseph-emerick-5zcic)).  
**Tips:** update firmware before daily use; keep account recovery codes; developer mode still wipes conference secrets.
