"""Municipality-neutral canonical inventory validation and enrichment."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from predictor import calculate_risk_details


CANONICAL_COLUMNS = (
    "road_id",
    "segment_id",
    "road_name",
    "from_street",
    "to_street",
    "jurisdiction",
    "latitude",
    "longitude",
    "road_length_miles",
    "lanes",
    "surface_type",
    "functional_class",
    "pci",
    "condition_date",
    "traffic_level",
    "adt",
    "age_years",
    "freeze_thaw",
    "recommended_treatment",
    "treatment_cost_per_lane_mile",
    "data_status",
    "data_source",
    "data_updated_at",
)

_NUMERIC_COLUMNS = (
    "latitude", "longitude", "road_length_miles", "lanes", "pci", "adt",
    "age_years", "treatment_cost_per_lane_mile",
)

_UI_COLUMNS = {
    "road_id": "Road ID",
    "road_name": "Road Name",
    "pci": "PCI",
    "traffic_level": "Traffic",
    "age_years": "Age",
    "freeze_thaw": "Freeze_Thaw",
    "recommended_treatment": "Treatment",
    "latitude": "Latitude",
    "longitude": "Longitude",
    "road_length_miles": "Road Length",
    "lanes": "Lanes",
    "surface_type": "Surface Type",
    "adt": "ADT",
}


def normalize_treatment(value: object) -> str:
    """Normalize common treatment labels into the shared vocabulary."""

    normalized = str(value or "").strip().lower()
    aliases = {
        "": "Not Assigned",
        "none": "Not Assigned",
        "no treatment": "Not Assigned",
        "mill & overlay": "Mill & Fill",
        "mill and overlay": "Mill & Fill",
        "mill & fill": "Mill & Fill",
        "mill and fill": "Mill & Fill",
        "crack seal": "Crack Seal",
        "overlay": "Overlay",
        "reconstruction": "Reconstruction",
    }
    return aliases.get(normalized, str(value).strip())


def validate_canonical_schema(roads: pd.DataFrame) -> None:
    """Validate a canonical illustrative municipality inventory."""

    missing = [column for column in CANONICAL_COLUMNS if column not in roads.columns]
    if missing:
        raise ValueError(
            "Canonical inventory is missing required columns: " + ", ".join(missing)
        )

    if roads["segment_id"].isna().any() or roads["segment_id"].duplicated().any():
        raise ValueError(
            "Canonical inventory segment_id values must be present and unique."
        )

    numeric_values = {}
    for column in _NUMERIC_COLUMNS:
        numeric_values[column] = pd.to_numeric(roads[column], errors="coerce")
        if numeric_values[column].isna().any():
            raise ValueError(
                f"Canonical inventory column '{column}' must contain numeric values."
            )

    if not numeric_values["pci"].between(0, 100).all():
        raise ValueError("Canonical inventory pci must be between 0 and 100.")

    if not roads["data_status"].eq("Illustrative demonstration data").all():
        raise ValueError(
            "Canonical demonstration inventory must be explicitly marked illustrative."
        )


def enrich_canonical_inventory(roads: pd.DataFrame) -> pd.DataFrame:
    """Normalize treatments and add shared risk fields to validated roads."""

    enriched = roads.copy()
    enriched["recommended_treatment"] = enriched["recommended_treatment"].map(
        normalize_treatment
    )
    details = enriched.apply(
        lambda row: calculate_risk_details(
            condition=row["pci"],
            traffic=row["traffic_level"],
            age=row["age_years"],
            freeze=row["freeze_thaw"],
            pci=row["pci"],
            adt=row["adt"],
        ),
        axis=1,
    )
    enriched["risk_score"] = details.map(lambda detail: detail["score"])
    enriched["risk_level"] = details.map(lambda detail: detail["level"])
    enriched["risk_reason"] = details.map(lambda detail: detail["reason"])
    return enriched


def load_canonical_inventory(path: str | Path) -> pd.DataFrame:
    """Load, validate, and enrich one canonical municipality CSV."""

    roads = pd.read_csv(path)
    validate_canonical_schema(roads)
    return enrich_canonical_inventory(roads)


def to_streamlit_inventory(
    roads: pd.DataFrame,
    municipality_name: str,
) -> pd.DataFrame:
    """Adapt enriched canonical roads to the existing Streamlit UI contract."""

    inventory = roads.rename(columns=_UI_COLUMNS).copy()
    inventory["Condition"] = inventory["PCI"]
    inventory["Risk Score"] = inventory["risk_score"]
    inventory["Risk Level"] = inventory["risk_level"]
    inventory["Risk Reason"] = inventory["risk_reason"]
    inventory["Speed Limit"] = 25
    inventory["County"] = municipality_name
    inventory["Lane Miles"] = inventory["Road Length"] * inventory["Lanes"]
    inventory["Estimated Cost"] = (
        inventory["Lane Miles"] * inventory["treatment_cost_per_lane_mile"]
    )
    return inventory


def load_streamlit_inventory(
    path: str | Path,
    municipality_name: str,
) -> pd.DataFrame:
    """Run the shared canonical-to-Streamlit inventory pipeline."""

    return to_streamlit_inventory(
        load_canonical_inventory(path),
        municipality_name=municipality_name,
    )
