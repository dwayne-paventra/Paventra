"""Declarative mapped-CSV onboarding into the canonical inventory pipeline."""

from __future__ import annotations

import argparse
from collections.abc import Mapping
import json
from pathlib import Path
import sys
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


MANIFEST_REQUIRED_FIELDS = (
    "municipality_id",
    "slug",
    "state",
    "entity_type",
    "formal_name",
    "short_name",
    "source_csv_path",
    "column_mapping",
    "canonical_defaults",
    "map_center",
    "map_zoom",
    "inventory_adapter",
    "scenario_catalog_id",
    "pilot_mode",
    "pilot_label",
    "leadership_label",
    "official_action_label",
)


def parse_onboarding_manifest(
    manifest: Mapping[str, Any],
    manifest_path: str | Path,
) -> MunicipalityConfig:
    """Construct and validate the existing config model from one manifest."""

    path = Path(manifest_path).resolve()
    if not isinstance(manifest, Mapping):
        raise ValueError(f"Onboarding manifest '{path}' must contain a JSON object.")

    missing = [field for field in MANIFEST_REQUIRED_FIELDS if field not in manifest]
    if missing:
        raise ValueError(
            f"Onboarding manifest '{path}' is missing required fields: "
            f"{', '.join(missing)}."
        )
    unknown = sorted(set(manifest) - set(MANIFEST_REQUIRED_FIELDS))
    if unknown:
        raise ValueError(
            f"Onboarding manifest '{path}' contains unknown fields: "
            f"{', '.join(unknown)}."
        )

    source_value = manifest["source_csv_path"]
    if not isinstance(source_value, str) or not source_value.strip():
        raise ValueError(
            f"Onboarding manifest '{path}' field 'source_csv_path' must be a "
            "non-empty string."
        )
    source_path = Path(source_value)
    if not source_path.is_absolute():
        source_path = path.parent / source_path
    source_path = source_path.resolve()

    map_center = manifest["map_center"]
    if isinstance(map_center, list):
        map_center = tuple(map_center)

    config = MunicipalityConfig(
        municipality_id=manifest["municipality_id"],
        slug=manifest["slug"],
        state=manifest["state"],
        data_directory=path.parent,
        data_path=source_path,
        map_center=map_center,
        map_zoom=manifest["map_zoom"],
        pilot_mode=manifest["pilot_mode"],
        inventory_adapter=manifest["inventory_adapter"],
        entity_type=manifest["entity_type"],
        formal_name=manifest["formal_name"],
        short_name=manifest["short_name"],
        pilot_label=manifest["pilot_label"],
        leadership_label=manifest["leadership_label"],
        official_action_label=manifest["official_action_label"],
        scenario_catalog_id=manifest["scenario_catalog_id"],
        source_column_mapping=manifest["column_mapping"],
        canonical_defaults=manifest["canonical_defaults"],
    )
    validate_onboarding_configuration(config)
    return config


def load_onboarding_manifest(manifest_path: str | Path) -> MunicipalityConfig:
    """Read a JSON onboarding manifest and return a validated config."""

    path = Path(manifest_path).resolve()
    try:
        with path.open(encoding="utf-8") as manifest_file:
            manifest = json.load(manifest_file)
    except FileNotFoundError as exc:
        raise ValueError(f"Onboarding manifest was not found at '{path}'.") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Onboarding manifest '{path}' contains invalid JSON at line "
            f"{exc.lineno}, column {exc.colno}: {exc.msg}."
        ) from exc
    except OSError as exc:
        raise ValueError(f"Onboarding manifest '{path}' could not be read: {exc}") from exc
    return parse_onboarding_manifest(manifest, path)


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


def prepare_manifest_inventory(
    manifest_path: str | Path,
) -> tuple[MunicipalityConfig, pd.DataFrame]:
    """Run a manifest source through the existing validated onboarding pipeline."""

    config = load_onboarding_manifest(manifest_path)
    inventory = load_onboarded_canonical_inventory(config)
    return config, inventory


def export_canonical_inventory(
    inventory: pd.DataFrame,
    output_path: str | Path,
    *,
    force: bool = False,
) -> Path:
    """Write validated canonical columns in deterministic order."""

    output = Path(output_path).resolve()
    canonical = inventory.loc[:, CANONICAL_COLUMNS].copy()
    validate_canonical_schema(canonical)

    if output.exists() and not force:
        raise ValueError(
            f"Output file '{output}' already exists; use --force to overwrite it."
        )
    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        mode = "w" if force else "x"
        with output.open(mode, encoding="utf-8", newline="") as output_file:
            canonical.to_csv(output_file, index=False, lineterminator="\n")
    except FileExistsError as exc:
        raise ValueError(
            f"Output file '{output}' already exists; use --force to overwrite it."
        ) from exc
    except OSError as exc:
        raise ValueError(f"Canonical output '{output}' could not be written: {exc}") from exc
    return output


def _print_onboarding_summary(
    config: MunicipalityConfig,
    manifest_path: Path,
    inventory: pd.DataFrame,
    output_path: Path | None,
) -> None:
    mapping = dict(config.source_column_mapping or {})
    defaults = dict(config.canonical_defaults or {})
    mapped_columns = ", ".join(
        f"{source} -> {canonical}" for source, canonical in mapping.items()
    )
    default_fields = ", ".join(defaults) if defaults else "none"

    print(f"Municipality: {config.formal_name} ({config.slug})")
    print(f"Manifest: {manifest_path}")
    print(f"Source CSV: {config.data_path}")
    print(f"Source rows: {len(inventory)}")
    print(f"Canonical rows: {len(inventory)}")
    print(f"Mapped columns ({len(mapping)}): {mapped_columns}")
    print(f"Defaults used ({len(defaults)}): {default_fields}")
    print(f"Inventory adapter: {config.inventory_adapter}")
    print(f"Scenario catalog: {config.scenario_catalog_id}")
    if output_path is None:
        print("Output: no files written (dry run)")
    else:
        print(f"Output: {output_path}")
    print("Validation result: PASS")


def build_cli_parser() -> argparse.ArgumentParser:
    """Build the onboarding command-line interface."""

    parser = argparse.ArgumentParser(
        description="Validate and optionally export a municipality onboarding manifest."
    )
    parser.add_argument("--manifest", required=True, type=Path)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate the manifest and source without writing files.",
    )
    action.add_argument(
        "--output",
        type=Path,
        help="Write the validated canonical inventory CSV.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Allow --output to replace an existing file.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run declarative onboarding and return a process-style exit code."""

    parser = build_cli_parser()
    args = parser.parse_args(argv)
    if args.force and args.output is None:
        parser.error("--force requires --output")

    manifest_path = args.manifest.resolve()
    try:
        config, inventory = prepare_manifest_inventory(manifest_path)
        output_path = None
        if args.output is not None:
            output_path = export_canonical_inventory(
                inventory,
                args.output,
                force=args.force,
            )
        _print_onboarding_summary(config, manifest_path, inventory, output_path)
    except (TypeError, ValueError) as exc:
        print(f"Onboarding failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
