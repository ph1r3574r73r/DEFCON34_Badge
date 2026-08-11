#!/usr/bin/env python3
"""Offline AesKwp unwrap of PDDB SCD using HKDF master from dump_qr.json.

Does not talk to the badge. SCD dump is 8 KB (lite @0 + full @4096) from asid_scd.
Writes system PT/data keys to captures/hop132/pddb_syskeys.json (do not commit).
k0 still needs page-table + data pages after this.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[0]))
sys.path.insert(0, str(HERE))

from constants import (
    K0_HASH_PREFIX,
    SCD_PAGE,
    SCD_VERSION,
    WRAPPED_AES_KEYSIZE,
)
from derive import derive

try:
    from cryptography.hazmat.primitives.keywrap import (
        aes_key_unwrap,
        aes_key_unwrap_with_padding,
    )
except ImportError:
    aes_key_unwrap = None  # type: ignore
    aes_key_unwrap_with_padding = None  # type: ignore

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_KEYS = ROOT / "captures" / "hop132" / "dump_qr.json"
DEFAULT_SCD = ROOT / "captures" / "hop132" / "dump_scd.json"
DEFAULT_OUT = ROOT / "captures" / "hop132" / "pddb_syskeys.json"


def _master_from_dump(doc: dict) -> bytes:
    # Re-run HKDF; do not persist master unless --emit-master.
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF

    from constants import SLOT_CHAFF, SLOT_NUISANCE0, SLOT_NUISANCE1

    def hx(name: str, n: int) -> bytes:
        b = bytes.fromhex(doc[name].replace("_", "").replace(" ", ""))
        if len(b) != n:
            raise SystemExit(f"{name}: expected {n}B, got {len(b)}")
        return b

    root = hx("root_seed", 32)
    n0 = hx("nuisance0", len(SLOT_NUISANCE0) * 32)
    chaff = hx("chaff", len(SLOT_CHAFF) * 32)
    n1 = hx("nuisance1", len(SLOT_NUISANCE1) * 32)
    uuid = hx("uuid", 32)
    cpid = hx("cp_id", 32)
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
    salt = uuid + cpid
    info = bytearray()
    info.extend(b"dev" if int(doc.get("developer_mode", 0)) else b"sec")
    if int(doc.get("oem_mode", 0)):
        info.extend(b"oem")
    if int(doc.get("boot0_pubkey_fail", 0)):
        info.extend(b"tampered")
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=salt, info=bytes(info)).derive(bytes(ikm))


def parse_scd(page: bytes) -> dict | None:
    if len(page) < 4 + 2 * WRAPPED_AES_KEYSIZE:
        return None
    ver = struct.unpack_from("<I", page, 0)[0]
    pt = page[4 : 4 + WRAPPED_AES_KEYSIZE]
    data = page[4 + WRAPPED_AES_KEYSIZE : 4 + 2 * WRAPPED_AES_KEYSIZE]
    return {"version": ver, "system_key_pt": pt, "system_key": data}


def try_unwrap(master: bytes, wrapped: bytes) -> tuple[str, bytes] | None:
    if aes_key_unwrap is None:
        raise SystemExit("pip install cryptography")
    for name, fn in (
        ("kwp", aes_key_unwrap_with_padding),
        ("kw", aes_key_unwrap),
    ):
        try:
            pt = fn(master, wrapped)
        except Exception:
            continue
        if len(pt) == 32:
            return name, pt
    return None


def unwrap_dump(scd_blob: bytes, master: bytes) -> dict:
    hits = []
    for label, off, spi in (
        ("lite", 0, 0x403000),
        ("full", SCD_PAGE, 0x404000),
    ):
        if off + SCD_PAGE > len(scd_blob):
            continue
        page = scd_blob[off : off + SCD_PAGE]
        parsed = parse_scd(page)
        if parsed is None:
            continue
        rec = {
            "label": label,
            "spi": hex(spi),
            "version": parsed["version"],
            "version_ok": parsed["version"] == SCD_VERSION,
            "pt_unwrap": None,
            "data_unwrap": None,
            "system_key_pt_sha256": None,
            "system_key_sha256": None,
        }
        if parsed["version"] not in (SCD_VERSION,):
            # still try unwrap; blank flash is 0 / 0xFFFFFFFF
            rec["note"] = "unexpected SCD version"
        pt_u = try_unwrap(master, parsed["system_key_pt"])
        dat_u = try_unwrap(master, parsed["system_key"])
        if pt_u:
            rec["pt_unwrap"] = pt_u[0]
            rec["system_key_pt"] = pt_u[1].hex()
            rec["system_key_pt_sha256"] = hashlib.sha256(pt_u[1]).hexdigest()
        if dat_u:
            rec["data_unwrap"] = dat_u[0]
            rec["system_key"] = dat_u[1].hex()
            rec["system_key_sha256"] = hashlib.sha256(dat_u[1]).hexdigest()
        hits.append(rec)
    ok = [h for h in hits if h.get("system_key") and h.get("system_key_pt")]
    return {
        "scd_len": len(scd_blob),
        "master_sha256": hashlib.sha256(master).hexdigest(),
        "candidates": hits,
        "ok": bool(ok),
        "note": (
            "AesKwp unwrap of PDDB system keys. Next: dump page table + dc34/k0 pages. "
            f"Meditations prefix still {K0_HASH_PREFIX}."
        ),
    }


def selftest() -> None:
    from cryptography.hazmat.primitives.keywrap import (
        aes_key_wrap,
        aes_key_wrap_with_padding,
    )

    kek = bytes(range(32))
    key = bytes(range(32, 64))
    w = aes_key_wrap_with_padding(kek, key)
    u = aes_key_unwrap_with_padding(kek, w)
    assert u == key, u.hex()
    w2 = aes_key_wrap(kek, key)
    assert len(w2) == 40
    assert aes_key_unwrap(kek, w2) == key
    page = bytearray(SCD_PAGE)
    struct.pack_into("<I", page, 0, SCD_VERSION)
    page[4 : 4 + 40] = w
    page[44 : 44 + 40] = w2
    out = unwrap_dump(bytes(page) + bytes(SCD_PAGE), kek)
    assert out["candidates"][0]["pt_unwrap"] == "kwp"
    assert out["candidates"][0]["data_unwrap"] == "kw"
    print("unwrap selftest OK")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--keys", type=Path, default=DEFAULT_KEYS, help="dump_qr.json (HKDF inputs)")
    ap.add_argument("--scd", type=Path, default=DEFAULT_SCD, help="dump_scd.json or raw .bin")
    ap.add_argument("-o", "--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()
    if args.selftest:
        selftest()
        return 0
    if aes_key_unwrap is None:
        raise SystemExit("pip install cryptography")
    keys_doc = json.loads(args.keys.read_text())
    master = _master_from_dump(keys_doc)
    derived = derive(keys_doc)
    if derived["master_sha256"] != hashlib.sha256(master).hexdigest():
        raise SystemExit("master mismatch vs derive.py")
    raw = args.scd.read_bytes()
    if args.scd.suffix.lower() == ".json":
        doc = json.loads(raw)
        blob = bytes.fromhex(doc["dump"])
    else:
        blob = raw
    out = unwrap_dump(blob, master)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps({k: out[k] for k in ("scd_len", "master_sha256", "ok", "note")}, indent=2))
    for c in out["candidates"]:
        print(
            f"  {c['label']} ver={c['version']} pt={c['pt_unwrap']} data={c['data_unwrap']} "
            f"pt_sha={(c['system_key_pt_sha256'] or '')[:16]}…"
        )
    print(f"wrote {args.out}")
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
