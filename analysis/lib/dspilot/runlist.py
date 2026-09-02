"""Stage 2 parse: session runlist + long trials table for pilot-02.

Session key is `firebase_doc_id`, not `panda_id` -- one researcher can run
the study more than once (both reference sessions share `17291H`), and every
artifact path, beep anchor and webcam video keys off the doc id.
"""

from __future__ import annotations

import polars as pl
from smiledata import SmileDataset

from .beeps import load_beeps
from .config import LAST_BEEP_OFFSET_SEC, video_path
from .loading import last_visit_only

TRIALS_PAGE = "trials"
N_TRIALS_EXPECTED = 8
PREVIEW_PANDA_ID = "PANDA_TEST_001"


def _last_updated_sec(p) -> float | None:
    lu = p.raw_data.get("lastUpdated")
    if isinstance(lu, dict):
        return lu.get("_seconds", 0) + lu.get("_nanoseconds", 0) / 1e9
    return None


def _session_meta(ds: SmileDataset) -> pl.DataFrame:
    """Per-session attributes smiledata has no concept of, keyed on doc id."""
    rows = []
    for p in ds:
        fs = p.get_form("enter_fullscreen") or {}
        try:
            webcam = str(video_path(p.id))
        except (FileNotFoundError, ValueError) as e:
            # Not fatal: the runlist is built before videos are downloaded.
            # Recorded verbatim so the gap is visible in the CSV, not implied.
            webcam = f"UNRESOLVED: {e}"
        rows.append(
            {
                "firebase_doc_id": p.id,
                "panda_id": p.raw_data.get("panda_id"),
                "webcam_video": webcam,
                "layout": p.conditions.get("layout"),
                "consented": p.consented,
                "done": p.done,
                "withdrawn": p.withdrawn,
                "last_updated_sec": _last_updated_sec(p),
                "git_branch": p.git_branch,
                "git_commit": p.git_commit,
                "timezone": p.timezone,
                "recording_start_ts": fs.get("recording_start_ts"),
                "screen_width": fs.get("screen_width"),
                "screen_height": fs.get("screen_height"),
                "inner_width": fs.get("inner_width"),
                "inner_height": fs.get("inner_height"),
                "device_pixel_ratio": fs.get("device_pixel_ratio"),
            }
        )
    return pl.DataFrame(rows)


def raw_steps_df(ds: SmileDataset) -> pl.DataFrame:
    """All trial-page rows, last visit only, keyed on firebase_doc_id.

    `kind` defaults to 'trial' -- pre-calib-video records lack the key and
    must never be rejected for it.
    """
    df = ds.to_page_data_df(TRIALS_PAGE)
    if df.is_empty():
        return df
    df = last_visit_only(df)  # must precede any per-session row counting
    if "kind" not in df.columns:
        df = df.with_columns(pl.lit("trial").alias("kind"))
    return df.with_columns(pl.col("kind").fill_null("trial")).rename(
        {"participant_id": "firebase_doc_id", "id": "step_id"}
    )


def select_sessions(ds: SmileDataset, steps: pl.DataFrame) -> tuple[list[str], dict[str, int]]:
    """Session keys passing every filter, plus a per-stage count trail."""
    counts = {"loaded": len(ds)}

    ds = ds.complete_only()
    counts["complete_only"] = len(ds)

    meta = _session_meta(ds)
    meta = meta.filter(pl.col("panda_id") != PREVIEW_PANDA_ID)
    counts["not_preview"] = meta.height

    n_trials = (
        steps.filter(pl.col("kind") == "trial")
        .group_by("firebase_doc_id")
        .len(name="n_trials")
    )
    meta = meta.join(n_trials, on="firebase_doc_id", how="left").filter(
        pl.col("n_trials") == N_TRIALS_EXPECTED
    )
    counts["exactly_8_trials"] = meta.height

    # Dedupe on panda_id+layout: a repeat session by the same researcher in the
    # other condition is a distinct session, not a duplicate.
    meta = (
        meta.sort("last_updated_sec", descending=True, nulls_last=True)
        .unique(subset=["panda_id", "layout"], keep="first", maintain_order=True)
    )
    counts["deduped"] = meta.height

    return meta["firebase_doc_id"].to_list(), counts


def _anchor_inputs(steps: pl.DataFrame) -> pl.DataFrame:
    calib = (
        steps.filter((pl.col("step_id") == "00") & (pl.col("kind") == "calib"))
        .group_by("firebase_doc_id")
        .agg(pl.col("trial_start_ts").min().alias("calib_start_ts"))
    )
    trial01 = (
        steps.filter(pl.col("kind") == "trial")
        .sort("step_id")
        .group_by("firebase_doc_id")
        .agg(pl.col("trial_start_ts").first().alias("trial_01_start_ts"))
    )
    both = calib.join(trial01, on="firebase_doc_id", how="full", coalesce=True)
    # A session with trial rows but no calib row would otherwise produce a null
    # anchor and read as "no beep anchor" -- a different, unrelated problem.
    missing = both.filter(
        pl.col("calib_start_ts").is_null() | pl.col("trial_01_start_ts").is_null()
    )
    if not missing.is_empty():
        raise ValueError(
            "session is missing a calib (step '00', kind 'calib') or trial row, "
            f"so no anchor can be derived: {missing.to_dicts()}"
        )
    return both


def build_tables(
    ds: SmileDataset, beeps: pl.DataFrame | None = None
) -> tuple[pl.DataFrame, pl.DataFrame, dict[str, int], list[str]]:
    """Return (runlist, trials, filter counts, excluded-no-anchor rows).

    Sessions with no hand-verified beep anchor appear ONLY in the excluded
    frame -- never in runlist or trials.
    """
    beeps = load_beeps() if beeps is None else beeps
    steps = raw_steps_df(ds)
    keys, counts = select_sessions(ds, steps)

    steps = steps.filter(pl.col("firebase_doc_id").is_in(keys))
    meta = _session_meta(ds).filter(pl.col("firebase_doc_id").is_in(keys))

    # conditions['layout'] vs the layout each step row recorded. They diverged
    # once already (2026-08-17: conditions clobbered to {} while TrialView's
    # fallback wrote 'quad' into every row) -- and a null layout here would
    # otherwise surface as "missing beep", pointing the researcher at the wrong
    # problem entirely.
    if "layout" in steps.columns:
        step_layout = steps.select(
            "firebase_doc_id", pl.col("layout").alias("step_layout")
        ).unique()
        # ne_missing, so a null conditions['layout'] (the 2026-08-17 clobber
        # shape) is a mismatch rather than a null that filters itself away.
        bad = meta.join(step_layout, on="firebase_doc_id", how="left").filter(
            pl.col("step_layout").ne_missing(pl.col("layout"))
        )
        if not bad.is_empty():
            raise ValueError(
                "conditions['layout'] disagrees with the layout recorded on the "
                f"step rows (randomization may have been clobbered): "
                f"{bad.select('firebase_doc_id', 'layout', 'step_layout').to_dicts()}"
            )

    # sessions.csv's layout column is a checksum on conditions['layout'], which
    # stays authoritative -- a mismatch picks the wrong beep offset (1.5s apart).
    # load_beeps requires the column, so this check is never skipped.
    bad = (
        meta.join(beeps.select("firebase_doc_id", "layout"), on="firebase_doc_id")
        .filter(pl.col("layout").ne_missing(pl.col("layout_right")))["firebase_doc_id"]
        .to_list()
    )
    if bad:
        raise ValueError(f"beep-source layout disagrees with conditions['layout']: {bad}")

    runlist = (
        meta.join(
            beeps.select(
                "firebase_doc_id", "video_last_beep_sec", "anchor_uncertainty_sec"
            ),
            on="firebase_doc_id",
            how="left",
        )
        .join(_anchor_inputs(steps), on="firebase_doc_id", how="left")
        .with_columns(
            # No default: an unrecognized layout must not silently become a
            # null offset that reads downstream as "no beep anchor".
            pl.col("layout").replace_strict(LAST_BEEP_OFFSET_SEC)
            .alias("last_beep_offset_sec")
        )
        .with_columns(
            ((pl.col("trial_01_start_ts") - pl.col("calib_start_ts")) / 1000.0)
            .alias("calib_to_trial01_sec"),
            (pl.col("video_last_beep_sec") - pl.col("last_beep_offset_sec"))
            .alias("calib_video_start_sec"),
        )
        .with_columns(
            (pl.col("calib_video_start_sec") + pl.col("calib_to_trial01_sec"))
            .alias("video_trial_01_start_sec")
        )
        .with_columns(
            pl.when(pl.col("video_trial_01_start_sec").is_not_null())
            .then(pl.lit("beep"))
            .otherwise(pl.lit("missing"))
            .alias("anchor_source")
        )
        .join(
            steps.filter(pl.col("kind") == "trial")
            .group_by("firebase_doc_id")
            .len(name="n_trials"),
            on="firebase_doc_id",
            how="left",
        )
    )

    # Excluded sessions leave the runlist entirely rather than sitting in it
    # with a null anchor: an unverified anchor produces confidently wrong gaze,
    # and a row that is present-but-null relies on a downstream filter that
    # does not exist yet. The exclusion is a fact on disk, not a promise.
    excluded = runlist.filter(pl.col("anchor_source") != "beep")
    runlist = runlist.filter(pl.col("anchor_source") == "beep")
    counts["has_beep_anchor"] = runlist.height

    trials = steps.join(
        runlist.select("firebase_doc_id", "panda_id", "video_trial_01_start_sec"),
        on="firebase_doc_id",
        how="inner",
    ).sort("firebase_doc_id", "step_id")

    return (
        runlist.sort("firebase_doc_id"),
        trials,
        counts,
        excluded.sort("firebase_doc_id"),
    )
