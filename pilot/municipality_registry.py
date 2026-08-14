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
    entity_type="city",
    formal_name="City of Jackson",
    short_name="Jackson",
    pilot_label="Municipal Pilot",
    leadership_label="municipal leadership",
    official_action_label="official city finding",
    scenario_catalog_id="standard",
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
    entity_type="city",
    formal_name="City of Demo City",
    short_name="Demo City",
    pilot_label="Municipal Pilot",
    leadership_label="municipal leadership",
    official_action_label="official city finding",
    scenario_catalog_id="standard",
)

DEMO_ROAD_COMMISSION_MUNICIPALITY = MunicipalityConfig(
    municipality_id="demo-county-road-commission-mi",
    slug="demo_road_commission",
    name="Demo County",
    state="Michigan",
    display_name="Demo County Road Commission",
    data_directory=PROJECT_ROOT / "data" / "demo_city",
    data_path=PROJECT_ROOT / "data" / "demo_city" / "roads_demo_city.csv",
    map_center=(42.3100, -84.0200),
    map_zoom=11,
    pilot_mode="demo_road_commission_pilot",
    inventory_adapter="canonical_demo",
    entity_type="road commission",
    formal_name="Demo County Road Commission",
    short_name="Demo County",
    pilot_label="Road Commission Pilot",
    leadership_label="road commission leadership",
    official_action_label="official road commission determination",
    scenario_catalog_id="road_commission_demo",
)

MUNICIPALITIES = {
    JACKSON_MUNICIPALITY.slug: JACKSON_MUNICIPALITY,
    DEMO_CITY_MUNICIPALITY.slug: DEMO_CITY_MUNICIPALITY,
    DEMO_ROAD_COMMISSION_MUNICIPALITY.slug: DEMO_ROAD_COMMISSION_MUNICIPALITY,
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
