#!/usr/bin/env python3
"""Upload sealed BIO memprobe and drain FIFO3 report over USB.

See bio/memprobe/main.c for the wire protocol.
"""
from __future__ import annotations

import argparse
import struct
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import serial
from serial.serialutil import SerialException

ROOT = Path(__file__).resolve().parents[1]
BIN = ROOT / "bio" / "memprobe" / "memprobe.bin"
BAUD = 1_000_000

TAGS = {
    0x4D455001: "START",
    0x43414E00: "CANARY",
    0x4D45444E: "DONE",
}


def find_port(preferred: str | None) -> str:
    from serial_port import resolve_port

    return resolve_port(preferred)


def drain(ser: serial.Serial, seconds: float = 0.4) -> str:
    end = time.time() + seconds
    chunks: list[bytes] = []
    while time.time() < end:
        b = ser.read(8192)
        if b:
            chunks.append(b)
        else:
            time.sleep(0.02)
    return b"".join(chunks).decode("utf-8", "replace")


def wait_token(ser: serial.Serial, tokens: tuple[str, ...], timeout: float = 8.0) -> str:
    end = time.time() + timeout
    buf = ""
    while time.time() < end:
        chunk = ser.read(4096)
        if chunk:
            buf += chunk.decode("utf-8", "replace")
            for line in buf.replace("\r", "\n").split("\n"):
                s = line.strip()
                if s.startswith("[console]"):
                    s = s[len("[console]") :].strip()
                # strip log prefixes
                if "SUCCESS" in s or s in tokens or any(t == s for t in tokens):
                    for t in tokens:
                        if t in s:
                            return t
                if s in ("OK", "ERR", "CLEAR", "SUCCESS"):
                    return s
        else:
            time.sleep(0.02)
    raise TimeoutError(f"timeout waiting {tokens}; got {buf[-300:]!r}")


def wait_ok(ser: serial.Serial, timeout: float = 8.0) -> str:
    """Wait for OK/SUCCESS/CLEAR/ERR, ignoring INFO/WARN keyboard spam."""
    end = time.time() + timeout
    buf = ""
    while time.time() < end:
        chunk = ser.read(4096)
        if chunk:
            buf += chunk.decode("utf-8", "replace")
            while "\n" in buf:
                line, buf = buf.split("\n", 1)
                s = line.strip()
                if s.startswith("[console]"):
                    s = s[len("[console]") :].strip()
                if s.startswith("INFO:") or s.startswith("WARN:") or "Input overflow" in s:
                    continue
                if s in ("OK", "ERR", "SUCCESS", "CLEAR"):
                    return s
                if "BIO load successful" in s:
                    return "OK"
                if s.endswith(" OK") and "INFO" not in s:
                    return "OK"
        else:
            time.sleep(0.02)
    raise TimeoutError(f"timeout waiting OK; tail={buf[-240:]!r}")


def upload(ser: serial.Serial, code: bytes, delay: float = 0.35) -> None:
    """Noise-tolerant upload (stock dc34-bio treats INFO lines as failures)."""
    sys.path.insert(0, str(ROOT / "repos" / "dc34-bio"))
    from dc34_bio.dc34_bio import make_chunk, CHUNK_DATA_SIZE  # type: ignore
    import base64

    if len(code) > 0xF00:
        raise ValueError("code too large")
    padded = code + bytes(0xF00 - len(code))
    n_chunks = max(1, (len(code) + CHUNK_DATA_SIZE - 1) // CHUNK_DATA_SIZE)

    ser.reset_input_buffer()
    ser.write(b"\r\n")
    time.sleep(0.2)
    drain(ser, 0.6)

    for cmd, accept in (
        (b"bio clear\r\n", ("CLEAR", "OK")),
        # no SAO pins — GPIO blink was colliding with keyboard INFO spam
        (b"bio clk 10000000\r\n", ("OK",)),
    ):
        ser.write(cmd)
        try:
            tok = wait_ok(ser, timeout=6)
            print(f"{cmd.decode().strip()}: {tok}")
            if tok not in accept and tok != "OK":
                print(f"warn: unexpected {tok}")
        except TimeoutError as e:
            print(f"warn: {e}")
        time.sleep(delay)

    for idx in range(n_chunks):
        data = padded[idx * CHUNK_DATA_SIZE : (idx + 1) * CHUNK_DATA_SIZE]
        payload = make_chunk(idx, data)
        line = f"bio {base64.b64encode(payload).decode()}\r\n".encode()
        for attempt in range(8):
            ser.write(line)
            try:
                tok = wait_ok(ser, timeout=6)
            except TimeoutError:
                print(f"chunk {idx+1}/{n_chunks} timeout attempt {attempt+1}")
                time.sleep(0.5)
                continue
            print(f"chunk {idx+1}/{n_chunks}: {tok}")
            if tok == "ERR":
                time.sleep(0.5)
                continue
            if tok in ("OK", "SUCCESS"):
                break
        else:
            raise RuntimeError(f"chunk {idx} failed")
        time.sleep(delay)

    ser.write(b"bio pad\r\n")
    tok = wait_ok(ser, timeout=10)
    print(f"pad: {tok}")
    # commit() only writes PDDB — must reload to start the core
    ser.write(b"bio reload\r\n")
    try:
        tok2 = wait_ok(ser, timeout=10)
        print(f"reload: {tok2}")
    except TimeoutError:
        out = drain(ser, 2.0)
        print(f"reload drain: {out[-240:]!r}")
        if "successful" not in out.lower() and "OK" not in out:
            raise RuntimeError("bio reload failed")
        print("reload: OK (soft)")


def parse_info_hex(line: str) -> int | None:
    """Parse `INFO:...bio: deadbeef (src/...)` hex words from bio rx."""
    s = line.strip()
    if "timeout" in s.lower():
        return None  # empty FIFO — do not treat RXF garbage as data
    if "INFO:" in s and "bio" in s.lower():
        core = s.split("(")[0]
        parts = core.replace(",", " ").split()
        for p in reversed(parts):
            p = p.strip()
            if p.startswith("0x"):
                p = p[2:]
            if p and all(c in "0123456789abcdefABCDEF" for c in p):
                try:
                    return int(p, 16)
                except ValueError:
                    continue
    return None


def rx_words(ser: serial.Serial, n: int, timeout_s: int = 2) -> list[int]:
    """Pull up to n FIFO words; stop early after consecutive empty timeouts."""
    words: list[int] = []
    empty_streak = 0
    while len(words) < n and empty_streak < 3:
        batch = min(8, n - len(words))  # FIFO depth is 8
        ser.write(f"bio rx {batch} {timeout_s}\r\n".encode())
        end = time.time() + timeout_s * batch + 4
        buf = ""
        got = 0
        timeouts = 0
        while time.time() < end and got < batch:
            chunk = ser.read(4096)
            if not chunk:
                time.sleep(0.02)
                continue
            buf += chunk.decode("utf-8", "replace")
            while "\n" in buf:
                line, buf = buf.split("\n", 1)
                if "timeout" in line.lower():
                    timeouts += 1
                    continue
                v = parse_info_hex(line)
                if v is not None:
                    words.append(v)
                    got += 1
                    if len(words) >= n or got >= batch:
                        break
                if line.strip() == "OK" or line.strip().endswith("OK") and "INFO" not in line:
                    # command finished
                    end = 0
                    break
        if got == 0 or timeouts >= batch:
            empty_streak += 1
        else:
            empty_streak = 0
        time.sleep(0.05)
    return words


def decode_report(words: list[int]) -> list[str]:
    lines: list[str] = []
    i = 0
    while i < len(words):
        w = words[i]
        if w == 0x4D455001:
            lines.append("START")
            i += 1
        elif w == 0x43414E00:
            if i + 3 < len(words):
                addr, wrote, got = words[i + 1], words[i + 2], words[i + 3]
                ok = "OK" if wrote == got else "FAIL"
                lines.append(f"CANARY local@{addr:#x} wrote={wrote:#x} read={got:#x} => {ok}")
                i += 4
            else:
                lines.append(f"CANARY truncated @ {i}")
                break
        elif (w & 0xFFFFFF00) == 0x57525200:
            pid = w & 0xFF
            if i + 3 < len(words):
                addr, wrote, got = words[i + 1], words[i + 2], words[i + 3]
                ok = "OPEN?" if wrote == got else "blocked/gutter"
                lines.append(
                    f"WRPROBE id={pid} @{addr:#x} wrote={wrote:#x} read={got:#x} => {ok}"
                )
                i += 4
            else:
                lines.append(f"WRPROBE truncated @ {i}")
                break
        elif (w & 0xFFFFFF00) == 0x53434E00:
            rid = w & 0xFF
            need = 9  # tag already consumed; need base,nwords,z,nz,fa,fv,la,lv,hh = 9 more
            if i + need < len(words):
                base = words[i + 1]
                nwords = words[i + 2]
                zeros = words[i + 3]
                nonzeros = words[i + 4]
                fa, fv = words[i + 5], words[i + 6]
                la, lv = words[i + 7], words[i + 8]
                hh = words[i + 9]
                lines.append(
                    f"SCAN id={rid} base={base:#x} words={nwords} zeros={zeros} nz={nonzeros} "
                    f"first={fa:#x}:{fv:#x} last={la:#x}:{lv:#x} hash_hits={hh}"
                )
                i += 10
            else:
                lines.append(f"SCAN truncated @ {i}")
                break
        elif w == 0x4D45444E:
            lines.append("DONE")
            i += 1
        else:
            lines.append(f"RAW[{i}] {w:#010x}")
            i += 1
    return lines


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--port", default=None, help="USB serial (default: auto-detect)")
    ap.add_argument("--bin", type=Path, default=BIN)
    ap.add_argument("--delay", type=float, default=0.5)
    ap.add_argument("--rx", type=int, default=64, help="FIFO words to pull")
    ap.add_argument(
        "--log",
        type=Path,
        default=None,
    )
    ap.add_argument("--skip-upload", action="store_true", help="Only drain FIFO (already loaded)")
    args = ap.parse_args()

    port = find_port(args.port)
    code = args.bin.read_bytes()
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")
    log_path = args.log or (ROOT / "captures" / "bio" / f"memprobe_{ts}.txt")
    log_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"port={port} bin={args.bin} ({len(code)} bytes)")
    ser = serial.Serial(port, baudrate=BAUD, timeout=0.25, write_timeout=3)
    try:
        drain(ser, 0.8)
        if not args.skip_upload:
            upload(ser, code, delay=args.delay)
            time.sleep(0.3)
            drain(ser, 0.3)

        words = rx_words(ser, args.rx, timeout_s=3)
        decoded = decode_report(words)
        report = [
            f"# bio memprobe {datetime.now(timezone.utc).isoformat()}",
            f"port: {port}",
            f"bin: {args.bin} ({len(code)} bytes)",
            f"words_read: {len(words)}",
            "",
            "## raw",
            *[f"{w:#010x}" for w in words],
            "",
            "## decoded",
            *decoded,
            "",
            "## operator",
            "- Confirm Meditations still Sealed / dca9ea49",
            "",
        ]
        log_path.write_text("\n".join(report))
        print("\n".join(decoded) if decoded else "(no decoded words)")
        print(f"log → {log_path}")
        # Heuristic exit: START+DONE and canary OK and WR probes not OPEN
        text = "\n".join(decoded)
        if "START" in text and "DONE" in text and "CANARY" in text and "OPEN?" not in text:
            return 0
        if "OPEN?" in text:
            print("ALERT: write-then-read matched — firewall may be open")
            return 0
        return 1 if not words else 0
    finally:
        try:
            ser.close()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
