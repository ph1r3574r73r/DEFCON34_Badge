#include <stdint.h>

#include "bio.h" // must be first — places _start at 0x0

/*
 * Sealed-safe BIO memprobe (no GPIO — avoids SAO/key noise during FIFO report)
 *
 * Protocol (u32 words on FIFO3; host: `bio rx`):
 *   0x4D455001          START
 *   0x43414E00          CANARY
 *     addr, wrote, read
 *   0x57525200 | id     WR probe
 *     base, wrote, read
 *   0x53434E00 | id     SCAN
 *     base, nwords, zeros, nonzeros,
 *     first_nz_addr, first_nz_val, last_nz_addr, last_nz_val, hash_hits
 *   0x4D45444E          DONE
 * then idle (halt on quantum)
 */

#define TAG_START  0x4D455001u
#define TAG_CANARY 0x43414E00u
#define TAG_WR     0x57525200u
#define TAG_SCAN   0x53434E00u
#define TAG_DONE   0x4D45444Eu
#define HASH_WORD  0xDCA9EA49u
#define SCAN_WORDS 4096u

static void report_u32(uint32_t v)
{
    push_fifo3(v);
}

static void wr_probe(uint32_t id, uint32_t addr, uint32_t magic)
{
    volatile uint32_t *p = (volatile uint32_t *)addr;
    report_u32(TAG_WR | id);
    report_u32(addr);
    report_u32(magic);
    *p = magic;
    report_u32(*p);
}

static void scan_range(uint32_t id, uint32_t base, uint32_t nwords)
{
    volatile uint32_t *p = (volatile uint32_t *)base;
    uint32_t zeros = 0;
    uint32_t nonzeros = 0;
    uint32_t hash_hits = 0;
    uint32_t first_a = 0;
    uint32_t first_v = 0;
    uint32_t last_a = 0;
    uint32_t last_v = 0;
    uint32_t have_first = 0;
    uint32_t i;

    report_u32(TAG_SCAN | id);
    report_u32(base);
    report_u32(nwords);

    for (i = 0; i < nwords; i++) {
        uint32_t v = p[i];
        uint32_t a = base + (i << 2);
        if (v == 0) {
            zeros++;
        } else {
            nonzeros++;
            if (have_first == 0) {
                first_a = a;
                first_v = v;
                have_first = 1;
            }
            last_a = a;
            last_v = v;
            if (v == HASH_WORD) {
                hash_hits++;
            }
        }
    }

    report_u32(zeros);
    report_u32(nonzeros);
    report_u32(first_a);
    report_u32(first_v);
    report_u32(last_a);
    report_u32(last_v);
    report_u32(hash_hits);
}

void main(void)
{
    volatile uint32_t *canary = (volatile uint32_t *)0x00000800u;

    report_u32(TAG_START);

    report_u32(TAG_CANARY);
    report_u32(0x00000800u);
    report_u32(0xC4A1F00Du);
    *canary = 0xC4A1F00Du;
    report_u32(*canary);

    wr_probe(1, 0x10000000u, 0xBEEF0001u);
    wr_probe(2, 0x61000100u, 0xBEEF0002u);
    wr_probe(3, 0x50019000u, 0xBEEF0003u);

    scan_range(1, 0x10000000u, SCAN_WORDS);
    scan_range(2, 0x61000000u, SCAN_WORDS);
    scan_range(3, 0x50000000u, 256u);

    report_u32(TAG_DONE);

    while (1) {
        wait_quantum();
    }
}
