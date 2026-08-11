#!/usr/bin/env python3
"""Build unsigned-header hop UF2. Offline only — does not talk to the badge."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from asm import assemble, enc_j, enc_u
from constants import (
    DEFAULT_LOADER,
    HOP_JAL,
    LOADER_START,
    SPRING_OFF,
    SPRINGBOARD,
    STAGE2_ADDR,
    STOCK_JAL,
)
from inspect_loader import inspect
from payload import ARCHIVE_VARIANTS, FRONT_DOOR, build_stage2
from uf2util import encode_writes

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = Path(__file__).resolve().parent / "out"


def selftest(*, include_archive: bool = False) -> None:
    assert enc_j(0x70, 0, 0x6F) == HOP_JAL, hex(enc_j(0x70, 0, 0x6F))
    assert enc_j(0x300, 0, 0x6F) == STOCK_JAL, hex(enc_j(0x300, 0, 0x6F))
    lui = enc_u(0x6008C, 5, 0x37)
    jalr = 0x00028067
    got = lui.to_bytes(4, "little") + jalr.to_bytes(4, "little") + bytes(12)
    assert got == SPRINGBOARD, got.hex()
    spin = assemble("spin:\n    j spin\n", base=STAGE2_ADDR)
    assert len(spin) == 4
    qr = build_stage2("asid_qr")
    assert 512 < len(qr) < 0x13D00, len(qr)
    msg = f"selftest OK (asid_qr={len(qr)}B"
    if include_archive:
        sizes = {}
        for name in ARCHIVE_VARIANTS:
            blob = build_stage2(name)
            assert 512 < len(blob) < 0x13D00, (name, len(blob))
            sizes[name] = len(blob)
        msg += " " + " ".join(f"{k}={v}B" for k, v in sizes.items())
    print(msg + ")")


def build(variant: str, loader: Path, out_dir: Path) -> dict:
    info = inspect(loader)
    stage2 = build_stage2(variant)
    writes = [
        (LOADER_START, struct.pack("<I", HOP_JAL)),
        (LOADER_START + SPRING_OFF, SPRINGBOARD),
        (STAGE2_ADDR, stage2),
    ]
    uf2 = encode_writes(writes)
    out_dir.mkdir(parents=True, exist_ok=True)
    uf2_path = out_dir / f"hop_{variant}.uf2"
    uf2_path.write_bytes(uf2)
    meta = {
        "variant": variant,
        "loader": str(loader),
        "loader_asserts": {k: info[k] for k in ("jal", "aad_len", "tail_zero", "body_end", "gap_ok")},
        "stage2_bytes": len(stage2),
        "uf2_blocks": len(uf2) // 512,
        "uf2_sha256": hashlib.sha256(uf2).hexdigest(),
        "writes": [{"addr": hex(a), "len": len(b)} for a, b in writes],
        "uf2_path": str(uf2_path.relative_to(ROOT) if uf2_path.is_relative_to(ROOT) else uf2_path),
        "restore": "Update mode → copy stock loader.uf2 → commit. Do not use this hop UF2 until operator go.",
    }
    (out_dir / f"hop_{variant}.json").write_text(json.dumps(meta, indent=2) + "\n")
    return meta


def main() -> None:
    all_names = (*FRONT_DOOR, *ARCHIVE_VARIANTS)
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--selftest", action="store_true")
    p.add_argument("--variant", choices=sorted(all_names), default="handback")
    p.add_argument("--loader", type=Path, default=ROOT / DEFAULT_LOADER)
    p.add_argument("--out", type=Path, default=OUT_DIR)
    p.add_argument("--all", action="store_true", help="build front-door variants (spin/handback/hold/qr)")
    p.add_argument(
        "--all-archive",
        action="store_true",
        help="also build hex/SCD archive variants (oled/pages/scd)",
    )
    args = p.parse_args()
    if args.selftest:
        selftest(include_archive=args.all_archive)
        if not args.all and not args.all_archive and args.variant == "handback" and "--variant" not in sys.argv:
            return
    if args.all_archive:
        variants = list(all_names)
    elif args.all:
        variants = list(FRONT_DOOR)
    else:
        variants = [args.variant]
    for v in variants:
        meta = build(v, args.loader, args.out)
        print(f"{v:12} {meta['uf2_blocks']:3} blk  stage2={meta['stage2_bytes']:4}B  {meta['uf2_path']}")
        print(f"{'':12} sha256 {meta['uf2_sha256'][:16]}…")
    print("\nNO LIVE WRITE. Restore image is stock loader.uf2 in Update mode.")


if __name__ == "__main__":
    main()
