"""asid_qr: U-mode keystore dump as looping QR v6-M on the SH1107.

Same dump layout as asid_pages (12160 B). Each frame is ASCII:
  H2 + page:02X + n_pages:02X + cksum16:04X + b64(72 B chunk)
so phone/cv2 never see NUL. 169 frames, ~2 s hold, loop forever.

Film a full loop; decode_qr.py → dump JSON. Optional: archive/derive.py for PDDB HKDF.
Restore stock loader.uf2. No live write from this module.
"""

from __future__ import annotations

from constants import IOX_GPIOOUT_PC, PAGE_TABLE_ADDR, TRUSTED_PID
from oled_common import DUMP_BASE, DUMP_BYTES, _copy_calls, _mega, oled_driver_src
from qr_v6 import (
    BYTE_CAP,
    CHUNK,
    DC_LEN,
    EC_LEN,
    N_BLOCKS,
    N_QR,
    QR_ORIGIN,
    SIZE,
    TOTAL_CW,
    n_qr_for,
    table_words,
)

FB_ADDR = 0x61005000
SEG_SRAM = 0x61005840
STATUS_ADDR = 0x61005F00
CKSUM_ADDR = 0x61005F04
STACK_ADDR = 0x61006000
MATRIX = 0x61004000
PAYLOAD = 0x61004700
DC_BUF = 0x61004770
EC_BUF = 0x610047E0
CW_BUF = 0x61004820
CHUNK_BUF = 0x61004900

SATP = (1 << 31) | (TRUSTED_PID << 22) | (PAGE_TABLE_ADDR >> 12)
QR_HOLD = 180_000_000  # ~2 s (asid_pages 40e6 ≈ 0.46 s)


def _word_block(label: str, words: list[int]) -> str:
    lines = [f"{label}:"]
    for i in range(0, len(words), 4):
        chunk = " ".join(f"0x{w:08x}" for w in words[i : i + 4])
        lines.append(f"    .word {chunk}")
    return "\n".join(lines)


def oled_qr_src(
    *,
    dump_bytes: int | None = None,
    dump_base: int | None = None,
    fill_src: str | None = None,
    asid: bool = True,
    px: int = 2,
) -> str:
    dump_bytes = DUMP_BYTES if dump_bytes is None else dump_bytes
    dump_base = DUMP_BASE if dump_base is None else dump_base
    n_qr = n_qr_for(dump_bytes)
    if px < 1 or px > 4:
        raise SystemExit(f"px={px} out of 1..4")
    origin = (128 - SIZE * px) // 2
    if origin < 0:
        raise SystemExit(f"QR {SIZE}×{px}px does not fit 128 OLED")
    fill = fill_src if fill_src is not None else _copy_calls()
    tw = table_words()
    tables = "\n\n".join(
        _word_block(name, tw[name])
        for name in ("gf_exp", "gf_log", "rs_gen", "func_bits", "dark_bits", "b64alpha", "hexdigits")
    )
    cksum_block = f"""
    li a0, 0x{dump_base:x}
    li a1, {dump_bytes // 4}
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
"""
    if asid:
        head = f"""
# asid_qr — dump uuid/cp/root/flag1/n0/chaff/n1, QR v6-M loop
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
qr_loop:
    call draw_qr
    li a0, {QR_HOLD}
    call delay
    addi s10, s10, 1
    li t0, {n_qr}
    bne s10, t0, qr_loop
    li s10, 0
    j qr_loop

s_stub:
    li t1, 0x22222222
    li t2, 0x{STATUS_ADDR:x}
    sw t1, 0(t2)
{fill}
{cksum_block}
    ecall
    j s_done
s_done:
    j s_done

copy_slots:
"""
    else:
        head = f"""
# M-mode QR dump (no ASID). fill_src loads SRAM, then loop.
    fence.i
    li sp, 0x{STACK_ADDR:x}
    call oled_bringup
    li t1, 0x11111111
    li t2, 0x{STATUS_ADDR:x}
    sw t1, 0(t2)
{fill}
{cksum_block}
    li s10, 0
qr_loop:
    call draw_qr
    li a0, {QR_HOLD}
    call delay
    addi s10, s10, 1
    li t0, {n_qr}
    bne s10, t0, qr_loop
    li s10, 0
    j qr_loop

copy_slots:
"""
    return head + f"""
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

# a0=bit. s6 accum, s7 nbits, s8 dest
emit_bit:
    slli s6, s6, 1
    or s6, s6, a0
    addi s7, s7, 1
    li t0, 8
    bne s7, t0, eb_ret
    sb s6, 0(s8)
    addi s8, s8, 1
    addi s6, zero, 0
    addi s7, zero, 0
eb_ret:
    ret

# a0=value a1=nbits (MSB first)
emit_n:
    addi sp, sp, -16
    sw ra, 12(sp)
    sw s9, 8(sp)
    sw a0, 4(sp)
    sw a1, 0(sp)
    mv s9, a1
en_loop:
    beq s9, zero, en_done
    addi s9, s9, -1
    lw t0, 4(sp)
    mv t1, s9
    srl t0, t0, t1
    andi a0, t0, 1
    call emit_bit
    j en_loop
en_done:
    lw ra, 12(sp)
    lw s9, 8(sp)
    addi sp, sp, 16
    ret

gf_mul:
    beqz a0, gm_z
    beqz a1, gm_z
    la t0, gf_log
    add t1, t0, a0
    lbu t1, 0(t1)
    add t2, t0, a1
    lbu t2, 0(t2)
    add t1, t1, t2
    li t2, 255
    bltu t1, t2, gm_e
    addi t1, t1, -255
gm_e:
    la t0, gf_exp
    add t0, t0, t1
    lbu a0, 0(t0)
    ret
gm_z:
    li a0, 0
    ret

# a0=dc[27] a1=ec[16]
rs_encode:
    addi sp, sp, -28
    sw ra, 24(sp)
    sw s2, 20(sp)
    sw s4, 16(sp)
    sw s5, 12(sp)
    sw s6, 8(sp)
    sw s7, 4(sp)
    mv s2, a0
    mv s4, a1
    mv t0, s4
    li t1, 4
rs_z:
    sw zero, 0(t0)
    addi t0, t0, 4
    addi t1, t1, -1
    bnez t1, rs_z
    li s5, 0
rs_i:
    li t0, {DC_LEN}
    beq s5, t0, rs_done
    add t0, s2, s5
    lbu t1, 0(t0)
    lbu t2, 0(s4)
    xor s6, t1, t2
    li t0, 0
rs_sh:
    li t1, 15
    beq t0, t1, rs_shz
    add t2, s4, t0
    lbu t3, 1(t2)
    sb t3, 0(t2)
    addi t0, t0, 1
    j rs_sh
rs_shz:
    sb zero, 15(s4)
    beqz s6, rs_next
    li s7, 0
rs_j:
    li t0, {EC_LEN}
    beq s7, t0, rs_next
    la t0, rs_gen
    add t0, t0, s7
    lbu a0, 0(t0)
    mv a1, s6
    call gf_mul
    add t0, s4, s7
    lbu t1, 0(t0)
    xor t1, t1, a0
    sb t1, 0(t0)
    addi s7, s7, 1
    j rs_j
rs_next:
    addi s5, s5, 1
    j rs_i
rs_done:
    lw ra, 24(sp)
    lw s2, 20(sp)
    lw s4, 16(sp)
    lw s5, 12(sp)
    lw s6, 8(sp)
    lw s7, 4(sp)
    addi sp, sp, 28
    ret

# packed bit: a0=row a1=col a2=base → a0=0/1
pack_bit:
    slli t1, a0, 2
    slli t2, a0, 1
    add t1, t1, t2
    srli t2, a1, 3
    add t1, t1, t2
    add t1, a2, t1
    lbu t1, 0(t1)
    andi t2, a1, 7
    li t3, 1
    sll t3, t3, t2
    and t1, t1, t3
    beqz t1, pb_z
    li a0, 1
    ret
pb_z:
    li a0, 0
    ret

# a0=row a1=col → a0 = MATRIX + row*41 + col
mat_addr:
    slli t0, a0, 5
    slli t1, a0, 3
    add t0, t0, t1
    add t0, t0, a0
    add t0, t0, a1
    li t1, 0x{MATRIX:x}
    add a0, t0, t1
    ret

# map one data module. a0=row a1=col. s2=CW, s4=row, s5=inc, s6=bitIndex, s7=byteIndex
map_one:
    addi sp, sp, -16
    sw ra, 12(sp)
    sw a0, 8(sp)
    sw a1, 4(sp)
    la a2, func_bits
    call pack_bit
    bnez a0, mo_ret
    lw a0, 8(sp)
    lw a1, 4(sp)
    li t0, {TOTAL_CW}
    bge s7, t0, mo_zero
    add t0, s2, s7
    lbu t0, 0(t0)
    mv t1, s6
    srl t0, t0, t1
    andi t0, t0, 1
    j mo_mask
mo_zero:
    addi t0, zero, 0
mo_mask:
    lw t1, 8(sp)
    lw t2, 4(sp)
    add t1, t1, t2
    andi t1, t1, 1
    bnez t1, mo_store
    xori t0, t0, 1
mo_store:
    lw a0, 8(sp)
    lw a1, 4(sp)
    sw t0, 0(sp)
    call mat_addr
    lw t0, 0(sp)
    sb t0, 0(a0)
    addi s6, s6, -1
    bge s6, zero, mo_ret
    addi s7, s7, 1
    li s6, 7
mo_ret:
    lw ra, 12(sp)
    addi sp, sp, 16
    ret

draw_qr:
    addi sp, sp, -16
    sw ra, 12(sp)
    li s1, 0x{IOX_GPIOOUT_PC:x}
    li s3, 0x{FB_ADDR:x}
    lw s0, 0(s1)

    # chunk = dump[page*72:] zero-padded to 72
    li t0, 0x{CHUNK_BUF:x}
    li t1, {CHUNK // 4}
ch_z:
    sw zero, 0(t0)
    addi t0, t0, 4
    addi t1, t1, -1
    bnez t1, ch_z
    # page*72 = page*64 + page*8
    slli t1, s10, 6
    slli t2, s10, 3
    add t1, t1, t2
    li t2, {dump_bytes}
    bgeu t1, t2, chunk_ready
    sub t2, t2, t1
    li t0, {CHUNK}
    bltu t2, t0, ch_len
    li t2, {CHUNK}
ch_len:
    li t3, 0x{dump_base:x}
    add t3, t3, t1
    li t4, 0x{CHUNK_BUF:x}
ch_cp:
    beq t2, zero, chunk_ready
    lbu t0, 0(t3)
    sb t0, 0(t4)
    addi t3, t3, 1
    addi t4, t4, 1
    addi t2, t2, -1
    j ch_cp
chunk_ready:

    # payload: H2 + hex(page) + hex(n_qr) + hex(cksum16) + b64(chunk)
    li s4, 0x{PAYLOAD:x}
    li t0, 0x32
    slli t0, t0, 8
    addi t0, t0, 0x48
    sh t0, 0(s4)
    addi s4, s4, 2
    mv a0, s10
    call emit_hex2
    li a0, {n_qr}
    call emit_hex2
    li t0, 0x{CKSUM_ADDR:x}
    lhu a0, 0(t0)
    call emit_hex4
    li s2, 0x{CHUNK_BUF:x}
    li s5, 0
b64_g:
    li t0, 24
    beq s5, t0, b64_done
    lbu t1, 0(s2)
    lbu t2, 1(s2)
    lbu t3, 2(s2)
    srli a0, t1, 2
    call b64_emit
    andi t0, t1, 3
    slli t0, t0, 4
    srli t4, t2, 4
    or a0, t0, t4
    call b64_emit
    andi t0, t2, 15
    slli t0, t0, 2
    srli t4, t3, 6
    or a0, t0, t4
    call b64_emit
    andi a0, t3, 63
    call b64_emit
    addi s2, s2, 3
    addi s5, s5, 1
    j b64_g
b64_done:

    # bit-pack payload → DC[108]
    addi s6, zero, 0
    addi s7, zero, 0
    li s8, 0x{DC_BUF:x}
    li a0, 4
    li a1, 4
    call emit_n
    li a0, {BYTE_CAP}
    li a1, 8
    call emit_n
    li s2, 0x{PAYLOAD:x}
    li s5, 0
pk_b:
    li t0, {BYTE_CAP}
    beq s5, t0, pk_term
    add t0, s2, s5
    lbu a0, 0(t0)
    li a1, 8
    call emit_n
    addi s5, s5, 1
    j pk_b
pk_term:
    li a0, 0
    li a1, 4
    call emit_n

    # RS 4 blocks + interleave
    li s5, 0
rs_blk:
    li t0, {N_BLOCKS}
    beq s5, t0, rs_all
    slli t2, s5, 4
    slli t3, s5, 3
    add t2, t2, t3
    slli t3, s5, 1
    add t2, t2, t3
    add t2, t2, s5
    li a0, 0x{DC_BUF:x}
    add a0, a0, t2
    slli t2, s5, 4
    li a1, 0x{EC_BUF:x}
    add a1, a1, t2
    call rs_encode
    addi s5, s5, 1
    j rs_blk
rs_all:
    li s2, 0x{CW_BUF:x}
    li s5, 0
il_i:
    li t0, {DC_LEN}
    beq s5, t0, il_ec
    li s4, 0
il_b:
    li t0, {N_BLOCKS}
    beq s4, t0, il_n
    slli t2, s4, 4
    slli t3, s4, 3
    add t2, t2, t3
    slli t3, s4, 1
    add t2, t2, t3
    add t2, t2, s4
    add t2, t2, s5
    li t3, 0x{DC_BUF:x}
    add t3, t3, t2
    lbu t3, 0(t3)
    sb t3, 0(s2)
    addi s2, s2, 1
    addi s4, s4, 1
    j il_b
il_n:
    addi s5, s5, 1
    j il_i
il_ec:
    li s5, 0
il_ei:
    li t0, {EC_LEN}
    beq s5, t0, il_done
    li s4, 0
il_eb:
    li t0, {N_BLOCKS}
    beq s4, t0, il_en
    slli t2, s4, 4
    add t2, t2, s5
    li t3, 0x{EC_BUF:x}
    add t3, t3, t2
    lbu t3, 0(t3)
    sb t3, 0(s2)
    addi s2, s2, 1
    addi s4, s4, 1
    j il_eb
il_en:
    addi s5, s5, 1
    j il_ei
il_done:

    # init matrix from dark template
    li s4, 0
im_y:
    li t0, {SIZE}
    beq s4, t0, im_done
    li s5, 0
im_x:
    li t0, {SIZE}
    beq s5, t0, im_yn
    mv a0, s4
    mv a1, s5
    la a2, dark_bits
    call pack_bit
    mv t3, a0
    mv a0, s4
    mv a1, s5
    call mat_addr
    sb t3, 0(a0)
    addi s5, s5, 1
    j im_x
im_yn:
    addi s4, s4, 1
    j im_y
im_done:

    # zigzag map_data
    li s2, 0x{CW_BUF:x}
    li s4, {SIZE - 1}
    li s5, -1
    li s6, 7
    li s7, 0
    li s8, {SIZE - 1}
md_col:
    li t0, 1
    blt s8, t0, md_done
    mv s9, s8
    li t0, 7
    bge s9, t0, md_ok
    addi s9, s9, -1
md_ok:
md_row:
    mv a0, s4
    mv a1, s9
    call map_one
    mv a0, s4
    addi a1, s9, -1
    call map_one
    add s4, s4, s5
    blt s4, zero, md_flip
    li t0, {SIZE}
    bge s4, t0, md_flip
    j md_row
md_flip:
    sub s4, s4, s5
    sub s5, zero, s5
    addi s8, s8, -2
    j md_col
md_done:

    # white background + black modules at {px}× (OLED bezel = quiet zone)
    call fb_fill_ones
{"" if origin < 16 else f'''
    call load_seg7
    mv a0, s10
    srli a0, a0, 4
    andi a0, a0, 0xf
    li a1, 4
    li a2, 1
    call blit_7seg
    mv a0, s10
    andi a0, a0, 0xf
    li a1, 12
    li a2, 1
    call blit_7seg
'''}
    li s4, 0
bl_y:
    li t0, {SIZE}
    beq s4, t0, bl_done
    li s5, 0
bl_x:
    li t0, {SIZE}
    beq s5, t0, bl_yn
    mv a0, s4
    mv a1, s5
    call mat_addr
    lbu t0, 0(a0)
    beqz t0, bl_n
    # ox = origin + x*px, oy = origin + y*px
    mv t6, s5
    li a0, {origin}
    li t4, {px}
bl_sx:
    beq t4, zero, bl_sxd
    add a0, a0, t6
    addi t4, t4, -1
    j bl_sx
bl_sxd:
    sw a0, 8(sp)
    mv t6, s4
    li a0, {origin}
    li t4, {px}
bl_sy:
    beq t4, zero, bl_syd
    add a0, a0, t6
    addi t4, t4, -1
    j bl_sy
bl_syd:
    sw a0, 4(sp)
    li t5, 0
bl_dy:
    li t0, {px}
    beq t5, t0, bl_n
    li t6, 0
bl_dx:
    li t0, {px}
    beq t6, t0, bl_dyd
    lw a0, 8(sp)
    add a0, a0, t6
    lw a1, 4(sp)
    add a1, a1, t5
    call clr_pixel
    addi t6, t6, 1
    j bl_dx
bl_dyd:
    addi t5, t5, 1
    j bl_dy
bl_n:
    addi s5, s5, 1
    j bl_x
bl_yn:
    addi s4, s4, 1
    j bl_y
bl_done:
    call oled_flush
    lw ra, 12(sp)
    addi sp, sp, 16
    ret

# emit 2 hex chars of a0 (low 8 bits) to s4, advance s4
emit_hex2:
    addi sp, sp, -8
    sw ra, 4(sp)
    sw a0, 0(sp)
    srli a0, a0, 4
    andi a0, a0, 0xf
    call hex_digit
    sb a0, 0(s4)
    lw a0, 0(sp)
    andi a0, a0, 0xf
    call hex_digit
    sb a0, 1(s4)
    addi s4, s4, 2
    lw ra, 4(sp)
    addi sp, sp, 8
    ret

emit_hex4:
    addi sp, sp, -8
    sw ra, 4(sp)
    sw a0, 0(sp)
    srli a0, a0, 8
    call emit_hex2
    lw a0, 0(sp)
    call emit_hex2
    lw ra, 4(sp)
    addi sp, sp, 8
    ret

hex_digit:
    la t0, hexdigits
    add t0, t0, a0
    lbu a0, 0(t0)
    ret

# a0 = 0..63 → ascii via b64alpha, store at s4++
b64_emit:
    la t0, b64alpha
    add t0, t0, a0
    lbu t0, 0(t0)
    sb t0, 0(s4)
    addi s4, s4, 1
    ret

{tables}
""" + oled_driver_src(fb_addr=FB_ADDR, seg_sram=SEG_SRAM)


def qr_layout_note() -> str:
    return (
        f"QR v6-M mask0, {N_QR} frames × {CHUNK}B dump, ASCII H2+hex+b64. "
        "Film full loop. decode_qr.py → verify flag1 SHA. Restore loader.uf2."
    )
