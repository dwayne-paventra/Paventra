"""Versioned, dependency-free contract for municipality onboarding manifests."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any


CURRENT_MANIFEST_VERSION = 1
MANIFEST_VERSION_FIELD = "manifest_version"


@dataclass(frozen=True)
class ManifestFieldDefinition:
    """Accepted shape for one field in one manifest contract version."""

    accepted_types: tuple[type, ...]
    type_description: str
    required: bool = True
    non_empty: bool = False


def _text_field() -> ManifestFieldDefinition:
    return ManifestFieldDefinition((str,), "a non-empty string", non_empty=True)


MANIFEST_V1_FIELDS = MappingProxyType(
    {
        MANIFEST_VERSION_FIELD: ManifestFieldDefinition((int,), "integer 1"),
        "municipality_id": _text_field(),
        "slug": _text_field(),
        "state": _text_field(),
        "entity_type": _text_field(),
        "formal_name": _text_field(),
        "short_name": _text_field(),
        "source_csv_path": _text_field(),
        "column_mapping": ManifestFieldDefinition(
            (Mapping,),
            "a non-empty JSON object",
            non_empty=True,
        ),
        "canonical_defaults": ManifestFieldDefinition(
            (Mapping,),
            "a JSON object",
        ),
        "map_center": ManifestFieldDefinition(
            (list, tuple),
            "a two-item latitude/longitude array",
        ),
        "map_zoom": ManifestFieldDefinition((int,), "an integer from 0 to 22"),
        "inventory_adapter": _text_field(),
        "scenario_catalog_id": _text_field(),
        "pilot_mode": _text_field(),
        "pilot_label": _text_field(),
        "leadership_label": _text_field(),
        "official_action_label": _text_field(),
    }
)

MANIFEST_CONTRACTS = MappingProxyType({1: MANIFEST_V1_FIELDS})


def get_manifest_contract(
    version: int = CURRENT_MANIFEST_VERSION,
) -> Mapping[str, ManifestFieldDefinition]:
    """Return the centralized field contract for a supported version."""

    if isinstance(version, bool) or not isinstance(version, int):
        raise ValueError(
            f"Onboarding manifest version must be an integer; received {version!r}."
        )
    try:
        return MANIFEST_CONTRACTS[version]
    except KeyError as exc:
        supported = ", ".join(str(item) for item in sorted(MANIFEST_CONTRACTS))
        raise ValueError(
            f"Unsupported onboarding manifest version '{version}'. "
            f"Supported versions: {supported}."
        ) from exc


def get_required_manifest_fields(
    version: int = CURRENT_MANIFEST_VERSION,
) -> tuple[str, ...]:
    """Return required field names for a supported contract version."""

    return tuple(
        name for name, definition in get_manifest_contract(version).items()
        if definition.required
    )


def get_optional_manifest_fields(
    version: int = CURRENT_MANIFEST_VERSION,
) -> tuple[str, ...]:
    """Return optional field names for a supported contract version."""

    return tuple(
        name for name, definition in get_manifest_contract(version).items()
        if not definition.required
    )


def validate_manifest_contract(
    manifest: Mapping[str, Any],
    manifest_path: str | Path,
) -> int:
    """Validate version first, then fields and types for that exact version."""

    path = Path(manifest_path).resolve()
    if not isinstance(manifest, Mapping):
        raise ValueError(f"Onboarding manifest '{path}' must contain a JSON object.")

    if MANIFEST_VERSION_FIELD not in manifest:
        raise ValueError(
            f"Onboarding manifest '{path}' is missing required field "
            f"'{MANIFEST_VERSION_FIELD}'."
        )
    version = manifest[MANIFEST_VERSION_FIELD]
    if isinstance(version, bool) or not isinstance(version, int):
        raise ValueError(
            f"Onboarding manifest '{path}' field '{MANIFEST_VERSION_FIELD}' "
            f"must be an integer; received {version!r}."
        )
    if version not in MANIFEST_CONTRACTS:
        supported = ", ".join(str(item) for item in sorted(MANIFEST_CONTRACTS))
        raise ValueError(
            f"Onboarding manifest '{path}' has unsupported "
            f"'{MANIFEST_VERSION_FIELD}' value '{version}'. Supported versions: "
            f"{supported}."
        )

    contract = get_manifest_contract(version)
    missing = [
        name for name, definition in contract.items()
        if definition.required and name not in manifest
    ]
    if missing:
        raise ValueError(
            f"Onboarding manifest '{path}' is missing required fields: "
            f"{', '.join(missing)} (manifest version {version})."
        )
    unknown = sorted(set(manifest) - set(contract))
    if unknown:
        raise ValueError(
            f"Onboarding manifest '{path}' contains unknown fields: "
            f"{', '.join(unknown)} (manifest version {version})."
        )

    for name, definition in contract.items():
        if name not in manifest:
            continue
        value = manifest[name]
        invalid_boolean = isinstance(value, bool) and int in definition.accepted_types
        if invalid_boolean or not isinstance(value, definition.accepted_types):
            raise ValueError(
                f"Onboarding manifest '{path}' field '{name}' must be "
                f"{definition.type_description}; received {type(value).__name__}."
            )
        if definition.non_empty and not value:
            raise ValueError(
                f"Onboarding manifest '{path}' field '{name}' must be "
                f"{definition.type_description}."
            )
        if definition.non_empty and isinstance(value, str) and not value.strip():
            raise ValueError(
                f"Onboarding manifest '{path}' field '{name}' must be "
                f"{definition.type_description}."
            )
    return version
