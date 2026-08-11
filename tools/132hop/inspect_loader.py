#!/usr/bin/env python3
"""Assert stock loader header matches the 132-byte hop preconditions."""

from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from constants import (
    AAD_LEN_FIDO2,
    AAD_TAIL_OFF,
    DEFAULT_LOADER,
    HOP_JAL,
    KERNEL_START,
    LOADER_START,
    SPRING_OFF,
    STAGE2_ADDR,
    STOCK_JAL,
    UNSIGNED_LEN,
)
from uf2util import load_loader


def inspect(path: Path) -> dict:
    img, base, meta = load_loader(path)
    if base != LOADER_START:
        raise SystemExit(f"loader base {base:#x} != {LOADER_START:#x}")
    jal = struct.unpack_from("<I", img, 0)[0]
    aad_len = struct.unpack_from("<I", img, 0x44)[0]
    tail = img[AAD_TAIL_OFF:UNSIGNED_LEN]
    ver, mag0, mag1, signed_len, fn = struct.unpack_from("<5I", img, UNSIGNED_LEN)
    body_end = base + UNSIGNED_LEN + signed_len
    return {
        "path": str(path),
        "family": hex(meta["family"]),
        "nblocks": meta["nblocks"],
        "decoded_len": meta["decoded_len"],
        "jal": hex(jal),
        "jal_ok": jal == STOCK_JAL,
        "aad_len": aad_len,
        "aad_len_ok": aad_len == AAD_LEN_FIDO2,
        "tail_hex": tail.hex(),
        "tail_zero": all(b == 0 for b in tail),
        "signed_len": signed_len,
        "function": hex(fn),
        "body_end": hex(body_end),
        "stage2": hex(STAGE2_ADDR),
        "kernel": hex(KERNEL_START),
        "gap_ok": body_end <= STAGE2_ADDR < KERNEL_START,
        "hop_jal": hex(HOP_JAL),
        "spring_off": hex(LOADER_START + SPRING_OFF),
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("loader", nargs="?", type=Path, default=Path(DEFAULT_LOADER))
    args = p.parse_args()
    info = inspect(args.loader)
    for k, v in info.items():
        print(f"{k:16} {v}")
    bad = [k for k in ("jal_ok", "aad_len_ok", "tail_zero", "gap_ok") if not info[k]]
    if bad:
        raise SystemExit(f"ASSERT FAIL: {', '.join(bad)}")
    print("OK — header matches hop preconditions")


if __name__ == "__main__":
    main()
