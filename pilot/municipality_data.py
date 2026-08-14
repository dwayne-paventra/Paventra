"""Inventory adapter selection for registered municipalities."""

from __future__ import annotations

from collections.abc import Callable

import pandas as pd

from pilot.municipality_config import MunicipalityConfig


InventoryAdapter = Callable[[MunicipalityConfig], pd.DataFrame]
InventoryAdapterValidator = Callable[[MunicipalityConfig], None]


def _load_canonical_demo_inventory(config: MunicipalityConfig) -> pd.DataFrame:
    """Load a canonical demonstration CSV through the shared adapter."""

    from pilot.canonical_inventory import load_streamlit_inventory

    return load_streamlit_inventory(
        config.data_path,
        agency_name=config.short_name,
    )


def _load_mapped_csv_inventory(config: MunicipalityConfig) -> pd.DataFrame:
    """Load a source CSV through the municipality onboarding mapper."""

    from pilot.municipality_onboarding import load_onboarded_streamlit_inventory

    return load_onboarded_streamlit_inventory(config)


def _validate_mapped_csv_configuration(config: MunicipalityConfig) -> None:
    """Validate mapped-source options without loading the source CSV."""

    from pilot.municipality_onboarding import validate_onboarding_configuration

    validate_onboarding_configuration(config)


INVENTORY_ADAPTERS: dict[str, InventoryAdapter] = {
    "canonical_demo": _load_canonical_demo_inventory,
    "mapped_csv": _load_mapped_csv_inventory,
}

INVENTORY_ADAPTER_VALIDATORS: dict[str, InventoryAdapterValidator] = {
    "mapped_csv": _validate_mapped_csv_configuration,
}


def load_municipality_inventory(config: MunicipalityConfig) -> pd.DataFrame:
    """Load one municipality's inventory with its configured adapter."""

    try:
        adapter = INVENTORY_ADAPTERS[config.inventory_adapter]
    except KeyError as exc:
        raise ValueError(
            f"Unknown inventory adapter '{config.inventory_adapter}' for "
            f"municipality '{config.slug}'."
        ) from exc
    return adapter(config)
