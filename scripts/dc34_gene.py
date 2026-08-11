#!/usr/bin/env python3
"""Port of dc34-api light-gene types: Haploid, Diploid, meiosis, mutate.

Faithful to repos/dc34-api/src/lib.rs + vault get_padded_gamete (config.rs):
  padded gamete[16] = haploid.serialize()[:9] + zero pad + badge_type at [15]

RNG matches firmware intent (thread_rng / gen_range / roll) via secrets.SystemRandom
unless an explicit random.Random is passed (for reproducible tests).
"""

from __future__ import annotations

import argparse
import json
import random
from dataclasses import dataclass, fields
from enum import IntEnum
from typing import Optional, Sequence

HAPLOID_SIZE = 9  # sizeof(Haploid) in Rust #[repr(C)]


class BadgeType(IntEnum):
    UBER = 0
    OTHER = 1
    COMMUNITY = 2
    VILLAGE = 3
    CTF = 4
    HUMAN = 5
    GOON = 6
    NONE = 7


BADGE_ALIASES = {
    "uber": BadgeType.UBER,
    "other": BadgeType.OTHER,
    "community": BadgeType.COMMUNITY,
    "village": BadgeType.VILLAGE,
    "ctf": BadgeType.CTF,
    "ctfcontest": BadgeType.CTF,
    "human": BadgeType.HUMAN,
    "goon": BadgeType.GOON,
    "none": BadgeType.NONE,
}


class MutationRate(IntEnum):
    NONE = 0
    BASELINE = 64
    ELEVATED = 100
    RADIOACTIVE = 140
    APOCALYPTIC = 240


MUTATION_ALIASES = {
    "none": MutationRate.NONE,
    "baseline": MutationRate.BASELINE,
    "elevated": MutationRate.ELEVATED,
    "radioactive": MutationRate.RADIOACTIVE,
    "apocalyptic": MutationRate.APOCALYPTIC,
}

_BIT_CHANGES = {
    MutationRate.NONE: 0,
    MutationRate.BASELINE: 1,
    MutationRate.ELEVATED: 3,
    MutationRate.RADIOACTIVE: 7,
    MutationRate.APOCALYPTIC: 0x1F,
}


def parse_badge(name: str) -> BadgeType:
    key = name.strip().lower().replace("-", "").replace("_", "")
    if key in BADGE_ALIASES:
        return BADGE_ALIASES[key]
    raise SystemExit(f"unknown badge type {name!r}; choose from {sorted(BADGE_ALIASES)}")


def parse_rate(name: str) -> MutationRate:
    key = name.strip().lower()
    if key in MUTATION_ALIASES:
        return MUTATION_ALIASES[key]
    raise SystemExit(f"unknown mutation rate {name!r}; choose from {sorted(MUTATION_ALIASES)}")


def _rng(rng: Optional[random.Random]) -> random.Random:
    return rng if rng is not None else random.SystemRandom()


def _randint(rng: random.Random, lo: int, hi: int) -> int:
    """Inclusive range, matching Rust gen_range(lo..=hi) / gen_range(RangeInclusive)."""
    return rng.randint(lo, hi)


def _rand_u8(rng: random.Random) -> int:
    return rng.randint(0, 255)


def _choice2(rng: random.Random) -> int:
    return rng.randrange(0, 2)


# --- BadgeType ranges (dc34-api) -------------------------------------------------


def hue_range(bt: BadgeType) -> tuple[int, int]:
    return {
        BadgeType.GOON: (0, 20),
        BadgeType.COMMUNITY: (32, 80),
        BadgeType.VILLAGE: (80, 128),
        BadgeType.HUMAN: (128, 160),
        BadgeType.OTHER: (160, 192),
        BadgeType.CTF: (192, 220),
        BadgeType.UBER: (220, 255),
        BadgeType.NONE: (128, 160),
    }[bt]


def sat_range(bt: BadgeType) -> tuple[int, int]:
    return {
        BadgeType.GOON: (160, 255),
        BadgeType.COMMUNITY: (32, 160),
        BadgeType.VILLAGE: (32, 160),
        BadgeType.HUMAN: (32, 255),
        BadgeType.OTHER: (16, 255),
        BadgeType.CTF: (16, 255),
        BadgeType.UBER: (130, 255),
        BadgeType.NONE: (32, 255),
    }[bt]


def chaser_range(bt: BadgeType) -> tuple[int, int]:
    return {
        BadgeType.GOON: (90, 255),
        BadgeType.COMMUNITY: (90, 255),
        BadgeType.VILLAGE: (90, 255),
        BadgeType.HUMAN: (90, 255),
        BadgeType.OTHER: (0, 255),
        BadgeType.CTF: (90, 255),
        BadgeType.UBER: (0, 45),
        BadgeType.NONE: (90, 255),
    }[bt]


def nonlin_range(bt: BadgeType) -> tuple[int, int]:
    return {
        BadgeType.GOON: (0, 255),
        BadgeType.COMMUNITY: (0, 255),
        BadgeType.VILLAGE: (0, 255),
        BadgeType.HUMAN: (0, 255),
        BadgeType.OTHER: (0, 90),
        BadgeType.CTF: (0, 90),
        BadgeType.UBER: (0, 44),
        BadgeType.NONE: (0, 255),
    }[bt]


def cd_dir_range(bt: BadgeType) -> tuple[int, int]:
    return {
        BadgeType.GOON: (0, 255),
        BadgeType.COMMUNITY: (0, 255),
        BadgeType.VILLAGE: (0, 45),
        BadgeType.HUMAN: (0, 255),
        BadgeType.OTHER: (0, 255),
        BadgeType.CTF: (0, 255),
        BadgeType.UBER: (0, 45),
        BadgeType.NONE: (0, 255),
    }[bt]


def cd_period_max(bt: BadgeType) -> int:
    return {
        BadgeType.GOON: 4,
        BadgeType.COMMUNITY: 2,
        BadgeType.VILLAGE: 4,
        BadgeType.HUMAN: 5,
        BadgeType.OTHER: 6,
        BadgeType.CTF: 6,
        BadgeType.UBER: 3,
        BadgeType.NONE: 4,
    }[bt]


# --- Haploid / Diploid -----------------------------------------------------------


@dataclass
class Haploid:
    cd_period: int = 0
    cd_rate: int = 0
    cd_dir: int = 0
    sat: int = 0
    hue_ratedir: int = 0
    hue_base: int = 0
    hue_bound: int = 0
    chaser: int = 0
    nonlin: int = 0

    def serialize(self) -> bytes:
        return bytes(
            [
                self.cd_period & 0xFF,
                self.cd_rate & 0xFF,
                self.cd_dir & 0xFF,
                self.sat & 0xFF,
                self.hue_ratedir & 0xFF,
                self.hue_base & 0xFF,
                self.hue_bound & 0xFF,
                self.chaser & 0xFF,
                self.nonlin & 0xFF,
            ]
        )

    @classmethod
    def deserialize(cls, data: bytes | Sequence[int]) -> Optional["Haploid"]:
        if len(data) < HAPLOID_SIZE:
            return None
        b = bytes(data[:HAPLOID_SIZE])
        return cls(*b)

    @classmethod
    def from_rand(cls, rng: Optional[random.Random] = None) -> "Haploid":
        r = _rng(rng)
        return cls(
            cd_period=_randint(r, 0, 6),
            cd_rate=_rand_u8(r),
            cd_dir=_rand_u8(r),
            sat=_rand_u8(r),
            hue_ratedir=_rand_u8(r),
            hue_base=_rand_u8(r),
            hue_bound=_rand_u8(r),
            chaser=_rand_u8(r),
            nonlin=_rand_u8(r),
        )

    @classmethod
    def from_type(cls, badge_type: BadgeType, rng: Optional[random.Random] = None) -> "Haploid":
        r = _rng(rng)
        h = cls()
        h.cd_period = _randint(r, 0, cd_period_max(badge_type))
        h.cd_rate = _rand_u8(r)
        lo, hi = cd_dir_range(badge_type)
        h.cd_dir = _randint(r, lo, hi)
        lo, hi = sat_range(badge_type)
        h.sat = _randint(r, lo, hi)
        h.hue_ratedir = _rand_u8(r)
        lo, hi = hue_range(badge_type)
        h.hue_base = _randint(r, lo, hi)
        if badge_type == BadgeType.GOON:
            h.hue_base = 0
        h.hue_bound = _randint(r, h.hue_base, hi)
        if badge_type == BadgeType.UBER:
            h.hue_bound = 255
        lo, hi = chaser_range(badge_type)
        h.chaser = _randint(r, lo, hi)
        lo, hi = nonlin_range(badge_type)
        h.nonlin = _randint(r, lo, hi)
        return h

    def as_dict(self) -> dict:
        return {f.name: getattr(self, f.name) for f in fields(self)}


@dataclass
class Diploid:
    a: Haploid
    b: Haploid

    @classmethod
    def from_type(cls, badge_type: BadgeType, rng: Optional[random.Random] = None) -> "Diploid":
        r = _rng(rng)
        return cls(Haploid.from_type(badge_type, r), Haploid.from_type(badge_type, r))

    @classmethod
    def from_rand(cls, rng: Optional[random.Random] = None) -> "Diploid":
        r = _rng(rng)
        return cls(Haploid.from_rand(r), Haploid.from_rand(r))

    def serialize(self) -> bytes:
        return self.a.serialize() + self.b.serialize()

    @classmethod
    def deserialize(cls, data: bytes | Sequence[int]) -> Optional["Diploid"]:
        if len(data) < HAPLOID_SIZE * 2:
            return None
        a = Haploid.deserialize(data[:HAPLOID_SIZE])
        b = Haploid.deserialize(data[HAPLOID_SIZE : HAPLOID_SIZE * 2])
        if a is None or b is None:
            return None
        return cls(a, b)

    def phenotype(self) -> Haploid:
        # saturating_add for u8 == min(a+b, 255)
        e = Haploid(
            cd_period=min((self.a.cd_period + self.b.cd_period) // 2, 6),
            cd_rate=((self.a.cd_rate + self.b.cd_rate) // 2) & 0xFF,
            cd_dir=min(self.a.cd_dir + self.b.cd_dir, 255),
            sat=min(self.a.sat + self.b.sat, 255),
            hue_ratedir=(2 + (14 - min(self.a.hue_ratedir + self.b.hue_ratedir, 14))) % 14,
            hue_base=min(self.a.hue_base, self.b.hue_base),
            hue_bound=max(self.a.hue_bound, self.b.hue_bound),
            chaser=min(self.a.chaser + self.b.chaser, 255),
            # firmware mirrors: nonlin uses a.chaser + b.nonlin (not a.nonlin)
            nonlin=min(self.a.chaser + self.b.nonlin, 255),
        )
        e.hue_bound = max(e.hue_bound, e.hue_base)
        return e

    def meiosis(self, rng: Optional[random.Random] = None) -> Haploid:
        r = _rng(rng)
        g = Haploid()
        parent = _choice2(r)
        strands = (self.a, self.b)
        g.cd_period = strands[parent].cd_period
        g.cd_rate = strands[parent].cd_rate
        g.cd_dir = strands[parent].cd_dir
        g.sat = strands[_choice2(r)].sat
        parent = _choice2(r)
        g.hue_ratedir = strands[parent].hue_ratedir
        g.hue_base = strands[parent].hue_base
        g.hue_bound = strands[parent].hue_bound
        g.chaser = strands[_choice2(r)].chaser
        g.nonlin = strands[_choice2(r)].nonlin
        return g


def gray_encode(n: int) -> int:
    n &= 0xFF
    return n ^ (n >> 1)


def gray_decode(n: int) -> int:
    n &= 0xFF
    p = n
    while (n >> 1) != 0:
        n >>= 1
        p ^= n
    return p & 0xFF


def mutation_func(gene: int, bits: int, rng: random.Random) -> int:
    shift = rng.randint(0, 7)
    return gray_decode(gray_encode(gene) ^ ((bits << shift) & 0xFF))


def rate_roll(rate: MutationRate, rng: random.Random) -> bool:
    if rate == MutationRate.NONE:
        return False
    return rng.randint(0, 255) < int(rate)


def mutate(gamete: Haploid, rate: MutationRate, rng: Optional[random.Random] = None) -> None:
    r = _rng(rng)
    bits = _BIT_CHANGES[rate]
    if rate_roll(rate, r):
        gamete.cd_period = mutation_func(gamete.cd_period, bits, r) % 7
    if rate_roll(rate, r):
        gamete.cd_rate = mutation_func(gamete.cd_rate, bits, r)
    if rate_roll(rate, r):
        gamete.cd_dir = mutation_func(gamete.cd_dir, bits, r)
    if rate_roll(rate, r):
        gamete.sat = mutation_func(gamete.sat, bits, r)
    if rate_roll(rate, r):
        gamete.hue_ratedir = mutation_func(gamete.hue_ratedir, bits, r)
    if rate_roll(rate, r):
        gamete.hue_base = mutation_func(gamete.hue_base, bits, r)
    if rate_roll(rate, r):
        gamete.hue_bound = mutation_func(gamete.hue_bound, bits, r)
    if rate_roll(rate, r):
        gamete.chaser = mutation_func(gamete.chaser, bits, r)
    if rate_roll(rate, r):
        gamete.nonlin = mutation_func(gamete.nonlin, bits, r)


def get_padded_gamete(
    diploid: Diploid,
    badge_type: BadgeType,
    rate: MutationRate = MutationRate.BASELINE,
    rng: Optional[random.Random] = None,
    *,
    mutate_gamete: bool = True,
) -> bytes:
    """Match vault GlobalConfig::get_padded_gamete."""
    r = _rng(rng)
    gamete = diploid.meiosis(r)
    if mutate_gamete:
        mutate(gamete, rate, r)
    d = bytearray(16)
    ser = gamete.serialize()
    length = min(len(ser), 15)
    d[:length] = ser[:length]
    d[15] = int(badge_type) & 0xFF
    return bytes(d)


def describe_padded(gamete16: bytes) -> str:
    if len(gamete16) != 16:
        return f"len={len(gamete16)}"
    h = Haploid.deserialize(gamete16)
    bt = BadgeType(gamete16[15]) if gamete16[15] in list(BadgeType) else None
    bt_s = bt.name.lower() if bt is not None else f"unknown({gamete16[15]})"
    if h is None:
        return f"badge={bt_s} raw={gamete16.hex()}"
    return (
        f"badge={bt_s} period={h.cd_period} rate={h.cd_rate} dir={h.cd_dir} "
        f"sat={h.sat} hue=({h.hue_ratedir},{h.hue_base}-{h.hue_bound}) "
        f"chaser={h.chaser} nonlin={h.nonlin}"
    )


def describe_allele(h: Haploid, badge_type: Optional[BadgeType] = None) -> dict:
    """Structured allele summary for trackers / JSON export."""
    out = {
        "haploid_hex": h.serialize().hex(),
        "loci": h.as_dict(),
        "notes": {
            "cd_period": "spatial brightness frequency on ring",
            "cd_rate": "animation speed (maps to tau)",
            "cd_dir": "wave direction (>128 flips)",
            "sat": "HSV saturation",
            "hue_ratedir": "low nibble=rate, high nibble=direction",
            "hue_base": "palette min hue",
            "hue_bound": "palette max hue",
            "chaser": "C lin: <88 enables shoot/eye flash variant",
            "nonlin": ">127 squares value (dimmer)",
        },
    }
    if badge_type is not None:
        out["badge_type"] = badge_type.name.lower()
        out["badge_type_u8"] = int(badge_type)
    return out


def hsv_to_rgb(h: int, s: int, v: int) -> tuple[int, int, int]:
    """Match lightgenes/main.c HsvToRgb (h,s,v as u8)."""
    h &= 0xFF
    s &= 0xFF
    v &= 0xFF
    if s == 0:
        return v, v, v
    region = h // 43
    remainder = (h - region * 43) * 6
    p = (v * (255 - s)) >> 8
    q = (v * (255 - ((s * remainder) >> 8))) >> 8
    t = (v * (255 - ((s * (255 - remainder)) >> 8))) >> 8
    if region == 0:
        return v, t, p
    if region == 1:
        return q, v, p
    if region == 2:
        return p, v, t
    if region == 3:
        return p, q, v
    if region == 4:
        return t, p, v
    return v, p, q


def approx_frame(
    pheno: Haploid,
    t_ms: float,
    *,
    ring_leds: int = 8,
    loop: Optional[int] = None,
) -> dict:
    """Best-effort host preview of lightgenes phenotype (not cycle-accurate BIO).

    Returns {ring: [[r,g,b],...], eyes: [[r,g,b],[r,g,b]], loop, tau_ms}.
    Field `chaser` maps to C `lin` (shoot variant when < 88).
    """
    import math

    count = ring_leds
    tau = int(60 + (pheno.cd_rate / 255.0) * (700 - 60))
    tau = max(1, tau)
    # firmware: loop_state advances; indextime from time_ms/10 vs reftime
    curtime = t_ms / 10.0
    # approximate continuous phase instead of discrete reftime snaps
    indextime = -(curtime % tau)
    if loop is None:
        loop = int((t_ms / max(tau / 8.0, 1.0))) & 0x1FF
    else:
        loop = int(loop) & 0x1FF

    hue_rate = pheno.hue_ratedir & 0xF
    hue_dir = 1 if ((pheno.hue_ratedir >> 4) & 0xF) > 10 else 0
    half = max(count // 2, 1)

    ring: list[list[int]] = []
    eye_left = [0, 0, 0]
    eye_right = [0, 0, 0]
    shoot_override = False
    shoot_i = -1
    if pheno.chaser < 88:
        shoot_i = (loop // 2) % count
        if shoot_i < half:
            eye_left = [192, 192, 192]
        else:
            eye_right = [192, 192, 192]

    for i in range(count):
        if not hue_dir:
            hue_temp = ((128 // half) * i + (loop * hue_rate)) & 0x1FF
        else:
            hue_temp = ((128 // half) * i - (loop * hue_rate)) & 0x1FF
        if hue_temp > 0xFF:
            hue_temp = 511 - hue_temp
        # map 0..255 -> hue_base..hue_bound
        span = max(pheno.hue_bound - pheno.hue_base, 0)
        hh = pheno.hue_base + (hue_temp * span) // 255 if span else pheno.hue_base

        space = 2 * math.pi * pheno.cd_period * (i / max(count - 1, 1))
        time = 2 * math.pi * indextime / tau
        spacetime = space + time if pheno.cd_dir > 128 else space - time
        val = int(127 * (1.0 + math.cos(spacetime))) & 0xFF
        if pheno.nonlin > 127:
            val = (val * val) >> 8

        if pheno.chaser < 88 and shoot_i == i:
            rgb = [160, 160, 160]
            shoot_override = True
        else:
            rgb = list(hsv_to_rgb(hh, pheno.sat, val))

        if pheno.chaser >= 88:
            if i == 0:
                eye_left = rgb[:]
            if i == half:
                eye_right = rgb[:]

        ring.append(rgb)

    # power shift approximation (non-uber shift=5)
    def dim(c: list[int], sh: int = 5) -> list[int]:
        return [x >> sh for x in c]

    return {
        "ring": [dim(c) for c in ring],
        "eyes": [dim(eye_left, 3), dim(eye_right, 3)],
        "loop": loop,
        "tau_ms": tau * 10,  # curtime is ms/10
        "shoot_variant": pheno.chaser < 88,
        "approx": True,
    }


def make_rng(seed: Optional[int]) -> random.Random:
    if seed is None:
        return random.SystemRandom()
    return random.Random(seed)


# --- CLI / selftest --------------------------------------------------------------


def _selftest() -> None:
    # serialize roundtrip
    rng = random.Random(0xDC34)
    h = Haploid.from_type(BadgeType.HUMAN, rng)
    assert Haploid.deserialize(h.serialize()) == h

    d = Diploid.from_type(BadgeType.GOON, rng)
    assert Diploid.deserialize(d.serialize()) == d
    assert len(d.serialize()) == 18

    # goon forces hue_base=0
    assert d.a.hue_base == 0 and d.b.hue_base == 0

    # padded layout
    pad = get_padded_gamete(d, BadgeType.GOON, MutationRate.NONE, random.Random(1), mutate_gamete=False)
    assert len(pad) == 16
    assert pad[15] == BadgeType.GOON
    assert pad[9:15] == b"\x00" * 6
    assert Haploid.deserialize(pad) is not None

    # gray codec
    for n in range(256):
        assert gray_decode(gray_encode(n)) == n

    # phenotype saturating add
    p = Diploid(
        Haploid(cd_dir=200, sat=200, chaser=200, nonlin=10, hue_base=10, hue_bound=20),
        Haploid(cd_dir=200, sat=200, chaser=200, nonlin=10, hue_base=5, hue_bound=30),
    ).phenotype()
    assert p.cd_dir == 255 and p.sat == 255
    assert p.hue_base == 5 and p.hue_bound == 30

    # mutation with None rate is no-op
    before = Haploid.from_rand(random.Random(2))
    after = Haploid(**before.as_dict())
    mutate(after, MutationRate.NONE, random.Random(3))
    assert before == after

    fr = approx_frame(Haploid.from_type(BadgeType.HUMAN, random.Random(9)), 1000.0)
    assert len(fr["ring"]) == 8 and len(fr["eyes"]) == 2
    assert fr["approx"] is True

    print("dc34_gene selftest OK")


def main() -> None:
    p = argparse.ArgumentParser(description="DC34 gene model (Haploid/Diploid port)")
    sub = p.add_subparsers(dest="cmd", required=True)

    t = sub.add_parser("selftest", help="Run port consistency checks")
    t.set_defaults(func=lambda _a: _selftest())

    d = sub.add_parser("diploid", help="Create a synthetic peer diploid")
    d.add_argument("--badge-type", default="human")
    d.add_argument("--seed", type=int, default=None)
    d.add_argument("--json", action="store_true")
    d.set_defaults(func=_cmd_diploid)

    g = sub.add_parser("gamete", help="meiosis+mutate → 16-byte padded gamete")
    g.add_argument("--badge-type", default="human")
    g.add_argument("--diploid-hex", help="18-byte diploid; else generate from --badge-type")
    g.add_argument("--rate", default="baseline", help=f"one of {sorted(MUTATION_ALIASES)}")
    g.add_argument("--seed", type=int, default=None)
    g.add_argument("--no-mutate", action="store_true")
    g.set_defaults(func=_cmd_gamete)

    a = sub.add_parser("describe", help="Describe haploid hex or padded gamete")
    a.add_argument("hex", help="9-byte haploid or 16-byte padded gamete")
    a.add_argument("--json", action="store_true")
    a.set_defaults(func=_cmd_describe)

    f = sub.add_parser("frame", help="One approx LED frame as JSON")
    f.add_argument("--haploid-hex", required=True)
    f.add_argument("--t-ms", type=float, default=0.0)
    f.set_defaults(func=_cmd_frame)

    args = p.parse_args()
    args.func(args)


def _cmd_diploid(args: argparse.Namespace) -> None:
    bt = parse_badge(args.badge_type)
    dip = Diploid.from_type(bt, make_rng(args.seed))
    hx = dip.serialize().hex()
    if args.json:
        print(
            json.dumps(
                {
                    "badge_type": bt.name.lower(),
                    "badge_type_u8": int(bt),
                    "diploid_hex": hx,
                    "a": dip.a.as_dict(),
                    "b": dip.b.as_dict(),
                    "phenotype": dip.phenotype().as_dict(),
                },
                indent=2,
            )
        )
    else:
        print(f"badge_type: {bt.name.lower()} ({int(bt)})")
        print(f"diploid_hex: {hx}")
        print(f"a: {dip.a.as_dict()}")
        print(f"b: {dip.b.as_dict()}")
        print(f"phenotype: {dip.phenotype().as_dict()}")


def _cmd_gamete(args: argparse.Namespace) -> None:
    bt = parse_badge(args.badge_type)
    rate = parse_rate(args.rate)
    rng = make_rng(args.seed)
    if args.diploid_hex:
        raw = bytes.fromhex(args.diploid_hex)
        dip = Diploid.deserialize(raw)
        if dip is None:
            raise SystemExit("bad diploid hex (need 18 bytes)")
    else:
        dip = Diploid.from_type(bt, rng)
    pad = get_padded_gamete(dip, bt, rate, rng, mutate_gamete=not args.no_mutate)
    print(f"diploid_hex: {dip.serialize().hex()}")
    print(f"gamete_hex:  {pad.hex()}")
    print(f"describe:    {describe_padded(pad)}")


def _cmd_describe(args: argparse.Namespace) -> None:
    raw = bytes.fromhex(args.hex.replace(" ", ""))
    if len(raw) == 16:
        h = Haploid.deserialize(raw)
        bt = BadgeType(raw[15]) if raw[15] in list(BadgeType) else None
        if args.json and h:
            print(json.dumps(describe_allele(h, bt), indent=2))
        else:
            print(describe_padded(raw))
    elif len(raw) >= 9:
        h = Haploid.deserialize(raw)
        if h is None:
            raise SystemExit("bad haploid")
        if args.json:
            print(json.dumps(describe_allele(h), indent=2))
        else:
            print(describe_allele(h)["haploid_hex"], h.as_dict())
    else:
        raise SystemExit("need 9-byte haploid or 16-byte padded gamete hex")


def _cmd_frame(args: argparse.Namespace) -> None:
    h = Haploid.deserialize(bytes.fromhex(args.haploid_hex.replace(" ", "")))
    if h is None:
        raise SystemExit("bad haploid hex")
    print(json.dumps(approx_frame(h, args.t_ms), indent=2))


if __name__ == "__main__":
    main()
