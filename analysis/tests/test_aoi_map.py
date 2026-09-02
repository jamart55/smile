"""Tests for dspilot.aoi_map (stage 4: layer-2 correction + AOI tagging).

Synthetic gaze throughout -- a session whose OWLET output is an exact linear function of
the known dwell positions, so the fit has a right answer to recover.
"""

import math

import numpy as np
import polars as pl
import pytest

from dspilot import aoi_map as am

# Four corner dwells, all informative on both axes (a quad-shaped calib clip).
DWELLS = {
    "quad-calib": {"layout": "quad", "dwells": [
        {"t_start": 6.0, "t_end": 10.0, "cx": 0.1, "cy": 0.2},
        {"t_start": 11.0, "t_end": 15.0, "cx": 0.9, "cy": 0.8},
        {"t_start": 16.0, "t_end": 20.0, "cx": 0.1, "cy": 0.8},
        {"t_start": 21.0, "t_end": 25.0, "cx": 0.9, "cy": 0.2},
    ]},
}

# The generating map, inverted by the fit: frac = obs / SCALE.
SCALE_X, SCALE_Y = 960.0, 540.0

T0 = 1_000_000  # trial 01 wall clock, ms
ANCHOR = 100.0  # trial 01 lands 100s into the webcam recording


def _trials(with_ag=True):
    """One calib step then two trials, each followed by its attention-getter."""
    rows = [{
        "firebase_doc_id": "s1", "kind": "calib", "layout": "quad",
        "name": "quad-calib", "attention": None,
        "trial_start_ts": T0 - 30_000, "trial_end_ts": T0 - 2_000,
        "attention_start_ts": None, "video_trial_01_start_sec": ANCHOR,
    }]
    for i, (name, start) in enumerate((("01_car_UL", T0), ("02_apple_UR", T0 + 30_000))):
        rows.append({
            "firebase_doc_id": "s1", "kind": "trial", "layout": "quad",
            "name": name, "attention": f"videos/trials/pilot02/ag/rainbow.mp4",
            "trial_start_ts": start, "trial_end_ts": start + 18_000,
            "attention_start_ts": (start + 18_100) if with_ag else None,
            "video_trial_01_start_sec": ANCHOR,
        })
    return pl.DataFrame(rows)


def _gaze(known_at):
    """30 Hz gaze over 200s. `known_at(t_sec) -> (frac_x, frac_y) or None`."""
    t, xs, ys = [], [], []
    for i in range(200 * 30):
        sec = i / 30.0
        k = known_at(sec)
        t.append(sec * 1000.0)
        xs.append(np.nan if k is None else k[0] * SCALE_X)
        ys.append(np.nan if k is None else k[1] * SCALE_Y)
    return pl.DataFrame({"Time": t, "X-coord": xs, "Y-coord": ys})


def _perfect_gaze(trials=None, ag_frac=(0.5, 0.5)):
    trials = _trials() if trials is None else trials
    windows = []
    for r in trials.iter_rows(named=True):
        if r["kind"] == "calib":
            start = am.video_sec(r["trial_start_ts"], ANCHOR, T0)
            for d in DWELLS["quad-calib"]["dwells"]:
                windows.append((start + d["t_start"], start + d["t_end"],
                                (d["cx"], d["cy"])))
        elif r["attention_start_ts"] is not None:
            start = am.video_sec(r["attention_start_ts"], ANCHOR, T0)
            windows.append((start + am.AG_WINDOW_SEC[0], start + am.AG_WINDOW_SEC[1],
                            ag_frac))

    def known_at(sec):
        for a, b, k in windows:
            if a <= sec < b:
                return k
        return (0.5, 0.5)  # between windows: looking at nothing in particular

    return _gaze(known_at)


# --- dwell_observations --------------------------------------------------


def test_calib_dwells_anchor_on_trial_start_ag_dwells_on_attention_start():
    obs = am.dwell_observations(_perfect_gaze(), _trials(), DWELLS)

    calib = obs.filter(pl.col("kind") == "calib")
    ag = obs.filter(pl.col("kind") == "ag")
    assert calib.height == 4 and ag.height == 2
    # Recovered exactly, which only happens if each window was sampled at the right time.
    assert calib["kx"].to_list() == [0.1, 0.9, 0.1, 0.9]
    assert calib["ox"].to_list() == [96.0, 864.0, 96.0, 864.0]
    # The AG follows its trial: its window sits AFTER trial_end_ts, not before the trial.
    assert ag["t_mid"].min() > calib["t_mid"].max()
    assert ag["period"].to_list() == ["rainbow", "rainbow"]


def test_only_calib_dwells_are_marked_for_the_fit():
    obs = am.dwell_observations(_perfect_gaze(), _trials(), DWELLS)
    assert obs.filter(pl.col("in_fit"))["kind"].unique().to_list() == ["calib"]


def test_dwell_with_too_little_gaze_is_dropped_not_zero_filled():
    obs = am.dwell_observations(_gaze(lambda sec: None), _trials(), DWELLS)
    assert obs.is_empty()


# --- fit_correction ------------------------------------------------------


def test_fit_recovers_the_generating_map_from_calib_dwells():
    obs = am.dwell_observations(_perfect_gaze(), _trials(), DWELLS)
    fit = am.fit_correction(obs)
    assert fit["gain_x"] == pytest.approx(1 / SCALE_X, rel=1e-6)
    assert fit["gain_y"] == pytest.approx(1 / SCALE_Y, rel=1e-6)
    assert fit["coef_x"][1] == pytest.approx(0.0, abs=1e-9)
    assert fit["gain_sign_ok"] is True
    assert fit["n_dwells_calib"] == 4 and fit["n_dwells_ag"] == 2


def test_ag_centres_cannot_move_the_fit():
    """AG windows are observed-gaze only. A session where the subject stared at the
    corner during every AG must fit identically to one where they looked at centre."""
    base = am.fit_correction(am.dwell_observations(_perfect_gaze(), _trials(), DWELLS))
    skewed = am.fit_correction(
        am.dwell_observations(_perfect_gaze(ag_frac=(0.05, 0.95)), _trials(), DWELLS)
    )
    assert skewed["coef_x"] == base["coef_x"]
    assert skewed["coef_y"] == base["coef_y"]


def test_negative_gain_is_reported_not_silently_accepted():
    obs = am.dwell_observations(_perfect_gaze(), _trials(), DWELLS).with_columns(
        (SCALE_X - pl.col("ox")).alias("ox")  # x channel anti-correlated with position
    )
    fit = am.fit_correction(obs)
    assert fit["gain_x"] < 0
    assert fit["gain_sign_ok"] is False


def test_midline_dwells_are_excluded_from_decode():
    """diam's calib clip puts T/B at x~0.5 and L/R at y~0.5, so no dwell is informative
    on both axes and the combined score has no denominator."""
    obs = am.dwell_observations(_perfect_gaze(), _trials(), DWELLS).with_columns(
        pl.Series("ky", [0.5, 0.5, 0.5, 0.5] + [0.5] * 2),
    )
    fit = am.fit_correction(obs)
    assert fit["n_informative_x"] == 4
    assert fit["n_informative_y"] == 0
    assert fit["n_informative_both"] == 0
    assert fit["decode_lr_calib"] == 1.0
    assert math.isnan(fit["decode_tb_calib"])
    assert math.isnan(fit["decode_quadrant_calib"])


def test_fit_raises_rather_than_fitting_two_points():
    obs = am.dwell_observations(_perfect_gaze(), _trials(), DWELLS).head(2)
    with pytest.raises(ValueError, match="needs >=3 calib dwells"):
        am.fit_correction(obs)


# --- tagging -------------------------------------------------------------


BOXES = am.frac_boxes({
    "UL": {"cx": 0.225, "cy": 0.225, "w": 0.45, "h": 0.45},
    "BR": {"cx": 0.775, "cy": 0.775, "w": 0.45, "h": 0.45},
})


def test_tag_aoi_distinguishes_out_from_offscreen():
    assert am.tag_aoi(0.2, 0.2, BOXES) == "UL"
    assert am.tag_aoi(0.5, 0.05, BOXES) == "OUT"        # on the video, in no box
    assert am.tag_aoi(-0.5, 0.5, BOXES) == "OFFSCREEN"  # off the video entirely
    assert am.tag_aoi(float("nan"), 0.5, BOXES) == "OFFSCREEN"


def test_tag_gaze_covers_trials_only_and_lands_in_the_right_box():
    trials = _trials()
    fit = am.fit_correction(am.dwell_observations(_perfect_gaze(), trials, DWELLS))
    # Subject looks at UL for the whole recording.
    gaze = _gaze(lambda sec: (0.2, 0.2))
    tagged = am.tag_gaze(gaze, trials, fit, BOXES)

    assert set(tagged["trial_name"]) == {"quad_01_car_UL.mp4", "quad_02_apple_UR.mp4"}
    assert set(tagged["aoi_tag"]) == {"UL"}
    assert tagged["trial_sec"].min() >= 0
    assert tagged["trial_sec"].max() < 18.0
