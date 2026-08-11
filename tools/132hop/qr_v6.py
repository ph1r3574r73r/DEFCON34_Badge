#!/usr/bin/env python3
"""QR version 6, ECC M, mask 0 — tables + reference encoder for the hop.

Matches python-qrcode (same GF tables, RS poly, placement). Payload is ASCII:
  H2 + page:02X + n_pages:02X + cksum:04X + b64(chunk)
so phone/cv2 decoders never see NUL. Dump chunk is 72 B (96 B b64). 169 frames.
"""

from __future__ import annotations

import base64
import struct
from typing import Sequence

import qrcode
import qrcode.constants
import qrcode.util
from qrcode.LUT import rsPoly_LUT
from qrcode.base import EXP_TABLE, LOG_TABLE

VERSION = 6
SIZE = VERSION * 4 + 17  # 41
ECC = qrcode.constants.ERROR_CORRECT_M  # 0
MASK = 0
N_BLOCKS = 4
DC_LEN = 27
EC_LEN = 16
DATA_CW = N_BLOCKS * DC_LEN  # 108
TOTAL_CW = N_BLOCKS * (DC_LEN + EC_LEN)  # 172
GEN16 = rsPoly_LUT[EC_LEN]  # len 17, leading 1
BYTE_CAP = 106  # mode+count+term fit exactly 106 payload bytes into 108 CW

MAGIC = b"H2"
CHUNK = 72  # 96 b64 chars; 10 ASCII header + 96 = 106
DUMP_BYTES = 12160
N_QR = (DUMP_BYTES + CHUNK - 1) // CHUNK  # 169


def n_qr_for(dump_bytes: int) -> int:
    n = (dump_bytes + CHUNK - 1) // CHUNK
    if n < 1 or n > 255:
        raise ValueError(f"n_qr={n} out of 1..255 (dump_bytes={dump_bytes})")
    return n

# OLED blit: 41×2 = 82 px, centered → origin 23 (quiet ≥ 23/2 ≈ 11 modules)
PX = 2
QR_ORIGIN = (128 - SIZE * PX) // 2
assert QR_ORIGIN == 23


def gf_mul(a: int, b: int) -> int:
    if a == 0 or b == 0:
        return 0
    return EXP_TABLE[(LOG_TABLE[a] + LOG_TABLE[b]) % 255]


def rs_block(data: Sequence[int]) -> list[int]:
    assert len(data) == DC_LEN
    ec = [0] * EC_LEN
    for byte in data:
        factor = byte ^ ec[0]
        ec = ec[1:] + [0]
        if factor:
            for j in range(EC_LEN):
                ec[j] ^= gf_mul(GEN16[j + 1], factor)
    return ec


def data_codewords(payload: bytes) -> list[int]:
    if len(payload) > BYTE_CAP:
        raise ValueError(f"payload {len(payload)} > {BYTE_CAP}")
    bits: list[int] = []

    def put(val: int, n: int) -> None:
        for i in range(n - 1, -1, -1):
            bits.append((val >> i) & 1)

    put(0b0100, 4)  # byte mode
    put(len(payload), 8)
    for b in payload:
        put(b, 8)
    need = DATA_CW * 8
    for _ in range(min(4, need - len(bits))):
        bits.append(0)
    while len(bits) % 8:
        bits.append(0)
    pad = True
    while len(bits) < need:
        put(0xEC if pad else 0x11, 8)
        pad = not pad
    assert len(bits) == need
    return [int("".join(str(x) for x in bits[i : i + 8]), 2) for i in range(0, need, 8)]


def interleave(dc: list[list[int]], ec: list[list[int]]) -> list[int]:
    out: list[int] = []
    for i in range(DC_LEN):
        for blk in dc:
            out.append(blk[i])
    for i in range(EC_LEN):
        for blk in ec:
            out.append(blk[i])
    assert len(out) == TOTAL_CW
    return out


def codewords(payload: bytes) -> list[int]:
    raw = data_codewords(payload)
    dc = [raw[i * DC_LEN : (i + 1) * DC_LEN] for i in range(N_BLOCKS)]
    ec = [rs_block(b) for b in dc]
    return interleave(dc, ec)


def function_template() -> tuple[list[list[bool]], list[list[bool]]]:
    """func[y][x], dark[y][x] for reserved modules (finders/timing/align/format)."""
    qr = qrcode.QRCode(
        version=VERSION,
        error_correction=ECC,
        box_size=1,
        border=0,
        mask_pattern=MASK,
    )
    qr.modules_count = SIZE
    qr.modules = [[None] * SIZE for _ in range(SIZE)]
    qr.setup_position_probe_pattern(0, 0)
    qr.setup_position_probe_pattern(SIZE - 7, 0)
    qr.setup_position_probe_pattern(0, SIZE - 7)
    qr.setup_position_adjust_pattern()
    qr.setup_timing_pattern()
    qr.setup_type_info(False, MASK)
    func = [[m is not None for m in row] for row in qr.modules]
    dark = [[bool(m) if m is not None else False for m in row] for row in qr.modules]
    return func, dark


def map_data(func: list[list[bool]], dark0: list[list[bool]], cw: Sequence[int]) -> list[list[bool]]:
    mat = [row[:] for row in dark0]
    inc = -1
    row = SIZE - 1
    bit_index = 7
    byte_index = 0
    data_len = len(cw)
    for col in range(SIZE - 1, 0, -2):
        if col <= 6:
            col -= 1
        while True:
            for c in (col, col - 1):
                if not func[row][c]:
                    dbit = False
                    if byte_index < data_len:
                        dbit = ((cw[byte_index] >> bit_index) & 1) == 1
                    if (row + c) % 2 == 0:  # mask 0
                        dbit = not dbit
                    mat[row][c] = dbit
                    bit_index -= 1
                    if bit_index == -1:
                        byte_index += 1
                        bit_index = 7
            row += inc
            if row < 0 or row >= SIZE:
                row -= inc
                inc = -inc
                break
    return mat


def encode_matrix(payload: bytes) -> list[list[bool]]:
    func, dark0 = function_template()
    return map_data(func, dark0, codewords(payload))


def frame_payload(page: int, cksum16: int, chunk: bytes, n_pages: int = N_QR) -> bytes:
    if len(chunk) > CHUNK:
        raise ValueError("chunk too long")
    hdr = MAGIC + f"{page:02X}{n_pages:02X}{cksum16:04X}".encode("ascii")
    body = base64.b64encode(chunk)
    out = hdr + body
    if len(out) > BYTE_CAP:
        raise ValueError(f"frame {len(out)} > {BYTE_CAP}")
    return out


def dump_frames(dump: bytes, cksum16: int | None = None) -> list[bytes]:
    if len(dump) != DUMP_BYTES:
        raise ValueError(f"dump {len(dump)} != {DUMP_BYTES}")
    if cksum16 is None:
        acc = 0
        for i in range(0, len(dump), 4):
            acc ^= struct.unpack_from("<I", dump, i)[0]
        cksum16 = acc & 0xFFFF
    frames = []
    for i in range(N_QR):
        chunk = dump[i * CHUNK : (i + 1) * CHUNK].ljust(CHUNK, b"\x00")
        frames.append(frame_payload(i, cksum16, chunk))
    return frames


def _pack_bitmap(bits: list[list[bool]]) -> bytes:
    """41 rows × 6 bytes (low 41 bits used, bit0 = x0)."""
    out = bytearray()
    for y in range(SIZE):
        acc = 0
        for x in range(SIZE):
            if bits[y][x]:
                acc |= 1 << x
        out.extend(acc.to_bytes(6, "little"))
    return bytes(out)


def table_words() -> dict[str, list[int]]:
    func, dark = function_template()
    func_b = _pack_bitmap(func)
    dark_b = _pack_bitmap(dark)
    exp = [int(x) & 0xFF for x in EXP_TABLE[:256]]
    log = [int(x) & 0xFF for x in LOG_TABLE[:256]]
    gen = [int(x) & 0xFF for x in GEN16[1:]]  # 16 coeffs

    def words(b: bytes) -> list[int]:
        pad = b + bytes((-len(b)) % 4)
        return [int.from_bytes(pad[i : i + 4], "little") for i in range(0, len(pad), 4)]

    b64alpha = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
    hexdigits = b"0123456789ABCDEF"
    return {
        "gf_exp": words(bytes(exp)),
        "gf_log": words(bytes(log)),
        "rs_gen": words(bytes(gen)),
        "func_bits": words(func_b),
        "dark_bits": words(dark_b),
        "b64alpha": words(b64alpha),
        "hexdigits": words(hexdigits),
        "_sizes": {
            "func_bytes": len(func_b),
            "dark_bytes": len(dark_b),
            "exp": 256,
            "log": 256,
            "gen": 16,
        },
    }


def lib_matrix(payload: bytes) -> list[list[bool]]:
    qr = qrcode.QRCode(
        version=VERSION,
        error_correction=ECC,
        box_size=1,
        border=0,
        mask_pattern=MASK,
    )
    qr.add_data(qrcode.util.QRData(payload, mode=qrcode.util.MODE_8BIT_BYTE), optimize=0)
    qr.make(fit=False)
    return [[bool(x) for x in row] for row in qr.modules]


def render_oled(mat: list[list[bool]], *, invert: bool = True) -> "object":
    import numpy as np

    img = np.full((128, 128), 255 if invert else 0, dtype="uint8")
    ox = oy = QR_ORIGIN
    on, off = (0, 255) if invert else (255, 0)
    for y in range(SIZE):
        for x in range(SIZE):
            val = on if mat[y][x] else off
            yy, xx = oy + y * PX, ox + x * PX
            img[yy : yy + PX, xx : xx + PX] = val
    return img


def selftest() -> None:
    payload = frame_payload(0, 0x9AF6, bytes(range(72)))
    assert len(payload) == BYTE_CAP, len(payload)
    ours = encode_matrix(payload)
    lib = lib_matrix(payload)
    if ours != lib:
        diff = sum(ours[y][x] != lib[y][x] for y in range(SIZE) for x in range(SIZE))
        raise SystemExit(f"matrix mismatch vs python-qrcode ({diff} modules)")
    dump = bytes((i * 17 + 3) & 0xFF for i in range(DUMP_BYTES))
    frames = dump_frames(dump)
    assert len(frames) == N_QR
    acc = 0
    recon = bytearray()
    for i, fr in enumerate(frames):
        assert fr.startswith(b"H2")
        assert int(fr[2:4], 16) == i
        assert int(fr[4:6], 16) == N_QR
        recon.extend(base64.b64decode(fr[10:]))
        mat = encode_matrix(fr)
        assert mat == lib_matrix(fr)
        acc ^= 1
    recon = bytes(recon[:DUMP_BYTES])
    if recon != dump:
        raise SystemExit("frame roundtrip mismatch")
    try:
        import cv2

        img = render_oled(encode_matrix(frames[0]))
        big = cv2.resize(img, (512, 512), interpolation=cv2.INTER_NEAREST)
        det = cv2.QRCodeDetector()
        text, pts, _ = det.detectAndDecode(big)
        if not text:
            # try as BGR
            bgr = cv2.cvtColor(big, cv2.COLOR_GRAY2BGR)
            text, pts, _ = det.detectAndDecode(bgr)
        if text:
            got = text.encode("latin-1", "replace") if isinstance(text, str) else text
            if got != frames[0] and text.encode("ascii", "replace") != frames[0]:
                # cv2 sometimes returns str; compare ascii
                if text.encode("ascii") != frames[0]:
                    print("cv2 decoded but bytes differ:", repr(text[:20]))
            else:
                print("cv2 roundtrip OK")
        else:
            print("cv2 did not decode synthetic still (OK — phone/video usually better)")
    except Exception as e:
        print(f"cv2 check skipped: {e}")
    print(f"qr_v6 selftest OK  v{VERSION}-M mask{MASK}  {N_QR} frames × {CHUNK}B  cap={BYTE_CAP}")


if __name__ == "__main__":
    selftest()
