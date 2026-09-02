"""Single seam for webcam video location, plus stimulus timing constants.

Keyed on the session key (firebase_doc_id), not panda_id: one panda_id can
run the study twice, in two different layouts.
"""

from __future__ import annotations

import os
from pathlib import Path

# In-clip time of the LAST beep of each calib clip's 4-beep train, measured
# offline from quad-calib.mp4 / diam-calib.mp4. Per-layout because the trains
# start at different in-clip offsets (0.5125 vs 2.0125), not because spacing
# differs. Do NOT inherit 01_pilot's FIRST_BEEP_OFFSET_SEC = 1.0121.
LAST_BEEP_OFFSET_SEC = {"quad": 3.5099, "diam": 5.0099}

_DEFAULT_ROOT = Path(__file__).resolve().parents[2] / "data" / "participants"


def video_dir(session_key: str) -> Path:
    root = Path(os.environ.get("DS_VIDEO_ROOT", _DEFAULT_ROOT))
    return root / session_key / "videos"


# Artifacts the OWLET stage writes into the same videos/ dir. They must never be
# mistaken for a subject video: <stem>_calibration.mp4 is a ~27s cut of the session
# and would yield a short but entirely valid-looking owlet_raw.csv.
_DERIVED_SUFFIXES = ("_calibration", "_annotated")


def _is_derived(p: Path) -> bool:
    return any(s in p.stem for s in _DERIVED_SUFFIXES)


def video_path(session_key: str) -> Path:
    """Resolve the one webcam video for a session (firebase_doc_id).

    Globs *.webm first, then *.mp4 (a CFR-transcoded <stem>.mp4 sitting
    beside its .webm source is legitimate, not a conflict). Skips this
    pipeline's own outputs. Raises if a pattern matches more than once,
    or if nothing matches at all.
    """
    d = video_dir(session_key)
    for pattern in ("*.webm", "*.mp4"):
        matches = sorted(p for p in d.glob(pattern) if not _is_derived(p))
        if len(matches) > 1:
            names = ", ".join(m.name for m in matches)
            raise ValueError(
                f"Multiple {pattern} videos for session={session_key!r} in {d}: {names}"
            )
        if matches:
            return matches[0]
    raise FileNotFoundError(f"No video found for session={session_key!r} in {d}")
