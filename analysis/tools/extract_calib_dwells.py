"""Extract dwell positions (known screen locations) from the calibration videos.

Each calib video shows a single small object on a white background, moving to a sequence
of fixed positions and dwelling at each (matching one AOI layout). This script tracks the
object's centroid per frame (threshold on distance from white), segments the track into
low-speed "dwell" runs, and writes their median position + time window in the same schema
as attention_dwells.json — see analysis/lib/calib_from_attention.py, which merges the two.

pilot-02 has one calib clip per layout, keyed by layout name (quad-calib / diam-calib), not
by the old 100/101 trial ids. The two clips differ in target geometry, which is why
dspilot.owlet._target_span() is per-layout.

Run with the OWLET venv (numpy + opencv; the analysis venv has neither):
    OWLET/.owlet-venv/bin/python3 smile/analysis/tools/extract_calib_dwells.py

Writes smile/analysis/config/calib_dwells.json and
smile/analysis/data/qa/calib_dwells_contact_sheet.png. The contact sheet MUST be looked at
before trusting the JSON -- a wrong cx/cy biases every downstream calibration fit without
raising an error.
"""
import argparse
import json
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_VIDEOS_DIR = ROOT / "smile" / "public" / "videos" / "trials" / "pilot02" / "calib"
DEFAULT_OUT_JSON = Path(__file__).resolve().parents[1] / "config" / "calib_dwells.json"
DEFAULT_CONTACT_SHEET = (Path(__file__).resolve().parents[1] / "data" / "qa"
                         / "calib_dwells_contact_sheet.png")

# key -> (filename, layout, axes the dwells must span, min expected dwell count)
VIDEOS = {
    "quad-calib": ("quad-calib.mp4", "quad", "xy", 4),
    "diam-calib": ("diam-calib.mp4", "diam", "xy", 4),
}

WHITE_DIST_THRESH = 30       # pixel counts as "object" if max-channel distance from white > this
MIN_OBJECT_PIXELS = 50       # ignore frames with fewer non-white pixels (nothing detected)
MIN_DWELL_SEC = 1.0


def track_centroids(video_path):
    cap = cv2.VideoCapture(str(video_path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    frames = []
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        dist = (255 - frame.astype(np.int16)).max(axis=2)
        mask = dist > WHITE_DIST_THRESH
        n = int(mask.sum())
        if n < MIN_OBJECT_PIXELS:
            frames.append((np.nan, np.nan))
            continue
        ys, xs = np.nonzero(mask)
        h, w = frame.shape[:2]
        frames.append((xs.mean() / w, ys.mean() / h))
    cap.release()
    return np.array(frames), fps


def segment_dwells(track, fps):
    """track: Nx2 array of (cx_frac, cy_frac), NaN where nothing detected.

    The object jitters/spins in place during a dwell (per attention_dwells.json's precedent
    for the AG object), so frame-to-frame speed doesn't reliably separate dwell from
    transition -- empirically, detection dropout (no non-white pixels -> NaN) does: the
    object is invisible/off-frame between dwell positions. So a dwell is just a contiguous
    run of detected frames long enough to be real, median position over the run averaging
    out the in-place jitter.
    """
    valid = ~np.isnan(track[:, 0])
    dwells = []
    run_start = None
    for i, v in enumerate(valid):
        if v and run_start is None:
            run_start = i
        elif not v and run_start is not None:
            _maybe_add_dwell(dwells, track, fps, run_start, i - 1)
            run_start = None
    if run_start is not None:
        _maybe_add_dwell(dwells, track, fps, run_start, len(valid) - 1)
    return dwells


def _maybe_add_dwell(dwells, track, fps, i0, i1):
    if (i1 - i0 + 1) / fps < MIN_DWELL_SEC:
        return
    seg = track[i0:i1 + 1]
    dwells.append({
        "t_start": round(i0 / fps, 3),
        "t_end": round((i1 + 1) / fps, 3),
        "cx": round(float(np.median(seg[:, 0])), 4),
        "cy": round(float(np.median(seg[:, 1])), 4),
        "_mid_frame": (i0 + i1) // 2,
    })


def build_contact_sheet(video_path, dwells, out_frames):
    cap = cv2.VideoCapture(str(video_path))
    for tid, idx, d in out_frames:
        cap.set(cv2.CAP_PROP_POS_FRAMES, d["_mid_frame"])
        ok, frame = cap.read()
        if not ok:
            continue
        h, w = frame.shape[:2]
        cx_px, cy_px = int(d["cx"] * w), int(d["cy"] * h)
        cv2.drawMarker(frame, (cx_px, cy_px), (0, 0, 255), cv2.MARKER_CROSS, 40, 3)
        label = f"{tid} dwell{idx} cx={d['cx']:.3f} cy={d['cy']:.3f}"
        cv2.putText(frame, label, (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 255), 3)
        small = cv2.resize(frame, (w // 3, h // 3))
        yield small
    cap.release()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--videos-dir", type=Path, default=DEFAULT_VIDEOS_DIR)
    ap.add_argument("--out-json", type=Path, default=DEFAULT_OUT_JSON)
    ap.add_argument("--out-contact-sheet", type=Path, default=DEFAULT_CONTACT_SHEET)
    args = ap.parse_args()

    result = {}
    all_panels = []
    for tid, (fname, layout, axes, min_dwells) in VIDEOS.items():
        video_path = args.videos_dir / fname
        if not video_path.exists():
            raise SystemExit(f"missing {video_path}")
        track, fps = track_centroids(video_path)
        dwells = segment_dwells(track, fps)
        print(f"{tid} ({fname}): {len(dwells)} dwells, fps={fps:.1f}, frames={len(track)}")
        for i, d in enumerate(dwells):
            print(f"    dwell {i}: t={d['t_start']:.1f}-{d['t_end']:.1f}s cx={d['cx']:.3f} cy={d['cy']:.3f}")

        if len(dwells) < min_dwells:
            raise SystemExit(f"{tid}: only {len(dwells)} dwells detected (<{min_dwells}) -- stopping, "
                              f"check MIN_OBJECT_PIXELS/MIN_DWELL_SEC, not writing JSON")
        cxs = [d["cx"] for d in dwells]
        cys = [d["cy"] for d in dwells]
        if "x" in axes and not (min(cxs) < 0.4 and max(cxs) > 0.6):
            raise SystemExit(f"{tid}: cx values {cxs} don't span both halves of the frame -- stopping")
        if "y" in axes and not (min(cys) < 0.4 and max(cys) > 0.6):
            raise SystemExit(f"{tid}: cy values {cys} don't span both halves of the frame -- stopping")

        result[tid] = {"layout": layout, "dwells": [
            {k: v for k, v in d.items() if not k.startswith("_")} for d in dwells
        ]}
        all_panels.extend(build_contact_sheet(video_path, dwells, [(tid, i, d) for i, d in enumerate(dwells)]))

    args.out_contact_sheet.parent.mkdir(parents=True, exist_ok=True)
    if all_panels:
        cols = 3
        rows = -(-len(all_panels) // cols)
        ph, pw = all_panels[0].shape[:2]
        sheet = np.full((rows * ph, cols * pw, 3), 255, dtype=np.uint8)
        for i, panel in enumerate(all_panels):
            r, c = divmod(i, cols)
            sheet[r * ph:(r + 1) * ph, c * pw:(c + 1) * pw] = panel
        cv2.imwrite(str(args.out_contact_sheet), sheet)
        print(f"Wrote {args.out_contact_sheet}")

    out = {
        "_comment": ("Known screen positions the pilot-02 calibration clips dwell at, one per "
                     "layout. Positions in fractional coords of the 1920x1080 trial frame "
                     "(video-frac, same space as aoi_layouts.json). Derived by centroid "
                     "tracking of smile/public/videos/trials/pilot02/calib/*.mp4 "
                     "(tools/extract_calib_dwells.py) and visually confirmed at each dwell's "
                     "midpoint frame via data/qa/calib_dwells_contact_sheet.png. t_start/t_end "
                     "are seconds from that clip's own start."),
        "trials": result,
    }
    args.out_json.write_text(json.dumps(out, indent=2))
    print(f"Wrote {args.out_json}")


if __name__ == "__main__":
    main()
