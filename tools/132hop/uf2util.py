"""UF2 encode/decode for Baochip-1x (256-byte payloads, family 0xa7d76373)."""

from __future__ import annotations

import struct
from pathlib import Path

from constants import BAOCHIP_1X_UF2_FAMILY

UF2_MAGIC0 = 0x0A324655
UF2_MAGIC1 = 0x9E5D5157
UF2_MAGIC_END = 0x0AB16F30
UF2_FLAG_FAMILY = 0x00002000
BLOCK = 512
PAYLOAD_MAX = 476
DEFAULT_PAYLOAD = 256


def decode(data: bytes) -> tuple[bytes, int, dict]:
    if len(data) % BLOCK:
        raise ValueError(f"UF2 length {len(data)} not multiple of {BLOCK}")
    chunks: dict[int, bytes] = {}
    family = None
    payload_sizes: set[int] = set()
    for i in range(len(data) // BLOCK):
        blk = data[i * BLOCK : (i + 1) * BLOCK]
        m0, m1, flags, addr, psize, _bno, _total, fam = struct.unpack_from("<8I", blk, 0)
        mend = struct.unpack_from("<I", blk, BLOCK - 4)[0]
        if m0 != UF2_MAGIC0 or m1 != UF2_MAGIC1 or mend != UF2_MAGIC_END:
            raise ValueError(f"bad UF2 magic at block {i}")
        if psize > PAYLOAD_MAX:
            raise ValueError(f"payload_size {psize} too large at block {i}")
        family = fam if family is None else family
        payload_sizes.add(psize)
        chunks[addr] = blk[32 : 32 + psize]
    if not chunks:
        raise ValueError("empty UF2")
    base = min(chunks)
    end = max(a + len(d) for a, d in chunks.items())
    out = bytearray(end - base)
    for addr, blob in chunks.items():
        off = addr - base
        out[off : off + len(blob)] = blob
    meta = {
        "nblocks": len(chunks),
        "family": family,
        "base": base,
        "decoded_len": len(out),
        "payload_sizes": sorted(payload_sizes),
    }
    return bytes(out), base, meta


def encode_writes(
    writes: list[tuple[int, bytes]],
    *,
    family: int = BAOCHIP_1X_UF2_FAMILY,
    payload: int = DEFAULT_PAYLOAD,
) -> bytes:
    """Emit UF2 blocks for (address, data) patches.

    Short patches keep their true payload_size so RRAM 32B RMW preserves neighbors
    (signature after jal, authenticated AAD before springboard).
    """
    records: list[tuple[int, bytes]] = []
    for addr, blob in writes:
        if not blob:
            continue
        off = 0
        while off < len(blob):
            chunk = blob[off : off + payload]
            records.append((addr + off, chunk))
            off += len(chunk)
    n = len(records)
    out = bytearray()
    for i, (addr, chunk) in enumerate(records):
        data = chunk + bytes(PAYLOAD_MAX - len(chunk))
        hdr = struct.pack(
            "<8I",
            UF2_MAGIC0,
            UF2_MAGIC1,
            UF2_FLAG_FAMILY,
            addr,
            len(chunk),
            i,
            n,
            family,
        )
        out.extend(hdr + data + struct.pack("<I", UF2_MAGIC_END))
    return bytes(out)


def load_loader(path: Path) -> tuple[bytes, int, dict]:
    return decode(path.read_bytes())
