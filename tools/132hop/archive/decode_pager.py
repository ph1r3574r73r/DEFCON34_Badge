#!/usr/bin/env python3
"""Decode asid_pages OLED pager videos → dump JSON for derive.py.

Status row: page, 0xBE, cksum16 LE. 190 pages × 64B.
No live write.
"""

from __future__ import annotations

import argparse
import json
import struct
import sys
from collections import Counter, defaultdict
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
sys.path.insert(0, str(PARENT))
sys.path.insert(0, str(HERE))
from oled_dump import SEG7  # noqa: E402
from oled_pages import DUMP_BYTES, N_PAGES  # noqa: E402

HEX = "0123456789abcdef"


def _seg_glyph(nibble: int, s: int) -> np.ndarray:
    """Render one 7-seg nibble. s = camera pixels per OLED pixel. Cell 8×14 OLED."""
    cw, ch = 8 * s, 14 * s
    g = np.zeros((ch, cw), np.uint8)
    bits = SEG7[nibble]

    def hline(x: int, y: int, n: int = 3) -> None:
        g[y * s : (y + 1) * s, x * s : (x + n) * s] = 255

    def vline(x: int, y: int, n: int = 3) -> None:
        g[y * s : (y + n) * s, x * s : (x + 1) * s] = 255

    if bits & 1:
        hline(1, 0)
    if bits & 2:
        vline(4, 1)
    if bits & 4:
        vline(4, 5)
    if bits & 8:
        hline(1, 8)
    if bits & 16:
        vline(0, 5)
    if bits & 32:
        vline(0, 1)
    if bits & 64:
        hline(1, 4)
    return g


def _legend_tmpl(s: int) -> np.ndarray:
    parts = [_seg_glyph(i, s) for i in range(16)]
    return np.hstack(parts)


def _find_oled_bbox(gray: np.ndarray) -> tuple[int, int, int, int] | None:
    """Return (x0, y0, x1, y1) of the near-square OLED blob."""
    h, w = gray.shape
    thr = max(150, int(np.percentile(gray, 96)))
    mask = (gray >= thr).astype(np.uint8) * 255
    ker = cv2.getStructuringElement(cv2.MORPH_RECT, (21, 21))
    mask = cv2.dilate(mask, ker)
    _n, _labels, stats, _cents = cv2.connectedComponentsWithStats(mask, 8)
    best = None  # area, x0,y0,x1,y1
    for i in range(1, _n):
        x, y, bw, bh, area = (int(v) for v in stats[i])
        if min(bw, bh) < 180 or max(bw, bh) > 620:
            continue
        if y < h * 0.18 or y > h * 0.82:
            continue
        aspect = bw / max(bh, 1)
        if not 0.75 <= aspect <= 1.35:
            continue
        if best is None or area > best[0]:
            inset = 10
            best = (
                area,
                x + inset,
                y + inset,
                x + bw - inset,
                y + bh - inset,
            )
    if best is None:
        return None
    _, x0, y0, x1, y1 = best
    if x1 - x0 < 160 or y1 - y0 < 160:
        return None
    return x0, y0, x1, y1


def _ncc(a: np.ndarray, b: np.ndarray) -> float:
    a = a.astype(np.float32).ravel()
    b = b.astype(np.float32).ravel()
    a -= a.mean()
    b -= b.mean()
    d = float(np.linalg.norm(a) * np.linalg.norm(b))
    if d < 1e-6:
        return -1.0
    return float(np.dot(a, b) / d)


def _match_nibble(cell: np.ndarray, tmpls: list[np.ndarray]) -> tuple[int, float]:
    best_i, best_s = 0, -2.0
    for i, t in enumerate(tmpls):
        if t.shape != cell.shape:
            t = cv2.resize(t, (cell.shape[1], cell.shape[0]), interpolation=cv2.INTER_AREA)
        s = _ncc(cell, t)
        if s > best_s:
            best_i, best_s = i, s
    return best_i, best_s


def _cell(gray: np.ndarray, x: float, y: float, s: float) -> np.ndarray:
    x0, y0 = int(round(x)), int(round(y))
    x1, y1 = int(round(x + 8 * s)), int(round(y + 14 * s))
    x0 = max(0, x0)
    y0 = max(0, y0)
    x1 = min(gray.shape[1], x1)
    y1 = min(gray.shape[0], y1)
    crop = gray[y0:y1, x0:x1]
    if crop.size == 0:
        return np.zeros((max(1, int(14 * s)), max(1, int(8 * s))), np.uint8)
    tw, th = max(4, int(8 * s)), max(6, int(14 * s))
    return cv2.resize(crop, (tw, th), interpolation=cv2.INTER_AREA)


def decode_frame(bgr: np.ndarray) -> dict | None:
    if bgr.ndim == 3:
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    else:
        gray = bgr
    bbox = _find_oled_bbox(gray)
    if bbox is None:
        return None
    x0, y0, x1, y1 = bbox
    s0 = (x1 - x0) / 128.0
    if s0 < 1.4 or s0 > 4.8:
        return None

    # legend lives in the top ~30% of the OLED
    roi = gray[y0 : y0 + max(40, int(0.40 * (y1 - y0))), x0:x1]
    best = None  # score, scale_int, lx, ly
    for ss in range(max(2, int(s0) - 1), int(s0) + 3):
        tmpl = _legend_tmpl(ss)
        if roi.shape[0] < tmpl.shape[0] or roi.shape[1] < tmpl.shape[1]:
            continue
        res = cv2.matchTemplate(roi, tmpl, cv2.TM_CCOEFF_NORMED)
        _minv, maxv, _minl, maxl = cv2.minMaxLoc(res)
        if best is None or maxv > best[0]:
            best = (maxv, ss, x0 + maxl[0], y0 + maxl[1])
    if best is None or best[0] < 0.30:
        return None
    leg_score, s_i, lx, ly = best
    s = float(s_i)
    ox = float(lx)
    oy = float(ly) - 4.0 * s

    tmpls = [_seg_glyph(i, s_i) for i in range(16)]

    def read_row(y_oled: float, n: int) -> tuple[list[int], float]:
        vals = []
        scores = []
        y = oy + y_oled * s
        for i in range(n):
            cell = _cell(gray, ox + i * 8 * s, y, s)
            d, sc = _match_nibble(cell, tmpls)
            vals.append(d)
            scores.append(sc)
        return vals, float(np.mean(scores)) if scores else -1.0

    # verify legend
    leg_vals, leg_m = read_row(4.0, 16)
    if leg_vals != list(range(16)) and sum(a == b for a, b in zip(leg_vals, range(16))) < 12:
        # still try — status BE check will reject junk
        pass

    st_vals, st_m = read_row(16.0, 8)
    if len(st_vals) < 8:
        return None
    page = (st_vals[0] << 4) | st_vals[1]
    be = (st_vals[2] << 4) | st_vals[3]
    ck_lo = (st_vals[4] << 4) | st_vals[5]
    ck_hi = (st_vals[6] << 4) | st_vals[7]
    if be != 0xBE or page >= N_PAGES:
        return None

    hex_vals: list[int] = []
    hex_scores: list[float] = []
    for r in range(8):
        vals, sc = read_row(28.0 + 12.0 * r, 16)
        hex_vals.extend(vals)
        hex_scores.append(sc)
    if len(hex_vals) != 128:
        return None
    data = bytes(((hex_vals[i] << 4) | hex_vals[i + 1]) for i in range(0, 128, 2))
    return {
        "page": page,
        "be": be,
        "cksum16": ck_lo | (ck_hi << 8),
        "data": data.hex(),
        "leg_score": round(leg_score, 3),
        "leg_match": sum(a == b for a, b in zip(leg_vals, range(16))),
        "st_score": round(st_m, 3),
        "hex_score": round(float(np.mean(hex_scores)), 3),
        "scale": round(s, 2),
        "origin": [round(ox, 1), round(oy, 1)],
        "legend": "".join(HEX[v] for v in leg_vals),
        "status_hex": "".join(HEX[v] for v in st_vals),
    }


def decode_dir(frame_dir: Path, limit: int | None = None) -> list[dict]:
    paths = sorted(frame_dir.glob("*.jpg")) + sorted(frame_dir.glob("*.png"))
    if limit:
        paths = paths[:limit]
    out = []
    for i, p in enumerate(paths):
        img = cv2.imread(str(p), cv2.IMREAD_GRAYSCALE)
        if img is None:
            continue
        rec = decode_frame(img)
        if rec:
            rec["file"] = p.name
            rec["src"] = frame_dir.name
            out.append(rec)
        if (i + 1) % 50 == 0 or i + 1 == len(paths):
            print(f"  {frame_dir.name}: {i+1}/{len(paths)} ok={len(out)}", flush=True)
    return out


def vote_pages(recs: list[dict]) -> dict[int, dict]:
    by_page: dict[int, list[dict]] = defaultdict(list)
    for r in recs:
        by_page[r["page"]].append(r)
    voted = {}
    for page, rs in sorted(by_page.items()):
        # prefer higher hex_score * leg_match
        rs = sorted(rs, key=lambda r: (r["hex_score"] + 0.05 * r["leg_match"]), reverse=True)
        top = rs[: max(3, min(8, len(rs)))]
        hex_chars = []
        confs = []
        for i in range(128):
            c = Counter(r["data"][i] for r in top)
            ch, n = c.most_common(1)[0]
            hex_chars.append(ch)
            confs.append(n / len(top))
        data_hex = "".join(hex_chars)
        ck = Counter(r["cksum16"] for r in rs)
        voted[page] = {
            "page": page,
            "n_frames": len(rs),
            "cksum16": ck.most_common(1)[0][0],
            "data": data_hex,
            "mean_conf": round(float(np.mean(confs)), 3),
            "best_hex_score": rs[0]["hex_score"],
            "files": [r["file"] for r in top[:3]],
        }
    return voted


def assemble(voted: dict[int, dict]) -> dict:
    missing = [p for p in range(N_PAGES) if p not in voted]
    blob = bytearray(DUMP_BYTES)
    for p, rec in voted.items():
        off = p * 64
        b = bytes.fromhex(rec["data"])
        if len(b) != 64:
            continue
        blob[off : off + 64] = b
    words = list(struct.unpack("<" + "I" * (DUMP_BYTES // 4), bytes(blob)))
    xor_all = 0
    for w in words:
        xor_all ^= w
    ck16 = xor_all & 0xFFFF
    reported = None
    if voted:
        reported = Counter(v["cksum16"] for v in voted.values()).most_common(1)[0][0]
    uuid = blob[0:32]
    cpid = blob[32:64]
    root = blob[64:96]
    flag1 = blob[96:128]
    n0 = blob[128 : 128 + 3840]
    chaff = blob[128 + 3840 : 128 + 3840 + 4096]
    n1 = blob[128 + 3840 + 4096 : 128 + 3840 + 4096 + 4096]
    return {
        "n_pages_ok": len(voted),
        "n_pages_total": N_PAGES,
        "missing_pages": missing,
        "cksum16_reported": reported,
        "cksum16_computed": ck16,
        "cksum_match": reported == ck16 if reported is not None else False,
        "uuid": uuid.hex(),
        "cp_id": cpid.hex(),
        "root_seed": root.hex(),
        "flag1": flag1.hex(),
        "nuisance0": n0.hex(),
        "chaff": chaff.hex(),
        "nuisance1": n1.hex(),
        "developer_mode": 0,
        "oem_mode": 1,
        "boot0_pubkey_fail": 0,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("frames", nargs="+", type=Path, help="directories of jpeg/png frames")
    ap.add_argument("-o", "--out", type=Path, default=Path("captures/hop132/dump_pages.json"))
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--dump-recs", type=Path, default=None)
    args = ap.parse_args()
    recs: list[dict] = []
    for d in args.frames:
        print(f"decoding {d} ...", flush=True)
        recs.extend(decode_dir(d, limit=args.limit or None))
    print(f"decoded frames with BE: {len(recs)}")
    voted = vote_pages(recs)
    print(f"unique pages: {len(voted)} / {N_PAGES}")
    if voted:
        pages = sorted(voted)
        print(f"page range {pages[0]}..{pages[-1]} missing {N_PAGES - len(voted)}")
        gaps = [p for p in range(N_PAGES) if p not in voted]
        if gaps:
            print(f"missing: {gaps[:40]}{'...' if len(gaps)>40 else ''}")
    doc = assemble(voted)
    doc["source_videos"] = [str(p) for p in args.frames]
    doc["n_good_frames"] = len(recs)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(doc, indent=2) + "\n")
    print("wrote", args.out)
    if args.dump_recs:
        slim = [{k: r[k] for k in r if k != "data" or True} for r in recs]
        args.dump_recs.write_text(json.dumps(slim, indent=2) + "\n")
    print(json.dumps({k: doc[k] for k in (
        "n_pages_ok", "n_pages_total", "missing_pages", "cksum16_reported",
        "cksum16_computed", "cksum_match", "uuid", "cp_id", "root_seed", "flag1",
    )}, indent=2))


if __name__ == "__main__":
    main()
