# /// script
# requires-python = ">=3.11"
# dependencies = ["marimo", "pyzmq"]
# ///
"""Stage 4 -- fit the layer-2 correction per session, tag gaze against the AOI boxes.

Reads data/01_runlist.csv, data/01_trials.csv, data/02_owlet_qa.csv and each session's
owlet_raw.csv. Writes data/participants/<firebase_doc_id>/gaze_tagged.csv,
data/03_calib_fit.csv, and one fit-QA PNG per session under data/qa/calib_fit/.

Sessions flagged `y_collapsed` by stage 3 are SKIPPED, not fit: an affine map cannot
recover position from a constant regressor.

Run as a script (`uv run python notebooks/03_aoi_mapping.py`) or edit with marimo.
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
    import numpy as np

    from dspilot.aoi_map import (
        dwell_observations, fit_correction, frac_boxes, load_dwells, load_layouts,
        tag_gaze,
    )

    runlist = pl.read_csv(ROOT / "data" / "01_runlist.csv")
    trials_all = pl.read_csv(ROOT / "data" / "01_trials.csv")
    qa = pl.read_csv(ROOT / "data" / "02_owlet_qa.csv")
    dwells, layouts = load_dwells(), load_layouts()

    qa_dir = ROOT / "data" / "qa" / "calib_fit"
    qa_dir.mkdir(parents=True, exist_ok=True)

    collapsed = set(qa.filter(pl.col("y_collapsed"))["firebase_doc_id"].to_list())
    fits = []
    for row in runlist.iter_rows(named=True):
        key, layout = row["firebase_doc_id"], row["layout"]
        if key in collapsed:
            print(f"[skip-collapsed] {key} ({layout}): stage 3 flagged y_collapsed -- "
                  f"an affine fit on a constant regressor is not a calibration.")
            continue

        raw = ROOT / "data" / "participants" / key / "owlet_raw.csv"
        if not raw.exists():
            print(f"[skip-no-gaze] {key}: {raw} missing -- run notebooks/02_owlet.py")
            continue

        gaze = pl.read_csv(raw)
        trials = trials_all.filter(pl.col("firebase_doc_id") == key)
        obs = dwell_observations(gaze, trials, dwells)
        try:
            fit = fit_correction(obs)
        except ValueError as e:  # one bad session must not kill the rest
            print(f"[skip-unfittable] {key}: {e}")
            continue

        obs.write_csv(ROOT / "data" / "participants" / key / "calib_obs.csv")
        boxes = frac_boxes(layouts[layout]["boxes"])
        tagged = tag_gaze(gaze, trials, fit, boxes)
        tagged.write_csv(ROOT / "data" / "participants" / key / "gaze_tagged.csv")

        fits.append({"firebase_doc_id": key, "layout": layout, **{
            k: (str(v) if isinstance(v, list) else v) for k, v in fit.items()}})

        print(f"[fit] {key} ({layout}) gain_x={fit['gain_x']:+.5f} "
              f"gain_y={fit['gain_y']:+.5f} sign_ok={fit['gain_sign_ok']} "
              f"decode_quadrant_calib={fit['decode_quadrant_calib']:.2f} "
              f"({fit['n_dwells_calib']} calib dwells, {fit['n_dwells_ag']} AG centres)")
        if not fit["gain_sign_ok"]:
            print(f"  [WARN] a fitted gain is negative -- OWLET's output moves OPPOSITE "
                  f"to where the subject was looking on this session. Every tag below "
                  f"is derived from that fit; read them as diagnostics, not gaze.")
        print(tagged.group_by("aoi_tag").len().sort("len", descending=True))

        fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))
        for ax, axis, (o_col, k_col) in zip(axes, "xy", (("ox", "kx"), ("oy", "ky"))):
            c = obs.filter(pl.col("in_fit"))
            a = obs.filter(pl.col("kind") == "ag")
            ax.scatter(c[o_col], c[k_col], s=70, color="tab:blue",
                       label=f"calib dwells (n={c.height}, FIT)")
            ax.scatter(a[o_col], a[k_col], s=40, color="0.6", marker="x",
                       label=f"AG centres (n={a.height}, not fit)")
            xs = np.linspace(0, 960 if axis == "x" else 540, 50)
            b = fit[f"coef_{axis}"]
            ax.plot(xs, b[0] * xs + b[1], color="tab:red", lw=1,
                    label=f"fit: {b[0]:+.5f}·o {b[1]:+.3f}")
            ax.axhline(0.5, color="0.8", lw=0.8)
            ax.set_xlabel(f"observed OWLET {axis} (of {960 if axis == 'x' else 540})")
            ax.set_ylabel(f"known {axis} (video-frac)")
            ax.set_ylim(-0.1, 1.1)
            ax.legend(fontsize=7)
        fig.suptitle(f"{key} ({layout}) -- layer-2 fit. Slope rests on the blue points "
                     f"only; AG targets all sit at 0.5.", fontsize=9)
        fig.tight_layout()
        fig.savefig(qa_dir / f"{key}_calib_fit_qa.png", dpi=150)
        plt.close(fig)

    fit_df = pl.DataFrame(fits)
    if fit_df.is_empty():
        print("\nNo session was fittable. Nothing written to data/03_calib_fit.csv.")
    else:
        fit_df.write_csv(ROOT / "data" / "03_calib_fit.csv")
        with pl.Config(tbl_rows=-1, tbl_cols=-1, tbl_width_chars=250):
            print(fit_df)
    return


if __name__ == "__main__":
    app.run()
