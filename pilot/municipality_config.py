"""Generic municipality identity and file-location configuration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


@dataclass(frozen=True)
class MunicipalityConfig:
    """Identity and deployment values that vary by municipality."""

    municipality_id: str
    slug: str
    name: str
    state: str
    display_name: str
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

    @property
    def pilot_name(self) -> str:
        return f"{self.short_name} {self.pilot_label}"

    @property
    def pilot_disclaimer(self) -> str:
        return f"Demonstration Environment — Not an official {self.formal_name} analysis."


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
