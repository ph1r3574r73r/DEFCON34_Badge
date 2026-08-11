# Development

Authoritative index: [defcon.org/34b](https://defcon.org/34b) · chip docs: [baochip.com](https://baochip.com/) · coder’s guide: [baochip.github.io/baochip-1x](https://baochip.github.io/baochip-1x/).  
Full GitHub + press catalog: [repos.md](repos.md). Host scripts in this tree: [`scripts/README.md`](../scripts/README.md).

## Critical warning: developer mode

Flashing your own code enters **developer mode**.

- **One-way** transition
- **Erases provisioned secrets** (including conference challenge / light-exchange material)
- You will not be able to trade lights with stock badges afterward (unless keys are recovered some other way)

If you still care about con challenges, wait until after you’re done hunting — or dual-boot carefully.

## Quick links (firmware & silicon)

| Need | Go |
| --- | --- |
| Vault / lights / `k0` scheme | [bunnie/dc34-vault](https://github.com/bunnie/dc34-vault) ([`defcon-scheme.md`](https://github.com/bunnie/dc34-vault/blob/main/defcon-scheme.md)) |
| Console / LEDs / BIO genes | [bunnie/dc34-console](https://github.com/bunnie/dc34-console) |
| Shared types / genomes | [bunnie/dc34-api](https://github.com/bunnie/dc34-api) |
| Core KiCad | [bunnie/dc34-core-hw](https://github.com/bunnie/dc34-core-hw) · [media core-board](https://media.defcon.org/DEF%20CON%2034/DEF%20CON%2034%20badge/DEF%20CON%2034%20badge%20-%20hardware/DEF%20CON%2034%20badge%20core-board/) |
| Carriers | [HUMAN](https://media.defcon.org/DEF%20CON%2034/DEF%20CON%2034%20badge/DEF%20CON%2034%20badge%20-%20hardware/DEF%20CON%2034%20badge%20human-carrier/) · [INHUMAN](https://media.defcon.org/DEF%20CON%2034/DEF%20CON%2034%20badge/DEF%20CON%2034%20badge%20-%20hardware/DEF%20CON%2034%20badge%20nonhuman-carrier/) · [LED jump table](hardware.md#led-jump-tables) |
| Xous | [betrusted-io/xous-core](https://github.com/betrusted-io/xous-core) · [Xous Book](https://betrusted.io/xous-book/) |
| RTL / BIO / Dabao | [baochip-1x](https://github.com/baochip/baochip-1x) · [bio-sim](https://github.com/baochip/bio-sim) · [dabao](https://github.com/baochip/dabao) · [BIO-surfer](https://baochip.com/bio-surfer/) |

Everything else (community repos, CI, press): [repos.md](repos.md).

## Upload a custom OLED image

Ideal input: **128×128 black-and-white PNG**. Stock firmware stores **one** static bitmap in PDDB (no multi-frame animation). On idle, the UI dissolves between your image and the DEF CON logo about every 3s.

**Wire format gotcha:** bitmap words must be packed **big-endian** (`u32::from_be_bytes` in console). Little-endian packing (easy mistake on macOS/Python `struct.pack("I")`) scrambles the image into 32-pixel strips.

### Local script (this repo)

```bash
# Needs pyserial (+ Pillow for --png); port auto-detects
.venv/bin/python scripts/upload_oled.py --png /path/to/your-128x128.png
.venv/bin/python scripts/upload_oled.py --line HACK --line THE --line PLANET
```

### Official tool (`dc34-image`)

```bash
pipx install git+https://github.com/bunnie/dc34-image.git

# Linux
dc34-image --port /dev/ttyACM0 --image your-128x128.png --force
# macOS (prefer /dev/cu.usbmodem* over tty.*)
dc34-image --port /dev/cu.usbmodemXXXX --image your-128x128.png --force
# Windows
dc34-image --port COM3 --image your-128x128.png --force
dc34-image --port /dev/ttyACM0 --clear
```

| Flag | Description |
| --- | --- |
| `--port` | Serial port (`/dev/ttyACM*`, `/dev/cu.usbmodem*`, `COMx`) |
| `--image` | Path to image file |
| `--force` | Auto-convert / resize to 128×128 B&W |
| `--clear` | Clear image on device and exit |
| `--delay` | Delay between chunks in seconds (default `0.2`) |

Port discovery notes: [dc34-image README](https://github.com/bunnie/dc34-image).

## Upload BIO code (sealed-safe)

Unsigned PicoRV on a BIO core — **does not** enter developer mode if only the stock console `bio` path is used.

```bash
pipx install git+https://github.com/bunnie/dc34-bio.git
# then follow that repo’s README for port + binary args
```

This tree also has a tiny sealed demo under [`bio/hello/`](../bio/hello/) and a firewall probe under [`bio/memprobe/`](../bio/memprobe/). Stock firmware keeps DMA filters closed (GPIO/SAO only). Prefer `--delay` ≥ 0.3s if uploads flake.

## Reproducible boot / verify

Vault source pins [sbellem/baobit](https://github.com/sbellem/baobit) for rebuilding `boot1-lite` and comparing hashes to a live device audit. That is the supply-chain / secure-boot track — separate from conference `k0`. See the baobit README / `VERIFY.md` (Guix-based).

## Other SDKs / ports

| Resource | Notes |
| --- | --- |
| [ArmstrongSubero/dabao-sdk](https://github.com/ArmstrongSubero/dabao-sdk) | Third-party bare-metal **C SDK** for Baochip-1x (linked from 34b) |
| [MicroPython experimental port](https://github.com/orgs/micropython/discussions/19580) | WIP; Dabao target |
| [Dabao Book / coder’s guide](https://baochip.github.io/baochip-1x/) | Dev-board reference; much applies to the badge |
| [bunnie/dabao-tester-app](https://github.com/bunnie/dabao-tester-app) | Example stand-alone Xous app for Dabao |

## Platform stack

```
Apps (vault, console, …)     Host tools (dc34-image, dc34-bio)
        │                              │
   Xous microkernel (Rust)      USB-serial / UF2
        │
 Baochip-1x (Vexriscv + BIO PicoRV32s + crypto + RRAM)
        │
   Core module PCB  ↔  Carrier PCB + SAOs
```

## Contributing findings

1. Reproduce on **latest** firmware.
2. Prefer a **PR** or **issue** on the relevant repo.
3. Or email **dc34@baochip.com**.

The project expects community review; patches already exist for early issues.
