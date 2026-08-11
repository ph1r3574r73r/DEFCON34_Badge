#!/usr/bin/env python3
"""Live Update-mode flash of a hop UF2 via boot1 serial `uf2`.

RRAM write is immediate (32B RMW). Then `boot` to run the hop.
Requires: hold ANY button + RESET until OLED says Update mode.

Default is hop_handback.uf2. Hang hops (no Xous): asid_qr / spin / asid_hold, plus archive asid_oled/pages/scd.
Restore = stock loader.uf2 the same way.
"""

from __future__ import annotations

import argparse
import base64
import re
import struct
import sys
import time
from pathlib import Path

import serial
from serial.serialutil import SerialException

sys.path.insert(0, str(Path(__file__).resolve().parent))

from boot1_serial import classify, ensure_open, read_for, wait_for_boot1
from constants import (
    BAOCHIP_1X_UF2_FAMILY,
    LOADER_START,
    SPRING_OFF,
    STAGE2_ADDR,
    STAGE2_CEILING,
    STOCK_JAL,
)
from payload import HANG_VARIANTS
from uf2util import UF2_MAGIC0, UF2_MAGIC1, UF2_MAGIC_END

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_UF2 = Path(__file__).resolve().parent / "out" / "hop_handback.uf2"


def _variant_from_path(path: Path) -> str:
    name = path.stem  # hop_asid_oled
    return name.removeprefix("hop_") if name.startswith("hop_") else name


def parse_blocks(path: Path) -> list[tuple[int, int, bytes]]:
    data = path.read_bytes()
    if len(data) < 3 * 512 or len(data) % 512:
        raise SystemExit(f"{path} must be ≥3 UF2 blocks (got {len(data)} bytes)")
    n = len(data) // 512
    blocks = []
    for i in range(n):
        blk = data[i * 512 : (i + 1) * 512]
        m0, m1, _flags, addr, psize, _bno, total, fam = struct.unpack_from("<8I", blk, 0)
        mend = struct.unpack_from("<I", blk, 508)[0]
        if m0 != UF2_MAGIC0 or m1 != UF2_MAGIC1 or mend != UF2_MAGIC_END:
            raise SystemExit(f"block {i}: bad UF2 magic")
        if fam != BAOCHIP_1X_UF2_FAMILY:
            raise SystemExit(f"block {i}: family {fam:#x} != {BAOCHIP_1X_UF2_FAMILY:#x}")
        if total != n or psize < 1 or psize > 256:
            raise SystemExit(f"block {i}: bad total {total} or psize {psize}")
        blocks.append((addr, psize, blk))
    if blocks[0][0] != LOADER_START:
        raise SystemExit(f"block 0 addr {blocks[0][0]:#x} != loader {LOADER_START:#x}")
    if blocks[0][1] == 4:
        if blocks[1][0] != LOADER_START + SPRING_OFF or blocks[1][1] != 20:
            raise SystemExit(f"block 1 must be 20B springboard @ {LOADER_START + SPRING_OFF:#x}")
        expect = STAGE2_ADDR
        for i, (addr, psize, _) in enumerate(blocks[2:], start=2):
            if addr != expect:
                raise SystemExit(f"block {i}: expected contiguous stage2 @ {expect:#x}, got {addr:#x}")
            expect += psize
        if expect > STAGE2_CEILING:
            raise SystemExit(f"stage2 ends at {expect:#x} past ceiling {STAGE2_CEILING:#x}")
        return blocks
    # Stock loader restore: 256B payloads, stock jal, contiguous from LOADER_START.
    jal = struct.unpack_from("<I", blocks[0][2], 32)[0]
    if jal != STOCK_JAL:
        raise SystemExit(f"restore UF2 jal {jal:#x} != stock {STOCK_JAL:#x}")
    expect = LOADER_START
    for i, (addr, psize, _) in enumerate(blocks):
        if addr != expect:
            raise SystemExit(f"restore block {i}: expected {expect:#x}, got {addr:#x}")
        expect += psize
    return blocks


def send_block(ser: serial.Serial, addr: int, psize: int, blk: bytes, timeout: float = 5.0) -> str:
    b64 = base64.b64encode(blk).decode("ascii")
    ser.reset_input_buffer()
    ser.write(f"uf2 {b64}\r".encode())
    ser.flush()
    end = time.time() + timeout
    buf = ""
    while time.time() < end:
        chunk = ser.read(8192)
        if chunk:
            buf += chunk.decode("ascii", "replace")
            m = re.search(r"Wrote\s+(\d+)\s+to\s+(0x[0-9a-fA-F]+)", buf)
            if m:
                got_n, got_a = int(m.group(1)), int(m.group(2), 16)
                if got_n == psize and got_a == addr:
                    return buf
                raise SystemExit(f"write mismatch: expected {psize}@{addr:#x} got {got_n}@{got_a:#x}\n{buf}")
            if "Invalid write" in buf or "Decode error" in buf or "invalid u2f" in buf:
                raise SystemExit(f"boot1 rejected block:\n{buf}")
        time.sleep(0.02)
    raise SystemExit(f"timeout waiting for Wrote {psize} @ {addr:#x}\n{buf[-800:]}")


def after_boot_check(port_pref: str | None, baud: int) -> str:
    print("waiting for Xous re-enum…", flush=True)
    ser = None
    acc = ""
    for _ in range(40):
        try:
            ser, port = ensure_open(port_pref, baud, ser)
        except SystemExit:
            time.sleep(0.5)
            continue
        try:
            ser.write(b"\r\nver\r\n")
        except SerialException:
            try:
                ser.close()
            except Exception:
                pass
            ser = None
            time.sleep(0.5)
            continue
        text = read_for(ser, 1.5)
        acc = (acc + text)[-12000:]
        if classify(text) == "xous" or classify(acc) == "xous" or "VER.XOUS" in acc or "[console]" in acc:
            try:
                ser.write(b"test hw\r\n")
            except SerialException:
                pass
            acc += read_for(ser, 3.0)
            try:
                ser.close()
            except Exception:
                pass
            return acc
        time.sleep(0.5)
    if ser:
        try:
            ser.close()
        except Exception:
            pass
    return acc


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--uf2", type=Path, default=DEFAULT_UF2)
    ap.add_argument("--port", default=None)
    ap.add_argument("--baud", type=int, default=1_000_000)
    ap.add_argument("--wait", type=float, default=180.0)
    ap.add_argument("--no-boot", action="store_true", help="write only; do not send boot")
    args = ap.parse_args()

    blocks = parse_blocks(args.uf2)
    variant = _variant_from_path(args.uf2)
    restore = blocks[0][1] == 256
    hang = (not restore) and variant in HANG_VARIANTS
    print(f"UF2 OK: {args.uf2} ({len(blocks)} blocks, variant={variant})", flush=True)
    if restore:
        print(
            f"\n*** RESTORE STOCK LOADER ***\n"
            "Hold ANY button + RESET (lower-right) until OLED says Update mode.\n"
            f"Serial `uf2` will write {len(blocks)} RRAM blocks, then `boot`.\n"
            "This is ship loader.uf2, not developer firmware.\n",
            flush=True,
        )
    else:
        print(
            f"\n*** HOP {variant.upper()} FLASH ***\n"
            "Hold ANY button + RESET (lower-right) until OLED says Update mode.\n"
            f"Serial `uf2` will write {len(blocks)} RRAM patches, then `boot`.\n"
            "This is NOT developer firmware. Restore = stock loader.uf2.\n",
            flush=True,
        )
    if hang:
        print("This variant HANGS (no Xous). Photo the OLED, then restore loader.uf2.\n", flush=True)

    ser, port, _pre = wait_for_boot1(args.port, args.baud, args.wait)
    print(f"flashing on {port}…", flush=True)
    log = []
    for addr, psize, blk in blocks:
        print(f"  write {psize:3}B @ {addr:#010x}", flush=True)
        resp = send_block(ser, addr, psize, blk)
        log.append(resp)
        print(f"    ok", flush=True)
        time.sleep(0.15)

    if not args.no_boot:
        print("sending boot…", flush=True)
        try:
            ser.write(b"boot\r\n")
            ser.flush()
        except SerialException as e:
            print(f"boot write failed ({e}); reset the badge if it stays in Update mode", flush=True)
        try:
            ser.close()
        except Exception:
            pass
        time.sleep(2.0)
        post = after_boot_check(args.port, args.baud)
        cap = ROOT / "captures" / "hop132" / f"{variant}_{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}.txt"
        cap.parent.mkdir(parents=True, exist_ok=True)
        cap.write_text("===== uf2 =====\n" + "\n".join(log) + "\n===== post =====\n" + post)
        print(f"wrote {cap}", flush=True)
        print("--- post-boot excerpt ---", flush=True)
        print(post[-2000:], flush=True)
        xous_up = classify(post) == "xous" or "VER.XOUS" in post or "[console]" in post
        if hang:
            if xous_up:
                print("Xous came back — hop probably did not run. Still Sealed? Restore if unsure.", flush=True)
                return 1
            print("No Xous (expected). Photo OLED hex; then Update mode → stock loader.uf2.", flush=True)
            return 0
        if xous_up:
            if restore:
                print("RESTORE LOOKS UP (Xous). Check Meditations: still Sealed / dca9ea49.", flush=True)
            else:
                print("HANDBACK LOOKS UP (Xous). Check Meditations: still Sealed / dca9ea49.", flush=True)
            return 0
        print("Xous not clearly detected — check OLED. Restore with stock loader.uf2 if stuck.", flush=True)
        return 1

    try:
        ser.close()
    except Exception:
        pass
    print("writes done; --no-boot set. Send `boot` or reset yourself.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
