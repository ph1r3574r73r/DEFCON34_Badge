#!/usr/bin/env python3
"""Flash the sealed hop that loops THE_FLAG_1 dump as QR codes on the OLED.

Unsigned 132-byte loader hop (amattas) → U-mode ASID=3 keystore read → QR v6-M
frames on the SH1107. Hangs on purpose (no Xous). Restore stock loader after.

Credit: Anthony Mattas — https://www.anthonymattas.com/articles/only-132-bytes

::

  python dump_via_qr.py build              # hop_asid_qr.uf2 (+ handback)
  python dump_via_qr.py handback           # smoke: still Sealed?
  python dump_via_qr.py flash              # QR loop on OLED
  python dump_via_qr.py restore            # stock loader.uf2

Hard rules: never flash developer-signed FW; never CRC-valid ``test k0`` while
sealed-hunting; always restore stock loader when done.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))

from constants import DEFAULT_LOADER  # noqa: E402


def _py(args: list[str], *, check: bool = True) -> int:
    cmd = [sys.executable, *args]
    print("+", " ".join(cmd), flush=True)
    r = subprocess.run(cmd, cwd=str(HERE))
    if check and r.returncode:
        raise SystemExit(r.returncode)
    return r.returncode


def _loader_path(explicit: Path | None) -> Path:
    if explicit:
        p = explicit.expanduser().resolve()
    else:
        p = (ROOT / DEFAULT_LOADER).resolve()
    if not p.is_file():
        raise SystemExit(
            f"stock loader not found: {p}\n"
            "Pass --loader /path/to/loader.uf2 (34b / CI ship loader)."
        )
    return p


def cmd_build(ns: argparse.Namespace) -> int:
    loader = _loader_path(ns.loader)
    _py([str(HERE / "build.py"), "--selftest"])
    for variant in ("handback", "asid_qr"):
        _py(
            [
                str(HERE / "build.py"),
                "--variant",
                variant,
                "--loader",
                str(loader),
                "--out",
                str(HERE / "out"),
            ]
        )
    print(
        "\nBuilt:\n"
        f"  {HERE / 'out' / 'hop_handback.uf2'}\n"
        f"  {HERE / 'out' / 'hop_asid_qr.uf2'}\n"
        "Next: dump_via_qr.py handback  →  dump_via_qr.py flash  →  dump_via_qr.py restore",
        flush=True,
    )
    return 0


def cmd_flash_uf2(uf2: Path, ns: argparse.Namespace) -> int:
    if not uf2.is_file():
        raise SystemExit(f"missing {uf2} — run: dump_via_qr.py build")
    args = [str(HERE / "flash.py"), "--uf2", str(uf2)]
    if ns.port:
        args.extend(["--port", ns.port])
    if ns.baud:
        args.extend(["--baud", str(ns.baud)])
    return _py(args, check=False)


def cmd_handback(ns: argparse.Namespace) -> int:
    print(
        "\n=== HANDBACK smoke ===\n"
        "Expect Xous back. Check About → Meditations: still Sealed.\n"
        "If Sealed dies here, STOP.\n",
        flush=True,
    )
    return cmd_flash_uf2(HERE / "out" / "hop_handback.uf2", ns)


def cmd_flash(ns: argparse.Namespace) -> int:
    print(
        "\n=== ASID_QR hop ===\n"
        "OLED loops QR frames of the keystore dump (includes THE_FLAG_1).\n"
        "HANGS — no Xous. When finished: dump_via_qr.py restore\n",
        flush=True,
    )
    return cmd_flash_uf2(HERE / "out" / "hop_asid_qr.uf2", ns)


def cmd_restore(ns: argparse.Namespace) -> int:
    loader = _loader_path(ns.loader)
    print(
        "\n=== RESTORE stock loader ===\n"
        f"Writing {loader}\n"
        "Then Meditations: Sealed + same k0 hash prefix.\n",
        flush=True,
    )
    return cmd_flash_uf2(loader, ns)


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--loader", type=Path, default=None, help=f"stock loader UF2 (default {DEFAULT_LOADER})")
    ap.add_argument("--port", default=None, help="boot1 serial port")
    ap.add_argument("--baud", type=int, default=1_000_000)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("build", help="build hop_handback.uf2 + hop_asid_qr.uf2")
    sub.add_parser("handback", help="flash handback smoke (must stay Sealed)")
    sub.add_parser("flash", help="flash asid_qr hop (QR loop on OLED)")
    sub.add_parser("restore", help="flash stock loader.uf2")

    ns = ap.parse_args()
    if ns.cmd == "build":
        return cmd_build(ns)
    if ns.cmd == "handback":
        return cmd_handback(ns)
    if ns.cmd == "flash":
        return cmd_flash(ns)
    if ns.cmd == "restore":
        return cmd_restore(ns)
    raise SystemExit(f"unknown cmd {ns.cmd}")


if __name__ == "__main__":
    raise SystemExit(main())
