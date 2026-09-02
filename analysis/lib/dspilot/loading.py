"""Load `getdata` exports, which wrap each record as {id, data: {...}}.

smiledata.load_json calls Participant(p) directly on each element, but
Participant reads flat records (participant.py: self._data.get("conditions"),
self._data.get("done"), ...). Fed a wrapper straight, every property except
`.id` reads back empty/default. load_export unwraps first.
"""

from __future__ import annotations

import json
from pathlib import Path

import polars as pl
from smiledata import Participant, SmileDataset


def load_export(path: str | Path) -> SmileDataset:
    """Load a getdata export ({id, data: {...}} per record) into a SmileDataset."""
    with open(path, "r", encoding="utf-8") as f:
        records = json.load(f)

    participants = [Participant({**r.get("data", {}), "id": r["id"]}) for r in records]
    return SmileDataset(participants)


def last_visit_only(df: pl.DataFrame) -> pl.DataFrame:
    """Keep only the highest-numbered visit's rows per participant.

    A session resumed in the same browser leaves an abandoned pass in
    visit_0 and writes the real run to visit_1+; reading all visits silently
    parses the wrong session when the earlier pass also looks complete.
    """
    if df.is_empty():
        return df
    return df.filter(pl.col("visit") == pl.col("visit").max().over("participant_id"))
