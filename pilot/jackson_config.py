"""Jackson Pilot configuration.

The dataset shipped with this repository is illustrative and is not sourced
from, approved by, or representative of the City of Jackson.
"""

from __future__ import annotations

import os
from pathlib import Path


PILOT_NAME = "Jackson Municipal Pilot"
PILOT_DISCLAIMER = (
    "Demonstration Environment — Not an official City of Jackson analysis."
)
PILOT_MODE_ENV_VAR = "PAVENTRA_MODE"
JACKSON_PILOT_MODE = "jackson_pilot"

PROJECT_ROOT = Path(__file__).resolve().parent.parent
JACKSON_DATA_DIR = PROJECT_ROOT / "data" / "jackson"
JACKSON_DEMO_DATA_PATH = JACKSON_DATA_DIR / "roads_jackson_demo.csv"

JACKSON_MAP_CENTER = (42.2459, -84.4013)
JACKSON_MAP_ZOOM = 12


def is_jackson_pilot_mode() -> bool:
    """Return whether the Jackson demo should be rendered.

    This Jackson-specific repository opens the pilot by default. An explicit
    non-Jackson ``PAVENTRA_MODE`` value still exposes the retained legacy app.
    """

    configured_mode = os.getenv(PILOT_MODE_ENV_VAR, JACKSON_PILOT_MODE)
    return configured_mode.strip().lower() == JACKSON_PILOT_MODE
