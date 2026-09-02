# /// script
# requires-python = ">=3.11"
# dependencies = ["marimo", "pyzmq"]
# ///
"""Stage 3 -- run OWLET per session, with self-derived layer-1 calibration.

Reads data/01_runlist.csv, writes data/participants/<firebase_doc_id>/owlet_raw.csv,
data/02_owlet_qa.csv, and one raw-gaze PNG per session under data/qa/owlet/.

Slow: OWLET runs a CNN over every frame of a ~10 minute recording. Sessions whose
owlet_raw.csv is already newer than their video are skipped.

Run as a script (`uv run python notebooks/02_owlet.py`) or edit with marimo.
"""

import marimo

__generated_with = "0.18.4"
app = marimo.App(width="medium", css_file="marimo.css")


@app.cell
def _():
    import sys
    from pathlib import Path

    import polars as pl

    ROOT = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(ROOT / "lib"))
    return ROOT, pl


@app.cell
def _(ROOT, pl):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    from dspilot.config import video_path
    from dspilot.owlet import (
        calib_windows_from_runlist, qa_row, run, study_window_sec,
    )

    runlist = pl.read_csv(ROOT / "data" / "01_runlist.csv")
    trials = pl.read_csv(ROOT / "data" / "01_trials.csv")
    qa_dir = ROOT / "data" / "qa" / "owlet"
    qa_dir.mkdir(parents=True, exist_ok=True)

    qa_rows = []
    for row in runlist.iter_rows(named=True):
        key, layout = row["firebase_doc_id"], row["layout"]
        src = video_path(key)
        out_csv = ROOT / "data" / "participants" / key / "owlet_raw.csv"

        if out_csv.exists():
            # skip-existing cannot tell "already processed" from "processed from a
            # DIFFERENT video" -- a re-test drops a new webm beside a stale
            # owlet_raw.csv, and stage 4 would then tag the old session's gaze with
            # the new session's anchor. Silent and wrong.
            if out_csv.stat().st_mtime < src.stat().st_mtime:
                print(f"[STALE] {key}: {out_csv.name} predates {src.name} -- delete it "
                      f"to re-run OWLET, or restore the video it was made from.")
            else:
                print(f"[skip-existing] {key}: {out_csv.name} already present")
        else:
            windows = calib_windows_from_runlist(row)
            if windows is None:
                print(f"[skip-no-anchor] {key}: runlist has no calib_video_start_sec / "
                      f"calib_to_trial01_sec -- cannot locate the calibration clip in "
                      f"this recording. Not defaulting.")
                continue
            print(f"[run] {key} ({layout}) <- {src.name}, calib window {windows[0]}")
            try:
                _, calib_info = run(src, layout, output_csv=out_csv, calib_windows=windows)
            except Exception as e:  # one bad session must not kill the rest
                print(f"  ERROR: {e}")
                continue
            print(f"  -> {out_csv}")

        gaze = pl.read_csv(out_csv)
        settings_csv = next(src.parent.glob("*_calibration_settings.csv"), None)
        calib = pl.read_csv(settings_csv).row(0, named=True) if settings_csv else {}
        window = study_window_sec(row, trials)
        qa_rows.append(qa_row(key, layout, gaze, calib, window))

        t = gaze["Time"] / 1000
        fig, axes = plt.subplots(2, 1, figsize=(12, 6), sharex=True)
        for ax, col in zip(axes, ("X-coord", "Y-coord")):
            ax.plot(t, gaze[col], lw=0.4)
            ax.set_ylabel(col)
            ax.axvspan(row["calib_video_start_sec"],
                       row["calib_video_start_sec"] + row["calib_to_trial01_sec"],
                       color="tab:orange", alpha=0.35, label="calib clip")
            ax.axvspan(*window, color="tab:blue", alpha=0.08, label="study window")
        axes[0].legend(loc="upper right")
        axes[0].set_title(f"{key} ({layout}) -- OWLET raw gaze")
        axes[1].set_xlabel("webcam video time (s)")
        fig.tight_layout()
        fig.savefig(qa_dir / f"{key}_raw_gaze.png", dpi=150)
        plt.close(fig)

    qa = pl.DataFrame(qa_rows)
    qa.write_csv(ROOT / "data" / "02_owlet_qa.csv")
    with pl.Config(tbl_rows=-1, tbl_cols=-1, tbl_width_chars=250):
        print(qa)
    for r in qa.filter(pl.col("y_collapsed")).iter_rows(named=True):
        print(f"[COLLAPSE] {r['firebase_doc_id']} ({r['layout']}): Y-coord is a single "
              f"constant across the whole study window -- OWLET's layer-1 calibration does "
              f"not describe this session and every trial's vertical gaze is fabricated. "
              f"Do not pass this session to stage 4.")
    return


if __name__ == "__main__":
    app.run()
