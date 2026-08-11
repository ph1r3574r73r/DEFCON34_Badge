#!/usr/bin/env python3
"""Sealed-safe CDC stress for Corigine USB / IFRAM loose-bounds probing.

Exercises oversized writes, short-packet-ish bursts, open/close thrash, and
interleaved console commands. Never sends CRC-valid `test k0`, factory wipe,
or flash commands.

After a run: confirm Meditations still shows Sealed / dca9ea49 on-device.
"""
from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import serial
from serial.serialutil import SerialException

BAUD = 1_000_000
ROOT = Path(__file__).resolve().parents[1]
CAPTURES = ROOT / "captures"

# Hard deny — never emit these on the wire.
DENY_PREFIXES = (
    b"test k0 ",
    b"test k0\t",
    b"factory",
    b"baosec-init",
    b"self_destruct",
    b"lockdown",
)


@dataclass
class Stats:
    phases: list[str] = field(default_factory=list)
    writes: int = 0
    bytes_out: int = 0
    reconnects: int = 0
    serial_errors: list[str] = field(default_factory=list)
    panic_hits: list[str] = field(default_factory=list)
    health_ok: bool | None = None
    notes: list[str] = field(default_factory=list)


def find_port(preferred: str | None) -> str:
    from serial_port import resolve_port

    return resolve_port(preferred)


def open_port(port: str, timeout: float = 0.2) -> serial.Serial:
    ser = serial.Serial(port, baudrate=BAUD, timeout=timeout, write_timeout=2.0)
    # drain boot/log spam
    t_end = time.time() + 0.8
    while time.time() < t_end:
        ser.read(8192)
    return ser


def safe_write(ser: serial.Serial, data: bytes, stats: Stats) -> None:
    low = data.lower()
    for p in DENY_PREFIXES:
        if p in low:
            raise RuntimeError(f"refusing to send denied payload containing {p!r}")
    ser.write(data)
    stats.writes += 1
    stats.bytes_out += len(data)


def drain(ser: serial.Serial, seconds: float = 0.3) -> str:
    end = time.time() + seconds
    chunks: list[bytes] = []
    while time.time() < end:
        b = ser.read(8192)
        if b:
            chunks.append(b)
        else:
            time.sleep(0.02)
    return b"".join(chunks).decode("utf-8", "replace")


def scan_for_panic(text: str, stats: Stats, tag: str) -> None:
    for key in ("PANIC", "panicked", "stack backtrace", "page fault", "EXCEPTION"):
        if key in text:
            line = next((ln for ln in text.splitlines() if key in ln), key)
            stats.panic_hits.append(f"{tag}: {line.strip()[:200]}")


def cmd(ser: serial.Serial, line: str, stats: Stats, wait: float = 0.6) -> str:
    safe_write(ser, (line.rstrip() + "\r\n").encode("ascii", "replace"), stats)
    out = drain(ser, wait)
    scan_for_panic(out, stats, f"cmd:{line.split()[0] if line.strip() else 'empty'}")
    return out


def health_check(ser: serial.Serial, stats: Stats) -> bool:
    """Return True if echo + ver + test hw look alive."""
    ok = True
    checks = (
        ("echo ifram-stress", ("ifram-stress",)),
        ("ver", ("xous", "v0.", "VER.")),
        ("test hw", ("HW.PASS", "HW.FAIL", "HW.VBAT", "HW.")),
    )
    for c, needles in checks:
        out = cmd(ser, c, stats, wait=1.5)
        low = out.lower()
        if not any(n.lower() in low or n in out for n in needles):
            ok = False
            stats.notes.append(f"health miss after `{c}`: {out[-180:]!r}")
    stats.health_ok = ok
    return ok


def phase_baseline(ser: serial.Serial, stats: Stats) -> None:
    stats.phases.append("baseline")
    health_check(ser, stats)


def phase_oversized(ser: serial.Serial, stats: Stats, rounds: int) -> None:
    """Blast CDC with payloads larger than APP/MPS to stress enqueue accounting."""
    stats.phases.append(f"oversized×{rounds}")
    sizes = (64, 512, 1024, 2048, 4096, 8192)
    for i in range(rounds):
        for n in sizes:
            payload = bytes([(i + n) & 0xFF]) * n
            # raw binary (no CRLF) — hits USB bulk path, not console parser
            try:
                safe_write(ser, payload, stats)
            except SerialException as e:
                stats.serial_errors.append(f"oversized write {n}: {e}")
                return
            time.sleep(0.01)
        # keep console awake interleaved
        if i % 2 == 0:
            cmd(ser, "echo ping", stats, wait=0.25)
        out = drain(ser, 0.15)
        scan_for_panic(out, stats, "oversized")


def phase_short_bursts(ser: serial.Serial, stats: Stats, rounds: int) -> None:
    """Many tiny writes / ZLP-ish gaps — residual / short-packet pressure."""
    stats.phases.append(f"short_bursts×{rounds}")
    for i in range(rounds):
        try:
            for _ in range(32):
                safe_write(ser, b"x", stats)
                time.sleep(0.001)
            safe_write(ser, b"\r\n", stats)
        except SerialException as e:
            stats.serial_errors.append(f"short_bursts: {e}")
            return
        out = drain(ser, 0.1)
        scan_for_panic(out, stats, "short")
        if i % 5 == 0:
            cmd(ser, f"echo burst-{i}", stats, wait=0.2)


def phase_console_flood(ser: serial.Serial, stats: Stats, rounds: int) -> None:
    """Long console lines (still safe verbs only)."""
    stats.phases.append(f"console_flood×{rounds}")
    safe_verbs = ("echo", "ver")
    for i in range(rounds):
        verb = safe_verbs[i % len(safe_verbs)]
        pad = "A" * (200 + (i % 300))
        try:
            cmd(ser, f"{verb} {pad}", stats, wait=0.35)
        except SerialException as e:
            stats.serial_errors.append(f"console_flood: {e}")
            return


def phase_reconnect(port: str, stats: Stats, rounds: int) -> serial.Serial | None:
    """Open/close thrash — exercises init / IFRAM zeroize paths."""
    stats.phases.append(f"reconnect×{rounds}")
    ser: serial.Serial | None = None
    for i in range(rounds):
        try:
            if ser and ser.is_open:
                ser.close()
            time.sleep(0.15)
            ser = open_port(port)
            stats.reconnects += 1
            out = cmd(ser, f"echo recon-{i}", stats, wait=0.5)
            scan_for_panic(out, stats, "reconnect")
        except SerialException as e:
            stats.serial_errors.append(f"reconnect {i}: {e}")
            time.sleep(0.5)
            try:
                ser = open_port(port)
            except SerialException as e2:
                stats.serial_errors.append(f"reconnect recover: {e2}")
                return None
    return ser


def write_report(path: Path, port: str, stats: Stats, elapsed: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# usb_ifram_stress {datetime.now(timezone.utc).isoformat()}",
        f"port: {port}",
        f"elapsed_s: {elapsed:.2f}",
        f"phases: {', '.join(stats.phases)}",
        f"writes: {stats.writes}",
        f"bytes_out: {stats.bytes_out}",
        f"reconnects: {stats.reconnects}",
        f"health_ok: {stats.health_ok}",
        f"panic_hits: {len(stats.panic_hits)}",
        f"serial_errors: {len(stats.serial_errors)}",
        "",
        "## panics / exceptions",
    ]
    lines += [f"- {p}" for p in stats.panic_hits] or ["- (none)"]
    lines += ["", "## serial errors"]
    lines += [f"- {e}" for e in stats.serial_errors] or ["- (none)"]
    lines += ["", "## notes"]
    lines += [f"- {n}" for n in stats.notes] or ["- (none)"]
    lines += [
        "",
        "## operator check",
        "- On badge: About → … → Meditations → still **Sealed** / `dca9ea49`.",
        "- If USB died: unplug/replug; re-run with `--quick`.",
        "",
    ]
    path.write_text("\n".join(lines))


def phase_trb_aim(ser: serial.Serial, stats: Stats, rounds: int) -> None:
    """Targeted APP-buffer pressure toward enq_index edge (not blind flood).

    Design notes (research-k0 § USB TRB→SPIM_FLASH):
    - Aim is cross-EP smash inside USB IFRAM slack, hoping to perturb TRB.dplo
      toward SPIM_FLASH_IFRAM (0x5001_9000). Host cannot set dplo directly.
    - Pattern: paced 512-byte OUT aligned to APP slot size, interleaved with
      PDDB-touching console cmds (`ver` / `test freemem` / `test proc`) to race SPI bounce.
    - Expectation: DoS / disconnect more likely than k0 exfil.
    """
    stats.phases.append("trb_aim")
    stats.notes.append(
        "trb-aim: paced 512B OUT + PDDB race (ver/freemem/proc); see research-k0 USB TRB design"
    )
    block = b"\xA5" * 512
    pddb_cmds = (b"ver\r\n", b"test freemem\r\n", b"test proc\r\n")
    for i in range(rounds):
        for _ in range(4):
            safe_write(ser, block, stats)
            time.sleep(0.01)
        safe_write(ser, pddb_cmds[i % len(pddb_cmds)], stats)
        time.sleep(0.15)
        drain = ser.read(16384)
        text = drain.decode("ascii", "replace")
        for line in text.splitlines():
            if "PANIC" in line or "panic" in line:
                stats.panic_hits.append(line[:200])
        if i % 4 == 0:
            print(f"  trb-aim {i+1}/{rounds}", flush=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--port", default=None, help="USB serial (default: auto-detect)")
    ap.add_argument("--quick", action="store_true", help="Fewer rounds (smoke)")
    ap.add_argument("--skip-reconnect", action="store_true")
    ap.add_argument(
        "--mode",
        choices=("stress", "trb-aim"),
        default="stress",
        help="stress=generic CDC; trb-aim=targeted APP/TRB pressure (design PoC)",
    )
    ap.add_argument(
        "--log",
        type=Path,
        default=None,
        help="Report path (default captures/usb_ifram_stress_TIMESTAMP.txt)",
    )
    args = ap.parse_args()

    try:
        port = find_port(args.port)
    except SystemExit as e:
        print(e, file=sys.stderr)
        return 2

    rounds = 3 if args.quick else 12
    short_rounds = 10 if args.quick else 40
    recon_rounds = 0 if args.skip_reconnect else (2 if args.quick else 6)
    trb_rounds = 6 if args.quick else 24

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")
    prefix = "usb_trb_aim" if args.mode == "trb-aim" else "usb_ifram_stress"
    log_path = args.log or (CAPTURES / f"{prefix}_{ts}.txt")
    stats = Stats()
    t0 = time.time()
    ser: serial.Serial | None = None

    print(f"port={port} mode={args.mode} quick={args.quick} log={log_path}")
    try:
        ser = open_port(port)
        phase_baseline(ser, stats)
        if stats.health_ok is False:
            stats.notes.append("baseline health failed — aborting")
            write_report(log_path, port, stats, time.time() - t0)
            print(f"ABORT baseline health fail → {log_path}")
            return 1

        if args.mode == "trb-aim":
            phase_trb_aim(ser, stats, trb_rounds)
        else:
            phase_oversized(ser, stats, rounds)
            phase_short_bursts(ser, stats, short_rounds)
            phase_console_flood(ser, stats, rounds)

            if recon_rounds:
                if ser and ser.is_open:
                    ser.close()
                ser = phase_reconnect(port, stats, recon_rounds)

        if ser is None or not ser.is_open:
            try:
                ser = open_port(port)
            except SerialException as e:
                stats.serial_errors.append(f"final open: {e}")
                stats.health_ok = False
                write_report(log_path, port, stats, time.time() - t0)
                print(f"FAIL could not reopen → {log_path}")
                return 1

        health_check(ser, stats)
    except SerialException as e:
        stats.serial_errors.append(f"fatal: {e}")
        stats.health_ok = False
    finally:
        if ser and ser.is_open:
            ser.close()
        write_report(log_path, port, stats, time.time() - t0)

    print(
        f"done health_ok={stats.health_ok} panics={len(stats.panic_hits)} "
        f"errors={len(stats.serial_errors)} → {log_path}"
    )
    print("Confirm on-device: Meditations still Sealed / dca9ea49")
    return 0 if stats.health_ok and not stats.panic_hits else 1


if __name__ == "__main__":
    raise SystemExit(main())
