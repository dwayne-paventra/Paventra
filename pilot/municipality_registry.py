"""Registered municipality configurations and active selection."""

from __future__ import annotations

import os
from pathlib import Path

from pilot.municipality_config import MunicipalityConfig, resolve_municipality


PROJECT_ROOT = Path(__file__).resolve().parent.parent
MUNICIPALITY_ENV_VAR = "PAVENTRA_MUNICIPALITY"
PILOT_MODE_ENV_VAR = "PAVENTRA_MODE"

JACKSON_MUNICIPALITY = MunicipalityConfig(
    municipality_id="jackson-mi",
    slug="jackson",
    name="Jackson",
    state="Michigan",
    display_name="City of Jackson",
    data_directory=PROJECT_ROOT / "data" / "jackson",
    data_path=PROJECT_ROOT / "data" / "jackson" / "roads_jackson_demo.csv",
    map_center=(42.2459, -84.4013),
    map_zoom=12,
    pilot_mode="jackson_pilot",
    inventory_adapter="canonical_demo",
)

DEMO_CITY_MUNICIPALITY = MunicipalityConfig(
    municipality_id="demo-city-mi",
    slug="demo_city",
    name="Demo City",
    state="Michigan",
    display_name="City of Demo City",
    data_directory=PROJECT_ROOT / "data" / "demo_city",
    data_path=PROJECT_ROOT / "data" / "demo_city" / "roads_demo_city.csv",
    map_center=(42.3100, -84.0200),
    map_zoom=12,
    pilot_mode="demo_city_pilot",
    inventory_adapter="canonical_demo",
)

MUNICIPALITIES = {
    JACKSON_MUNICIPALITY.slug: JACKSON_MUNICIPALITY,
    DEMO_CITY_MUNICIPALITY.slug: DEMO_CITY_MUNICIPALITY,
}
DEFAULT_MUNICIPALITY_SLUG = JACKSON_MUNICIPALITY.slug


def get_municipality_config(slug: str | None) -> MunicipalityConfig:
    """Resolve one registered municipality by slug."""

    return resolve_municipality(MUNICIPALITIES, slug, DEFAULT_MUNICIPALITY_SLUG)


def get_active_municipality_config() -> MunicipalityConfig:
    """Resolve the active municipality from the environment."""

    return get_municipality_config(os.getenv(MUNICIPALITY_ENV_VAR))


ACTIVE_MUNICIPALITY = get_active_municipality_config()


def is_active_municipality_pilot_mode() -> bool:
    """Return whether the active municipality's pilot should be rendered."""

    configured_mode = os.getenv(PILOT_MODE_ENV_VAR, ACTIVE_MUNICIPALITY.pilot_mode)
    return configured_mode.strip().lower() == ACTIVE_MUNICIPALITY.pilot_mode
