"""asid_oled stage-2 (archive): hex dump on OLED. Prefer asid_qr.

Runs at 0x6008c000. Photo the screen, then restore stock loader.uf2.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from constants import (  # noqa: E402
    DUMP_FLAG1,
    DUMP_ROOT,
    FB_ADDR,
    IOX_GPIOOUT_PC,
    PAGE_TABLE_ADDR,
    SLOT_FLAG1,
    SLOT_ROOT,
    STACK_ADDR,
    STATUS_ADDR,
    TRUSTED_PID,
)
from oled_common import SATP, SEG7, _mega, _slot, oled_driver_src  # noqa: E402

__all__ = ["SEG7", "oled_dump_src", "oled_layout_note"]

def oled_dump_src() -> str:
    return f"""
# asid_oled — dump slots 256+260, 7-seg hex on OLED, spin
    fence.i
    li sp, 0x{STACK_ADDR:x}
    call oled_bringup

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
    li t0, 0x{_mega(0x40000000):x}
    sw t0, 0x400(a0)
    li t0, 0x{_mega(0x50000000):x}
    sw t0, 0x500(a0)
    li t0, 0x{_mega(0x60000000):x}
    sw t0, 0x600(a0)
    li t0, 0x{_mega(0x61000000):x}
    sw t0, 0x610(a0)
    sfence.vma

    la t0, m_trap
    csrw mtvec, t0

    li t0, 0x{SATP:x}
    csrw satp, t0
    sfence.vma

    li t1, 0x11111111
    li t2, 0x{STATUS_ADDR:x}
    sw t1, 0(t2)

    csrr t0, mstatus
    li t1, 0x1800
    not t1, t1
    and t0, t0, t1
    csrw mstatus, t0

    la t0, s_stub
    csrw mepc, t0
    mret

m_trap:
    call oled_hex
hang:
    j hang

s_stub:
    li t1, 0x22222222
    li t2, 0x{STATUS_ADDR:x}
    sw t1, 0(t2)
    li a0, 0x{_slot(SLOT_ROOT):x}
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
    li a0, 0x{_slot(SLOT_FLAG1):x}
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
    li t1, 0x33333333
    li t2, 0x{STATUS_ADDR:x}
    sw t1, 0(t2)
    ecall
    j s_done

oled_hex:
    addi sp, sp, -8
    sw ra, 4(sp)
    li s1, 0x{IOX_GPIOOUT_PC:x}
    li s3, 0x{FB_ADDR:x}
    lw s0, 0(s1)
    call fb_clear
    call fb_stripe
    call load_seg7
    li s5, 0
    li s4, 0x{STATUS_ADDR:x}
st_byte:
    li t0, 4
    beq s5, t0, leg_start
    lbu t1, 0(s4)
    srli a0, t1, 4
    slli a1, s5, 4
    li a2, 16
    call blit_7seg
    lbu t1, 0(s4)
    andi a0, t1, 0xf
    slli t2, s5, 4
    addi a1, t2, 8
    li a2, 16
    call blit_7seg
    addi s4, s4, 1
    addi s5, s5, 1
    j st_byte
leg_start:
    li s5, 0
leg_loop:
    li t0, 16
    beq s5, t0, hex_start
    mv a0, s5
    slli a1, s5, 3
    li a2, 4
    call blit_7seg
    addi s5, s5, 1
    j leg_loop
hex_start:
    li s4, 0x{DUMP_ROOT:x}
    li s5, 0
hex_byte:
    li t0, 64
    beq s5, t0, hex_done
    lbu t1, 0(s4)
    srli a0, t1, 4
    andi t2, s5, 7
    slli t2, t2, 1
    slli a1, t2, 3
    srli a2, s5, 3
    slli t3, a2, 3
    slli t4, a2, 2
    add a2, t3, t4
    addi a2, a2, 28
    call blit_7seg
    lbu t1, 0(s4)
    andi a0, t1, 0xf
    andi t2, s5, 7
    slli t2, t2, 1
    addi t2, t2, 1
    slli a1, t2, 3
    srli a2, s5, 3
    slli t3, a2, 3
    slli t4, a2, 2
    add a2, t3, t4
    addi a2, a2, 28
    call blit_7seg
    addi s4, s4, 1
    addi s5, s5, 1
    j hex_byte
hex_done:
    call oled_flush
    lw ra, 4(sp)
    addi sp, sp, 8
    ret
""" + oled_driver_src()


def oled_layout_note() -> str:
    return (
        "OLED: bar, 0–F legend, status (11111111=no U / 22222222=in U / "
        "33333333=copy done), then 8 dump rows (root+flag1). "
        "Photo, transcribe, check SHA-256(flag1) vs 8e817665… Restore stock loader.uf2."
    )
