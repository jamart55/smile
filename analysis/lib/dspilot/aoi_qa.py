"""Derive/verify pilot-02 AOI boxes against the trial videos themselves.

Run: PYTHONPATH=lib uv run python -m dspilot.aoi_qa   (from smile/analysis/)

Reads config/aoi_layouts.json, measures where each trial's object actually sits
in its own video, asserts the object falls inside the box its filename names,
and writes one human-eyeballable overlay per trial to data/qa/aoi/.
"""

from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[3]          # smile/
PILOT = ROOT.parent                                  # pilot/
VIDEOS = ROOT / "public/videos/trials/pilot02"
TIMING = PILOT / "pilot-02-trial-timing.csv"
LAYOUTS = ROOT / "analysis/config/aoi_layouts.json"
QA = ROOT / "analysis/data/qa/aoi"
W, H, DS = 1920, 1080, 8
REF_T = 0.3          # motion trials: background reference (object still at start)
MIN_BLOCKS = 12      # ~768 px; kills codec speckle, keeps every real object


def _frame(mp4: Path, t: float) -> np.ndarray:
    out = subprocess.run(
        ["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", str(mp4),
         "-frames:v", "1", "-f", "image2pipe", "-vcodec", "png", "-"],
        capture_output=True, check=True).stdout
    import io
    return np.asarray(Image.open(io.BytesIO(out)).convert("RGB")).astype(np.int16)


def _duration(mp4: Path) -> float:
    return float(subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
         "format=duration", "-of", "csv=p=0", str(mp4)],
        capture_output=True, text=True, check=True).stdout)


def _blobs(mask: np.ndarray) -> list[dict]:
    """Connected components of a full-res boolean mask, bbox in video-frac."""
    blocks = mask[: H // DS * DS, : W // DS * DS].reshape(
        H // DS, DS, W // DS, DS).sum((1, 3)) >= 8
    seen = np.zeros_like(blocks)
    out = []
    for sy, sx in zip(*np.where(blocks)):
        if seen[sy, sx]:
            continue
        stack, px = [(sy, sx)], []
        seen[sy, sx] = True
        while stack:
            y, x = stack.pop()
            px.append((y, x))
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    ny, nx = y + dy, x + dx
                    if (0 <= ny < blocks.shape[0] and 0 <= nx < blocks.shape[1]
                            and blocks[ny, nx] and not seen[ny, nx]):
                        seen[ny, nx] = True
                        stack.append((ny, nx))
        if len(px) < MIN_BLOCKS:
            continue
        ys = [p[0] for p in px]
        xs = [p[1] for p in px]
        sub = np.zeros_like(mask)
        y0, y1 = min(ys) * DS, (max(ys) + 1) * DS
        x0, x1 = min(xs) * DS, (max(xs) + 1) * DS
        sub[y0:y1, x0:x1] = mask[y0:y1, x0:x1]
        yy, xx = np.where(sub)
        out.append(dict(x1=xx.min() / W, x2=(xx.max() + 1) / W,
                        y1=yy.min() / H, y2=(yy.max() + 1) / H, n=len(px)))
    return out


def object_blobs(mp4: Path, t: float, motion: bool, ref: np.ndarray | None) -> list[dict]:
    a = _frame(mp4, t)
    if motion:                       # track + occluder are static -> difference them out
        mask = np.abs(a - ref).max(2) > 30
    else:                            # 4-object trials sit on pure white, no track
        mask = a.min(2) < 240
    return _blobs(mask)


def box_edges(b: dict) -> tuple[float, float, float, float]:
    return b["cx"] - b["w"] / 2, b["cx"] + b["w"] / 2, b["cy"] - b["h"] / 2, b["cy"] + b["h"] / 2


def inside(blob: dict, b: dict) -> bool:
    x1, x2, y1, y2 = box_edges(b)
    return x1 <= blob["x1"] and blob["x2"] <= x2 and y1 <= blob["y1"] and blob["y2"] <= y2


def center_in(blob: dict, b: dict) -> bool:
    x1, x2, y1, y2 = box_edges(b)
    cx, cy = (blob["x1"] + blob["x2"]) / 2, (blob["y1"] + blob["y2"]) / 2
    return x1 <= cx <= x2 and y1 <= cy <= y2


def union(blobs: list[dict]) -> dict:
    return dict(x1=min(b["x1"] for b in blobs), x2=max(b["x2"] for b in blobs),
                y1=min(b["y1"] for b in blobs), y2=max(b["y2"] for b in blobs))


def draw(mp4: Path, t: float, layout: dict, named: str, boxes: list[dict], dst: Path) -> None:
    im = Image.fromarray(_frame(mp4, t).astype(np.uint8))
    d = ImageDraw.Draw(im)
    font = ImageFont.load_default(size=44)
    for key, b in layout.items():
        x1, x2, y1, y2 = box_edges(b)
        hit = key == named
        d.rectangle([x1 * W, y1 * H, x2 * W - 1, y2 * H - 1],
                    outline=(0, 160, 0) if hit else (0, 90, 255), width=10 if hit else 4)
        d.text((x1 * W + 14, y1 * H + 10), key, fill=(0, 160, 0) if hit else (0, 90, 255), font=font)
    for bb in boxes:                                   # measured object extents
        d.rectangle([bb["x1"] * W, bb["y1"] * H, bb["x2"] * W, bb["y2"] * H],
                    outline=(255, 0, 255), width=3)
    d.text((14, H - 60), f"{dst.stem}  target+1.0s frame  green=named AOI  magenta=measured object",
           fill=(0, 0, 0), font=ImageFont.load_default(size=32))
    im.save(dst)


def main() -> int:
    layouts = json.loads(LAYOUTS.read_text())
    QA.mkdir(parents=True, exist_ok=True)
    rows = list(csv.DictReader(TIMING.open(encoding="utf-8-sig")))
    fails = []
    print(f"{'trial':22s} {'t1':>6s} {'t2':>6s}  union bbox (video-frac)              "
          f"{'box':>4s}  clearance L/R/T/B (frac)")
    for r in rows:
        name = r["trial_name"][:-4]
        lay, num, obj, named = name.split("_")
        mp4 = VIDEOS / lay / f"{num}_{obj}_{named}.mp4"
        layout = layouts[lay]["boxes"]
        motion = bool(r["occlude"].strip())
        dur = _duration(mp4)
        t1 = min(float(r["target"]) + 1.0, dur - 0.1)
        t2 = dur - 0.3
        ref = _frame(mp4, REF_T) if motion else None
        picked, measured = [], []
        for t in (t1, t2):
            bl = object_blobs(mp4, t, motion, ref)
            if motion:
                cand = [b for b in bl if center_in(b, layout[named])]
            else:
                cand = [b for b in bl if center_in(b, layout[named])]
                # 4-object trials: every box must hold exactly one blob, none stray
                for k, b in layout.items():
                    if len(v := [x for x in bl if center_in(x, b)]) != 1:
                        fails.append(f"{name} t={t:.2f}: box {k} holds {len(v)} blobs, expected 1")
                stray = [b for b in bl if not any(center_in(b, x) for x in layout.values())]
                if stray:
                    fails.append(f"{name} t={t:.2f}: {len(stray)} blob(s) outside all boxes")
            if not cand:
                fails.append(f"{name} t={t:.2f}: NO object blob in named box {named}")
                continue
            picked.append(max(cand, key=lambda b: b["n"]))
        if not picked:
            continue
        u = union(picked)
        measured = picked
        bx1, bx2, by1, by2 = box_edges(layout[named])
        cl = (u["x1"] - bx1, bx2 - u["x2"], u["y1"] - by1, by2 - u["y2"])
        if min(cl) < 0:
            fails.append(f"{name}: object OUTSIDE named box {named} by {-min(cl):.3f} frac")
        print(f"{name:22s} {t1:6.2f} {t2:6.2f}  "
              f"x[{u['x1']:.3f},{u['x2']:.3f}] y[{u['y1']:.3f},{u['y2']:.3f}]  {named:>4s}  "
              + " ".join(f"{c:+.3f}" for c in cl))
        draw(mp4, t1, layout, named, measured, QA / f"{name}.png")

    print()
    if fails:
        print("FAIL:")
        for f in fails:
            print("  " + f)
        return 1
    print(f"PASS: all {len(rows)} objects inside their named AOI box; overlays in {QA}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
