# Sealed-safe BIO hello (GPIO 21 / SAO connector pin 1)

Hand-assembled RV32 blink — entry at 0x0, no host RAM access. Demonstrates that unsigned BIO loads stay **Sealed** (does not enter developer mode).

## Build (optional)

Needs Zig + a clone of [baochip/bio-sim](https://github.com/baochip/bio-sim):

```bash
cd /path/to/bio-sim/sw
zig build -Dmodule=blink
# copy blink.bin next to this README if rebuilding
```

Prebuilt: `blink_sao1.bin` in this folder.

## Upload

Use [bunnie/dc34-bio](https://github.com/bunnie/dc34-bio) (or this repo’s `scripts/bio_memprobe.py`-style serial path). Then check Menu → About → … → **~Meditations~** → still **Sealed**.

Do not flash developer-signed firmware. Do not send CRC-valid `test k0 …` while hunting conference secrets.
