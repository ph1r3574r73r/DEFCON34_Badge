#!/usr/bin/env python3
"""Generate a fake DC34 nonce QR (base45 of DC34_HEADER || 12-byte nonce).

Badge firmware uses ECC M (often QR v3 for 42-char payloads). Phone screens are
hard for the nearsighted badge camera — default here is ECC L (often v2), which
is easier to decode. Decoded content is what matters; ECC is only for the printed QR.

Usage:
  .venv/bin/python scripts/gen_nonce_qr.py
  .venv/bin/python scripts/gen_nonce_qr.py --ecc M   # match badge-to-badge
  .venv/bin/python scripts/gen_nonce_qr.py --nonce 0102030405060708090a0b0c
"""

from __future__ import annotations

import argparse
from pathlib import Path

import base45
import qrcode
from qrcode.constants import ERROR_CORRECT_L, ERROR_CORRECT_M
from qrcode.util import MODE_ALPHA_NUM, QRData

DC34_HEADER = bytes.fromhex("49db7671f34435ed5fddffdfcbb7508a")
DEFAULT_NONCE = bytes.fromhex("0102030405060708090a0b0c")


def main() -> None:
    p = argparse.ArgumentParser(description="Generate fake DC34 nonce QR payload + PNG")
    p.add_argument("--nonce", default=DEFAULT_NONCE.hex(), help="12-byte nonce as hex (24 chars)")
    p.add_argument("--ecc", choices=("L", "M"), default="L", help="QR ECC (L easier on phone)")
    p.add_argument("--png", type=Path, default=None)
    p.add_argument("--txt", type=Path, default=Path("captures/fake_nonce_qr.txt"))
    p.add_argument("--box", type=int, default=28)
    p.add_argument("--border", type=int, default=8)
    args = p.parse_args()

    nonce = bytes.fromhex(args.nonce)
    if len(nonce) != 12:
        raise SystemExit(f"nonce must be 12 bytes, got {len(nonce)}")

    raw = DC34_HEADER + nonce
    payload = base45.b45encode(raw).decode()

    args.txt.parent.mkdir(parents=True, exist_ok=True)
    args.txt.write_text(payload + "\n", encoding="utf-8")

    ecc = ERROR_CORRECT_L if args.ecc == "L" else ERROR_CORRECT_M
    png = args.png or Path(f"captures/fake_nonce_qr_ecc{args.ecc}.png")

    qr = qrcode.QRCode(version=None, error_correction=ecc, box_size=args.box, border=args.border)
    qr.add_data(QRData(payload, mode=MODE_ALPHA_NUM, check_data=True))
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    # Extra scale for phone full-screen
    img = img.resize((img.size[0] * 2, img.size[1] * 2))
    png.parent.mkdir(parents=True, exist_ok=True)
    img.save(png)

    # Keep stable alias for the easy default
    if args.ecc == "L":
        alias = Path("captures/fake_nonce_qr.png")
        img.save(alias)
        print(f"also wrote {alias}")

    print(f"payload: {payload}")
    print(f"raw hex: {raw.hex()}")
    print(f"wrote {args.txt}")
    print(f"wrote {png} (QR version {qr.version}, ECC {args.ecc}, {img.size[0]}x{img.size[1]})")
    print("Scan tips: GeneScan (middle/🔥); full-screen bright; or print on paper / use laptop LCD.")


if __name__ == "__main__":
    main()
