# /// script
# requires-python = ">=3.11"
# dependencies = ["marimo", "pyzmq"]
# ///
"""Stage 2 parse -- runlist + trials table for pilot-02.

Run as a script (`uv run python notebooks/01_parse.py`) or edit with marimo.
Writes data/01_runlist.csv and data/01_trials.csv.
"""

import marimo

__generated_with = "0.18.4"
app = marimo.App(width="medium", css_file="marimo.css")


@app.cell
def _():
    import os
    import sys
    from pathlib import Path

    import polars as pl

    ROOT = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(ROOT / "lib"))
    os.environ.setdefault("DS_BEEP_SOURCE", "csv")
    os.environ.setdefault("DS_BEEP_PATH", str(ROOT / "data" / "sessions.csv"))

    EXPORT = ROOT.parent / "data" / "anonymized" / "pilot-02-2026-08-21.json"
    return EXPORT, ROOT, pl


@app.cell
def _(EXPORT, ROOT, pl):
    from dspilot.loading import load_export
    from dspilot.runlist import build_tables

    ds = load_export(EXPORT)
    runlist, trials, counts, no_beep = build_tables(ds)

    (ROOT / "data").mkdir(exist_ok=True)
    runlist.write_csv(ROOT / "data" / "01_runlist.csv")
    trials.write_csv(ROOT / "data" / "01_trials.csv")

    print("filter counts:", counts)
    if not no_beep.is_empty():
        print("SKIPPED, no beep anchor:")
        print(no_beep.select("firebase_doc_id", "panda_id", "layout"))

    with pl.Config(tbl_cols=-1, tbl_width_chars=250, fmt_str_lengths=40):
        print("\n=== anchor arithmetic ===")
        print(
            runlist.select(
                "firebase_doc_id", "panda_id", "layout", "video_last_beep_sec",
                "last_beep_offset_sec", "calib_video_start_sec", "calib_start_ts",
                "trial_01_start_ts", "calib_to_trial01_sec", "video_trial_01_start_sec",
            )
        )
        print("\n=== runlist ===")
        print(runlist)
        print("\n=== trials ===")
        print(
            trials.select(
                "firebase_doc_id", "layout", "step_id", "kind", "name",
                "trial_start_ts", "trial_end_ts", "trial_duration_ms",
                "attention_start_ts", "video_trial_01_start_sec",
            )
        )
    return


if __name__ == "__main__":
    app.run()
