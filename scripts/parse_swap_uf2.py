#!/usr/bin/env python3
"""Offline parse of a Baochip swap.uf2: unsigned header + zero-key AEAD trial.

Sealed-safe. Does not talk to the badge. Matches loader/src/platform/bao1x/swap.rs
and tools/src/swap_writer.rs @ ship + tip.
"""
from __future__ import annotations

import argparse
import json
import struct
import sys
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCMSIV

UF2_MAGIC0 = 0x0A324655
UF2_MAGIC1 = 0x9E5D5157
UF2_MAGIC_END = 0x0AB16F30
PAGE = 4096
SIGBLOCK_LEN = 768
UNSIGNED_LEN = 4 + 64 + 4 + 60  # jal + sig + aad_len + aad
SWAP_HEADER_LEN = PAGE
UNSIGNED_HEADER_LEN = SWAP_HEADER_LEN - SIGBLOCK_LEN  # 3328
ZERO_KEY = b"\x00" * 32


def uf2_to_bin(data: bytes) -> tuple[bytes, dict]:
    if len(data) % 512:
        raise ValueError(f"UF2 length {len(data)} not multiple of 512")
    nblocks = len(data) // 512
    chunks: dict[int, bytes] = {}
    family = None
    addrs = []
    for i in range(nblocks):
        blk = data[i * 512 : (i + 1) * 512]
        m0, m1, flags, addr, payload_size, blockno, total, fam = struct.unpack_from("<8I", blk, 0)
        mend = struct.unpack_from("<I", blk, 512 - 4)[0]
        if m0 != UF2_MAGIC0 or m1 != UF2_MAGIC1 or mend != UF2_MAGIC_END:
            raise ValueError(f"bad UF2 magic at block {i}")
        if payload_size != 256:
            raise ValueError(f"unexpected payload size {payload_size} at block {i}")
        if family is None:
            family = fam
        elif fam != family:
            raise ValueError(f"family mismatch at block {i}: {fam:#x} vs {family:#x}")
        rel = addr - (addrs[0] if addrs else addr)
        if not addrs:
            base = addr
        else:
            rel = addr - base
        if not addrs:
            base = addr
        rel = addr - base
        chunks[rel] = blk[32 : 32 + 256]
        addrs.append(addr)
    if not chunks:
        raise ValueError("empty UF2")
    base = min(addrs)
    max_off = max(chunks) + 256
    out = bytearray(max_off)
    for off, chunk in chunks.items():
        out[off : off + 256] = chunk
    meta = {
        "nblocks": nblocks,
        "family": f"{family:#010x}" if family is not None else None,
        "base_addr": f"{base:#010x}",
        "decoded_len": len(out),
    }
    return bytes(out), meta


def parse_swap_source_header(page0: bytes) -> dict:
    version, nonce, mac_offset, aad_len = struct.unpack_from("<I8sII", page0, 0)
    aad = page0[20 : 20 + 64]
    if aad_len > 64:
        raise ValueError(f"aad_len {aad_len} > 64")
    return {
        "version": f"{version:#010x}",
        "version_u32": version,
        "partial_nonce_hex": nonce.hex(),
        "partial_nonce_u64_be": int.from_bytes(nonce, "big"),
        "mac_offset": mac_offset,
        "aad_len": aad_len,
        "aad_hex": aad[:aad_len].hex(),
        "aad_ascii": aad[:aad_len].decode("ascii", "replace"),
    }


def parse_sigblock(sig: bytes) -> dict:
    jal = struct.unpack_from("<I", sig, 0)[0]
    signature = sig[4:68]
    aad_len = struct.unpack_from("<I", sig, 68)[0]
    aad = sig[72:132]
    sealed = sig[UNSIGNED_LEN:]
    version, magic0, magic1, signed_len, function_code, anti_rollback = struct.unpack_from(
        "<6I", sealed, 0
    )
    # SealedFields: version u32, magic [u32;2], signed_len, function_code, anti_rollback,
    # min_semver[16], semver[16], pubkeys[4]*(32+4), toolchain[20]
    return {
        "jal": f"{jal:#010x}",
        "signature_hex": signature.hex(),
        "sig_aad_len": aad_len,
        "sig_aad_hex": aad[: min(aad_len, 60)].hex() if aad_len else "",
        "sealed_version": f"{version:#x}",
        "magic": bytes(struct.pack("<II", magic0, magic1)),
        "magic_ascii": bytes(struct.pack("<II", magic0, magic1)).decode("ascii", "replace"),
        "signed_len": signed_len,
        "function_code": f"{function_code:#x}",
        "anti_rollback": anti_rollback,
    }


def try_decrypt_page0(blob: bytes, ssh: dict) -> dict:
    mac_offset = ssh["mac_offset"]
    image_start = PAGE  # encrypted region after header page
    mac_start = image_start + mac_offset
    if mac_start + 16 > len(blob):
        return {"ok": False, "error": f"mac_start {mac_start} past blob {len(blob)}"}
    page = bytearray(blob[image_start : image_start + PAGE])
    tag = blob[mac_start : mac_start + 16]
    offset = 0
    nonce = offset.to_bytes(4, "big") + bytes.fromhex(ssh["partial_nonce_hex"])
    aad = bytes.fromhex(ssh["aad_hex"])
    try:
        # AESGCMSIV.decrypt(nonce, data+tag, aad)
        pt = AESGCMSIV(ZERO_KEY).decrypt(nonce, bytes(page) + tag, aad)
    except Exception as e:
        return {
            "ok": False,
            "error": f"{type(e).__name__}: {e}",
            "nonce_hex": nonce.hex(),
            "tag_hex": tag.hex(),
            "ct_head_hex": bytes(page[:32]).hex(),
        }
    return {
        "ok": True,
        "nonce_hex": nonce.hex(),
        "tag_hex": tag.hex(),
        "pt_len": len(pt),
        "pt_head_hex": pt[:64].hex(),
        "pt_head_ascii": "".join(chr(b) if 32 <= b < 127 else "." for b in pt[:64]),
        "looks_like_elf": pt[:4] == b"\x7fELF",
        "looks_like_xous_minielf": pt[:4] == b"XouS" or pt[0:2] == b"\x7fE",
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("uf2", type=Path)
    ap.add_argument("-o", "--out-json", type=Path, default=None)
    args = ap.parse_args()
    raw = args.uf2.read_bytes()
    blob, uf2_meta = uf2_to_bin(raw)
    if len(blob) < PAGE + 16:
        print("decoded image too short", file=sys.stderr)
        return 1
    ssh = parse_swap_source_header(blob[:PAGE])
    sig_off = UNSIGNED_HEADER_LEN
    sig = parse_sigblock(blob[sig_off : sig_off + SIGBLOCK_LEN])
    dec = try_decrypt_page0(blob, ssh)
    report = {
        "file": str(args.uf2),
        "file_size": len(raw),
        "uf2": uf2_meta,
        "unsigned_header": ssh,
        "sigblock_at": sig_off,
        "sigblock": {
            **sig,
            "magic_ascii": sig["magic_ascii"],
            "magic_hex": sig["magic"].hex(),
        },
        "zero_key_page0": dec,
        "notes": [
            "This is the *update* zip swap unless you passed a ship artifact.",
            "Unsigned SwapSourceHeader is first 3328 bytes; sigblock at 3328; AEAD pages at 4096.",
            "Zero-key decrypt matches loader trial with swap.key == [0;32].",
        ],
    }
    # don't dump raw magic bytes in json
    report["sigblock"].pop("magic", None)
    text = json.dumps(report, indent=2)
    print(text)
    if args.out_json:
        args.out_json.parent.mkdir(parents=True, exist_ok=True)
        args.out_json.write_text(text + "\n")
        print(f"WROTE {args.out_json}", file=sys.stderr)
    return 0 if dec.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
