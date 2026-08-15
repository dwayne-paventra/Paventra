"""Central data-provenance contract for inventories, UI, and reports."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import pandas as pd


class DataProvenanceStatus(str, Enum):
    """Stable canonical identifiers for supported inventory provenance states."""

    ILLUSTRATIVE = "illustrative"
    PROVISIONAL = "provisional"
    OFFICIAL = "official"


DEFAULT_DATA_STATUS = DataProvenanceStatus.ILLUSTRATIVE.value
LEGACY_ILLUSTRATIVE_STATUS = "Illustrative demonstration data"


@dataclass(frozen=True)
class DataProvenanceDefinition:
    """Status-aware language shared by the application and generated reports."""

    status: DataProvenanceStatus
    label: str
    analysis_label: str
    notice_template: str
    inventory_statement: str
    validation_heading: str

    def notice(self, formal_name: str) -> str:
        return self.notice_template.format(formal_name=formal_name)


DATA_PROVENANCE_DEFINITIONS = {
    DataProvenanceStatus.ILLUSTRATIVE: DataProvenanceDefinition(
        status=DataProvenanceStatus.ILLUSTRATIVE,
        label="Illustrative",
        analysis_label="Illustrative demonstration analysis",
        notice_template=(
            "Illustrative demonstration environment — Not an official "
            "{formal_name} analysis."
        ),
        inventory_statement=(
            "Roadway records, PCI values, costs, and map locations are synthetic or "
            "illustrative demonstration inputs."
        ),
        validation_heading="A validation pilot would replace or validate these inputs:",
    ),
    DataProvenanceStatus.PROVISIONAL: DataProvenanceDefinition(
        status=DataProvenanceStatus.PROVISIONAL,
        label="Provisional",
        analysis_label="Provisional analysis",
        notice_template=(
            "Provisional analysis — Inventory inputs have not been designated official "
            "by {formal_name}."
        ),
        inventory_statement=(
            "Roadway records, PCI values, costs, and map locations are provisional "
            "inputs and may change after agency validation."
        ),
        validation_heading="An official analysis would validate these inputs:",
    ),
    DataProvenanceStatus.OFFICIAL: DataProvenanceDefinition(
        status=DataProvenanceStatus.OFFICIAL,
        label="Official",
        analysis_label="Official-data analysis",
        notice_template=(
            "Official-data analysis — Inventory status is explicitly configured as "
            "official for {formal_name}."
        ),
        inventory_statement=(
            "Roadway inventory inputs are explicitly configured as official. Paventra "
            "does not independently certify agency approval or data accuracy."
        ),
        validation_heading="Ongoing data stewardship should maintain these inputs:",
    ),
}

_STATUS_ALIASES = {
    DataProvenanceStatus.ILLUSTRATIVE.value: DataProvenanceStatus.ILLUSTRATIVE,
    LEGACY_ILLUSTRATIVE_STATUS.casefold(): DataProvenanceStatus.ILLUSTRATIVE,
    DataProvenanceStatus.PROVISIONAL.value: DataProvenanceStatus.PROVISIONAL,
    DataProvenanceStatus.OFFICIAL.value: DataProvenanceStatus.OFFICIAL,
}


def normalize_data_status(value: object, *, field_name: str = "data_status") -> str:
    """Normalize one accepted status or fail with the centralized vocabulary."""

    if isinstance(value, DataProvenanceStatus):
        return value.value
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"field '{field_name}' must be a non-empty data status.")
    key = " ".join(value.strip().casefold().split())
    try:
        return _STATUS_ALIASES[key].value
    except KeyError as exc:
        supported = ", ".join(status.value for status in DataProvenanceStatus)
        raise ValueError(
            f"field '{field_name}' has unsupported data status '{value}'. "
            f"Supported canonical values: {supported}."
        ) from exc


def get_data_provenance(value: object) -> DataProvenanceDefinition:
    """Return shared presentation metadata for an accepted status or alias."""

    return DATA_PROVENANCE_DEFINITIONS[DataProvenanceStatus(normalize_data_status(value))]


def resolve_inventory_data_status(
    roads: pd.DataFrame,
    *,
    expected_status: object | None = None,
    municipality_slug: str | None = None,
) -> str:
    """Validate row statuses and their agreement with configured municipality intent."""

    identity = f" for municipality '{municipality_slug}'" if municipality_slug else ""
    if "data_status" not in roads.columns:
        raise ValueError(f"Canonical inventory{identity} is missing field 'data_status'.")
    if roads.empty:
        raise ValueError(f"Canonical inventory{identity} must contain at least one row.")

    normalized: list[str] = []
    invalid: list[str] = []
    for position, value in enumerate(roads["data_status"], start=2):
        try:
            normalized.append(normalize_data_status(value))
        except ValueError:
            invalid.append(f"row {position}: {value!r}")
    if invalid:
        raise ValueError(
            f"Canonical inventory{identity} field 'data_status' contains unsupported "
            f"values ({'; '.join(invalid)}). Supported canonical values: illustrative, "
            "provisional, official."
        )

    distinct = sorted(set(normalized))
    if len(distinct) != 1:
        raise ValueError(
            f"Canonical inventory{identity} field 'data_status' must be consistent "
            f"across all rows; found: {', '.join(distinct)}."
        )
    resolved = distinct[0]
    if expected_status is not None:
        expected = normalize_data_status(expected_status)
        if resolved != expected:
            raise ValueError(
                f"Canonical inventory{identity} field 'data_status' resolves to "
                f"'{resolved}' but configured data_status is '{expected}'."
            )
    return resolved


def normalize_inventory_data_status(
    roads: pd.DataFrame,
    *,
    expected_status: object | None = None,
    municipality_slug: str | None = None,
) -> pd.DataFrame:
    """Return a copy whose validated row status uses the stable canonical identifier."""

    normalized = roads.copy()
    resolved = resolve_inventory_data_status(
        normalized,
        expected_status=expected_status,
        municipality_slug=municipality_slug,
    )
    normalized["data_status"] = resolved
    return normalized
