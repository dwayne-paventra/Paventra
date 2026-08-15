"""Registered municipality configurations and active selection."""

from __future__ import annotations

from collections.abc import Mapping
import os
from pathlib import Path

from pilot.municipality_config import (
    MunicipalityConfig,
    resolve_municipality,
    validate_municipality_config,
)
from pilot.municipality_onboarding import load_onboarding_manifest


PROJECT_ROOT = Path(__file__).resolve().parent.parent
MUNICIPALITY_ENV_VAR = "PAVENTRA_MUNICIPALITY"
PILOT_MODE_ENV_VAR = "PAVENTRA_MODE"

JACKSON_MUNICIPALITY = MunicipalityConfig(
    municipality_id="jackson-mi",
    slug="jackson",
    state="Michigan",
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
    data_status="illustrative",
)

DEMO_CITY_MUNICIPALITY = MunicipalityConfig(
    municipality_id="demo-city-mi",
    slug="demo_city",
    state="Michigan",
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
    data_status="illustrative",
)

DEMO_ROAD_COMMISSION_MUNICIPALITY = MunicipalityConfig(
    municipality_id="demo-county-road-commission-mi",
    slug="demo_road_commission",
    state="Michigan",
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
    data_status="illustrative",
)

ONBOARDING_DEMO_MANIFEST_PATH = (
    PROJECT_ROOT / "data" / "onboarding_demo" / "manifest.json"
)
ONBOARDING_DEMO_MUNICIPALITY = load_onboarding_manifest(
    ONBOARDING_DEMO_MANIFEST_PATH
)
# Phase 7 compatibility alias. The manifest is now the single source of truth.
ONBOARDING_DEMO_COLUMN_MAPPING = dict(
    ONBOARDING_DEMO_MUNICIPALITY.source_column_mapping or {}
)

MUNICIPALITIES = {
    JACKSON_MUNICIPALITY.slug: JACKSON_MUNICIPALITY,
    DEMO_CITY_MUNICIPALITY.slug: DEMO_CITY_MUNICIPALITY,
    DEMO_ROAD_COMMISSION_MUNICIPALITY.slug: DEMO_ROAD_COMMISSION_MUNICIPALITY,
    ONBOARDING_DEMO_MUNICIPALITY.slug: ONBOARDING_DEMO_MUNICIPALITY,
}
DEFAULT_MUNICIPALITY_SLUG = JACKSON_MUNICIPALITY.slug


def validate_municipality_registry(
    configurations: Mapping[str, MunicipalityConfig] | None = None,
    *,
    inventory_adapters: Mapping | None = None,
    inventory_adapter_validators: Mapping | None = None,
    scenario_catalogs: Mapping | None = None,
    default_slug: str | None = None,
) -> None:
    """Validate the complete registry-to-adapter-to-catalog configuration graph."""

    registry = MUNICIPALITIES if configurations is None else configurations
    if not isinstance(registry, Mapping) or not registry:
        raise ValueError("Municipality registry must be a non-empty mapping.")

    if inventory_adapters is None:
        from pilot.municipality_data import (
            INVENTORY_ADAPTERS,
            INVENTORY_ADAPTER_VALIDATORS,
        )

        inventory_adapters = INVENTORY_ADAPTERS
        if inventory_adapter_validators is None:
            inventory_adapter_validators = INVENTORY_ADAPTER_VALIDATORS
    elif inventory_adapter_validators is None:
        inventory_adapter_validators = {}
    if scenario_catalogs is None:
        from pilot.municipality_scenarios import SCENARIO_CATALOGS

        scenario_catalogs = SCENARIO_CATALOGS

    from pilot.municipality_scenarios import validate_scenario_catalogs

    validate_scenario_catalogs(scenario_catalogs)

    seen_slugs: dict[str, str] = {}
    seen_ids: dict[str, str] = {}
    for registry_key, config in registry.items():
        if not isinstance(config, MunicipalityConfig):
            raise ValueError(
                f"Municipality registry entry '{registry_key}' must be a MunicipalityConfig."
            )
        validate_municipality_config(config)

        if config.slug in seen_slugs:
            raise ValueError(
                f"Duplicate municipality slug '{config.slug}' in registry entries "
                f"'{seen_slugs[config.slug]}' and '{registry_key}'."
            )
        seen_slugs[config.slug] = str(registry_key)

        if config.municipality_id in seen_ids:
            raise ValueError(
                f"Duplicate municipality ID '{config.municipality_id}' for "
                f"'{seen_ids[config.municipality_id]}' and '{config.slug}'."
            )
        seen_ids[config.municipality_id] = config.slug

    for registry_key, config in registry.items():
        if registry_key != config.slug:
            raise ValueError(
                f"Municipality '{config.slug}' field 'slug' does not match registry key "
                f"'{registry_key}'."
            )
        if config.inventory_adapter not in inventory_adapters:
            raise ValueError(
                f"Municipality '{config.slug}' field 'inventory_adapter' references "
                f"unknown adapter '{config.inventory_adapter}'."
            )
        if not callable(inventory_adapters[config.inventory_adapter]):
            raise ValueError(
                f"Municipality '{config.slug}' field 'inventory_adapter' references "
                f"non-callable adapter '{config.inventory_adapter}'."
            )
        if config.scenario_catalog_id not in scenario_catalogs:
            raise ValueError(
                f"Municipality '{config.slug}' field 'scenario_catalog_id' references "
                f"unknown catalog '{config.scenario_catalog_id}'."
            )
        adapter_validator = inventory_adapter_validators.get(config.inventory_adapter)
        if adapter_validator is not None:
            if not callable(adapter_validator):
                raise ValueError(
                    f"Inventory adapter validator for '{config.inventory_adapter}' "
                    "must be callable."
                )
            adapter_validator(config)

    if default_slug is not None and default_slug not in registry:
        raise ValueError(
            f"Default municipality slug '{default_slug}' is not registered."
        )


validate_municipality_registry(default_slug=DEFAULT_MUNICIPALITY_SLUG)


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
