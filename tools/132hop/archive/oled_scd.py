"""asid_scd: M-mode SPI dump of PDDB SCD pages → QR v6-M loop.

Dumps 8 KB: baosec-lite SCD @ 0x403000 then full-PT SCD @ 0x404000.
Boot1 already inits UDMA SPIM ch1 + QPI before `boot`; hop reuses it.
No ASID / no RRAM ACL. Film loop → decode_qr.py --layout scd → archive/unwrap.py.
Restore stock loader.uf2. No live write from this module.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from constants import (  # noqa: E402
    SCD_DUMP_BYTES,
    SCD_PAGE,
    SCD_SPI_FULL,
    SCD_SPI_LITE,
    SPIM_CSR,
    SPIM_IFRAM,
    SPIM_RX_LEN,
    SPIM_TX_LEN,
)
from oled_common import DUMP_BASE  # noqa: E402
from oled_qr import oled_qr_src  # noqa: E402
from qr_v6 import n_qr_for  # noqa: E402

# UDMA bank offsets (bytes) from SPIM CSR
_TX_SADDR = 0x10
_TX_SIZE = 0x14
_TX_CFG = 0x18
_RX_SADDR = 0x00
_RX_SIZE = 0x04
_RX_CFG = 0x08
_CMD_SADDR = 0x20
_CMD_SIZE = 0x24
_CMD_CFG = 0x28
_CFG8 = 0x90  # EN | SIZE_8 | BACKPRESSURE (enqueue ORs BP)
_CFG32 = 0x94  # EN | SIZE_32 | BACKPRESSURE

# Quad mem_read cmds (dummy_cycles=6, 24-bit addr)
_CMD_CS_ON = 0x10000000  # StartXfer(Cs0)
_CMD_CS_OFF = 0x90000000  # EndXfer(Disabled)
_CMD_EB = 0x280700EB  # SendCmd(Quad, 8, 0xEB)
_CMD_TX6 = 0x68070005  # TxData(Quad, 1, 8, MSB, 6)
# RxData(Quad, 1, 8, MSB, 4096) → len-1 = 0xFFF
_CMD_RX4K = 0x78070FFF

_TX_BUF = SPIM_IFRAM
_RX_BUF = SPIM_IFRAM + SPIM_TX_LEN
_CMD_BUF = SPIM_IFRAM + SPIM_TX_LEN + SPIM_RX_LEN
_RX_TIMEOUT = SCD_PAGE * 10_000


def _spi_fill_src() -> str:
    return f"""
    # dump lite SCD then full SCD (4 KB each) into dump_base
    li a0, 0x{SCD_SPI_LITE:x}
    li a1, 0x{DUMP_BASE:x}
    li a2, {SCD_PAGE}
    call spi_read
    li a0, 0x{SCD_SPI_FULL:x}
    li a1, 0x{DUMP_BASE + SCD_PAGE:x}
    li a2, {SCD_PAGE}
    call spi_read
    j spi_fill_done

# a0=24-bit SPI addr  a1=dest  a2=len (<=4096)
spi_read:
    addi sp, sp, -16
    sw ra, 12(sp)
    sw s0, 8(sp)
    sw s1, 4(sp)
    sw s2, 0(sp)
    mv s0, a0
    mv s1, a1
    mv s2, a2
    # tx_buf: addr[23:0] BE + 3 dummy FF
    li t0, 0x{_TX_BUF:x}
    srli t1, s0, 16
    andi t1, t1, 0xff
    sb t1, 0(t0)
    srli t1, s0, 8
    andi t1, t1, 0xff
    sb t1, 1(t0)
    andi t1, s0, 0xff
    sb t1, 2(t0)
    li t1, 0xff
    sb t1, 3(t0)
    sb t1, 4(t0)
    sb t1, 5(t0)
    # CS on
    li a0, 0x{_CMD_CS_ON:x}
    call spi_cmd1
    # enqueue TX 6 bytes
    li t3, 0x{SPIM_CSR:x}
    li t0, 0x{_TX_BUF:x}
    sw t0, {_TX_SADDR}(t3)
    li t0, 6
    sw t0, {_TX_SIZE}(t3)
    li t0, {_CFG8}
    sw t0, {_TX_CFG}(t3)
    # SendCmd 0xEB + TxData 6
    li a0, 0x{_CMD_EB:x}
    li a1, 0x{_CMD_TX6:x}
    call spi_cmd2
    call spi_wait_tx
    # enqueue RX s2 bytes into rx_buf
    li t3, 0x{SPIM_CSR:x}
    li t0, 0x{_RX_BUF:x}
    sw t0, {_RX_SADDR}(t3)
    sw s2, {_RX_SIZE}(t3)
    li t0, {_CFG8}
    sw t0, {_RX_CFG}(t3)
    # RxData(len) — encode len-1 into low 16 of 0x78070000
    li a0, 0x78070000
    addi t0, s2, -1
    or a0, a0, t0
    call spi_cmd1
    call spi_wait_rx
    # CS off
    li a0, 0x{_CMD_CS_OFF:x}
    call spi_cmd1
    # copy rx_buf → dest
    li t0, 0x{_RX_BUF:x}
    mv t1, s1
    mv t2, s2
spi_cpy:
    beq t2, zero, spi_ret
    lbu t3, 0(t0)
    sb t3, 0(t1)
    addi t0, t0, 1
    addi t1, t1, 1
    addi t2, t2, -1
    j spi_cpy
spi_ret:
    lw ra, 12(sp)
    lw s0, 8(sp)
    lw s1, 4(sp)
    lw s2, 0(sp)
    addi sp, sp, 16
    ret

# a0 = cmd word → Custom bank, wait idle
spi_cmd1:
    addi sp, sp, -8
    sw ra, 4(sp)
    li t0, 0x{_CMD_BUF:x}
    sw a0, 0(t0)
    li t3, 0x{SPIM_CSR:x}
    sw t0, {_CMD_SADDR}(t3)
    li t0, 4
    sw t0, {_CMD_SIZE}(t3)
    li t0, {_CFG32}
    sw t0, {_CMD_CFG}(t3)
    call spi_wait_cmd
    lw ra, 4(sp)
    addi sp, sp, 8
    ret

# a0, a1 = two cmd words
spi_cmd2:
    addi sp, sp, -8
    sw ra, 4(sp)
    li t0, 0x{_CMD_BUF:x}
    sw a0, 0(t0)
    sw a1, 4(t0)
    li t3, 0x{SPIM_CSR:x}
    sw t0, {_CMD_SADDR}(t3)
    li t0, 8
    sw t0, {_CMD_SIZE}(t3)
    li t0, {_CFG32}
    sw t0, {_CMD_CFG}(t3)
    call spi_wait_cmd
    lw ra, 4(sp)
    addi sp, sp, 8
    ret

spi_wait_cmd:
    li t3, 0x{SPIM_CSR:x}
swc:
    lw t0, {_CMD_SADDR}(t3)
    bnez t0, swc
    ret

spi_wait_tx:
    li t3, 0x{SPIM_CSR:x}
swt:
    lw t0, {_TX_SADDR}(t3)
    bnez t0, swt
    ret

spi_wait_rx:
    li t3, 0x{SPIM_CSR:x}
    li t1, {_RX_TIMEOUT}
swr:
    lw t0, {_RX_SADDR}(t3)
    beq t0, zero, swr_ok
    addi t1, t1, -1
    bnez t1, swr
swr_ok:
    ret

spi_fill_done:
"""


def oled_scd_src() -> str:
    assert SCD_DUMP_BYTES % 4 == 0
    n_qr_for(SCD_DUMP_BYTES)
    return oled_qr_src(
        dump_bytes=SCD_DUMP_BYTES,
        dump_base=DUMP_BASE,
        fill_src=_spi_fill_src(),
        asid=False,
        px=3,
    )


def scd_layout_note() -> str:
    n = n_qr_for(SCD_DUMP_BYTES)
    return (
        f"SCD QR v6-M 3px (123×123), {n} frames × 72 B, SPI "
        f"0x{SCD_SPI_LITE:x}+0x{SCD_SPI_FULL:x}. "
        "decode_qr.py --layout scd → archive/unwrap.py. Restore loader.uf2."
    )
