#!/usr/bin/env python3
"""Boot1 Update-mode serial helpers (shared by flash.py / dump_via_qr.py)."""

from __future__ import annotations

import glob
import os
import time

import serial
from serial.serialutil import SerialException

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
    return sorted(glob.glob("/dev/cu.usbmodem*")) + sorted(glob.glob("/dev/tty.usbmodem*")) + sorted(
        glob.glob("/dev/ttyACM*")
    )


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
            ser.in_waiting
            return ser, ser.port
        except Exception:
            try:
                ser.close()
            except Exception:
                pass
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
        ">>> Keep holding through reset; release after Update mode shows.\n",
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
            time.sleep(0.5)
            continue
        try:
            ser.write(b"\r\naudit\r\n")
        except SerialException:
            try:
                ser.close()
            except Exception:
                pass
            ser = None
            time.sleep(0.5)
            continue
        text = read_for(ser, 1.2)
        acc = (acc + text)[-8000:]
        if classify(text) == "boot1" or classify(acc) == "boot1":
            return ser, port, acc
        time.sleep(0.4)
    if ser:
        try:
            ser.close()
        except Exception:
            pass
    raise SystemExit("timed out waiting for Boot1 Update mode")
