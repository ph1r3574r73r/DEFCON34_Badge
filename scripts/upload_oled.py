#!/usr/bin/env python3
"""Upload a simple 128x128 B&W test image to the DC34 badge (no Pillow required)."""
from __future__ import annotations

import argparse
import base64
import struct
import time
import zlib

import serial

W = H = 128
CHUNK = 64
NUM = 32
BAUD = 1_000_000

GLYPHS = {
    "D": ["###.", "#..#", "#..#", "#..#", "###."],
    "C": [".###", "#...", "#...", "#...", ".###"],
    "3": ["###.", "..#.", ".##.", "..#.", "###."],
    "4": ["#..#", "#..#", "####", "...#", "...#"],
    "B": ["###.", "#..#", "###.", "#..#", "###."],
    "A": [".##.", "#..#", "####", "#..#", "#..#"],
    "O": [".##.", "#..#", "#..#", "#..#", ".##."],
    "H": ["#..#", "#..#", "####", "#..#", "#..#"],
    "I": ["###", ".#.", ".#.", ".#.", "###"],
    "P": ["###.", "#..#", "###.", "#...", "#..."],
    "S": [".###", "#...", ".##.", "...#", "###."],
    "E": ["####", "#...", "###.", "#...", "####"],
    "L": ["#...", "#...", "#...", "#...", "####"],
    "N": ["#..#", "##.#", "#.##", "#..#", "#..#"],
    " ": ["....", "....", "....", "....", "...."],
}


def make_bitmap(lines: list[str] | None = None) -> bytes:
    pix = [[True] * W for _ in range(H)]

    def rect(x0, y0, x1, y1, fill=False):
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                if 0 <= x < W and 0 <= y < H and (fill or x in (x0, x1) or y in (y0, y1)):
                    pix[y][x] = False

    def draw_text(x, y, text, scale=2):
        cx = x
        for ch in text:
            g = GLYPHS.get(ch, GLYPHS[" "])
            gw = max(len(r) for r in g)
            for ri, row in enumerate(g):
                row = row.ljust(gw, ".")
                for ci, c in enumerate(row):
                    if c != "#":
                        continue
                    for dy in range(scale):
                        for dx in range(scale):
                            yy, xx = y + ri * scale + dy, cx + ci * scale + dx
                            if 0 <= xx < W and 0 <= yy < H:
                                pix[yy][xx] = False
            cx += (gw + 1) * scale

    rect(0, 0, 127, 127)
    rect(1, 1, 126, 126)
    if lines is None:
        lines = ["DC34", "BAOCHIP", "SEALED"]
    y = 20
    for i, line in enumerate(lines[:3]):
        draw_text(10, y, line, 3 if i == 0 else 2)
        y += 28 if i == 0 else 24
    for yy in range(100, 120):
        for xx in range(100, 120):
            if (xx + yy) % 2 == 0:
                pix[yy][xx] = False

    pixels = [pix[y][x] for y in range(H) for x in range(W - 1, -1, -1)]
    packed: list[int] = []
    cur = n = 0
    for p in pixels:
        bit = 0 if p else 1
        cur |= bit << (31 - n)
        n += 1
        if n == 32:
            packed.append(cur)
            cur = n = 0
    reordered: list[int] = []
    for i in range(128):
        reordered += [packed[i * 4 + 3], packed[i * 4 + 2], packed[i * 4 + 1], packed[i * 4 + 0]]
    # Firmware reads with u32::from_be_bytes — must be big-endian on the wire.
    return struct.pack(f">{len(reordered)}I", *reordered)


def make_chunk(index: int, data: bytes) -> bytes:
    payload = struct.pack(">H", index) + data
    return payload + struct.pack(">I", zlib.crc32(payload) & 0xFFFFFFFF)


def read_response(ser: serial.Serial, timeout: float = 4.0) -> str | None:
    end = time.time() + timeout
    buf = ""
    while time.time() < end:
        line = ser.readline().decode("ascii", "replace")
        if not line:
            continue
        buf += line
        for part in buf.replace("\r", "\n").split("\n"):
            part = part.strip()
            if part.startswith("[console]"):
                part = part[len("[console]") :].strip()
            if part in ("OK", "ERR", "SUCCESS", "CLEAR"):
                return part
    return None


def upload(port: str, bitmap: bytes, delay: float = 0.15) -> None:
    assert len(bitmap) == 2048
    ser = serial.Serial(port, baudrate=BAUD, timeout=0.3)
    try:
        t = time.time() + 1.5
        while time.time() < t:
            ser.read(8192)
        ser.write(b"\r\n")
        time.sleep(0.2)
        ser.read(8192)

        chunks = [bitmap[i : i + CHUNK] for i in range(0, 2048, CHUNK)]
        for idx, data in enumerate(chunks):
            line = f"image {base64.b64encode(make_chunk(idx, data)).decode()}\r\n".encode()
            for attempt in range(6):
                ser.read(8192)
                ser.write(line)
                resp = read_response(ser)
                print(f"chunk {idx + 1}/{NUM} attempt {attempt + 1}: {resp}")
                if resp == "SUCCESS":
                    print("DONE — image uploaded")
                    return
                if resp == "OK":
                    break
                time.sleep(0.4)
            else:
                raise SystemExit(f"failed at chunk {idx}")
            time.sleep(delay)
        print("WARN: all chunks sent but no SUCCESS")
    finally:
        ser.close()


def bitmap_from_png(path: str) -> bytes:
    """Pack a 128x128 (or force-resized) B&W PNG the same way as dc34-image."""
    from PIL import Image

    img = Image.open(path)
    if img.size != (W, H):
        img = img.convert("L").resize((W, H), Image.Resampling.LANCZOS)
        img = img.convert("1", dither=Image.Dither.FLOYDSTEINBERG)
    img = img.transpose(Image.FLIP_LEFT_RIGHT).convert("1")
    pixels = list(img.getdata())
    packed: list[int] = []
    cur = n = 0
    for p in pixels:
        bit = 0 if p else 1
        cur |= bit << (31 - n)
        n += 1
        if n == 32:
            packed.append(cur)
            cur = n = 0
    reordered: list[int] = []
    for i in range(128):
        reordered += [packed[i * 4 + 3], packed[i * 4 + 2], packed[i * 4 + 1], packed[i * 4 + 0]]
    return struct.pack(f">{len(reordered)}I", *reordered)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--port", default=None, help="USB serial (default: auto-detect)")
    p.add_argument("--line", action="append", help="Up to 3 text lines (repeat flag)")
    p.add_argument("--png", help="Path to 128x128 (or any) PNG to upload")
    p.add_argument("--delay", type=float, default=0.15)
    args = p.parse_args()
    from serial_port import resolve_port

    port = resolve_port(args.port)
    if args.png:
        bitmap = bitmap_from_png(args.png)
    else:
        bitmap = make_bitmap(args.line)
    upload(port, bitmap, args.delay)


if __name__ == "__main__":
    main()
