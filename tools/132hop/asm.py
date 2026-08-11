"""Tiny RV32I assembler (two-pass, labels). Enough for hop stage-2 stubs."""

from __future__ import annotations

import re
from dataclasses import dataclass

REGS = {
    "zero": 0,
    "ra": 1,
    "sp": 2,
    "gp": 3,
    "tp": 4,
    "t0": 5,
    "t1": 6,
    "t2": 7,
    "s0": 8,
    "fp": 8,
    "s1": 9,
    "a0": 10,
    "a1": 11,
    "a2": 12,
    "a3": 13,
    "a4": 14,
    "a5": 15,
    "a6": 16,
    "a7": 17,
    "s2": 18,
    "s3": 19,
    "s4": 20,
    "s5": 21,
    "s6": 22,
    "s7": 23,
    "s8": 24,
    "s9": 25,
    "s10": 26,
    "s11": 27,
    "t3": 28,
    "t4": 29,
    "t5": 30,
    "t6": 31,
}
for i in range(32):
    REGS[f"x{i}"] = i

CSRS = {
    "mstatus": 0x300,
    "mtvec": 0x305,
    "mepc": 0x341,
    "mcause": 0x342,
    "medeleg": 0x302,
    "mideleg": 0x303,
    "satp": 0x180,
}


def _reg(tok: str) -> int:
    t = tok.lower().rstrip(",")
    if t not in REGS:
        raise ValueError(f"unknown reg {tok!r}")
    return REGS[t]


def _imm(tok: str) -> int:
    t = tok.lower().rstrip(",").replace("_", "")
    if t.startswith("0x"):
        return int(t, 16)
    return int(t, 0) if t.startswith(("+", "-")) or t.isdigit() else int(t, 10)


def _imm_or_label(tok: str, labels: dict[str, int] | None) -> int | str:
    t = tok.rstrip(",")
    if re.fullmatch(r"[+-]?0x[0-9a-fA-F]+|[+-]?\d+", t.replace("_", "")):
        return _imm(t)
    if labels is not None and t in labels:
        return labels[t]
    return t


def u32(n: int) -> int:
    return n & 0xFFFFFFFF


def enc_r(funct7: int, rs2: int, rs1: int, funct3: int, rd: int, opcode: int) -> int:
    return (funct7 << 25) | (rs2 << 20) | (rs1 << 15) | (funct3 << 12) | (rd << 7) | opcode


def enc_i(imm: int, rs1: int, funct3: int, rd: int, opcode: int) -> int:
    return ((imm & 0xFFF) << 20) | (rs1 << 15) | (funct3 << 12) | (rd << 7) | opcode


def enc_s(imm: int, rs2: int, rs1: int, funct3: int, opcode: int) -> int:
    imm &= 0xFFF
    return ((imm >> 5) << 25) | (rs2 << 20) | (rs1 << 15) | (funct3 << 12) | ((imm & 0x1F) << 7) | opcode


def enc_b(imm: int, rs2: int, rs1: int, funct3: int, opcode: int) -> int:
    imm &= 0x1FFF
    return (
        ((imm >> 12) & 1) << 31
        | ((imm >> 5) & 0x3F) << 25
        | rs2 << 20
        | rs1 << 15
        | funct3 << 12
        | ((imm >> 1) & 0xF) << 8
        | ((imm >> 11) & 1) << 7
        | opcode
    )


def enc_u(imm: int, rd: int, opcode: int) -> int:
    return (imm << 12) | (rd << 7) | opcode


def enc_j(imm: int, rd: int, opcode: int) -> int:
    imm &= 0x1FFFFF
    return (
        ((imm >> 20) & 1) << 31
        | ((imm >> 1) & 0x3FF) << 21
        | ((imm >> 11) & 1) << 20
        | ((imm >> 12) & 0xFF) << 12
        | rd << 7
        | opcode
    )


@dataclass
class Asm:
    base: int
    words: list[int]
    labels: dict[str, int]
    relocs: list[tuple[int, str, str]]  # pc, kind, label

    @classmethod
    def assemble(cls, src: str, *, base: int) -> bytes:
        a = cls(base=base, words=[], labels={}, relocs=[])
        for raw in src.splitlines():
            line = raw.split("#", 1)[0].strip()
            if not line:
                continue
            while True:
                m = re.match(r"^([A-Za-z_][\w]*):\s*(.*)$", line)
                if not m:
                    break
                a.labels[m.group(1)] = a.base + 4 * len(a.words)
                line = m.group(2).strip()
                if not line:
                    break
            if line:
                a._emit(line)
        a._fixup()
        out = b"".join(w.to_bytes(4, "little") for w in a.words)
        return out

    def _pc(self) -> int:
        return self.base + 4 * len(self.words)

    def _emit(self, line: str) -> None:
        parts = [p for p in re.split(r"[,\s]+", line) if p]
        op = parts[0].lower()
        args = parts[1:]
        pc = self._pc()

        if op == "nop":
            self.words.append(enc_i(0, 0, 0, 0, 0x13))
            return
        if op == "ret":
            self.words.append(enc_i(0, 1, 0, 0, 0x67))
            return
        if op == "ecall":
            self.words.append(0x00000073)
            return
        if op == "mret":
            self.words.append(0x30200073)
            return
        if op == "fence.i":
            self.words.append(0x0000100F)
            return
        if op == "fence":
            self.words.append(0x0FF0000F)
            return
        if op == "sfence.vma":
            rs1 = _reg(args[0]) if args else 0
            rs2 = _reg(args[1]) if len(args) > 1 else 0
            self.words.append((0x09 << 25) | (rs2 << 20) | (rs1 << 15) | 0x73)
            return
        if op == "j":
            tgt = args[0]
            if tgt in self.labels:
                imm = self.labels[tgt] - pc
                self.words.append(enc_j(imm, 0, 0x6F))
            else:
                self.relocs.append((pc, "j", tgt))
                self.words.append(0)
            return
        if op == "jal" and len(args) == 2:
            rd = _reg(args[0])
            tgt = args[1]
            if tgt in self.labels:
                self.words.append(enc_j(self.labels[tgt] - pc, rd, 0x6F))
            elif re.fullmatch(r"[+-]?0x[0-9a-fA-F]+|[+-]?\d+", tgt.replace("_", "")):
                self.words.append(enc_j(_imm(tgt), rd, 0x6F))
            else:
                self.relocs.append((pc, f"jal:{rd}", tgt))
                self.words.append(0)
            return
        if op in ("beq", "bne", "blt", "bge", "bltu", "bgeu"):
            f3 = {"beq": 0, "bne": 1, "blt": 4, "bge": 5, "bltu": 6, "bgeu": 7}[op]
            rs1, rs2, tgt = _reg(args[0]), _reg(args[1]), args[2]
            if tgt in self.labels:
                self.words.append(enc_b(self.labels[tgt] - pc, rs2, rs1, f3, 0x63))
            else:
                self.relocs.append((pc, f"{op}:{rs1}:{rs2}", tgt))
                self.words.append(0)
            return
        if op == "beqz":
            return self._emit(f"beq {args[0]}, zero, {args[1]}")
        if op == "bnez":
            return self._emit(f"bne {args[0]}, zero, {args[1]}")
        if op == "call":
            return self._emit(f"jal ra, {args[0]}")
        if op == ".word":
            for tok in args:
                self.words.append(u32(_imm(tok)))
            return
        if op == "lui":
            self.words.append(enc_u(_imm(args[1]) & 0xFFFFF, _reg(args[0]), 0x37))
            return
        if op == "auipc":
            self.words.append(enc_u(_imm(args[1]) & 0xFFFFF, _reg(args[0]), 0x17))
            return
        if op == "jalr":
            # jalr rd, rs1, imm   OR jalr rd, imm(rs1)
            if len(args) == 3:
                rd, rs1, imm = _reg(args[0]), _reg(args[1]), _imm(args[2])
            else:
                m = re.match(r"(-?0x[0-9a-fA-F]+|-?\d+)\((\w+)\)", args[1].replace(" ", ""))
                if not m:
                    raise ValueError(f"bad jalr {line}")
                rd, imm, rs1 = _reg(args[0]), _imm(m.group(1)), _reg(m.group(2))
            self.words.append(enc_i(imm, rs1, 0, rd, 0x67))
            return
        if op == "addi":
            self.words.append(enc_i(_imm(args[2]), _reg(args[1]), 0, _reg(args[0]), 0x13))
            return
        if op == "andi":
            self.words.append(enc_i(_imm(args[2]), _reg(args[1]), 7, _reg(args[0]), 0x13))
            return
        if op == "ori":
            self.words.append(enc_i(_imm(args[2]), _reg(args[1]), 6, _reg(args[0]), 0x13))
            return
        if op == "xori":
            self.words.append(enc_i(_imm(args[2]), _reg(args[1]), 4, _reg(args[0]), 0x13))
            return
        if op == "slli":
            self.words.append(enc_i(_imm(args[2]) & 0x1F, _reg(args[1]), 1, _reg(args[0]), 0x13))
            return
        if op == "srli":
            self.words.append(enc_i(_imm(args[2]) & 0x1F, _reg(args[1]), 5, _reg(args[0]), 0x13))
            return
        if op == "srai":
            self.words.append(enc_i((_imm(args[2]) & 0x1F) | 0x400, _reg(args[1]), 5, _reg(args[0]), 0x13))
            return
        if op == "not":
            self.words.append(enc_i(0xFFF, _reg(args[1]), 4, _reg(args[0]), 0x13))
            return
        if op == "mv":
            self.words.append(enc_i(0, _reg(args[1]), 0, _reg(args[0]), 0x13))
            return
        if op == "la":
            rd = _reg(args[0])
            tgt = args[1]
            self.relocs.append((pc, f"la:{rd}", tgt))
            self.words.append(0)
            self.words.append(0)
            return
        if op == "li":
            rd, imm = _reg(args[0]), _imm(args[1])
            imm = u32(imm)
            hi = (imm + 0x800) >> 12  # lui + addi sign-extend
            lo = imm - (hi << 12)
            if hi & ~0xFFFFF:
                hi &= 0xFFFFF
            if hi == 0:
                self.words.append(enc_i(lo, 0, 0, rd, 0x13))
            else:
                self.words.append(enc_u(hi, rd, 0x37))
                if lo:
                    self.words.append(enc_i(lo, rd, 0, rd, 0x13))
            return
        if op in ("lb", "lh", "lw", "lbu", "lhu"):
            f3 = {"lb": 0, "lh": 1, "lw": 2, "lbu": 4, "lhu": 5}[op]
            rd = _reg(args[0])
            m = re.match(r"(-?0x[0-9a-fA-F]+|-?\d+)\((\w+)\)", args[1].replace(" ", ""))
            if not m:
                raise ValueError(f"bad {op} {line}")
            self.words.append(enc_i(_imm(m.group(1)), _reg(m.group(2)), f3, rd, 0x03))
            return
        if op in ("sb", "sh", "sw"):
            f3 = {"sb": 0, "sh": 1, "sw": 2}[op]
            rs2 = _reg(args[0])
            m = re.match(r"(-?0x[0-9a-fA-F]+|-?\d+)\((\w+)\)", args[1].replace(" ", ""))
            if not m:
                raise ValueError(f"bad {op} {line}")
            self.words.append(enc_s(_imm(m.group(1)), rs2, _reg(m.group(2)), f3, 0x23))
            return
        if op == "add":
            self.words.append(enc_r(0, _reg(args[2]), _reg(args[1]), 0, _reg(args[0]), 0x33))
            return
        if op == "sub":
            self.words.append(enc_r(0x20, _reg(args[2]), _reg(args[1]), 0, _reg(args[0]), 0x33))
            return
        if op == "sll":
            self.words.append(enc_r(0, _reg(args[2]), _reg(args[1]), 1, _reg(args[0]), 0x33))
            return
        if op == "srl":
            self.words.append(enc_r(0, _reg(args[2]), _reg(args[1]), 5, _reg(args[0]), 0x33))
            return
        if op == "sra":
            self.words.append(enc_r(0x20, _reg(args[2]), _reg(args[1]), 5, _reg(args[0]), 0x33))
            return
        if op == "xor":
            self.words.append(enc_r(0, _reg(args[2]), _reg(args[1]), 4, _reg(args[0]), 0x33))
            return
        if op == "or":
            self.words.append(enc_r(0, _reg(args[2]), _reg(args[1]), 6, _reg(args[0]), 0x33))
            return
        if op == "and":
            self.words.append(enc_r(0, _reg(args[2]), _reg(args[1]), 7, _reg(args[0]), 0x33))
            return
        if op == "slt":
            self.words.append(enc_r(0, _reg(args[2]), _reg(args[1]), 2, _reg(args[0]), 0x33))
            return
        if op == "sltu":
            self.words.append(enc_r(0, _reg(args[2]), _reg(args[1]), 3, _reg(args[0]), 0x33))
            return
        if op in ("csrrw", "csrrs", "csrrc"):
            f3 = {"csrrw": 1, "csrrs": 2, "csrrc": 3}[op]
            rd, csr_tok, rs1 = _reg(args[0]), args[1].lower().rstrip(","), _reg(args[2])
            csr = CSRS.get(csr_tok, _imm(csr_tok) if re.match(r"0x", csr_tok) else None)
            if csr is None:
                raise ValueError(f"unknown csr {csr_tok}")
            self.words.append(((csr & 0xFFF) << 20) | (rs1 << 15) | (f3 << 12) | (rd << 7) | 0x73)
            return
        if op == "csrw":
            # csrw csr, rs1
            csr_tok, rs1 = args[0].lower().rstrip(","), _reg(args[1])
            csr = CSRS.get(csr_tok, _imm(csr_tok) if csr_tok.startswith("0x") else None)
            if csr is None:
                raise ValueError(f"unknown csr {csr_tok}")
            self.words.append(((csr & 0xFFF) << 20) | (rs1 << 15) | (1 << 12) | (0 << 7) | 0x73)
            return
        if op == "csrr":
            rd, csr_tok = _reg(args[0]), args[1].lower().rstrip(",")
            csr = CSRS.get(csr_tok)
            if csr is None:
                raise ValueError(f"unknown csr {csr_tok}")
            self.words.append(((csr & 0xFFF) << 20) | (0 << 15) | (2 << 12) | (rd << 7) | 0x73)
            return
        raise ValueError(f"unsupported op: {line}")

    def _fixup(self) -> None:
        for pc, kind, label in self.relocs:
            if label not in self.labels:
                raise ValueError(f"undefined label {label}")
            imm = self.labels[label] - pc
            idx = (pc - self.base) // 4
            if kind == "j":
                self.words[idx] = enc_j(imm, 0, 0x6F)
            elif kind.startswith("jal:"):
                rd = int(kind.split(":")[1])
                self.words[idx] = enc_j(imm, rd, 0x6F)
            elif kind.split(":")[0] in ("beq", "bne", "blt", "bge", "bltu", "bgeu"):
                op, rs1, rs2 = kind.split(":")
                f3 = {"beq": 0, "bne": 1, "blt": 4, "bge": 5, "bltu": 6, "bgeu": 7}[op]
                self.words[idx] = enc_b(imm, int(rs2), int(rs1), f3, 0x63)
            elif kind.startswith("la:"):
                rd = int(kind.split(":")[1])
                hi = (imm + 0x800) >> 12
                lo = imm - (hi << 12)
                self.words[idx] = enc_u(hi & 0xFFFFF, rd, 0x17)  # auipc
                self.words[idx + 1] = enc_i(lo, rd, 0, rd, 0x13)  # addi
            else:
                raise ValueError(kind)


def assemble(src: str, *, base: int) -> bytes:
    return Asm.assemble(src, base=base)
