"""Tests for dspilot.predicted (stage 5: predicted-vs-observed windows).

No gaze data exists yet -- everything here runs against synthetic trials
rows and a synthetic timing CSV, plus the real aoi_layouts.json fixture.
"""

from pathlib import Path

import polars as pl
import pytest

from dspilot import predicted as pred

AOI_LAYOUTS = {
    "quad": {"boxes": {"UL": {}, "UR": {}, "BL": {}, "BR": {}}},
    "diam": {"boxes": {"T": {}, "B": {}, "L": {}, "R": {}}},
}


def _timing_df():
    return pl.DataFrame(
        {
            "trial_name": [
                "quad_01_car_UL.mp4",
                "quad_02_apple_UR.mp4",
                "diam_02_apple_T.mp4",
            ],
            "begin": [0.0, 0.0, 0.0],
            "occlude": [9.0, None, None],
            "target": [13.4, 8.5, 8.5],
            "occlude_aoi": ["BL", None, None],
        }
    )


def _make_video_dir(tmp_path: Path) -> Path:
    video_dir = tmp_path / "videos"
    (video_dir / "quad").mkdir(parents=True)
    (video_dir / "diam").mkdir(parents=True)
    (video_dir / "quad" / "01_car_UL.mp4").touch()
    (video_dir / "quad" / "02_apple_UR.mp4").touch()
    (video_dir / "diam" / "02_apple_T.mp4").touch()
    return video_dir


# --- _windows_for_trial ------------------------------------------------


def test_motion_trial_scores_occlusion_and_post_target_windows():
    windows = pred._windows_for_trial(
        begin=0.0, occlude=9.0, target=13.4, end=18.6, target_aoi="UL", occlude_aoi="BL"
    )
    assert windows == [
        {"window": "begin_to_occlude", "t_start_sec": 0.0, "t_end_sec": 9.0,
         "predicted_aoi": None, "scored": False},
        {"window": "occlude_to_target", "t_start_sec": 9.0, "t_end_sec": 13.4,
         "predicted_aoi": "BL", "scored": True},
        {"window": "target_to_end", "t_start_sec": 13.4, "t_end_sec": 18.6,
         "predicted_aoi": "UL", "scored": True},
    ]


def test_object_recognition_trial_pre_target_window_unscored():
    windows = pred._windows_for_trial(
        begin=0.0, occlude=None, target=8.5, end=14.7, target_aoi="UR", occlude_aoi=None
    )
    assert windows == [
        {"window": "begin_to_target", "t_start_sec": 0.0, "t_end_sec": 8.5,
         "predicted_aoi": None, "scored": False},
        {"window": "target_to_end", "t_start_sec": 8.5, "t_end_sec": 14.7,
         "predicted_aoi": "UR", "scored": True},
    ]


# --- _predicted_aoi ------------------------------------------------------


def test_predicted_aoi_parses_token_from_name():
    assert pred._predicted_aoi("01_car_UL", "quad", AOI_LAYOUTS) == "UL"


def test_out_is_a_valid_aoi_but_not_a_box():
    # diam's occluder sits in the uncoded middle; OUT must survive validation.
    assert pred._validate_aoi("OUT", "diam", AOI_LAYOUTS, "diam_01_car_B") == "OUT"


def test_predicted_aoi_unknown_token_raises():
    with pytest.raises(ValueError, match="Unknown AOI token"):
        pred._predicted_aoi("01_car_ZZ", "quad", AOI_LAYOUTS)


# --- assert_csv_matches_video_files --------------------------------------


def test_csv_matches_video_files_passes_when_1to1(tmp_path):
    video_dir = _make_video_dir(tmp_path)
    pred.assert_csv_matches_video_files(_timing_df(), video_dir)  # no raise


def test_csv_matches_video_files_raises_on_mismatch(tmp_path):
    video_dir = _make_video_dir(tmp_path)
    (video_dir / "quad" / "99_extra_BR.mp4").touch()
    with pytest.raises(ValueError, match="disagree"):
        pred.assert_csv_matches_video_files(_timing_df(), video_dir)


# --- build_predicted_windows ---------------------------------------------


def _trials_df():
    return pl.DataFrame(
        {
            "firebase_doc_id": ["sess1", "sess1", "sess1", "sess2"],
            "kind": ["calib", "trial", "trial", "trial"],
            "layout": ["quad", "quad", "quad", "diam"],
            "name": ["quad-calib", "01_car_UL", "02_apple_UR", "02_apple_T"],
        }
    )


def test_build_predicted_windows_excludes_calib_row_without_error(tmp_path, monkeypatch):
    monkeypatch.setattr(pred, "_video_duration_sec", lambda p: 18.6)
    video_dir = _make_video_dir(tmp_path)

    out = pred.build_predicted_windows(_trials_df(), _timing_df(), AOI_LAYOUTS, video_dir)

    # calib row's session/trial contributes no rows -- only quad's 2 trial
    # steps (3 + 2 windows) and diam's 1 (2 windows) = 7 rows total.
    assert out.height == 7
    assert "quad-calib" not in out["trial_name"].to_list()


def test_build_predicted_windows_full_table_for_two_sessions(tmp_path, monkeypatch):
    monkeypatch.setattr(pred, "_video_duration_sec", lambda p: 18.6 if "car" in str(p) else 14.7)
    video_dir = _make_video_dir(tmp_path)

    out = pred.build_predicted_windows(_trials_df(), _timing_df(), AOI_LAYOUTS, video_dir)

    row = out.filter(
        (pl.col("firebase_doc_id") == "sess1") & (pl.col("trial_name") == "quad_01_car_UL.mp4")
        & (pl.col("window") == "target_to_end")
    ).to_dicts()[0]
    assert row["predicted_aoi"] == "UL"
    assert row["t_start_sec"] == 13.4
    assert row["t_end_sec"] == 18.6
    assert row["scored"] is True

    occ = out.filter(
        (pl.col("firebase_doc_id") == "sess1") & (pl.col("trial_name") == "quad_01_car_UL.mp4")
        & (pl.col("window") == "occlude_to_target")
    ).to_dicts()[0]
    assert occ["predicted_aoi"] == "BL"
    assert occ["scored"] is True

    pre = out.filter(
        (pl.col("firebase_doc_id") == "sess1") & (pl.col("trial_name") == "quad_01_car_UL.mp4")
        & (pl.col("window") == "begin_to_occlude")
    ).to_dicts()[0]
    assert pre["predicted_aoi"] is None
    assert pre["scored"] is False


def test_build_predicted_windows_raises_on_unjoined_trial(tmp_path, monkeypatch):
    monkeypatch.setattr(pred, "_video_duration_sec", lambda p: 18.6)
    video_dir = _make_video_dir(tmp_path)
    trials = pl.DataFrame(
        {
            "firebase_doc_id": ["sess1"],
            "kind": ["trial"],
            "layout": ["quad"],
            "name": ["03_nonexistent_BR"],
        }
    )
    with pytest.raises(ValueError, match="no matching"):
        pred.build_predicted_windows(trials, _timing_df(), AOI_LAYOUTS, video_dir)


def test_load_timing_csv_raises_when_occlude_aoi_missing(tmp_path):
    csv = tmp_path / "timing.csv"
    csv.write_text(
        "trial_name,begin,occlude,target,occlude_aoi\n"
        "quad_01_car_UL.mp4,0,9,13.4,\n"
    )
    with pytest.raises(ValueError, match="must be populated together"):
        pred.load_timing_csv(csv)


# --- join_observed -------------------------------------------------------


def _windows_df():
    return pl.DataFrame(
        {
            "firebase_doc_id": ["sess1", "sess1", "sess2"],
            "layout": ["quad", "quad", "diam"],
            "trial_name": ["quad_01_car_UL.mp4", "quad_01_car_UL.mp4", "diam_02_apple_T.mp4"],
            "window": ["occlude_to_target", "target_to_end", "target_to_end"],
            "t_start_sec": [9.0, 13.4, 8.5],
            "t_end_sec": [13.4, 18.6, 14.7],
            "predicted_aoi": ["BL", "UL", "T"],
            "scored": [True, True, True],
        }
    )


def _gaze_df():
    return pl.DataFrame(
        {
            "firebase_doc_id": ["sess1"] * 5,
            "trial_name": ["quad_01_car_UL.mp4"] * 5,
            "trial_sec": [8.9, 10.0, 11.0, 14.0, 15.0],  # 8.9 is before the window
            "aoi_tag": ["UL", "BL", "UR", "UL", "OFFSCREEN"],
        }
    )


def test_join_observed_ignores_samples_outside_the_window():
    out = pred.join_observed(_windows_df(), _gaze_df())
    occ = out.filter(pl.col("window") == "occlude_to_target").to_dicts()[0]
    # 8.9s falls outside [9.0, 13.4) and must not be counted.
    assert occ["n_samples"] == 2 and occ["n_hit"] == 1
    assert occ["hit_rate"] == 0.5

    # The on-video filtering is what the target_to_end case below exercises.
    post = out.filter(
        (pl.col("firebase_doc_id") == "sess1") & (pl.col("window") == "target_to_end")
    ).to_dicts()[0]
    # One UL hit, one OFFSCREEN -- look-away leaves the denominator, so 1/1, not 1/2.
    assert post["n_offscreen"] == 1 and post["n_onvideo"] == 1
    assert post["hit_rate"] == 1.0


def test_join_observed_keeps_windows_of_sessions_with_no_gaze():
    out = pred.join_observed(_windows_df(), _gaze_df())
    sess2 = out.filter(pl.col("firebase_doc_id") == "sess2").to_dicts()[0]
    assert out.height == 3
    assert sess2["n_samples"] is None and sess2["hit_rate"] is None


def test_build_predicted_windows_raises_on_a_repeated_trial_row(tmp_path, monkeypatch):
    monkeypatch.setattr(pred, "_video_duration_sec", lambda p: 18.6)
    video_dir = _make_video_dir(tmp_path)
    trials = pl.DataFrame(
        {
            "firebase_doc_id": ["sess1", "sess1"],
            "kind": ["trial", "trial"],
            "layout": ["quad", "quad"],
            "name": ["01_car_UL", "01_car_UL"],
        }
    )
    with pytest.raises(ValueError, match="Repeated"):
        pred.build_predicted_windows(trials, _timing_df(), AOI_LAYOUTS, video_dir)
