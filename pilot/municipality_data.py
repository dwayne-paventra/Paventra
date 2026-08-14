"""Inventory adapter selection for registered municipalities."""

from __future__ import annotations

from collections.abc import Callable

import pandas as pd

from pilot.municipality_config import MunicipalityConfig


InventoryAdapter = Callable[[MunicipalityConfig], pd.DataFrame]


def _load_canonical_demo_inventory(config: MunicipalityConfig) -> pd.DataFrame:
    """Load a canonical demonstration CSV through the shared adapter."""

    from pilot.canonical_inventory import load_streamlit_inventory

    return load_streamlit_inventory(
        config.data_path,
        agency_name=config.short_name,
    )


INVENTORY_ADAPTERS: dict[str, InventoryAdapter] = {
    "canonical_demo": _load_canonical_demo_inventory,
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
