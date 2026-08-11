# The Light Bank

Breed pretty lights without standing in a hallway squinting at someone else’s OLED.

1. Pick a **donor type** + tune the **9-byte gene**
2. Tap the core → scan your badge’s **nonce QR**
3. Scan the **gene QR** back onto the badge
4. Keep or rollback — same as the floor game

```bash
python3 -m http.server 8765
# → http://127.0.0.1:8765/
```

Needs **localhost** or **HTTPS** (webcam + WebCrypto). Live: https://ph1r3574r73r.github.io/DEFCON34_Badge/

**Tips:** Mutation **None** = exact sperm; same type as you → inbreeding. The badge still blends with a new egg — you’re donating DNA, not painting pixels.

## Attribution

Badge by **Baochip** / **CHEESO** for DEF CON 34. Carrier **outlines** in `assets/*.svg` are simplified vectors derived from the public KiCad drop on [media.defcon.org](https://media.defcon.org/DEF%20CON%2034/DEF%20CON%2034%20badge/) (HUMAN / INHUMAN); Uber is an approximate silhouette (no public Uber KiCad). Not an official DEF CON / Baochip / CHEESO product. Public `k0` is community-shared so the light game stays playable.

Promo / reference photos stay **out of git** — this site only ships the SVG outlines + LED layout math. More: [docs/genetics.md](../../docs/genetics.md) · [CREDITS](../../docs/CREDITS.md).
