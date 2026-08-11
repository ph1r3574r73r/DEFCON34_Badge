#!/usr/bin/env python3
"""Warp OLED from pager frames → 512² stills + contact sheets for transcription."""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np


def oled_warp(gray: np.ndarray, size: int = 512) -> np.ndarray | None:
    h, w = gray.shape
    thr = max(150, int(np.percentile(gray, 96)))
    mask = (gray >= thr).astype(np.uint8) * 255
    ker = cv2.getStructuringElement(cv2.MORPH_RECT, (21, 21))
    mask = cv2.dilate(mask, ker)
    n, labels, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
    best = None
    for i in range(1, n):
        x, y, bw, bh, area = (int(v) for v in stats[i])
        if min(bw, bh) < min(180, min(h, w) // 4):
            continue
        # Close-up OLED can fill the frame (3px QR ~123/128). Do not reject
        # large near-square blobs the way a distant phone shot would.
        if max(bw, bh) > max(h, w):
            continue
        close = area >= (h * w) * 0.12
        if not close and (y < h * 0.18 or y > h * 0.82):
            continue
        aspect = bw / max(bh, 1)
        if not 0.70 <= aspect <= 1.45:
            continue
        if best is None or area > best[0]:
            best = (area, i)
    if best is None:
        return None
    ys, xs = np.where(labels == best[1])
    pts = np.stack([xs, ys], 1).astype(np.float32)
    box = cv2.boxPoints(cv2.minAreaRect(pts))
    s = box.sum(1)
    d = np.diff(box, axis=1).ravel()
    tl, br = box[np.argmin(s)], box[np.argmax(s)]
    tr, bl = box[np.argmin(d)], box[np.argmax(d)]
    q = np.array([tl, tr, br, bl], np.float32)
    dst = np.array([[0, 0], [size - 1, 0], [size - 1, size - 1], [0, size - 1]], np.float32)
    M = cv2.getPerspectiveTransform(q, dst)
    return cv2.warpPerspective(gray, M, (size, size))


def sharpness(img: np.ndarray) -> float:
    return float(cv2.Laplacian(img, cv2.CV_64F).var())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("frames", type=Path, nargs="+")
    ap.add_argument("-o", "--out", type=Path, default=Path("captures/hop132/page_stills"))
    ap.add_argument("--every", type=int, default=3, help="keep every Nth frame (~0.75s at 4fps)")
    ap.add_argument("--sheet", type=int, default=4)
    args = ap.parse_args()
    stills = args.out / "stills"
    sheets = args.out / "sheets"
    stills.mkdir(parents=True, exist_ok=True)
    sheets.mkdir(parents=True, exist_ok=True)

    saved = []
    idx = 0
    for d in args.frames:
        paths = sorted(d.glob("*.jpg")) + sorted(d.glob("*.png"))
        paths = paths[:: max(1, args.every)]
        print(f"{d.name}: {len(paths)} sampled", flush=True)
        for p in paths:
            im = cv2.imread(str(p), cv2.IMREAD_GRAYSCALE)
            if im is None:
                continue
            w = oled_warp(im)
            if w is None:
                continue
            name = f"{idx:04d}_{d.name}_{p.stem}.png"
            cv2.imwrite(str(stills / name), w)
            saved.append((stills / name, sharpness(w), d.name, p.stem))
            idx += 1
            if idx % 20 == 0:
                print(f"  warped {idx}", flush=True)
    print(f"stills {len(saved)}", flush=True)

    n = args.sheet
    for si in range(0, len(saved), n):
        chunk = saved[si : si + n]
        cols = 2
        rows = (len(chunk) + cols - 1) // cols
        tile = 512
        sheet = np.zeros((rows * tile, cols * tile), np.uint8)
        for j, (path, _sh, src, stem) in enumerate(chunk):
            img = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
            r, c = divmod(j, cols)
            sheet[r * tile : (r + 1) * tile, c * tile : (c + 1) * tile] = img
            label = f"{si+j} {src}/{stem}"
            cv2.putText(
                sheet,
                label,
                (c * tile + 8, r * tile + 28),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                255,
                2,
                cv2.LINE_AA,
            )
        outp = sheets / f"sheet_{si:04d}.png"
        cv2.imwrite(str(outp), sheet)
        print("wrote", outp, flush=True)


if __name__ == "__main__":
    main()
