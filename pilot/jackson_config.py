"""Jackson Pilot configuration.

The dataset shipped with this repository is illustrative and is not sourced
from, approved by, or representative of the City of Jackson.
"""

from __future__ import annotations

import os
from pathlib import Path

from pilot.municipality_config import MunicipalityConfig, resolve_municipality


PILOT_MODE_ENV_VAR = "PAVENTRA_MODE"
MUNICIPALITY_ENV_VAR = "PAVENTRA_MUNICIPALITY"
JACKSON_PILOT_MODE = "jackson_pilot"

PROJECT_ROOT = Path(__file__).resolve().parent.parent
JACKSON_DATA_DIR = PROJECT_ROOT / "data" / "jackson"
JACKSON_DEMO_DATA_PATH = JACKSON_DATA_DIR / "roads_jackson_demo.csv"

JACKSON_MUNICIPALITY = MunicipalityConfig(
    municipality_id="jackson-mi",
    slug="jackson",
    name="Jackson",
    state="Michigan",
    display_name="City of Jackson",
    data_directory=JACKSON_DATA_DIR,
    data_path=JACKSON_DEMO_DATA_PATH,
    map_center=(42.2459, -84.4013),
    map_zoom=12,
    pilot_mode=JACKSON_PILOT_MODE,
)

MUNICIPALITIES = {JACKSON_MUNICIPALITY.slug: JACKSON_MUNICIPALITY}
DEFAULT_MUNICIPALITY_SLUG = JACKSON_MUNICIPALITY.slug


def get_active_municipality_config() -> MunicipalityConfig:
    """Return the selected municipality, defaulting to Jackson."""

    return resolve_municipality(
        MUNICIPALITIES,
        os.getenv(MUNICIPALITY_ENV_VAR),
        DEFAULT_MUNICIPALITY_SLUG,
    )


ACTIVE_MUNICIPALITY = get_active_municipality_config()

# Backward-compatible Jackson constants retained for existing pilot modules.
PILOT_NAME = JACKSON_MUNICIPALITY.pilot_name
PILOT_DISCLAIMER = JACKSON_MUNICIPALITY.pilot_disclaimer
JACKSON_MAP_CENTER = JACKSON_MUNICIPALITY.map_center
JACKSON_MAP_ZOOM = JACKSON_MUNICIPALITY.map_zoom


def is_jackson_pilot_mode() -> bool:
    """Return whether the Jackson demo should be rendered.

    This Jackson-specific repository opens the pilot by default. An explicit
    non-Jackson ``PAVENTRA_MODE`` value still exposes the retained legacy app.
    """

    configured_mode = os.getenv(PILOT_MODE_ENV_VAR, ACTIVE_MUNICIPALITY.pilot_mode)
    return (
        ACTIVE_MUNICIPALITY.slug == JACKSON_MUNICIPALITY.slug
        and configured_mode.strip().lower() == ACTIVE_MUNICIPALITY.pilot_mode
    )
