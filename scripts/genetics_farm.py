#!/usr/bin/env python3
"""Gene-QR campaign helper (farm nonce→gene pairs for k0 recovery).

Workflow (no K required):
  1. Batch-mint Bob nonce QRs (header || 12B nonce, base45).
  2. On the sealed badge: scan each nonce → OLED shows gene QR.
  3. Capture gene (phone scan of OLED, or paste base45) → register pair.
  4. Offline: verify layouts / future brute against *all* pairs (same K).

Crypto reminder:
  Gene = AES-256-GCM-SIV(K, nonce, padded_gamete[16]).
  padded = haploid.serialize()[:9] + zeros + badge_type @ [15].
  More (nonce, CT||tag) pairs do not shrink Ko alone, but kill bad layouts
  and make post-Kp-drop farms faster / more reliable.

Usage:
  .venv/bin/python scripts/genetics_farm.py new --count 8
  .venv/bin/python scripts/genetics_farm.py add --nonce-hex … --gene-b45 '…'
  .venv/bin/python scripts/genetics_farm.py add --from-png captures/….png
  .venv/bin/python scripts/genetics_farm.py status
  .venv/bin/python scripts/genetics_farm.py verify
"""

from __future__ import annotations

import argparse
import json
import secrets
import sys
from datetime import datetime, timezone
from pathlib import Path

import base45
import qrcode
from qrcode.constants import ERROR_CORRECT_L
from qrcode.util import MODE_ALPHA_NUM, QRData

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from dc34_gene import BadgeType, describe_padded  # noqa: E402
from verify_k0_gene import (  # noqa: E402
    DEFAULT_KP_PUBLIC,
    build_key_templates,
    decrypt_gene,
    k0_hash,
    materialize,
)

DC34_HEADER = bytes.fromhex("49db7671f34435ed5fddffdfcbb7508a")
FARM_ROOT = ROOT / "captures" / "genetics"
EXPECTED_HASH = "dca9ea49"


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")


def _latest_campaign() -> Path | None:
    if not FARM_ROOT.exists():
        return None
    cams = sorted(FARM_ROOT.glob("campaign_*"), key=lambda p: p.name)
    return cams[-1] if cams else None


def _load_manifest(camp: Path) -> dict:
    path = camp / "manifest.json"
    if not path.exists():
        raise SystemExit(f"missing {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _save_manifest(camp: Path, man: dict) -> None:
    (camp / "manifest.json").write_text(json.dumps(man, indent=2) + "\n", encoding="utf-8")


def write_nonce_qr(nonce: bytes, png: Path, *, box: int = 20, border: int = 6) -> str:
    if len(nonce) != 12:
        raise ValueError("nonce must be 12 bytes")
    # Distinct from header prefix (firmware regenerates if equal)
    if nonce == DC34_HEADER[:12]:
        raise ValueError("nonce collides with header prefix")
    payload = base45.b45encode(DC34_HEADER + nonce).decode()
    qr = qrcode.QRCode(version=None, error_correction=ERROR_CORRECT_L, box_size=box, border=border)
    qr.add_data(QRData(payload, mode=MODE_ALPHA_NUM, check_data=True))
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    png.parent.mkdir(parents=True, exist_ok=True)
    img.save(png)
    (png.with_suffix(".txt")).write_text(payload + "\n", encoding="utf-8")
    return payload


def cmd_new(args: argparse.Namespace) -> int:
    FARM_ROOT.mkdir(parents=True, exist_ok=True)
    camp = FARM_ROOT / f"campaign_{_utc()}"
    camp.mkdir(parents=True, exist_ok=False)
    nonces_dir = camp / "nonces"
    nonces_dir.mkdir()
    entries = []
    for i in range(args.count):
        while True:
            nonce = secrets.token_bytes(12)
            if nonce != DC34_HEADER[:12]:
                break
        name = f"nonce_{i:02d}_{nonce.hex()}"
        png = nonces_dir / f"{name}.png"
        payload = write_nonce_qr(nonce, png, box=args.box)
        entries.append(
            {
                "id": i,
                "nonce_hex": nonce.hex(),
                "png": str(png.relative_to(ROOT)),
                "b45": payload,
                "gene_b45": None,
                "gene_hex": None,
                "captured_at": None,
            }
        )
        print(f"  [{i}] {png.name}")
    man = {
        "created_at": _utc(),
        "expect_hash": EXPECTED_HASH,
        "kp_public_hex": DEFAULT_KP_PUBLIC.hex(),
        "pairs": entries,
        "notes": (
            "Scan each nonce PNG with the badge camera (ShowKey / breed flow). "
            "When the gene QR appears on the OLED, scan it with a phone and "
            "`genetics_farm.py add --nonce-hex … --gene-b45 …` (or --from-png)."
        ),
    }
    _save_manifest(camp, man)
    print(f"\ncampaign: {camp}")
    print(f"manifest: {camp / 'manifest.json'}")
    print(f"next: scan nonces on badge, then register genes with `add`")
    return 0


def _decode_gene_b45(s: str) -> bytes:
    raw = base45.b45decode(s.strip())
    if len(raw) != 32:
        raise SystemExit(f"gene must decode to 32 bytes (CT||tag), got {len(raw)}")
    return raw


def _try_decode_png(png: Path) -> str | None:
    try:
        from PIL import Image
        from pyzbar.pyzbar import decode as zbar_decode
    except ImportError:
        return None
    img = Image.open(png)
    hits = zbar_decode(img)
    if not hits:
        return None
    data = hits[0].data.decode("ascii", "replace")
    return data


def cmd_add(args: argparse.Namespace) -> int:
    camp = Path(args.campaign) if args.campaign else _latest_campaign()
    if camp is None:
        raise SystemExit("no campaign — run `new` first")
    man = _load_manifest(camp)

    gene_b45 = args.gene_b45
    if args.from_png:
        decoded = _try_decode_png(Path(args.from_png))
        if not decoded:
            raise SystemExit(
                f"could not decode QR from {args.from_png} "
                "(install pyzbar+PIL, or pass --gene-b45 manually)"
            )
        gene_b45 = decoded
        print(f"decoded from png: {gene_b45[:48]}…")

    if not gene_b45:
        raise SystemExit("need --gene-b45 or --from-png")
    if not args.nonce_hex:
        raise SystemExit("need --nonce-hex (match the nonce you scanned)")

    nonce = bytes.fromhex(args.nonce_hex)
    if len(nonce) != 12:
        raise SystemExit("nonce must be 12 bytes hex")
    gene = _decode_gene_b45(gene_b45)

    hit = None
    for p in man["pairs"]:
        if p["nonce_hex"] == nonce.hex():
            hit = p
            break
    if hit is None:
        hit = {
            "id": len(man["pairs"]),
            "nonce_hex": nonce.hex(),
            "png": None,
            "b45": None,
            "gene_b45": None,
            "gene_hex": None,
            "captured_at": None,
        }
        man["pairs"].append(hit)
        print("note: nonce was not in campaign list — appended as ad-hoc pair")

    hit["gene_b45"] = gene_b45.strip()
    hit["gene_hex"] = gene.hex()
    hit["captured_at"] = _utc()
    _save_manifest(camp, man)

    # also write a verify-compatible capture json
    out = camp / f"pair_{nonce.hex()[:8]}.json"
    try:
        camp_rel = str(camp.resolve().relative_to(ROOT))
    except ValueError:
        camp_rel = str(camp)
    out.write_text(
        json.dumps(
            {
                "captured_at": hit["captured_at"],
                "method": "genetics_farm",
                "campaign": camp_rel,
                "nonce_hex": nonce.hex(),
                "gene_b45": hit["gene_b45"],
                "gene_hex": gene.hex(),
                "gene_len": 32,
                "structure": "AES-256-GCM-SIV CT(16)||tag(16); PT=padded gamete 16B",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"registered pair → {out}")
    print(f"pairs with genes: {sum(1 for p in man['pairs'] if p.get('gene_hex'))}/{len(man['pairs'])}")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    camp = Path(args.campaign) if args.campaign else _latest_campaign()
    if camp is None:
        print("no campaigns yet")
        return 1
    man = _load_manifest(camp)
    print(f"campaign: {camp}")
    print(f"created:  {man.get('created_at')}")
    n_gene = 0
    for p in man["pairs"]:
        has = bool(p.get("gene_hex"))
        n_gene += int(has)
        mark = "GENE" if has else "wait"
        print(f"  [{p['id']:02d}] {mark}  nonce={p['nonce_hex'][:16]}…")
    print(f"ready: {n_gene}/{len(man['pairs'])} gene pairs")
    print(
        "structure hint: PT[9:15]==0, PT[15]∈badge types; "
        "same K must decrypt every pair"
    )
    return 0


def structure_ok(pt: bytes) -> tuple[bool, str]:
    if len(pt) != 16:
        return False, f"len {len(pt)}"
    if any(pt[9:15]):
        return False, f"pad not zero: {pt[9:15].hex()}"
    bt = pt[15]
    if bt not in list(BadgeType):
        return False, f"bad badge_type {bt}"
    return True, describe_padded(pt)


def cmd_verify(args: argparse.Namespace) -> int:
    camp = Path(args.campaign) if args.campaign else _latest_campaign()
    if camp is None:
        raise SystemExit("no campaign")
    man = _load_manifest(camp)
    pairs = [
        (bytes.fromhex(p["nonce_hex"]), bytes.fromhex(p["gene_hex"]))
        for p in man["pairs"]
        if p.get("gene_hex")
    ]
    if not pairs:
        raise SystemExit("no gene pairs registered — capture some first")

    pub = bytes.fromhex(man.get("kp_public_hex", DEFAULT_KP_PUBLIC.hex()))
    templates = build_key_templates(pub)
    print(f"campaign {camp.name}: {len(pairs)} gene pair(s)")
    print(f"public Kp: {pub.hex()} ({len(pub)} B)")
    print()

    # Fixed layouts that are fully determined
    print("Fixed layouts (public-only complete keys):")
    any_hit = False
    for name, slots, note in templates:
        k = materialize(slots)
        if k is None:
            u = sum(1 for v in slots if v is None)
            print(f"  {name}: skip ({u} unknown bytes) — {note}")
            continue
        ok_all = True
        pts = []
        for nonce, gene in pairs:
            pt = decrypt_gene(k, nonce, gene)
            if pt is None:
                ok_all = False
                break
            so, msg = structure_ok(pt)
            pts.append((pt, so, msg))
        h = k0_hash(k)
        if ok_all:
            any_hit = True
            print(f"  HIT {name} hash={h} match={h == EXPECTED_HASH}")
            for pt, so, msg in pts:
                print(f"    pt={pt.hex()} structure_ok={so} {msg}")
        else:
            print(f"  miss {name} hash={h}")
    if not any_hit:
        print("  (no complete public layout decrypts — expected until more Kp)")

    print()
    print("Consistency check: same K must open every pair.")
    print("When more Kp drops, re-run verify / feed pairs into verify_k0_gene.py --brute-max …")
    print(f"Pair files: {camp}/pair_*.json")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_new = sub.add_parser("new", help="create campaign + batch nonce QRs")
    p_new.add_argument("--count", type=int, default=8)
    p_new.add_argument("--box", type=int, default=20)
    p_new.set_defaults(func=cmd_new)

    p_add = sub.add_parser("add", help="register a captured gene for a nonce")
    p_add.add_argument("--campaign", default=None)
    p_add.add_argument("--nonce-hex", default=None)
    p_add.add_argument("--gene-b45", default=None)
    p_add.add_argument("--from-png", default=None, help="decode gene QR from image")
    p_add.set_defaults(func=cmd_add)

    p_st = sub.add_parser("status", help="show campaign progress")
    p_st.add_argument("--campaign", default=None)
    p_st.set_defaults(func=cmd_status)

    p_v = sub.add_parser("verify", help="try layouts against all captured pairs")
    p_v.add_argument("--campaign", default=None)
    p_v.set_defaults(func=cmd_verify)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
