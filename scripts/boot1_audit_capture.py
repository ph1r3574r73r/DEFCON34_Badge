#!/usr/bin/env python3
"""Capture Boot1 `audit` over USB (sealed-safe).

Enter Update mode: hold ANY button through hardware RESET (lower-right).
Screen should say **Update mode**. USB re-enumerates; console moves to CDC.

Safe: sends only `audit` (and newlines). Never: baosec-init, self_destruct,
lockdown, uf2 commit paths, paranoid, boardtype, etc.
"""
from __future__ import annotations

import argparse
import glob
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import serial
from serial.serialutil import SerialException

CAPTURE_DIR = Path(__file__).resolve().parents[1] / "captures" / "boot1"

BOOT1_HINTS = (
    "Commands include:",
    "USB is connected!",
    "Console moved to USB serial",
    "USB device ready",
    "Update mode",
    "bogomips",
    "bootwait is",
)
XOUS_HINTS = ("[console]", "VER.XOUS", "INFO:ux_api", "INFO:dc34", "selected index")


def list_ports() -> list[str]:
    return sorted(glob.glob("/dev/cu.usbmodem*")) + sorted(glob.glob("/dev/tty.usbmodem*"))


def pick_port(preferred: str | None) -> str | None:
    cands = list_ports()
    if preferred and os.path.exists(preferred):
        return preferred
    if not cands:
        return None
    if preferred and preferred not in cands:
        print(f"note: preferred {preferred} missing; using {cands[0]}", flush=True)
    return cands[0]


def open_ser(port: str, baud: int) -> serial.Serial:
    return serial.Serial(port, baudrate=baud, timeout=0.25, write_timeout=2.0)


def read_for(ser: serial.Serial, seconds: float) -> str:
    end = time.time() + seconds
    buf = bytearray()
    while time.time() < end:
        try:
            chunk = ser.read(8192)
        except SerialException:
            break
        if chunk:
            buf.extend(chunk)
    return buf.decode("ascii", "replace")


def classify(text: str) -> str:
    # Boot1 first — "USB is connected" can appear in both eras; prefer command list / ready
    boot_score = sum(1 for h in BOOT1_HINTS if h in text)
    xous_score = sum(1 for h in XOUS_HINTS if h in text)
    if boot_score >= 1 and xous_score == 0:
        return "boot1"
    if "Commands include:" in text or ("USB device ready" in text and "[console]" not in text):
        return "boot1"
    if xous_score >= 1:
        return "xous"
    return "unknown"


def ensure_open(port_pref: str | None, baud: int, ser: serial.Serial | None) -> tuple[serial.Serial, str]:
    if ser is not None and ser.is_open:
        try:
            ser.in_waiting  # probe
            return ser, ser.port
        except Exception:
            try:
                ser.close()
            except Exception:
                pass
    # wait for re-enum after reset
    for _ in range(40):
        port = pick_port(port_pref)
        if port:
            try:
                s = open_ser(port, baud)
                return s, port
            except SerialException:
                pass
        time.sleep(0.25)
    raise SystemExit("no USB serial after wait — plug badge / enter Update mode")


def wait_for_boot1(port_pref: str | None, baud: int, timeout: float) -> tuple[serial.Serial, str, str]:
    print(
        "\nWaiting for Boot1 Update mode.\n"
        ">>> Hold ANY button and press RESET (lower-right) until OLED says Update mode.\n"
        ">>> Keep holding through reset; release after Update mode shows.\n"
        ">>> Script will send `audit` only.\n",
        flush=True,
    )
    deadline = time.time() + timeout
    ser: serial.Serial | None = None
    port = port_pref
    acc = ""
    while time.time() < deadline:
        try:
            ser, port = ensure_open(port_pref, baud, ser)
        except SystemExit:
            print("… no port (resetting?)", flush=True)
            time.sleep(1.0)
            continue
        try:
            ser.reset_input_buffer()
            ser.write(b"\r\nhelp\r\n")
        except SerialException:
            try:
                ser.close()
            except Exception:
                pass
            ser = None
            print("… port dropped", flush=True)
            time.sleep(0.5)
            continue
        text = read_for(ser, 1.0)
        acc = (acc + text)[-8000:]
        mode = classify(text) if text.strip() else classify(acc)
        if mode == "boot1":
            print(f"Detected Boot1 on {port}", flush=True)
            return ser, port, acc
        if mode == "xous":
            print(f"… still Xous on {port}", flush=True)
        else:
            print(f"… quiet/unknown on {port}", flush=True)
        time.sleep(1.0)
    raise SystemExit("timeout waiting for Boot1")


def run_audit(ser: serial.Serial) -> str:
    try:
        ser.write(b"\r\n")
    except SerialException as e:
        raise SystemExit(f"write failed: {e}") from e
    time.sleep(0.2)
    read_for(ser, 0.4)
    ser.write(b"audit\r\n")
    return read_for(ser, 10.0) + read_for(ser, 5.0)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--port", default=None)
    ap.add_argument("--baud", type=int, default=1_000_000)
    ap.add_argument("--wait", type=float, default=300.0)
    ap.add_argument("--no-wait", action="store_true")
    args = ap.parse_args()

    CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")
    out_path = CAPTURE_DIR / f"audit_{ts}.txt"

    if args.no_wait:
        ser, port = ensure_open(args.port, args.baud, None)
        preamble = read_for(ser, 1.0)
        if classify(preamble) == "xous":
            raise SystemExit("looks like Xous; enter Update mode (omit --no-wait)")
    else:
        ser, port, preamble = wait_for_boot1(args.port, args.baud, args.wait)

    print(f"running audit on {port}…", flush=True)
    body = run_audit(ser)
    full = preamble + "\n===== audit =====\n" + body
    out_path.write_text(full, encoding="utf-8")
    print(f"wrote {out_path}", flush=True)

    interesting = re.compile(
        r"(Board type|Boot partition|Semver|serializer|Public serial|UUID|Paranoid|"
        r"Erase proof|Revocations|Boot0:|Boot1:|Next stage:|auto-audit|Stepping|"
        r"Possible attack|Description is|Commands include)",
        re.I,
    )
    print("--- interesting lines ---", flush=True)
    hits = 0
    for line in full.splitlines():
        if interesting.search(line):
            print(line, flush=True)
            hits += 1
    if hits == 0:
        print("(no audit fields matched — check full capture)", flush=True)
        print(full[-1500:], flush=True)

    try:
        ser.close()
    except Exception:
        pass
    return 0 if hits or "Semver" in full or "Board type" in full else 1


if __name__ == "__main__":
    raise SystemExit(main())
