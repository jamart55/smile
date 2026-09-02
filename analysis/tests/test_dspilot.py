"""Tests for the dspilot package."""

import json

import polars as pl
import pytest
from smiledata import load_json

from smiledata import Participant, SmileDataset

from dspilot.beeps import load_beeps
from dspilot.config import LAST_BEEP_OFFSET_SEC, video_path
from dspilot.loading import last_visit_only, load_export
from dspilot.runlist import build_tables, raw_steps_df


# --- loading.load_export ---------------------------------------------------


def _wrapped_record(complete_participant_data):
    return [{"id": "doc123", "data": complete_participant_data}]


def test_load_export_recovers_nested_fields(complete_participant_data, tmp_path):
    records = _wrapped_record(complete_participant_data)
    path = tmp_path / "export.json"
    path.write_text(json.dumps(records))

    ds = load_export(path)
    p = ds[0]

    assert p.id == "doc123"
    assert p.conditions == {"condition": "A", "block_order": "1"}
    assert p.done is True
    assert p.get_page_data("trial") != {}


def test_load_export_missing_data_key_does_not_raise(tmp_path):
    records = [{"id": "doc123"}]
    path = tmp_path / "export.json"
    path.write_text(json.dumps(records))

    ds = load_export(path)
    assert ds[0].id == "doc123"


def test_load_json_fails_on_wrapped_export(complete_participant_data, tmp_path):
    """Same input through smiledata.load_json does NOT recover nested fields."""
    records = _wrapped_record(complete_participant_data)
    path = tmp_path / "export.json"
    path.write_text(json.dumps(records))

    ds = load_json(path)
    p = ds[0]

    assert p.conditions == {}
    assert p.done is False
    assert not p.get_page_data("trial")


# --- loading.last_visit_only -------------------------------------------------


def test_last_visit_only_keeps_max_visit_per_participant():
    df = pl.DataFrame(
        {
            "participant_id": ["a", "a", "b"],
            "visit": [0, 1, 0],
            "value": ["stale", "real", "only"],
        }
    )
    out = last_visit_only(df)
    rows = out.sort("participant_id").to_dicts()
    assert rows == [
        {"participant_id": "a", "visit": 1, "value": "real"},
        {"participant_id": "b", "visit": 0, "value": "only"},
    ]


def test_last_visit_only_empty_df_does_not_raise():
    df = pl.DataFrame({"participant_id": [], "visit": []})
    out = last_visit_only(df)
    assert out.is_empty()


# --- config.video_path -------------------------------------------------------


def test_video_path_raises_on_two_webm(tmp_path, monkeypatch):
    monkeypatch.setenv("DS_VIDEO_ROOT", str(tmp_path))
    vdir = tmp_path / "p1" / "videos"
    vdir.mkdir(parents=True)
    (vdir / "a.webm").touch()
    (vdir / "b.webm").touch()

    with pytest.raises(ValueError):
        video_path("p1")


def test_video_path_webm_and_mp4_sidecar_is_fine(tmp_path, monkeypatch):
    monkeypatch.setenv("DS_VIDEO_ROOT", str(tmp_path))
    vdir = tmp_path / "p1" / "videos"
    vdir.mkdir(parents=True)
    (vdir / "x.webm").touch()
    (vdir / "x.mp4").touch()

    result = video_path("p1")
    assert result.name == "x.webm"


def test_video_path_raises_when_empty(tmp_path, monkeypatch):
    monkeypatch.setenv("DS_VIDEO_ROOT", str(tmp_path))
    (tmp_path / "p1" / "videos").mkdir(parents=True)

    with pytest.raises(FileNotFoundError):
        video_path("p1")


def test_video_path_respects_env_root(tmp_path, monkeypatch):
    root = tmp_path / "custom_root"
    vdir = root / "p1" / "videos"
    vdir.mkdir(parents=True)
    (vdir / "only.webm").touch()
    monkeypatch.setenv("DS_VIDEO_ROOT", str(root))

    result = video_path("p1")
    assert result == vdir / "only.webm"


# --- beeps.load_beeps ---------------------------------------------------------


def test_load_beeps_csv_roundtrip(tmp_path, monkeypatch):
    csv_path = tmp_path / "beeps.csv"
    csv_path.write_text("firebase_doc_id,video_last_beep_sec,layout\nABC123,12.34,quad\n")
    monkeypatch.setenv("DS_BEEP_SOURCE", "csv")
    monkeypatch.setenv("DS_BEEP_PATH", str(csv_path))

    df = load_beeps()
    assert df.to_dicts() == [
        {
            "firebase_doc_id": "ABC123",
            "video_last_beep_sec": 12.34,
            "layout": "quad",
            # Absent from the sheet must stay null, not 0 -- 0 reads as an
            # exact measurement (CLAUDE.md 2026-08-21, diam is +/-0.2s).
            "anchor_uncertainty_sec": None,
        }
    ]


def test_load_beeps_duplicate_session_key_raises(tmp_path, monkeypatch):
    csv_path = tmp_path / "beeps.csv"
    csv_path.write_text(
        "firebase_doc_id,video_last_beep_sec,layout\n"
        "ABC123,12.34,quad\nABC123,99.0,quad\n"
    )
    monkeypatch.setenv("DS_BEEP_SOURCE", "csv")
    monkeypatch.setenv("DS_BEEP_PATH", str(csv_path))

    with pytest.raises(ValueError):
        load_beeps()


def test_load_beeps_unknown_source_raises(monkeypatch):
    monkeypatch.setenv("DS_BEEP_SOURCE", "bogus")

    with pytest.raises(ValueError):
        load_beeps()


def test_load_beeps_unconfigured_returns_empty_with_schema(monkeypatch):
    monkeypatch.delenv("DS_BEEP_SOURCE", raising=False)
    monkeypatch.delenv("DS_BEEP_PATH", raising=False)

    df = load_beeps()
    assert df.is_empty()
    assert df.schema == {
        "firebase_doc_id": pl.Utf8,
        "video_last_beep_sec": pl.Float64,
        "layout": pl.Utf8,
        "anchor_uncertainty_sec": pl.Float64,
    }


# --- runlist ------------------------------------------------------------------


CALIB_TS = 1_000_000_000
TRIAL01_TS = CALIB_TS + 26_671


def _steps(layout, n_trials=8, first_trial_ts=TRIAL01_TS):
    rows = [
        {
            "id": "00",
            "kind": "calib",
            "layout": layout,
            "name": f"{layout}-calib",
            "trial_start_ts": CALIB_TS,
        }
    ]
    for i in range(1, n_trials + 1):
        rows.append(
            {
                "id": f"{i:02d}",
                "kind": "trial",
                "layout": layout,
                "name": f"{i:02d}_car_UL",
                "trial_start_ts": first_trial_ts + (i - 1) * 20_000,
            }
        )
    return rows


def _session(doc_id, panda_id, layout, visits=None, last_updated=1000.0, **over):
    visits = visits or [_steps(layout)]
    data = {
        "consented": True,
        "done": True,
        "withdrawn": False,
        "panda_id": panda_id,
        "conditions": {"layout": layout},
        "lastUpdated": {"_seconds": int(last_updated), "_nanoseconds": 0},
        "pageData_trials": {
            f"visit_{i}": {"data": rows} for i, rows in enumerate(visits)
        },
        **over,
    }
    return Participant({**data, "id": doc_id})


def _beeps(**vals):
    """Mirrors load_beeps' output contract: layout is required, uncertainty optional."""
    layouts = {"docD": "diam"}  # every other fixture session is quad
    return pl.DataFrame(
        {
            "firebase_doc_id": list(vals),
            "video_last_beep_sec": list(vals.values()),
            "layout": [layouts.get(k, "quad") for k in vals],
            "anchor_uncertainty_sec": [None] * len(vals),
        },
        schema_overrides={"anchor_uncertainty_sec": pl.Float64},
    )


def test_two_sessions_one_panda_id_both_survive_dedupe():
    """Both reference sessions share panda_id 17291H but differ on layout."""
    ds = SmileDataset(
        [_session("docQ", "17291H", "quad"), _session("docD", "17291H", "diam")]
    )
    runlist, _, counts, _ = build_tables(ds, _beeps(docQ=350.33, docD=329.9))
    assert counts["deduped"] == 2
    assert set(runlist["firebase_doc_id"]) == {"docQ", "docD"}


def test_dedupe_keeps_latest_last_updated_within_panda_id_and_layout():
    ds = SmileDataset(
        [
            _session("old", "17291H", "quad", last_updated=100.0),
            _session("new", "17291H", "quad", last_updated=200.0),
        ]
    )
    runlist, _, counts, _ = build_tables(ds, _beeps(old=350.33, new=350.33))
    assert counts["exactly_8_trials"] == 2
    assert runlist["firebase_doc_id"].to_list() == ["new"]


def test_last_visit_filter_runs_before_the_eight_trial_count():
    """A resumed session has 8 trial rows per visit; it must not read as 16."""
    ds = SmileDataset(
        [_session("doc", "P1", "quad", visits=[_steps("quad"), _steps("quad")])]
    )
    steps = raw_steps_df(ds)
    assert steps["visit"].unique().to_list() == [1]
    runlist, _, counts, _ = build_tables(ds, _beeps(doc=350.33))
    assert counts["exactly_8_trials"] == 1
    assert runlist["n_trials"].to_list() == [8]


def test_kind_defaults_to_trial_when_key_absent():
    rows = [dict(r) for r in _steps("quad")[1:]]
    for r in rows:
        r.pop("kind")
    ds = SmileDataset([_session("doc", "P1", "quad", visits=[rows])])
    steps = raw_steps_df(ds)
    assert steps["kind"].to_list() == ["trial"] * 8


def test_anchor_derivation_quad_and_diam():
    ds = SmileDataset(
        [_session("docQ", "P1", "quad"), _session("docD", "P2", "diam")]
    )
    runlist, _, _, no_beep = build_tables(ds, _beeps(docQ=350.33, docD=329.9))
    assert no_beep.is_empty()
    got = dict(zip(runlist["firebase_doc_id"], runlist["video_trial_01_start_sec"]))
    assert got["docQ"] == pytest.approx(350.33 - 3.5099 + 26.671)
    assert got["docD"] == pytest.approx(329.9 - 5.0099 + 26.671)
    # per-layout offset actually differs, so the two anchors cannot coincide
    assert LAST_BEEP_OFFSET_SEC["quad"] != LAST_BEEP_OFFSET_SEC["diam"]


def test_missing_beep_row_is_listed_and_anchor_is_null():
    ds = SmileDataset(
        [_session("docQ", "P1", "quad"), _session("docD", "P2", "diam")]
    )
    runlist, trials, _, no_beep = build_tables(ds, _beeps(docQ=350.33))
    # Excluded outright, not carried with a null anchor: a present-but-null row
    # relies on a downstream filter that does not exist.
    assert no_beep["firebase_doc_id"].to_list() == ["docD"]
    assert no_beep["panda_id"].to_list() == ["P2"]
    assert runlist["firebase_doc_id"].to_list() == ["docQ"]
    assert "docD" not in trials["firebase_doc_id"].to_list()


def test_beep_source_layout_mismatch_raises():
    ds = SmileDataset([_session("docQ", "P1", "quad")])
    beeps = _beeps(docQ=350.33).with_columns(pl.lit("diam").alias("layout"))
    with pytest.raises(ValueError, match="layout"):
        build_tables(ds, beeps)


def test_beep_source_blank_layout_cell_still_raises():
    """A blank sheet cell must not slip past the checksum: != against null is null."""
    ds = SmileDataset([_session("docQ", "P1", "quad")])
    beeps = _beeps(docQ=350.33).with_columns(
        pl.lit(None, dtype=pl.Utf8).alias("layout")
    )
    with pytest.raises(ValueError, match="layout"):
        build_tables(ds, beeps)


def test_preview_and_incomplete_sessions_are_dropped():
    ds = SmileDataset(
        [
            _session("real", "P1", "quad"),
            _session("preview", "PANDA_TEST_001", "quad"),
            _session("unfinished", "P2", "quad", done=False),
            _session("short", "P3", "quad", visits=[_steps("quad", n_trials=7)]),
        ]
    )
    runlist, _, counts, _ = build_tables(ds, _beeps(real=350.33))
    assert counts == {
        "loaded": 4,
        "complete_only": 3,
        "not_preview": 2,
        "exactly_8_trials": 1,
        "deduped": 1,
        "has_beep_anchor": 1,
    }
    assert runlist["firebase_doc_id"].to_list() == ["real"]


def test_trials_table_carries_layout_and_anchor_on_every_row():
    ds = SmileDataset([_session("docQ", "P1", "quad")])
    _, trials, _, _ = build_tables(ds, _beeps(docQ=350.33))
    assert trials.height == 9
    assert trials["layout"].unique().to_list() == ["quad"]
    assert trials["video_trial_01_start_sec"].null_count() == 0


def test_conditions_layout_disagreeing_with_step_rows_raises():
    """The 2026-08-17 clobber shape: conditions empty, steps say 'quad'."""
    p = _session("doc", "P1", "quad")
    p.raw_data["conditions"] = {}
    ds = SmileDataset([p])
    with pytest.raises(ValueError, match="randomization"):
        build_tables(ds, _beeps(doc=350.33))
