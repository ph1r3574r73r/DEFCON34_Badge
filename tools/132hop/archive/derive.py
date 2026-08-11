#!/usr/bin/env python3
"""Offline HKDF → PDDB master from a dumped key-material JSON.

Dump format (hex strings, no 0x):
  root_seed, nuisance0 (120×32B), chaff (128×32B), nuisance1 (128×32B),
  uuid, cp_id, developer_mode, oem_mode, boot0_pubkey_fail (ints 0/1)
  optional: flag1 (32B) — checked against published SHA-256
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from constants import (
    K0_HASH_PREFIX,
    KP_PUBLIC,
    SHA256_FLAG1,
    SHA256_PDDB_MASTER,
    SLOT_CHAFF,
    SLOT_NUISANCE0,
    SLOT_NUISANCE1,
)

try:
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF
    from cryptography.hazmat.primitives import hashes
except ImportError:
    HKDF = None  # type: ignore


def _hex(name: str, blob: str, n: int) -> bytes:
    b = bytes.fromhex(blob.replace("_", "").replace(" ", ""))
    if len(b) != n:
        raise SystemExit(f"{name}: expected {n} bytes, got {len(b)}")
    return b


def derive(doc: dict) -> dict:
    root = _hex("root_seed", doc["root_seed"], 32)
    n0 = _hex("nuisance0", doc["nuisance0"], len(SLOT_NUISANCE0) * 32)
    chaff = _hex("chaff", doc["chaff"], len(SLOT_CHAFF) * 32)
    n1 = _hex("nuisance1", doc["nuisance1"], len(SLOT_NUISANCE1) * 32)
    uuid = _hex("uuid", doc["uuid"], 32)
    cpid = _hex("cp_id", doc["cp_id"], 32)

    ikm = bytearray()
    ikm.extend(root)
    ikm.extend(n0)
    ikm.extend(n1)
    acc = bytearray(32)
    for i in range(0, len(chaff), 32):
        chunk = chaff[i : i + 32]
        for j in range(32):
            acc[j] ^= chunk[j]
    ikm.extend(acc)
    expect_len = (len(SLOT_NUISANCE0) + len(SLOT_NUISANCE1) + 1 + 1) * 32
    if len(ikm) != expect_len:
        raise SystemExit(f"ikm len {len(ikm)} != {expect_len}")

    salt = uuid + cpid
    info = bytearray()
    info.extend(b"dev" if int(doc.get("developer_mode", 0)) else b"sec")
    if int(doc.get("oem_mode", 0)):
        info.extend(b"oem")
    if int(doc.get("boot0_pubkey_fail", 0)):
        info.extend(b"tampered")

    if HKDF is None:
        raise SystemExit("pip install cryptography")
    master = HKDF(algorithm=hashes.SHA256(), length=32, salt=salt, info=bytes(info)).derive(bytes(ikm))
    out = {
        "master_sha256": hashlib.sha256(master).hexdigest(),
        "master_match_published": hashlib.sha256(master).hexdigest() == SHA256_PDDB_MASTER,
        "info": info.decode(),
        "ikm_len": len(ikm),
    }
    if "flag1" in doc:
        flag1 = _hex("flag1", doc["flag1"], 32)
        out["flag1_sha256"] = hashlib.sha256(flag1).hexdigest()
        out["flag1_match_published"] = out["flag1_sha256"] == SHA256_FLAG1
    out["note"] = (
        "master unlocks PDDB via AesKwp; k0 is dc34/k0 inside PDDB, not this digest. "
        f"Meditations prefix still {K0_HASH_PREFIX}; public Kp fragment {KP_PUBLIC.hex()}."
    )
    return out


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("dump", type=Path, help="JSON dump of key material")
    args = p.parse_args()
    doc = json.loads(args.dump.read_text())
    out = derive(doc)
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
