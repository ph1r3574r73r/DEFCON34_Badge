#!/usr/bin/env python3
"""DC34 light-breed protocol helper / peer-badge simulator.

Crypto fact (important):
  Gene QR ≠ the key. Gene = AES-256-GCM-SIV encrypt(K, nonce, gamete[16]).
  Knowing fake-nonce + gene response gives a ciphertext oracle for checking
  candidate K values (see verify_k0_gene.py). It does NOT reveal K.

Gene model (scripts/dc34_gene.py) ports Haploid/Diploid/meiosis/mutate from
dc34-api and get_padded_gamete from dc34-vault config.rs.

What works WITHOUT K:
  - Emit Bob's nonce QR (header || 12-byte nonce, base45) — badge will encrypt
    its gamete under that nonce and show a gene QR you can capture.
  - Decode gene base45 → CT||tag hex for offline verification.
  - Build synthetic peer diploids / padded gametes (no encrypt).

What REQUIRES K (--key-hex):
  - Act as donor peer: meiosis+mutate → encrypt → gene QR your sealed badge accepts.
  - Act as receiver: decrypt a gene under your locked nonce.

Usage:
  .venv/bin/python scripts/breed_sim.py nonce
  .venv/bin/python scripts/breed_sim.py decode --gene-b45 'Z+5O:…'
  .venv/bin/python scripts/breed_sim.py diploid --badge-type goon --seed 1
  .venv/bin/python scripts/breed_sim.py peer --key-hex <64hex> --nonce-hex <24hex> --badge-type goon
  .venv/bin/python scripts/breed_sim.py respond --key-hex <64hex> --nonce-hex <24hex>
  .venv/bin/python scripts/breed_sim.py accept  --key-hex <64hex> --nonce-hex <24hex> --gene-b45 '…'
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import base45
import qrcode
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCMSIV
from qrcode.constants import ERROR_CORRECT_L, ERROR_CORRECT_M
from qrcode.util import MODE_ALPHA_NUM, QRData

# same-dir import when run as scripts/breed_sim.py
sys.path.insert(0, str(Path(__file__).resolve().parent))
from dc34_gene import (  # noqa: E402
    BADGE_ALIASES,
    MUTATION_ALIASES,
    BadgeType,
    Diploid,
    Haploid,
    MutationRate,
    describe_padded,
    get_padded_gamete,
    make_rng,
    parse_badge,
    parse_rate,
)

DC34_HEADER = bytes.fromhex("49db7671f34435ed5fddffdfcbb7508a")
DEFAULT_OUT = Path("captures")


def write_qr(payload: str, png: Path, *, ecc: str = "L", box: int = 28, border: int = 8) -> None:
    ecc_c = ERROR_CORRECT_L if ecc == "L" else ERROR_CORRECT_M
    qr = qrcode.QRCode(version=None, error_correction=ecc_c, box_size=box, border=border)
    qr.add_data(QRData(payload, mode=MODE_ALPHA_NUM, check_data=True))
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    img = img.resize((img.size[0] * 2, img.size[1] * 2))
    png.parent.mkdir(parents=True, exist_ok=True)
    img.save(png)
    print(f"wrote {png} (QR v{qr.version}, ECC {ecc}, {img.size[0]}x{img.size[1]})")


def require_key(hex_s: str) -> bytes:
    key = bytes.fromhex(hex_s)
    if len(key) != 32:
        raise SystemExit("key must be 32 bytes (64 hex chars)")
    return key


def require_nonce(hex_s: str) -> bytes:
    nonce = bytes.fromhex(hex_s)
    if len(nonce) != 12:
        raise SystemExit("nonce must be 12 bytes (24 hex chars)")
    return nonce


def build_gamete(args: argparse.Namespace) -> tuple[bytes, dict]:
    """Return (16-byte padded gamete, metadata)."""
    meta: dict = {}
    if getattr(args, "gamete_hex", None):
        gamete = bytes.fromhex(args.gamete_hex)
        if len(gamete) != 16:
            raise SystemExit("gamete must be 16 bytes")
        meta["source"] = "gamete_hex"
        meta["gamete_hex"] = gamete.hex()
        return gamete, meta

    bt = parse_badge(getattr(args, "badge_type", "human"))
    rate = parse_rate(getattr(args, "rate", "baseline"))
    rng = make_rng(getattr(args, "seed", None))
    meta["badge_type"] = bt.name.lower()
    meta["badge_type_u8"] = int(bt)
    meta["mutation_rate"] = rate.name.lower()
    if getattr(args, "seed", None) is not None:
        meta["seed"] = args.seed

    if getattr(args, "diploid_hex", None):
        dip = Diploid.deserialize(bytes.fromhex(args.diploid_hex))
        if dip is None:
            raise SystemExit("diploid must be 18 bytes (9+9 haploid)")
        meta["source"] = "diploid_hex"
    elif getattr(args, "zeros", False):
        # legacy stub: zeros + badge type (pre-gene-port behavior)
        gamete = bytearray(16)
        gamete[15] = int(bt)
        meta["source"] = "zeros_pad"
        meta["gamete_hex"] = bytes(gamete).hex()
        return bytes(gamete), meta
    else:
        dip = Diploid.from_type(bt, rng)
        meta["source"] = "diploid_from_type"

    meta["diploid_hex"] = dip.serialize().hex()
    gamete = get_padded_gamete(
        dip,
        bt,
        rate,
        rng,
        mutate_gamete=not getattr(args, "no_mutate", False),
    )
    meta["gamete_hex"] = gamete.hex()
    meta["describe"] = describe_padded(gamete)
    return gamete, meta


def emit_gene_qr(
    key: bytes,
    nonce: bytes,
    gamete: bytes,
    *,
    png: Path | None,
    ecc: str,
    method: str,
    extra: dict | None = None,
) -> str:
    ct_tag = AESGCMSIV(key).encrypt(nonce, gamete, None)
    assert len(ct_tag) == 32
    payload = base45.b45encode(ct_tag).decode()
    out = png or (DEFAULT_OUT / "breed_sim_gene.png")
    txt = out.with_suffix(".txt")
    txt.write_text(payload + "\n", encoding="utf-8")
    write_qr(payload, out, ecc=ecc)

    capture = {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "method": method,
        "nonce_hex": nonce.hex(),
        "gene_b45": payload,
        "gene_hex": ct_tag.hex(),
        "gamete_hex": gamete.hex(),
        "gamete_describe": describe_padded(gamete),
        "key_hash_prefix": hashlib.sha256(key).hexdigest()[:8],
        "note": "Requires matching K on receiver badge to accept",
    }
    if extra:
        capture.update(extra)
    cap_path = DEFAULT_OUT / "qr" / f"{method}_{nonce.hex()[:8]}.json"
    cap_path.parent.mkdir(parents=True, exist_ok=True)
    cap_path.write_text(json.dumps(capture, indent=2) + "\n", encoding="utf-8")

    print(f"payload: {payload}")
    print(f"gene_hex: {ct_tag.hex()}")
    print(f"gamete:   {gamete.hex()}")
    print(f"describe: {describe_padded(gamete)}")
    print(f"wrote {txt}")
    print(f"wrote {cap_path}")
    return payload


def cmd_nonce(args: argparse.Namespace) -> None:
    import secrets

    nonce = bytes.fromhex(args.nonce) if args.nonce else secrets.token_bytes(12)
    if len(nonce) != 12:
        raise SystemExit("nonce must be 12 bytes")
    raw = DC34_HEADER + nonce
    payload = base45.b45encode(raw).decode()
    out = args.png or (DEFAULT_OUT / "breed_sim_nonce.png")
    txt = out.with_suffix(".txt")
    txt.write_text(payload + "\n", encoding="utf-8")
    write_qr(payload, out, ecc=args.ecc)
    print(f"payload: {payload}")
    print(f"nonce_hex: {nonce.hex()}")
    print(f"raw_hex:   {raw.hex()}")
    print(f"wrote {txt}")
    print("On badge: middle/🔥 GeneScan → scan this QR → photo the gene response.")
    print("Without K you can CAPTURE the gene; you cannot forge/decrypt a valid one.")


def cmd_decode(args: argparse.Namespace) -> None:
    if args.gene_b45:
        raw = base45.b45decode(args.gene_b45.strip())
    elif args.gene_hex:
        raw = bytes.fromhex(args.gene_hex)
    else:
        raise SystemExit("need --gene-b45 or --gene-hex")
    print(f"len: {len(raw)}")
    print(f"hex: {raw.hex()}")
    if len(raw) == 32:
        print(f"ct:  {raw[:16].hex()}")
        print(f"tag: {raw[16:].hex()}")
        print("layout: AES-GCM-SIV CT(16)||tag(16) — needs K + nonce to decrypt")
    elif len(raw) >= 16 + 12 and raw[:16] == DC34_HEADER:
        print("header: OK")
        print(f"nonce:  {raw[16:28].hex()}")
        print("this is a NONCE QR, not a gene")
    else:
        print("unrecognized length/layout")


def cmd_diploid(args: argparse.Namespace) -> None:
    bt = parse_badge(args.badge_type)
    dip = Diploid.from_type(bt, make_rng(args.seed))
    hx = dip.serialize().hex()
    out = {
        "badge_type": bt.name.lower(),
        "badge_type_u8": int(bt),
        "diploid_hex": hx,
        "a": dip.a.as_dict(),
        "b": dip.b.as_dict(),
        "phenotype": dip.phenotype().as_dict(),
    }
    if args.seed is not None:
        out["seed"] = args.seed
    if args.save:
        path = Path(args.save)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {path}")
    print(json.dumps(out, indent=2))


def cmd_gamete(args: argparse.Namespace) -> None:
    gamete, meta = build_gamete(args)
    print(json.dumps({**meta, "gamete_hex": gamete.hex(), "describe": describe_padded(gamete)}, indent=2))


def cmd_peer(args: argparse.Namespace) -> None:
    """Full peer donor: synthetic diploid → padded gamete → gene QR under Bob's nonce."""
    key = require_key(args.key_hex)
    nonce = require_nonce(args.nonce_hex)
    gamete, meta = build_gamete(args)
    emit_gene_qr(
        key,
        nonce,
        gamete,
        png=args.png,
        ecc=args.ecc,
        method="breed_sim_peer",
        extra=meta,
    )
    print("On badge: show YOUR nonce first (←/→), then scan this gene QR.")
    print("Peer gene differs from yours; shared K must match for accept.")


def cmd_respond(args: argparse.Namespace) -> None:
    """Donor mode: encrypt gamete under Bob's nonce → gene QR."""
    key = require_key(args.key_hex)
    nonce = require_nonce(args.nonce_hex)
    gamete, meta = build_gamete(args)
    emit_gene_qr(
        key,
        nonce,
        gamete,
        png=args.png,
        ecc=args.ecc,
        method="breed_sim_respond",
        extra=meta,
    )
    print("On badge: show YOUR nonce first (←/→), then scan this gene QR.")


def cmd_accept(args: argparse.Namespace) -> None:
    """Receiver mode: decrypt gene under locked nonce; parse haploid if possible."""
    key = require_key(args.key_hex)
    nonce = require_nonce(args.nonce_hex)
    if args.gene_b45:
        data = base45.b45decode(args.gene_b45.strip())
    else:
        data = bytes.fromhex(args.gene_hex)
    try:
        pt = AESGCMSIV(key).decrypt(nonce, data, None)
    except InvalidTag:
        raise SystemExit("DECRYPT FAIL — wrong K, wrong nonce, or truncated gene")
    print(f"OK plaintext ({len(pt)} bytes): {pt.hex()}")
    print(f"describe: {describe_padded(pt)}")
    h = Haploid.deserialize(pt)
    if h is not None:
        print(f"haploid: {h.as_dict()}")
    if len(pt) == 16:
        try:
            bt = BadgeType(pt[15])
            print(f"badge_type: {bt.name.lower()} ({int(bt)})")
        except ValueError:
            print(f"badge_type byte: {pt[15]} (unknown)")
    print(f"key hash prefix: {hashlib.sha256(key).hexdigest()[:8]}")


def _add_gene_args(p: argparse.ArgumentParser, *, for_encrypt: bool) -> None:
    p.add_argument("--badge-type", default="human", help=f"one of {sorted(BADGE_ALIASES)}")
    p.add_argument("--diploid-hex", help="18-byte diploid hex (reuse a saved peer)")
    p.add_argument("--gamete-hex", help="raw 16-byte padded gamete (skip meiosis)")
    p.add_argument("--rate", default="baseline", help=f"mutation rate: {sorted(MUTATION_ALIASES)}")
    p.add_argument("--seed", type=int, default=None, help="RNG seed for reproducible peer gene")
    p.add_argument("--no-mutate", action="store_true", help="meiosis only, skip mutate()")
    p.add_argument(
        "--zeros",
        action="store_true",
        help="legacy stub gamete (zeros + badge byte) instead of real meiosis",
    )
    if for_encrypt:
        p.add_argument("--png", type=Path, default=None)
        p.add_argument("--ecc", choices=("L", "M"), default="L")


def main() -> None:
    p = argparse.ArgumentParser(
        description="DC34 breed / peer simulator — gene model + AES-GCM-SIV"
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    n = sub.add_parser("nonce", help="Emit Bob nonce QR (no key needed)")
    n.add_argument("--nonce", default=None, help="12-byte hex; random if omitted")
    n.add_argument("--png", type=Path, default=None)
    n.add_argument("--ecc", choices=("L", "M"), default="L")
    n.set_defaults(func=cmd_nonce)

    d = sub.add_parser("decode", help="Decode gene or nonce base45/hex (no key)")
    d.add_argument("--gene-b45")
    d.add_argument("--gene-hex")
    d.set_defaults(func=cmd_decode)

    dip = sub.add_parser("diploid", help="Create synthetic peer diploid (no key)")
    dip.add_argument("--badge-type", default="human")
    dip.add_argument("--seed", type=int, default=None)
    dip.add_argument("--save", type=Path, default=None, help="write JSON capture")
    dip.set_defaults(func=cmd_diploid)

    g = sub.add_parser("gamete", help="Build padded gamete via meiosis+mutate (no key)")
    _add_gene_args(g, for_encrypt=False)
    g.set_defaults(func=cmd_gamete)

    peer = sub.add_parser(
        "peer",
        help="Full peer donor: diploid→gamete→gene QR (NEEDS --key-hex)",
    )
    peer.add_argument("--key-hex", required=True)
    peer.add_argument("--nonce-hex", required=True, help="Bob's 12-byte nonce (from badge ←/→)")
    _add_gene_args(peer, for_encrypt=True)
    peer.set_defaults(func=cmd_peer)

    r = sub.add_parser("respond", help="Donor: encrypt gamete → gene QR (NEEDS --key-hex)")
    r.add_argument("--key-hex", required=True)
    r.add_argument("--nonce-hex", required=True, help="Bob's 12-byte nonce")
    _add_gene_args(r, for_encrypt=True)
    r.set_defaults(func=cmd_respond)

    a = sub.add_parser("accept", help="Receiver: decrypt gene (NEEDS --key-hex)")
    a.add_argument("--key-hex", required=True)
    a.add_argument("--nonce-hex", required=True)
    a.add_argument("--gene-b45")
    a.add_argument("--gene-hex")
    a.set_defaults(func=cmd_accept)

    args = p.parse_args()
    if args.cmd == "accept" and not (args.gene_b45 or args.gene_hex):
        raise SystemExit("accept needs --gene-b45 or --gene-hex")
    args.func(args)


if __name__ == "__main__":
    main()
