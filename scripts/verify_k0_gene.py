#!/usr/bin/env python3
"""Offline AES-256-GCM-SIV checker for captured gene QR traffic.

Scheme (dc34-vault/defcon-scheme.md):
  K = Ko || Kp, 32 bytes. Day-1 target: Ko=12B (96b), Kp=20B (160b).
  Gene = AES-256-GCM-SIV(K, nonce, padded_gamete||badge_type) → CT(16)||tag(16).

Public starter (defcon.org/34b HTML comment, 2026-08-07):
  7ad8_4ed0_e00a_ec04_99ed_e656_15e1_da51  → 16 bytes (128 bits).
  That is only part of the envisioned 160-bit Day-1 Kp (32 bits of Kp still unpublished,
  unless the proclamation schedule has not fully dropped yet).

Usage:
  .venv/bin/python scripts/verify_k0_gene.py
  .venv/bin/python scripts/verify_k0_gene.py --capture captures/qr/pair_fake_nonce_2026-08-07.json
  .venv/bin/python scripts/verify_k0_gene.py --key-hex <64 hex chars>
  .venv/bin/python scripts/verify_k0_gene.py --layout ko_first__kp_prefix --brute-max 2

Requires: cryptography (AESGCMSIV).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from itertools import product
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCMSIV

# HTML comment on defcon.org/34b — 16-byte starter drop
DEFAULT_KP_PUBLIC = bytes.fromhex("7ad84ed0e00aec0499ede65615e1da51")
DEFAULT_CAPTURE = Path("captures/qr/pair_fake_nonce_2026-08-07.json")
EXPECTED_HASH_PREFIX = "dca9ea49"
# Hunt-era default pin for K[-2:] when only the 34b Kp prefix was public.
# Fits Ko(12)||Kp(20) if public Kp is a *prefix*; conflicts with kp_suffix layouts.
DEFAULT_K0_SUFFIX = bytes.fromhex("40b3")

# BadgeType values from dc34-api (byte 15 of padded gamete)
BADGE_TYPES = {
    0: "Uber",
    1: "Other",
    2: "Community",
    3: "Village",
    4: "CtfContest",
    5: "Human",
    6: "Goon",
    7: "None",
}


def k0_hash(k: bytes) -> str:
    return hashlib.sha256(k).hexdigest()[:8]


def load_capture(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    for key in ("nonce_hex", "gene_hex"):
        if key not in data:
            raise SystemExit(f"capture missing {key}: {path}")
    return data


def decrypt_gene(k: bytes, nonce: bytes, gene: bytes) -> bytes | None:
    try:
        return AESGCMSIV(k).decrypt(nonce, gene, None)
    except InvalidTag:
        return None


def describe_plaintext(pt: bytes) -> str:
    if len(pt) != 16:
        return f"unexpected plaintext len {len(pt)}"
    bt = BADGE_TYPES.get(pt[15], f"unknown({pt[15]})")
    return f"badge_type={bt} tail={pt[15]:#x} body={pt[:15].hex()}"


def unknown_count(slots: list[int | None]) -> int:
    return sum(1 for v in slots if v is None)


def build_key_templates(public: bytes) -> list[tuple[str, list[int | None], str]]:
    """Return (name, 32-slot key, note). None = unknown byte."""
    n = len(public)
    if n > 32:
        raise ValueError("public slice longer than 32 bytes")

    out: list[tuple[str, list[int | None], str]] = []

    def add(name: str, slots: list[int | None], note: str) -> None:
        if len(slots) != 32:
            raise ValueError(f"{name}: got {len(slots)} slots")
        out.append((name, slots, note))

    # Canonical scheme: Ko(12) || Kp(20); HTML bytes = prefix of Kp
    kp_known = min(n, 20)
    add(
        "ko_first__kp_prefix",
        [None] * 12 + list(public[:kp_known]) + [None] * (20 - kp_known),
        f"Scheme default. Ko unknown (96b) + Kp tail unknown ({(20 - kp_known) * 8}b).",
    )

    # Ko(12) || Kp(20); HTML bytes = suffix of Kp
    if n <= 20:
        add(
            "ko_first__kp_suffix",
            [None] * 12 + [None] * (20 - n) + list(public),
            "Public at end of Kp (unlikely).",
        )

    # Kp(20) || Ko(12); HTML = prefix of Kp
    add(
        "kp_first__kp_prefix",
        list(public[:kp_known]) + [None] * (20 - kp_known) + [None] * 12,
        "Swapped order hypothesis.",
    )

    # HTML is first n bytes of full K (Ko leak / mistimed drop)
    add(
        "public_at_k0",
        list(public) + [None] * (32 - n),
        "Public is K[0:n] (includes all of Ko if n>=12).",
    )

    # HTML is K[16:16+n] (second half)
    if n <= 16:
        add(
            "public_at_k16",
            [None] * 16 + list(public) + [None] * (16 - n),
            "Public is K[16:32].",
        )

    # HTML first 12 = Ko, remaining 4 start Kp (partial Day-1 drop shaped as Ko||Kpstart)
    if n >= 12:
        rest = public[12:]
        add(
            "html_ko12_then_kp",
            list(public[:12]) + list(rest) + [None] * (20 - len(rest)),
            "Treat HTML as Ko(12)||Kp_prefix; rest of Kp unknown.",
        )

    return out


def materialize(slots: list[int | None], fill: dict[int, int] | None = None) -> bytes | None:
    fill = fill or {}
    out = bytearray(32)
    for i, v in enumerate(slots):
        if v is not None:
            out[i] = v
        elif i in fill:
            out[i] = fill[i]
        else:
            return None
    return bytes(out)


def try_templates(
    templates: list[tuple[str, list[int | None], str]],
    nonce: bytes,
    gene: bytes,
    *,
    expect_hash: str | None,
) -> list[dict]:
    hits: list[dict] = []
    for name, slots, _note in templates:
        k = materialize(slots)
        if k is None:
            continue
        pt = decrypt_gene(k, nonce, gene)
        if pt is None:
            continue
        h = k0_hash(k)
        hits.append(
            {
                "layout": name,
                "key_hex": k.hex(),
                "hash": h,
                "hash_match": h == expect_hash if expect_hash else None,
                "plaintext_hex": pt.hex(),
                "plaintext_note": describe_plaintext(pt),
            }
        )
    return hits


def brute_unknown(
    slots: list[int | None],
    nonce: bytes,
    gene: bytes,
    *,
    max_bytes: int,
    expect_hash: str | None,
) -> list[dict]:
    unknown_idx = [i for i, v in enumerate(slots) if v is None]
    if not unknown_idx:
        return []
    if len(unknown_idx) > max_bytes:
        print(
            f"skip brute: {len(unknown_idx)} unknown bytes > --brute-max {max_bytes}",
            file=sys.stderr,
        )
        return []

    hits: list[dict] = []
    total = 256 ** len(unknown_idx)
    print(f"brute {len(unknown_idx)} byte(s) => {total:,} keys...", file=sys.stderr)
    checked = 0
    for tup in product(range(256), repeat=len(unknown_idx)):
        fill = dict(zip(unknown_idx, tup))
        k = materialize(slots, fill)
        assert k is not None
        checked += 1
        if expect_hash and k0_hash(k) != expect_hash:
            continue
        pt = decrypt_gene(k, nonce, gene)
        if pt is None:
            continue
        hits.append(
            {
                "layout": "brute",
                "key_hex": k.hex(),
                "hash": k0_hash(k),
                "hash_match": True,
                "plaintext_hex": pt.hex(),
                "plaintext_note": describe_plaintext(pt),
                "checked": checked,
            }
        )
        break
    return hits


def print_layout_report(
    templates: list[tuple[str, list[int | None], str]],
    public: bytes,
) -> None:
    print("Layout unknown-bit report (Day-1 scheme wants Ko=96b unknown if Kp fully public):")
    print(f"  HTML public bytes: {len(public)} ({len(public) * 8} bits)")
    print(f"  Scheme Day-1 Kp target: 20 bytes (160 bits) — shortfall vs HTML: {max(0, 20 - len(public))} bytes")
    print()
    for name, slots, note in templates:
        u = unknown_count(slots)
        bits = u * 8
        # Meditations hash prefix is 32 bits — rough remaining after filter
        after_hash = max(0, bits - 32)
        print(f"  {name}: {u} unknown bytes ({bits} bits)")
        print(f"      {note}")
        print(f"      after 32-bit hash filter ≈ 2^{after_hash} candidates (still huge if >40)")
    print()


def main() -> None:
    p = argparse.ArgumentParser(description="Verify captured gene QR against candidate k0")
    p.add_argument("--capture", type=Path, default=DEFAULT_CAPTURE)
    p.add_argument(
        "--kp-public",
        default=DEFAULT_KP_PUBLIC.hex(),
        help="Known public bytes (hex; underscores ok). Default = 34b HTML starter.",
    )
    p.add_argument("--key-hex", help="Test a full 32-byte candidate key (hex)")
    p.add_argument("--expect-hash", default=EXPECTED_HASH_PREFIX, help="Meditations hash prefix")
    p.add_argument("--layout", help="Only try one template name")
    p.add_argument("--brute-layout", default="ko_first__kp_prefix", help="Template to brute-fill")
    p.add_argument(
        "--last-byte",
        default="40b3",
        help="Pin K suffix hex (1–2 bytes). Default 40b3 (hunt-era hint). "
        "Empty / 'none' to leave unknown.",
    )
    p.add_argument("--brute-max", type=int, default=0, help="Max unknown bytes to exhaust (0=skip)")
    p.add_argument("--no-report", action="store_true", help="Skip layout bit report")
    args = p.parse_args()

    cap = load_capture(args.capture)
    nonce = bytes.fromhex(cap["nonce_hex"])
    gene = bytes.fromhex(cap["gene_hex"])
    kp_public = bytes.fromhex(args.kp_public.replace("_", ""))

    print(f"capture: {args.capture}")
    print(f"nonce:   {nonce.hex()}")
    print(f"gene:    {gene.hex()} ({len(gene)} bytes CT||tag)")
    print(f"public:  {kp_public.hex()} ({len(kp_public)} bytes)  [34b HTML default]")
    print(f"expect hash prefix: {args.expect_hash}")
    print()

    if args.key_hex:
        k = bytes.fromhex(args.key_hex.replace("_", ""))
        if len(k) != 32:
            raise SystemExit("key must be 32 bytes")
        pt = decrypt_gene(k, nonce, gene)
        h = k0_hash(k)
        print(f"key hash: {h} ({'MATCH' if h == args.expect_hash else 'no match'})")
        if pt is None:
            print("decrypt: FAIL (bad tag)")
            raise SystemExit(1)
        print(f"decrypt: OK — {describe_plaintext(pt)}")
        print(f"plaintext: {pt.hex()}")
        return

    templates = build_key_templates(kp_public)
    last_raw = (args.last_byte or "").strip().lower().replace("0x", "").replace("_", "")
    suffix: bytes | None = None
    if last_raw and last_raw not in {"none", "-", "off"}:
        if len(last_raw) not in (2, 4) or any(c not in "0123456789abcdef" for c in last_raw):
            raise SystemExit("--last-byte must be 1 or 2 hex bytes (e.g. b3 or 40b3)")
        suffix = bytes.fromhex(last_raw)
        pinned: list[tuple[str, list[int | None], str]] = []
        for name, slots, note in templates:
            s = list(slots)
            conflict = False
            for i, b in enumerate(suffix):
                idx = 32 - len(suffix) + i
                if s[idx] is None:
                    s[idx] = b
                elif s[idx] != b:
                    conflict = True
            if conflict:
                note = f"{note} CONFLICT suffix {suffix.hex()} vs layout."
            else:
                note = f"{note} K[-{len(suffix)}:]={suffix.hex()} (pinned)."
            pinned.append((name, s, note))
        templates = pinned
        print(f"pin K[-{len(suffix)}:]={suffix.hex()}")
    if args.layout:
        templates = [(n, s, note) for n, s, note in templates if n == args.layout]
        if not templates:
            names = ", ".join(n for n, _, _ in build_key_templates(kp_public))
            raise SystemExit(f"unknown layout {args.layout!r}; choose from: {names}")

    if not args.no_report:
        print_layout_report(templates, kp_public)

    print("Trying fixed layouts (public bytes only, unknowns left unset → skip incomplete)...")
    # Only fully-specified templates can decrypt without brute
    complete = [(n, s, note) for n, s, note in templates if unknown_count(s) == 0]
    if not complete:
        print("  (no layout is fully determined by public bytes alone)")
    hits = try_templates(templates, nonce, gene, expect_hash=args.expect_hash)
    if hits:
        for hit in hits:
            print(f"  HIT {hit['layout']} hash={hit['hash']} {hit['plaintext_note']}")
            print(f"       key={hit['key_hex']}")
    else:
        print("  no decrypt with public bytes alone (expected until more Kp drops or Ko found).")

    primary = next((s for n, s, _ in templates if n == args.brute_layout), None)
    if primary is None and templates:
        primary = templates[0][1]
        args.brute_layout = templates[0][0]
    if primary is None:
        return

    if args.brute_max <= 0:
        u = unknown_count(primary)
        print(f"\nBrute skipped (--brute-max {args.brute_max}). {args.brute_layout}: {u} unknown bytes.")
        print("Next: more Kp from 34b / proclamations, or --brute-max N when unknowns ≤3–4.")
        return

    brute_hits = brute_unknown(
        primary, nonce, gene, max_bytes=args.brute_max, expect_hash=args.expect_hash
    )
    if brute_hits:
        print("\nBrute hits:")
        for hit in brute_hits:
            print(f"  {hit}")
    else:
        unknown = unknown_count(primary)
        print(f"\nNo brute hit on {args.brute_layout} ({unknown} unknown bytes remain).")


if __name__ == "__main__":
    main()
