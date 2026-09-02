"""Stage 3 (OWLET) unit tests.

Only the pure parts are covered, matching the house precedent set by
predicted.py's un-covered ffprobe call: anything that shells out to ffmpeg,
OpenCV or OWLET itself is exercised by the real reference run, not by mocks.
"""

import json

import polars as pl
import pytest

from dspilot import owlet


# --- calib_stem / _existing_calib_video ----------------------------------


def test_calib_stem_lowercases():
    assert owlet.calib_stem("5nJexyg6m1RFzox37ijy") == "5njexyg6m1rfzox37ijy"


def test_existing_calib_video_matches_owlet_case_rule(tmp_path):
    """OWLET lower-cases the subject stem (OWLET.py:112) then matches filenames
    case-SENSITIVELY (:120). A case-preserving calibration file is invisible to
    it, and must be invisible here too -- 01_pilot's case-insensitive check said
    'calibration exists' for a file OWLET could not see, and the run silently
    fell through to hardcoded defaults."""
    stem = "Jacob-Quad-Test"

    # Separate dirs: macOS is case-insensitive, so both names in one dir are one file.
    preserved = tmp_path / "preserved"
    preserved.mkdir()
    (preserved / f"{stem}_calibration.mp4").touch()
    assert owlet._existing_calib_video(preserved, stem) is None

    lowered = tmp_path / "lowered"
    lowered.mkdir()
    (lowered / f"{stem.lower()}_calibration.mp4").touch()
    found = owlet._existing_calib_video(lowered, stem)
    assert found is not None and found.name == "jacob-quad-test_calibration.mp4"


def test_existing_calib_video_ignores_annotated(tmp_path):
    (tmp_path / "sess_calibration_annotated.mp4").touch()
    assert owlet._existing_calib_video(tmp_path, "sess") is None


# --- _target_span / _extrapolate_to_frame --------------------------------


def _fake_dwells(tmp_path, monkeypatch):
    path = tmp_path / "calib_dwells.json"
    path.write_text(json.dumps({"trials": {
        "quad-calib": {"layout": "quad", "dwells": [
            {"cx": 0.1, "cy": 0.2}, {"cx": 0.9, "cy": 0.8}]},
        "diam-calib": {"layout": "diam", "dwells": [
            {"cx": 0.3, "cy": 0.4}, {"cx": 0.7, "cy": 0.6}]},
    }}))
    monkeypatch.setattr(owlet, "CALIB_DWELLS_JSON", path)


def test_target_span_differs_by_layout(tmp_path, monkeypatch):
    """One shared span across both clips would mis-scale one condition."""
    _fake_dwells(tmp_path, monkeypatch)
    assert owlet._target_span("quad") == pytest.approx((0.8, 0.6))
    assert owlet._target_span("diam") == pytest.approx((0.4, 0.2))


def test_target_span_unknown_layout_raises(tmp_path, monkeypatch):
    _fake_dwells(tmp_path, monkeypatch)
    with pytest.raises(KeyError, match="leftright"):
        owlet._target_span("leftright")


def test_extrapolate_widens_range_holding_middle_fixed(tmp_path, monkeypatch):
    _fake_dwells(tmp_path, monkeypatch)
    result = {
        "range_xvals": 0.16, "middle_x": 0.5, "min_xval": 0.42, "max_xval": 0.58,
        "range_yvals": 0.12, "middle_y": 0.3, "min_yval": 0.24, "max_yval": 0.36,
    }
    out = owlet._extrapolate_to_frame(dict(result), "quad")
    assert out["range_xvals"] == pytest.approx(0.2)      # 0.16 / 0.8
    assert out["middle_x"] == 0.5
    assert out["min_xval"] == pytest.approx(0.4)
    assert out["max_xval"] == pytest.approx(0.6)
    assert out["range_yvals"] == pytest.approx(0.2)      # 0.12 / 0.6


def test_extrapolation_is_layout_specific(tmp_path, monkeypatch):
    _fake_dwells(tmp_path, monkeypatch)
    base = {"range_xvals": 0.16, "middle_x": 0.5, "range_yvals": 0.12, "middle_y": 0.3}
    q = owlet._extrapolate_to_frame(dict(base), "quad")["range_xvals"]
    d = owlet._extrapolate_to_frame(dict(base), "diam")["range_xvals"]
    assert q != d


def test_real_calib_dwells_have_both_layouts():
    """The shipped config must cover both pilot-02 clips, keyed by layout --
    not 01_pilot's 100/101 trial ids."""
    for layout in ("quad", "diam"):
        sx, sy = owlet._target_span(layout)
        assert 0.5 < sx < 1.0 and 0.5 < sy < 1.0


# --- calib_windows_from_runlist ------------------------------------------


def test_calib_window_from_runlist_row():
    row = {"calib_video_start_sec": 346.8201, "calib_to_trial01_sec": 26.671}
    assert owlet.calib_windows_from_runlist(row) == [(346.8201, 26.671)]


@pytest.mark.parametrize("missing", ["calib_video_start_sec", "calib_to_trial01_sec"])
def test_calib_window_missing_column_returns_none(missing):
    """A session with no verified anchor is skipped and named by the caller --
    never defaulted. An unverified anchor produces confidently wrong gaze."""
    row = {"calib_video_start_sec": 346.8201, "calib_to_trial01_sec": 26.671}
    row[missing] = None
    assert owlet.calib_windows_from_runlist(row) is None


# --- _ensure_calibration refusal path ------------------------------------


def test_ensure_calibration_raises_without_windows(tmp_path):
    with pytest.raises(ValueError, match="Refusing to run OWLET"):
        owlet._ensure_calibration(tmp_path, "sess", tmp_path / "sess.mp4", None, "quad")


@pytest.mark.parametrize("bad", [
    {"check_range_zero": 0},
    {"range_xvals": 0.05},
    {"range_yvals": 0.09},
    {"n_frames": 120},
])
def test_ensure_calibration_raises_on_degenerate_result(tmp_path, monkeypatch, bad):
    """Degeneracy is judged on the MEASURED range, before extrapolation --
    extrapolating first lets a collapsed channel inflate past CALIB_RANGE_MIN
    and get written out as if it were real."""
    good = {
        "check_range_zero": 0.3, "range_xvals": 0.2, "range_yvals": 0.2, "n_frames": 900,
        "middle_x": 0.5, "middle_y": 0.3, "min_xval": 0.4, "max_xval": 0.6,
        "min_yval": 0.2, "max_yval": 0.4, "mean": 4.0, "maximum": 5.5,
        "minimum": 2.0, "mean_eyeratio": 1.0,
    }
    monkeypatch.setattr(owlet, "_cut_calib_clip", lambda *a: tmp_path / "clip.mp4")
    monkeypatch.setattr(owlet, "_run_looking_calibration", lambda _: {**good, **bad})

    with pytest.raises(ValueError, match="degenerate"):
        owlet._ensure_calibration(tmp_path, "sess", tmp_path / "s.mp4", [(0.0, 27.0)], "quad")
    assert not (tmp_path / "sess_calibration.mp4").exists()


def test_ensure_calibration_writes_settings_under_lowercased_stem(tmp_path, monkeypatch):
    """OWLET derives the settings path from the calibration video's own name
    (run_owlet_cnn.py:52), so both must carry the lower-cased stem or OWLET
    recomputes -- or worse, never finds it."""
    good = {
        "check_range_zero": 0.3, "range_xvals": 0.2, "range_yvals": 0.2, "n_frames": 900,
        "middle_x": 0.5, "middle_y": 0.3, "min_xval": 0.4, "max_xval": 0.6,
        "min_yval": 0.2, "max_yval": 0.4, "mean": 4.0, "maximum": 5.5,
        "minimum": 2.0, "mean_eyeratio": 1.0,
    }
    monkeypatch.setattr(owlet, "_cut_calib_clip", lambda *a: tmp_path / "clip.mp4")
    monkeypatch.setattr(owlet, "_run_looking_calibration", lambda _: dict(good))

    out = owlet._ensure_calibration(
        tmp_path, "Jacob-Quad-Test", tmp_path / "v.mp4", [(0.0, 27.0)], "quad")

    csv = tmp_path / "jacob-quad-test_calibration_settings.csv"
    assert csv.exists()
    # run_owlet_cnn reads this file by POSITION (df.iloc[0, 0:4] / 4:8 / 8:12),
    # never by name -- reordering silently swaps the x and y calibration.
    assert csv.read_text().splitlines()[0].split(",") == owlet._CALIB_SETTINGS_COLS
    assert out["range_xvals"] > 0.2   # extrapolated past the measured range


# --- study_window_sec / qa_row -------------------------------------------


def _gaze(times_ms, xs, ys):
    return pl.DataFrame({"Time": times_ms, "X-coord": xs, "Y-coord": ys})


def _trials_one_session():
    return pl.DataFrame({
        "firebase_doc_id": ["s1", "s1", "s1"],
        "kind": ["calib", "trial", "trial"],
        "trial_start_ts": [1000, 30000, 50000],
        "trial_end_ts": [27000, 48000, 68000],
    })


def test_study_window_runs_from_calib_start_to_last_trial_end():
    row = {"firebase_doc_id": "s1", "calib_video_start_sec": 100.0,
           "video_trial_01_start_sec": 130.0}
    assert owlet.study_window_sec(row, _trials_one_session()) == (100.0, 168.0)


def test_qa_row_flags_collapse_that_a_whole_file_check_would_miss():
    """The quad reference session had 540 distinct Y values file-wide and exactly 1
    inside the study window. Scoring the whole file calls that a pass."""
    times = list(range(0, 20000, 100))
    ys = [float(i % 400) for i in range(100)] + [193.0] * 100  # varied, then constant
    gaze = _gaze(times, [500.0] * 200, ys)

    whole = owlet.qa_row("s1", "quad", gaze, {}, (0.0, 20.0))
    assert whole["y_collapsed"] is False

    study = owlet.qa_row("s1", "quad", gaze, {}, (10.0, 20.0))
    assert study["y_collapsed"] is True
    assert study["y_n_unique_study"] == 1
    assert study["y_n_unique_file"] > 1
