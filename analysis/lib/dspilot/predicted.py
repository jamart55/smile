"""Stage 5: predicted-AOI-per-window table from pilot-02-trial-timing.csv.

Defines the study's dependent measure -- one row per (session x trial x
window) with the AOI the child *should* be looking at in that window.
Observed `aoi_tag` is joined in later by task 6 (gaze pipeline); this module
never touches gaze data and must stay importable with none on disk.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import polars as pl

_LIB = Path(__file__).resolve().parents[1]  # smile/analysis/lib
ROOT = _LIB.parent                          # smile/analysis
SMILE = ROOT.parent                         # smile/
PILOT = SMILE.parent                        # pilot/

DEFAULT_TIMING_CSV = PILOT / "pilot-02-trial-timing.csv"
DEFAULT_VIDEO_DIR = SMILE / "public" / "videos" / "trials" / "pilot02"
DEFAULT_AOI_LAYOUTS = ROOT / "config" / "aoi_layouts.json"


def load_timing_csv(path: Path = DEFAULT_TIMING_CSV) -> pl.DataFrame:
    df = pl.read_csv(path).with_columns(
        pl.col("begin").cast(pl.Float64),
        pl.col("occlude").cast(pl.Float64),
        pl.col("target").cast(pl.Float64),
        pl.col("occlude_aoi").cast(pl.Utf8),
    )
    # Every motion trial needs an occluder AOI and vice versa -- otherwise a
    # hand-edit that adds `occlude` without `occlude_aoi` silently drops that
    # window out of scoring instead of failing.
    bad = df.filter(pl.col("occlude").is_null() != pl.col("occlude_aoi").is_null())
    if not bad.is_empty():
        raise ValueError(
            "occlude and occlude_aoi must be populated together: "
            f"{bad.select('trial_name', 'occlude', 'occlude_aoi').to_dicts()}"
        )
    return df


def load_aoi_layouts(path: Path = DEFAULT_AOI_LAYOUTS) -> dict:
    return json.loads(path.read_text())


def _video_duration_sec(mp4: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
         "format=duration", "-of", "csv=p=0", str(mp4)],
        capture_output=True, text=True, check=True,
    ).stdout
    return float(out)


def assert_csv_matches_video_files(
    timing: pl.DataFrame, video_dir: Path = DEFAULT_VIDEO_DIR
) -> None:
    """CSV rows and the deployed trial mp4s must agree 1:1, per layout.

    Independent of any trials table -- catches a stimulus rename even before
    a session has ever been run against it.
    """
    csv_names = set(timing["trial_name"].to_list())
    disk_names = set()
    for layout in ("quad", "diam"):
        for mp4 in (video_dir / layout).glob("*.mp4"):
            disk_names.add(f"{layout}_{mp4.name}")
    if csv_names != disk_names:
        missing_on_disk = csv_names - disk_names
        missing_in_csv = disk_names - csv_names
        raise ValueError(
            "pilot-02-trial-timing.csv and deployed trial videos disagree: "
            f"in CSV but not on disk: {sorted(missing_on_disk)}; "
            f"on disk but not in CSV: {sorted(missing_in_csv)}"
        )


def _predicted_aoi(name: str, layout: str, aoi_layouts: dict) -> str:
    token = name.split("_")[-1]
    return _validate_aoi(token, layout, aoi_layouts, name)


def _validate_aoi(token: str, layout: str, aoi_layouts: dict, name: str) -> str:
    # OUT is not a box: it is the tag for gaze that is on the video but inside
    # no named AOI, which is where diam's occluder sits. Stage 4 must emit OUT
    # for that case and keep it distinct from off-video look-away.
    valid = set(aoi_layouts[layout]["boxes"]) | {"OUT"}
    if token not in valid:
        raise ValueError(
            f"Unknown AOI token {token!r} parsed from trial name {name!r} "
            f"(layout={layout!r}); expected one of {sorted(valid)}"
        )
    return token


def _windows_for_trial(
    begin: float,
    occlude: float | None,
    target: float,
    end: float,
    target_aoi: str,
    occlude_aoi: str | None,
) -> list[dict]:
    """(window, t_start_sec, t_end_sec, predicted_aoi, scored) rows for one trial.

    Two windows carry a prediction. The filename's AOI token is where the object
    ends up, so it predicts from `target` onward. `occlude_aoi` (timing CSV) is
    where the occluder sits, so it predicts the hidden `occlude`->`target`
    window; on diam that is `OUT`, the occluder being in the uncoded middle.
    `begin`->`occlude` is unscored -- the object is still travelling -- and kept
    only for its observed-gaze distribution.
    """
    if occlude is not None:
        return [
            {"window": "begin_to_occlude", "t_start_sec": begin, "t_end_sec": occlude,
             "predicted_aoi": None, "scored": False},
            {"window": "occlude_to_target", "t_start_sec": occlude, "t_end_sec": target,
             "predicted_aoi": occlude_aoi, "scored": True},
            {"window": "target_to_end", "t_start_sec": target, "t_end_sec": end,
             "predicted_aoi": target_aoi, "scored": True},
        ]
    # Object-recognition trial: no travel or occlusion segment.
    return [
        {"window": "begin_to_target", "t_start_sec": begin, "t_end_sec": target,
         "predicted_aoi": None, "scored": False},
        {"window": "target_to_end", "t_start_sec": target, "t_end_sec": end,
         "predicted_aoi": target_aoi, "scored": True},
    ]


def build_predicted_windows(
    trials: pl.DataFrame,
    timing: pl.DataFrame | None = None,
    aoi_layouts: dict | None = None,
    video_dir: Path = DEFAULT_VIDEO_DIR,
) -> pl.DataFrame:
    """One row per (session x trial x window), joined against the timing CSV.

    `trials` is task 3's long trials table (`01_trials.csv`): needs
    `firebase_doc_id`, `kind`, `layout`, `name`. The `00`/calib step (kind !=
    'trial') is filtered out here, not treated as a join failure.
    """
    timing = load_timing_csv() if timing is None else timing
    aoi_layouts = load_aoi_layouts() if aoi_layouts is None else aoi_layouts
    assert_csv_matches_video_files(timing, video_dir)

    steps = trials.filter(pl.col("kind") == "trial").select(
        "firebase_doc_id", "layout", "name"
    ).with_columns(
        (pl.col("layout") + "_" + pl.col("name") + ".mp4").alias("trial_name")
    )

    joined = steps.join(timing, on="trial_name", how="left")
    unmatched = joined.filter(pl.col("begin").is_null())
    if not unmatched.is_empty():
        raise ValueError(
            "Trial rows with no matching pilot-02-trial-timing.csv row: "
            f"{unmatched.select('firebase_doc_id', 'trial_name').to_dicts()}"
        )

    # One window row per (session x trial x window). A doc with two rows for the same
    # trial_name would make join_observed count every gaze sample twice -- upstream
    # returns last-visit-only, so this is a guard against that breaking, not a feature.
    repeats = joined.group_by("firebase_doc_id", "trial_name").len().filter(pl.col("len") > 1)
    if not repeats.is_empty():
        raise ValueError(
            "Repeated (firebase_doc_id, trial_name) in the trials table: "
            f"{repeats.to_dicts()}"
        )

    duration_cache: dict[str, float] = {}
    rows: list[dict] = []
    for r in joined.iter_rows(named=True):
        video_path = video_dir / r["layout"] / (r["name"] + ".mp4")
        if r["trial_name"] not in duration_cache:
            duration_cache[r["trial_name"]] = _video_duration_sec(video_path)
        end = duration_cache[r["trial_name"]]

        target_aoi = _predicted_aoi(r["name"], r["layout"], aoi_layouts)
        occlude_aoi = r["occlude_aoi"]
        if occlude_aoi is not None:
            _validate_aoi(occlude_aoi, r["layout"], aoi_layouts, r["name"])
        for w in _windows_for_trial(
            r["begin"], r["occlude"], r["target"], end, target_aoi, occlude_aoi
        ):
            rows.append(
                {
                    "firebase_doc_id": r["firebase_doc_id"],
                    "layout": r["layout"],
                    "trial_name": r["trial_name"],
                    **w,
                }
            )

    return pl.DataFrame(rows).select(
        "firebase_doc_id", "layout", "trial_name", "window",
        "t_start_sec", "t_end_sec", "predicted_aoi", "scored",
    )


def join_observed(windows: pl.DataFrame, gaze: pl.DataFrame) -> pl.DataFrame:
    """Attach stage 4's observed `aoi_tag` distribution to each predicted window.

    `gaze` is stage 4's `gaze_tagged.csv` (needs firebase_doc_id, trial_name, trial_sec,
    aoi_tag). Sessions absent from it -- skipped by stage 4 as `y_collapsed`, say -- keep
    their windows with null observations rather than dropping out of the table.

    `hit_rate` is the fraction of ON-VIDEO samples in the window that landed in the
    predicted AOI; OFFSCREEN samples are counted separately and excluded from the
    denominator, because "the child looked away" is not evidence against the prediction.
    """
    keys = ("firebase_doc_id", "trial_name")
    inside = windows.join(gaze, on=list(keys), how="left").filter(
        pl.col("trial_sec").is_not_null()
        & (pl.col("trial_sec") >= pl.col("t_start_sec"))
        & (pl.col("trial_sec") < pl.col("t_end_sec"))
    )
    agg = inside.group_by([*keys, "window"]).agg(
        pl.len().alias("n_samples"),
        (pl.col("aoi_tag") == "OFFSCREEN").sum().alias("n_offscreen"),
        (pl.col("aoi_tag") == pl.col("predicted_aoi")).sum().alias("n_hit"),
        pl.col("aoi_tag").filter(pl.col("aoi_tag") != "OFFSCREEN")
          .mode().first().alias("modal_aoi"),
    )
    return windows.join(agg, on=[*keys, "window"], how="left").with_columns(
        (pl.col("n_samples") - pl.col("n_offscreen")).alias("n_onvideo"),
    ).with_columns(
        pl.when(pl.col("n_onvideo") > 0)
          .then(pl.col("n_hit") / pl.col("n_onvideo"))
          .otherwise(None).alias("hit_rate"),
    )
