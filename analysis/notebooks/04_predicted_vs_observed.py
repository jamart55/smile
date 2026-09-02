# /// script
# requires-python = ">=3.11"
# dependencies = ["marimo", "pyzmq"]
# ///
"""Stage 5 -- predicted-AOI-per-window table for pilot-02.

Reads task 3's data/01_trials.csv + pilot-02-trial-timing.csv, writes
data/04_predicted_windows.csv, then joins stage 4's per-sample tags
(participants/<id>/gaze_tagged.csv) onto each window. Sessions stage 4 skipped
keep their windows with null observations.

Run as a script (`uv run python notebooks/04_predicted_vs_observed.py`) or
edit with marimo.
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
    from dspilot.predicted import build_predicted_windows, join_observed

    trials = pl.read_csv(ROOT / "data" / "01_trials.csv")
    windows = build_predicted_windows(trials)

    tagged = [pl.read_csv(p) for p in
              sorted((ROOT / "data" / "participants").glob("*/gaze_tagged.csv"))]
    gaze = pl.concat(tagged) if tagged else None
    if gaze is None:
        print("[no gaze] no participants/*/gaze_tagged.csv -- run notebooks/03_aoi_mapping.py")
    else:
        windows = join_observed(windows, gaze)
        missing = sorted(set(windows["firebase_doc_id"]) - set(gaze["firebase_doc_id"]))
        for key in missing:
            print(f"[no gaze] {key}: windows kept with null observations (stage 4 skipped it)")

    (ROOT / "data").mkdir(exist_ok=True)
    windows.write_csv(ROOT / "data" / "04_predicted_windows.csv")

    with pl.Config(tbl_rows=-1, tbl_cols=-1, tbl_width_chars=250):
        print(f"{windows.height} rows ({windows['firebase_doc_id'].n_unique()} sessions)")
        print(windows.sort("firebase_doc_id", "trial_name", "t_start_sec"))
    if gaze is not None:
        scored = windows.filter(pl.col("scored") & pl.col("hit_rate").is_not_null())
        print("\nScored windows with gaze: mean hit_rate by layout/window")
        print(scored.group_by("layout", "window").agg(
            pl.col("hit_rate").mean().alias("mean_hit_rate"),
            pl.col("n_onvideo").sum().alias("n_onvideo"),
            pl.len().alias("n_windows"),
        ).sort("layout", "window"))
    return (windows,)


if __name__ == "__main__":
    app.run()
