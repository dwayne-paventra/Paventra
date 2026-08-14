"""Jackson Pilot configuration.

The dataset shipped with this repository is illustrative and is not sourced
from, approved by, or representative of the City of Jackson.
"""

from pilot.municipality_registry import (
    ACTIVE_MUNICIPALITY,
    DEFAULT_MUNICIPALITY_SLUG,
    JACKSON_MUNICIPALITY,
    MUNICIPALITIES,
    MUNICIPALITY_ENV_VAR,
    PILOT_MODE_ENV_VAR,
    PROJECT_ROOT,
    get_active_municipality_config,
    is_active_municipality_pilot_mode,
)


JACKSON_PILOT_MODE = JACKSON_MUNICIPALITY.pilot_mode
JACKSON_DATA_DIR = JACKSON_MUNICIPALITY.data_directory
JACKSON_DEMO_DATA_PATH = JACKSON_MUNICIPALITY.data_path

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

    return (
        ACTIVE_MUNICIPALITY.slug == JACKSON_MUNICIPALITY.slug
        and is_active_municipality_pilot_mode()
    )
