"""Stage 3 -- run OWLET over a session's webcam video, with layer-1 calibration
self-derived from that session's own calibration clip.

Ported from 01_pilot/analysis/lib/owlet_runner.py. Four pilot-02 changes, all of
which change what the output means:

1. Calibration artifacts are named with a LOWER-CASED stem. OWLET.py:112 lower-cases
   the subject name but :120 matches candidate filenames case-SENSITIVELY, so a
   mixed-case stem (every firebase_doc_id) never matches its own calibration file and
   OWLET falls through to hardcoded defaults, silently, exit code 0.
2. _target_span() is per-layout: quad and diam have separate calib clips whose dwell
   targets cover different fractions of the frame.
3. The calibration window comes from the runlist (calib_video_start_sec +
   calib_to_trial01_sec), not from a beep re-derivation. One clip per session.
4. Everything keys on firebase_doc_id; panda_id is not a session key.

Layer 1 (OWLET's own raw-ratio -> 960x540 mapping) has no graceful degradation: absent
it, OWLET substitutes built-in constants ~10x off a real rig and the Y channel collapses
to a single value. Every path here raises rather than letting that happen.
"""

from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import polars as pl

_ANALYSIS_DIR = Path(__file__).resolve().parents[2]
_DEFAULT_OWLET_ROOT = _ANALYSIS_DIR.parents[1] / "OWLET"

CFR_FPS = 30

# Layer-1 pass criteria, validated on 01_pilot's 2026-08-04 self-cut-clip test. Below
# CALIB_RANGE_MIN either axis trips run_owlet_cnn.py's threshold fallback; below
# CALIB_MIN_FRAMES the extremes-finder has not seen enough of the face to trust.
CALIB_RANGE_MIN = 0.10
CALIB_MIN_FRAMES = 300

CALIB_DWELLS_JSON = _ANALYSIS_DIR / "config" / "calib_dwells.json"

_FPS_PROBE = "import cv2,sys;c=cv2.VideoCapture(sys.argv[1]);print(c.get(5));c.release()"

_CALIB_SETTINGS_COLS = [
    "min_xval", "max_xval", "range_xvals", "middle_x",
    "min_yval", "max_yval", "range_yvals", "middle_y",
    "mean", "maximum", "minimum", "mean_eyeratio",
]

# Runs inside the OWLET venv (needs cv2/torch, absent from the analysis venv). Mirrors
# run_owlet_cnn.calibrate_gaze's own computation path, printed as JSON instead of written
# straight to a settings.csv, so the caller can apply the degeneracy check first.
_CALIB_SCRIPT = """
import sys, json
sys.path.insert(0, {owlet_dir!r})
from eyetracker.calibration import LookingCalibration
calib = LookingCalibration({owlet_dir!r})
calib.calibrate_eyes(sys.argv[1])
min_x, max_x, range_x, middle_x = calib.get_min_max_hor()
min_y, max_y, range_y, middle_y = calib.get_min_max_ver()
mean_b, max_b, min_b = calib.get_eye_ratio()
mean_eyeratio = calib.get_eye_area_ratio()
print(json.dumps(dict(
    min_xval=min_x, max_xval=max_x, range_xvals=range_x, middle_x=middle_x,
    min_yval=min_y, max_yval=max_y, range_yvals=range_y, middle_y=middle_y,
    mean=mean_b, maximum=max_b, minimum=min_b, mean_eyeratio=mean_eyeratio,
    n_frames=len(calib.ver_ratios), check_range_zero=calib.check_range_zero,
)))
"""


def owlet_dir() -> Path:
    return Path(os.environ.get("DS_OWLET_ROOT", _DEFAULT_OWLET_ROOT))


def owlet_python() -> Path:
    return owlet_dir() / ".owlet-venv" / "bin" / "python3"


def calib_stem(stem: str) -> str:
    """The stem calibration artifacts must be named with, so OWLET can find them.

    OWLET.py:112 lower-cases the subject name, then :120 keeps calibration filenames
    containing it -- a plain, case-sensitive `in`. A mixed-case subject stem therefore
    never matches a case-preserving `<stem>_calibration.mp4`.
    """
    return stem.lower()


def _target_span(layout: str) -> tuple[float, float]:
    """Fraction of the frame this layout's calib dwell targets actually cover, per axis.

    The self-cut clip only ever shows gaze at the dwell positions, which sit inside the
    frame rather than at its edges -- so the min/max LookingCalibration measures is the
    range over *those targets*, not over the full frame. Per-layout because quad and diam
    are different clips with different target geometry.
    """
    trials = json.loads(CALIB_DWELLS_JSON.read_text())["trials"]
    key = f"{layout}-calib"
    if key not in trials:
        raise KeyError(
            f"No calib dwells for layout {layout!r} (key {key!r}) in {CALIB_DWELLS_JSON}. "
            f"Have: {sorted(trials)}. Regenerate with tools/extract_calib_dwells.py."
        )
    d = trials[key]["dwells"]
    xs, ys = [w["cx"] for w in d], [w["cy"] for w in d]
    return max(xs) - min(xs), max(ys) - min(ys)


def _extrapolate_to_frame(result: dict, layout: str) -> dict:
    """Widen self-derived min/max/range to full-frame extent, holding the middle fixed."""
    sx, sy = _target_span(layout)
    for axis, span in (("x", sx), ("y", sy)):
        rng = result[f"range_{axis}vals"] / span
        mid = result[f"middle_{axis}"]
        result[f"range_{axis}vals"] = rng
        result[f"min_{axis}val"] = mid - rng / 2
        result[f"max_{axis}val"] = mid + rng / 2
    return result


def _owlet_frameval(video_path) -> int | None:
    """The `frameval` OWLET will compute for this video, or None if unreadable.

    Asks OWLET's own OpenCV rather than ffprobe. OpenCV is what OWLET actually reads, and
    container metadata does not predict it: the same Chrome .webm reports
    avg_frame_rate=0/0 whole but 1000/1 once sliced, and OpenCV returns fps=1000 for both.
    """
    result = subprocess.run(
        [str(owlet_python()), "-c", _FPS_PROBE, str(video_path)],
        capture_output=True, text=True,
    )
    try:
        fps = float(result.stdout.strip())
    except ValueError:
        return None
    if not fps or fps != fps:  # 0.0 or NaN
        return None
    return max(1, math.ceil(fps) // 30)


def _needs_cfr(video_path) -> bool:
    """True when OWLET would throw frames away on this video.

    Chrome's MediaRecorder writes .webm with no usable timing, so OpenCV reports fps=1000
    and OWLET's `frameval = ceil(fps) // 30` (run_owlet_cnn.py:403) becomes 33 -- 590 gaze
    samples out of a 19,495-frame video, ~0.9 Hz not 30 Hz.

    Unreadable fps also returns True: transcoding a file that did not need it is cheap,
    silently keeping 1 frame in 33 is not.
    """
    return _owlet_frameval(video_path) != 1


def _to_cfr(src, dst, fps: int = CFR_FPS) -> Path:
    """Re-encode to a constant frame rate so OpenCV reports a real fps.

    `-c copy` is not enough; the broken timestamps live in the stream, not just the
    container, so the frames have to be re-timed.
    """
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(src), "-r", str(fps),
         "-c:v", "libx264", "-preset", "veryfast", "-an", str(dst)],
        capture_output=True, text=True, check=True,
    )
    if _needs_cfr(dst):
        raise RuntimeError(f"CFR transcode left frame rate unreadable: {dst}")
    return Path(dst)


def _existing_calib_video(video_dir: Path, stem: str) -> Path | None:
    """A calibration video in video_dir that OWLET's OWN glob would pick for this subject.

    Deliberately replicates OWLET.py:78-79,112,120 exactly -- `subname.lower() in
    filename`, case-sensitive on the filename -- rather than being case-insensitive as
    01_pilot's version was. That mismatch was the whole bug: a case-insensitive check said
    "calibration exists, nothing to do" for a file OWLET itself could not see, and the run
    fell through to hardcoded defaults with no error.
    """
    needle = calib_stem(stem)
    cands = [
        p for p in sorted(list(video_dir.glob("*.mp4")) + list(video_dir.glob("*.mov")))
        if "calibration" in p.name.lower()
        and "annotated" not in p.name.lower()
        and needle in p.stem
    ]
    return cands[0] if cands else None


def _cut_calib_clip(cfr_video, windows, dst) -> Path:
    """Cut each (start_sec, dur_sec) window from cfr_video and concatenate into dst.

    Re-encodes rather than stream-copies (-ss after -i): a keyframe-snapped stream copy can
    drift seconds, which would silently feed the wrong footage to calibration.
    """
    with tempfile.TemporaryDirectory() as td:
        parts = []
        for i, (start, dur) in enumerate(windows):
            part = Path(td) / f"part{i}.mp4"
            subprocess.run(
                ["ffmpeg", "-y", "-i", str(cfr_video), "-ss", str(start), "-t", str(dur),
                 "-c:v", "libx264", "-preset", "veryfast", "-an", str(part)],
                capture_output=True, text=True, check=True,
            )
            parts.append(part)
        if len(parts) == 1:
            shutil.copy2(parts[0], dst)
        else:
            list_file = Path(td) / "concat.txt"
            list_file.write_text("".join(f"file '{p}'\n" for p in parts))
            subprocess.run(
                ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_file),
                 "-c:v", "libx264", "-preset", "veryfast", "-an", str(dst)],
                capture_output=True, text=True, check=True,
            )
    return Path(dst)


def _run_looking_calibration(clip_path) -> dict:
    script = _CALIB_SCRIPT.format(owlet_dir=str(owlet_dir()))
    result = subprocess.run(
        [str(owlet_python()), "-c", script, str(clip_path)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"layer-1 calibration subprocess failed (rc={result.returncode}).\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    # LookingCalibration prints progress lines (detector path, fps) before the JSON --
    # the JSON is always the last line.
    return json.loads(result.stdout.strip().splitlines()[-1])


def _ensure_calibration(video_dir, stem, cfr_video, calib_windows, layout) -> dict | None:
    """Make sure a layer-1 calibration exists for `stem` in video_dir, or raise.

    If a calibration video OWLET can see already matches this subject, its own
    calibrate_gaze handles it (cached settings.csv or fresh compute) -- nothing to do.
    Otherwise cut+concatenate calib_windows from cfr_video, run LookingCalibration, and
    write `<stem.lower()>_calibration_settings.csv` -- but only if the result clears
    CALIB_RANGE_MIN / CALIB_MIN_FRAMES. A degenerate or absent calibration must never fall
    through to OWLET's hardcoded defaults; it raises instead.

    Returns the calibration diagnostics dict when freshly derived, else None.
    """
    if _existing_calib_video(video_dir, stem) is not None:
        return None

    if not calib_windows:
        raise ValueError(
            f"No layer-1 calibration for {stem}: no calibration video in {video_dir} that "
            f"OWLET's own matcher would find, and no calib_windows supplied. Refusing to "
            f"run OWLET -- without this it falls back to hardcoded defaults and the "
            f"y-channel collapses to a constant."
        )

    lower = calib_stem(stem)
    dst_video = video_dir / f"{lower}_calibration.mp4"
    # OWLET derives this path itself as calib_file.replace(".mp4", "_settings.csv")
    # (run_owlet_cnn.py:52). Keep the two in lockstep.
    dst_csv = video_dir / f"{lower}_calibration_settings.csv"

    clip = _cut_calib_clip(cfr_video, calib_windows, dst_video)
    result = _run_looking_calibration(clip)

    degenerate = (
        result["check_range_zero"] == 0
        or result["range_xvals"] < CALIB_RANGE_MIN
        or result["range_yvals"] < CALIB_RANGE_MIN
        or result["n_frames"] < CALIB_MIN_FRAMES
    )
    if degenerate:
        dst_video.unlink(missing_ok=True)
        raise ValueError(
            f"Derived layer-1 calibration for {stem} is degenerate "
            f"(range_x={result['range_xvals']:.3f}, range_y={result['range_yvals']:.3f}, "
            f"n_frames={result['n_frames']}, need >= {CALIB_RANGE_MIN} range and "
            f">= {CALIB_MIN_FRAMES} frames). Refusing to write settings and fall through "
            f"to OWLET's hardcoded defaults."
        )

    # Degeneracy is judged on the MEASURED range; extrapolating first would let a collapsed
    # channel inflate past CALIB_RANGE_MIN and get written out.
    result = _extrapolate_to_frame(result, layout)
    pl.DataFrame([{c: float(result[c]) for c in _CALIB_SETTINGS_COLS}]).select(
        _CALIB_SETTINGS_COLS
    ).write_csv(dst_csv)
    return result


def calib_windows_from_runlist(row: dict) -> list[tuple[float, float]] | None:
    """The one calibration window for a session, in its own webcam-video clock.

    pilot-02 plays a single calib clip at session start, so this is one window:
    (calib_video_start_sec, calib_to_trial01_sec) -- both already derived by stage 2 from
    the hand-verified last-beep anchor. Returns None if either is missing, which the
    caller must treat as "skip and name this session", never as a default.

    The ~+0.10s by which calib_to_trial01_sec exceeds the calib mp4's own duration is
    playback-start latency, measured independently on the trial videos. It stays in.
    """
    start = row.get("calib_video_start_sec")
    dur = row.get("calib_to_trial01_sec")
    if start is None or dur is None:
        return None
    return [(float(start), float(dur))]


def run(video_path, layout, output_csv=None, override_audio=True, calib_windows=None):
    """Run OWLET on a webcam video. Returns (output_csv_path, calib_info).

    OWLET writes <video_stem>.csv next to the input video by default; if output_csv is
    given the result is moved there afterwards.

    Inputs whose container lacks a frame rate (PANDA .webm) are transcoded to constant-rate
    MP4 first -- see _needs_cfr.

    layout: 'quad' or 'diam'. Selects the calib dwell geometry used to extrapolate the
    self-derived range to full-frame extent.

    calib_windows: [(start_sec, dur_sec), ...] in the SOURCE video's own clock, from
    calib_windows_from_runlist. Used only if no calibration OWLET can see already sits
    beside video_path.

    calib_info is the freshly-derived calibration diagnostics dict, or None if calibration
    already existed and nothing was derived this run.
    """
    video_path = Path(video_path).resolve()
    if not video_path.exists():
        raise FileNotFoundError(video_path)

    # calibrate_gaze derives its settings path as calib_file.replace(".mp4", ...), so a
    # .mov calibration file resolves to the video itself and gets handed to pd.read_csv
    # (run_owlet_cnn.py:52-55). Catch it here with a usable message.
    bad_calib = [p for p in video_path.parent.glob("*.mov")
                 if "calibration" in p.name.lower() and "annotated" not in p.name.lower()]
    if bad_calib:
        raise ValueError(
            f"Calibration video must be .mp4, not .mov: {bad_calib[0].name}\n"
            f"Remux it: ffmpeg -i {bad_calib[0].name} -c copy {bad_calib[0].stem}.mp4"
        )

    owlet_input = video_path
    scratch = None
    if _needs_cfr(video_path):
        target = video_path.with_suffix(".mp4")
        if target == video_path:
            # Already .mp4 with a high but readable fps -- that is OWLET's intended
            # downsampling, not the Chrome-webm defect, and rewriting in place would
            # clobber the source.
            pass
        else:
            # Same directory and same stem as the source, deliberately: OWLET resolves the
            # calibration video by globbing the subject video's own directory (OWLET.py:78)
            # and keeping names containing the subject's stem (OWLET.py:120). A temp dir,
            # or a renamed stem, hides it and calibration silently does not run.
            owlet_input = scratch = _to_cfr(video_path, target)

    try:
        # Must happen before the OWLET subprocess call, and while owlet_input (the CFR
        # transcode, if one was needed) still exists on disk -- calib_windows are cut from
        # it. Raises rather than letting OWLET fall through to its hardcoded defaults.
        calib_info = _ensure_calibration(
            owlet_input.parent, owlet_input.stem, owlet_input, calib_windows, layout)

        cmd = [
            str(owlet_python()),
            str(owlet_dir() / "OWLET.py"),
            "--subject_video", str(owlet_input),
        ]
        if override_audio:
            cmd.append("--override_audio_matching")

        result = subprocess.run(cmd, cwd=str(owlet_dir()), capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(
                f"OWLET failed (rc={result.returncode}).\n"
                f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
            )

        produced_csv = owlet_input.with_suffix(".csv")
        if not produced_csv.exists():
            raise FileNotFoundError(f"Expected OWLET output not found: {produced_csv}")

        annotated = owlet_input.with_name(owlet_input.stem + "_annotated.mp4")
        annotated.unlink(missing_ok=True)

        dest = Path(output_csv) if output_csv else video_path.with_suffix(".csv")
        dest.parent.mkdir(parents=True, exist_ok=True)
        if produced_csv != dest:
            shutil.move(str(produced_csv), str(dest))
        return dest, calib_info
    finally:
        if scratch is not None:
            scratch.unlink(missing_ok=True)


def study_window_sec(row: dict, trials: "pl.DataFrame") -> tuple[float, float]:
    """(start, end) of the recording that actually matters, in webcam-video time.

    From the calibration clip's first frame to the last trial's last frame. Everything
    before it is the participant getting set up; everything after is the debrief. QA
    computed over the whole file is dominated by that irrelevant footage -- on the quad
    reference session the file-wide Y-coord had 540 distinct values while the study
    window had 1, and a whole-file check called that a pass.
    """
    t = trials.filter(pl.col("firebase_doc_id") == row["firebase_doc_id"])
    trial_rows = t.filter(pl.col("kind") == "trial")
    last_end_ts = trial_rows["trial_end_ts"].max()
    first_ts = trial_rows["trial_start_ts"].min()
    end = row["video_trial_01_start_sec"] + (last_end_ts - first_ts) / 1000
    return float(row["calib_video_start_sec"]), float(end)


def qa_row(key: str, layout: str, gaze: "pl.DataFrame", calib: dict,
           window: tuple[float, float]) -> dict:
    """One row of stage-3 QA. `window` is the study window from study_window_sec.

    The load-bearing column is y_n_unique_study. OWLET replaces any ycoord outside
    [0,540] with a single constant (run_owlet_cnn.py:322-323), so a value of 1 means
    layer-1 calibration did not describe this session and every trial's vertical gaze is
    fabricated. Report it over the study window, never over the whole file.

    pct_nan is NOT frame loss: run_owlet_cnn carries the prior gaze point forward on
    short rejections, so NaN fraction badly understates how many frames were imputed.
    calib_range_y is NOT gaze quality: y is the eyelid-aperture-driven channel.
    """
    t0, t1 = window
    study = gaze.with_columns((pl.col("Time") / 1000).alias("_t")).filter(
        (pl.col("_t") >= t0) & (pl.col("_t") <= t1)
    )
    n = study.height
    return {
        "firebase_doc_id": key,
        "layout": layout,
        "calib_range_x": calib.get("range_xvals"),
        "calib_range_y": calib.get("range_yvals"),
        "n_rows_file": gaze.height,
        "n_rows_study": n,
        "y_n_unique_file": gaze["Y-coord"].n_unique(),
        "y_n_unique_study": study["Y-coord"].n_unique(),
        "x_n_unique_study": study["X-coord"].n_unique(),
        "x_median_study": study["X-coord"].median(),
        "pct_x_below_50": round(100 * study.filter(pl.col("X-coord") < 50).height / n, 1),
        "pct_x_outside_0_960": round(
            100 * study.filter((pl.col("X-coord") < 0) | (pl.col("X-coord") > 960)).height / n, 1),
        "pct_nan": round(100 * study["X-coord"].null_count() / n, 1),
        "y_collapsed": study["Y-coord"].drop_nulls().n_unique() <= 1,
    }
