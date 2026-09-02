"""Stage 4 -- layer-2 correction of OWLET gaze into video-frac, then AOI tagging.

Scoped to what a pilot-02 session can actually identify (finding of 2026-09-02, see
`.claude/CLAUDE.md`). Two departures from `01_pilot`'s `calib_from_attention.py`, both
forced by measurement, not preference:

1. **The attention-getters spin at frame centre.** All three clips stay inside
   x 0.477-0.525 / y 0.459-0.540, so an AG window is one known point at (0.5, 0.5) --
   it carries no gain information, and `(pred < .5) == (known < .5)` decode over AG
   dwells scores targets sitting *on* the midline. AG windows are therefore carried as
   an observed-gaze distribution and are **not** fit input; decode is calib-only.
2. **No drift term.** The only known-position data with spatial spread is the 4 calib
   dwells inside the first ~27s. Gain+offset on 4 points is already 2 params from 4
   observations; a third term fit against a constant-target regressor would absorb
   OWLET's centre bias and call it drift.

Cross-validation is leave-one-*dwell*-out, not leave-one-period-out. With a single calib
period there is no period to hold out -- `01_pilot`'s note that this overstates accuracy
(it leaks local drift) still applies, so read `decode_*_calib` as an upper bound.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import polars as pl

_ANALYSIS_DIR = Path(__file__).resolve().parents[2]
CALIB_DWELLS_JSON = _ANALYSIS_DIR / "config" / "calib_dwells.json"
AOI_LAYOUTS_JSON = _ANALYSIS_DIR / "config" / "aoi_layouts.json"

# In-clip visible span of the AG object, centroid-tracked on all three clips: it fades
# in ~1.2s and out ~5.9s of a 7.07s clip.
AG_WINDOW_SEC = (1.5, 5.5)
AG_KNOWN = (0.5, 0.5)

DWELL_HALF_WINDOW_SEC = 1.2
MIN_DWELL_SAMPLES = 10

# A dwell whose known position sits on the midline carries no side information: the
# decode test is `(pred < .5) == (known < .5)`, so scoring it is a coin flip. diam's calib
# clip puts its T/B dwells at x~0.5 and its L/R dwells at y~0.5, so only 2 of its 4 dwells
# are informative per axis and NONE are informative on both -- decode_quadrant_calib is
# undefined there, and must read NaN rather than a number.
MIDLINE_MARGIN = 0.1

# Beyond this far outside the frame the sample is look-away, not "on the video but in no
# box". The distinction matters: diam's occluder is predicted as OUT, so OUT has to mean
# something a child can actually be doing.
OFFVIDEO_MARGIN = 0.2


def load_dwells(path: Path = CALIB_DWELLS_JSON) -> dict:
    return json.loads(Path(path).read_text())["trials"]


def load_layouts(path: Path = AOI_LAYOUTS_JSON) -> dict:
    return json.loads(Path(path).read_text())


def _anchor(trials: pl.DataFrame) -> tuple[float, float]:
    """(anchor_sec, t0_ms) -- webcam-video time of trial 01, and its wall clock."""
    steps = trials.filter(pl.col("kind") == "trial")
    if steps.is_empty():
        raise ValueError("trials has no kind=='trial' row -- cannot anchor video time")
    return float(trials["video_trial_01_start_sec"][0]), float(steps["trial_start_ts"][0])


def video_sec(ts_ms: float, anchor_sec: float, t0_ms: float) -> float:
    return anchor_sec + (ts_ms - t0_ms) / 1000.0


def dwell_observations(
    gaze: pl.DataFrame, trials: pl.DataFrame, dwells: dict
) -> pl.DataFrame:
    """Known vs observed gaze per dwell window, for one session.

    Calib rows anchor on `trial_start_ts` (the clip *is* the step); AG rows anchor on
    `attention_start_ts` -- in pilot-02 the attention-getter FOLLOWS its trial, so that
    window sits after the trial, not before it.

    `in_fit` marks the rows `fit_correction` may use: calib dwells only.
    """
    anchor_sec, t0 = _anchor(trials)
    gt = gaze["Time"].to_numpy() / 1000.0
    gx = gaze["X-coord"].to_numpy()
    gy = gaze["Y-coord"].to_numpy()

    def observed(mid: float):
        m = (gt >= mid - DWELL_HALF_WINDOW_SEC) & (gt < mid + DWELL_HALF_WINDOW_SEC)
        xs, ys = gx[m], gy[m]
        ok = ~(np.isnan(xs) | np.isnan(ys))
        if ok.sum() < MIN_DWELL_SAMPLES:
            return None
        return float(np.median(xs[ok])), float(np.median(ys[ok])), int(ok.sum())

    rows = []
    for r in trials.iter_rows(named=True):
        if r["kind"] == "calib":
            key = r["name"]
            if key not in dwells:
                continue
            start = video_sec(r["trial_start_ts"], anchor_sec, t0)
            spans = [
                ((d["t_start"] + d["t_end"]) / 2, d["cx"], d["cy"])
                for d in dwells[key]["dwells"]
            ]
            kind, in_fit = "calib", True
        else:
            if r["attention_start_ts"] is None:
                continue
            key = Path(str(r["attention"])).stem
            start = video_sec(r["attention_start_ts"], anchor_sec, t0)
            spans = [(sum(AG_WINDOW_SEC) / 2, *AG_KNOWN)]
            kind, in_fit = "ag", False

        for i, (offset, kx, ky) in enumerate(spans):
            mid = start + offset
            o = observed(mid)
            if o is None:
                continue
            rows.append({
                "period": key, "dwell_idx": i, "t_mid": mid,
                "kx": kx, "ky": ky, "ox": o[0], "oy": o[1], "n": o[2],
                "kind": kind, "in_fit": in_fit,
            })
    return pl.DataFrame(rows, schema={
        "period": pl.Utf8, "dwell_idx": pl.Int64, "t_mid": pl.Float64,
        "kx": pl.Float64, "ky": pl.Float64, "ox": pl.Float64, "oy": pl.Float64,
        "n": pl.Int64, "kind": pl.Utf8, "in_fit": pl.Boolean,
    })


def _lstsq(o: np.ndarray, k: np.ndarray) -> np.ndarray:
    beta, *_ = np.linalg.lstsq(np.column_stack([o, np.ones(len(o))]), k, rcond=None)
    return beta


def fit_correction(obs: pl.DataFrame) -> dict:
    """gain+offset per axis, fit on `in_fit` rows only, plus leave-one-dwell-out decode.

    Decode is scored only over dwells whose known position is off the midline by at least
    MIDLINE_MARGIN -- see that constant; on diam that leaves 2 per axis and 0 for the
    combined score, which reports NaN.

    `gain_sign_ok` is the first thing to read: OWLET's 960x540 output should increase
    with screen position, so both gains must be positive. A negative gain means the
    channel is anti-correlated with where the subject was actually looking, and no
    affine correction rescues that.
    """
    fit_rows = obs.filter(pl.col("in_fit"))
    n_calib, n_ag = fit_rows.height, obs.filter(pl.col("kind") == "ag").height
    if n_calib < 3:
        raise ValueError(
            f"fit needs >=3 calib dwells (2 params + 1), have {n_calib}. "
            "A session whose calib dwells did not yield gaze cannot be corrected."
        )

    k = {"x": fit_rows["kx"].to_numpy(), "y": fit_rows["ky"].to_numpy()}
    o = {"x": fit_rows["ox"].to_numpy(), "y": fit_rows["oy"].to_numpy()}
    coef = {ax: _lstsq(o[ax], k[ax]).tolist() for ax in ("x", "y")}

    informative = {ax: np.abs(k[ax] - 0.5) >= MIDLINE_MARGIN for ax in ("x", "y")}
    both = informative["x"] & informative["y"]
    correct = {"x": 0, "y": 0, "q": 0}
    for i in range(n_calib):
        tr = np.arange(n_calib) != i
        ok = {}
        for ax in ("x", "y"):
            b = _lstsq(o[ax][tr], k[ax][tr])
            ok[ax] = bool((b[0] * o[ax][i] + b[1] < 0.5) == (k[ax][i] < 0.5))
            correct[ax] += ok[ax] and informative[ax][i]
        correct["q"] += ok["x"] and ok["y"] and both[i]

    def rate(hits: int, denom: int) -> float:
        return hits / denom if denom else float("nan")

    return {
        "coef_x": coef["x"], "coef_y": coef["y"],
        "gain_x": coef["x"][0], "gain_y": coef["y"][0],
        "gain_sign_ok": coef["x"][0] > 0 and coef["y"][0] > 0,
        "decode_lr_calib": rate(correct["x"], int(informative["x"].sum())),
        "decode_tb_calib": rate(correct["y"], int(informative["y"].sum())),
        "decode_quadrant_calib": rate(correct["q"], int(both.sum())),
        "n_informative_x": int(informative["x"].sum()),
        "n_informative_y": int(informative["y"].sum()),
        "n_informative_both": int(both.sum()),
        "n_dwells_calib": n_calib, "n_dwells_ag": n_ag,
    }


def apply_correction(x, y, coef_x, coef_y):
    """OWLET 960x540 -> video-frac (fraction of the 1920x1080 trial frame)."""
    return coef_x[0] * np.asarray(x) + coef_x[1], coef_y[0] * np.asarray(y) + coef_y[1]


def frac_boxes(layout_dict: dict) -> dict:
    return {
        name: (s["cx"] - s["w"] / 2, s["cy"] - s["h"] / 2,
               s["cx"] + s["w"] / 2, s["cy"] + s["h"] / 2)
        for name, s in layout_dict.items()
    }


def tag_aoi(x: float, y: float, boxes: dict, margin: float = OFFVIDEO_MARGIN) -> str:
    """'OFFSCREEN' (off the video), 'OUT' (on it, in no box), or the box name."""
    if np.isnan(x) or np.isnan(y):
        return "OFFSCREEN"
    if not (-margin <= x <= 1 + margin and -margin <= y <= 1 + margin):
        return "OFFSCREEN"
    for name, (x0, y0, x1, y1) in boxes.items():
        if x0 <= x < x1 and y0 <= y < y1:
            return name
    return "OUT"


def tag_gaze(
    gaze: pl.DataFrame, trials: pl.DataFrame, fit: dict, boxes: dict
) -> pl.DataFrame:
    """One row per gaze sample inside a trial, corrected to video-frac and AOI-tagged.

    `trial_sec` is measured from `trial_start_ts`, which is when the browser *started*
    the video element -- ~0.1-0.3s before its first frame renders (CLAUDE.md). Stage 5's
    windows are in video content time, so joins carry that much slop. Not modelled: it is
    below the diam anchor's own +/-0.2s uncertainty.
    """
    anchor_sec, t0 = _anchor(trials)
    gt = gaze["Time"].to_numpy() / 1000.0
    xf, yf = apply_correction(
        gaze["X-coord"].to_numpy(), gaze["Y-coord"].to_numpy(),
        fit["coef_x"], fit["coef_y"],
    )

    rows = []
    for r in trials.filter(pl.col("kind") == "trial").iter_rows(named=True):
        start = video_sec(r["trial_start_ts"], anchor_sec, t0)
        end = video_sec(r["trial_end_ts"], anchor_sec, t0)
        m = (gt >= start) & (gt < end)
        for t, x, y in zip(gt[m], xf[m], yf[m]):
            rows.append({
                "firebase_doc_id": r["firebase_doc_id"],
                "trial_name": f"{r['layout']}_{r['name']}.mp4",
                "video_sec": float(t), "trial_sec": float(t - start),
                "x_frac": float(x), "y_frac": float(y),
                "aoi_tag": tag_aoi(x, y, boxes),
            })
    return pl.DataFrame(rows, schema={
        "firebase_doc_id": pl.Utf8, "trial_name": pl.Utf8, "video_sec": pl.Float64,
        "trial_sec": pl.Float64, "x_frac": pl.Float64, "y_frac": pl.Float64,
        "aoi_tag": pl.Utf8,
    })
