"""Layout constants for the unsigned loader-header hop (amattas / Only 132 Bytes).

Offline builder only. Do not flash without an explicit operator go.
"""

from __future__ import annotations

# UF2 / silicon
BAOCHIP_1X_UF2_FAMILY = 0xA7D7_6373
HW_RERAM_MEM = 0x6000_0000
HW_SRAM_MEM = 0x6100_0000
HW_DUART_BASE = 0x4004_2000

LOADER_START = 0x6006_0000
KERNEL_START = 0x600A_0000 - 768  # SIGBLOCK_LEN
SIGBLOCK_LEN = 768
UNSIGNED_LEN = 4 + 64 + 4 + 60  # jal + ed25519 sig + aad_len + aad
AAD_LEN_FIDO2 = 37
AAD_OFF = 4 + 64 + 4  # 0x48
AAD_TAIL_OFF = AAD_OFF + AAD_LEN_FIDO2  # 0x6D
SPRING_OFF = 0x70  # unauthenticated AAD tail
LOADER_ENTRY = LOADER_START + SIGBLOCK_LEN  # stock jal target 0x60060300

# Amattas hop-3 parking (after signed loader body, before kernel sigblock)
STAGE2_ADDR = 0x6008_C000
STAGE2_CEILING = KERNEL_START  # 0x6009FD00

# RRAM data slots
DATA_SLOT_START = 0x603E_0000
SLOT_BYTES = 32
SLOT_ROOT = 256
SLOT_FLAG1 = 260
SLOT_UUID = 1
SLOT_CP_ID = 3
SLOT_NUISANCE0 = range(8, 128)  # 120
SLOT_CHAFF = range(128, 256)  # 128
SLOT_NUISANCE1 = range(1920, 2048)  # 128
# asid_pages dump: uuid+cp+root+flag1+n0+chaff+n1 = 12160 B (190×64)

ONEWAY_START = 0x603D_A000
OWC_STRIDE = 32
OWC_DEVELOPER_MODE = 85
OWC_OEM_MODE = 86
OWC_BOOT0_PUBKEY_FAIL = 87

# Coreuser / paging
TRUSTED_PID = 3  # keystore ASID → Fw0
SATP_MODE_SV32 = 1
PAGE_TABLE_ADDR = HW_SRAM_MEM  # 4K-aligned root
SCRATCH_ADDR = HW_SRAM_MEM + 0x1000
DUMP_ROOT = SCRATCH_ADDR
DUMP_FLAG1 = SCRATCH_ADDR + 32
FB_ADDR = SCRATCH_ADDR + 0x40  # 2048B SH1107 framebuffer
STATUS_ADDR = HW_SRAM_MEM + 0x1F00  # copy-phase sentinel (not in dump/FB)
STACK_ADDR = HW_SRAM_MEM + 0x3000

# baosec OLED bit-bang (PC0=CLK, PC1=MOSI, PC2=CD, PC3=CS, PC4=PWR, PC6=RST)
IOX_BASE = 0x5012_F000
IOX_AFSEL4 = IOX_BASE + 0x10  # PC pins 0–7 AF, 2 bits/pin
IOX_GPIOOUT_PC = IOX_BASE + (76 + 2) * 4  # CRGO0 + IoxPort::PC
IOX_GPIOOE_PC = IOX_BASE + (82 + 2) * 4
PIN_CLK, PIN_DAT, PIN_CD, PIN_CS, PIN_PWR, PIN_RST = 0, 1, 2, 3, 4, 6

# Published digests for verify (flag1 is public; PDDB master is a device-local check)
SHA256_FLAG1 = "8e817665bab84a5131b08b9c7f2be4773d45ee86eaed25389212c9183c4c057a"
SHA256_PDDB_MASTER = "2f995eb865427ba2f4f363a76d5165fc0e03c271616b6b96a7926109e2c1aed7"
K0_HASH_PREFIX = "dca9ea49"
KP_PUBLIC = bytes.fromhex("7ad84ed0e00aec0499ede65615e1da51")

# Stock hop encodings (little-endian u32 views)
STOCK_JAL = 0x3000_006F  # jal x0, +0x300
HOP_JAL = 0x0700_006F  # jal x0, +0x70
SPRINGBOARD = bytes.fromhex("b7c2086067800200000000000000000000000000")  # lui t0,0x6008C; jalr x0,0(t0)

# Local-only path (captures/ is gitignored). Prefer --loader /path/to/ship/loader.uf2.
DEFAULT_LOADER = "captures/firmware/34b/loader.uf2"

# SPI / PDDB (baosec-lite 2.5 MiB vs full 4 MiB page-table sizes)
PDDB_ORIGIN = 0x0040_0000
SCD_SPI_LITE = 0x0040_3000  # sizeof(PT)=10240 → page-align 0x3000
SCD_SPI_FULL = 0x0040_4000  # sizeof(PT)=16384
SCD_PAGE = 4096
SCD_DUMP_BYTES = SCD_PAGE * 2  # both candidate SCD pages
SPIM_CSR = 0x5010_6000  # UDMA SPIM channel 1 (SPI_MEM_CHANNEL)
SPIM_IFRAM = 0x5001_9000  # SPIM_FLASH_IFRAM_ADDR
SPIM_TX_LEN = 256 + 16
SPIM_RX_LEN = 4096
WRAPPED_AES_KEYSIZE = 32 + 8
SCD_VERSION = 2
