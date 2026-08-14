"""Generic municipality identity and file-location configuration."""

from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
from typing import Mapping, Any


SUPPORTED_ENTITY_TYPES = frozenset({
    "agency",
    "city",
    "county",
    "municipality",
    "road commission",
    "township",
    "village",
})


@dataclass(frozen=True)
class MunicipalityConfig:
    """Identity and deployment values that vary by municipality."""

    municipality_id: str
    slug: str
    state: str
    data_directory: Path
    data_path: Path
    map_center: tuple[float, float]
    map_zoom: int
    pilot_mode: str
    inventory_adapter: str
    entity_type: str
    formal_name: str
    short_name: str
    pilot_label: str
    leadership_label: str
    official_action_label: str
    scenario_catalog_id: str
    source_column_mapping: Mapping[str, str] | None = None
    canonical_defaults: Mapping[str, Any] | None = None

    @property
    def name(self) -> str:
        """Deprecated compatibility alias for ``short_name``."""

        return self.short_name

    @property
    def display_name(self) -> str:
        """Deprecated compatibility alias for ``formal_name``."""

        return self.formal_name

    @property
    def pilot_name(self) -> str:
        return f"{self.short_name} {self.pilot_label}"

    @property
    def pilot_disclaimer(self) -> str:
        return f"Demonstration Environment — Not an official {self.formal_name} analysis."


def validate_municipality_config(config: MunicipalityConfig) -> None:
    """Validate one municipality's intrinsic identity and map configuration."""

    identity = config.slug.strip() or config.municipality_id.strip() or "<unknown>"

    required_text_fields = (
        "municipality_id",
        "slug",
        "state",
        "entity_type",
        "formal_name",
        "short_name",
        "pilot_label",
        "leadership_label",
        "official_action_label",
        "pilot_mode",
        "inventory_adapter",
        "scenario_catalog_id",
    )
    for field_name in required_text_fields:
        value = getattr(config, field_name)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(
                f"Municipality '{identity}' field '{field_name}' must be a non-empty string."
            )

    if config.entity_type.strip().lower() not in SUPPORTED_ENTITY_TYPES:
        supported = ", ".join(sorted(SUPPORTED_ENTITY_TYPES))
        raise ValueError(
            f"Municipality '{identity}' field 'entity_type' has unsupported value "
            f"'{config.entity_type}'. Supported values: {supported}."
        )

    if not isinstance(config.map_center, (tuple, list)) or len(config.map_center) != 2:
        raise ValueError(
            f"Municipality '{identity}' field 'map_center' must contain latitude and longitude."
        )
    latitude, longitude = config.map_center
    if (
        isinstance(latitude, bool)
        or not isinstance(latitude, (int, float))
        or not math.isfinite(latitude)
        or not -90 <= latitude <= 90
    ):
        raise ValueError(
            f"Municipality '{identity}' field 'map_center.latitude' must be between -90 and 90."
        )
    if (
        isinstance(longitude, bool)
        or not isinstance(longitude, (int, float))
        or not math.isfinite(longitude)
        or not -180 <= longitude <= 180
    ):
        raise ValueError(
            f"Municipality '{identity}' field 'map_center.longitude' must be between -180 and 180."
        )

    if isinstance(config.map_zoom, bool) or not isinstance(config.map_zoom, int) or not 0 <= config.map_zoom <= 22:
        raise ValueError(
            f"Municipality '{identity}' field 'map_zoom' must be an integer between 0 and 22."
        )

    for field_name in ("data_directory", "data_path"):
        value = getattr(config, field_name)
        if not isinstance(value, Path) or value == Path():
            raise ValueError(
                f"Municipality '{identity}' field '{field_name}' must be a configured Path."
            )


def resolve_municipality(
    configurations: Mapping[str, MunicipalityConfig],
    requested_slug: str | None,
    default_slug: str,
) -> MunicipalityConfig:
    """Resolve a configured municipality, using a declared default when unset."""

    slug = (requested_slug or default_slug).strip().lower()
    try:
        return configurations[slug]
    except KeyError as exc:
        available = ", ".join(sorted(configurations))
        raise ValueError(
            f"Unknown municipality '{slug}'. Available municipalities: {available}."
        ) from exc
