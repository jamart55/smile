"""Single seam for hand-verified video timing anchors (a researcher-filled
Google Sheet), joined on firebase_doc_id. Values are authoritative by construction -- never validated
or corrected here.
"""

from __future__ import annotations

import os

import polars as pl

_SCHEMA = {
    "firebase_doc_id": pl.Utf8,
    "video_last_beep_sec": pl.Float64,
    # Checksum on conditions['layout']; runlist.build_tables raises on a
    # mismatch, and the two LAST_BEEP_OFFSET_SEC values are 1.5s apart, so
    # a silently-missing column picks the wrong offset. Required, not optional.
    "layout": pl.Utf8,
    # Provenance, not a guard: quad's anchor is corroborated by two methods,
    # diam's is burst-onset only at +/-0.2s. Optional, and null when absent --
    # never 0, which would read as an exact measurement.
    "anchor_uncertainty_sec": pl.Float64,
}


def load_beeps() -> pl.DataFrame:
    source = os.environ.get("DS_BEEP_SOURCE", "csv")

    if source == "csv":
        path = os.environ.get("DS_BEEP_PATH")
        if not path:
            return pl.DataFrame(schema=_SCHEMA)
        df = pl.read_csv(path)
    elif source == "gsheet":
        url = os.environ.get("DS_BEEP_URL")
        if not url:
            return pl.DataFrame(schema=_SCHEMA)
        df = pl.read_csv(url)
    else:
        raise ValueError(f"Unknown DS_BEEP_SOURCE={source!r}, expected 'csv' or 'gsheet'")

    df = df.with_columns(pl.col("firebase_doc_id").cast(pl.Utf8))

    dupes = df.filter(pl.col("firebase_doc_id").is_duplicated())
    if not dupes.is_empty():
        ids = dupes["firebase_doc_id"].unique().to_list()
        raise ValueError(f"Duplicate firebase_doc_id in beep source: {ids}")

    missing = [c for c in ("video_last_beep_sec", "layout") if c not in df.columns]
    if missing:
        raise ValueError(f"Beep source is missing required column(s): {missing}")

    if "anchor_uncertainty_sec" not in df.columns:
        df = df.with_columns(pl.lit(None, dtype=pl.Float64).alias("anchor_uncertainty_sec"))

    return df.select(list(_SCHEMA))
