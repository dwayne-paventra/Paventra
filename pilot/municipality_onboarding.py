"""Mapped-CSV onboarding into the shared canonical inventory pipeline."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pandas as pd

from pilot.canonical_inventory import (
    CANONICAL_COLUMNS,
    CANONICAL_NUMERIC_COLUMNS,
    enrich_canonical_inventory,
    to_streamlit_inventory,
    validate_canonical_schema,
)
from pilot.municipality_config import MunicipalityConfig, validate_municipality_config


def _source_csv_rows(mask: pd.Series) -> list[int]:
    """Convert a positional validation mask to one-based CSV rows plus a header."""

    return [position + 2 for position, invalid in enumerate(mask) if invalid]


def validate_onboarding_configuration(
    config: MunicipalityConfig,
    column_mapping: Mapping[str, str] | None = None,
    canonical_defaults: Mapping[str, Any] | None = None,
) -> tuple[dict[str, str], dict[str, Any]]:
    """Validate identity, adapter/catalog references, mappings, and defaults."""

    validate_municipality_config(config)

    from pilot.municipality_data import INVENTORY_ADAPTERS
    from pilot.municipality_scenarios import SCENARIO_CATALOGS

    if config.inventory_adapter not in INVENTORY_ADAPTERS:
        raise ValueError(
            f"Municipality '{config.slug}' field 'inventory_adapter' references "
            f"unknown adapter '{config.inventory_adapter}'."
        )
    if config.scenario_catalog_id not in SCENARIO_CATALOGS:
        raise ValueError(
            f"Municipality '{config.slug}' field 'scenario_catalog_id' references "
            f"unknown catalog '{config.scenario_catalog_id}'."
        )

    resolved_mapping = (
        config.source_column_mapping if column_mapping is None else column_mapping
    )
    resolved_defaults = (
        config.canonical_defaults if canonical_defaults is None else canonical_defaults
    )
    if not isinstance(resolved_mapping, Mapping) or not resolved_mapping:
        raise ValueError(
            f"Municipality '{config.slug}' field 'source_column_mapping' must be a non-empty mapping."
        )
    if resolved_defaults is None:
        resolved_defaults = {}
    if not isinstance(resolved_defaults, Mapping):
        raise ValueError(
            f"Municipality '{config.slug}' field 'canonical_defaults' must be a mapping."
        )

    normalized_mapping: dict[str, str] = {}
    target_sources: dict[str, str] = {}
    for source_column, canonical_column in resolved_mapping.items():
        if not isinstance(source_column, str) or not source_column.strip():
            raise ValueError(
                f"Municipality '{config.slug}' has an empty source column mapping key."
            )
        if canonical_column not in CANONICAL_COLUMNS:
            raise ValueError(
                f"Municipality '{config.slug}' source column '{source_column}' maps to "
                f"unknown canonical field '{canonical_column}'."
            )
        if canonical_column in target_sources:
            raise ValueError(
                f"Municipality '{config.slug}' source columns '{target_sources[canonical_column]}' "
                f"and '{source_column}' both map to canonical field '{canonical_column}'."
            )
        normalized_mapping[source_column] = canonical_column
        target_sources[canonical_column] = source_column

    normalized_defaults = dict(resolved_defaults)
    unknown_defaults = sorted(set(normalized_defaults) - set(CANONICAL_COLUMNS))
    if unknown_defaults:
        raise ValueError(
            f"Municipality '{config.slug}' field 'canonical_defaults' contains unknown "
            f"canonical fields: {', '.join(unknown_defaults)}."
        )
    overlaps = sorted(set(normalized_defaults) & set(target_sources))
    if overlaps:
        raise ValueError(
            f"Municipality '{config.slug}' maps and defaults the same canonical fields: "
            f"{', '.join(overlaps)}."
        )
    return normalized_mapping, normalized_defaults


def map_source_to_canonical(
    config: MunicipalityConfig,
    source_roads: pd.DataFrame,
    column_mapping: Mapping[str, str] | None = None,
    canonical_defaults: Mapping[str, Any] | None = None,
) -> pd.DataFrame:
    """Rename and coerce source data, then delegate canonical validation."""

    mapping, defaults = validate_onboarding_configuration(
        config,
        column_mapping,
        canonical_defaults,
    )
    if not isinstance(source_roads, pd.DataFrame) or source_roads.empty:
        raise ValueError(
            f"Municipality '{config.slug}' source inventory must contain at least one road."
        )

    missing_source_columns = [
        column for column in mapping if column not in source_roads.columns
    ]
    if missing_source_columns:
        details = ", ".join(
            f"'{column}' -> '{mapping[column]}'" for column in missing_source_columns
        )
        raise ValueError(
            f"Municipality '{config.slug}' source inventory is missing mapped columns: {details}."
        )

    canonical = source_roads.rename(columns=mapping).copy()
    duplicate_columns = canonical.columns[canonical.columns.duplicated()].unique()
    if len(duplicate_columns):
        raise ValueError(
            f"Municipality '{config.slug}' source mappings produce duplicate canonical "
            f"fields: {', '.join(duplicate_columns)}."
        )
    for canonical_column, value in defaults.items():
        canonical[canonical_column] = value

    missing_canonical = [
        column for column in CANONICAL_COLUMNS if column not in canonical.columns
    ]
    if missing_canonical:
        raise ValueError(
            f"Municipality '{config.slug}' onboarding is missing source mappings or defaults "
            f"for canonical fields: {', '.join(missing_canonical)}."
        )
    canonical = canonical.loc[:, CANONICAL_COLUMNS].copy()

    for identifier in ("road_id", "segment_id"):
        missing_identifier = (
            canonical[identifier].isna()
            | canonical[identifier].astype(str).str.strip().eq("")
        )
        if missing_identifier.any():
            rows = _source_csv_rows(missing_identifier)
            raise ValueError(
                f"Municipality '{config.slug}' canonical field '{identifier}' has missing "
                f"values at source CSV rows: {rows}."
            )
        canonical[identifier] = canonical[identifier].astype(str).str.strip()
        duplicate_identifier = canonical[identifier].duplicated(keep=False)
        if duplicate_identifier.any():
            duplicates = sorted(canonical.loc[duplicate_identifier, identifier].unique())
            raise ValueError(
                f"Municipality '{config.slug}' canonical field '{identifier}' must be unique; "
                f"duplicate values: {', '.join(duplicates)}."
            )

    for column in CANONICAL_NUMERIC_COLUMNS:
        numeric = pd.to_numeric(canonical[column], errors="coerce")
        invalid = numeric.isna()
        if invalid.any():
            rows = _source_csv_rows(invalid)
            raise ValueError(
                f"Municipality '{config.slug}' canonical numeric field '{column}' contains "
                f"invalid values at source CSV rows: {rows}."
            )
        canonical[column] = numeric

    coordinate_ranges = {
        "latitude": (-90, 90),
        "longitude": (-180, 180),
    }
    for column, (minimum, maximum) in coordinate_ranges.items():
        unusable = ~canonical[column].between(minimum, maximum)
        if unusable.any():
            rows = _source_csv_rows(unusable)
            raise ValueError(
                f"Municipality '{config.slug}' canonical field '{column}' must be between "
                f"{minimum} and {maximum}; invalid source CSV rows: {rows}."
            )

    try:
        validate_canonical_schema(canonical)
    except ValueError as exc:
        raise ValueError(
            f"Municipality '{config.slug}' canonical inventory validation failed: {exc}"
        ) from exc
    return canonical


def load_onboarded_canonical_inventory(
    config: MunicipalityConfig,
    source_path: str | Path | None = None,
    column_mapping: Mapping[str, str] | None = None,
    canonical_defaults: Mapping[str, Any] | None = None,
) -> pd.DataFrame:
    """Load and map a source CSV, then use the shared canonical enrichment."""

    path = Path(source_path) if source_path is not None else config.data_path
    try:
        source_roads = pd.read_csv(path)
    except FileNotFoundError as exc:
        raise ValueError(
            f"Municipality '{config.slug}' source inventory CSV was not found at '{path}'."
        ) from exc
    except (OSError, pd.errors.ParserError) as exc:
        raise ValueError(
            f"Municipality '{config.slug}' source inventory CSV at '{path}' could not be read: {exc}"
        ) from exc
    canonical = map_source_to_canonical(
        config,
        source_roads,
        column_mapping,
        canonical_defaults,
    )
    return enrich_canonical_inventory(canonical)


def load_onboarded_streamlit_inventory(config: MunicipalityConfig) -> pd.DataFrame:
    """Load an onboarded source through the existing shared UI conversion."""

    enriched = load_onboarded_canonical_inventory(config)
    return to_streamlit_inventory(enriched, agency_name=config.short_name)
