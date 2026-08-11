"""Shared SH1107 driver + keystore dump layout for asid_qr (and archive hops)."""

from __future__ import annotations

from constants import (
    DATA_SLOT_START,
    FB_ADDR,
    IOX_AFSEL4,
    IOX_GPIOOE_PC,
    IOX_GPIOOUT_PC,
    PAGE_TABLE_ADDR,
    SLOT_BYTES,
    SLOT_CP_ID,
    SLOT_FLAG1,
    SLOT_ROOT,
    SLOT_UUID,
    TRUSTED_PID,
)

# 7-segment hex (bit0=A … bit6=G). Copied to SRAM so we never lbu font from RRAM.
SEG7 = bytes(
    [
        0x3F,
        0x06,
        0x5B,
        0x4F,
        0x66,
        0x6D,
        0x7D,
        0x07,
        0x7F,
        0x6F,
        0x77,
        0x7C,
        0x39,
        0x5E,
        0x79,
        0x71,
    ]
)
SEG_SRAM = 0x61001840  # after 2048B framebuffer (asid_oled layout)

# D A U X W R V — U=1 required: after protect()+INVERT_PRIV, RRC vex_mm
# is 1 only in U-mode. S-mode looks like the kernel and data-slot reads return 0.
PTE_U_DAXWRV = 0xDF
SATP = (1 << 31) | (TRUSTED_PID << 22) | (PAGE_TABLE_ADDR >> 12)

# Keystore dump layout in SRAM (same for asid_pages / asid_qr)
DUMP_BASE = 0x61001000
DUMP_BYTES = 12160
N_PAGES = DUMP_BYTES // 64  # 190

# (slot_index, nslots, dest_off)
_RANGES = (
    (SLOT_UUID, 1, 0),
    (SLOT_CP_ID, 1, 32),
    (SLOT_ROOT, 1, 64),
    (SLOT_FLAG1, 1, 96),
    (8, 120, 128),
    (128, 128, 128 + 3840),
    (1920, 128, 128 + 3840 + 4096),
)


def _slot(index: int) -> int:
    return DATA_SLOT_START + index * SLOT_BYTES


def _mega(pa: int) -> int:
    return ((pa >> 22) << 20) | PTE_U_DAXWRV


def _copy_calls() -> str:
    lines = []
    for idx, n, off in _RANGES:
        lines.append(f"    li a0, 0x{_slot(idx):x}")
        lines.append(f"    li a1, 0x{DUMP_BASE + off:x}")
        lines.append(f"    li a2, {n}")
        lines.append("    call copy_slots")
    return "\n".join(lines)


# SH1107 init (page/column mode matching bao1x-hal), display-on last.
INIT_CMDS = bytes(
    [
        0xAE,  # display off
        0xAD, 0x80,  # DC-DC
        0xDC, 0x00,  # start line
        0xD3, 0x00,  # offset
        0x81, 0x3F,  # contrast
        0x20,  # page address mode (CS-held bursts)
        0xA1,  # segment remap (flip L/R vs first 7-seg flash)
        0xC8,  # COM scan inverted
        0xA8, 0x7F,  # mux 128
        0xD5, 0x60,  # clock
        0xD9, 0x22,  # charge
        0xDB, 0x35,  # VCOMH
        0xB0,  # page 0
        0xA4,  # not entire-on
        0xA6,  # normal (1 = lit)
        0xAF,  # display on
    ]
)


def _words_le(blob: bytes) -> list[int]:
    pad = blob + bytes((-len(blob)) % 4)
    return [int.from_bytes(pad[i : i + 4], "little") for i in range(0, len(pad), 4)]

def oled_driver_src(
    *,
    fb_addr: int = FB_ADDR,
    seg_sram: int = SEG_SRAM,
    iox_out: int = IOX_GPIOOUT_PC,
    iox_oe: int = IOX_GPIOOE_PC,
    iox_afsel: int = IOX_AFSEL4,
) -> str:
    init_words = "\n".join(f"    .word 0x{w:08x}" for w in _words_le(INIT_CMDS))
    seg_words = [int.from_bytes(SEG7[i : i + 4], "little") for i in range(0, 16, 4)]
    return f"""
# --- GPIO SH1107 ---
# s0 = PC out shadow, s1 = GPIOOUT_PC, s3 = FB
oled_bringup:
    addi sp, sp, -8
    sw ra, 4(sp)
    li s1, 0x{iox_out:x}
    li t0, 0x{iox_afsel:x}
    lw t1, 0(t0)
    li t2, 0xffffc000
    and t1, t1, t2
    sw t1, 0(t0)
    li t0, 0x{iox_oe:x}
    lw t1, 0(t0)
    ori t1, t1, 0x5f
    sw t1, 0(t0)
    li s0, 0x8
    sw s0, 0(s1)
    li a0, 4000000
    call delay
    ori s0, s0, 0x50
    sw s0, 0(s1)
    li a0, 12000000
    call delay
    li s3, 0x{fb_addr:x}
    la s4, init_cmds
    li s5, {len(INIT_CMDS)}
init_loop:
    beq s5, zero, init_done
    lbu a0, 0(s4)
    call oled_cmd
    addi s4, s4, 1
    addi s5, s5, -1
    j init_loop
init_done:
    call fb_clear
    call fb_stripe
    call oled_flush
    lw ra, 4(sp)
    addi sp, sp, 8
    ret

load_seg7:
    li t0, 0x{seg_sram:x}
    li t1, 0x{seg_words[0]:x}
    sw t1, 0(t0)
    li t1, 0x{seg_words[1]:x}
    sw t1, 4(t0)
    li t1, 0x{seg_words[2]:x}
    sw t1, 8(t0)
    li t1, 0x{seg_words[3]:x}
    sw t1, 12(t0)
    ret

# a0=nibble a1=x a2=y  (5×9 7-seg in 8×14 cell)
blit_7seg:
    addi sp, sp, -20
    sw ra, 16(sp)
    sw s6, 12(sp)
    sw s7, 8(sp)
    sw s8, 4(sp)
    sw s9, 0(sp)
    mv s6, a1
    mv s7, a2
    li s8, 0x{seg_sram:x}
    add s8, s8, a0
    lbu s9, 0(s8)
    andi t0, s9, 1
    beq t0, zero, sA
    addi a0, s6, 1
    mv a1, s7
    li a2, 3
    call hline
sA:
    andi t0, s9, 2
    beq t0, zero, sB
    addi a0, s6, 4
    addi a1, s7, 1
    li a2, 3
    call vline
sB:
    andi t0, s9, 4
    beq t0, zero, sC
    addi a0, s6, 4
    addi a1, s7, 5
    li a2, 3
    call vline
sC:
    andi t0, s9, 8
    beq t0, zero, sD
    addi a0, s6, 1
    addi a1, s7, 8
    li a2, 3
    call hline
sD:
    andi t0, s9, 16
    beq t0, zero, sE
    mv a0, s6
    addi a1, s7, 5
    li a2, 3
    call vline
sE:
    andi t0, s9, 32
    beq t0, zero, sF
    mv a0, s6
    addi a1, s7, 1
    li a2, 3
    call vline
sF:
    andi t0, s9, 64
    beq t0, zero, sG
    addi a0, s6, 1
    addi a1, s7, 4
    li a2, 3
    call hline
sG:
    lw ra, 16(sp)
    lw s6, 12(sp)
    lw s7, 8(sp)
    lw s8, 4(sp)
    lw s9, 0(sp)
    addi sp, sp, 20
    ret

# a0=x a1=y a2=count
hline:
    addi sp, sp, -16
    sw ra, 12(sp)
    sw a0, 8(sp)
    sw a1, 4(sp)
    sw a2, 0(sp)
hl_loop:
    lw t0, 0(sp)
    beq t0, zero, hl_done
    lw a0, 8(sp)
    lw a1, 4(sp)
    call set_pixel
    lw t0, 8(sp)
    addi t0, t0, 1
    sw t0, 8(sp)
    lw t0, 0(sp)
    addi t0, t0, -1
    sw t0, 0(sp)
    j hl_loop
hl_done:
    lw ra, 12(sp)
    addi sp, sp, 16
    ret

vline:
    addi sp, sp, -16
    sw ra, 12(sp)
    sw a0, 8(sp)
    sw a1, 4(sp)
    sw a2, 0(sp)
vl_loop:
    lw t0, 0(sp)
    beq t0, zero, vl_done
    lw a0, 8(sp)
    lw a1, 4(sp)
    call set_pixel
    lw t0, 4(sp)
    addi t0, t0, 1
    sw t0, 4(sp)
    lw t0, 0(sp)
    addi t0, t0, -1
    sw t0, 0(sp)
    j vl_loop
vl_done:
    lw ra, 12(sp)
    addi sp, sp, 16
    ret

set_pixel:
    srli t0, a1, 3
    slli t0, t0, 7
    add t0, t0, a0
    add t0, t0, s3
    lbu t1, 0(t0)
    andi t2, a1, 7
    li t3, 1
    sll t3, t3, t2
    or t1, t1, t3
    sb t1, 0(t0)
    ret

clr_pixel:
    srli t0, a1, 3
    slli t0, t0, 7
    add t0, t0, a0
    add t0, t0, s3
    lbu t1, 0(t0)
    andi t2, a1, 7
    li t3, 1
    sll t3, t3, t2
    not t3, t3
    and t1, t1, t3
    sb t1, 0(t0)
    ret

fb_fill_ones:
    mv t0, s3
    li t1, 512
    li t2, 0xffffffff
ff_loop:
    beq t1, zero, ff_done
    sw t2, 0(t0)
    addi t0, t0, 4
    addi t1, t1, -1
    j ff_loop
ff_done:
    ret

fb_clear:
    mv t0, s3
    li t1, 512
fc_loop:
    beq t1, zero, fc_done
    sw zero, 0(t0)
    addi t0, t0, 4
    addi t1, t1, -1
    j fc_loop
fc_done:
    ret

fb_stripe:
    mv t0, s3
    li t1, 128
    li t2, 0x07
fs_loop:
    beq t1, zero, fs_done
    sb t2, 0(t0)
    addi t0, t0, 1
    addi t1, t1, -1
    j fs_loop
fs_done:
    ret

oled_flush:
    addi sp, sp, -16
    sw ra, 12(sp)
    sw s4, 8(sp)
    sw s5, 4(sp)
    sw s6, 0(sp)
    li s4, 0
flush_page:
    li t0, 16
    beq s4, t0, flush_done
    ori a0, s4, 0xb0
    call oled_cmd
    li a0, 0x00
    call oled_cmd
    li a0, 0x10
    call oled_cmd
    call oled_dstart
    slli s5, s4, 7
    add s5, s5, s3
    li s6, 128
flush_byte:
    lbu a0, 0(s5)
    call spi_tx
    addi s5, s5, 1
    addi s6, s6, -1
    bnez s6, flush_byte
    call oled_dend
    addi s4, s4, 1
    j flush_page
flush_done:
    lw ra, 12(sp)
    lw s4, 8(sp)
    lw s5, 4(sp)
    lw s6, 0(sp)
    addi sp, sp, 16
    ret

oled_cmd:
    addi sp, sp, -8
    sw ra, 4(sp)
    sw a0, 0(sp)
    li t0, 0xfffffffb
    and s0, s0, t0
    li t0, 0xfffffff7
    and s0, s0, t0
    sw s0, 0(s1)
    lw a0, 0(sp)
    call spi_tx
    ori s0, s0, 8
    sw s0, 0(s1)
    lw ra, 4(sp)
    addi sp, sp, 8
    ret

oled_dstart:
    ori s0, s0, 4
    li t0, 0xfffffff7
    and s0, s0, t0
    sw s0, 0(s1)
    ret

oled_dend:
    ori s0, s0, 8
    sw s0, 0(s1)
    ret

spi_tx:
    li t2, 8
spi_bit:
    srli t0, a0, 7
    andi t0, t0, 1
    li t1, 0xfffffffd
    and s0, s0, t1
    slli t0, t0, 1
    or s0, s0, t0
    sw s0, 0(s1)
    ori s0, s0, 1
    sw s0, 0(s1)
    li t1, 0xfffffffe
    and s0, s0, t1
    sw s0, 0(s1)
    slli a0, a0, 1
    addi t2, t2, -1
    bnez t2, spi_bit
    ret

delay:
    beqz a0, delay_ret
    addi a0, a0, -1
    j delay
delay_ret:
    ret

init_cmds:
{init_words}
"""

