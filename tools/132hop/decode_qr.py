#!/usr/bin/env python3
"""Decode asid_qr OLED video/stills → dump JSON.

Expects ASCII frames: H2 + page:02X + n_pages:02X + cksum:04X + b64(chunk).
Uses OpenCV QRCodeDetector. Tries gray + invert + warp.
"""

from __future__ import annotations

import argparse
import base64
import binascii
import json
import struct
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from constants import SCD_DUMP_BYTES
from oled_common import DUMP_BYTES
from qr_v6 import CHUNK, DUMP_BYTES as QR_DUMP_BYTES, MAGIC, N_QR, n_qr_for
from warp_pages import oled_warp

assert DUMP_BYTES == QR_DUMP_BYTES

VIDEO_EXTS = {".mov", ".mp4", ".m4v", ".avi", ".mkv", ".webm"}


def _parse_frame(
    text: str | bytes, expect_n: int | None = None
) -> tuple[int, int, int, bytes] | None:
    if isinstance(text, bytes):
        try:
            text = text.decode("ascii")
        except UnicodeDecodeError:
            return None
    text = text.strip()
    if not text.startswith("H2") or len(text) < 10:
        return None
    try:
        page = int(text[2:4], 16)
        n_pages = int(text[4:6], 16)
        cksum = int(text[6:10], 16)
        chunk = base64.b64decode(text[10:], validate=False)
    except (ValueError, TypeError, binascii.Error):
        return None
    if expect_n is not None and n_pages != expect_n:
        return None
    if n_pages < 1 or n_pages > 255 or page >= n_pages or not chunk:
        return None
    return page, n_pages, cksum, chunk


def _detect(img: np.ndarray) -> list[str]:
    det = cv2.QRCodeDetector()
    out: list[str] = []
    variants = [img]
    if img.ndim == 2:
        variants.append(255 - img)
        variants.append(cv2.cvtColor(img, cv2.COLOR_GRAY2BGR))
        variants.append(cv2.cvtColor(255 - img, cv2.COLOR_GRAY2BGR))
    else:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        variants.extend([gray, 255 - gray])
    for im in variants:
        try:
            text, _pts, _ = det.detectAndDecode(im)
        except cv2.error:
            continue
        if text:
            out.append(text)
        try:
            ok, texts, _pts, _ = det.detectAndDecodeMulti(im)
        except (cv2.error, AttributeError):
            continue
        if ok and texts:
            out.extend(t for t in texts if t)
    return out


def decode_gray(
    gray: np.ndarray, expect_n: int | None = None
) -> list[tuple[int, int, int, bytes]]:
    found = []
    variants = [
        gray,
        cv2.rotate(gray, cv2.ROTATE_90_CLOCKWISE),
        cv2.rotate(gray, cv2.ROTATE_180),
        cv2.rotate(gray, cv2.ROTATE_90_COUNTERCLOCKWISE),
    ]
    warped = oled_warp(gray)
    if warped is not None:
        variants.append(warped)
        variants.append(cv2.rotate(warped, cv2.ROTATE_90_CLOCKWISE))
        variants.append(cv2.rotate(warped, cv2.ROTATE_180))
        variants.append(cv2.rotate(warped, cv2.ROTATE_90_COUNTERCLOCKWISE))
    for src in variants:
        for text in _detect(src):
            parsed = _parse_frame(text, expect_n=expect_n)
            if parsed:
                found.append(parsed)
    if found:
        return found
    # Close-up 3px OLED: native cv2 often misses; 3× nearest on a square crop
    # works. Only on miss so full scans stay fast.
    h, w = gray.shape
    s = min(h, w)
    y0, x0 = (h - s) // 2, (w - s) // 2
    crop = gray[y0 : y0 + s, x0 : x0 + s]
    for src in (crop, 255 - crop):
        up = cv2.resize(
            src,
            (src.shape[1] * 3, src.shape[0] * 3),
            interpolation=cv2.INTER_NEAREST,
        )
        for text in _detect(up):
            parsed = _parse_frame(text, expect_n=expect_n)
            if parsed:
                found.append(parsed)
    return found


def decode_image(
    path: Path, expect_n: int | None = None
) -> list[tuple[int, int, int, bytes]]:
    bgr = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if bgr is None:
        return []
    return decode_gray(cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY), expect_n=expect_n)


def _ffmpeg_exe() -> str:
    import imageio_ffmpeg

    return imageio_ffmpeg.get_ffmpeg_exe()


def _probe_video(path: Path) -> tuple[int, int, float]:
    """Input stream size + displaymatrix degrees (0 if missing)."""
    p = subprocess.run(
        [_ffmpeg_exe(), "-hide_banner", "-i", str(path)],
        capture_output=True,
        text=True,
        errors="replace",
    )
    import re

    m = re.search(r"Stream #0:0.* (\d{2,5})x(\d{2,5})", p.stderr)
    if not m:
        raise SystemExit(f"could not probe video size: {path}")
    rot = 0.0
    r = re.search(r"rotation of (-?[\d.]+) degrees", p.stderr)
    if r:
        rot = float(r.group(1))
    return int(m.group(1)), int(m.group(2)), rot


def _orient_vf(rot: float) -> tuple[str, bool]:
    """Explicit displaymatrix vf (use with -noautorotate). swap_wh for ±90."""
    r = ((rot + 180.0) % 360.0) - 180.0
    if abs(r) < 1.0:
        return "", False
    if abs(abs(r) - 180.0) < 1.0:
        return "hflip,vflip", False
    if abs(r - 90.0) < 1.0:
        return "transpose=1", True
    if abs(r + 90.0) < 1.0:
        return "transpose=2", True
    return "", False


def iter_video_grays(path: Path, fps: float, extra_vf: str | None = None):
    """Yield grayscale frames sampled at fps (rgb24 pipe)."""
    w, h, rot = _probe_video(path)
    extra, swap = _orient_vf(rot)
    if extra_vf:
        extra, swap = extra_vf, extra_vf.startswith("transpose")
    if swap:
        w, h = h, w
    parts = [f"fps={fps:.4f}"]
    if extra:
        parts.append(extra)
    parts.append("format=rgb24")
    vf = ",".join(parts)
    print(f"{path.name}: {w}x{h} rot={rot:g} vf={vf}", flush=True)
    cmd = [
        _ffmpeg_exe(),
        "-hide_banner",
        "-loglevel",
        "error",
        "-noautorotate",
        "-i",
        str(path),
        "-vf",
        vf,
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "pipe:1",
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert proc.stdout is not None
    frame_n = w * h * 3
    i = 0
    try:
        while True:
            buf = proc.stdout.read(frame_n)
            if not buf or len(buf) < frame_n:
                break
            rgb = np.frombuffer(buf, dtype=np.uint8).reshape(h, w, 3)
            yield cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
            i += 1
    finally:
        proc.kill()
        proc.wait()


def decode_video(
    path: Path,
    fps: float,
    expect_n: int | None = None,
    extra_vf: str | None = None,
) -> tuple[dict[int, bytes], dict[int, int], int | None]:
    chunks: dict[int, bytes] = {}
    cksum_votes: dict[int, int] = {}
    n_qr = expect_n
    n = 0
    for gray in iter_video_grays(path, fps, extra_vf=extra_vf):
        n += 1
        hits = decode_gray(gray, expect_n=n_qr)
        seen = set()
        for page, npages, ck, chunk in hits:
            if page in seen:
                continue
            seen.add(page)
            if n_qr is None:
                n_qr = npages
            if page not in chunks:
                chunks[page] = chunk
                want = n_qr or "?"
                print(
                    f"{path.name}@{n}: NEW page {page:02X} chunk {len(chunk)}B "
                    f"cksum {ck:04X}  have {len(chunks)}/{want}",
                    flush=True,
                )
            cksum_votes[ck] = cksum_votes.get(ck, 0) + 1
        if n % 50 == 0:
            print(f"{path.name}: frame {n} have {len(chunks)}/{n_qr or '?'}", flush=True)
        if n_qr and len(chunks) == n_qr:
            print(f"{path.name}: complete at frame {n}", flush=True)
            break
    print(f"{path.name}: scanned {n} frames, unique pages {len(chunks)}/{n_qr or '?'}", flush=True)
    return chunks, cksum_votes, n_qr


def assemble(
    chunks: dict[int, bytes],
    cksum16: int | None,
    *,
    n_qr: int,
    dump_bytes: int,
    layout: str,
) -> dict:
    blob = bytearray()
    missing = []
    for i in range(n_qr):
        c = chunks.get(i)
        if c is None:
            missing.append(i)
            blob.extend(b"\x00" * CHUNK)
        else:
            blob.extend(c[:CHUNK].ljust(CHUNK, b"\x00"))
    dump = bytes(blob[:dump_bytes])
    acc = 0
    for i in range(0, len(dump) // 4 * 4, 4):
        acc ^= struct.unpack_from("<I", dump, i)[0]
    base = {
        "n_qr": n_qr,
        "chunk": CHUNK,
        "dump_bytes": dump_bytes,
        "have": len(chunks),
        "missing_pages": missing,
        "cksum16_header": None if cksum16 is None else f"{cksum16:04x}",
        "cksum16_recon": f"{acc & 0xFFFF:04x}",
        "cksum_match": cksum16 is not None and (acc & 0xFFFF) == cksum16 and not missing,
        "layout": layout,
    }
    if layout == "scd":
        base["dump"] = dump.hex()
        base["note"] = "SCD dump (lite 4K + full 4K). Feed to archive/unwrap.py with dump_qr.json."
        return base
    base.update(
        {
            "uuid": dump[0:32].hex(),
            "cp_id": dump[32:64].hex(),
            "root_seed": dump[64:96].hex(),
            "flag1": dump[96:128].hex(),
            "nuisance0": dump[128 : 128 + 3840].hex(),
            "chaff": dump[128 + 3840 : 128 + 3840 + 4096].hex(),
            "nuisance1": dump[128 + 3840 + 4096 :].hex(),
            "developer_mode": 0,
            "oem_mode": 1,
            "boot0_pubkey_fail": 0,
            "note": "oem_mode from USB audit; override if needed. Feed to archive/derive.py when cksum_match.",
        }
    )
    return base


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("inputs", nargs="+", type=Path, help="images, video, or still directories")
    ap.add_argument("-o", "--out", type=Path, default=Path("dump_qr.json"))
    ap.add_argument("--fps", type=float, default=2.0, help="sample rate for video inputs")
    ap.add_argument("--layout", choices=("asid", "scd"), default="asid")
    ap.add_argument("--n-qr", type=int, default=None)
    ap.add_argument("--dump-bytes", type=int, default=None)
    ap.add_argument(
        "--vf",
        default=None,
        help="override displaymatrix vf (e.g. transpose=2). empty = auto",
    )
    args = ap.parse_args()
    expect_n = args.n_qr
    if args.layout == "scd" and expect_n is None:
        expect_n = n_qr_for(args.dump_bytes or SCD_DUMP_BYTES)
    dump_bytes = args.dump_bytes
    if dump_bytes is None:
        dump_bytes = SCD_DUMP_BYTES if args.layout == "scd" else DUMP_BYTES
    files: list[Path] = []
    videos: list[Path] = []
    for p in args.inputs:
        if p.is_dir():
            files.extend(sorted(p.glob("*.png")) + sorted(p.glob("*.jpg")))
        elif p.suffix.lower() in VIDEO_EXTS:
            videos.append(p)
        else:
            files.append(p)
    chunks: dict[int, bytes] = {}
    cksum_votes: dict[int, int] = {}
    seen_n: int | None = expect_n
    for f in files:
        for page, npages, ck, chunk in decode_image(f, expect_n=seen_n):
            if seen_n is None:
                seen_n = npages
            chunks.setdefault(page, chunk)
            cksum_votes[ck] = cksum_votes.get(ck, 0) + 1
            print(f"{f.name}: page {page:02X} chunk {len(chunk)}B cksum {ck:04X}")
    for v in videos:
        vc, votes, vn = decode_video(
            v, args.fps, expect_n=seen_n, extra_vf=args.vf
        )
        if seen_n is None:
            seen_n = vn
        for page, chunk in vc.items():
            chunks.setdefault(page, chunk)
        for ck, n in votes.items():
            cksum_votes[ck] = cksum_votes.get(ck, 0) + n
    cksum16 = max(cksum_votes, key=cksum_votes.get) if cksum_votes else None
    n_qr = seen_n or n_qr_for(dump_bytes)
    doc = assemble(
        chunks, cksum16, n_qr=n_qr, dump_bytes=dump_bytes, layout=args.layout
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(doc, indent=2) + "\n")
    print(f"wrote {args.out}  have {doc['have']}/{n_qr}  cksum_match={doc['cksum_match']}")
    return 0 if doc["have"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
